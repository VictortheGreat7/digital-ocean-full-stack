# Install K6 Operator
resource "helm_release" "k6_operator" {
  name             = "k6-operator"
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "k6-operator"
  namespace        = kubernetes_namespace_v1.kronos_test.metadata[0].name
  create_namespace = false
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

  depends_on = [
    digitalocean_kubernetes_cluster.kronos,
    kubernetes_namespace_v1.kronos_test
  ]
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

resource "kubernetes_manifest" "k6_test" {
  manifest = {
    apiVersion = "k6.io/v1alpha1"
    kind       = "TestRun"
    metadata = {
      name      = "kronos-loadtest"
      namespace = helm_release.k6_operator.namespace
    }
    spec = {
      cleanup     = "post"
      parallelism = 5
      runner = {
        image = "grafana/k6:latest"
        resources = {
          requests = {
            cpu    = "250m"
            memory = "256Mi"
          }
          limits = {
            cpu    = "300m"
            memory = "512Mi"
          }
        }
        env = [
          {
            name  = "BASE_URL"
            value = "https://${var.subdomains[0]}.${var.domain}"
          },
          {
            name  = "TEST_TYPE"
            value = "spike"
          },
          {
            name  = "K6_OUT"
            value = "experimental-prometheus-rw"
          },
          {
            name  = "K6_PROMETHEUS_RW_PUSH_INTERVAL"
            value = "10s"
          },
          {
            name  = "K6_PROMETHEUS_RW_SERVER_URL"
            value = "http://kube-prometheus-stack-prometheus.${kubernetes_namespace_v1.kronos_monitoring.metadata[0].name}.svc.cluster.local:9090/api/v1/write"
          },
          {
            name  = "K6_PROMETHEUS_RW_TREND_STATS"
            value = "p(95),p(99),min,max,avg"
          },
          {
            name  = "K6_PROMETHEUS_RW_TREND_AS_NATIVE_HISTOGRAM"
            value = "true"
          }
        ]
      }
      script = {
        configMap = {
          name = kubernetes_config_map_v1.k6_test_script.metadata[0].name
          file = "loadtest.js"
        }
      }
    }
  }

  depends_on = [
    kubernetes_config_map_v1.k6_test_script,
    kubernetes_manifest.kronos_https_route
  ]
}