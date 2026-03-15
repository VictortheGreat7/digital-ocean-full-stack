# Post-Mortem: Severe Latency and Timeouts During Stress Test

**Date:** March 15, 2026

**Authors:** Site Reliability Engineering & Backend Teams

**Status:** Complete

## 1. Summary

During a scheduled K6 stress test simulating 5,000 concurrent users, the Kronos application experienced severe degradation. The system breached its 2000ms p(95) latency SLO, with maximum response times reaching ~60 seconds. The `/api/world-clocks` endpoint experienced a 3.7% failure rate due to request timeouts. Deep profiling revealed that the root cause was not simple resource exhaustion, but **event loop starvation** within the application's `gevent` concurrency model, triggered by synchronous C-extensions blocking the worker threads.

## 2. Impact

* **Severity:** SEV-2 (Simulated)
* **User Impact:** 3.7% of total requests failed completely (HTTP 504/503). 49% of API requests breached the 500ms latency threshold. During peak load, backend workers became entirely unresponsive to health checks and incoming requests.
* **Duration of Outage:** ~12 minutes (Duration of the load test)

## 3. Root Cause

The severe latency and timeouts were caused by **head-of-line blocking and event loop starvation** in the Gunicorn/gevent worker processes.

Because `gevent` relies on cooperative multitasking within a single OS thread, any synchronous, blocking I/O operation performed by a C-extension will block the entire OS process, preventing it from serving other concurrent requests. Profiling data captured during the event identified two specific culprits:

1. **Unpatched PostgreSQL Driver:** `psycopg2` was blocking the event loop while waiting for database responses (`SocketMixin.recv` recorded at **5.38s**). Because `psycogreen` was not implemented, the standard `gevent` monkey-patching did not make these database calls asynchronous.
2. **gRPC OpenTelemetry Exporter:** The standard `grpcio` library used for exporting traces is notoriously incompatible with `gevent`. Trace exports were synchronously blocking the thread (`_UnaryUnaryMultiCallable._blocking` recorded at **386ms** per block), heavily degrading the event loop's ability to process traffic.

Consequently, incoming requests queued up at the ingress/socket level until they timed out, despite CPU and Memory metrics not strictly indicating a complete system-level bottleneck.

## 4. Trigger

The initiation of the K6 `stress` profile, which rapidly scaled traffic to 5,000 virtual users. This sudden influx of concurrent requests immediately exposed the asynchronous blocking flaws, gridlocking the available worker pool.

## 5. Resolution

The incident resolved automatically when the K6 load test concluded and traffic dropped to 0, allowing the backlog of blocked network/database sockets to finally clear.

## 6. Detection

The incident was detected automatically by K6 threshold monitors, which marked the test pods as `Error`. Datadog APM captured the massive latency spikes, and Kubernetes metrics noted elevated queueing and eventual pod unresponsiveness.

## 7. Action Items

### **Immediate SRE Mitigations (To stabilize the current environment):**

* **[Done]** **Disable gRPC Tracing:** Temporarily disable the gRPC OpenTelemetry exporter via environment variables (`OTEL_TRACES_EXPORTER=none`) to instantly remove the 386ms blocking overhead from the event loop.
* **[Done]** **Implement Load Shedding:** Reduce timeout thresholds at the Ingress Controller/Load Balancer to 2-3 seconds to fail-fast and prevent massive request backlogs from exhausting database connections.
* **[To Do]** **Tweak Worker Strategy:** Temporarily increase Gunicorn worker counts or evaluate switching the worker class from `gevent` to standard threads (`gthread`) if memory overhead permits, until the asynchronous code is patched.

### **Developer Fixes (To prevent recurrence):**

* **[To Do]** **Implement `psycogreen`:** Update the application initialization code to invoke `psycogreen.gevent.patch_psycopg()` immediately after standard gevent monkey-patching. This will ensure PostgreSQL queries yield to the gevent hub.
* **[To Do]** **Switch OTel Exporter:** Migrate the OpenTelemetry exporter from gRPC to the HTTP/Protobuf variant (`opentelemetry-exporter-otlp-proto-http`), which utilizes standard, gevent-compatible HTTP libraries (like `urllib3`).
* **[To Do]** **Query Optimization:** Investigate the specific database query that resulted in a 5.38s `SocketMixin.recv` block. Even with properly patched async I/O, a 5-second query is an anti-pattern requiring indexing or optimization.

### **Long-Term Architecture:**

* **[To Do]** Introduce PgBouncer to manage PostgreSQL connection pooling securely outside of the Python application.
* **[To Do]** Implement an in-memory cache (Redis) for the `/api/world-clocks` endpoint to reduce overall database load.
* **[To Do]** Review and adjust the Horizontal Pod Autoscaler (HPA) baseline to ensure enough independent processes exist to handle sudden concurrency spikes.

## 8. Timeline (UTC)

* **09:06:30** - K6 load test initiates. Traffic begins ramping up.
* **09:06:30** - First request timeouts observed on `https://kronos.mywonderworks.tech/api/world-clocks`.
* **09:08:04** - Prometheus remote write endpoint begins failing due to metric volume.
* **09:12:08** - K6 test automatically fails and halts pods due to breached latency thresholds (p(95) hit ~14 seconds).
* **09:15:00** - Traffic ceases; system recovers to normal operational baseline.