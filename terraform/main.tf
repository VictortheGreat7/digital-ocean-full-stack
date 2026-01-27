resource "random_pet" "kronos" {}

resource "digitalocean_project" "kronos" {
  name        = "kronos"
  description = "Kronos World Clock Project"
  purpose     = "Class project / Educational purposes"
  environment = "Development"
  resources = [
    digitalocean_kubernetes_cluster.kronos.urn
  ]

  depends_on = [
    digitalocean_kubernetes_cluster.kronos
  ]
}

resource "digitalocean_kubernetes_cluster" "kronos" {
  name     = "${random_pet.kronos.id}-cluster"
  region   = var.region
  version  = data.digitalocean_kubernetes_versions.kronos.latest_version
  vpc_uuid = digitalocean_vpc.kronos.id

  node_pool {
    name       = "worker-pool"
    size       = "s-4vcpu-8gb"
    auto_scale = true
    min_nodes  = 1
    max_nodes  = 2
    tags       = [digitalocean_tag.kronos.name]
  }

  auto_upgrade                     = true
  destroy_all_associated_resources = true

  tags = [digitalocean_tag.kronos.name]

}

resource "kubernetes_namespace_v1" "kronos" {
  metadata {
    name = "kronos"
  }

  depends_on = [digitalocean_kubernetes_cluster.kronos]
}
