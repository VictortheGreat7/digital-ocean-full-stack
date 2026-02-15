# # Install K6 Operator
# resource "helm_release" "k6_operator" {
#   name             = "k6-operator"
#   repository       = "https://grafana.github.io/helm-charts"
#   chart            = "k6-operator"
#   namespace        = "default"
#   create_namespace = false
#   atomic           = true
#   cleanup_on_fail  = true

#   values = [
#     yamlencode({
#       manager = {
#         resources = {
#           requests = {
#             cpu    = "50m"
#             memory = "128Mi"
#           }
#           limits = {
#             cpu    = "200m"
#             memory = "256Mi"
#           }
#         }
#       }
#     })
#   ]

#   wait    = true
#   timeout = 600

#   depends_on = [
#     digitalocean_kubernetes_cluster.kronos
#   ]
# }

# # ConfigMap with K6 test script
# resource "kubernetes_config_map_v1" "k6_test_script" {
#   metadata {
#     name      = "k6-test-script"
#     namespace = helm_release.k6_operator.namespace
#   }

#   data = {
#     "loadtest.js" = file("${path.module}/scripts/loadtest.js")
#   }

#   depends_on = [helm_release.k6_operator]
# }

# resource "kubernetes_manifest" "k6_test" {
#   manifest = {
#     apiVersion = "k6.io/v1alpha1"
#     kind       = "TestRun"
#     metadata = {
#       name      = "kronos-loadtest"
#       namespace = helm_release.k6_operator.namespace
#     }
#     spec = {
#       cleanup     = "post"
#       parallelism = 5
#       runner = {
#         image = "grafana/k6:latest"
#         resources = {
#           requests = {
#             cpu    = "250m"
#             memory = "512Mi"
#           }
#           limits = {
#             cpu    = "300m"
#             memory = "1Gi"
#           }
#         }
#         env = [
#           {
#             name  = "BASE_URL"
#             value = "https://${var.subdomains[0]}.${var.domain}"
#           },
#           {
#             name  = "TEST_TYPE"
#             value = "stress"
#           },
#           {
#             name  = "K6_OUT"
#             value = "experimental-prometheus-rw"
#           },
#           {
#             name  = "K6_PROMETHEUS_RW_PUSH_INTERVAL"
#             value = "10s"
#           },
#           {
#             name  = "K6_PROMETHEUS_RW_SERVER_URL"
#             value = "http://kube-prometheus-stack-prometheus.${kubernetes_namespace_v1.kronos_monitoring.metadata[0].name}.svc.cluster.local:9090/api/v1/write"
#           },
#           {
#             name  = "K6_PROMETHEUS_RW_TREND_STATS"
#             value = "p(95),p(99),min,max,avg"
#           },
#           {
#             name  = "K6_PROMETHEUS_RW_TREND_AS_NATIVE_HISTOGRAM"
#             value = "true"
#           }
#         ]
#       }
#       script = {
#         configMap = {
#           name = kubernetes_config_map_v1.k6_test_script.metadata[0].name
#           file = "loadtest.js"
#         }
#       }
#     }
#   }

#   depends_on = [
#     kubernetes_config_map_v1.k6_test_script,
#     kubernetes_manifest.kronos_https_route,
#     cloudflare_dns_record.kronos
#   ]
# }

# resource "kubernetes_manifest" "kronos_slos" {
#   manifest = {
#     apiVersion = "monitoring.coreos.com/v1"
#     kind       = "PrometheusRule"
#     metadata = {
#       name      = "kronos-slos"
#       namespace = "monitoring"
#       labels = {
#         release = "kube-prometheus-stack"
#       }
#     }
#     spec = {
#       groups = [
#         {
#           name     = "slo.world_clocks"
#           interval = "30s"
#           rules = [
#             # Availability SLI for /world-clocks
#             {
#               record = "sli:world_clocks:availability:ratio_rate5m"
#               expr   = "1 - (sum(rate(frontend_http_request_errors_total{path=\"/world-clocks\"}[5m])) / clamp_min(sum(rate(frontend_http_request_duration_seconds_count{path=\"/world-clocks\"}[5m])), 1))"
#             },
#             # Latency SLI: % of requests <= 0.5s for /world-clocks
#             {
#               record = "sli:world_clocks:latency_500ms:ratio_rate5m"
#               expr   = "sum(rate(frontend_http_request_duration_seconds_bucket{path=\"/world-clocks\",le=\"0.5\"}[5m])) / clamp_min(sum(rate(frontend_http_request_duration_seconds_count{path=\"/world-clocks\"}[5m])), 1)"
#             },
#             # Error-budget burn rate (99.9% availability budget = 0.001)
#             {
#               record = "burn:world_clocks:availability:1h"
#               expr   = "(1 - sli:world_clocks:availability:ratio_rate5m) / 0.001"
#             },
#             {
#               record = "burn:world_clocks:availability:6h"
#               expr   = "(1 - sli:world_clocks:availability:ratio_rate5m) / 0.001"
#             },
#             # Error-budget burn rate (99% latency budget = 0.01)
#             {
#               record = "burn:world_clocks:latency:1h"
#               expr   = "(1 - sli:world_clocks:latency_500ms:ratio_rate5m) / 0.01"
#             },
#             {
#               record = "burn:world_clocks:latency:6h"
#               expr   = "(1 - sli:world_clocks:latency_500ms:ratio_rate5m) / 0.01"
#             },
#             # Readiness availability SLI (/ready)
#             {
#               record = "sli:ready:availability:ratio_rate5m"
#               expr   = "1 - (sum(rate(frontend_http_request_errors_total{path=\"/ready\"}[5m])) / clamp_min(sum(rate(frontend_http_request_duration_seconds_count{path=\"/ready\"}[5m])), 1))"
#             }
#           ]
#         },
#         {
#           name = "slo.alerts"
#           rules = [
#             {
#               alert = "WorldClocksAvailabilityBurnRateHigh"
#               expr  = "burn:world_clocks:availability:1h > 14.4 and burn:world_clocks:availability:6h > 6"
#               for   = "5m"
#               labels = {
#                 severity = "page"
#               }
#               annotations = {
#                 summary     = "World-clocks availability SLO burn rate high"
#                 description = "Error budget burn rate indicates a likely SLO violation if sustained."
#               }
#             },
#             {
#               alert = "WorldClocksLatencyBurnRateHigh"
#               expr  = "burn:world_clocks:latency:1h > 14.4 and burn:world_clocks:latency:6h > 6"
#               for   = "5m"
#               labels = {
#                 severity = "page"
#               }
#               annotations = {
#                 summary     = "World-clocks latency SLO burn rate high"
#                 description = "Latency budget is being consumed too quickly."
#               }
#             }
#           ]
#         }
#       ]
#     }
#   }

#   depends_on = [
#     kubernetes_manifest.kronos_https_route,
#     helm_release.kube_prometheus_stack
#   ]
# }
