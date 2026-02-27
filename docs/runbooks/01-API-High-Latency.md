# Runbook: High API Latency (> 2000ms)

## 🚨 Description

This alert triggers when the 95th percentile (p95) latency for the backend API exceeds 2 seconds for more than 5 minutes.

## 📊 Dashboards & Links

* [Datadog APM Dashboard](link-to-your-datadog)
* [ArgoCD UI](link-to-argocd)

## 🩺 Triage & Confirmation

1. Check the Datadog APM dashboard to confirm the spike is ongoing.
2. Run this command to check if the backend pods are struggling or restarting:
   `kubectl get pods -n kronos -l app=backend`
3. Check if the database is overwhelmed:
   `kubectl logs -n kronos -l app=backend | grep -i "timeout"`

## 🩹 Mitigation (Stop the Bleeding)

If the backend pods are overwhelmed, manually scale up the deployment temporarily until the autoscaler catches up:
`kubectl scale deployment backend -n kronos --replicas=10`

If the database is blocking connections, restart the backend pods to clear dead connection pools:
`kubectl rollout restart deployment backend -n kronos`

## 🕵️ Investigation (Find the Root Cause)

* Check the PostgreSQL database metrics in Datadog (`postgresql.connections`). Are we hitting the connection limit?
* Look at the APM traces in Datadog: Is the slowdown happening in the application logic, or is it waiting on a specific database query?

## 📞 Escalation

If scaling up does not resolve the issue within 10 minutes, escalate to the Database Reliability team.

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
