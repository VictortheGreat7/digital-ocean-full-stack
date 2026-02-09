resource "helm_release" "kube_prometheus_stack" {
  name             = "kube-prometheus-stack"
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  namespace        = kubernetes_namespace_v1.kronos_monitoring.metadata[0].name
  create_namespace = false
  atomic           = true
  cleanup_on_fail  = true

  values = [
    yamlencode({
      prometheus = {
        prometheusSpec = {
          resources = {
            requests = {
              cpu    = "60m"
              memory = "500Mi"
            }
            limits = {
              cpu    = "70m"
              memory = "600Mi"
            }
          }
          storageSpec = {
            volumeClaimTemplate = {
              spec = {
                storageClassName = "do-block-storage"
                resources = {
                  requests = {
                    storage = "10Gi"
                  }
                }
              }
            }
          }
          enableRemoteWriteReceiver = true
          enableFeatures            = ["native-histograms", "exemplar-storage"]
          externalUrl               = "https://${var.subdomains[0]}.${var.domain}/monitoring/prometheus/"
          routePrefix               = "/"
        }
        route = {
          main = {
            enabled = true
            parentRefs = [{
              name        = "kronos"
              namespace   = "kube-system"
              sectionName = "https"
            }]
            hostnames = ["${var.subdomains[0]}.${var.domain}"]
            matches = [{
              path = {
                type  = "PathPrefix"
                value = "/monitoring/prometheus"
              }
            }]
            filters = [{
              type = "URLRewrite"
              urlRewrite = {
                path = {
                  type               = "ReplacePrefixMatch"
                  replacePrefixMatch = "/"
                }
              }
            }]
          }
        }
      }
      alertmanager = {
        enabled = true
        alertmanagerSpec = {
          resources = {
            requests = {
              cpu    = "1m"
              memory = "50Mi"
            }
            limits = {
              cpu    = "2m"
              memory = "60Mi"
            }
          }
          storage = {
            volumeClaimTemplate = {
              spec = {
                storageClassName = "do-block-storage"
                resources = {
                  requests = {
                    storage = "10Gi"
                  }
                }
              }
            }
          }
          externalUrl = "https://${var.subdomains[0]}.${var.domain}/monitoring/alertmanager/"
          routePrefix = "/"
        }
        route = {
          main = {
            enabled = true
            parentRefs = [{
              name        = "kronos"
              namespace   = "kube-system"
              sectionName = "https"
            }]
            hostnames = ["${var.subdomains[0]}.${var.domain}"]
            matches = [{
              path = {
                type  = "PathPrefix"
                value = "/monitoring/alertmanager"
              }
            }]
            filters = [{
              type = "URLRewrite"
              urlRewrite = {
                path = {
                  type               = "ReplacePrefixMatch"
                  replacePrefixMatch = "/"
                }
              }
            }]
          }
        }
      }
      grafana = {
        persistence = {
          enabled          = true
          storageClassName = "do-block-storage"
          size             = "10Gi"
        }
        resources = {
          limits = {
            cpu    = "40m"
            memory = "256Mi"
          }
          requests = {
            cpu    = "20m"
            memory = "160Mi"
          }
        }
        sidecar = {
          resources = {
            limits = {
              cpu    = "40m",
              memory = "160Mi"
            }
            requests = {
              cpu    = "20m",
              memory = "96Mi"
            }
          }
        }
        adminPassword = "admin"
        "grafana.ini" = {
          server = {
            root_url            = "https://${var.subdomains[0]}.${var.domain}/monitoring/grafana/"
            serve_from_sub_path = true
          }
        }
        route = {
          main = {
            enabled = true
            parentRefs = [{
              name        = "kronos"
              namespace   = "kube-system"
              sectionName = "https"
            }]
            hostnames = ["${var.subdomains[0]}.${var.domain}"]
            matches = [{
              path = {
                type  = "PathPrefix"
                value = "/monitoring/grafana"
              }
            }]
          }
        }
      }
    })
  ]

  wait    = true
  timeout = 600

  depends_on = [kubernetes_manifest.cilium_gateway, helm_release.cert_manager_prod_issuer]
}

resource "helm_release" "tempo" {
  name             = "tempo"
  repository       = "https://grafana-community.github.io/helm-charts"
  chart            = "tempo"
  namespace        = helm_release.kube_prometheus_stack.namespace
  create_namespace = false
  atomic           = true
  cleanup_on_fail  = true

  values = [
    yamlencode({
      tempo = {
        resources = {
          requests = {
            cpu    = "250m"
            memory = "1Gi"
          }
          limits = {
            cpu    = "500m"
            memory = "2Gi"
          }
        }
        memBallastSizeMbs = "256"
        storage = {
          trace = {
            backend = "local"
            local = {
              path = "/var/tempo/traces"
            }
          }
        }
        receivers = {
          otlp = {
            protocols = {
              grpc = {
                endpoint = "0.0.0.0:4317"
              }
              http = {
                endpoint = "0.0.0.0:4318"
              }
            }
          }
        }
        metricsGenerator = {
          enabled        = true
          remoteWriteUrl = "http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090/api/v1/write"
        }
        overrides = {
          defaults = {
            metrics_generator = {
              processors = ["service-graphs", "span-metrics", "local-blocks"]
            }
          }
        }
      }
      persistence = {
        enabled          = true
        storageClassName = "do-block-storage"
        size             = "10Gi"
      }
    })
  ]

  depends_on = [helm_release.kube_prometheus_stack, helm_release.cert_manager_prod_issuer]
}

