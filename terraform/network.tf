resource "digitalocean_vpc" "kronos" {
  name     = "${random_pet.kronos.id}-vnet"
  region   = var.region
  ip_range = "10.240.0.0/16"
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
