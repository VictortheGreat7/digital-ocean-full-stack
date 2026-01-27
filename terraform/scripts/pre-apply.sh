#!/usr/bin/env bash
set -euo pipefail

# Set variables
RESOURCE_GROUP_NAME="tfbackend-rg"
STORAGE_ACCOUNT_NAME="kronos349"
CONTAINER_NAME="tfstate"
REGION="eastus"

# Check if Azure CLI is installed and user is logged in
if ! command -v az &> /dev/null; then
    echo "Azure CLI is not installed. Please install it first."
    exit 1
fi

if ! az account show &> /dev/null; then
    echo "You are not logged into Azure. Please run 'az login' first."
    exit 1
fi

# Check if container already exists
echo "Checking if storage account and container already exist..."
if az storage container show --name "$CONTAINER_NAME" --account-name "$STORAGE_ACCOUNT_NAME" &> /dev/null; then
        echo "Storage account and container already exist. Exiting..."
        exit 0
    else
        echo "Container does not exist. Proceeding with creation."
fi

# Create resource group
echo "Creating resource group..."
if ! az group create --name "$RESOURCE_GROUP_NAME" --location "$REGION"; then
    echo "Failed to create resource group"
    exit 1
fi

# Create storage account
echo "Creating storage account..."
if ! az storage account create \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$STORAGE_ACCOUNT_NAME" \
    --sku Standard_LRS \
    --encryption-services blob \
    --min-tls-version TLS1_2 \
    --https-only true; then
    echo "Failed to create storage account"
    exit 1
fi

# Wait for storage account to be fully provisioned
echo "Waiting for storage account to be fully provisioned..."
sleep 30

# Verify storage account exists
echo "Verifying storage account..."
if ! az storage account show --name "$STORAGE_ACCOUNT_NAME" --resource-group "$RESOURCE_GROUP_NAME" &> /dev/null; then
    echo "Storage account not found after creation. Please try again."
    exit 1
fi

# Create blob container using AAD authentication
echo "Creating blob container..."
if ! az storage container create \
    --name "$CONTAINER_NAME" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --auth-mode login; then
    echo "Failed to create container"
    exit 1
fi

echo "Setup completed successfully!"
echo "Resource Group: '$RESOURCE_GROUP_NAME'"
echo "Storage Account: '$STORAGE_ACCOUNT_NAME'"
echo "Container: '$CONTAINER_NAME'"
