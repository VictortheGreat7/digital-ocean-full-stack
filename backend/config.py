"""
Application configuration — environment variables, constants, and shared settings.
"""

import os

# --- Telemetry ---
OTEL_EXPORTER_OTLP_ENDPOINT: str = os.getenv(
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "otel-collector.monitoring.svc.cluster.local:4317",
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
