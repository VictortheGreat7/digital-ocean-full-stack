# Install K6 Operator
resource "helm_release" "k6_operator" {
  name             = "k6-operator"
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "k6-operator"
  namespace        = helm_release.kube_prometheus_stack.namespace
  create_namespace = false

  set = [
    {
      name  = "serviceAccount.create"
      value = "true"
    }
  ]

  depends_on = [helm_release.kube_prometheus_stack,helm_release.alloy]
}

# ConfigMap with K6 test script
resource "kubernetes_config_map_v1" "k6_test_script" {
  metadata {
    name      = "k6-test-script"
    namespace = helm_release.kube_prometheus_stack.namespace
  }

  data = {
    "loadtest.js" = file("${path.module}/loadtest.js")
  }

  depends_on = [helm_release.k6_operator]
}

# Create the K6 CustomResource (test run)
resource "kubernetes_manifest" "k6_loadtest" {
  manifest = {
    apiVersion = "k6.io/v1alpha1"
    kind       = "K6"
    metadata = {
      name      = "kronos-loadtest"
      namespace = helm_release.kube_prometheus_stack.namespace
    }
    spec = {
      parallelism = 4  # Run test on 4 pods in parallel
      script = {
        configMap = {
          name = kubernetes_config_map_v1.k6_test_script.metadata[0].name
          file = "loadtest.js"
        }
      }
      runner = {
        image = "grafana/k6:latest"
      }
      arguments = "--vus 10 --duration 60s"
      env = [
        {
          name  = "BASE_URL"
          value = "${var.subdomains[0]}.${var.domain}/api" # Change to your public URL
        }
      ]
      # Optional: send results to cloud.k6.io
      # cloud = {
      #   projectID = 12345
      # }
    }
  }

  depends_on = [helm_release.k6_operator, kubernetes_config_map_v1.k6_test_script]
}

# Service Monitor to scrape K6 metrics into Prometheus
resource "kubernetes_manifest" "k6_service_monitor" {
  manifest = {
    apiVersion = "monitoring.coreos.com/v1"
    kind       = "ServiceMonitor"
    metadata = {
      name      = "k6-metrics"
      namespace = helm_release.kube_prometheus_stack.namespace
    }
    spec = {
      selector = {
        matchLabels = {
          app = "k6"
        }
      }
      endpoints = [
        {
          port   = "metrics"
          interval = "30s"
        }
      ]
    }
  }

  depends_on = [helm_release.kube_prometheus_stack]
}

# PrometheusRule for K6 alerts
resource "kubernetes_manifest" "k6_alert_rules" {
  manifest = {
    apiVersion = "monitoring.coreos.com/v1"
    kind       = "PrometheusRule"
    metadata = {
      name      = "k6-alerts"
      namespace = helm_release.kube_prometheus_stack.namespace
      labels = {
        prometheus = "kube-prometheus"
      }
    }
    spec = {
      groups = [
        {
          name  = "k6.rules"
          interval = "30s"
          rules = [
            {
              alert = "K6ErrorRateHigh"
              expr  = "k6_errors > 0.05"
              for   = "5m"
              annotations = {
                summary = "K6 load test error rate exceeds 5%"
              }
              labels = {
                severity = "warning"
              }
            },
            {
              alert = "K6P99LatencyHigh"
              expr  = "histogram_quantile(0.99, k6_latency_ms) > 1000"
              for   = "5m"
              annotations = {
                summary = "K6 p99 latency exceeds 1000ms"
              }
              labels = {
                severity = "warning"
              }
            }
          ]
        }
      ]
    }
  }

  depends_on = [helm_release.kube_prometheus_stack]
}

# Grafana Dashboard for K6 results
resource "kubernetes_config_map_v1" "grafana_k6_dashboard" {
  metadata {
    name      = "grafana-k6-dashboard"
    namespace = helm_release.kube_prometheus_stack.namespace
    labels = {
      grafana_dashboard = "1"
    }
  }

  data = {
    "k6-dashboard.json" = jsonencode({
      title = "K6 Load Test Results"
      panels = [
        {
          title = "Request Rate"
          targets = [
            {
              expr = "rate(k6_requests_total[1m])"
            }
          ]
        },
        {
          title = "Error Rate"
          targets = [
            {
              expr = "rate(k6_errors[1m])"
            }
          ]
        },
        {
          title = "Latency p95/p99"
          targets = [
            {
              expr = "histogram_quantile(0.95, k6_latency_ms)"
              legendFormat = "p95"
            },
            {
              expr = "histogram_quantile(0.99, k6_latency_ms)"
              legendFormat = "p99"
            }
          ]
        }
      ]
    })
  }

  depends_on = [helm_release.kube_prometheus_stack]
}