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
    replicas = 1
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
            name  = "TEMPO_ENDPOINT"
            value = "tempo.monitoring.svc.cluster.local:4317"
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
    kubernetes_namespace_v1.kronos
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
    scale_target_ref {
      kind = "Deployment"
      name = kubernetes_deployment_v1.kronos_backend.metadata[0].name
      api_version = "apps/v1"
    }

    max_replicas = 5

    metric {
      type = "Resource"
      resource {
        name = "cpu"
        target {
          type               = "Utilization"
          average_utilization = 100
        }
      }
    }
    metric {
      type = "Resource"
      resource {
        name = "memory"
        target {
          type               = "Utilization"
          average_utilization = 100
        }
      }
    }
  }

  depends_on = [kubernetes_deployment_v1.kronos_backend]
}
