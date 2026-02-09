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
TEMPO_ENDPOINT: str = os.getenv(
    "TEMPO_ENDPOINT", "tempo.monitoring.svc.cluster.local:4317"
)
TEMPO_HTTP_URL: str = os.getenv(
    "TEMPO_HTTP_URL", "http://tempo.monitoring.svc.cluster.local:4318/v1/traces"
)

SERVICE_NAME: str = "kronos-backend"
SERVICE_NAMESPACE: str = "kronos"
DEPLOYMENT_ENV: str = os.getenv("DEPLOYMENT_ENV", "development")

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
