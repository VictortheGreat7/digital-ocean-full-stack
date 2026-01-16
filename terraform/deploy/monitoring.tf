resource "helm_release" "kube_prometheus_stack" {
  name             = "kube-prometheus-stack"
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  create_namespace = true
  namespace        = "monitoring"

  set = [
    # Prometheus settings
    {
      name  = "prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.storageClassName"
      value = "do-block-storage"
    },
    {
      name  = "prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage"
      value = "5Gi"
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
      name  = "alertmanager.alertmanagerSpec.storage.volumeClaimTemplate.spec.storageClassName"
      value = "do-block-storage"
    },
    {
      name  = "alertmanager.alertmanagerSpec.storage.volumeClaimTemplate.spec.resources.requests.storage"
      value = "5Gi"
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
      name  = "grafana.persistence.storageClassName"
      value = "do-block-storage"
    },
    {
      name  = "grafana.persistence.size"
      value = "5Gi"
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
  
  wait = true
  timeout = 600

  depends_on = [module.nginx-controller, helm_release.cert_manager_prod_issuer]
}

resource "helm_release" "tempo" {
  name             = "tempo"
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "tempo"
  namespace        = helm_release.kube_prometheus_stack.namespace
  create_namespace = false

  set = [
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
      name  = "persistence.enabled"
      value = "true"
    },
    {
      name  = "persistence.storageClassName"
      value = "do-block-storage"
    },
    {
      name  = "persistence.size"
      value = "5Gi"
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

  values = [
    yamlencode({
      deploymentMode = "SimpleScalable"

      minio = {
        enabled = true
      }

      loki = {
        auth_enabled = false
        
        commonConfig = {
          replication_factor = 1
        }

        storage = {
          type = "s3"
          bucketNames = {
            chunks = "chunks"
            ruler  = "ruler"
            admin  = "admin"
          }
          s3 = {
            endpoint = "http://loki-minio.monitoring.svc.cluster.local:9000"
            secretAccessKey = "loki12345"
            accessKeyId     = "loki"
            s3ForcePathStyle = true
            insecure         = true
          }
        }

        schemaConfig = {
          configs = [{
            from         = "2024-04-01"
            store        = "tsdb"
            object_store = "s3"
            schema       = "v13"
            index = {
              prefix = "index_"
              period = "24h"
            }
          }]
        }
      }

      write = {
        replicas = 2
        persistence = {
          size = "10Gi"
          storageClass = "do-block-storage"
        }
      }
      read = {
        replicas = 2
      }
      backend = {
        replicas = 2
        persistence = {
          size = "10Gi"
          storageClass = "do-block-storage"
        }
      }
    })
  ]

  depends_on = [helm_release.kube_prometheus_stack]
}

resource "helm_release" "alloy" {
  name             = "alloy"
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "alloy"
  namespace        = helm_release.kube_prometheus_stack.namespace
  create_namespace = false

  values = [
    yamlencode({
      alloy = {
        configMap = {
          content = <<-EOT
            // Service discovery for pods
            discovery.kubernetes "pods" {
              role = "pod"
            }

            // Collect logs from pods
            loki.source.kubernetes "pods" {
              targets = discovery.kubernetes.pods.targets
              forward_to = [loki.process.pod_logs.receiver]
            }

            // Process and add labels to pod logs
            loki.process "pod_logs" {
              // Extract JSON logs
              stage.json {
                expressions = {
                  level = "level",
                  timestamp = "timestamp",
                  message   = "message"
                }
                on_error = "keep"
              }

              // Add detected level as a label
              stage.labels {
                values = {
                  level = ""
                }
              }

              forward_to = [loki.write.loki.receiver]
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
