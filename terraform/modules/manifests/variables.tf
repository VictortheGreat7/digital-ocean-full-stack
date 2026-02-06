variable "doks_host" {
  type        = any
  description = "The API server URL for the DOKS cluster"
}

variable "doks_token" {
  type        = any
  description = "The API token for authenticating with the DOKS cluster"
}

variable "doks_client_certificate" {
  type        = any
  description = "The client certificate for authenticating with the DOKS cluster"
}

variable "doks_client_key" {
  type        = any
  description = "The client key for authenticating with the DOKS cluster"
}

variable "doks_cluster_ca_certificate" {
  type        = any
  description = "The cluster CA certificate for authenticating with the DOKS cluster"
}

variable "cilium_gateway_manifest" {
  type        = any
  description = "Kubernetes manifest for Cilium Gateway"
}

variable "kronos_http_route_manifest" {
  type        = any
  description = "Kubernetes manifest for Kronos HTTP Route"
}

variable "kronos_https_route_manifest" {
  type        = any
  description = "Kubernetes manifest for Kronos HTTPS Route"
}

variable "k6_test_manifest" {
  type        = any
  description = "Kubernetes manifest for K6 Load Test"
}
