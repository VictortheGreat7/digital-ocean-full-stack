#!/usr/bin/env bash

RESOURCE_GROUP=$(terraform output -raw aks_resource_group)
CLUSTER_NAME=$(terraform output -raw aks_cluster_name)

az aks get-credentials --resource-group $RESOURCE_GROUP --name $CLUSTER_NAME --overwrite-existing