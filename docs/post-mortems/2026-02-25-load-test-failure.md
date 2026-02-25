# Post-Mortem: Severe Latency and Timeouts During Stress Test

**Date:** February 25, 2026  
**Authors:** [Your Name]  
**Status:** Complete  

## 1. Summary

During a scheduled K6 stress test simulating 5,000 concurrent users, the Kronos application experienced severe degradation. The system breached its 2000ms p(95) latency SLO, with maximum response times reaching ~60 seconds. The `/api/world-clocks` endpoint experienced a 3.7% failure rate due to request timeouts.

## 2. Impact

* **Severity:** SEV-2 (Simulated)
* **User Impact:** 3.7% of total requests failed completely. 49% of API requests breached the 500ms latency threshold.
* **Duration of Outage:** ~12 minutes (Duration of the load test)

## 3. Root Cause

The sheer volume of concurrent requests overwhelmed the backend architecture. Preliminary analysis of Datadog metrics and Kubernetes logs indicates that the backend pods (or the PostgreSQL database) exhausted their available connections or hit CPU limits, causing severe queueing and eventual request timeouts.

## 4. Trigger

The initiation of the K6 `stress` profile, which rapidly scaled traffic to 5,000 virtual users.

## 5. Resolution

The incident resolved automatically when the K6 load test concluded and traffic dropped to 0.

## 6. Detection

The incident was detected automatically by K6 threshold monitors, which marked the test pods as `Error`. Datadog APM and Kubernetes metrics also captured the degradation.

## 7. Action Items

* **[To Do]** Implement an in-memory cache (Redis) for the `/api/world-clocks` endpoint to reduce database load.
* **[To Do]** Introduce PgBouncer to manage PostgreSQL connection pooling.
* **[To Do]** Review and adjust the Horizontal Pod Autoscaler (HPA) and CPU limits for the backend deployment.
* **[To Do]** Increase resources for `kube-prom-stack` to prevent metric dropping during high-load events.

## 8. Timeline (UTC)

* **09:06:30** - K6 load test initiates. Traffic begins ramping up.
* **09:06:30** - First request timeouts observed on `https://kronos.mywonderworks.tech/api/world-clocks`.
* **09:08:04** - Prometheus remote write endpoint begins failing due to metric volume.
* **09:12:08** - K6 test automatically fails and halts pods due to breached latency thresholds (p(95) hit ~14 seconds).
* **09:15:00** - Traffic ceases; system recovers to normal operational baseline.
