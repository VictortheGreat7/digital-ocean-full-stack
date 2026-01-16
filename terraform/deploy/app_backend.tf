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
              memory = "128Mi"
              cpu    = "100m"
            }
            limits = {
              memory = "256Mi"
              cpu    = "200m"
            }
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = 5000
            }
            initial_delay_seconds = 10
            period_seconds        = 10
            timeout_seconds       = 5
            failure_threshold     = 3
          }

          readiness_probe {
            http_get {
              path = "/ready"
              port = 5000
            }
            initial_delay_seconds = 5
            period_seconds        = 5
            timeout_seconds       = 5
            failure_threshold     = 3
          }
        }
      }
    }
  }

  depends_on = [
    module.nginx-controller,
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


# # Backend Load Test
# resource "kubernetes_job_v1" "kronos_backend" {
#   metadata {
#     name      = "kronos-backend-test"
#     namespace = "kronos"
#   }

#   spec {
#     template {
#       metadata {
#         name = "kronos-backend-test"
#       }
#       spec {
#         container {
#           name    = "kronos-backend-loadtest"
#           image   = "busybox:latest"
#           command = ["/bin/sh", "-c"]
#           args = [<<-EOF
#             echo "Testing backend API endpoints..."
#             for i in $(seq 1 30); do 
#               wget -q -O- http://kronos-backend-svc.kronos.svc.cluster.local:80/api/world-clocks && 
#               echo "Backend request $i successful" || echo "Backend request $i failed"; 
#               sleep 0.1; 
#             done
#             echo "All backend tests completed successfully!"
#           EOF
#           ]
#         }
#         restart_policy = "Never"
#       }
#     }
#     backoff_limit           = 4
#     active_deadline_seconds = 300
#   }

#   depends_on = [kubernetes_service_v1.kronos_backend]
# }