# Configure Grafana to use Tempo as a data source
resource "kubernetes_config_map_v1" "grafana_tempo_datasources" {
  metadata {
    name      = "grafana-tempo-datasource"
    namespace = helm_release.kube_prometheus_stack.namespace
    labels = {
      grafana_datasource = "1"
    }
  }

  data = {
    "tempo-datasource.yaml" = yamlencode({
      apiVersion = 1
      datasources = [
        {
          name      = "Tempo"
          type      = "tempo"
          access    = "proxy"
          url       = "http://tempo.monitoring:3200"
          isDefault = false
          jsonData = {
            tracesToLogsV2 = {
              datasourceUid = "prometheus"
            }
            tracesToMetrics = {
              datasourceUid = "prometheus"
            }
            serviceMap = {
              datasourceUid = "prometheus"
            }
            nodeGraph = {
              enabled = true
            }
          }
        }
      ]
    })
  }

  depends_on = [helm_release.tempo]
}

resource "helm_release" "loki" {
  name             = "loki"
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "loki"
  namespace        = helm_release.kube_prometheus_stack.namespace
  create_namespace = false
  atomic           = true
  cleanup_on_fail  = true

  values = [
    yamlencode({
      deploymentMode = "SingleBinary"

      loki = {
        auth_enabled = false
        memberlistConfig = {
          join_members = [
            "loki-0.loki-headless.monitoring.svc.cluster.local:7946"
          ]
        }
        commonConfig = {
          replication_factor = 1
          ring = {
            kvstore = {
              store = "inmemory"
            }
          }
        }
        readinessProbe = {
          httpGet = {
            path = "/loki/api/v1/status/buildinfo"
          }
          initialDelaySeconds = 20
        }
        storage = {
          type = "filesystem"
        }
        schemaConfig = {
          configs = [{
            from         = "2026-01-16"
            store        = "tsdb"
            object_store = "filesystem"
            schema       = "v13"
            index = {
              prefix = "index_"
              period = "24h"
            }
          }]
        }
        limits_config = {
          allow_structured_metadata = true
        }
      }

      chunksCache = {
        enabled = false
      }
      resultsCache = {
        enabled = false
      }

      singleBinary = {
        replicas = 1
        resources = {
          requests = {
            cpu    = "50m"
            memory = "512Mi"
          }
          limits = {
            cpu    = "60m"
            memory = "640Mi"
          }
        }
        persistence = {
          enabled          = true
          storageClassName = "do-block-storage"
          size             = "10Gi"
        }
        memberlist = {
          enabled = false
        }
      }

      read = {
        replicas = 0
      }
      write = {
        replicas = 0
      }
      backend = {
        replicas = 0
      }

      monitoring = {
        selfMonitoring = {
          grafanaAgent = {
            installOperator = false
          }
        }
      }
    })
  ]

  depends_on = [helm_release.kube_prometheus_stack, helm_release.cert_manager_prod_issuer]
}

