resource "kubernetes_namespace_v1" "kronos" {
  metadata {
    name = "kronos"
  }

  depends_on = [digitalocean_kubernetes_cluster.kronos]
}

resource "kubernetes_config_map_v1" "kronos_config" {
  metadata {
    name      = "${kubernetes_namespace_v1.kronos.metadata[0].name}-config"
    namespace = kubernetes_namespace_v1.kronos.metadata[0].name
  }

  data = {
    TIME_ZONE = "UTC"
  }

  depends_on = [kubernetes_namespace_v1.kronos]
}

resource "kubernetes_config_map_v1" "psql_config" {
  metadata {
    name      = "postgres-init"
    namespace = kubernetes_namespace_v1.kronos.metadata[0].name
  }

  data = {
    "init.sql" = <<-EOF
      CREATE TABLE IF NOT EXISTS requests (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        path VARCHAR(255),
        method VARCHAR(10),
        status INT,
        latency_ms FLOAT,
        timezone VARCHAR(100),
        city VARCHAR(100),
        trace_id VARCHAR(255)
      );

      CREATE INDEX idx_created_at ON requests(created_at DESC);
      CREATE INDEX idx_status ON requests(status);
      CREATE INDEX idx_path ON requests(path);
    EOF
  }

  depends_on = [kubernetes_namespace_v1.kronos]
}

resource "kubernetes_stateful_set_v1" "postgres" {
  metadata {
    name = "postgres"
    namespace = kubernetes_namespace_v1.kronos.metadata[0].name
  }

  spec {
    service_name = "postgres"
    replicas     = 1

    selector {
      match_labels = {
        app = "postgres"
      }
    }

    template {
      metadata {
        labels = {
          app = "postgres"
        }
      }

      spec {
        container {
          name              = "postgres"
          image             = "postgres:15-alpine"
          image_pull_policy = "IfNotPresent"

          port {
            container_port = 5432
            name          = "postgres"
          }

          env {
            name  = "POSTGRES_DB"
            value = "kronos"
          }
          env {
            name  = "POSTGRES_USER"
            value = "app"
          }
          env {
            name  = "POSTGRES_PASSWORD"
            value_from {
              secret_key_ref {
                name = "postgres-secret"
                key  = "password"
              }
            }
          }

          volume_mount {
            name       = "postgres-storage"
            mount_path = "/var/lib/postgresql/data"
            sub_path   = "postgres"
          }
          volume_mount {
            name       = "init-script"
            mount_path = "/docker-entrypoint-initdb.d"
          }

          liveness_probe {
            exec {
              command = ["/bin/sh", "-c", "pg_isready -U app -d kronos"]
            }
            initial_delay_seconds = 30
            period_seconds        = 10
          }
        }

        termination_grace_period_seconds = 300

        volume {
          name = "init-script"
          config_map {
            name = "postgres-init"
          }
        }
      }
    }

    volume_claim_template {
      metadata {
        name = "postgres-storage"
      }

      spec {
        access_modes       = ["ReadWriteOnce"]
        storage_class_name = "do-block-storage"

        resources {
          requests = {
            storage = "5Gi"
          }
        }
      }
    }

    persistent_volume_claim_retention_policy {
      when_deleted = "Delete"
      when_scaled  = "Delete"
    }
  }
}

resource "kubernetes_service_v1" "kronos_postgres" {
  metadata {
    name      = "${kubernetes_namespace_v1.kronos.metadata[0].name}-postgres-svc"
    namespace = kubernetes_namespace_v1.kronos.metadata[0].name
  }

  spec {
    cluster_ip = "None"
    selector = {
      app         = "postgres"
    }

    port {
      port        = 5432
      target_port = 5432
    }

    type = "ClusterIP"
  }

  depends_on = [kubernetes_deployment_v1.kronos_backend]
}

resource "kubernetes_secret_v1" "postgres_secret" {
  metadata {
    name      = "postgres-secret"
    namespace = kubernetes_namespace_v1.kronos.metadata[0].name
  }

  data = {
    password = "dev-password-change-in-prod"
  }

  type = "Opaque"

  depends_on = [helm_release.cert_manager]
}

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
