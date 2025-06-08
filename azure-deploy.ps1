# Azure Deployment Script for MCP Tutorial Project
# This script builds and deploys the MCP Tutorial project to Azure Container Apps

# Configuration variables
$resourceGroup = "mcp-tutorial-rg"
$location = "eastus"
$acrName = "mcptutorialacr" 
$envName = "mcp-tutorial-env"
$serverAppName = "mcp-weather-server"
$webClientAppName = "mcp-web-client"

# Function to check if command exists
function Test-CommandExists {
    param ($command)
    $exists = $null -ne (Get-Command $command -ErrorAction SilentlyContinue)
    return $exists
}

# Function to load environment variables from .env file
function Load-EnvFile {
    param ($envFilePath)
    
    if (Test-Path $envFilePath) {
        Write-Host "📄 Loading environment variables from $envFilePath" -ForegroundColor Cyan
        
        Get-Content $envFilePath | ForEach-Object {
            if ($_ -match '^([^#][^=]*?)=(.*)$') {
                $name = $matches[1].Trim()
                $value = $matches[2].Trim()
                
                # Remove surrounding quotes if present
                if ($value -match '^"(.*)"$' -or $value -match "^'(.*)'$") {
                    $value = $matches[1]
                }
                
                # Only set if not already set in environment
                if (-not (Get-Item "env:$name" -ErrorAction SilentlyContinue)) {
                    Set-Item "env:$name" $value
                    Write-Host "  ✓ Set $name" -ForegroundColor Green
                } else {
                    Write-Host "  ↳ $name already set, skipping" -ForegroundColor Yellow
                }
            }
        }
        Write-Host "✅ Environment variables loaded" -ForegroundColor Green
    } else {
        Write-Host "⚠️ .env file not found at $envFilePath" -ForegroundColor Yellow
    }
}

# Load environment variables from .env file
Load-EnvFile -envFilePath "web_client\.env"

# Check prerequisites
Write-Host "🔍 Checking prerequisites..." -ForegroundColor Cyan
if (-not (Test-CommandExists "az")) {
    Write-Host "❌ Azure CLI not found. Please install it: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli" -ForegroundColor Red
    exit 1
}

# Check if logged in to Azure
$loginStatus = az account show --query name 2>$null
if (-not $?) {
    Write-Host "🔑 Not logged in to Azure. Please log in..." -ForegroundColor Yellow
    az login
    if (-not $?) {
        Write-Host "❌ Failed to log in to Azure." -ForegroundColor Red
        exit 1
    }
}
Write-Host "✅ Logged in to Azure" -ForegroundColor Green

# Create resource group if it doesn't exist
Write-Host "🔧 Creating resource group if it doesn't exist..." -ForegroundColor Cyan
az group create --name $resourceGroup --location $location
Write-Host "✅ Resource group ready" -ForegroundColor Green

# Create ACR if it doesn't exist
Write-Host "🔧 Creating Azure Container Registry if it doesn't exist..." -ForegroundColor Cyan
$acrExists = az acr show --name $acrName --resource-group $resourceGroup 2>$null
if (-not $?) {
    Write-Host "Creating new ACR: $acrName" -ForegroundColor Yellow
    az acr create --name $acrName --resource-group $resourceGroup --sku Basic --admin-enabled true
}
Write-Host "✅ ACR ready" -ForegroundColor Green

# Build images directly in ACR
Write-Host "🏗️ Building images in ACR..." -ForegroundColor Cyan
Write-Host "Building server image..." -ForegroundColor Yellow
az acr build --registry $acrName --image "$serverAppName`:latest" --file server/Dockerfile ./server
Write-Host "Building web client image..." -ForegroundColor Yellow
az acr build --registry $acrName --image "$webClientAppName`:latest" --file web_client/Dockerfile ./web_client
Write-Host "✅ Images built successfully" -ForegroundColor Green

# Create Container Apps environment if it doesn't exist
Write-Host "🔧 Creating Container Apps environment if it doesn't exist..." -ForegroundColor Cyan
$envExists = az containerapp env show --name $envName --resource-group $resourceGroup 2>$null
if (-not $?) {
    Write-Host "Creating new Container Apps environment: $envName" -ForegroundColor Yellow
    az containerapp env create --name $envName --resource-group $resourceGroup --location $location
}
Write-Host "✅ Container Apps environment ready" -ForegroundColor Green

# Get ACR credentials
Write-Host "🔑 Getting ACR credentials..." -ForegroundColor Cyan
$acrUsername = az acr credential show --name $acrName --query "username" -o tsv
$acrPassword = az acr credential show --name $acrName --query "passwords[0].value" -o tsv
Write-Host "✅ ACR credentials retrieved" -ForegroundColor Green

# Deploy MCP Weather Server
Write-Host "🚀 Deploying MCP Weather Server..." -ForegroundColor Cyan
az containerapp create `
    --name $serverAppName `
    --resource-group $resourceGroup `
    --environment $envName `
    --image "$acrName.azurecr.io/$serverAppName`:latest" `
    --registry-server "$acrName.azurecr.io" `
    --registry-username $acrUsername `
    --registry-password $acrPassword `
    --target-port 8000 `
    --ingress internal `
    --env-vars "HOST=0.0.0.0" "PORT=8000"
