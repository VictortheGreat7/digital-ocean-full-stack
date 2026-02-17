resource "cloudflare_dns_record" "kronos" {
  for_each = toset(var.subdomains)

  zone_id = var.cloudflare_zone_id
  name    = each.value
  type    = "A"
  ttl     = 1
  content = "164.90.255.237"
  proxied = true

  depends_on = [
    helm_release.gateway_argocd
  ]
}
