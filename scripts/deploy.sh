#!/bin/bash

# Econome Cloud Deployment Script
# This script automates the deployment of Econome to Google Cloud Run

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID=""
REGION="us-central1"
SERVICE_NAME="econome"
CREDENTIALS_FILE=""

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to get user input
get_input() {
    local prompt="$1"
    local var_name="$2"
    local default="$3"
    
    if [ -n "$default" ]; then
        read -p "$prompt [$default]: " input
        if [ -z "$input" ]; then
            input="$default"
        fi
    else
        read -p "$prompt: " input
        while [ -z "$input" ]; do
            print_error "This field is required!"
            read -p "$prompt: " input
        done
    fi
    
    eval "$var_name='$input'"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if gcloud is installed
    if ! command_exists gcloud; then
        print_error "Google Cloud CLI (gcloud) is not installed!"
        print_status "Please install it from: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    
    # Check if docker is installed
    if ! command_exists docker; then
        print_error "Docker is not installed!"
        print_status "Please install Docker from: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    print_success "All prerequisites are installed"
}

# Function to setup Google Cloud project
setup_gcloud() {
    print_status "Setting up Google Cloud configuration..."
    
    # Get project ID
    get_input "Enter your Google Cloud Project ID" PROJECT_ID
    
    # Set the project
    gcloud config set project "$PROJECT_ID"
    
    # Enable required APIs
    print_status "Enabling required Google Cloud APIs..."
    gcloud services enable cloudbuild.googleapis.com
    gcloud services enable run.googleapis.com
    gcloud services enable speech.googleapis.com
    gcloud services enable aiplatform.googleapis.com
    gcloud services enable secretmanager.googleapis.com
    
    print_success "Google Cloud project configured"
}

# Function to setup secrets
setup_secrets() {
    print_status "Setting up Google Cloud secrets..."

    # Check if speech credentials file exists
    if [ ! -f "speech-credentials.json" ]; then
        print_error "speech-credentials.json not found!"
        print_status "Please ensure your Google Cloud Speech-to-Text credentials are saved as 'speech-credentials.json'"
        exit 1
    fi

    # Check if gemini credentials file exists
    if [ ! -f "gemini-credentials.json" ]; then
        print_error "gemini-credentials.json not found!"
        print_status "Please ensure your Gemini AI credentials are saved as 'gemini-credentials.json'"
        exit 1
    fi

    # Create secret for Speech credentials
    print_status "Creating secret for Speech-to-Text credentials..."
    gcloud secrets create speech-credentials --data-file=speech-credentials.json || {
        print_warning "Speech credentials secret already exists, updating..."
        gcloud secrets versions add speech-credentials --data-file=speech-credentials.json
    }

    # Create secret for Gemini credentials
    print_status "Creating secret for Gemini AI credentials..."
    gcloud secrets create gemini-credentials --data-file=gemini-credentials.json || {
        print_warning "Gemini credentials secret already exists, updating..."
        gcloud secrets versions add gemini-credentials --data-file=gemini-credentials.json
    }

    print_success "All secrets configured"
}

# Function to build and deploy
deploy_service() {
    print_status "Building and deploying Econome to Cloud Run..."
    
    # Submit build to Cloud Build
    gcloud builds submit --config cloudbuild.yaml .
    
    print_success "Deployment completed!"
    
    # Get service URL
    SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format="value(status.url)")
    
    print_success "🎉 Econome is now deployed!"
    print_status "Service URL: $SERVICE_URL"
    print_status "Health check: $SERVICE_URL/health"
    print_status "API docs: $SERVICE_URL/docs"
}

# Function to setup IAM permissions
setup_iam() {
    print_status "Setting up IAM permissions..."
    
    # Get the Cloud Run service account
    SERVICE_ACCOUNT=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format="value(spec.template.spec.serviceAccountName)" 2>/dev/null || echo "")
    
    if [ -z "$SERVICE_ACCOUNT" ]; then
        # Use the default compute service account
        PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
        SERVICE_ACCOUNT="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"
    fi
    
    print_status "Granting permissions to service account: $SERVICE_ACCOUNT"
    
    # Grant necessary permissions
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SERVICE_ACCOUNT" \
        --role="roles/secretmanager.secretAccessor"
    
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SERVICE_ACCOUNT" \
        --role="roles/speech.client"
    
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SERVICE_ACCOUNT" \
        --role="roles/aiplatform.user"
    
    print_success "IAM permissions configured"
}

# Main deployment function
main() {
    echo "🚀 Econome Cloud Deployment Script"
    echo "=================================="
    
    check_prerequisites
    setup_gcloud
    setup_secrets
    setup_iam
    deploy_service
    
    echo ""
    print_success "🎉 Deployment completed successfully!"
    print_status "Your Econome service is now running in the cloud!"
    echo ""
}

# Run main function
main "$@"