Write-Host "✅ MCP Weather Server deployed" -ForegroundColor Green

# Get server FQDN
Write-Host "🔍 Getting server FQDN..." -ForegroundColor Cyan
$serverFqdn = az containerapp show --name $serverAppName --resource-group $resourceGroup --query "properties.configuration.ingress.fqdn" -o tsv
Write-Host "Server FQDN: $serverFqdn" -ForegroundColor Yellow

# Check for Azure OpenAI environment variables
Write-Host "🔍 Checking Azure OpenAI environment variables..." -ForegroundColor Cyan

$missingVars = @()
if (-not $env:AZURE_OPENAI_API_BASE) { $missingVars += "AZURE_OPENAI_API_BASE" }
if (-not $env:AZURE_OPENAI_API_KEY) { $missingVars += "AZURE_OPENAI_API_KEY" }
if (-not $env:AZURE_OPENAI_API_VERSION) { $missingVars += "AZURE_OPENAI_API_VERSION" }
if (-not $env:AZURE_OPENAI_DEPLOYMENT_NAME) { $missingVars += "AZURE_OPENAI_DEPLOYMENT_NAME" }

if ($missingVars.Count -gt 0) {
    Write-Host "⚠️ Missing Azure OpenAI environment variables: $($missingVars -join ', ')" -ForegroundColor Yellow
    Write-Host "💡 You can set these in web_client\.env file or as environment variables" -ForegroundColor Cyan
    
    # Prompt for variables if missing
    if (-not $env:AZURE_OPENAI_API_BASE) { 
        $env:AZURE_OPENAI_API_BASE = Read-Host "Enter Azure OpenAI API Base URL (e.g. https://your-resource.openai.azure.com/)" 
    }
    if (-not $env:AZURE_OPENAI_API_KEY) { 
        $env:AZURE_OPENAI_API_KEY = Read-Host "Enter Azure OpenAI API Key" 
    }
    if (-not $env:AZURE_OPENAI_API_VERSION) { 
        $env:AZURE_OPENAI_API_VERSION = Read-Host "Enter Azure OpenAI API Version (e.g. 2024-02-15-preview)" 
    }
    if (-not $env:AZURE_OPENAI_DEPLOYMENT_NAME) { 
        $env:AZURE_OPENAI_DEPLOYMENT_NAME = Read-Host "Enter Azure OpenAI Deployment Name" 
    }
} else {
    Write-Host "✅ All required Azure OpenAI environment variables are set:" -ForegroundColor Green
    Write-Host "  - AZURE_OPENAI_API_BASE: $env:AZURE_OPENAI_API_BASE" -ForegroundColor Gray
    Write-Host "  - AZURE_OPENAI_API_KEY: $($env:AZURE_OPENAI_API_KEY.Substring(0, [Math]::Min(8, $env:AZURE_OPENAI_API_KEY.Length)))..." -ForegroundColor Gray
    Write-Host "  - AZURE_OPENAI_API_VERSION: $env:AZURE_OPENAI_API_VERSION" -ForegroundColor Gray
    Write-Host "  - AZURE_OPENAI_DEPLOYMENT_NAME: $env:AZURE_OPENAI_DEPLOYMENT_NAME" -ForegroundColor Gray
}
Write-Host "✅ Azure OpenAI environment variables ready" -ForegroundColor Green

# Deploy MCP Web Client
Write-Host "🚀 Deploying MCP Web Client..." -ForegroundColor Cyan
az containerapp create `
    --name $webClientAppName `
    --resource-group $resourceGroup `
    --environment $envName `
    --image "$acrName.azurecr.io/$webClientAppName`:latest" `
    --registry-server "$acrName.azurecr.io" `
    --registry-username $acrUsername `
    --registry-password $acrPassword `
    --target-port 8080 `
    --ingress external `
    --env-vars `
        "MCP_SERVER_URL=https://$serverFqdn/sse" `
        "AZURE_OPENAI_API_BASE=$env:AZURE_OPENAI_API_BASE" `
        "AZURE_OPENAI_API_KEY=$env:AZURE_OPENAI_API_KEY" `
        "AZURE_OPENAI_API_VERSION=$env:AZURE_OPENAI_API_VERSION" `
        "AZURE_OPENAI_DEPLOYMENT_NAME=$env:AZURE_OPENAI_DEPLOYMENT_NAME"
Write-Host "✅ MCP Web Client deployed" -ForegroundColor Green

# Get web client URL
$webClientFqdn = az containerapp show --name $webClientAppName --resource-group $resourceGroup --query "properties.configuration.ingress.fqdn" -o tsv
Write-Host "🎉 Deployment completed successfully!" -ForegroundColor Green
Write-Host "📊 Web Client URL: https://$webClientFqdn" -ForegroundColor Cyan
Write-Host "📋 Try the following example request:" -ForegroundColor Cyan
Write-Host "curl -X POST https://$webClientFqdn/chat -H `"Content-Type: application/json`" -d '{`"query`": `"What is the weather in San Francisco?`"}'" -ForegroundColor Yellow
