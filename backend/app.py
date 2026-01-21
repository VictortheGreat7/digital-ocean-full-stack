import os
import pytz
import atexit
import psycopg2
import requests
from queue import Queue
from flask_cors import CORS
from threading import Thread
from datetime import datetime
from time import monotonic, sleep
from opentelemetry import trace
from opentelemetry import context
from flask import Flask, jsonify, request, g
from opentelemetry.sdk.resources import Resource
from prometheus_client import Counter, Histogram
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.propagate import set_global_textmap
from prometheus_flask_exporter import PrometheusMetrics
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import format_trace_id, NonRecordingSpan
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

# Instantiate a Flask app
app = Flask(__name__)
# Allow CrossOriginResourceSharing
CORS(app)

set_global_textmap(TraceContextTextMapPropagator())

# Identify service sending OpenTelemetry data
resource = Resource(attributes={
    "service.name": "kronos-backend",
    "service.namespace": "kronos",
    "deployment.environment": "development"
})
# Set up the tracer provider
tracer_provider = TracerProvider(resource=resource)
trace.set_tracer_provider(tracer_provider)

# Configure OTLP exporter to send traces to Tempo
tempo_endpoint = os.getenv("TEMPO_ENDPOINT", "tempo.monitoring.svc.cluster.local:4317")
otlp_exporter = OTLPSpanExporter(
    endpoint=tempo_endpoint,
    insecure=True  # True for internal cluster communication
)
# Add span processor to process traces in batches
tracer_provider.add_span_processor(BatchSpanProcessor(
    otlp_exporter,
    schedule_delay_millis=2000,
    max_export_batch_size=512
))
# Get tracer
tracer = trace.get_tracer(__name__)

@atexit.register
def shutdown_tracer():
    tracer_provider.shutdown()

# Watch incoming requests to Flask app
FlaskInstrumentor().instrument_app(app)
# Watch outgoing requests via requests library
RequestsInstrumentor().instrument()
# Watch psycopg2 database connections
Psycopg2Instrumentor().instrument()

# Create /metrics endpoint on the Flask app for Prometheus scraping
metrics = PrometheusMetrics(app)
# Basic static metrics label
metrics.info('app_info', 'World Clock Backend Application', version='1.0.0')

# Database connection config
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "kronos-postgres-svc.kronos.svc.cluster.local"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "kronos"),
    "user": os.getenv("DB_USER", "app"),
    "password": os.getenv("DB_PASSWORD", "dev-password-change-in-prod")
}

# Queue for async user request logging (non-blocking)
log_queue = Queue()

# Background worker thread that writes request logs to DB
def db_worker():
    conn = None

    while True:
        if conn is None:
            try:
                conn = psycopg2.connect(**DB_CONFIG)
                app.logger.info("DB connection established")
            except Exception as e:
                app.logger.error(f"DB connection failed, retrying in 5s: {e}")
                sleep(5)
                continue

        # Get logged user request record
        item = log_queue.get()
        if item is None:
            if conn:
                conn.close()
            break

        record, parent_span_ctx, ctx = item

        # Create a non-recording span from the parent context
        parent_span = trace.NonRecordingSpan(parent_span_ctx)

        token = context.attach(ctx) if ctx else None

        try:
            with tracer.start_as_current_span("db.insert", context=trace.set_span_in_context(parent_span)) as span:
                span.set_attribute("db.operation", "insert")
                span.set_attribute("db.table", "requests")
                
                # Debug logging
                app.logger.info(f"DB span active: {span.is_recording()}, trace_id: {format_trace_id(span.get_span_context().trace_id)}")

                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO requests (path, method, status, latency_ms, timezone, city, trace_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, record)
                    conn.commit()
        except Exception as e:
            app.logger.error(f"DB write error: {e}")
            # On write failure, reset connection
            if conn:
                try:
                    conn.rollback()
                    conn.close()
                except:
                    pass
            conn = None  # Force reconnection
        finally:
            context.detach(token)

# Start background worker thread
db_thread = Thread(target=db_worker, daemon=True)
db_thread.start()

# Save user request start time
@app.before_request
def start_timer():
    g.start_time = monotonic()

# Custom app metrics to track frontend HTTP requests
frontend_http_errors = Counter(
    'frontend_http_request_errors_total',
    'Total frontend HTTP request errors',
    ['method', 'path', 'status']
)
frontend_http_latency = Histogram(
    'frontend_http_request_duration_seconds',
    'Latency of frontend HTTP requests',
    ['method', 'path', 'status']
)
EXCLUDED_PATHS = [
    '/metrics',
    '/health',
    '/favicon.ico',
    '/ready'
]

