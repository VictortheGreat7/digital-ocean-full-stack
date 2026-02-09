# Install K6 Operator
resource "helm_release" "k6_operator" {
  name             = "k6-operator"
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "k6-operator"
  namespace        = "default"
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
    digitalocean_kubernetes_cluster.kronos
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
            memory = "512Mi"
          }
          limits = {
            cpu    = "300m"
            memory = "1Gi"
          }
        }
        env = [
          {
            name  = "BASE_URL"
            value = "https://${var.subdomains[0]}.${var.domain}"
          },
          {
            name  = "TEST_TYPE"
            value = "load"
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
    kubernetes_manifest.kronos_https_route,
    cloudflare_dns_record.kronos
  ]
}

resource "kubernetes_manifest" "k6_alerts" {
  manifest = {
    apiVersion = "monitoring.coreos.com/v1"
    kind       = "PrometheusRule"
    metadata = {
      name      = "k6-alerts"
      namespace = "monitoring"
      labels = {
        release = "kube-prometheus-stack"
      }
    }
    spec = {
      groups = [
        {
          name     = "k6.critical"
          interval = "30s"
          rules = [
            {
              alert = "ChaosErrorRateCritical"
              expr  = "rate(k6_http_req_failed[5m]) / clamp_min(rate(k6_http_reqs[5m]), 1) > 0.10"
              for   = "2m"
              labels = {
                severity  = "critical"
                test_type = "{{ $labels.test_type }}"
              }
              annotations = {
                summary     = "K6 load test error rate exceeds 10%"
                description = "Error rate is {{ $value | humanizePercentage }} for test type: {{ $labels.test_type }}"
                runbook     = <<-EOT
                  1. Check the k6 load test results for high error rates.
                  2. Investigate application logs for errors.
                  3. Scale up application resources if necessary.
                  4. Rerun the load test after addressing issues.
                EOT
              }
            },
            {
              alert = "ChaosCompleteFailure"
              expr  = "rate(k6_http_req_failed[2m]) / clamp_min(rate(k6_http_reqs[2m]), 1) > 0.90"
              for   = "1m"
              labels = {
                severity  = "critical"
                test_type = "{{ $labels.test_type }}"
              }
              annotations = {
                summary     = "K6 test >90% failure rate"
                description = "{{ $value | humanizePercentage }} of requests failing for test type: {{ $labels.test_type }}"
                runbook     = <<-EOT
                  1. Immediately check application status and logs.
                  2. Identify and resolve critical issues causing high failure rate.
                  3. Consider rolling back recent deployments if needed.
                  4. Notify team and stakeholders.
                EOT
              }
            }
          ]
        },
        {
          name     = "k6.warning"
          interval = "30s"
          rules = [
            {
              alert = "K6ErrorRateHigh"
              expr  = "rate(k6_http_req_failed[5m]) / clamp_min(rate(k6_http_reqs[5m]), 1) > 0.05"
              for   = "3m"
              labels = {
                severity  = "warning"
                test_type = "{{ $labels.test_type }}"
              }
              annotations = {
                summary     = "K6 error rate exceeds 5%"
                description = "Error rate is {{ $value | humanizePercentage }} for test type: {{ $labels.test_type }}"
                runbook     = <<-EOT
                  1. Review k6 load test results for error trends.
                  2. Check logs for 4xx/5xx errors.
                  3. Optimize application performance and error handling.
                  4. Rerun load tests to verify improvements.
                EOT
              }
            },
            {
              alert = "K6P99LatencyHigh"
              expr  = "histogram_quantile(0.99, sum(rate(k6_http_req_duration[5m])) by (le, name)) > 1"
              for   = "3m"
              labels = {
                severity  = "warning"
                test_type = "{{ $labels.test_type }}"
              }
              annotations = {
                summary     = "K6 p99 latency exceeds 1000ms"
                description = "P99 latency is {{ $value }}s for test type: {{ $labels.test_type }}"
                runbook     = <<-EOT
                  1. Analyze k6 load test results for latency.
                  2. Profile performance to find bottlenecks.
                  3. Optimize DB queries, caching, and code.
                  4. Rerun load tests to validate improvements.
                EOT
              }
            },
            {
              alert = "K6P95LatencyHigh"
              expr  = "histogram_quantile(0.95, sum(rate(k6_http_req_duration[5m])) by (le, name)) > 0.5"
              for   = "3m"
              labels = {
                severity  = "warning"
                test_type = "{{ $labels.test_type }}"
              }
              annotations = {
                summary     = "K6 p95 latency exceeds 500ms"
                description = "P95 latency is {{ $value }}s for test type: {{ $labels.test_type }}"
                runbook     = <<-EOT
                  1. Check k6 latency patterns.
                  2. Investigate application components contributing to high latency.
                  3. Apply performance improvements.
                  4. Rerun load tests to validate results.
                EOT
              }
            },
            {
              alert = "K6P50LatencyElevated"
              expr  = "histogram_quantile(0.50, sum(rate(k6_http_req_duration[5m])) by (le, name)) > 0.2"
              for   = "5m"
              labels = {
                severity  = "info"
                test_type = "{{ $labels.test_type }}"
              }
              annotations = {
                summary     = "K6 median latency exceeds 200ms"
                description = "Median latency is {{ $value }}s for test type: {{ $labels.test_type }}"
                runbook     = <<-EOT
                  1. Monitor median latency trends.
                  2. Identify changes affecting performance.
                  3. Apply minor optimizations.
                  4. Continue monitoring subsequent tests.
                EOT
              }
            }
          ]
        },
        {
          name     = "k6.performance"
          interval = "30s"
          rules = [
            {
              alert = "K6ThroughputDrop"
              expr  = "rate(k6_http_reqs[5m]) < 10"
              for   = "5m"
              labels = {
                severity  = "warning"
                test_type = "{{ $labels.test_type }}"
              }
              annotations = {
                summary     = "K6 throughput <10 req/s"
                description = "Current throughput: {{ $value }} RPS for test type: {{ $labels.test_type }}"
              }
            },
            {
              alert = "K6IterationRateLow"
              expr  = "rate(k6_iterations[5m]) < 5"
              for   = "5m"
              labels = {
                severity  = "info"
                test_type = "{{ $labels.test_type }}"
              }
              annotations = {
                summary     = "K6 iteration rate <5 it/s"
                description = "Current iteration rate: {{ $value }} it/s for test type: {{ $labels.test_type }}"
              }
            }
          ]
        }
      ]
    }
  }

  depends_on = [
    kubernetes_manifest.k6_test,
    helm_release.kube_prometheus_stack
  ]
}
