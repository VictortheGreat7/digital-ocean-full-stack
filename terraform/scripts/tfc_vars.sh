#!/usr/bin/env bash
set -eu

vars=("ARM_CLIENT_ID" "ARM_CLIENT_SECRET" "ARM_SUBSCRIPTION_ID" "ARM_TENANT_ID")

for var_name in "${vars[@]}"; do
  # Get the value from the environment (passed from GitHub secrets)
  value=${!var_name}

  echo "Pushing $var_name to Terraform Cloud..."

  curl --header "Authorization: Bearer $TF_TOKEN_app_terraform_io" \
       --header "Content-Type: application/vnd.api+json" \
       --request POST \
       --data "{
         \"data\": {
           \"type\":\"vars\",
           \"attributes\": {
             \"key\":\"$var_name\",
             \"value\":\"$value\",
             \"category\":\"env\",
             \"sensitive\":true
           }
         }
       }" \
       "https://app.terraform.io/api/v2/workspaces/$WS_ID/vars"
done