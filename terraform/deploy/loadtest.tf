# Install K6 Operator
resource "helm_release" "k6_operator" {
  name             = "k6-operator"
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "k6-operator"
  create_namespace = true

  wait = true
  timeout = 600

  depends_on = [helm_release.kube_prometheus_stack, helm_release.alloy]
}

# ConfigMap with K6 test script
resource "kubernetes_config_map_v1" "k6_test_script" {
  metadata {
    name      = "k6-test-script"
    namespace = helm_release.k6_operator.namespace
  }

  data = {
    "loadtest.js" = file("${path.module}/loadtest.js")
  }

  depends_on = [helm_release.k6_operator]
}

resource "helm_release" "k6_test" {
  name       = "k6-test"
  chart      = "./charts/k6-test"
  namespace  = helm_release.k6_operator.namespace

  values = [
    yamlencode({
      baseUrl       = "${var.subdomains[0]}.${var.domain}/api"
      configMapName = kubernetes_config_map_v1.k6_test_script.metadata[0].name
    })
  ]

  depends_on = [
    digitalocean_kubernetes_cluster.kronos,
    helm_release.k6_operator,
    kubernetes_config_map_v1.k6_test_script,
    helm_release.kube_prometheus_stack
  ]
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
              expr         = "histogram_quantile(0.95, k6_latency_ms)"
              legendFormat = "p95"
            },
            {
              expr         = "histogram_quantile(0.99, k6_latency_ms)"
              legendFormat = "p99"
            }
          ]
        }
      ]
    })
  }

  depends_on = [digitalocean_kubernetes_cluster.kronos, helm_release.kube_prometheus_stack]
}