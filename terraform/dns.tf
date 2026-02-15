resource "cloudflare_dns_record" "kronos" {
  for_each = toset(var.subdomains)

  zone_id = var.cloudflare_zone_id
  name    = each.value
  type    = "A"
  ttl     = 1
  content = data.kubernetes_service_v1.cilium_gateway.status[0].load_balancer[0].ingress[0].ip
  proxied = true

  depends_on = [
    helm_release.argocd_apps
  ]
}
