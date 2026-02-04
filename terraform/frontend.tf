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
              memory = "6Mi"
              cpu    = "40m"
            }
            limits = {
              memory = "7Mi"
              cpu    = "50m"
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

resource "kubernetes_horizontal_pod_autoscaler_v2" "kronos_frontend_hpa" {
  metadata {
    name      = "kronos-frontend-hpa"
    namespace = kubernetes_namespace_v1.kronos.metadata[0].name
  }

  spec {
    scale_target_ref {
      kind = "Deployment"
      name = kubernetes_deployment_v1.kronos_frontend.metadata[0].name
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

  depends_on = [kubernetes_deployment_v1.kronos_frontend]
}
