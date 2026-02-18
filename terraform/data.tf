# This file contains the data sources that are used in the Terraform configuration.
data "digitalocean_kubernetes_versions" "kronos" {

  depends_on = [random_pet.kronos]
}

data "digitalocean_kubernetes_cluster" "kronos" {
  name = digitalocean_kubernetes_cluster.kronos.name

  depends_on = [
    random_pet.kronos,
    digitalocean_kubernetes_cluster.kronos,
    data.digitalocean_kubernetes_versions.kronos
  ]
}

data "kubernetes_service_v1" "cilium_gateway" {
  metadata {
    name      = "cilium-gateway-kronos-gateway"
    namespace = "kube-system"
  }

  depends_on = [
    random_pet.kronos,
    helm_release.gateway,
    data.digitalocean_kubernetes_versions.kronos
  ]
}
