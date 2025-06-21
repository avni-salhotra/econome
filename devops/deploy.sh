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

# Environment-specific configuration
ENVIRONMENT="${ENVIRONMENT:-production}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Adjust service name based on environment
if [ "$ENVIRONMENT" != "production" ]; then
    SERVICE_NAME="econome-$ENVIRONMENT"
fi

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

# Environment detection
IS_CLOUD_BUILD=false
if [ -n "$BUILD_ID" ] && [ -n "$PROJECT_ID" ]; then
    IS_CLOUD_BUILD=true
    print_status "Detected Cloud Build environment (BUILD_ID: $BUILD_ID)"
else
    print_status "Detected local environment"
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to get user input (only in local environment)
get_input() {
    local prompt="$1"
    local var_name="$2"
    local default="$3"

    # Skip input in Cloud Build environment
    if [ "$IS_CLOUD_BUILD" = true ]; then
        if [ -n "$default" ]; then
            eval "$var_name='$default'"
            print_status "Using default value for $var_name: $default"
        else
            print_error "Required value $var_name not available in Cloud Build environment"
            exit 1
        fi
        return
    fi

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

    # In Cloud Build, PROJECT_ID is already set
    if [ "$IS_CLOUD_BUILD" = true ]; then
        print_status "Using Cloud Build PROJECT_ID: $PROJECT_ID"
    else
        # Get project ID from user in local environment
        get_input "Enter your Google Cloud Project ID" PROJECT_ID
        # Set the project
        gcloud config set project "$PROJECT_ID"
    fi

    # Enable required APIs (skip in Cloud Build as they should already be enabled)
    if [ "$IS_CLOUD_BUILD" = false ]; then
        print_status "Enabling required Google Cloud APIs..."
        gcloud services enable cloudbuild.googleapis.com
        gcloud services enable run.googleapis.com
        gcloud services enable speech.googleapis.com
        gcloud services enable aiplatform.googleapis.com
        gcloud services enable secretmanager.googleapis.com
    else
        print_status "Skipping API enablement in Cloud Build environment"
    fi

    print_success "Google Cloud project configured"
}

# Function to setup secrets
setup_secrets() {
    print_status "Setting up Google Cloud secrets..."

    # In Cloud Build, secrets should already exist or be handled differently
    if [ "$IS_CLOUD_BUILD" = true ]; then
        print_status "Skipping secret creation in Cloud Build environment"
        print_status "Secrets should be pre-configured or handled by the build trigger"
        return
    fi

    # Check if speech credentials file exists (local environment only)
    if [ ! -f "devops/secrets/speech-credentials.json" ]; then
        print_error "devops/secrets/speech-credentials.json not found!"
        print_status "Please ensure your Google Cloud Speech-to-Text credentials are saved as 'devops/secrets/speech-credentials.json'"
        exit 1
    fi

    # Check if gemini credentials file exists (local environment only)
    if [ ! -f "devops/secrets/gemini-credentials.json" ]; then
        print_error "devops/secrets/gemini-credentials.json not found!"
        print_status "Please ensure your Gemini AI credentials are saved as 'devops/secrets/gemini-credentials.json'"
        exit 1
    fi

    # Create secret for Speech credentials
    print_status "Creating secret for Speech-to-Text credentials..."
    gcloud secrets create speech-credentials --data-file=devops/secrets/speech-credentials.json || {
        print_warning "Speech credentials secret already exists, updating..."
        gcloud secrets versions add speech-credentials --data-file=devops/secrets/speech-credentials.json
    }

    # Create secret for Gemini credentials
    print_status "Creating secret for Gemini AI credentials..."
    gcloud secrets create gemini-credentials --data-file=devops/secrets/gemini-credentials.json || {
        print_warning "Gemini credentials secret already exists, updating..."
        gcloud secrets versions add gemini-credentials --data-file=devops/secrets/gemini-credentials.json
    }

    print_success "All secrets configured"
}

# Function to build and deploy
deploy_service() {
    if [ "$IS_CLOUD_BUILD" = true ]; then
        print_status "Deploying existing image to Cloud Run..."

        # In Cloud Build environment, deploy the image that was built by CI
        print_status "Deploying to environment: $ENVIRONMENT"
        print_status "Using image tag: $IMAGE_TAG"

        gcloud run deploy "$SERVICE_NAME" \
            --image="gcr.io/$PROJECT_ID/econome:$IMAGE_TAG" \
            --platform=managed \
            --region="$REGION" \
            --allow-unauthenticated \
            --memory=2Gi \
            --cpu=2 \
            --concurrency=100 \
            --timeout=3600 \
            --max-instances=10 \
            --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,PORT=8080" \
            --set-secrets="/secrets/speech-credentials.json=speech-credentials:latest" \
            --set-secrets="/secrets/gemini-credentials.json=gemini-credentials:latest"
    else
        print_status "Building and deploying Econome to Cloud Run..."

        # In local environment, trigger full build and deploy
        gcloud builds submit --config devops/cloudbuild-prod.yaml .
    fi

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

    if [ "$IS_CLOUD_BUILD" = true ]; then
        print_status "Running in Cloud Build environment"
        # In Cloud Build, we deploy existing image and setup IAM
        setup_gcloud
        setup_iam
        deploy_service
        print_success "🎉 Cloud Build deployment completed successfully!"
    else
        print_status "Running in local environment"
        # Full local deployment process
        check_prerequisites
        setup_gcloud
        setup_secrets
        setup_iam
        deploy_service

        echo ""
        print_success "🎉 Local deployment completed successfully!"
        print_status "Your Econome service is now running in the cloud!"
        echo ""
    fi
}

# Run main function
main "$@"
