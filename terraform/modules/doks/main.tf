terraform {
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = ">= 2.72.0"
    }
  }
}

resource "digitalocean_kubernetes_cluster" "module" {
  name     = "${var.random_pet}-cluster"
  region   = var.region
  version  = var.kubernetes_version
  vpc_uuid = var.vpc_uuid

  node_pool {
    name       = var.node_pool_name
    size       = var.node_pool_size
    auto_scale = true
    min_nodes  = var.node_pool_min_nodes
    max_nodes  = var.node_pool_max_nodes
    tags       = [var.tag_name]
  }

  auto_upgrade                     = true
  destroy_all_associated_resources = true

  tags = [var.tag_name]
}

output name {
  value       = digitalocean_kubernetes_cluster.module.name
  sensitive   = false
  description = "The name of the DigitalOcean Kubernetes cluster"
  depends_on  = [digitalocean_kubernetes_cluster.module]
}


output urn {
  value       = digitalocean_kubernetes_cluster.module.urn
  sensitive   = true
  description = "The URN of the DigitalOcean Kubernetes cluster"
  depends_on  = [digitalocean_kubernetes_cluster.module]
}

output api_server_endpoint {
  value       = digitalocean_kubernetes_cluster.module.endpoint
  sensitive   = true
  description = "The API server endpoint of the DigitalOcean Kubernetes cluster"
  depends_on  = [digitalocean_kubernetes_cluster.module]
}

output kubeconfig {
  value       = digitalocean_kubernetes_cluster.module.kube_config[0]
  sensitive   = true
  description = "The kubeconfig of the DigitalOcean Kubernetes cluster"
  depends_on  = [digitalocean_kubernetes_cluster.module]
}

