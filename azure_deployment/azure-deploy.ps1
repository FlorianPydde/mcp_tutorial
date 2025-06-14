# Simple Azure Deployment Script
# Deploy MCP Tutorial to Azure Container Apps
# 
# Prerequisites:
# 1. Install Azure CLI: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
# 2. Run: az login
# 3. Create web_client\.env file with your Azure OpenAI settings

# ===== CONFIGURATION =====
$resourceGroup = "mcp-tutorial-rg"
$location = "westeurope"  # Amsterdam, Netherlands - Great for European users
# Generate a unique ACR name using timestamp to avoid conflicts
$acrName = "mcptutorial"
$envName = "mcp-tutorial-env"
$serverApp = "mcp-weather-server"
$webClientApp = "mcp-web-client"

Write-Host "Using ACR name: $acrName" -ForegroundColor Cyan

# ===== LOAD ENVIRONMENT VARIABLES =====
Write-Host "Loading environment variables..." -ForegroundColor Cyan

# Load server environment variables
if (Test-Path "server\.env") {
    Write-Host "Loading server settings..." -ForegroundColor Green
    Get-Content "server\.env" | Where-Object {$_ -match "=" -and $_ -notmatch "^#"} | ForEach-Object {
        $name, $value = $_ -split "=", 2
        $cleanName = $name.Trim()
        $cleanValue = $value.Trim().Trim('"').Trim("'")
        [Environment]::SetEnvironmentVariable($cleanName, $cleanValue)
        Write-Host "  Server: $cleanName" -ForegroundColor Gray
    }
}

# Load web client environment variables  
if (Test-Path "web_client\.env") {
    Write-Host "Loading web client settings..." -ForegroundColor Green
    Get-Content "web_client\.env" | Where-Object {$_ -match "=" -and $_ -notmatch "^#"} | ForEach-Object {
        $name, $value = $_ -split "=", 2
        $cleanName = $name.Trim()
        $cleanValue = $value.Trim().Trim('"').Trim("'")
        [Environment]::SetEnvironmentVariable($cleanName, $cleanValue)
        Write-Host "  Client: $cleanName" -ForegroundColor Gray
    }
} else {
    Write-Host "No web_client\.env file found - you'll be prompted for Azure OpenAI settings" -ForegroundColor Yellow
}

# ===== CHECK PREREQUISITES =====
Write-Host "Checking prerequisites..." -ForegroundColor Cyan

# Check Azure CLI
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Azure CLI not found!" -ForegroundColor Red
    Write-Host "Install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli" -ForegroundColor Yellow
    exit
}

# Check Azure login and show current subscription
$loginCheck = az account show 2>$null
if (-not $?) {
    Write-Host "Please log in to Azure..." -ForegroundColor Yellow
    az login
} else {
    $currentSub = az account show --query "{name:name,id:id}" -o table
    Write-Host "Current Azure subscription:" -ForegroundColor Green
    Write-Host $currentSub -ForegroundColor Gray
}

# ===== CREATE RESOURCES =====
Write-Host "Creating Azure resources..." -ForegroundColor Cyan

# Resource Group
Write-Host "Creating resource group..." -ForegroundColor Yellow
az group create --name $resourceGroup --location $location
if (-not $?) {
    Write-Host "ERROR: Failed to create resource group!" -ForegroundColor Red
    exit 1
}

# Container Registry
Write-Host "Creating Azure Container Registry..." -ForegroundColor Yellow
$acrExists = az acr show --name $acrName --resource-group $resourceGroup 2>$null
if (-not $?) {
    Write-Host "Creating new ACR: $acrName (this may take a few minutes)..." -ForegroundColor Yellow
    az acr create --name $acrName --resource-group $resourceGroup --sku Basic --admin-enabled true
    if (-not $?) {
        Write-Host "ERROR: Failed to create Azure Container Registry!" -ForegroundColor Red
        exit 1
    }
      # Wait for ACR to be ready
    Write-Host "Waiting for ACR to be ready..." -ForegroundColor Yellow
    $maxAttempts = 30  # 5 minutes max (10 seconds * 30)
    $attempt = 0
    
    do {
        Start-Sleep 10
        $attempt++
        $acrStatus = az acr show --name $acrName --resource-group $resourceGroup --query "provisioningState" -o tsv 2>$null
        Write-Host "ACR Status (attempt $attempt/$maxAttempts): $acrStatus" -ForegroundColor Gray
        
        if ($attempt -ge $maxAttempts) {
            Write-Host "ERROR: Timeout waiting for ACR to be ready!" -ForegroundColor Red
            exit 1
        }
    } while ($acrStatus -ne "Succeeded")
    
    Write-Host "ACR is ready!" -ForegroundColor Green
} else {
    Write-Host "ACR already exists" -ForegroundColor Green
}

