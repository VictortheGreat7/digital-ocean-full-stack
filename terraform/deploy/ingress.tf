# Ingress Webhook Check: This makes sure the ingress controller's admission webhook is ready before creating ingress resources.
resource "null_resource" "wait_for_ingress_webhook" {
  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -e

      wget https://github.com/digitalocean/doctl/releases/download/v1.146.0/doctl-1.146.0-linux-amd64.tar.gz -O doctl.tar.gz
      tar xf doctl.tar.gz

      # Install locally (no root)
      mkdir -p $HOME/bin
      mv doctl $HOME/bin/
      export PATH=$HOME/bin:$PATH

      curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
      chmod +x kubectl
      mv kubectl $HOME/bin/
      export PATH=$HOME/bin:$PATH

      doctl auth init -t ${var.do_token}

      doctl kubernetes cluster kubeconfig save ${digitalocean_kubernetes_cluster.kronos.name} --access-token ${var.do_token}

      echo "Waiting for ingress-nginx-controller DaemonSet pods to be ready..."
      for i in {1..100}; do
        READY=$(kubectl get daemonset ingress-nginx-controller -n kube-system -o jsonpath='{.status.numberReady}')

        echo "Attempt $i: $READY pods ready"

        if [[ "$READY" -ge 1 ]]; then
          echo "At least one DaemonSet pod is ready"
          break
        fi

        if [[ "$i" -eq 100 ]]; then
          echo "Timed out waiting for at least one DaemonSet pod to be ready"
          exit 1
        fi

        sleep 10
      done


      echo "Waiting for admission webhook to be ready..."
      for i in {1..100}; do
        echo "Checking webhook readiness... attempt $i"
        if kubectl get endpoints ingress-nginx-controller-admission -n kube-system -o jsonpath='{.subsets[*].addresses[*].ip}' | grep -q .; then
          echo "Webhook server is ready"
          exit 0
        fi
        sleep 10
      done

      echo "Timed out waiting for ingress-nginx admission webhook"
      exit 1
    EOT
  }

  depends_on = [module.nginx-controller]
}

# Service Account for Ingress Webhook Check
resource "kubernetes_service_account_v1" "check_ingress_sa" {
  metadata {
    name      = "check-ingress-sa"
    namespace = "kube-system"
  }

  depends_on = [null_resource.wait_for_ingress_webhook]
}

# Role for Ingress Check Service Account
resource "kubernetes_role_v1" "check_ingress_role" {
  metadata {
    name      = "check-ingress-role"
    namespace = "kube-system"
  }

  rule {
    api_groups = [""]
    resources  = ["endpoints"]
    verbs      = ["get", "list"]
  }

  depends_on = [kubernetes_service_account_v1.check_ingress_sa]
}

# Role Binding for Ingress Check Service Account
resource "kubernetes_role_binding_v1" "check_ingress_binding" {
  metadata {
    name      = "check-ingress-binding"
    namespace = "kube-system"
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role_v1.check_ingress_role.metadata[0].name
  }

  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account_v1.check_ingress_sa.metadata[0].name
    namespace = "kube-system"
  }

  depends_on = [kubernetes_role_v1.check_ingress_role]
}

