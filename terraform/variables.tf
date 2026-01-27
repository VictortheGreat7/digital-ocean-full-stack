variable "region" {
  description = "The location/region of the resource group"
  type        = string
  default     = "nyc1"
}

variable "do_token" {
  description = "The DigitalOcean API token"
  type        = string
  sensitive   = true
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token for managing DNS records"
  type        = string
  sensitive   = true
}

variable "cloudflare_zone_id" {
  description = "Cloudflare Zone ID for the domain"
  type        = string
  sensitive   = true
}

variable "subdomains" {
  description = "List of subdomains to create"
  type        = list(string)
  default = [
    "kronos"
  ]
}

variable "domain" {
  description = "The root domain for the world clock application"
  type        = string
  default     = "mywonderworks.tech"
}
