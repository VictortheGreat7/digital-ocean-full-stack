# Runbook: High API Latency (> 500ms)

## Description

This alert triggers when the 99th percentile (p99) latency for the backend API exceeds 500 milliseconds for more than 5 minutes.

**Known Architectural Vulnerability:** The backend currently uses `gevent`. If C-extensions (like `psycopg2` or `grpcio`) are not properly monkey-patched, they will perform synchronous blocking I/O, starving the event loop. This results in the entire worker process freezing, leading to massive latency spikes and request queuing, even if CPU/Memory utilization appears normal or low.

## 📊 Dashboards & Links

* [Datadog APM Dashboard](http://us5.datadoghq.com/)
* [Datadog Continuous Profiler](http://us5.datadoghq.com/) *(Crucial for diagnosing Event Loop blocks)*
* [ArgoCD UI](https://www.google.com/search?q=link-to-argocd)
* [NGINX / Ingress Controller Metrics](https://www.google.com/search?q=link-to-ingress-dashboard)

---

## Triage & Confirmation

1. **Confirm the Spike:** Check the Datadog APM dashboard to confirm the spike is ongoing across multiple pods.
2. **Check Pod Health & Queuing:** Run this command to check if backend pods are struggling, restarting, or maxing out concurrency:\

```bash
kubectl get pods -n kronos -l component=backend
```

3. **Scan for Gridlock Symptoms (Gevent Starvation):** Check backend logs for timeouts, specifically looking for workers failing to heartbeat or trace exporter warnings.

```bash
kubectl logs -n kronos -l component=backend --tail=100 | grep -iE "timeout|critical|worker"
```

4. **Profiler Check:** Open Datadog Continuous Profiler. If you see methods like `SocketMixin.recv` or `_UnaryUnaryMultiCallable._blocking` taking hundreds of milliseconds or seconds, **you are experiencing event loop starvation.**

---

## Mitigation (Stop the Bleeding)

*Execute these steps in order until the system stabilizes. Do not wait for root-cause analysis to mitigate.*

### Level 1: Disable Tracing Overhead (Fastest Mitigation)

If `grpcio` is blocking the event loop, disabling the OpenTelemetry exporter instantly frees up the workers.

```bash
# Inject environment variable to disable OTel exporter dynamically
kubectl set env deployment/kronos-backend -n kronos OTEL_TRACES_EXPORTER=none

```

### Level 2: Aggressive Horizontal Scaling

If requests are queuing up behind blocked workers, you need more OS processes immediately. Bypass the HPA and over-provision.

```bash
# Pause HPA temporarily to prevent it from scaling back down
kubectl patch hpa kronos-backend-hpa -n kronos -p '{"spec":{"paused":true}}'

# Manually blast the replica count to clear the backlog
kubectl scale deployment kronos-backend -n kronos --replicas=30

```

### Level 3: Database Connection Purge

If the database is blocking connections (or PgBouncer is exhausted due to held open connections from frozen workers), restart the backend pods to sever all dead connections.

```bash
kubectl rollout restart deployment kronos-backend -n kronos

```

### Level 4: Load Shedding / Fail-Fast (Ingress Level)

If the backend is completely locked and scaling isn't helping, protect the database and downstream services by dropping requests early.

* Go to the Ingress/Gateway configuration in ArgoCD (or via `kubectl edit`).
* **Reduce the proxy read timeout** from default (e.g., 60s) down to `2s` or `3s`.
* *Result:* Users will see fast 504 Gateway Timeouts instead of holding connections open and cascading the failure.

---

## Investigation (Find the Root Cause)

Once the system is stabilized (latency < 500ms or traffic is successfully load-shedding):

1. **Investigate Database Contention:**

* Check the PostgreSQL metrics in Datadog (`postgresql.connections`). Did we hit the max connection limit?
* Look at Datadog APM Database traces. Find the longest-running query. Even with asynchronous workers, a 5-second raw query (`SocketMixin.recv - 5.38s`) is an application anti-pattern.

2. **Investigate Python Profiler:**

* Validate if `psycogreen` is properly patching `psycopg2`. If database calls are blocking the main thread, the SWEs must patch this.

---

## Escalation & Developer Handoff

* **Time threshold:** If Level 1-3 mitigations do not restore service within 10 minutes, page the **Database Reliability Team**.
* **Post-Incident SWE Handoff:** Regardless of resolution, open a high-priority Jira ticket for the Software Engineering team with the following requirements:

1. **Migrate Exporter:** Switch OpenTelemetry from gRPC to HTTP/Protobuf (`opentelemetry-exporter-otlp-proto-http`) to ensure compatibility with `gevent`.
2. **Implement Psycogreen:** Ensure `psycogreen.gevent.patch_psycopg()` is invoked immediately after the standard gevent monkey patch on app startup.
3. **Query Optimization:** Provide the specific slow SQL query found in Datadog so they can add indices or optimize it.

k6_checks_rate		
k6_data_received_total		
k6_data_sent_total		
k6_group_duration_seconds		
k6_http_req_blocked_seconds		
k6_http_req_connecting_seconds		
k6_http_req_duration_seconds		
k6_http_req_failed_rate		
k6_http_req_receiving_seconds		
k6_http_req_sending_seconds		
k6_http_req_tls_handshaking_seconds		
k6_http_req_waiting_seconds		
k6_http_reqs_total		
k6_iteration_duration_seconds		
k6_iterations_total		
k6_sli_error_budget_burn_rate		
k6_sli_latency_vs_slo_ratio		
k6_sli_request_count_total		
k6_vus		
k6_vus_max		
