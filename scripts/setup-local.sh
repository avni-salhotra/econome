#!/bin/bash

# Econome Local Development Setup Script
# This script helps set up Econome for local development

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
    
    # Check Python
    if ! command_exists python3; then
        print_error "Python 3 is not installed!"
        exit 1
    fi
    
    # Check pip
    if ! command_exists pip3; then
        print_error "pip3 is not installed!"
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

# Function to setup virtual environment
setup_venv() {
    print_status "Setting up Python virtual environment..."
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        print_success "Virtual environment created"
    else
        print_warning "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install requirements
    print_status "Installing Python dependencies..."
    pip install -r requirements.txt
    
    print_success "Dependencies installed"
}

# Function to setup environment file
setup_env() {
    print_status "Setting up environment configuration..."
    
    if [ ! -f ".env" ]; then
        cp .env.example .env
        print_success "Created .env file from template"
        
        # Get user input for configuration
        echo ""
        print_status "Please configure your environment variables:"
        
        get_input "Enter your Google Cloud Project ID" PROJECT_ID
        
        # Update .env file
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/your-project-id/$PROJECT_ID/g" .env
        else
            # Linux
            sed -i "s/your-project-id/$PROJECT_ID/g" .env
        fi
        
        print_success "Environment file configured"
        print_warning "Please ensure you have your GCP credentials file as 'gcp-credentials.json'"
    else
        print_warning ".env file already exists"
    fi
}

# Function to test the setup
test_setup() {
    print_status "Testing the setup..."

    # Check if speech credentials file exists
    if [ ! -f "speech-credentials.json" ]; then
        print_error "speech-credentials.json not found!"
        print_status "Please download your Google Cloud Speech-to-Text credentials and save as 'speech-credentials.json'"
        return 1
    fi

    # Check if gemini credentials file exists
    if [ ! -f "gemini-credentials.json" ]; then
        print_error "gemini-credentials.json not found!"
        print_status "Please download your Gemini AI credentials and save as 'gemini-credentials.json'"
        return 1
    fi
    
    # Test import
    python3 -c "
import sys
sys.path.append('.')
try:
    from web_api import app
    print('✅ Import test passed')
except Exception as e:
    print(f'❌ Import test failed: {e}')
    sys.exit(1)
"
    
    print_success "Setup test passed"
}

# Function to show next steps
show_next_steps() {
    echo ""
    print_success "🎉 Local development setup completed!"
    echo ""
    print_status "Next steps:"
    echo "1. Activate the virtual environment: source venv/bin/activate"
    echo "2. Ensure your credentials are in place:"
    echo "   - speech-credentials.json (Google Cloud Speech-to-Text)"
    echo "   - gemini-credentials.json (Gemini AI)"
    echo "3. Start the development server: python web_api.py"
    echo "4. Open your browser to: http://localhost:8080"
    echo ""
    print_status "For deployment to cloud, run: ./deploy.sh"
    echo ""
}

# Main setup function
main() {
    echo "🛠️  Econome Local Development Setup"
    echo "=================================="
    
    check_prerequisites
    setup_venv
    setup_env
    test_setup
    show_next_steps
}

# Run main function
main "$@"
