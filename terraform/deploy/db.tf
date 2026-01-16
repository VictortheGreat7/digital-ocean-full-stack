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

resource "kubernetes_secret_v1" "postgres_secret" {
  metadata {
    name      = "postgres-secret"
    namespace = kubernetes_namespace_v1.kronos.metadata[0].name
  }

  data = {
    password = "dev-password-change-in-prod"
  }

  type = "Opaque"

  depends_on = [kubernetes_namespace_v1.kronos]
}

resource "kubernetes_stateful_set_v1" "kronos_db" {
  metadata {
    name      = "${kubernetes_namespace_v1.kronos.metadata[0].name}-postgres"
    namespace = kubernetes_namespace_v1.kronos.metadata[0].name
  }

  spec {
    service_name = "postgres"
    replicas     = 1

    selector {
      match_labels = {
        app         = "${kubernetes_namespace_v1.kronos.metadata[0].name}-app"
        component   = "db"
        environment = "development"
      }
    }

    template {
      metadata {
        labels = {
          app         = "${kubernetes_namespace_v1.kronos.metadata[0].name}-app"
          component   = "db"
          environment = "development"
        }
      }

      spec {
        container {
          name              = "postgres"
          image             = "postgres:15-alpine"
          image_pull_policy = "IfNotPresent"

          port {
            container_port = 5432
            name           = "postgres"
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
            name = "POSTGRES_PASSWORD"
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

  depends_on = [
    kubernetes_secret_v1.postgres_secret,
    kubernetes_config_map_v1.psql_config
  ]
}

resource "kubernetes_service_v1" "kronos_db" {
  metadata {
    name      = "${kubernetes_namespace_v1.kronos.metadata[0].name}-postgres-svc"
    namespace = kubernetes_namespace_v1.kronos.metadata[0].name
  }

  spec {
    selector = {
      app         = "${kubernetes_namespace_v1.kronos.metadata[0].name}-app"
      component   = "db"
      environment = "development"
    }

    cluster_ip = "None"

    port {
      port        = 5432
      target_port = 5432
    }

    type = "ClusterIP"
  }

  depends_on = [kubernetes_stateful_set_v1.kronos_db]
}
