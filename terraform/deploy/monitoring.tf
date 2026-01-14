resource "helm_release" "kube_prometheus_stack" {
  name             = "kube-prometheus-stack"
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  create_namespace = true
  namespace        = "monitoring"

  set = [
    # Prometheus settings
    {
      name  = "prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.storageClassName"
      value = "do-block-storage"
    },
    {
      name  = "prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage"
      value = "5Gi"
    },
    # Prometheus ingress
    {
      name  = "prometheus.ingress.enabled"
      value = "true"
    },
    {
      name  = "prometheus.ingress.ingressClassName"
      value = "nginx"
    },
    {
      name  = "prometheus.ingress.hosts[0]"
      value = "prometheus.${data.kubernetes_service_v1.nginx_ingress.status.0.load_balancer.0.ingress.0.ip}.nip.io"
    },
    # {
    #   name  = "prometheus.prometheusSpec.ingress.tls[0].hosts[0]"
    #   value = "prometheus.${data.kubernetes_service_v1.nginx_ingress.status.0.load_balancer.0.ingress.0.ip}.nip.io"
    # },
    # {
    #   name  = "prometheus.prometheusSpec.ingress.tls[0].secretName"
    #   value = "kronos-tls"
    # },

    # Alertmanager settings
    {
      name  = "alertmanager.enabled"
      value = "true"
    },
    {
      name  = "alertmanager.alertmanagerSpec.storage.volumeClaimTemplate.spec.storageClassName"
      value = "do-block-storage"
    },
    {
      name  = "alertmanager.alertmanagerSpec.storage.volumeClaimTemplate.spec.resources.requests.storage"
      value = "5Gi"
    },
    # Alertmanager ingress
    {
      name  = "alertmanager.ingress.enabled"
      value = "true"
    },
    {
      name  = "alertmanager.ingress.ingressClassName"
      value = "nginx"
    },
    {
      name  = "alertmanager.ingress.hosts[0]"
      value = "alertmanager.${data.kubernetes_service_v1.nginx_ingress.status.0.load_balancer.0.ingress.0.ip}.nip.io"
    },
    # {
    #   name  = "alertmanager.ingress.tls[0].hosts[0]"
    #   value = "alertmanager.${data.kubernetes_service_v1.nginx_ingress.status.0.load_balancer.0.ingress.0.ip}.nip.io"
    # },
    # {
    #   name  = "alertmanager.ingress.tls[0].secretName"
    #   value = "kronos-tls"
    # },

    # Grafana settings
    {
      name  = "grafana.persistence.enabled"
      value = "true"
    },
    {
      name  = "grafana.persistence.storageClassName"
      value = "do-block-storage"
    },
    {
      name  = "grafana.persistence.size"
      value = "5Gi"
    },
    {
      name  = "grafana.adminPassword"
      value = "admin"
    },
    # Grafana ingress
    {
    name  = "grafana.ingress.enabled"
    value = "true"
    },
    # {
    # name  = "grafana.ingress.tls[0].hosts[0]"
    # value = "grafana.${data.kubernetes_service_v1.nginx_ingress.status.0.load_balancer.0.ingress.0.ip}.nip.io"
    # },
    # {
    #   name  = "grafana.ingress.tls[0].secretName"
    #   value = "kronos-tls"
    # },
    {
      name  = "grafana.ingress.ingressClassName"
      value = "nginx"
    },
    {
      name  = "grafana.ingress.hosts[0]"
      value = "grafana.${data.kubernetes_service_v1.nginx_ingress.status.0.load_balancer.0.ingress.0.ip}.nip.io"
    }
  ]

  depends_on = [module.nginx-controller, helm_release.cert_manager_prod_issuer]
}

resource "helm_release" "tempo" {
  name             = "tempo"
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "tempo"
  namespace        = helm_release.kube_prometheus_stack.namespace
  create_namespace = false

  set = [
    {
      name  = "tempo.storage.trace.backend"
      value = "local"
    },
    {
      name  = "tempo.storage.trace.local.path"
      value = "/var/tempo/traces"
    },
    {
      name  = "tempo.receivers.otlp.protocols.grpc.endpoint"
      value = "0.0.0.0:4317"
    },
    {
      name  = "tempo.receivers.otlp.protocols.http.endpoint"
      value = "0.0.0.0:4318"
    },
    {
      name  = "persistence.enabled"
      value = "true"
    },
    {
      name  = "persistence.storageClassName"
      value = "do-block-storage"
    },
    {
      name  = "persistence.size"
      value = "5Gi"
    },
    # Tempo ingress
    {
      name  = "tempoQuery.ingress.enabled"
      value = "true"
    },
    # {
    #   name  = "ingress.tls[0].secretName"
    #   value = "kronos-tls"
    # },
    # {
    #   name  = "ingress.tls[0].hosts[0]"
    #   value = "tempo.${data.kubernetes_service_v1.nginx_ingress.status.0.load_balancer.0.ingress.0.ip}.nip.io"
    # },
    # {
    #   name  = "ingress.annotations.nginx\\.ingress\\.kubernetes\\.io/force-ssl-redirect"
    #   value = "true"
    # },
    # {
    #   name  = "ingress.hosts[0].paths[0]"
    #   value = "/"
    # },
    # {
    #   name  = "ingress.hosts[0].paths[0].pathType"
    #   value = "Prefix"
    # },
    {
      name = "tempoQuery.ingress.annotations.kubernetes\\.io/ingress\\.class"
      value = "nginx"
    },
    {
      name  = "tempoQuery.ingress.hosts[0].host"
      value = "tempo.${data.kubernetes_service_v1.nginx_ingress.status.0.load_balancer.0.ingress.0.ip}.nip.io"
    }
  ]

  depends_on = [helm_release.kube_prometheus_stack, helm_release.cert_manager_prod_issuer]
}

# Configure Grafana to use Tempo as a data source
resource "kubernetes_config_map_v1" "grafana_datasources" {
  metadata {
    name      = "grafana-tempo-datasource"
    namespace = helm_release.kube_prometheus_stack.namespace
    labels = {
      grafana_datasource = "1"
    }
  }

  data = {
    "tempo-datasource.yaml" = yamlencode({
      apiVersion = 1
      datasources = [
        {
          name      = "Tempo"
          type      = "tempo"
          access    = "proxy"
          url       = "http://tempo.monitoring:3200"
          isDefault = false
          jsonData = {
            tracesToLogsV2 = {
              datasourceUid = "prometheus"
            }
            tracesToMetrics = {
              datasourceUid = "prometheus"
            }
          }
        }
      ]
    })
  }

  depends_on = [helm_release.tempo]
}