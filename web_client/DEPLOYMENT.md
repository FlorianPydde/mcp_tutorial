# Azure Deployment Guide for MCP Tutorial

This guide provides step-by-step instructions for deploying the MCP weather tutorial to Azure using Container Apps.

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │ Azure Container  │    │ External APIs   │
│   (Web/Mobile)  │───▶│     Apps         │───▶│ (Weather.gov)   │
│                 │    │ (Web Client)     │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │ Azure Container  │
                       │  Apps (Server)   │
                       └──────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │ Azure OpenAI     │
                       │   Service        │
                       └──────────────────┘
```

## Prerequisites

1. **Azure CLI**: Install and configure Azure CLI
2. **Docker**: For local testing and building images
3. **Azure Container Registry**: For storing container images
4. **Azure OpenAI**: Deployed Azure OpenAI service

## Step 1: Prepare Azure Resources

### Create Resource Group
```bash
az group create --name mcp-tutorial-rg --location eastus
```

### Create Azure Container Registry
```bash
az acr create \
  --resource-group mcp-tutorial-rg \
  --name mcptutorialacr \
  --sku Basic \
  --admin-enabled true
```

### Get ACR Login Server
```bash
az acr show --name mcptutorialacr --query loginServer --output tsv
```

## Step 2: Build and Push Container Images

### Login to ACR
```bash
az acr login --name mcptutorialacr
```

### Build and Push Server Image
```bash
# Navigate to server directory
cd server

# Build image
docker build -t mcptutorialacr.azurecr.io/mcp-weather-server:latest .

# Push image
docker push mcptutorialacr.azurecr.io/mcp-weather-server:latest
```

### Build and Push Web Client Image
```bash
# Navigate to web_client directory
cd ../web_client

# Build image
docker build -t mcptutorialacr.azurecr.io/mcp-web-client:latest .

# Push image
docker push mcptutorialacr.azurecr.io/mcp-web-client:latest
```

## Step 3: Create Container Apps Environment

```bash
az containerapp env create \
  --name mcp-tutorial-env \
  --resource-group mcp-tutorial-rg \
  --location eastus
```

## Step 4: Deploy MCP Weather Server

```bash
# Get ACR credentials first
az acr credential show --name mcptutorialacr --query "username" -o tsv
az acr credential show --name mcptutorialacr --query "passwords[0].value" -o tsv

# Deploy using the credentials from above commands
az containerapp create \
  --name mcp-weather-server \
  --resource-group mcp-tutorial-rg \
  --environment mcp-tutorial-env \
  --image mcptutorialacr.azurecr.io/mcp-weather-server:latest \
  --registry-server mcptutorialacr.azurecr.io \
  --registry-username [USERNAME_FROM_ABOVE] \
  --registry-password [PASSWORD_FROM_ABOVE] \
  --target-port 8000 \
  --ingress internal \
  --min-replicas 1 \
  --max-replicas 3 \
  --env-vars "HOST=0.0.0.0" "PORT=8000"
```

## Step 5: Deploy MCP Web Client

First, get the server's internal URL:
```bash
az containerapp show --name mcp-weather-server --resource-group mcp-tutorial-rg --query "properties.configuration.ingress.fqdn" -o tsv
```

Then deploy the web client using the URL from above:
```bash
# Get ACR credentials
az acr credential show --name mcptutorialacr --query "username" -o tsv
az acr credential show --name mcptutorialacr --query "passwords[0].value" -o tsv

# Deploy web client (replace SERVER_URL_FROM_ABOVE with the URL from the first command)
az containerapp create \
  --name mcp-web-client \
  --resource-group mcp-tutorial-rg \
  --environment mcp-tutorial-env \
  --image mcptutorialacr.azurecr.io/mcp-web-client:latest \
  --registry-server mcptutorialacr.azurecr.io \
  --registry-username [USERNAME_FROM_ABOVE] \
  --registry-password [PASSWORD_FROM_ABOVE] \
  --target-port 8080 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 5 \
  --env-vars \
    "MCP_SERVER_URL=https://[SERVER_URL_FROM_ABOVE]/sse" \
    "AZURE_OPENAI_API_BASE=YOUR_AZURE_OPENAI_ENDPOINT" \
    "AZURE_OPENAI_API_KEY=YOUR_AZURE_OPENAI_KEY" \
    "AZURE_OPENAI_API_VERSION=2024-02-15-preview" \
    "AZURE_OPENAI_DEPLOYMENT_NAME=YOUR_DEPLOYMENT_NAME"
