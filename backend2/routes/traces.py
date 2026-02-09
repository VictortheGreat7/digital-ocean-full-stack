"""
Frontend-trace forwarding endpoint.
"""

from __future__ import annotations

import requests as http_requests
from flask import Blueprint, jsonify, request

from config import TEMPO_HTTP_URL
from telemetry import tracer

traces_bp = Blueprint("traces", __name__)


@traces_bp.route("/frontend-traces", methods=["POST"])
def forward_frontend_traces():
    """Proxy OpenTelemetry trace data from the browser to Tempo."""
    with tracer.start_as_current_span("frontend_traces_forward") as span:
        try:
            trace_data = request.get_data()
            span.set_attribute("trace.size_bytes", len(trace_data))

            headers = {
                "Content-Type": request.headers.get(
                    "Content-Type", "application/x-protobuf"
                )
            }

            resp = http_requests.post(
                url=TEMPO_HTTP_URL,
                data=trace_data,
                headers=headers,
                timeout=5,
            )

            span.set_attribute("tempo.response_status", resp.status_code)
            return jsonify({"status": "traces forwarded"}), resp.status_code

        except Exception as exc:
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(exc))
            return jsonify({"error": "Failed to forward traces"}), 500
