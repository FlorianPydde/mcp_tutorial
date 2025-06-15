#!/bin/bash

# Simple Azure Deployment Script
# Deploy MCP Tutorial to Azure Container Apps
# 
# Prerequisites:
# 1. Install Azure CLI: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
# 2. Run: az login
# 3. Create web_client/.env file with your Azure OpenAI settings

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

# ===== CONFIGURATION =====
RESOURCE_GROUP="mcp-tutorial-rg"
LOCATION="westeurope"  # Amsterdam, Netherlands - Great for European users
# Generate a unique ACR name using timestamp to avoid conflicts
ACR_NAME="mcptutorial"
ENV_NAME="mcp-tutorial-env"
SERVER_APP="mcp-weather-server"
WEB_CLIENT_APP="mcp-web-client"

echo -e "${CYAN}Using ACR name: $ACR_NAME${NC}"

# ===== LOAD ENVIRONMENT VARIABLES =====
echo -e "${CYAN}Loading environment variables...${NC}"

# Function to load env file
load_env_file() {
    local file=$1
    local prefix=$2
    
    if [[ -f "$file" ]]; then
        echo -e "${GREEN}Loading $prefix settings...${NC}"
        while IFS='=' read -r name value; do
            # Skip comments and empty lines
            if [[ $name =~ ^[[:space:]]*# ]] || [[ -z "$name" ]]; then
                continue
            fi
            
            # Clean up the name and value
            name=$(echo "$name" | xargs)
            value=$(echo "$value" | xargs | sed 's/^["'\'']//' | sed 's/["'\'']$//')
            
            if [[ -n "$name" && -n "$value" ]]; then
                export "$name"="$value"
                echo -e "  ${GRAY}$prefix: $name${NC}"
            fi
        done < "$file"
    fi
}

# Load server environment variables
load_env_file "server/.env" "Server"

# Load web client environment variables  
if [[ -f "web_client/.env" ]]; then
    load_env_file "web_client/.env" "Client"
else
    echo -e "${YELLOW}No web_client/.env file found - you'll be prompted for Azure OpenAI settings${NC}"
fi

# ===== CHECK PREREQUISITES =====
echo -e "${CYAN}Checking prerequisites...${NC}"

# Check Azure CLI
if ! command -v az &> /dev/null; then
    echo -e "${RED}ERROR: Azure CLI not found!${NC}"
    echo -e "${YELLOW}Install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli${NC}"
    exit 1
fi

# Check Azure login and show current subscription
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}Please log in to Azure...${NC}"
    az login
else
    echo -e "${GREEN}Current Azure subscription:${NC}"
    az account show --query "{name:name,id:id}" -o table
fi

# ===== CREATE RESOURCES =====
echo -e "${CYAN}Creating Azure resources...${NC}"

# Resource Group
echo -e "${YELLOW}Creating resource group...${NC}"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

# Container Registry
echo -e "${YELLOW}Creating Azure Container Registry...${NC}"
if ! az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    echo -e "${YELLOW}Creating new ACR: $ACR_NAME (this may take a few minutes)...${NC}"
    az acr create --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --sku Basic --admin-enabled true
    
    # Wait for ACR to be ready
    echo -e "${YELLOW}Waiting for ACR to be ready...${NC}"
    MAX_ATTEMPTS=30  # 5 minutes max (10 seconds * 30)
    ATTEMPT=0
    
    while true; do
        sleep 10
        ((ATTEMPT++))
        ACR_STATUS=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query "provisioningState" -o tsv 2>/dev/null || echo "")
        echo -e "${GRAY}ACR Status (attempt $ATTEMPT/$MAX_ATTEMPTS): $ACR_STATUS${NC}"
        
        if [[ $ATTEMPT -ge $MAX_ATTEMPTS ]]; then
            echo -e "${RED}ERROR: Timeout waiting for ACR to be ready!${NC}"
            exit 1
        fi
        
        if [[ "$ACR_STATUS" == "Succeeded" ]]; then
            break
        fi
    done
    
    echo -e "${GREEN}ACR is ready!${NC}"
