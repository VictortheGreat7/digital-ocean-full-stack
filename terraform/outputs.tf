output "ssh_command" {
  value = "ssh -i ssh_keys/id_rsa azureuser@${digitalocean_droplet.kronos.ipv4_address}"
}
