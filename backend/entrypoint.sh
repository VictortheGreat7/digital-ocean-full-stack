#!/bin/sh
set -e

echo "Clearing Prometheus multiproc directory..."
rm -rf /tmp/prometheus_multiproc/*

echo "Starting Gunicorn..."
# Use exec to hand over control to Gunicorn (PID 1)
exec gunicorn --config gunicorn.conf.py "app:create_app()"