import os
import pytz
import atexit
import logging
import requests
import psycopg2
from queue import Queue
from flask_cors import CORS
from threading import Thread
from datetime import datetime
from time import monotonic, sleep
from opentelemetry import trace, context
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
from opentelemetry.instrumentation.logging import LoggingInstrumentor

set_global_textmap(TraceContextTextMapPropagator())

# Instantiate a Flask app
app = Flask(__name__)
# Allow CrossOriginResourceSharing
CORS(app)

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
# OpenTelemetry's logging instrumentor (automatic)
LoggingInstrumentor().instrument(set_logging_format=True)

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - [trace_id=%(otelTraceID)s span_id=%(otelSpanID)s] - %(levelname)s - %(message)s'
))
app.logger.handlers.clear()
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

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
    with tracer.start_as_current_span("frontend_traces_forward") as span:
        try:
            trace_data = request.get_data()
            span.set_attribute("trace.size_bytes", len(trace_data))
            headers = {
                'Content-Type': request.headers.get('Content-Type', 'application/x-protobuf')
            }
        
            response = requests.post(
                url=f"http://tempo.monitoring.svc.cluster.local:4318/v1/traces",
                data=trace_data,
                headers=headers,
                timeout=5
            )

            span.set_attribute("tempo.response_status", response.status_code)

            return jsonify({"status": "traces forwarded"}), response.status_code
        except Exception as e:
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
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
    with tracer.start_as_current_span("get_time_endpoint") as span:
        timezone = request.args.get('timezone', 'UTC')
        span.set_attribute("timezone.requested", timezone)
        
        try:
            tz = pytz.timezone(timezone)
            current_time = datetime.now(tz)

            span.set_attribute("timezone.valid", True)
            span.set_attribute("timezone.offset_hours", int(current_time.strftime("%z")[:3]))
            span.set_attribute("timezone.is_dst", bool(current_time.dst())) 
            
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
            span.set_attribute("timezone.valid", False)
            span.set_attribute("error", True)
            span.record_exception(Exception(f"Unknown timezone: {timezone}"))
            return jsonify({"error": "Unknown timezone"}), 400

@app.route('/timezones', methods=['GET'])
def get_timezones():
    """List all available timezones by region"""
    with tracer.start_as_current_span("get_timezones_endpoint") as span:
        all_timezones = pytz.all_timezones
        span.set_attribute("timezone.total_count", len(all_timezones))
        
        # Group timezones by region
        regions = {}
        for tz in all_timezones:
            if '/' in tz:
                region = tz.split('/')[0]
                if region not in regions:
                    regions[region] = []
                regions[region].append(tz)

        span.set_attribute("timezone.regions_count", len(regions))
        
        return jsonify({
            "count": len(all_timezones),
            "regions": regions,
            "common_timezones": pytz.common_timezones
        })

@app.route('/world-clocks', methods=['GET'])
def get_world_clocks():
    """Get time for multiple major cities simultaneously"""
    with tracer.start_as_current_span("get_world_clocks_endpoint") as span:
        cities_data = []
        span.set_attribute("city.requested_count", len(MAJOR_CITIES))
        
        for city, timezone in MAJOR_CITIES.items():
            with tracer.start_as_current_span(f"city_time_fetch.{city.replace(' ', '_')}") as city_span:
                city_span.set_attribute("city.name", city)
                city_span.set_attribute("city.timezone", timezone)

                try:
                    tz = pytz.timezone(timezone)
                    current_time = datetime.now(tz)
                    
                    # Determine if it's day or night (6 AM to 6 PM is day)
                    hour = current_time.hour
                    is_day = 6 <= hour < 18

                    city_span.set_attribute("city.is_day", is_day)
                    city_span.set_attribute("city.hour", hour)
                    
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
                    city_span.set_attribute("error", True)
                    city_span.record_exception(e)
                    cities_data.append({
                        "city": city,
                        "error": str(e)
                    })

        span.set_attribute("city.processed_count", len(cities_data))
        
        return jsonify({
            "cities": cities_data,
            "count": len(cities_data)
        })

# Keep backward compatibility with the old /time endpoint
@app.route('/legacy/time', methods=['GET'])
def get_current_time():
    """Legacy endpoint for backward compatibility"""
    with tracer.start_as_current_span("legacy_get_time_endpoint") as span:
        span.set_attribute("endpoint.deprecated", True)
        span.set_attribute("note", "This is a legacy endpoint, use /time instead")
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return jsonify({"current_time": current_time})

# Provide better health and readiness checks later. Currently simple but insufficient.
@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    with tracer.start_as_current_span("health_check_endpoint") as span:
        try:
            conn = psycopg2.connect(**DB_CONFIG, connect_timeout=2)
            conn.close()
            db_status = "up"
            span.set_attribute("db.status", "healthy")
        except Exception as e:
            db_status = f"unhealthy: {str(e)}"
            span.set_attribute("db.status", "unhealthy")
            span.set_attribute("error", True)
            span.record_exception(e)

        status_code = 200 if db_status == "up" else 500
        span.set_attribute("http.status_code", status_code)
        
        return jsonify({
            "status": "healthy",
            "database": db_status
        }), status_code

@app.route('/ready', methods=['GET'])
def ready():
    """Readiness check endpoint"""
    with tracer.start_as_current_span("readiness_check_endpoint") as span:
        span.set_attribute("readiness.status", "ready")
        return jsonify({"status": "ready"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)