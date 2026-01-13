# This file contains the network resources for the Time API Azure Kubernetes cluster.

resource "digitalocean_vpc" "kronos" {
  name     = "${random_pet.kronos.id}-vnet"
  region   = var.region
  ip_range = "10.240.0.0/16"
  default = false

  lifecycle {
    create_before_destroy = true
    prevent_destroy = true
    ignore_changes = [
      name
    ]
  }

  depends_on = [digitalocean_vpc.default]
}

resource "digitalocean_vpc" "default" {
  name     = "default-vnet"
  region   = var.region
  ip_range = "10.0.0.0/16"
  default = true
}

data "digitalocean_vpc" "default" {
  name = digitalocean_vpc.default.name
}

resource "digitalocean_vpc_nat_gateway" "kronos" {
  name   = "${random_pet.kronos.id}-natgw"
  type   = "PUBLIC"
  region = var.region
  size   = "1"
  vpcs {
    vpc_uuid        = digitalocean_vpc.kronos.id
    default_gateway = true
  }
  tcp_timeout_seconds  = 30
  udp_timeout_seconds  = 30
  icmp_timeout_seconds = 30
}

resource "digitalocean_firewall" "kronos_bastion" {
  name = "${random_pet.kronos.id}-bastion-firewall"

  droplet_ids = [digitalocean_droplet.kronos.id]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = ["0.0.0.0/0"]
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0"]
  }

  outbound_rule {
    protocol              = "icmp"
    destination_addresses = ["0.0.0.0/0"]
  }
}

resource "digitalocean_tag" "kronos" {
  name = "kronos"
}

resource "digitalocean_firewall" "kronos" {
  name = "${random_pet.kronos.id}-firewall"

  tags = [digitalocean_tag.kronos.name]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "443"
    source_addresses = ["0.0.0.0/0"]
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0"]
  }

  outbound_rule {
    protocol              = "icmp"
    destination_addresses = ["0.0.0.0/0"]
  }
}
