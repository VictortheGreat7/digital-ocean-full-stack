# Multi-stage build for optimized the production image

# Stage 1: Build dependencies and compile Python wheels
FROM python:3.14-slim AS builder

# Disable pip caching, log buffering, and .pyc files.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install build dependencies
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get clean \
    && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Build wheels for all dependencies
RUN pip wheel --wheel-dir /wheels -r requirements.txt


# Stage 2: Create the final runtime image
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
    
# Install runtime dependencies
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get clean \
    && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user to run the application
RUN addgroup --system app && adduser --system --ingroup app app

# Enable Prometheus client to use the multiprocess mode
ENV PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc

# Create the directory and give ownership to the 'app' user
RUN mkdir -p /tmp/prometheus_multiproc && chown app:app /tmp/prometheus_multiproc

WORKDIR /app

# Install dependencies from the built wheels
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links /wheels -r requirements.txt \
    && rm -rf /wheels

# Copy application code and set ownership to the non-root user
COPY --chown=app:app . .

# Make the entrypoint executable
RUN chmod +x entrypoint.sh

# Switch to the non-root user
USER app

ENV GRPC_ENABLE_FORK_SUPPORT=1

# Expose the application port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost/health').read()" || exit 1

# Start the application using the entrypoint script
CMD ["./entrypoint.sh"]