resource "digitalocean_project" "kronos" {
  name        = "kronos"
  description = "Kronos World Clock Project"
  purpose     = "Class project / Educational purposes"
  environment = "Development"
  resources = [
    digitalocean_droplet.kronos.urn,
    digitalocean_kubernetes_cluster.kronos.urn,
  ]

  depends_on = [
    digitalocean_droplet.kronos,
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

  # control_plane_firewall {
  #   enabled = true
  #   allowed_addresses = [digitalocean_droplet.kronos.ipv4_address]
  # }

  auto_upgrade                     = true
  destroy_all_associated_resources = true

  tags = [digitalocean_tag.kronos.name]

  depends_on = [digitalocean_droplet.kronos]
}

output "doks_cluster_name" {
  value = digitalocean_kubernetes_cluster.kronos.name
}

# provider "kubernetes" {
#   host  = digitalocean_kubernetes_cluster.kronos.endpoint
#   token = digitalocean_kubernetes_cluster.kronos.kube_config[0].token
#   client_certificate = base64decode(
#     digitalocean_kubernetes_cluster.kronos.kube_config[0].client_certificate
#   )
#   client_key = base64decode(
#     digitalocean_kubernetes_cluster.kronos.kube_config[0].client_key
#   )
#   cluster_ca_certificate = base64decode(
#     digitalocean_kubernetes_cluster.kronos.kube_config[0].cluster_ca_certificate
#   )
# }

provider "kubernetes" {
  host  = data.digitalocean_kubernetes_cluster.kronos.endpoint
  token = data.digitalocean_kubernetes_cluster.kronos.kube_config[0].token

  client_certificate = base64decode(
    data.digitalocean_kubernetes_cluster.kronos.kube_config[0].client_certificate
  )
  client_key = base64decode(
    data.digitalocean_kubernetes_cluster.kronos.kube_config[0].client_key
  )
  cluster_ca_certificate = base64decode(
    data.digitalocean_kubernetes_cluster.kronos.kube_config[0].cluster_ca_certificate
  )
}

provider "helm" {
  kubernetes = {
    host  = digitalocean_kubernetes_cluster.kronos.endpoint
    token = digitalocean_kubernetes_cluster.kronos.kube_config[0].token
    client_certificate = base64decode(
      digitalocean_kubernetes_cluster.kronos.kube_config[0].client_certificate
    )
    client_key = base64decode(
      digitalocean_kubernetes_cluster.kronos.kube_config[0].client_key
    )
    cluster_ca_certificate = base64decode(
      digitalocean_kubernetes_cluster.kronos.kube_config[0].cluster_ca_certificate
    )
  }
}

provider "kubectl" {
  host  = digitalocean_kubernetes_cluster.kronos.endpoint
  token = digitalocean_kubernetes_cluster.kronos.kube_config[0].token
  client_certificate = base64decode(
    digitalocean_kubernetes_cluster.kronos.kube_config[0].client_certificate
  )
  client_key = base64decode(
    digitalocean_kubernetes_cluster.kronos.kube_config[0].client_key
  )
  cluster_ca_certificate = base64decode(
    digitalocean_kubernetes_cluster.kronos.kube_config[0].cluster_ca_certificate
  )
}
