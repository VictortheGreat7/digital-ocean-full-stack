resource "helm_release" "argo_cd" {
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  namespace        = "knative-cd"
  create_namespace = true
  atomic           = true
  cleanup_on_fail  = true

  values = [yamlencode({
    server = {
      httproute = {
        enabled = true
        parentRefs = [{
          name        = "kronos"
          namespace   = "kube-system"
          sectionName = "https"
        }]
        hostnames = ["${var.subdomains[0]}.${var.domain}"]
        rules = [
          {
            backendRefs = [
              {
                name = "argocd-server"
                port = 80
              }
            ]
            matches = [
              {
                path = {
                  type  = "PathPrefix"
                  value = "/kcd/argo"
                }
              }
            ]
          }
        ]
      }
    }
    configs = {
      params = {
        "server.basehref" = "/kcd/argo"
        "server.rootpath" = "/kcd/argo"
        "server.insecure" = "true"
      }
    }
  })]

  wait    = true
  timeout = 600

  depends_on = [
    digitalocean_kubernetes_cluster.kronos
  ]
}

resource "helm_release" "argocd_apps" {
  name             = "argocd-apps"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argocd-apps"
  namespace        = "knative-cd"
  create_namespace = false
  atomic           = true
  cleanup_on_fail  = true

  values = [yamlencode({
    applications = {
      reflector = {
        namespace = "knative-cd"
        project   = "default"
        sources = [
          {
            repoURL        = "https://github.com/VictortheGreat7/digital-ocean-full-stack.git"
            targetRevision = "main"
            ref            = "values"
          },
          {
            repoURL        = "https://emberstack.github.io/helm-charts"
            chart          = "reflector"
            targetRevision = "10.0.8"
            helm = {
              valueFiles = ["$values/manifests/reflector/values.yaml"]
            }
          }
        ]
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "secrets"
        }
        syncPolicy = {
          automated = {
            # prune    = true
            selfHeal = true
          }
        }
      },
      cert-manager = {
        namespace = "knative-cd"
        project   = "default"
        sources = [
          {
            repoURL        = "https://github.com/VictortheGreat7/digital-ocean-full-stack.git"
            targetRevision = "main"
            ref            = "values"
          },
          {
            repoURL        = "https://charts.jetstack.io"
            chart          = "cert-manager"
            targetRevision = "1.19.3"
            helm = {
              valueFiles = ["$values/manifests/ingress/cert-manager/values.yaml"]
            }
          }
        ]
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "cert-manager"
        }
        annotations = {
          "argocd.argoproj.io/sync-wave" = "1"
        }
        syncPolicy = {
          automated = {
            # prune    = true
            selfHeal = true
          }
          syncOptions = [
            "CreateNamespace=true"
          ]
        }
      },
      cluster-issuer = {
        namespace = "knative-cd"
        project   = "default"
        source = {
          repoURL        = "https://github.com/VictortheGreat7/digital-ocean-full-stack.git"
          targetRevision = "main"
          path           = "manifests/ingress"
        }
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "cert-manager"
        }
        annotations = {
          "argocd.argoproj.io/depends-on" = "cert-manager"
          "argocd.argoproj.io/sync-wave" = "2"
        }
        syncPolicy = {
          automated = {
            # prune    = true
            selfHeal = true
          }
        }
      },
      gateway = {
        namespace = "knative-cd"
        project   = "default"
        source = {
          repoURL        = "https://github.com/VictortheGreat7/digital-ocean-full-stack.git"
          targetRevision = "main"
          path           = "manifests/ingress/gateway"
        }
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "kube-system"
        }
        syncPolicy = {
          automated = {
            # prune    = true
            selfHeal = true
          }
        }
      },
      monitoring = {
        namespace = "knative-cd"
        project   = "default"
        source = {
          repoURL        = "https://github.com/VictortheGreat7/digital-ocean-full-stack.git"
          targetRevision = "main"
          path           = "manifests/monitoring/"
        }
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "monitoring"
        }
        syncPolicy = {
          automated = {
            # prune    = true
            selfHeal = true
          }
          syncOptions = [
            "CreateNamespace=true"
          ]
        }
      },
      kube-prom-crds = {
        namespace = "knative-cd"
        project   = "default"
        source = {
          repoURL        = "https://github.com/prometheus-operator/kube-prometheus"
          targetRevision = "main"
          path = "manifests/setup"
        }
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "monitoring"
        }
        annotations = {
          "argocd.argoproj.io/depends-on" = "monitoring"
        }
        syncPolicy = {
          automated = {
            # prune    = true
            selfHeal = true
          }
          syncOptions = [
            "ServerSideApply=true"
          ]
        }
      },
      kube-prom-stack = {
        namespace = "knative-cd"
        project   = "default"
        sources = [
          {
            repoURL        = "https://github.com/VictortheGreat7/digital-ocean-full-stack.git"
            targetRevision = "main"
            ref            = "values"
          },
          {
            repoURL        = "https://prometheus-community.github.io/helm-charts"
            chart          = "kube-prometheus-stack"
            targetRevision = "81.6.7"
            helm = {
              valueFiles = ["$values/manifests/monitoring/kube-prom-stack/helm/values.yaml"]
              skipCrds = true
            }
          }
        ]
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "monitoring"
        }
        annotations = {
          "argocd.argoproj.io/depends-on" = "monitoring,kube-prom-crds"
        }
        annotations = {
          "argocd.argoproj.io/depends-on" = "cert-manager"
          "argocd.argoproj.io/sync-wave" = "3"
        }
        syncPolicy = {
          automated = {
            # prune    = true
            selfHeal = true
          }
        }
      },
      datadog = {
        namespace = "knative-cd"
        project   = "default"
        sources = [
          {
            repoURL        = "https://github.com/VictortheGreat7/digital-ocean-full-stack.git"
            targetRevision = "main"
            ref            = "values"
          },
          {
            repoURL        = "https://helm.datadoghq.com"
            chart          = "datadog"
            targetRevision = "3.170.1"
            helm = {
              valueFiles     = ["$values/manifests/monitoring/datadog/helm/values.yaml"]
              parameters = [
                {
                  name  = "datadog.clusterName"
                  value = "${digitalocean_kubernetes_cluster.kronos.name}"
                }
              ]
            }
          }
        ]
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "monitoring"
        }
        annotations = {
          "argocd.argoproj.io/depends-on" = "monitoring"
          "argocd.argoproj.io/sync-wave" = "4"
        }
        syncPolicy = {
          automated = {
            # prune    = true
            selfHeal = true
          }
        }
      },
      chaos-operator = {
        namespace = "knative-cd"
        project   = "default"
        sources = [
          {
            repoURL        = "https://github.com/VictortheGreat7/digital-ocean-full-stack.git"
            targetRevision = "main"
            ref            = "values"
          },
          {
            repoURL        = "https://grafana.github.io/helm-charts"
            chart          = "k6-operator"
            targetRevision = "4.2.0"
            helm = {
              valueFiles     = ["$values/manifests/chaos-testing/helm/values.yaml"]
            }
          }
        ]
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "chaos"
        }
        annotations = {
          "argocd.argoproj.io/depends-on" = "cert-manager"
          "argocd.argoproj.io/sync-wave" = "6"
        }
        syncPolicy = {
          automated = {
            # prune    = true
            selfHeal = true
          }
          syncOptions = [
            "CreateNamespace=true"
          ]
        }
      },
      chaos-test = {
        namespace = "knative-cd"
        project   = "default"
        source = {
          repoURL        = "https://github.com/VictortheGreat7/digital-ocean-full-stack.git"
          targetRevision = "main"
          path           = "manifests/chaos-testing"
        }
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "chaos"
        }
        annotations = {
          "argocd.argoproj.io/depends-on" = "chaos-operator"
          "argocd.argoproj.io/sync-wave" = "7"
        }
        syncPolicy = {
          automated = {
            # prune    = true
            selfHeal = true
          }
        }
      },
      kronos = {
        namespace = "knative-cd"
        project   = "default"
        source = {
          repoURL        = "https://github.com/VictortheGreat7/digital-ocean-full-stack.git"
          targetRevision = "main"
          path           = "manifests/kronos-app"
        }
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "kronos"
        }
        annotations = {
          "argocd.argoproj.io/depends-on" = "cert-manager"
          "argocd.argoproj.io/sync-wave" = "5"
        }
        syncPolicy = {
          automated = {
            # prune    = true
            selfHeal = true
          }
          syncOptions = [
            "CreateNamespace=true"
          ]
        }
      }
    }
  })]

  wait    = true
  timeout = 600

  depends_on = [
    digitalocean_kubernetes_cluster.kronos,
    helm_release.argo_cd,
    kubernetes_secret_v1.cloudflare_api
  ]
}