else
    echo -e "${GREEN}ACR already exists${NC}"
fi

# Small delay before creating next resource
echo -e "${GRAY}Waiting a moment before creating Container Apps environment...${NC}"
sleep 5

# Container Apps Environment
echo -e "${YELLOW}Creating Container Apps environment...${NC}"
if ! az containerapp env show --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    echo -e "${YELLOW}Creating new Container Apps environment: $ENV_NAME (this may take 5-10 minutes)...${NC}"
    echo -e "${GRAY}This will also create a Log Analytics workspace automatically...${NC}"
    
    # Start the environment creation
    az containerapp env create --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" --location "$LOCATION"
    
    # Wait for environment to be ready (this can take several minutes)
    echo -e "${YELLOW}Waiting for Container Apps environment to be ready...${NC}"
    MAX_ATTEMPTS=60  # 10 minutes max (10 seconds * 60)
    ATTEMPT=0
    
    while true; do
        sleep 10
        ((ATTEMPT++))
        ENV_STATUS=$(az containerapp env show --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" --query "properties.provisioningState" -o tsv 2>/dev/null || echo "")
        echo -e "${GRAY}Environment Status (attempt $ATTEMPT/$MAX_ATTEMPTS): $ENV_STATUS${NC}"
        
        if [[ $ATTEMPT -ge $MAX_ATTEMPTS ]]; then
            echo -e "${RED}ERROR: Timeout waiting for Container Apps environment to be ready!${NC}"
            echo -e "${YELLOW}You can check the status in Azure Portal and run the script again later.${NC}"
            exit 1
        fi
        
        if [[ "$ENV_STATUS" == "Succeeded" ]]; then
            break
        fi
    done
    
    echo -e "${GREEN}Container Apps environment is ready!${NC}"
else
    echo -e "${GREEN}Container Apps environment already exists${NC}"
fi

# ===== BUILD IMAGES =====
echo -e "${CYAN}Building Docker images...${NC}"

# Verify ACR is accessible before building
echo -e "${YELLOW}Verifying ACR access...${NC}"
ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query "loginServer" -o tsv)
echo -e "${GREEN}ACR Login Server: $ACR_LOGIN_SERVER${NC}"

# Additional verification - test ACR login capability (better test for build readiness)
echo -e "${YELLOW}Testing ACR build readiness...${NC}"
MAX_RETRIES=10
RETRY=0

while true; do
    ((RETRY++))
    echo -e "${GRAY}Testing ACR login capability (attempt $RETRY/$MAX_RETRIES)...${NC}"
    
    # Try ACR login - this is a better test for ACR build readiness
    if ACR_LOGIN_TEST=$(az acr login --name "$ACR_NAME" --expose-token --output tsv --query accessToken 2>/dev/null) && [[ -n "$ACR_LOGIN_TEST" ]]; then
        echo -e "${GREEN}ACR is ready for build operations!${NC}"
        break
    fi
    
    if [[ $RETRY -ge $MAX_RETRIES ]]; then
        echo -e "${RED}ERROR: ACR is not ready for build operations!${NC}"
        echo -e "${YELLOW}The ACR may still be initializing internal services.${NC}"
        echo -e "${YELLOW}Please wait 5-10 more minutes and run the script again.${NC}"
        exit 1
    fi
    
    echo -e "${YELLOW}ACR login not ready yet, waiting 45 seconds...${NC}"
    sleep 45
done

echo -e "${YELLOW}Building server image...${NC}"
az acr build --registry "$ACR_NAME" --image "$SERVER_APP:latest" --file server/Dockerfile ./server

echo -e "${YELLOW}Building web client image...${NC}"
az acr build --registry "$ACR_NAME" --image "$WEB_CLIENT_APP:latest" --file web_client/Dockerfile ./web_client

# ===== GET REGISTRY CREDENTIALS =====
ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query "username" -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)

