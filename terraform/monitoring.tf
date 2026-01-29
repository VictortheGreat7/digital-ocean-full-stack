resource "helm_release" "kube_prometheus_stack" {
  name             = "kube-prometheus-stack"
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  create_namespace = true
  namespace        = "monitoring"
  atomic           = true
  cleanup_on_fail  = true

  set = [
    # Prometheus settings
    {
      name  = "prometheus.prometheusSpec.resources.requests.cpu"
      value = "500m"
    },
    {
      name  = "prometheus.prometheusSpec.resources.requests.memory"
      value = "1Gi"
    },
    {
      name  = "prometheus.prometheusSpec.resources.limits.cpu"
      value = "1"
    },
    {
      name  = "prometheus.prometheusSpec.resources.limits.memory"
      value = "2Gi"
    },
    {
      name  = "prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.storageClassName"
      value = "do-block-storage"
    },
    {
      name  = "prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage"
      value = "10Gi"
    },
    {
      name  = "prometheus.prometheusSpec.enableRemoteWriteReceiver"
      value = "true"
    },
    {
      name  = "prometheus.prometheusSpec.enableFeatures[0]"
      value = "native-histograms"
    },
    {
      name  = "prometheus.prometheusSpec.enableFeatures[1]"
      value = "exemplar-storage"
    },
    # Prometheus ingress
    {
      name  = "prometheus.ingress.enabled"
      value = "true"
    },
    {
      name  = "prometheus.ingress.ingressClassName"
      value = "nginx"
    },
    {
      name  = "prometheus.ingress.hosts[0]"
      value = "prometheus.${data.kubernetes_service_v1.nginx_ingress.status.0.load_balancer.0.ingress.0.ip}.nip.io"
    },

    # Alertmanager settings
    {
      name  = "alertmanager.enabled"
      value = "true"
    },
    {
      name  = "alertmanager.alertmanagerSpec.resources.requests.cpu"
      value = "100m"
    },
    {
      name  = "alertmanager.alertmanagerSpec.resources.requests.memory"
      value = "256Mi"
    },
    {
      name  = "alertmanager.alertmanagerSpec.resources.limits.cpu"
      value = "200m"
    },
    {
      name  = "alertmanager.alertmanagerSpec.resources.limits.memory"
      value = "512Mi"
    },
    {
      name  = "alertmanager.alertmanagerSpec.storage.volumeClaimTemplate.spec.storageClassName"
      value = "do-block-storage"
    },
    {
      name  = "alertmanager.alertmanagerSpec.storage.volumeClaimTemplate.spec.resources.requests.storage"
      value = "10Gi"
    },
    # Alertmanager ingress
    {
      name  = "alertmanager.ingress.enabled"
      value = "true"
    },
    {
      name  = "alertmanager.ingress.ingressClassName"
      value = "nginx"
    },
    {
      name  = "alertmanager.ingress.hosts[0]"
      value = "alertmanager.${data.kubernetes_service_v1.nginx_ingress.status.0.load_balancer.0.ingress.0.ip}.nip.io"
    },

    # Grafana settings
    {
      name  = "grafana.persistence.enabled"
      value = "true"
    },
    {
      name  = "grafana.resources.requests.cpu"
      value = "100m"
    },
    {
      name  = "grafana.resources.requests.memory"
      value = "256Mi"
    },
    {
      name  = "grafana.resources.limits.cpu"
      value = "200m"
    },
    {
      name  = "grafana.resources.limits.memory"
      value = "512Mi"
    },
    {
      name  = "grafana.persistence.storageClassName"
      value = "do-block-storage"
    },
    {
      name  = "grafana.persistence.size"
      value = "10Gi"
    },
    {
      name  = "grafana.adminPassword"
      value = "admin"
    },
    # Grafana ingress
    {
      name  = "grafana.ingress.enabled"
      value = "true"
    },
    {
      name  = "grafana.ingress.ingressClassName"
      value = "nginx"
    },
    {
      name  = "grafana.ingress.hosts[0]"
      value = "grafana.${data.kubernetes_service_v1.nginx_ingress.status.0.load_balancer.0.ingress.0.ip}.nip.io"
    }
  ]

  wait    = true
  timeout = 600

  depends_on = [module.nginx-controller, helm_release.cert_manager_prod_issuer]
}

