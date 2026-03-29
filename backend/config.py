"""
Application configuration — environment variables, constants, and shared settings.
"""

import os


# --- Database ---
DB_CONFIG: dict[str, str] = {
    "host": os.getenv("DB_HOST", "kronos-postgres-svc.kronos.svc.cluster.local"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "kronos"),
    "user": os.getenv("DB_USER", "app"),
    "password": os.getenv("DB_PASSWORD", "dev-password-change-in-prod"),
}

# --- Telemetry ---
OTEL_EXPORTER_OTLP_ENDPOINT: str = os.getenv(
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "http://datadog.monitoring.svc.cluster.local:4318/v1/traces",
)

SERVICE_NAME: str = os.getenv("OTEL_SERVICE_NAME", "kronos-backend")
SERVICE_NAMESPACE: str = os.getenv("SERVICE_NAMESPACE", "kronos")
DEPLOYMENT_ENV: str = os.getenv("DEPLOYMENT_ENV", "dev")
SERVICE_VERSION: str = os.getenv("SERVICE_VERSION", "1.0.0")

# --- Metrics ---
EXCLUDED_PATHS: set[str] = {
    "/metrics",
    "/health",
    "/favicon.ico",
    "/ready",
}

# --- Major Cities ---
MAJOR_CITIES: dict[str, str] = {
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
    "Berlin": "Europe/Berlin",
}

# --- Endpoint-specific Cache TTLs ---
CACHE_TTL_WORLD_CLOCKS: int = int(os.getenv("CACHE_TTL_WORLD_CLOCKS", "2"))
CACHE_TTL_TIMEZONES: int = int(os.getenv("CACHE_TTL_TIMEZONES", "86400"))

# --- Telemetry toggles ---
RUNTIME_METRICS_ENABLED: bool = True if str(os.getenv("DD_RUNTIME_METRICS_ENABLED", "false")) == "true" and str(os.getenv("DD_RUNTIME_METRICS_RUNTIME_ID_ENABLED", "false")) == "true" else False
PROFILER_ENABLED: bool = True if str(os.getenv("DD_PROFILING_ENABLED", "false")) == "true" else False

BATCH_SIZE = 200
BATCH_FLUSH_SECONDS = 0.2