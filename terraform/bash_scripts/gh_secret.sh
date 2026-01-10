#!/usr/bin/env bash
set -eu

# Define repository name for reuse
REPO_NAME=""

GITHUB_RUNNER_TOKEN=""
DO_API_TOKEN=""
CLOUDFLARE_TOKEN=""
CLOUDFLARE_ZONE_ID=""

# Declare an associative array to hold secrets and their corresponding values
declare -A secrets=(
  ["RUNNER_TOKEN"]="${GITHUB_RUNNER_TOKEN}"
  ["DO_API_TOKEN"]="${DO_API_TOKEN}"
  ["CLOUDFLARE_TOKEN"]="${CLOUDFLARE_TOKEN}"
  ["CLOUDFLARE_ZONE_ID"]="${CLOUDFLARE_ZONE_ID}"
  ["DOCKER_USERNAME"]=""
  ["DOCKER_PASSWORD"]=""
)

# Iterate over the secrets and set them using `gh secret set`
for secret_name in "${!secrets[@]}"; do
  gh secret set "$secret_name" --repo "$REPO_NAME" --body "${secrets[$secret_name]}"
done

echo "All secrets have been set successfully!"
