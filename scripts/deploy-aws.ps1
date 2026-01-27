# AWS ECS Deployment Script (PowerShell)
# Helper script for deploying the Contact Center Orchestrator to AWS ECS

param(
    [Parameter(Position=0)]
    [ValidateSet('init','plan','apply','destroy','output','logs','status')]
    [string]$Command,
    
    [Parameter(Position=1)]
    [ValidateSet('staging','production')]
    [string]$Environment,
    
    [Parameter()]
    [Alias('i')]
    [string]$Image,
    
    [Parameter()]
    [switch]$Help
)

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Blue
    Write-Host $Message -ForegroundColor Blue
    Write-Host "========================================" -ForegroundColor Blue
    Write-Host ""
}

function Show-Usage {
    @"
AWS ECS Deployment Script

Usage: .\deploy-aws.ps1 [COMMAND] [ENVIRONMENT] [OPTIONS]

Commands:
    init                Initialize Terraform
    plan                Plan deployment
    apply               Apply deployment
    destroy             Destroy infrastructure
    output              Show Terraform outputs
    logs                Tail CloudWatch logs
    status              Show ECS service status

Environment:
    staging             Staging environment
    production          Production environment

Options:
    -Image <uri>        Docker image URI (required for plan/apply)
    -Help               Show this help message

Environment Variables:
    OPENAI_API_KEY      OpenAI API key (required)

Examples:
    # Initialize
    .\deploy-aws.ps1 init

    # Plan staging deployment
    .\deploy-aws.ps1 plan staging -Image ghcr.io/myorg/myrepo:latest

    # Apply to production
    .\deploy-aws.ps1 apply production -Image ghcr.io/myorg/myrepo:v1.0.0

    # View outputs
    .\deploy-aws.ps1 output staging

    # Check service status
    .\deploy-aws.ps1 status production

    # View logs
    .\deploy-aws.ps1 logs staging
"@
}

function Test-Prerequisites {
    Write-Header "Checking Prerequisites"
    
    # Check AWS CLI
    if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
        Write-Error "AWS CLI not found. Please install it: https://aws.amazon.com/cli/"
        exit 1
    }
    Write-Success "AWS CLI found: $(aws --version)"
    
    # Check Terraform
    if (-not (Get-Command terraform -ErrorAction SilentlyContinue)) {
        Write-Error "Terraform not found. Please install it: https://www.terraform.io/downloads"
        exit 1
    }
    $tfVersion = (terraform version -json | ConvertFrom-Json).terraform_version
    Write-Success "Terraform found: $tfVersion"
    
    # Check AWS credentials
    try {
        aws sts get-caller-identity | Out-Null
        Write-Success "AWS credentials configured"
    } catch {
        Write-Error "AWS credentials not configured. Run 'aws configure'"
        exit 1
    }
}

function Initialize-Terraform {
    Write-Header "Initializing Terraform"
    Push-Location terraform
    terraform init
    Pop-Location
    Write-Success "Terraform initialized"
}

function Plan-Deployment {
    param([string]$Env, [string]$ImageUri)
    
    if (-not $Env) {
        Write-Error "Environment not specified"
        Show-Usage
        exit 1
    }
    
    if (-not $ImageUri) {
        Write-Error "Docker image not specified. Use -Image parameter"
        exit 1
    }
    
    if (-not $env:OPENAI_API_KEY) {
        Write-Error "OPENAI_API_KEY environment variable not set"
        exit 1
    }
    
    Write-Header "Planning Deployment to $Env"
    Push-Location terraform
    
    terraform plan `
        -var-file="environments/$Env.tfvars" `
        -var="container_image=$ImageUri" `
        -var="openai_api_key=$($env:OPENAI_API_KEY)" `
        -out="$Env.tfplan"
    
    Pop-Location
    Write-Success "Plan saved to $Env.tfplan"
}

