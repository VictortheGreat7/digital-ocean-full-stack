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