# Ingress Webhook Check Job
resource "kubernetes_job_v1" "wait_for_ingress_webhook" {
  metadata {
    name      = "check-ingress-webhook"
    namespace = "kube-system"
  }

  spec {
    template {
      metadata {
        name = "ingress-webhook-test"
      }
      spec {
        service_account_name = kubernetes_service_account_v1.check_ingress_sa.metadata[0].name
        container {
          name    = "check"
          image   = "bitnami/kubectl:latest"
          command = ["/bin/bash", "-c"]
          args = [
            <<-EOC
            kubectl auth can-i get endpoints -n kube-system
            for i in {1..100}; do
              echo "Checking for webhook admission endpoint..."
              IP=$(kubectl get endpoints ingress-nginx-controller-admission -n kube-system -o jsonpath='{.subsets[*].addresses[*].ip}')
              if [[ ! -z "$IP" ]]; then
                echo "Admission webhook is ready"
                exit 0
              fi
              echo "Attempt $i: Admission webhook not ready yet"
              sleep 10
            done
            echo "Timed out waiting for admission webhook"
            exit 1
            EOC
          ]
        }
        restart_policy = "Never"
      }
    }
    backoff_limit           = 4
    active_deadline_seconds = 1000
  }

  depends_on = [null_resource.wait_for_ingress_webhook]
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

resource "helm_release" "cert_manager" {
  name       = "cert-manager"
  repository = "https://charts.jetstack.io"
  chart      = "cert-manager"
  version    = "v1.19.2"

  create_namespace = true
  namespace        = "cert-manager"

  set = [
    {
      name  = "installCRDs"
      value = "true"
    }
  ]

  timeout = 600

  depends_on = [
    module.nginx-controller,
    kubernetes_job_v1.wait_for_ingress_webhook
  ]
}

resource "kubernetes_secret_v1" "cloudflare_api" {
  metadata {
    name      = "cloudflare-api"
    namespace = "cert-manager"
  }

  data = {
    api-token = var.cloudflare_api_token
  }

  type = "Opaque"

  depends_on = [helm_release.cert_manager]
}

resource "helm_release" "cert_manager_prod_issuer" {
  chart      = "cert-manager-issuers"
  name       = "cert-manager-prod-issuer"
  version    = "0.3.0"
  repository = "https://charts.adfinis.com"
  namespace  = "cert-manager"

  values = [
    <<-EOT
clusterIssuers:
  - name: letsencrypt-prod
    spec:
      acme:
        email: "greatvictor.anjorin@gmail.com"
        server: "https://acme-v02.api.letsencrypt.org/directory"
        privateKeySecretRef:
          name: letsencrypt-prod
        solvers:
          - dns01:
              cloudflare:
                email: "greatvictor.anjorin@gmail.com"
                apiTokenSecretRef:
                  name: cloudflare-api
                  key: api-token               
EOT
  ]

  depends_on = [
    helm_release.cert_manager,
    kubernetes_secret_v1.cloudflare_api
  ]
}

# resource "helm_release" "cert_manager_stag_issuer" {
#   chart      = "cert-manager-issuers"
#   name       = "cert-manager-stag-issuer"
#   version    = "0.3.0"
#   repository = "https://charts.adfinis.com"
#   namespace  = "cert-manager"

#   values = [
#     <<-EOT
# clusterIssuers:
#   - name: letsencrypt-staging
#     spec:
#       acme:
#         email: "greatvictor.anjorin@gmail.com"
#         server: "https://acme-staging-v02.api.letsencrypt.org/directory"
#         privateKeySecretRef:
#           name: letsencrypt-staging
#         solvers:
#           - dns01:
#               cloudflare:
#                 email: "greatvictor.anjorin@gmail.com"
#                 apitokensecret:
#                   name: cloudflare-api
#                   key: api-token               
# EOT
#   ]

#   depends_on = [helm_release.cert_manager, kubernetes_secret_v1.cloudflare_api]
# }

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

# Ingress Configuration for routing frontend traffic
resource "kubernetes_ingress_v1" "kronos_frontend" {
  metadata {
    name      = "kronos-frontend-ingress"
    namespace = "kronos"
    annotations = {
      "cert-manager.io/cluster-issuer"                 = "letsencrypt-prod"
      # "nginx.ingress.kubernetes.io/force-ssl-redirect" = "true"
    }
  }

  spec {
    ingress_class_name = "nginx"
    # tls {
    #   hosts       = ["${var.subdomains[0]}.${var.domain}"]
    #   secret_name = "kronos-tls"
    # }

    rule {
      # host = "${var.subdomains[0]}.${var.domain}"
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          backend {
            service {
              name = kubernetes_service_v1.kronos_frontend.metadata[0].name
              port {
                number = kubernetes_service_v1.kronos_frontend.spec[0].port[0].port
              }
            }
          }
        }
      }
    }
  }

  depends_on = [
    kubernetes_service_v1.kronos_frontend,
    null_resource.wait_for_ingress_webhook,
    kubernetes_job_v1.wait_for_ingress_webhook,
    helm_release.cert_manager_prod_issuer
  ]
}

