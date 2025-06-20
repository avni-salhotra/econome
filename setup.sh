#!/bin/bash
# Project Setup Script for Conversation Intelligence System

echo "🚀 Setting up Conversation Intelligence Project..."

# Check if virtual environment exists
if [ ! -d "adk-env" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv adk-env
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source adk-env/bin/activate

# Verify activation
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ Virtual environment activated: $VIRTUAL_ENV"
else
    echo "❌ Failed to activate virtual environment"
    exit 1
fi

# Upgrade pip
echo "📈 Upgrading pip..."
pip install --upgrade pip

# Install requirements
if [ -f "requirements.txt" ]; then
    echo "📋 Installing requirements..."
    pip install -r requirements.txt
else
    echo "⚠️ No requirements.txt found - creating basic one..."
    cat > requirements.txt << EOF
# Google Cloud Speech V2
google-cloud-speech==2.21.0

# Audio processing
sounddevice==0.4.6
scipy==1.11.3
numpy==1.24.3

# Google Cloud services (optional)
google-cloud-aiplatform==1.34.0
google-cloud-bigquery==3.11.4
google-oauth2-tool==0.0.3

# Development
pytest==7.4.2
black==23.7.0
EOF
    pip install -r requirements.txt
fi

# Check for credentials
if [ ! -f "speech-credentials.json" ]; then
    echo "⚠️ speech-credentials.json not found"
    echo "   Place your Google Cloud service account key here for production mode"
    echo "   The system will run in mock mode without it"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "🎯 Next steps:"
echo "   1. Activate environment: source adk-env/bin/activate"
echo "   2. Test STT only: python speech_agent.py"
echo "   3. Test full system: python meeting_agents.py test"
echo "   4. Run demo: python meeting_agents.py"
echo ""
