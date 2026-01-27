#!/bin/bash

# AWS ECS Deployment Script
# Helper script for deploying the Contact Center Orchestrator to AWS ECS

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_info() {
    echo -e "${BLUE}ℹ ${1}${NC}"
}

print_success() {
    echo -e "${GREEN}✓ ${1}${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ ${1}${NC}"
}

print_error() {
    echo -e "${RED}✗ ${1}${NC}"
}

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}${1}${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI not found. Please install it: https://aws.amazon.com/cli/"
        exit 1
    fi
    print_success "AWS CLI found: $(aws --version)"
    
    # Check Terraform
    if ! command -v terraform &> /dev/null; then
        print_error "Terraform not found. Please install it: https://www.terraform.io/downloads"
        exit 1
    fi
    print_success "Terraform found: $(terraform version -json | jq -r '.terraform_version')"
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured. Run 'aws configure'"
        exit 1
    fi
    print_success "AWS credentials configured"
    
    # Check jq
    if ! command -v jq &> /dev/null; then
        print_warning "jq not found (optional but recommended)"
    fi
}

# Display usage
usage() {
    cat << EOF
Usage: $0 [COMMAND] [OPTIONS]

Commands:
    init                Initialize Terraform
    plan <env>          Plan deployment (staging|production)
    apply <env>         Apply deployment (staging|production)
    destroy <env>       Destroy infrastructure (staging|production)
    output <env>        Show Terraform outputs (staging|production)
    logs <env>          Tail CloudWatch logs (staging|production)
    status <env>        Show ECS service status (staging|production)

Options:
    -h, --help          Show this help message
    -i, --image <uri>   Docker image URI (required for plan/apply)

Environment Variables:
    OPENAI_API_KEY      OpenAI API key (required)
    TF_VAR_*            Additional Terraform variables

Examples:
    # Initialize
    $0 init

    # Plan staging deployment
    $0 plan staging -i ghcr.io/myorg/myrepo:latest

    # Apply to production
    $0 apply production -i ghcr.io/myorg/myrepo:v1.0.0

    # View outputs
    $0 output staging

    # Check service status
    $0 status production

    # View logs
    $0 logs staging
EOF
}

# Initialize Terraform
terraform_init() {
    print_header "Initializing Terraform"
    cd terraform
    terraform init
    print_success "Terraform initialized"
    cd ..
}

# Plan deployment
terraform_plan() {
    local env=$1
    local image=$2
    
    if [ -z "$env" ]; then
        print_error "Environment not specified"
        usage
        exit 1
    fi
    
    if [ -z "$image" ]; then
        print_error "Docker image not specified. Use -i or --image flag"
        exit 1
    fi
    
    if [ -z "$OPENAI_API_KEY" ]; then
        print_error "OPENAI_API_KEY environment variable not set"
        exit 1
    fi
    
    print_header "Planning Deployment to ${env}"
    cd terraform
    
    terraform plan \
        -var-file="environments/${env}.tfvars" \
        -var="container_image=${image}" \
        -var="openai_api_key=${OPENAI_API_KEY}" \
        -out="${env}.tfplan"
    
    print_success "Plan saved to ${env}.tfplan"
    cd ..
}

# Apply deployment
terraform_apply() {
    local env=$1
    local image=$2
    
    if [ -z "$env" ]; then
        print_error "Environment not specified"
        usage
        exit 1
    fi
    
    if [ -z "$image" ]; then
        print_error "Docker image not specified. Use -i or --image flag"
        exit 1
    fi
    
    if [ -z "$OPENAI_API_KEY" ]; then
        print_error "OPENAI_API_KEY environment variable not set"
        exit 1
    fi
    
    print_header "Deploying to ${env}"
    print_warning "This will apply changes to your AWS infrastructure"
    read -p "Are you sure you want to continue? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        print_info "Deployment cancelled"
        exit 0
    fi
    
    cd terraform
    
    terraform apply \
        -var-file="environments/${env}.tfvars" \
        -var="container_image=${image}" \
        -var="openai_api_key=${OPENAI_API_KEY}" \
        -auto-approve
    
    print_success "Deployment complete!"
    
    # Show outputs
    echo ""
    print_header "Deployment Information"
    terraform output
    
    cd ..
}

