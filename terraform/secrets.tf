resource "kubernetes_namespace_v1" "secrets" {
  metadata {
    name = "secrets"
  }

  depends_on = [digitalocean_kubernetes_cluster.kronos]
}

resource "kubernetes_secret_v1" "datadog_api" {
  metadata {
    name      = "datadog-api-key"
    namespace = "secrets"
    annotations = {
      "reflector.v1.k8s.emberstack.com/reflection-allowed" = "true"
      "reflector.v1.k8s.emberstack.com/reflection-allowed-namespaces" = "monitoring"
    }
  }

  data = {
    api-key = var.datadog_api_key
  }

  type = "Opaque"

  depends_on = [kubernetes_namespace_v1.secrets]
}

resource "kubernetes_secret_v1" "datadog_app" {
  metadata {
    name      = "datadog-app-key"
    namespace = "secrets"
    annotations = {
      "reflector.v1.k8s.emberstack.com/reflection-allowed" = "true"
      "reflector.v1.k8s.emberstack.com/reflection-allowed-namespaces" = "monitoring"
    }
  }

  data = {
    app-key = var.datadog_app_key
  }

  type = "Opaque"

  depends_on = [kubernetes_secret_v1.datadog_api]
}

resource "kubernetes_secret_v1" "postgres_pass" {
  metadata {
    name      = "postgres-secret"
    namespace = "secrets"
    annotations = {
      "reflector.v1.k8s.emberstack.com/reflection-allowed" = "true"
      "reflector.v1.k8s.emberstack.com/reflection-allowed-namespaces" = "kronos"
    }
  }

  data = {
    password = var.postgres_pass
  }

  type = "Opaque"

  depends_on = [kubernetes_secret_v1.datadog_app]
}

resource "kubernetes_secret_v1" "cloudflare_api" {
  metadata {
    name      = "cloudflare-api"
    namespace = "secrets"
    annotations = {
      "reflector.v1.k8s.emberstack.com/reflection-allowed" = "true"
      "reflector.v1.k8s.emberstack.com/reflection-allowed-namespaces" = "cert-manager"
    }
  }

  data = {
    api-token = var.cloudflare_api_token
  }

  type = "Opaque"

  depends_on = [kubernetes_secret_v1.postgres_pass]
}
