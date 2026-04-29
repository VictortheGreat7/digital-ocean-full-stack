# Post-Mortem: Severe Latency and Timeouts During Spike Test

**Date:** April 29, 2026

**Authors:** Site Reliability Engineering & Backend Teams

**Status:** Complete

## 1. Summary

During a scheduled K6 spike test simulating a traffic spike from a 1,000-user baseline to 1,500 users, the Kronos application experienced severe degradation. The system breached all latency SLO, with maximum response times reaching over 1 minute. Out of a combined 455,382 requests, 182,657 failed due to request timeouts and 500 errors. Investigation revealed that the root cause was a non-functioning HorizontalPodAutoscaler due to the absence of a Metrics API installation in the cluster. This led to a complete lack of pod auto-scaling in response to the load. The incident was resolved by manually installing the Metrics API via `doctl`. The incident lasted approximately 20 minutes, during which the system was unable to meet performance expectations.

## 2. Impact

* **Severity:** SEV-2 (Simulated)
* **User Impact:** None (Test Environment Only)
* **Duration of Incident:** ~20 minutes (Duration of the load test)

## 3. Root Cause

The Metrics Server was not installed in the Kubernetes cluster at the time of the spike test. The HPA (`kronos-backend-hpa`) could not fetch CPU and memory metrics from the metrics API endpoint (`pods.metrics.k8s.io`), resulting in the following error:

```txt
FailedComputeMetricsReplicas: invalid metrics (2 invalid out of 2), first error is: failed to get cpu resource metric value: 
failed to get cpu utilization: unable to get metrics for resource cpu: unable to fetch metrics from resource metrics API: 
the server could not find the requested resource (get pods.metrics.k8s.io)
```

Without valid metrics, the HPA remained at its minimum replica count (1 backend pod) and could not scale out in response to increased load. This resulted in:

- All incoming traffic being routed to a single pod
- Request timeouts due to resource saturation
- 59.78% request failure rate (90,628 failures out of 151,627 requests)
- Response times exceeding 60 seconds (SLO: max 5 seconds for p95)

## 4. Trigger

The spike test was initiated at 12:06:30 UTC as scheduled, ramping from 1,000 to 1,500 concurrent users over 3 minutes. The test was designed to validate system behavior under peak load conditions. However, the infrastructure was not ready to handle the test due to missing Metrics Server installation. The scheduling conflict occurred because:

1. Terraform provisioning had encountered failures earlier
2. ArgoCD was already deployed and managing the cluster
3. The manual step to install the Metrics API addon via Helm was not completed before the test started
4. The test proceeded without waiting for all infrastructure dependencies to be ready

## 5. Resolution

The incident was resolved by manually installing the Metrics Server via doctl command:

```bash
doctl kubernetes 1-click install <DOKS_CLUSTER_ID> --1-clicks metrics-server
```

Once the Metrics Server was deployed and the metrics API became available:

1. HPA successfully retrieved CPU and memory utilization metrics
2. HPA scaled the backend deployment from 1 to 2 replicas at 12:31:30 UTC
3. Request success rate improved as load was distributed across multiple pods
4. Response times normalized back to acceptable levels

ArgoCD `parent` application `helm_release` depends_on [configuration](../../terraform/kcd.tf) was updated to be the last step in the provisioning workflow to delay tests until all cluster dependencies (Metrics Server, Gateway) are installed.

## 6. Detection

The incident was detected through:

1. **Load Test Logs**: K6 test output showed a 59.78% error rate and request timeouts starting at 12:16:00 UTC
2. **Grafana Dashboards**: Real-time loadtest monitoring dashboards displayed a severe spike in latency and error rates
3. **HPA Events**: Multiple `FailedGetResourceMetric` warnings in HPA event logs spanning 51+ minutes
4. **Manual Inspection**: Verification of Metrics API availability revealed the absence of `pods.metrics.k8s.io` resource
5. **Threshold Violations**: K6 thresholds on `http_req_duration` and `http_req_failed` metrics were crossed (error at 12:23:11 UTC)

Post-incident analysis revealed the root cause was evident in HPA logs from the beginning (12:06:30 UTC).

## 7. Action Items

### **Immediate SRE Mitigations (To stabilize the current environment):**

* **[Done]** Install Metrics Server via `doctl kubernetes 1-click install` command
* **[Done]** Verify HPA can retrieve metrics from metrics API
* **[Done]** Monitor backend replica scaling and system recovery

### **Developer Fixes (To prevent recurrence):**

* **[To Do]** Add Metrics Server Installation via `helm_release` to Terraform provisioning workflow (build.yaml line 150)
* **[To Do]** Implement depends_on in ArgoCD `parent` application to delay creation until Metrics Server is fully deployed

### **Long-Term Architecture:**

* **[To Do]** Add initContainer checks to backend deployment to ensure Metrics Server is operational
* **[To Do]** Implement automated dashboard alerting for HPA failures (FailedGetResourceMetric warnings)
* **[To Do]** Document cluster bootstrap dependencies and ordering in deployment runbooks 

## 8. Timeline (UTC)

* **12:06:30** — K6 spike test initiated, starting at 1,000 and ramping up to 1,500 users
* **12:06:30 - 12:23:11** — HPA unable to retrieve metrics; backend deployment remains at 1 replica
* **12:16:00** — First request timeouts appear in K6 logs; system starts experiencing degradation
* **12:16:00 - 12:23:11** — Continuous stream of request failures due to single pod saturation
* **12:23:11** — K6 test completes; threshold violations recorded (http_req_duration, http_req_failed)
* **12:23:30** — Metrics Server manually installed via `doctl kubernetes 1-click install` command
* **12:31:30** — HPA detects valid metrics; scales backend deployment to 2 replicas
* **~12:35:00** — System recovers
* **13:00+** — Post-incident investigation begins; root cause identified as missing Metrics Server installation 