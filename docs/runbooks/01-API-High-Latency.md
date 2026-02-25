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