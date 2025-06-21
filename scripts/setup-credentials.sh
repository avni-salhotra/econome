#!/bin/bash

# Econome Credential Setup Helper
# This script helps set up the required credential files

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Function to check if file exists
check_file() {
    local file="$1"
    local description="$2"
    
    if [ -f "$file" ]; then
        print_success "$description found: $file"
        return 0
    else
        print_error "$description not found: $file"
        return 1
    fi
}

# Function to copy credentials
setup_credentials() {
    print_status "Setting up Econome credentials..."
    echo ""
    
    # Check if user has a single service account key
    if [ -f "service-account-key.json" ]; then
        print_status "Found service-account-key.json, copying to required locations..."
        
        cp service-account-key.json speech-credentials.json
        cp service-account-key.json gemini-credentials.json
        
        print_success "Credentials copied successfully!"
        return 0
    fi
    
    # Check for existing credential files
    local speech_exists=false
    local gemini_exists=false
    
    if check_file "speech-credentials.json" "Speech-to-Text credentials"; then
        speech_exists=true
    fi
    
    if check_file "gemini-credentials.json" "Gemini AI credentials"; then
        gemini_exists=true
    fi
    
    # If both exist, we're good
    if [ "$speech_exists" = true ] && [ "$gemini_exists" = true ]; then
        print_success "All required credentials are present!"
        return 0
    fi
    
    # If one exists, offer to copy it
    if [ "$speech_exists" = true ] && [ "$gemini_exists" = false ]; then
        print_status "Speech credentials found, copying to gemini-credentials.json..."
        cp speech-credentials.json gemini-credentials.json
        print_success "Gemini credentials created from speech credentials"
        return 0
    fi
    
    if [ "$gemini_exists" = true ] && [ "$speech_exists" = false ]; then
        print_status "Gemini credentials found, copying to speech-credentials.json..."
        cp gemini-credentials.json speech-credentials.json
        print_success "Speech credentials created from gemini credentials"
        return 0
    fi
    
    # Neither exists, show instructions
    print_error "No credential files found!"
    echo ""
    print_status "Please follow these steps:"
    echo ""
    echo "1. Go to Google Cloud Console: https://console.cloud.google.com"
    echo "2. Navigate to 'IAM & Admin' > 'Service Accounts'"
    echo "3. Create a service account with these roles:"
    echo "   - Cloud Run Admin"
    echo "   - Speech-to-Text Admin"
    echo "   - AI Platform Admin"
    echo "   - Secret Manager Admin"
    echo "4. Download the JSON key file"
    echo "5. Save it as 'service-account-key.json' in this folder"
    echo "6. Run this script again"
    echo ""
    print_status "Alternatively, you can manually place:"
    echo "   - speech-credentials.json (for Google Cloud Speech-to-Text)"
    echo "   - gemini-credentials.json (for Gemini AI)"
    echo ""
    
    return 1
}

# Function to validate credentials
validate_credentials() {
    print_status "Validating credentials..."
    
    # Check JSON format
    for file in "speech-credentials.json" "gemini-credentials.json"; do
        if [ -f "$file" ]; then
            if python3 -c "import json; json.load(open('$file'))" 2>/dev/null; then
                print_success "$file is valid JSON"
            else
                print_error "$file is not valid JSON!"
                return 1
            fi
        fi
    done
    
    print_success "All credential files are valid!"
    return 0
}

# Function to show next steps
show_next_steps() {
    echo ""
    print_success "🎉 Credential setup completed!"
    echo ""
    print_status "Next steps:"
    echo "1. For local development: ./setup-local.sh"
    echo "2. For cloud deployment: ./deploy.sh"
    echo ""
    print_status "Files created:"
    echo "- speech-credentials.json (Google Cloud Speech-to-Text)"
    echo "- gemini-credentials.json (Gemini AI)"
    echo ""
}

# Main function
main() {
    echo "🔑 Econome Credential Setup"
    echo "=========================="
    echo ""
    
    if setup_credentials && validate_credentials; then
        show_next_steps
    else
        print_error "Credential setup failed. Please follow the instructions above."
        exit 1
    fi
}

# Run main function
main "$@"
