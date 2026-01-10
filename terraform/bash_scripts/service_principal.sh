#!/usr/bin/env bash
set -euo pipefail

# Check if the jq command exists and install it if it doesn't
if ! sudo which jq &> /dev/null; then
  echo "Error: jq command not found. Installing jq..."
  sudo apt-get update
  sudo apt-get install -y jq
fi

# Define variables
SERVICE_PRINCIPAL_NAME=""
ROLE="Owner"
SCOPE="/subscriptions/"  # Input your current Azure subscription ID
GITHUB_NAME="" # Input your GitHub username
GITHUB_REPO="" # Input your GitHub repository name
CREDENTIALS=$(cat <<EOF
{
    "name": "GitHubActions",
    "issuer": "https://token.actions.githubusercontent.com/",
    "subject": "repo:$GITHUB_NAME/$GITHUB_REPO:branch:main",
    "description": "Testing",
    "audiences": [
        "api://AzureADTokenExchange"
    ]
}
EOF
)
ESCAPED_CREDENTIALS=$(echo "$CREDENTIALS" | jq -c .) # Escape the credentials for the az command
USER_OBJECT_ID=$(az ad signed-in-user show --query id -o tsv) # Get the current user's object ID
EXISTING_SP=$(az ad sp list --display-name "$SERVICE_PRINCIPAL_NAME" --query "[].appId" -o tsv)

# Check if the service principal already exists
if [ -z "$EXISTING_SP" ]; then
    # Create the service principal if it doesn't exist
    echo "Creating service principal with name: $SERVICE_PRINCIPAL_NAME"
    SP_OUTPUT=$(az ad sp create-for-rbac --name="$SERVICE_PRINCIPAL_NAME" --role="$ROLE" --scopes="$SCOPE" --query "{appId: appId, objectId: objectId, password: password, tenant: tenant}" -o json)

    # Extract the details from the output
    APP_ID=$(echo $SP_OUTPUT | jq -r '.appId')
    OBJECT_ID=$(echo $SP_OUTPUT | jq -r '.objectId')
    PASSWORD=$(echo $SP_OUTPUT | jq -r '.password')
    TENANT=$(echo $SP_OUTPUT | jq -r '.tenant')

    if [ -z "$APP_ID" ] || [ -z "$PASSWORD" ] || [ -z "$TENANT" ]; then
        echo "Failed to create service principal. Exiting."
        exit 1
    fi

else
    # Retrieve the existing service principal's appId, objectId, and tenant
    echo "Service principal already exists. Retrieving details."
    SP_OUTPUT=$(az ad sp show --id "$EXISTING_SP" --query "{appId: appId, objectId: objectId, tenant: appOwnerTenantId}" -o json)

    APP_ID=$(echo $SP_OUTPUT | jq -r '.appId')
    OBJECT_ID=$(echo $SP_OUTPUT | jq -r '.objectId')
    TENANT=$(echo $SP_OUTPUT | jq -r '.tenant')
    PASSWORD="N/A (Existing SP does not show the password)"
fi

# Display the service principal details
echo "Service Principal created or retrieved successfully!"
echo "App ID (Client ID): $APP_ID"
echo "Password (Client Secret): $PASSWORD"
echo "Tenant ID: $TENANT"
echo "Subscription ID: $(az account show --query id -o tsv)"

# Save the details to a file
echo "Saving service principal details to secrets.yaml"
cat <<EOF > secrets.yaml
azure:
  client_id: "$APP_ID"
  client_secret: "$PASSWORD"
  subscription_id: "$(az account show --query id -o tsv)"
  tenant_id: "$TENANT"
  user_object_id: "$USER_OBJECT_ID"
EOF
echo "Service principal details saved to secrets.yaml"

# Add federated credentials for GitHub Actions
if [ "$PASSWORD" != "N/A (Existing SP does not show the password)" ]; then
    echo "Adding federated credentials for GitHub Actions"
    az ad app federated-credential create --id $APP_ID --parameters "$ESCAPED_CREDENTIALS"
else
    echo "Federated credentials not added because the service principal was not newly created."
fi
