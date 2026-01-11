# This file contains the main Terraform configuration for creating an Azure Kubernetes Service (AKS) cluster for the Time API application.

resource "random_pet" "kronos" {}

resource "digitalocean_project" "kronos" {
  name        = "kronos-project"
  description = "Kronos World Clock Project"
  purpose     = "Class project / Educational purposes"
  environment = "Development"
  resources = [
    digitalocean_tag.kronos.urn,
    digitalocean_vpc.kronos.urn,
    digitalocean_firewall.kronos.urn,
    digitalocean_vpc_nat_gateway.kronos.urn,
    digitalocean_firewall.kronos_bastion.urn,
    digitalocean_droplet.kronos.urn,
    digitalocean_kubernetes_cluster.kronos.urn
  ]

  depends_on = [
    digitalocean_tag.kronos,
    digitalocean_vpc.kronos,
    digitalocean_firewall.kronos,
    digitalocean_vpc_nat_gateway.kronos,
    digitalocean_firewall.kronos_bastion,
    digitalocean_droplet.kronos,
    digitalocean_kubernetes_cluster.kronos
  ]
}

resource "digitalocean_tag" "kronos" {
  name = "kronos"
}

# Create a new Web Droplet in the nyc2 region
resource "digitalocean_droplet" "kronos" {
  image    = "ubuntu-24-04-x64"
  name     = "${random_pet.kronos.id}-bastion"
  region   = var.region
  size     = "s-1vcpu-1gb-intel"
  vpc_uuid = digitalocean_vpc.kronos.id
  user_data = templatefile(
    "${path.module}/cloud-init.yaml.tpl",
    {
      github_runner_token = var.github_runner_token
    }
  )
  ssh_keys          = [53204003]
  graceful_shutdown = true
  backups           = true
  backup_policy {
    plan    = "weekly"
    weekday = "TUE"
    hour    = 8
  }
}