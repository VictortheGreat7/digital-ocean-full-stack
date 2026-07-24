bind = "0.0.0.0:5000"

workers = 2
worker_class = "gevent"
worker_connections = 250

backlog = 2048
keepalive = 5
timeout = 30
graceful_timeout = 30


def post_fork(server, worker):
    server.log.info(
        "Worker spawned (pid: %s) -> Patching DNS for IPv4 and init OpenTelemetry",
        worker.pid,
    )

    # 0. Force gevent to patch EVERYTHING before any OpenTelemetry/urllib3 imports occur
    import gevent.monkey

    gevent.monkey.patch_all()

    # 1. Implement IPv4 Monkey Patch to prevent gevent breaking DNS
    import socket

    _orig_getaddrinfo = socket.getaddrinfo

    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        # Force family to AF_INET (IPv4)
        if family == 0 or family == socket.AF_UNSPEC:
            family = socket.AF_INET
        return _orig_getaddrinfo(host, port, family, type, proto, flags)

    socket.getaddrinfo = _ipv4_getaddrinfo

    # 2. Re-initialize OpenTelemetry BatchSpanProcessor in the new worker process
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    from telemetry import _otlp_exporter, tracer_provider

    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            _otlp_exporter,
            schedule_delay_millis=2000,
            max_export_batch_size=512,
            max_queue_size=2048,
        )
    )


control_socket_disable = True
