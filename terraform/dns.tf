resource "kubernetes_secret_v1" "cloudflare_api" {
  metadata {
    name      = "cloudflare-api"
    namespace = helm_release.cert_manager.namespace
  }

  data = {
    api-token = var.cloudflare_api_token
  }

  type = "Opaque"

  depends_on = [helm_release.cert_manager]
}

resource "cloudflare_dns_record" "kronos" {
  for_each = toset(var.subdomains)

  zone_id = var.cloudflare_zone_id
  name    = each.value
  type    = "A"
  ttl     = 1
  content = data.kubernetes_service_v1.nginx_ingress.status[0].load_balancer[0].ingress[0].ip
  proxied = true

  depends_on = [module.nginx-controller]
}
