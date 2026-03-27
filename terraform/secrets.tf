resource "kubernetes_namespace_v1" "secrets" {
  metadata {
    name = "secrets"
  }

  depends_on = [digitalocean_kubernetes_cluster.kronos]
}

resource "helm_release" "reflector" {
  name             = "reflector"
  repository       = "https://emberstack.github.io/helm-charts"
  chart            = "reflector"
  namespace        = kubernetes_namespace_v1.secrets.metadata[0].name
  create_namespace = false
  atomic           = true
  cleanup_on_fail  = true

  wait    = true
  timeout = 600

  depends_on = [
    digitalocean_kubernetes_cluster.kronos
  ]
}

resource "kubernetes_secret_v1" "cloudflare_api" {
  metadata {
    name      = "cloudflare-api"
    namespace = "secrets"
    annotations = {
      "reflector.v1.k8s.emberstack.com/reflection-auto-enabled"       = "true"
      "reflector.v1.k8s.emberstack.com/reflection-auto-namespaces"    = "cert-manager,kube-system"
      "reflector.v1.k8s.emberstack.com/reflection-allowed"            = "true"
      "reflector.v1.k8s.emberstack.com/reflection-allowed-namespaces" = "cert-manager,kube-system"
    }
  }

  data = {
    api-token = var.cloudflare_api_token
  }

  type = "Opaque"

  depends_on = [helm_release.reflector]
}

resource "kubernetes_secret_v1" "datadog_secret" {
  metadata {
    name      = "datadog-secret"
    namespace = "secrets"
    annotations = {
      "reflector.v1.k8s.emberstack.com/reflection-auto-enabled"       = "true"
      "reflector.v1.k8s.emberstack.com/reflection-auto-namespaces"    = "monitoring"
      "reflector.v1.k8s.emberstack.com/reflection-allowed"            = "true"
      "reflector.v1.k8s.emberstack.com/reflection-allowed-namespaces" = "monitoring"
    }
  }

  data = {
    api-key = var.datadog_api_key
    app-key = var.datadog_app_key
  }

  type = "Opaque"

  depends_on = [helm_release.reflector]
}

resource "kubernetes_secret_v1" "postgres_pass" {
  metadata {
    name      = "postgres-secret"
    namespace = "secrets"
    annotations = {
      "reflector.v1.k8s.emberstack.com/reflection-auto-enabled"       = "true"
      "reflector.v1.k8s.emberstack.com/reflection-auto-namespaces"    = "kronos"
      "reflector.v1.k8s.emberstack.com/reflection-allowed"            = "true"
      "reflector.v1.k8s.emberstack.com/reflection-allowed-namespaces" = "kronos"
    }
  }

  data = {
    password = var.postgres_pass
  }

  type = "Opaque"

  depends_on = [helm_release.reflector]
}

resource "kubernetes_secret_v1" "pgbouncer_auth" {
  metadata {
    name      = "pgbouncer-auth"
    namespace = "secrets"
    annotations = {
      "reflector.v1.k8s.emberstack.com/reflection-auto-enabled"       = "true"
      "reflector.v1.k8s.emberstack.com/reflection-auto-namespaces"    = "kronos"
      "reflector.v1.k8s.emberstack.com/reflection-allowed"            = "true"
      "reflector.v1.k8s.emberstack.com/reflection-allowed-namespaces" = "kronos"
    }
  }

  data = {
    "users.txt" = <<-EOT
      "app" "md5${md5("${var.postgres_pass}app")}"
    EOT
    "exporter_connection_string" = "postgresql://app:${var.postgres_pass}@localhost:5432/pgbouncer?sslmode=disable"
  }

  type = "Opaque"

  depends_on = [helm_release.reflector]
}