# Ingress Configuration for backend traffic
resource "kubernetes_ingress_v1" "kronos_backend" {
  metadata {
    name      = "kronos-backend-ingress"
    namespace = "kronos"
    annotations = {
      "nginx.ingress.kubernetes.io/rewrite-target" = "/$2"
    }
  }

  spec {
    ingress_class_name = "nginx"

    rule {
      http {
        # Route /api/* to backend
        path {
          path      = "/api(/|$)(.*)"
          path_type = "ImplementationSpecific"
          backend {
            service {
              name = kubernetes_service_v1.kronos_backend.metadata[0].name
              port {
                number = kubernetes_service_v1.kronos_backend.spec[0].port[0].port
              }
            }
          }
        }
      }
    }
  }

  depends_on = [
    kubernetes_service_v1.kronos_backend,
    null_resource.wait_for_ingress_webhook,
    kubernetes_job_v1.wait_for_ingress_webhook,
    helm_release.cert_manager_prod_issuer
  ]
}

# Ingress Configuration for Monitoring Stack
resource "kubernetes_ingress_v1" "grafana" {
  metadata {
    name      = "grafana-ingress"
    namespace = "monitoring"
  }
  spec {
    ingress_class_name = "nginx"

    rule {
      host = "grafana.${data.kubernetes_service_v1.nginx_ingress.status.0.load_balancer.0.ingress.0.ip}.nip.io"
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          backend {
            service {
              name = "kube-prometheus-stack-grafana"
              port { number = 80 }
            }
          }
        }
      }
    }
  }
  depends_on = [
    helm_release.kube_prometheus_stack,
    helm_release.cert_manager_prod_issuer
  ]
}

resource "kubernetes_ingress_v1" "prometheus" {
  metadata {
    name      = "prometheus-ingress"
    namespace = "monitoring"
  }
  spec {
    ingress_class_name = "nginx"

    rule {
      host = "prometheus.${data.kubernetes_service_v1.nginx_ingress.status.0.load_balancer.0.ingress.0.ip}.nip.io"
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          backend {
            service {
              name = "kube-prometheus-stack-prometheus"
              port { number = 9090 }
            }
          }
        }
      }
    }
  }
  depends_on = [
    helm_release.kube_prometheus_stack,
    helm_release.cert_manager_prod_issuer
  ]
}

resource "kubernetes_ingress_v1" "alertmanager" {
  metadata {
    name      = "alertmanager-ingress"
    namespace = "monitoring"
  }
  spec {
    ingress_class_name = "nginx"

    rule {
      host = "alertmanager.${data.kubernetes_service_v1.nginx_ingress.status.0.load_balancer.0.ingress.0.ip}.nip.io"
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          backend {
            service {
              name = "kube-prometheus-stack-alertmanager"
              port { number = 9093 }
            }
          }
        }
      }
    }
  }
  depends_on = [
    helm_release.kube_prometheus_stack,
    helm_release.cert_manager_prod_issuer
  ]
}

# resource "kubernetes_ingress_v1" "tempo" {
#   metadata {
#     name      = "tempo-ingress"
#     namespace = "monitoring"
#   }
#   spec {
#     ingress_class_name = "nginx"

#     rule {
#       host = "tempo.${data.kubernetes_service_v1.nginx_ingress.status.0.load_balancer.0.ingress.0.ip}.nip.io"
#       http {
#         path {
#           path      = "/"
#           path_type = "Prefix"
#           backend {
#             service {
#               name = "tempo"
#               port { number = 3100 }
#             }
#           }
#         }
#       }
#     }
#   }
#   depends_on = [helm_release.kube_prometheus_stack, helm_release.cert_manager_prod_issuer]
# }

output "grafana_ingress" {
  value = kubernetes_ingress_v1.grafana.spec[0].rule[0].host
}

output "prometheus_ingress" {
  value = kubernetes_ingress_v1.prometheus.spec[0].rule[0].host
}

output "alertmanager_ingress" {
  value = kubernetes_ingress_v1.alertmanager.spec[0].rule[0].host
}

# output "tempo_ingress" {
#   value = kubernetes_ingress_v1.tempo.spec[0].rule[0].host
# }