# ===== DEPLOY SERVER =====
echo -e "${CYAN}Deploying weather server...${NC}"

# Use server settings from .env or defaults
SERVER_HOST=${HOST:-"0.0.0.0"}
SERVER_PORT=${PORT:-"8000"}
LOG_LEVEL=${LOG_LEVEL:-"INFO"}

az containerapp create \
    --name "$SERVER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$ENV_NAME" \
    --image "$ACR_NAME.azurecr.io/$SERVER_APP:latest" \
    --registry-server "$ACR_NAME.azurecr.io" \
    --registry-username "$ACR_USERNAME" \
    --registry-password "$ACR_PASSWORD" \
    --target-port "$SERVER_PORT" \
    --ingress internal \
    --env-vars \
        "HOST=$SERVER_HOST" \
        "PORT=$SERVER_PORT" \
        "LOG_LEVEL=$LOG_LEVEL"

# Get server URL
SERVER_URL=$(az containerapp show --name "$SERVER_APP" --resource-group "$RESOURCE_GROUP" --query "properties.configuration.ingress.fqdn" -o tsv)

# ===== CHECK AZURE OPENAI SETTINGS =====
echo -e "${CYAN}Checking Azure OpenAI settings...${NC}"

if [[ -z "$AZURE_OPENAI_API_BASE" ]]; then
    read -p "Azure OpenAI Endpoint (e.g. https://your-resource.openai.azure.com/): " AZURE_OPENAI_API_BASE
fi

if [[ -z "$AZURE_OPENAI_API_KEY" ]]; then
    read -p "Azure OpenAI API Key: " AZURE_OPENAI_API_KEY
fi

if [[ -z "$AZURE_OPENAI_API_VERSION" ]]; then
    read -p "API Version (e.g. 2024-02-15-preview): " AZURE_OPENAI_API_VERSION
fi

if [[ -z "$AZURE_OPENAI_DEPLOYMENT_NAME" ]]; then
    read -p "Model Deployment Name: " AZURE_OPENAI_DEPLOYMENT_NAME
fi

# ===== DEPLOY WEB CLIENT =====
echo -e "${CYAN}Deploying web client...${NC}"

# Use web client settings from .env or defaults
WEB_CLIENT_PORT="8080"  # Default for web client
WEB_CLIENT_LOG_LEVEL=${LOG_LEVEL:-"INFO"}

az containerapp create \
    --name "$WEB_CLIENT_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$ENV_NAME" \
    --image "$ACR_NAME.azurecr.io/$WEB_CLIENT_APP:latest" \
    --registry-server "$ACR_NAME.azurecr.io" \
    --registry-username "$ACR_USERNAME" \
    --registry-password "$ACR_PASSWORD" \
    --target-port "$WEB_CLIENT_PORT" \
    --ingress external \
    --env-vars \
        "MCP_SERVER_URL=https://$SERVER_URL/sse" \
        "AZURE_OPENAI_API_BASE=$AZURE_OPENAI_API_BASE" \
        "AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY" \
        "AZURE_OPENAI_API_VERSION=$AZURE_OPENAI_API_VERSION" \
        "AZURE_OPENAI_DEPLOYMENT_NAME=$AZURE_OPENAI_DEPLOYMENT_NAME" \
        "LOG_LEVEL=$WEB_CLIENT_LOG_LEVEL"

# ===== DEPLOYMENT COMPLETE =====
WEB_URL=$(az containerapp show --name "$WEB_CLIENT_APP" --resource-group "$RESOURCE_GROUP" --query "properties.configuration.ingress.fqdn" -o tsv)

echo ""
echo -e "${GREEN}🎉 DEPLOYMENT COMPLETE!${NC}"
echo -e "${CYAN}Check Web App Status at: https://$WEB_URL/health${NC}"
echo ""
echo -e "${CYAN}Test with:${NC}"
echo -e "${NC}curl -X POST https://$WEB_URL/chat -H \"Content-Type: application/json\" -d '{\"query\": \"What is the weather in Paris?\"}'"
