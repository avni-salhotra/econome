#!/usr/bin/env python3
"""
FastAPI Web Server for Econome System
GCP-native web interface with real-time WebSocket communication
"""

import os
import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# Import our existing system components
from .meeting_agents import ConversationIntelligenceSystem
from .gcp_session_manager import GCPEphemeralSessionManager
from .websocket_manager import WebSocketManager

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Set up logging
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=getattr(logging, log_level))
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Econome - Privacy-First Conversation Intelligence",
    description="GCP-native conversation intelligence with automatic data deletion",
    version="1.0.0"
)

# CORS middleware for frontend access
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize managers
session_manager = GCPEphemeralSessionManager()
websocket_manager = WebSocketManager()

# Store active conversation systems per connection
active_conversations: Dict[str, ConversationIntelligenceSystem] = {}

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("🚀 Starting Econome Web API...")

    # Test session manager
    stats = await session_manager.get_session_stats()
    logger.info(f"📊 Session manager stats: {stats}")

    logger.info("✅ Econome Web API startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    logger.info("🧹 Shutting down Web API...")
    
    # Stop all active conversations
    for connection_id, system in active_conversations.items():
        try:
            system.stop_system()
            logger.info(f"🛑 Stopped conversation system for {connection_id}")
        except Exception as e:
            logger.error(f"❌ Error stopping system {connection_id}: {e}")
    
    active_conversations.clear()
    logger.info("✅ Web API shutdown complete")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check for Cloud Run"""
    return {
        "status": "healthy",
        "service": "econome",
        "timestamp": datetime.now().isoformat(),
        "active_conversations": len(active_conversations)
    }

@app.get("/debug/audio")
async def debug_audio_status():
    """Debug endpoint to check audio system status"""
    try:
        from src.speech_agent import AUDIO_AVAILABLE, CLOUD_RUN_MODE
        import os

        # Try to import sounddevice and check devices
        audio_info = {
            "audio_available": AUDIO_AVAILABLE,
            "cloud_run_mode": CLOUD_RUN_MODE,
            "environment": {
                "K_SERVICE": os.getenv('K_SERVICE'),
                "K_REVISION": os.getenv('K_REVISION'),
                "K_CONFIGURATION": os.getenv('K_CONFIGURATION'),
                "PORT": os.getenv('PORT'),
                "GOOGLE_CLOUD_PROJECT": os.getenv('GOOGLE_CLOUD_PROJECT')
            }
        }

        # Try to query audio devices if sounddevice is available
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            audio_info["sounddevice_available"] = True
            audio_info["device_count"] = len(devices)
            audio_info["devices"] = [
                {
                    "name": device["name"],
                    "max_input_channels": device["max_input_channels"],
                    "max_output_channels": device["max_output_channels"],
                    "default_samplerate": device["default_samplerate"]
                }
                for device in devices
            ]

            # Try to get default input device
            try:
                default_input = sd.query_devices(kind='input')
                audio_info["default_input_device"] = {
                    "name": default_input["name"],
                    "channels": default_input["max_input_channels"]
                }
            except Exception as e:
                audio_info["default_input_error"] = str(e)

        except Exception as e:
            audio_info["sounddevice_available"] = False
            audio_info["sounddevice_error"] = str(e)

        return audio_info

    except Exception as e:
        return {
            "error": f"Debug check failed: {e}",
            "timestamp": datetime.now().isoformat()
        }

# API endpoints
@app.get("/api/status")
async def get_system_status():
    """Get overall system status"""
    session_stats = await session_manager.get_session_stats()
    websocket_stats = websocket_manager.get_connection_stats()
    
    return {
        "system_status": "operational",
        "active_conversations": len(active_conversations),
        "session_storage": session_stats,
        "websocket_connections": websocket_stats,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/results/{token}")
async def get_ephemeral_results(token: str):
    """Retrieve results from ephemeral storage if still valid"""
    session = await session_manager.get_session(token)
    
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Results not found or expired. Data has been automatically deleted for privacy."
        )
    
    return {
        "summary": session.summary,
        "action_items": session.action_items,
        "created_at": session.created_at.isoformat() if hasattr(session.created_at, 'isoformat') else session.created_at,
        "expires_at": session.expires_at.isoformat() if hasattr(session.expires_at, 'isoformat') else session.expires_at,
        "time_remaining": session.time_remaining,
        "access_count": session.access_count,
        "session_metadata": session.session_metadata,
        "privacy_guarantee": "This data will be automatically deleted by Google Cloud when the timer expires."
    }

@app.get("/api/privacy/verify/{token}")
async def verify_data_deletion(token: str):
    """Allow users to verify their data was deleted"""
    verification = await session_manager.verify_deletion(token)
    return verification

@app.post("/api/demo/simulate")
async def simulate_conversation():
    """Simulate a conversation for demo purposes"""
    # Create a demo session with realistic results
    demo_summary = """
    Today's conversation covered several important topics. We discussed the upcoming project deadline
    and the need to coordinate with the design team. There was mention of a client meeting scheduled
    for Friday where we'll present the quarterly results. The team also talked about improving
    the development workflow and implementing better testing procedures.
    """

    demo_action_items = [
        {"type": "todo", "action": "Prepare quarterly presentation slides", "deadline": "Thursday", "recipient": None},
        {"type": "communicate", "action": "Send meeting agenda to design team", "deadline": "Tomorrow", "recipient": "Design Team"},
        {"type": "todo", "action": "Review and update testing procedures", "deadline": "Next week", "recipient": None},
        {"type": "reminder", "action": "Client meeting presentation", "deadline": "Friday at 2 PM", "recipient": None}
    ]

    # Create ephemeral session
    token = await session_manager.create_session(
        summary=demo_summary.strip(),
        action_items=demo_action_items,
        session_metadata={
            "demo": True,
            "duration": "45 seconds",
            "total_chunks": 8
        }
    )

    base_url = os.getenv("BASE_URL", "http://localhost:8080")
    ephemeral_url = f"{base_url}/api/results/{token}"

    return {
        "results": {
            "summary": demo_summary.strip(),
            "action_items": demo_action_items,
            "total_action_items": len(demo_action_items),
            "session_id": f"demo_{int(time.time())}",
            "duration": "0:00:45",
            "total_transcript_chunks": 8,
            "full_transcript": "This is a demo conversation about project planning and team coordination."
        },
        "ephemeral_url": ephemeral_url,
        "expires_in_hours": 24,
        "privacy_note": "This demo link will automatically expire and delete data in 24 hours."
    }

# WebSocket endpoint for real-time conversation
@app.websocket("/ws/conversation")
async def conversation_websocket(websocket: WebSocket):
    """Real-time conversation processing with WebSocket"""
    connection_id = await websocket_manager.connect(websocket)
    
    try:
        logger.info(f"🔗 New conversation session: {connection_id}")
        
        # Initialize conversation system for this connection
        conversation_system = ConversationIntelligenceSystem(
            mock_mode=False,  # Production mode with GCP
            chunk_duration=2.0,
            project_id=os.getenv("GOOGLE_CLOUD_PROJECT")
        )
        
        # Store active conversation
        active_conversations[connection_id] = conversation_system
        
        # Store the main event loop for thread-safe communication
        main_loop = asyncio.get_running_loop()

        # Start the multi-agent system FIRST
        session_id = await conversation_system.start_system()

        # Get the STT agent and its original callback
        stt_agent = conversation_system.get_agent("stt")
        original_callback = None
        if stt_agent and hasattr(stt_agent, '_on_transcript_segment'):
            original_callback = stt_agent._on_transcript_segment

        # FIXED: Real-time transcript callback that calls BOTH the original STT agent callback AND sends to WebSocket
        def transcript_callback(segment):
            """Callback for live transcription updates - CALLS BOTH STT AGENT AND WEBSOCKET"""
            # FIRST: Call the original STT agent callback to collect transcripts
            if original_callback:
                try:
                    original_callback(segment)
                except Exception as e:
                    print(f"⚠️ Error in original STT callback: {e}")

            # SECOND: Send to frontend via WebSocket (thread-safe)
            try:
                # Schedule the coroutine to run in the main event loop from this thread
                asyncio.run_coroutine_threadsafe(
                    websocket_manager.send_to_connection(connection_id, {
                        "type": "live_transcript",
                        "text": segment.text,
                        "confidence": segment.confidence,
                        "speaker_id": segment.speaker_id,
                        "timestamp": segment.timestamp.isoformat()
                    }),
                    main_loop
                )
            except Exception as e:
                print(f"⚠️ Failed to send live transcript to WebSocket: {e}")
                # Fallback: just log the transcript
                print(f"📝 [FALLBACK] {segment.speaker_id}: {segment.text}")

        # Connect the combined callback to STT service
        if stt_agent and hasattr(stt_agent, 'stt_service'):
            stt_agent.stt_service.set_transcript_callback(transcript_callback)
        
        await websocket_manager.send_to_connection(connection_id, {
            "type": "system_ready",
            "session_id": session_id,
            "connection_id": connection_id,
            "message": "Multi-agent conversation system initialized and ready"
        })
        
        # Message handling loop
        while True:
            # Receive commands from frontend
            data = await websocket.receive_text()
            command = json.loads(data)
            
            await handle_websocket_command(connection_id, command, conversation_system)
            
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"❌ WebSocket error for {connection_id}: {e}")
        await websocket_manager.send_to_connection(connection_id, {
            "type": "error",
            "message": f"System error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })
    finally:
        # Clean up
        if connection_id in active_conversations:
            try:
                active_conversations[connection_id].stop_system()
                del active_conversations[connection_id]
                logger.info(f"🧹 Cleaned up conversation system: {connection_id}")
            except Exception as e:
                logger.error(f"❌ Cleanup error for {connection_id}: {e}")
        
        websocket_manager.disconnect(connection_id)

async def start_frontend_streaming_mode(connection_id: str, conversation_system: ConversationIntelligenceSystem):
    """Initialize conversation system for frontend audio streaming"""
    try:
        # Start the conversation system but skip backend audio recording
        session_id = conversation_system.session_id or f"frontend_session_{int(time.time())}"

        # Initialize STT agent for processing but don't start backend recording
        stt_agent = conversation_system.get_agent("stt")
        if stt_agent:
            # Prepare STT agent for frontend streaming (without starting backend audio)
            stt_agent._is_recording = True
            stt_agent._session_start_time = time.time()
            stt_agent._chunk_counter = 0
            stt_agent._segments.clear()

            # Start the processing thread to handle incoming audio chunks
            if hasattr(stt_agent, '_processing_thread') and stt_agent._processing_thread is None:
                import threading
                stt_agent._processing_thread = threading.Thread(
                    target=stt_agent._process_audio_chunks,
                    daemon=True
                )
                stt_agent._processing_thread.start()
                logger.info("🎵 Started STT processing thread for frontend streaming")

        return {
            "success": True,
            "message": "Frontend streaming mode initialized",
            "session_id": session_id,
            "mode": "frontend_streaming"
        }

    except Exception as e:
        logger.error(f"❌ Error starting frontend streaming mode: {e}")
        return {
            "success": False,
            "message": f"Failed to start frontend streaming: {str(e)}"
        }

async def process_frontend_audio_chunk(connection_id: str, audio_data: str, mime_type: str, conversation_system: ConversationIntelligenceSystem):
    """Process audio chunk received from frontend"""
    try:
        import base64
        import io
        import numpy as np

        # Decode base64 audio data
        audio_bytes = base64.b64decode(audio_data)

        # Try to process audio with pydub (requires ffmpeg)
        try:
            from pydub import AudioSegment

            # Convert audio to the format expected by the speech agent
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes))

            # Convert to mono 16kHz (required for speech recognition)
            audio_segment = audio_segment.set_channels(1).set_frame_rate(16000)

            # Convert to numpy array (float32, normalized to [-1, 1])
            audio_array = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)
            audio_array = audio_array / 32768.0  # Normalize from int16 to float32

            logger.debug(f"📡 Processed audio chunk with pydub: {len(audio_array)} samples")

        except Exception as pydub_error:
            logger.warning(f"⚠️ pydub processing failed (ffmpeg missing?): {pydub_error}")

            # Fallback: Try to process raw audio data directly
            # This is a simplified approach for when ffmpeg is not available
            try:
                # Assume the audio is already in a reasonable format
                # Convert bytes to numpy array (this is a basic fallback)
                audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
                audio_array = audio_array / 32768.0  # Normalize from int16 to float32

                logger.info(f"📡 Processed audio chunk with fallback method: {len(audio_array)} samples")

            except Exception as fallback_error:
                logger.error(f"❌ Both pydub and fallback audio processing failed: {fallback_error}")
                raise Exception(f"Audio processing unavailable - ffmpeg required for pydub. Install ffmpeg in container.")

        # Get the STT agent and process the audio chunk
        stt_agent = conversation_system.get_agent("stt")
        if stt_agent and hasattr(stt_agent, '_audio_queue'):
            # Add the audio chunk to the processing queue
            stt_agent._audio_queue.put(audio_array)
            logger.debug(f"📡 Audio chunk queued for STT processing: {len(audio_array)} samples")
        else:
            logger.warning("⚠️ STT agent not available for frontend audio processing")

    except Exception as e:
        logger.error(f"❌ Error processing frontend audio chunk for {connection_id}: {e}")
        await websocket_manager.send_to_connection(connection_id, {
            "type": "error",
            "message": f"Audio processing error: {str(e)}. Please try Demo Mode or check server configuration.",
            "timestamp": datetime.now().isoformat()
        })

async def handle_websocket_command(connection_id: str, command: Dict[str, Any], conversation_system: ConversationIntelligenceSystem):
    """Handle WebSocket commands from frontend"""
    action = command.get("action")

    try:
        if action == "start_recording":
            # Handle both Safari and standard browsers with frontend or backend mode
            browser = command.get("browser", "unknown")
            mode = command.get("mode", "backend")
            streaming = command.get("streaming", False)

            logger.info(f"🎤 Starting recording for {browser} browser (mode: {mode}, streaming: {streaming})")

            if mode == "frontend_streaming":
                # Frontend streaming mode - initialize STT agent for real-time processing
                result = await start_frontend_streaming_mode(connection_id, conversation_system)
            else:
                # Backend microphone mode (fallback)
                result = conversation_system.start_conversation()

            await websocket_manager.send_to_connection(connection_id, {
                "type": "recording_started",
                "success": result.get("success"),
                "message": result.get("message"),
                "browser": browser,
                "mode": mode,
                "streaming": streaming,
                "timestamp": datetime.now().isoformat()
            })

            if result.get("success"):
                await websocket_manager.broadcast_system_status(
                    "recording",
                    f"Recording started for {browser} session {connection_id[:8]}... (mode: {mode})"
                )
        
        elif action == "audio_chunk":
            # Handle real-time audio chunks from frontend
            audio_data = command.get("audio_data")
            mime_type = command.get("mime_type", "audio/webm")

            if audio_data:
                # Process the audio chunk through the conversation system
                await process_frontend_audio_chunk(connection_id, audio_data, mime_type, conversation_system)

        elif action == "stop_recording":
            await websocket_manager.send_to_connection(connection_id, {
                "type": "processing",
                "message": "Stopping recording and running parallel Gemini analysis...",
                "timestamp": datetime.now().isoformat()
            })

            # Broadcast processing update
            await websocket_manager.broadcast_processing_update(
                "analysis",
                message="Running parallel Gemini processing (Summary + Action Items)..."
            )

            # Use existing stop_conversation method (async)
            results = await conversation_system.stop_conversation()

            # Create ephemeral session for results
            token = await session_manager.create_session(
                summary=results.get("gemini_summary", ""),
                action_items=results.get("action_items", []),
                session_metadata={
                    "connection_id": connection_id,
                    "session_id": results.get("session_id"),
                    "duration": results.get("duration_formatted"),
                    "total_chunks": results.get("total_transcript_chunks", 0)
                }
            )

            # Construct ephemeral URL (update with your actual domain)
            base_url = os.getenv("BASE_URL", "http://localhost:8080")
            ephemeral_url = f"{base_url}/results/{token}"

            # Send complete results to this connection
            await websocket_manager.send_analysis_results(connection_id, {
                "summary": results.get("gemini_summary"),
                "action_items": results.get("action_items", []),
                "total_action_items": results.get("total_action_items", 0),
                "session_id": results.get("session_id"),
                "duration": results.get("duration_formatted"),
                "total_transcript_chunks": results.get("total_transcript_chunks", 0),
                "full_transcript": results.get("full_transcript", "")
            }, ephemeral_url)

            # Broadcast completion
            await websocket_manager.broadcast_system_status(
                "complete",
                f"Analysis complete for session {connection_id[:8]}..."
            )
        
        elif action == "get_status":
            # Get current system status
            status = conversation_system.get_live_status()
            
            await websocket_manager.send_to_connection(connection_id, {
                "type": "status_response",
                "status": status,
                "timestamp": datetime.now().isoformat()
            })
        
        else:
            await websocket_manager.send_to_connection(connection_id, {
                "type": "error",
                "message": f"Unknown action: {action}",
                "timestamp": datetime.now().isoformat()
            })
    
    except Exception as e:
        logger.error(f"❌ Command handling error for {connection_id}: {e}")
        await websocket_manager.send_to_connection(connection_id, {
            "type": "error",
            "message": f"Error executing {action}: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })

# Serve static files (for frontend)
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve frontend HTML"""
    try:
        with open("frontend/index.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="""
        <html>
            <head><title>Econome</title></head>
            <body>
                <h1>🎤 Econome System</h1>
                <p>Frontend not found. API is running at <a href="/docs">/docs</a></p>
            </body>
        </html>
        """)

if __name__ == "__main__":
    # Run the server
    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "0.0.0.0")
    environment = os.environ.get("ENVIRONMENT", "production")

    print("🚀 Starting Econome Web API...")
    print(f"📡 Server will run on {host}:{port}")
    print(f"🌐 API docs available at http://localhost:{port}/docs")
    print(f"🔗 WebSocket endpoint: ws://localhost:{port}/ws/conversation")
    print(f"🔧 Environment: {environment}")

    uvicorn.run(
        "web_api:app",
        host=host,
        port=port,
        reload=True if environment == "development" else False,
        log_level=log_level.lower()
    )
