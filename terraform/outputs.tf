output "ssh_command" {
  value = "ssh -i ssh_keys/id_rsa root@${digitalocean_droplet.kronos.ipv4_address}"
}
