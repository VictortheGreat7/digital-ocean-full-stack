resource "kubernetes_manifest" "cilium_gateway" {
  manifest = {
    apiVersion = "gateway.networking.k8s.io/v1"
    kind       = "Gateway"
    metadata = {
      name = "kronos"
      namespace = "kube-system"
      annotations ={
        "cert-manager.io/cluster-issuer" = "letsencrypt-prod"
      }
    }
    spec = {
      gatewayClassName = "cilium"
      listeners = [
        {
          name     = "http"
          protocol = "HTTP"
          port     = 80
          allowedRoutes = {
            namespaces = {
              from = "All"
            }
          }
        },
        {
          name     = "https"
          protocol = "HTTPS"
          port     = 443
          hostname = "${var.subdomains[0]}.${var.domain}"
          tls = {
            mode = "Terminate"
            certificateRefs = [
              {
                name = "kronos-tls"
                group = ""
                kind = "Secret"
              }
            ]
          }
          allowedRoutes = {
            namespaces = {
              from = "All"
            }
          }
        }
      ]
    }
  }

  depends_on = [module.doks]
}

resource "kubernetes_manifest" "kronos_https_route" {
  manifest = {
    apiVersion = kubernetes_manifest.cilium_gateway.manifest["apiVersion"]
    kind       = "HTTPRoute"
    metadata = {
      name      = "kronos-https-route"
      namespace = kubernetes_namespace_v1.kronos.metadata[0].name
    }
    spec = {
      parentRefs = [
        {
          name = kubernetes_manifest.cilium_gateway.manifest["metadata"]["name"]
          sectionName = "https"
        }
      ]
      hostnames = ["${var.subdomains[0]}.${var.domain}"]
      rules = [
        {
          backendRefs = [
            {
              name = kubernetes_service_v1.kronos_frontend.metadata[0].name
              port = kubernetes_service_v1.kronos_frontend.spec[0].port[0].port
            }
          ]
        },
        {
          matches = [
            {
              path = {
                type  = "PathPrefix"
                value = "/api/metrics"
              }
            }
          ]
          filters = [
            {
              type = "URLRewrite"
              urlRewrite = {
                path = {
                  type  = "ReplacePrefixMatch"
                  replacePrefixMatch = "/"
                }
              }
            }
          ]
          backendRefs = [
            {
              name = kubernetes_service_v1.kronos_backend.metadata[0].name
              port = kubernetes_service_v1.kronos_backend.spec[0].port[0].port
            }
          ]
        },
        {
          matches = [
            {
              path = {
                type  = "PathPrefix"
                value = "/api"
              }
            }
          ]
          filters = [
            {
              type = "URLRewrite"
              urlRewrite = {
                path = {
                  type  = "ReplacePrefixMatch"
                  replacePrefixMatch = "/"
                }
              }
            }
          ]
          backendRefs = [
            {
              name = kubernetes_service_v1.kronos_backend.metadata[0].name
              port = kubernetes_service_v1.kronos_backend.spec[0].port[0].port
            }
          ]
        }
      ]
    }
  }

  depends_on = [
    kubernetes_service_v1.kronos_frontend,
    kubernetes_service_v1.kronos_backend,
    kubernetes_manifest.cilium_gateway
  ]
}
