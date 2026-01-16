# Frontend Deployment
resource "kubernetes_deployment_v1" "kronos_frontend" {
  metadata {
    name      = "${kubernetes_namespace_v1.kronos.metadata[0].name}-frontend"
    namespace = kubernetes_namespace_v1.kronos.metadata[0].name
    labels = {
      app         = "${kubernetes_namespace_v1.kronos.metadata[0].name}-app"
      component   = "frontend"
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
        component   = "frontend"
        environment = "development"
      }
    }

    template {
      metadata {
        labels = {
          app         = "${kubernetes_namespace_v1.kronos.metadata[0].name}-app"
          component   = "frontend"
          environment = "development"
        }
      }

      spec {
        container {
          name  = "frontend"
          image = "victorthegreat7/kronos-frontend:latest"

          port {
            container_port = 80
          }

          resources {
            requests = {
              memory = "64Mi"
              cpu    = "50m"
            }
            limits = {
              memory = "128Mi"
              cpu    = "100m"
            }
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = 80
            }
            initial_delay_seconds = 10
            period_seconds        = 10
            timeout_seconds       = 5
            failure_threshold     = 3
          }

          readiness_probe {
            http_get {
              path = "/ready"
              port = 80
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

# Frontend Service
resource "kubernetes_service_v1" "kronos_frontend" {
  metadata {
    name      = "${kubernetes_namespace_v1.kronos.metadata[0].name}-frontend-svc"
    namespace = kubernetes_namespace_v1.kronos.metadata[0].name
  }

  spec {
    selector = {
      app         = "${kubernetes_namespace_v1.kronos.metadata[0].name}-app"
      component   = "frontend"
      environment = "development"
    }

    port {
      protocol    = "TCP"
      port        = 80
      target_port = 80
    }

    type = "ClusterIP"
  }

  depends_on = [kubernetes_deployment_v1.kronos_frontend]
}

# # Frontend Load Test
# resource "kubernetes_job_v1" "kronos_frontend" {
#   metadata {
#     name      = "kronos-frontend-test"
#     namespace = "kronos"
#   }

#   spec {
#     template {
#       metadata {
#         name = "kronos-frontend-test"
#       }
#       spec {
#         container {
#           name    = "kronos-frontend-loadtest"
#           image   = "busybox:latest"
#           command = ["/bin/sh", "-c"]
#           args = [<<-EOF
#             echo "Testing frontend service..."
#             for i in $(seq 1 30); do 
#               wget -q -O- http://kronos-frontend-svc.kronos.svc.cluster.local:80/ && 
#               echo "Frontend request $i successful"; 
#               sleep 0.1; 
#             done
#             echo "All frontend tests completed successfully!"
#           EOF
#           ]
#         }
#         restart_policy = "Never"
#       }
#     }
#     backoff_limit           = 4
#     active_deadline_seconds = 300
#   }

#   depends_on = [kubernetes_service_v1.kronos_frontend]
# }