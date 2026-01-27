# Install K6 Operator
resource "helm_release" "k6_operator" {
  name             = "k6-operator"
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "k6-operator"
  namespace        = "default"
  create_namespace = false

  set = [
    {
      name  = "manager.resources.requests.cpu"
      value = "50m"
    },
    {
      name  = "manager.resources.requests.memory"
      value = "128Mi"
    },
    {
      name  = "manager.resources.limits.cpu"
      value = "200m"
    },
    {
      name  = "manager.resources.limits.memory"
      value = "256Mi"
    }
  ]

  wait    = true
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
    "loadtest.js" = file("${path.module}/scripts/loadtest.js")
  }

  depends_on = [helm_release.k6_operator]
}

resource "helm_release" "k6_test" {
  name      = "k6-test"
  chart     = "./charts/k6-test"
  namespace = helm_release.k6_operator.namespace

  values = [
    yamlencode({
      baseUrl             = "https://${var.subdomains[0]}.${var.domain}"
      testType            = "stress"
      configMapName       = kubernetes_config_map_v1.k6_test_script.metadata[0].name
      prometheusNamespace = helm_release.kube_prometheus_stack.namespace
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

  depends_on = [digitalocean_kubernetes_cluster.kronos, helm_release.kube_prometheus_stack]
}