```

## Step 6: Configure Environment Variables

Update the web client with your Azure OpenAI credentials:

```bash
az containerapp update \
  --name mcp-web-client \
  --resource-group mcp-tutorial-rg \
  --set-env-vars \
    "AZURE_OPENAI_API_BASE=https://your-openai-resource.openai.azure.com/" \
    "AZURE_OPENAI_API_KEY=your-api-key" \
    "AZURE_OPENAI_API_VERSION=2024-02-15-preview" \
    "AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name"
```

## Step 7: Verify Deployment

### Get Web Client URL
```bash
az containerapp show --name mcp-web-client --resource-group mcp-tutorial-rg --query "properties.configuration.ingress.fqdn" -o tsv
```

### Test Health Endpoint
```bash
# Replace WEB_CLIENT_URL with the URL from the command above
curl https://[WEB_CLIENT_URL]/health
```

### Test Chat Endpoint
```bash
# Replace WEB_CLIENT_URL with the URL from the first command
curl -X POST https://[WEB_CLIENT_URL]/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather in San Francisco?"}'
```

## Step 8: Monitor and Scale

### View Logs
```bash
az containerapp logs show --name mcp-web-client --resource-group mcp-tutorial-rg --follow
```

### Scale Application
```bash
az containerapp update \
  --name mcp-web-client \
  --resource-group mcp-tutorial-rg \
  --min-replicas 2 \
  --max-replicas 10
```

## Cost Optimization

### Enable Scale to Zero (for development)
```bash
az containerapp update \
  --name mcp-web-client \
  --resource-group mcp-tutorial-rg \
  --min-replicas 0
```

### Set Resource Limits
```bash
az containerapp update \
  --name mcp-web-client \
  --resource-group mcp-tutorial-rg \
  --cpu 0.5 \
  --memory 1Gi
```

## Security Best Practices

1. **Use Azure Key Vault** for storing sensitive configuration:
```bash
# Create Key Vault
az keyvault create \
  --name mcp-tutorial-kv \
  --resource-group mcp-tutorial-rg \
  --location eastus

# Store secrets
az keyvault secret set \
  --vault-name mcp-tutorial-kv \
  --name "azure-openai-key" \
  --value "your-api-key"
```

2. **Enable managed identity** for secure access to Azure resources
3. **Configure network restrictions** for production deployments
4. **Use HTTPS only** in production

## Troubleshooting

### Check Application Logs
```bash
az containerapp logs show --name mcp-web-client --resource-group mcp-tutorial-rg --tail 50
```

### Restart Application
```bash
# Get the current revision name first
az containerapp revision list --name mcp-web-client --resource-group mcp-tutorial-rg --query "[0].name" -o tsv

# Then restart using the revision name from above
az containerapp revision restart \
  --name mcp-web-client \
  --resource-group mcp-tutorial-rg \
  --revision [REVISION_NAME_FROM_ABOVE]
```

### Check Resource Usage
```bash
az containerapp show \
  --name mcp-web-client \
  --resource-group mcp-tutorial-rg \
  --query "properties.template.containers[0].resources"
```

## Cleanup

To remove all resources:
```bash
az group delete --name mcp-tutorial-rg --yes --no-wait
```

## Cost Estimation

| Resource | Configuration | Monthly Cost (USD) |
|----------|---------------|-------------------|
| Container Apps Environment | Consumption | $0 |
| MCP Server (1-3 replicas) | 0.25 vCPU, 0.5 GB | $5-15 |
| Web Client (1-5 replicas) | 0.5 vCPU, 1 GB | $10-50 |
| Container Registry (Basic) | 10 GB storage | $5 |
| **Total** | | **$20-70** |

*Note: Costs may vary based on usage patterns and Azure pricing changes.*