# Small delay before creating next resource
Write-Host "Waiting a moment before creating Container Apps environment..." -ForegroundColor Gray
Start-Sleep 5

# Container Apps Environment
Write-Host "Creating Container Apps environment..." -ForegroundColor Yellow
$envExists = az containerapp env show --name $envName --resource-group $resourceGroup 2>$null
if (-not $?) {
    Write-Host "Creating new Container Apps environment: $envName (this may take 5-10 minutes)..." -ForegroundColor Yellow
    Write-Host "This will also create a Log Analytics workspace automatically..." -ForegroundColor Gray
    
    # Start the environment creation
    az containerapp env create --name $envName --resource-group $resourceGroup --location $location
    if (-not $?) {
        Write-Host "ERROR: Failed to start Container Apps environment creation!" -ForegroundColor Red
        exit 1
    }
    
    # Wait for environment to be ready (this can take several minutes)
    Write-Host "Waiting for Container Apps environment to be ready..." -ForegroundColor Yellow
    $maxAttempts = 60  # 10 minutes max (10 seconds * 60)
    $attempt = 0
    
    do {
        Start-Sleep 10
        $attempt++
        $envStatus = az containerapp env show --name $envName --resource-group $resourceGroup --query "properties.provisioningState" -o tsv 2>$null
        Write-Host "Environment Status (attempt $attempt/$maxAttempts): $envStatus" -ForegroundColor Gray
        
        if ($attempt -ge $maxAttempts) {
            Write-Host "ERROR: Timeout waiting for Container Apps environment to be ready!" -ForegroundColor Red
            Write-Host "You can check the status in Azure Portal and run the script again later." -ForegroundColor Yellow
            exit 1
        }
    } while ($envStatus -ne "Succeeded")
    
    Write-Host "Container Apps environment is ready!" -ForegroundColor Green
} else {
    Write-Host "Container Apps environment already exists" -ForegroundColor Green
}

# ===== BUILD IMAGES =====
Write-Host "Building Docker images..." -ForegroundColor Cyan

# Verify ACR is accessible before building
Write-Host "Verifying ACR access..." -ForegroundColor Yellow
$acrLoginServer = az acr show --name $acrName --resource-group $resourceGroup --query "loginServer" -o tsv
if (-not $?) {
    Write-Host "ERROR: Cannot access ACR. Please check if it exists and you have permissions." -ForegroundColor Red
    exit 1
}
Write-Host "ACR Login Server: $acrLoginServer" -ForegroundColor Green

# Additional verification - test ACR login capability (better test for build readiness)
Write-Host "Testing ACR build readiness..." -ForegroundColor Yellow
$maxRetries = 10
$retry = 0

