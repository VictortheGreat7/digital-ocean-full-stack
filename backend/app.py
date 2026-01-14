from flask import Flask, jsonify, request, g
from flask_cors import CORS
from datetime import datetime
from time import monotonic
import pytz
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Counter, Histogram
from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
# import requests
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
import os

# Configure OpenTelemetry
resource = Resource(attributes={
    "service.name": "kronos-backend",
    "service.version": "1.0.0",
    "deployment.environment": "production"
})

# Set up the tracer provider
tracer_provider = TracerProvider(resource=resource)
trace.set_tracer_provider(tracer_provider)

# Configure OTLP exporter to send traces to Tempo
tempo_endpoint = os.getenv("TEMPO_ENDPOINT", "tempo.monitoring.svc.cluster.local:4317")
otlp_exporter = OTLPSpanExporter(
    endpoint=tempo_endpoint,
    insecure=True  # Use True for internal cluster communication
)

# Add span processor to tracer provider
tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

# Get tracer
tracer = trace.get_tracer(__name__)

app = Flask(__name__)
CORS(app)

# Instrument Flask app with OpenTelemetry
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

metrics = PrometheusMetrics(app)
metrics.info('app_info', 'World Clock Backend Application', version='1.0.0')

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
    # '/favicon.ico',
    '/ready'
]

@app.before_request
def start_timer():
    g.start_time = monotonic()

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
    
    span = trace.get_current_span()
    if span:
        span.set_attribute("http.route", path)
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.status_code", response.status_code)

    return response

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
    """Get current time for a specific timezone"""
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
    """Health check endpoint"""
    return jsonify({"status": "healthy"})

@app.route('/ready', methods=['GET'])
def ready():
    """Readiness check endpoint"""
    return jsonify({"status": "ready"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)