# Destroy infrastructure
terraform_destroy() {
    local env=$1
    
    if [ -z "$env" ]; then
        print_error "Environment not specified"
        usage
        exit 1
    fi
    
    print_header "Destroying Infrastructure in ${env}"
    print_error "WARNING: This will destroy all resources in ${env}!"
    read -p "Are you absolutely sure? Type '${env}' to confirm: " confirm
    
    if [ "$confirm" != "$env" ]; then
        print_info "Destruction cancelled"
        exit 0
    fi
    
    cd terraform
    
    # Need dummy values for required variables
    terraform destroy \
        -var-file="environments/${env}.tfvars" \
        -var="container_image=dummy" \
        -var="openai_api_key=dummy" \
        -auto-approve
    
    print_success "Infrastructure destroyed"
    cd ..
}

# Show outputs
terraform_output() {
    local env=$1
    
    if [ -z "$env" ]; then
        print_error "Environment not specified"
        usage
        exit 1
    fi
    
    print_header "Terraform Outputs for ${env}"
    cd terraform
    terraform output
    cd ..
}

# View logs
view_logs() {
    local env=$1
    
    if [ -z "$env" ]; then
        print_error "Environment not specified"
        usage
        exit 1
    fi
    
    print_header "Tailing Logs for ${env}"
    local log_group="/ecs/contact-center-orchestrator-${env}"
    
    print_info "Log group: ${log_group}"
    aws logs tail "${log_group}" --follow
}

# Check service status
check_status() {
    local env=$1
    
    if [ -z "$env" ]; then
        print_error "Environment not specified"
        usage
        exit 1
    fi
    
    print_header "Service Status for ${env}"
    
    local cluster="contact-center-orchestrator-${env}"
    local service="contact-center-orchestrator-service"
    
    print_info "Cluster: ${cluster}"
    print_info "Service: ${service}"
    echo ""
    
    # Get service info
    aws ecs describe-services \
        --cluster "${cluster}" \
        --services "${service}" \
        --query 'services[0].{Status:status,DesiredCount:desiredCount,RunningCount:runningCount,PendingCount:pendingCount}' \
        --output table
    
    echo ""
    print_info "Recent events:"
    aws ecs describe-services \
        --cluster "${cluster}" \
        --services "${service}" \
        --query 'services[0].events[:5]' \
        --output table
}

# Main script
main() {
    if [ $# -eq 0 ]; then
        usage
        exit 0
    fi
    
    local command=$1
    shift
    
    case $command in
        init)
            check_prerequisites
            terraform_init
            ;;
        plan)
            check_prerequisites
            local env=""
            local image=""
            while [[ $# -gt 0 ]]; do
                case $1 in
                    -i|--image)
                        image="$2"
                        shift 2
                        ;;
                    *)
                        env="$1"
                        shift
                        ;;
                esac
            done
            terraform_plan "$env" "$image"
            ;;
        apply)
            check_prerequisites
            local env=""
            local image=""
            while [[ $# -gt 0 ]]; do
                case $1 in
                    -i|--image)
                        image="$2"
                        shift 2
                        ;;
                    *)
                        env="$1"
                        shift
                        ;;
                esac
            done
            terraform_apply "$env" "$image"
            ;;
        destroy)
            check_prerequisites
            terraform_destroy "$1"
            ;;
        output)
            terraform_output "$1"
            ;;
        logs)
            view_logs "$1"
            ;;
        status)
            check_status "$1"
            ;;
        -h|--help)
            usage
            ;;
        *)
            print_error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

main "$@"