do {
    $retry++
    Write-Host "Testing ACR login capability (attempt $retry/$maxRetries)..." -ForegroundColor Gray
    
    # Try ACR login - this is a better test for ACR build readiness
    $acrLoginTest = az acr login --name $acrName --expose-token --output tsv --query accessToken 2>$null
    if ($? -and $acrLoginTest) {
        Write-Host "ACR is ready for build operations!" -ForegroundColor Green
        break
    }
    
    if ($retry -ge $maxRetries) {
        Write-Host "ERROR: ACR is not ready for build operations!" -ForegroundColor Red
        Write-Host "The ACR may still be initializing internal services." -ForegroundColor Yellow
        Write-Host "Please wait 5-10 more minutes and run the script again." -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "ACR login not ready yet, waiting 45 seconds..." -ForegroundColor Yellow
    Start-Sleep 45
} while ($retry -lt $maxRetries)

Write-Host "Building server image..." -ForegroundColor Yellow
az acr build --registry $acrName --image "$serverApp`:latest" --file server/Dockerfile ./server
if (-not $?) {
    Write-Host "ERROR: Failed to build server image!" -ForegroundColor Red
    Write-Host "ACR Status check:" -ForegroundColor Yellow
    az acr show --name $acrName --resource-group $resourceGroup --query "{name:name,provisioningState:provisioningState,loginServer:loginServer}" -o table
    exit 1
}

Write-Host "Building web client image..." -ForegroundColor Yellow
az acr build --registry $acrName --image "$webClientApp`:latest" --file web_client/Dockerfile ./web_client
if (-not $?) {
    Write-Host "ERROR: Failed to build web client image!" -ForegroundColor Red
    exit 1
}

# ===== GET REGISTRY CREDENTIALS =====
$acrUsername = az acr credential show --name $acrName --query "username" -o tsv
$acrPassword = az acr credential show --name $acrName --query "passwords[0].value" -o tsv

# ===== DEPLOY SERVER =====
Write-Host "Deploying weather server..." -ForegroundColor Cyan

# Use server settings from .env or defaults
$serverHost = if ($env:HOST) { $env:HOST } else { "0.0.0.0" }
$serverPort = if ($env:PORT) { $env:PORT } else { "8000" }
$logLevel = if ($env:LOG_LEVEL) { $env:LOG_LEVEL } else { "INFO" }

az containerapp create `
    --name $serverApp `
    --resource-group $resourceGroup `
    --environment $envName `
    --image "$acrName.azurecr.io/$serverApp`:latest" `
    --registry-server "$acrName.azurecr.io" `
    --registry-username $acrUsername `
    --registry-password $acrPassword `
    --target-port $serverPort `
    --ingress internal `
    --env-vars `
        "HOST=$serverHost" `
        "PORT=$serverPort" `
        "LOG_LEVEL=$logLevel"

# Get server URL
$serverUrl = az containerapp show --name $serverApp --resource-group $resourceGroup --query "properties.configuration.ingress.fqdn" -o tsv

# ===== CHECK AZURE OPENAI SETTINGS =====
Write-Host "Checking Azure OpenAI settings..." -ForegroundColor Cyan
if (-not $env:AZURE_OPENAI_API_BASE) { $env:AZURE_OPENAI_API_BASE = Read-Host "Azure OpenAI Endpoint (e.g. https://your-resource.openai.azure.com/)" }
if (-not $env:AZURE_OPENAI_API_KEY) { $env:AZURE_OPENAI_API_KEY = Read-Host "Azure OpenAI API Key" }
if (-not $env:AZURE_OPENAI_API_VERSION) { $env:AZURE_OPENAI_API_VERSION = Read-Host "API Version (e.g. 2024-02-15-preview)" }
if (-not $env:AZURE_OPENAI_DEPLOYMENT_NAME) { $env:AZURE_OPENAI_DEPLOYMENT_NAME = Read-Host "Model Deployment Name" }



# ===== DEPLOY WEB CLIENT =====
Write-Host "Deploying web client..." -ForegroundColor Cyan

# Use web client settings from .env or defaults
$webClientPort = "8080"  # Default for web client
$webClientLogLevel = if ($env:LOG_LEVEL) { $env:LOG_LEVEL } else { "INFO" }

az containerapp create `
    --name $webClientApp `
    --resource-group $resourceGroup `
    --environment $envName `
    --image "$acrName.azurecr.io/$webClientApp`:latest" `
    --registry-server "$acrName.azurecr.io" `
    --registry-username $acrUsername `
    --registry-password $acrPassword `
    --target-port $webClientPort `
    --ingress external `
    --env-vars `
        "MCP_SERVER_URL=https://$serverUrl/sse" `
        "AZURE_OPENAI_API_BASE=$env:AZURE_OPENAI_API_BASE" `
        "AZURE_OPENAI_API_KEY=$env:AZURE_OPENAI_API_KEY" `
        "AZURE_OPENAI_API_VERSION=$env:AZURE_OPENAI_API_VERSION" `
        "AZURE_OPENAI_DEPLOYMENT_NAME=$env:AZURE_OPENAI_DEPLOYMENT_NAME" `
        "LOG_LEVEL=$webClientLogLevel" `

# ===== DEPLOYMENT COMPLETE =====
$webUrl = az containerapp show --name $webClientApp --resource-group $resourceGroup --query "properties.configuration.ingress.fqdn" -o tsv

Write-Host ""
Write-Host "🎉 DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "Cehck Web App Status at: https://$webUrl/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "Test with:" -ForegroundColor Cyan
Write-Host "curl -X POST https://$webUrl/chat -H `"Content-Type: application/json`" -d '{`"query`": `"What is the weather in Paris?`"}'" -ForegroundColor White
