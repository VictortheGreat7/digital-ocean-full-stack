# This file contains the main Terraform configuration for creating an Azure Kubernetes Service (AKS) cluster for the Time API application.

resource "random_pet" "kronos" {}

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
      do_api_token        = var.do_token
      k8s_cluster_name    = digitalocean_kubernetes_cluster.kronos.name
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

output "ssh_command" {
  value = "ssh -i ssh_keys/id_rsa root@${digitalocean_droplet.kronos.ipv4_address}"
}