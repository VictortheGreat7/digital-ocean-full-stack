# Install K6 Operator
resource "helm_release" "k6_operator" {
  name             = "k6-operator"
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "k6-operator"
  namespace        = "k6"
  create_namespace = true
  atomic           = true
  cleanup_on_fail  = true

  values = [
    yamlencode({
      manager = {
        resources = {
          requests = {
            cpu    = "50m"
            memory = "128Mi"
          }
          limits = {
            cpu    = "200m"
            memory = "256Mi"
          }
        }
      }
    })
  ]

  wait    = true
  timeout = 600

  depends_on = [module.doks]
}

# ConfigMap with K6 test script
resource "kubernetes_config_map_v1" "k6_test_script" {
  metadata {
    name      = "k6-test-script"
    namespace = helm_release.k6_operator.namespace
  }

  data = {
    "loadtest.js" = file("${path.module}/scripts/loadtest.js")
  }

  depends_on = [helm_release.k6_operator]
}

# Grafana Dashboard for K6 results
resource "kubernetes_config_map_v1" "grafana_k6_dashboard" {
  metadata {
    name      = "grafana-k6-dashboard"
    namespace = kubernetes_namespace_v1.kronos_monitoring.metadata[0].name
    labels = {
      grafana_dashboard = "1"
    }
  }

  data = {
    "k6-loadtest.json" = jsonencode({
      title         = "K6 Load Test Results"
      uid           = "k6-loadtest"
      schemaVersion = 39
      version       = 1

      panels = [
        {
          type    = "timeseries"
          title   = "HTTP Request Rate"
          gridPos = { x = 0, y = 0, w = 12, h = 8 }
          targets = [
            {
              expr         = "sum(rate(k6_http_reqs_total[1m]))"
              legendFormat = "req/s"
            }
          ]
        },
        {
          type    = "timeseries"
          title   = "Average HTTP Latency (seconds)"
          gridPos = { x = 12, y = 0, w = 12, h = 8 }
          targets = [
            {
              expr         = "avg(k6_http_req_duration_seconds)"
              legendFormat = "avg latency"
            }
          ]
        },
        {
          type    = "timeseries"
          title   = "Virtual Users"
          gridPos = { x = 0, y = 8, w = 12, h = 8 }
          targets = [
            {
              expr         = "sum(k6_vus)"
              legendFormat = "active VUs"
            }
          ]
        },
        {
          type    = "timeseries"
          title   = "Iterations"
          gridPos = { x = 12, y = 8, w = 12, h = 8 }
          targets = [
            {
              expr         = "sum(rate(k6_iterations_total[1m]))"
              legendFormat = "iterations/s"
            }
          ]
        }
      ]
    })
  }

  depends_on = [kubernetes_namespace_v1.kronos_monitoring]
}