# Record request metrics and log user requests into db thread queue after each request
@app.after_request
def record_metrics(response):
    if request.path in EXCLUDED_PATHS:
        return response
    
    path = request.url_rule.rule if request.url_rule else request.path
    duration = monotonic() - g.start_time
    status = response.status_code

    frontend_http_latency.labels(
        method=request.method,
        path=path,
        status=status
    ).observe(duration)

    if status >= 400:
        frontend_http_errors.labels(
            method=request.method,
            path=path,
            status=status
        ).inc()
    
    # Add extra details to current trace span
    root_span = trace.get_current_span()
    app.logger.info(f"Current span before SQL: {root_span.get_span_context().trace_id if root_span else 'None'}")

    if root_span:
        root_span.set_attribute("http.route", path)
        root_span.set_attribute("http.method", request.method)
        root_span.set_attribute("http.status_code", status)
    
    trace_id = (
        format_trace_id(root_span.get_span_context().trace_id)
        if root_span and root_span.get_span_context().is_valid
        else None
    )

    ctx = context.get_current()
    
    # Queue the user request log record (non-blocking)
    log_queue.put((
        (
            path,
            request.method,
            status,
            int(duration * 1000),  # latency in ms
            request.args.get('timezone', 'unknown'),
            request.args.get('city', 'unknown'),
            trace_id
        ),
        root_span.get_span_context(),
        ctx
    ))

    return response

# Backend proxy endpoint for frontend to send traces to Tempo
@app.route('/frontend-traces', methods=['POST'])
def frontend_traces():
    try:
        trace_data = request.get_data()
        headers = {
            'Content-Type': request.headers.get('Content-Type', 'application/x-protobuf')
        }
    
        response = requests.post(
            url=f"http://tempo.monitoring.svc.cluster.local:4318/v1/traces",
            data=trace_data,
            headers=headers,
            timeout=5
        )

        return jsonify({"status": "traces forwarded"}), response.status_code
    except Exception as e:
        app.logger.error(f"Error forwarding traces: {e}")
        return jsonify({"error": "Failed to forward traces"}), 500

# Major cities with their timezones
MAJOR_CITIES = {
    "New York": "America/New_York",
    "London": "Europe/London",
    "Tokyo": "Asia/Tokyo",
    "Sydney": "Australia/Sydney",
    "Dubai": "Asia/Dubai",
    "Singapore": "Asia/Singapore",
    "São Paulo": "America/Sao_Paulo",
    "Mumbai": "Asia/Kolkata",
    "Paris": "Europe/Paris",
    "Los Angeles": "America/Los_Angeles",
    "Hong Kong": "Asia/Hong_Kong",
    "Berlin": "Europe/Berlin"
}

@app.route('/time', methods=['GET'])
def get_time():
    """Get current time for a specific timezone or UTC by default"""
    timezone = request.args.get('timezone', 'UTC')
    
    try:
        tz = pytz.timezone(timezone)
        current_time = datetime.now(tz)
        
        return jsonify({
            "timezone": timezone,
            "datetime": current_time.isoformat(),
            "time": current_time.strftime("%H:%M:%S"),
            "date": current_time.strftime("%Y-%m-%d"),
            "day": current_time.strftime("%A"),
            "offset": current_time.strftime("%z"),
            "offset_hours": int(current_time.strftime("%z")[:3]),
            "is_dst": bool(current_time.dst())
        })
    except pytz.exceptions.UnknownTimeZoneError:
        return jsonify({"error": "Unknown timezone"}), 400

@app.route('/timezones', methods=['GET'])
def get_timezones():
    """List all available timezones by region"""
    all_timezones = pytz.all_timezones
    
    # Group timezones by region
    regions = {}
    for tz in all_timezones:
        if '/' in tz:
            region = tz.split('/')[0]
            if region not in regions:
                regions[region] = []
            regions[region].append(tz)
    
    return jsonify({
        "count": len(all_timezones),
        "regions": regions,
        "common_timezones": pytz.common_timezones
    })

@app.route('/world-clocks', methods=['GET'])
def get_world_clocks():
    """Get time for multiple major cities simultaneously"""
    cities_data = []
    
    for city, timezone in MAJOR_CITIES.items():
        try:
            tz = pytz.timezone(timezone)
            current_time = datetime.now(tz)
            
            # Determine if it's day or night (6 AM to 6 PM is day)
            hour = current_time.hour
            is_day = 6 <= hour < 18
            
            cities_data.append({
                "city": city,
                "timezone": timezone,
                "datetime": current_time.isoformat(),
                "time": current_time.strftime("%H:%M:%S"),
                "time_12h": current_time.strftime("%I:%M:%S %p"),
                "date": current_time.strftime("%Y-%m-%d"),
                "day": current_time.strftime("%A"),
                "offset": current_time.strftime("%z"),
                "offset_hours": int(current_time.strftime("%z")[:3]),
                "is_day": is_day,
                "is_dst": bool(current_time.dst())
            })
        except Exception as e:
            cities_data.append({
                "city": city,
                "error": str(e)
            })
    
    return jsonify({
        "cities": cities_data,
        "count": len(cities_data)
    })

# Keep backward compatibility with the old /time endpoint
@app.route('/legacy/time', methods=['GET'])
def get_current_time():
    """Legacy endpoint for backward compatibility"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"current_time": current_time})

# Provide better health and readiness checks later. Currently simple but insufficient.
@app.route('/health', methods=['GET'])
def health():
    try:
        conn = psycopg2.connect(**DB_CONFIG, connect_timeout=2)
        conn.close()
        db_status = "up"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return jsonify({
        "status": "healthy",
        "database": db_status
    }), 200 if db_status == "up" else 500

@app.route('/ready', methods=['GET'])
def ready():
    """Readiness check endpoint"""
    return jsonify({"status": "ready"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)