resource "helm_release" "alloy" {
  name             = "alloy"
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "alloy"
  namespace        = helm_release.kube_prometheus_stack.namespace
  create_namespace = false
  atomic           = true
  cleanup_on_fail  = true

  values = [
    yamlencode({
      alloy = {
        resources = {
          requests = {
            cpu    = "100m"
            memory = "100Mi"
          }
          limits = {
            cpu    = "200m"
            memory = "150Mi"
          }
        }
        configMap = {
          content = <<-EOT
            // ── Discover pods ──────────────────────────────────────────
            discovery.kubernetes "pods" {
              role = "pod"
            }

            // ── Relabel: promote K8s metadata into usable labels ──────
            discovery.relabel "pod_labels" {
              targets = discovery.kubernetes.pods.targets

              // Keep namespace
              rule {
                source_labels = ["__meta_kubernetes_namespace"]
                target_label  = "namespace"
              }
              // Keep pod name
              rule {
                source_labels = ["__meta_kubernetes_pod_name"]
                target_label  = "pod"
              }
              // Keep container name
              rule {
                source_labels = ["__meta_kubernetes_pod_container_name"]
                target_label  = "container"
              }
              // Keep app label
              rule {
                source_labels = ["__meta_kubernetes_pod_label_app"]
                target_label  = "app"
              }
              // Keep component label
              rule {
                source_labels = ["__meta_kubernetes_pod_label_component"]
                target_label  = "component"
              }
            }

            // ── Tail container logs ───────────────────────────────────
            loki.source.kubernetes "pod_logs" {
              targets    = discovery.relabel.pod_labels.output
              forward_to = [loki.process.pod_logs.receiver]
            }

            // ── Process: extract trace_id from plain-text logs ────────
            loki.process "pod_logs" {
              // Match your app's format: [trace_id=abc123 span_id=def456]
              stage.regex {
                expression = "\\[trace_id=(?P<trace_id>[0-9a-fA-F]+)\\s+span_id=(?P<span_id>[0-9a-fA-F]+)\\]"
              }

              // Drop the label if it's all zeros (no active trace)
              stage.match {
                selector = "{trace_id=\"0\"}"
                stage.labels {
                  values = {
                    trace_id = "",
                    span_id  = "",
                  }
                }
                action = "drop"
              }

              // Also try JSON extraction for other services that log JSON
              stage.json {
                expressions = {
                  trace_id = "trace_id",
                }
              }

              // Extract log level from your format: "- INFO -", "- ERROR -"
              stage.regex {
                expression = "- (?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL) -"
              }

              // Promote extracted values to labels
              stage.labels {
                values = {
                  trace_id = "",
                  span_id  = "",
                  level    = "",
                }
              }

              // Attach trace_id as structured metadata (for Loki 3.x / schema v13)
              stage.structured_metadata {
                values = {
                  trace_id = "",
                  span_id  = "",
                }
              }

              forward_to = [loki.write.loki.receiver]
            }

            // ── Kubernetes cluster events ─────────────────────────────
            loki.source.kubernetes_events "cluster_events" {
              job_name   = "integrations/kubernetes/eventhandler"
              log_format = "logfmt"
              forward_to = [loki.process.cluster_events.receiver]
            }

            loki.process "cluster_events" {
              forward_to = [loki.write.loki.receiver]
              stage.static_labels {
                values = {
                  cluster = "${data.digitalocean_kubernetes_cluster.kronos.name}",
                }
              }
              stage.labels {
                values = {
                  kubernetes_cluster_events = "job",
                }
              }
            }

            // ── Write to Loki ─────────────────────────────────────────
            loki.write "loki" {
              endpoint {
                url = "http://loki.monitoring:3100/loki/api/v1/push"
              }
            }
          EOT
        }
      }
    })
  ]

  depends_on = [helm_release.loki, helm_release.tempo]
}

resource "kubernetes_config_map_v1" "grafana_loki_datasource" {
  metadata {
    name      = "grafana-loki-datasource"
    namespace = helm_release.kube_prometheus_stack.namespace
    labels = {
      grafana_datasource = "1"
    }
  }

  data = {
    "loki-datasource.yaml" = yamlencode({
      apiVersion = 1
      datasources = [
        {
          name   = "Loki"
          type   = "loki"
          access = "proxy"
          url    = "http://loki.monitoring:3100"
          jsonData = {
            maxLines = 1000
            derivedFields = [
              {
                datasourceUid = "tempo"
                matcherRegex  = "trace_id=(\\w+)"
                name          = "Trace ID"
                url           = "$${__value.raw}"
              }
            ]
          }
        }
      ]
    })
  }

  depends_on = [helm_release.loki]
}

resource "helm_release" "datadog" {
  name             = "datadog"
  repository       = "https://helm.datadoghq.com"
  chart            = "datadog"
  namespace        = "monitoring"
  create_namespace = false
  atomic           = true
  cleanup_on_fail  = true

  values = [
    yamlencode({
      datadog = {
        apiKey = var.datadog_api_key
        appKey = var.datadog_app_key
        site   = var.datadog_site

        clusterName = digitalocean_kubernetes_cluster.kronos.name

        logs = {
          enabled                = true
          containerCollectAll    = true
          autoMultiLineDetection = true
        }

        ignoreAutoConfig = ["cilium"]

        confd = {
          "cilium.yaml" = <<-EOT
            ad_identifiers:
              - cilium-agent
            init_config:
            instances:
              - prometheus_url: http://%%host%%:9090/metrics
                tags:
                  - "component:cilium-agent"
          EOT
        }
      }

      operator = {
        apiKey = var.datadog_api_key
        appKey = var.datadog_app_key

        datadogCRDs = {
          crds = {
            datadogAgents         = true
            datadogAgentInternals = true
            datadogDashboards     = true
          }
        }

        datadogAgent = {
          enabled = true
        }

        datadogAgentInternal = {
          enabled = true
        }

        datadogDashboard = {
          enabled = true
        }

        watchNamespaces = ""
      }
    })
  ]

  depends_on = [helm_release.alloy]
}
