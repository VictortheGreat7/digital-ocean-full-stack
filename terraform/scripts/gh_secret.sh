#!/usr/bin/env bash
set -eu

# Define name for use in uninitialized directories
REPO_NAME=""

TF_API_TOKEN=
CLIENT_ID=""
CLIENT_SECRET=""
SUBSCRIPTION_ID=""
TENANT_ID=""
GITHUB_RUNNER_TOKEN=""
DO_API_TOKEN=""
CLOUDFLARE_TOKEN=""
CLOUDFLARE_ZONE_ID=""
DOCKER_USERNAME=""
DOCKER_PASSWORD=""

# Azure credentials as JSON
AZURE_CREDENTIALS=$(cat <<EOF
{
  "clientId": "${CLIENT_ID}",
  "clientSecret": "${CLIENT_SECRET}",
  "subscriptionId": "${SUBSCRIPTION_ID}",
  "tenantId": "${TENANT_ID}"
}
EOF
)

# Declare an associative array to hold secrets and their corresponding values
declare -A secrets=(
  ["AZURE_CREDENTIALS"]="${AZURE_CREDENTIALS}"
  ["ARM_CLIENT_ID"]="${CLIENT_ID}"
  ["ARM_CLIENT_SECRET"]="${CLIENT_SECRET}"
  ["ARM_SUBSCRIPTION_ID"]="${SUBSCRIPTION_ID}"
  ["ARM_TENANT_ID"]="${TENANT_ID}"
  ["RUNNER_TOKEN"]="${GITHUB_RUNNER_TOKEN}"
  ["DO_API_TOKEN"]="${DO_API_TOKEN}"
  ["TF_API_TOKEN"]="${TF_API_TOKEN}"
  ["CLOUDFLARE_TOKEN"]="${CLOUDFLARE_TOKEN}"
  ["CLOUDFLARE_ZONE_ID"]="${CLOUDFLARE_ZONE_ID}"
  ["DOCKER_USERNAME"]="${DOCKER_USERNAME}"
  ["DOCKER_PASSWORD"]="${DOCKER_PASSWORD}"
)

# Iterate over the secrets and set them using `gh secret set`
for secret_name in "${!secrets[@]}"; do
  gh secret set "$secret_name" --repo "$REPO_NAME" --body "${secrets[$secret_name]}"
done

echo "All secrets have been set successfully!"
