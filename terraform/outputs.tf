output "doks_connect" {
  value     = "doctl kubernetes cluster kubeconfig save ${digitalocean_kubernetes_cluster.kronos.name}"
  sensitive = true
}

output "doks_cluster_name" {
  value     = digitalocean_kubernetes_cluster.kronos.name
  sensitive = true
}

output "doks_cluster_id" {
  value     = digitalocean_kubernetes_cluster.kronos.id
  sensitive = true
}
