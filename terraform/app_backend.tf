# Backend Deployment
resource "kubernetes_deployment_v1" "kronos_backend" {
  metadata {
    name      = "${kubernetes_namespace_v1.kronos.metadata[0].name}-backend"
    namespace = kubernetes_namespace_v1.kronos.metadata[0].name
    labels = {
      app         = "${kubernetes_namespace_v1.kronos.metadata[0].name}-app"
      component   = "backend"
      environment = "development"
    }
  }

  spec {
    replicas = 3
    strategy {
      type = "RollingUpdate"
      rolling_update {
        max_surge       = "25%"
        max_unavailable = "25%"
      }
    }

    selector {
      match_labels = {
        app         = "${kubernetes_namespace_v1.kronos.metadata[0].name}-app"
        component   = "backend"
        environment = "development"
      }
    }

    template {
      metadata {
        labels = {
          app         = "${kubernetes_namespace_v1.kronos.metadata[0].name}-app"
          component   = "backend"
          environment = "development"
        }
      }

      spec {
        container {
          name  = "backend"
          image = "victorthegreat7/kronos-backend:latest"
          env {
            name = "OTEL_SERVICE_NAME"
            value = "${kubernetes_namespace_v1.kronos.metadata[0].name}-backend"
          }
          env {
            name = "OTEL_K8S_NAMESPACE"
            value_from {
              field_ref {
                api_version = "v1"
                field_path = "metadata.namespace"
              }
            }
          }
          env {
            name = "OTEL_K8S_POD_NAME"
            value_from {
              field_ref {
                api_version = "v1"
                field_path = "metadata.name"
              }
            }
          }
          env {
            name = "OTEL_K8S_NODE_NAME"
            value_from {
              field_ref {
                api_version = "v1"
                field_path = "spec.nodeName"
              }
            }
          }
          env {
            name  = "DEPLOYMENT_ENV"
            value = "dev"
          }
          env {
            name  = "SERVICE_VERSION"
            value = "1.0.0"
          }
          env {
            name  = "OTEL_EXPORTER_OTLP_ENDPOINT"
            value = "http://datadog.monitoring.svc.cluster.local"
          }
          env {
            name = "OTLP_EXPORTER_OTLP_PROTOCOL"
            value = "grpc"
          }
          env {
            name = "OTEL_RESOURCE_ATTRIBUTES"
            value = "service.version=$(SERVICE_VERSION),deployment.environment=$(DEPLOYMENT_ENV),service.name=$(OTEL_SERVICE_NAME),k8s.namespace.name=$(OTEL_K8S_NAMESPACE),k8s.pod.name=$(OTEL_K8S_POD_NAME),host.name=$(OTEL_K8S_NODE_NAME)"
          }
          env {
            name  = "DB_HOST"
            value = "kronos-postgres-svc.kronos.svc.cluster.local"
          }
          env {
            name  = "DB_PORT"
            value = "5432"
          }
          env {
            name  = "DB_NAME"
            value = "kronos"
          }
          env {
            name  = "DB_USER"
            value = "app"
          }
          env {
            name = "DB_PASSWORD"
            value_from {
              secret_key_ref {
                name = "postgres-secret"
                key  = "password"
              }
            }
          }

          port {
            container_port = 5000
          }

          resources {
            requests = {
              memory = "256Mi"
              cpu    = "300m"
            }
            limits = {
              memory = "288Mi"
              cpu    = "400m"
            }
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = 5000
            }
            initial_delay_seconds = 30
            period_seconds        = 15
            timeout_seconds       = 5
            failure_threshold     = 3
          }

          readiness_probe {
            http_get {
              path = "/ready"
              port = 5000
            }
            initial_delay_seconds = 15
            period_seconds        = 5
            timeout_seconds       = 3
            failure_threshold     = 3
          }
        }
      }
    }
  }

  depends_on = [
    kubernetes_namespace_v1.kronos,
    kubernetes_service_v1.kronos_db
  ]
}

# Backend Service
resource "kubernetes_service_v1" "kronos_backend" {
  metadata {
    name      = "${kubernetes_namespace_v1.kronos.metadata[0].name}-backend-svc"
    namespace = kubernetes_namespace_v1.kronos.metadata[0].name
  }

  spec {
    selector = {
      app         = "${kubernetes_namespace_v1.kronos.metadata[0].name}-app"
      component   = "backend"
      environment = "development"
    }

    port {
      protocol    = "TCP"
      port        = 80
      target_port = 5000
    }

    type = "ClusterIP"
  }

  depends_on = [kubernetes_deployment_v1.kronos_backend]
}

resource "kubernetes_horizontal_pod_autoscaler_v2" "kronos_backend_hpa" {
  metadata {
    name      = "kronos-backend-hpa"
    namespace = kubernetes_namespace_v1.kronos.metadata[0].name
  }

  spec {
    min_replicas = 3
    max_replicas = 20

    scale_target_ref {
      kind        = "Deployment"
      name        = kubernetes_deployment_v1.kronos_backend.metadata[0].name
      api_version = "apps/v1"
    }

    behavior {
      scale_down {
        stabilization_window_seconds = 300
        select_policy                = "Min"
        policy {
          period_seconds = 60
          type           = "Pods"
          value          = 1
        }
      }
    }

    metric {
      type = "Resource"
      resource {
        name = "cpu"
        target {
          type                = "Utilization"
          average_utilization = 80
        }
      }
    }
    metric {
      type = "Resource"
      resource {
        name = "memory"
        target {
          type                = "Utilization"
          average_utilization = 80
        }
      }
    }
  }

  depends_on = [kubernetes_deployment_v1.kronos_backend]
}