function Apply-Deployment {
    param([string]$Env, [string]$ImageUri)
    
    if (-not $Env) {
        Write-Error "Environment not specified"
        Show-Usage
        exit 1
    }
    
    if (-not $ImageUri) {
        Write-Error "Docker image not specified. Use -Image parameter"
        exit 1
    }
    
    if (-not $env:OPENAI_API_KEY) {
        Write-Error "OPENAI_API_KEY environment variable not set"
        exit 1
    }
    
    Write-Header "Deploying to $Env"
    Write-Warning "This will apply changes to your AWS infrastructure"
    $confirm = Read-Host "Are you sure you want to continue? (yes/no)"
    
    if ($confirm -ne "yes") {
        Write-Info "Deployment cancelled"
        exit 0
    }
    
    Push-Location terraform
    
    terraform apply `
        -var-file="environments/$Env.tfvars" `
        -var="container_image=$ImageUri" `
        -var="openai_api_key=$($env:OPENAI_API_KEY)" `
        -auto-approve
    
    Write-Success "Deployment complete!"
    
    Write-Header "Deployment Information"
    terraform output
    
    Pop-Location
}

function Remove-Infrastructure {
    param([string]$Env)
    
    if (-not $Env) {
        Write-Error "Environment not specified"
        Show-Usage
        exit 1
    }
    
    Write-Header "Destroying Infrastructure in $Env"
    Write-Error "WARNING: This will destroy all resources in $Env!"
    $confirm = Read-Host "Are you absolutely sure? Type '$Env' to confirm"
    
    if ($confirm -ne $Env) {
        Write-Info "Destruction cancelled"
        exit 0
    }
    
    Push-Location terraform
    
    terraform destroy `
        -var-file="environments/$Env.tfvars" `
        -var="container_image=dummy" `
        -var="openai_api_key=dummy" `
        -auto-approve
    
    Pop-Location
    Write-Success "Infrastructure destroyed"
}

function Show-Output {
    param([string]$Env)
    
    if (-not $Env) {
        Write-Error "Environment not specified"
        Show-Usage
        exit 1
    }
    
    Write-Header "Terraform Outputs for $Env"
    Push-Location terraform
    terraform output
    Pop-Location
}

function Show-Logs {
    param([string]$Env)
    
    if (-not $Env) {
        Write-Error "Environment not specified"
        Show-Usage
        exit 1
    }
    
    Write-Header "Tailing Logs for $Env"
    $logGroup = "/ecs/contact-center-orchestrator-$Env"
    
    Write-Info "Log group: $logGroup"
    aws logs tail $logGroup --follow
}

function Show-Status {
    param([string]$Env)
    
    if (-not $Env) {
        Write-Error "Environment not specified"
        Show-Usage
        exit 1
    }
    
    Write-Header "Service Status for $Env"
    
    $cluster = "contact-center-orchestrator-$Env"
    $service = "contact-center-orchestrator-service"
    
    Write-Info "Cluster: $cluster"
    Write-Info "Service: $service"
    Write-Host ""
    
    aws ecs describe-services `
        --cluster $cluster `
        --services $service `
        --query 'services[0].{Status:status,DesiredCount:desiredCount,RunningCount:runningCount,PendingCount:pendingCount}' `
        --output table
    
    Write-Host ""
    Write-Info "Recent events:"
    aws ecs describe-services `
        --cluster $cluster `
        --services $service `
        --query 'services[0].events[:5]' `
        --output table
}

# Main execution
if ($Help -or -not $Command) {
    Show-Usage
    exit 0
}

switch ($Command) {
    'init' {
        Test-Prerequisites
        Initialize-Terraform
    }
    'plan' {
        Test-Prerequisites
        Plan-Deployment -Env $Environment -ImageUri $Image
    }
    'apply' {
        Test-Prerequisites
        Apply-Deployment -Env $Environment -ImageUri $Image
    }
    'destroy' {
        Test-Prerequisites
        Remove-Infrastructure -Env $Environment
    }
    'output' {
        Show-Output -Env $Environment
    }
    'logs' {
        Show-Logs -Env $Environment
    }
    'status' {
        Show-Status -Env $Environment
    }
    default {
        Write-Error "Unknown command: $Command"
        Show-Usage
        exit 1
    }
}
