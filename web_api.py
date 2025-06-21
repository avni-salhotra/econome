#!/usr/bin/env python3
"""
Econome Web API Entry Point

This is the main entry point for the web API that imports and runs
the FastAPI application from the src package.
"""

import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import the FastAPI app
from src.web_api import app

if __name__ == "__main__":
    import uvicorn
    import os
    
    # Run the server
    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "0.0.0.0")
    environment = os.environ.get("ENVIRONMENT", "production")
    log_level = os.environ.get("LOG_LEVEL", "INFO")

    print("🚀 Starting Econome Web API...")
    print(f"📡 Server will run on {host}:{port}")
    print(f"🌐 API docs available at http://localhost:{port}/docs")
    print(f"🔗 WebSocket endpoint: ws://localhost:{port}/ws/conversation")
    print(f"🔧 Environment: {environment}")

    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=True if environment == "development" else False,
        log_level=log_level.lower()
    )
