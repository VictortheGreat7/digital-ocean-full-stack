resource "random_pet" "kronos" {}

module "doks" {
  source = "./modules/doks"

  random_pet          = random_pet.kronos.id
  region              = var.region
  kubernetes_version  = data.digitalocean_kubernetes_versions.kronos.latest_version
  vpc_uuid            = digitalocean_vpc.kronos.id
  node_pool_name      = "kronos-pool"
  node_pool_size      = "s-4vcpu-8gb"
  node_pool_min_nodes = 1
  node_pool_max_nodes = 3
  tag_name            = digitalocean_tag.kronos.name
}

resource "digitalocean_project" "kronos" {
  name        = "kronos"
  description = "Kronos World Clock Project"
  purpose     = "Class project / Educational purposes"
  environment = "Development"
  resources   = [module.doks.urn]

  depends_on = [module.doks]
}

resource "kubernetes_namespace_v1" "kronos" {
  metadata {
    name = "kronos"
  }

  depends_on = [module.doks]
}

resource "kubernetes_namespace_v1" "kronos_monitoring" {
  metadata {
    name = "monitoring"
  }

  depends_on = [module.doks]
}

module "manifests" {
  source = "./modules/manifests"

  doks_host  = module.doks.api_server_endpoint
  doks_token = module.doks.kubeconfig.token
  doks_client_certificate = base64decode(
    module.doks.kubeconfig.client_certificate
  )
  doks_client_key = base64decode(
    module.doks.kubeconfig.client_key
  )
  doks_cluster_ca_certificate = base64decode(
    module.doks.kubeconfig.cluster_ca_certificate
  )

  cilium_gateway_manifest = {
    apiVersion = "gateway.networking.k8s.io/v1"
    kind       = "Gateway"
    metadata = {
      name      = "kronos"
      namespace = "kube-system"
      annotations = {
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
          hostname = "${var.subdomains[0]}.${var.domain}"
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
  kronos_http_route_manifest = {
    apiVersion = "gateway.networking.k8s.io/v1"
    kind       = "HTTPRoute"
    metadata = {
      name      = "kronos-http-route"
      namespace = kubernetes_namespace_v1.kronos.metadata[0].name
    }
    spec = {
      parentRefs = [
        {
          name        = "kronos"
          namespace   = "kube-system"
          sectionName = "http"
        }
      ]
      hostnames = ["${var.subdomains[0]}.${var.domain}"]
      rules = [
        {
          matches = [
            {
              path = {
                type  = "PathPrefix"
                value = "/"
              }
            }
          ]
          filters = [
            {
              type = "RequestRedirect"
              requestRedirect = {
                scheme     = "https"
                statusCode = 301
              }
            }
          ]
        }
      ]
    }
  }
  kronos_https_route_manifest = {
    apiVersion = "gateway.networking.k8s.io/v1"
    kind       = "HTTPRoute"
    metadata = {
      name      = "kronos-https-route"
      namespace = kubernetes_namespace_v1.kronos.metadata[0].name
    }
    spec = {
      parentRefs = [
        {
          name        = "kronos"
          namespace   = "kube-system"
          sectionName = "https"
        }
      ]
      hostnames = ["${var.subdomains[0]}.${var.domain}"]
      rules = [
        {
          matches = [
            {
              path = {
                type  = "PathPrefix"
                value = "/"
              }
            }
          ]
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
                  type               = "ReplacePrefixMatch"
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
                  type               = "ReplacePrefixMatch"
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
  k6_test_manifest = {
    apiVersion = "k6.io/v1alpha1"
    kind       = "TestRun"
    metadata = {
      name      = "kronos-loadtest"
      namespace = helm_release.k6_operator.namespace
    }
    spec = {
      cleanup     = "post"
      parallelism = 5
      runner = {
        image = "grafana/k6:latest"
        resources = {
          requests = {
            cpu    = "250m"
            memory = "256Mi"
          }
          limits = {
            cpu    = "300m"
            memory = "512Mi"
          }
        }
        env = [
          {
            name  = "BASE_URL"
            value = "https://${var.subdomains[0]}.${var.domain}"
          },
          {
            name  = "TEST_TYPE"
            value = "spike"
          },
          {
            name  = "K6_OUT"
            value = "experimental-prometheus-rw"
          },
          {
            name  = "K6_PROMETHEUS_RW_PUSH_INTERVAL"
            value = "10s"
          },
          {
            name  = "K6_PROMETHEUS_RW_SERVER_URL"
            value = "http://kube-prometheus-stack-prometheus.${kubernetes_namespace_v1.kronos_monitoring.metadata[0].name}.svc.cluster.local:9090/api/v1/write"
          },
          {
            name  = "K6_PROMETHEUS_RW_TREND_STATS"
            value = "p(95),p(99),min,max,avg"
          },
          {
            name  = "K6_PROMETHEUS_RW_TREND_AS_NATIVE_HISTOGRAM"
            value = "true"
          }
        ]
      }
      script = {
        configMap = {
          name = kubernetes_config_map_v1.k6_test_script.metadata[0].name
          file = "loadtest.js"
        }
      }
    }
  }
}