resource "helm_release" "tempo" {
  name             = "tempo"
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "tempo"
  namespace        = helm_release.kube_prometheus_stack.namespace
  create_namespace = false
  atomic           = true
  cleanup_on_fail  = true

  set = [
    {
      name  = "tempo.resources.requests.cpu"
      value = "500m"
    },
    {
      name  = "tempo.resources.requests.memory"
      value = "2Gi"
    },
    {
      name  = "tempo.resources.limits.cpu"
      value = "1"
    },
    {
      name  = "tempo.resources.limits.memory"
      value = "4Gi"
    },
    {
      name  = "tempo.memBallastSizeMbs"
      value = "256"
    },
    {
      name  = "tempo.storage.trace.backend"
      value = "local"
    },
    {
      name  = "tempo.storage.trace.local.path"
      value = "/var/tempo/traces"
    },
    {
      name  = "tempo.receivers.otlp.protocols.grpc.endpoint"
      value = "0.0.0.0:4317"
    },
    {
      name  = "tempo.receivers.otlp.protocols.http.endpoint"
      value = "0.0.0.0:4318"
    },
    {
      name  = "tempo.metricsGenerator.enabled"
      value = "true"
    },
    {
      name  = "tempo.metricsGenerator.remoteWriteUrl"
      value = "http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090/api/v1/write"
    },
    {
      name  = "tempo.overrides.defaults.metrics_generator.processors[0]"
      value = "service-graphs"
    },
    {
      name  = "tempo.overrides.defaults.metrics_generator.processors[1]"
      value = "span-metrics"
    },
    {
      name  = "tempo.overrides.defaults.metrics_generator.processors[2]"
      value = "local-blocks"
    },
    {
      name  = "persistence.enabled"
      value = "true"
    },
    {
      name  = "persistence.storageClassName"
      value = "do-block-storage"
    },
    {
      name  = "persistence.size"
      value = "10Gi"
    }
  ]

  depends_on = [helm_release.kube_prometheus_stack, helm_release.cert_manager_prod_issuer]
}

# Configure Grafana to use Tempo as a data source
resource "kubernetes_config_map_v1" "grafana_datasources" {
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
            cpu    = "200m"
            memory = "512Mi"
          }
          limits = {
            cpu    = "400m"
            memory = "1Gi"
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
            memory = "256Mi"
          }
          limits = {
            cpu    = "200m"
            memory = "512Mi"
          }
        }
        configMap = {
          content = <<-EOT
            // discovery.kubernetes allows you to find scrape targets from Kubernetes resources.
            // It watches cluster state and ensures targets are continually synced with what is currently running in your cluste  
            discovery.kubernetes "pods" {
              role = "pod"
            }
            // loki.source.kubernetes tails logs from Kubernetes containers using the Kubernetes API.
            loki.source.kubernetes "pod_logs" {
              targets    = discovery.kubernetes.pods.targets
              forward_to = [loki.process.pod_logs.receiver]
            }
            loki.process "pod_logs" {
              stage.json {
                expressions = {
                  trace_id = "trace_id",
                }
              }
              stage.labels {
                values = {
                  trace_id = "",
                }
              }
              forward_to = [loki.write.loki.receiver]
            }
            loki.source.podlogs "default" {
              forward_to = [loki.write.loki.receiver]
            }

            // loki.source.kubernetes_events tails events from the Kubernetes API and converts them
            // into log lines to forward to other Loki components.
            loki.source.kubernetes_events "cluster_events" {
              job_name   = "integrations/kubernetes/eventhandler"
              log_format = "logfmt"
              forward_to = [loki.process.cluster_events.receiver]
            }
            // loki.process receives log entries from other loki components, applies one or more processing stages,
            // and forwards the results to the list of receivers in the component's arguments.
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

            // Write logs to Loki
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

  set = [
    {
      name  = "datadog.apiKey"
      value = var.datadog_api_key
    },
    {
      name  = "datadog.appKey"
      value = var.datadog_app_key
    },
    {
      name  = "datadog.site"
      value = var.datadog_site
    },
    {
      name  = "datadog.clusterName"
      value = "${digitalocean_kubernetes_cluster.kronos.name}"
    },
    {
      name  = "operator.datadogCRDs.crds.datadogAgents"
      value = "true"
    },
    {
      name  = "operator.datadogCRDs.crds.datadogAgentInternals"
      value = "true"
    },
    {
      name  = "operator.datadogCRDs.crds.datadogDashboards"
      value = "true"
    },
    {
      name  = "operator.datadogAgent.enabled"
      value = "true"
    },
    {
      name  = "operator.datadogAgentInternal.enabled"
      value = "true"
    },
    {
      name  = "operator.datadogDashboard.enabled"
      value = "true"
    }
  ]

  depends_on = [helm_release.kube_prometheus_stack]
}
