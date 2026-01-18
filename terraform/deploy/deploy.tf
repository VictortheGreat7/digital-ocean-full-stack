resource "kubernetes_namespace_v1" "kronos" {
  metadata {
    name = "kronos"
  }

  depends_on = [digitalocean_kubernetes_cluster.kronos]
}
