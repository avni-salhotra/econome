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
    """
    WebSocket endpoint for real-time conversation intelligence
    """
    connection_id = None
    conversation_system = None
    
    try:
        # Accept connection and get ID
        connection_id = await websocket_manager.connect(websocket)
        
        # 🔍 CRITICAL DEBUG: WebSocket connection established
        connection_debug = {
            "timestamp": datetime.now().isoformat(),
            "connection_id": connection_id,
            "websocket_state": "connected",
            "client_host": websocket.client.host if websocket.client else "unknown",
            "client_port": websocket.client.port if websocket.client else "unknown"
        }
        logger.info(f"🔗 DEBUG_WEBSOCKET_CONNECTED: {connection_debug}")
        
        # Initialize conversation system for this connection
        conversation_system = ConversationIntelligenceSystem()
        active_conversations[connection_id] = conversation_system
        
        # Set up transcript callback for real-time updates
        def transcript_callback(segment):
            """Forward transcript segments to WebSocket client"""
            try:
                # 🔍 DEBUG: Transcript callback triggered
                transcript_debug = {
                    "timestamp": datetime.now().isoformat(),
                    "connection_id": connection_id,
                    "segment": {
                        "text": segment.text,
                        "speaker_id": segment.speaker_id,
                        "confidence": segment.confidence,
                        "is_final": segment.is_final,
                        "chunk_id": segment.chunk_id
                    }
                }
                logger.debug(f"📝 DEBUG_TRANSCRIPT_CALLBACK: {transcript_debug}")
                
                asyncio.create_task(websocket_manager.send_to_connection(
                    connection_id,
                    {
                        "type": "live_transcript",
                        "text": segment.text,
                        "speaker_id": segment.speaker_id,
                        "confidence": segment.confidence,
                        "is_final": segment.is_final,
                        "timestamp": segment.timestamp.isoformat(),
                        "chunk_id": segment.chunk_id
                    }
                ))
            except Exception as e:
                logger.error(f"❌ Error in transcript callback: {e}")
        
        # Register callback with STT agent
        stt_agent = conversation_system.get_agent("stt")
        if stt_agent and hasattr(stt_agent, 'stt_service'):
            stt_agent.stt_service.set_transcript_callback(transcript_callback)
            logger.info(f"✅ Transcript callback registered for {connection_id}")
        else:
            logger.warning(f"⚠️ STT agent not available for {connection_id}")
        
        # 🔍 CRITICAL DEBUG: Conversation system initialized
        system_debug = {
            "timestamp": datetime.now().isoformat(),
            "connection_id": connection_id,
            "system_id": conversation_system.session_id,
            "stt_agent_available": stt_agent is not None,
            "stt_service_available": hasattr(stt_agent, 'stt_service') if stt_agent else False
        }
        logger.info(f"🧠 DEBUG_CONVERSATION_SYSTEM_INIT: {system_debug}")
        
        # WebSocket message loop
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                
                # 🔍 DEBUG: Raw message received
                message_debug = {
                    "timestamp": datetime.now().isoformat(),
                    "connection_id": connection_id,
                    "message_length": len(data),
                    "message_preview": data[:200] + "..." if len(data) > 200 else data
                }
                logger.debug(f"📨 DEBUG_WEBSOCKET_MESSAGE_RECEIVED: {message_debug}")
                
                try:
                    message = json.loads(data)
                    
                    # 🔍 CRITICAL DEBUG: Parsed message analysis
                    parsed_debug = {
                        "timestamp": datetime.now().isoformat(),
                        "connection_id": connection_id,
                        "action": message.get("action"),
                        "message_keys": list(message.keys()),
                        "audio_data_length": len(message.get("audio_data", "")) if "audio_data" in message else 0
                    }
                    logger.info(f"🔍 DEBUG_WEBSOCKET_MESSAGE_PARSED: {parsed_debug}")
                    
                    # Handle the message
                    await handle_websocket_command(connection_id, message, conversation_system)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Invalid JSON message from {connection_id}: {e}")
                    await websocket_manager.send_to_connection(connection_id, {
                        "type": "error",
                        "message": "Invalid JSON format"
                    })
                    
            except WebSocketDisconnect:
                logger.info(f"🔌 WebSocket disconnected: {connection_id}")
                break
            except Exception as e:
                logger.error(f"❌ Error in WebSocket loop for {connection_id}: {e}")
                # Send error to client but continue listening
                try:
                    await websocket_manager.send_to_connection(connection_id, {
                        "type": "error",
                        "message": f"Server error: {str(e)}"
                    })
                except:
                    # If we can't send the error, the connection is probably dead
                    break
    
    except Exception as e:
        logger.error(f"❌ WebSocket connection error: {e}")
        # 🔍 DEBUG: Connection error analysis
        error_debug = {
            "timestamp": datetime.now().isoformat(),
            "connection_id": connection_id,
            "error": {
                "type": type(e).__name__,
                "message": str(e)
            }
        }
        logger.error(f"🔍 DEBUG_WEBSOCKET_CONNECTION_ERROR: {error_debug}")
    
    finally:
        # Cleanup on disconnect
        if connection_id:
            # 🔍 CRITICAL DEBUG: Connection cleanup
            cleanup_debug = {
                "timestamp": datetime.now().isoformat(),
                "connection_id": connection_id,
                "had_conversation_system": conversation_system is not None
            }
            logger.info(f"🧹 DEBUG_WEBSOCKET_CLEANUP_START: {cleanup_debug}")
            
            websocket_manager.disconnect(connection_id)
            
            if conversation_system:
                try:
                    conversation_system.stop_system()
                    logger.info(f"🛑 Stopped conversation system for {connection_id}")
                except Exception as e:
                    logger.error(f"❌ Error stopping conversation system for {connection_id}: {e}")
            
            # Remove from active conversations
            if connection_id in active_conversations:
                del active_conversations[connection_id]
                logger.info(f"🧹 Removed {connection_id} from active conversations")
            
            # 🔍 FINAL DEBUG: Cleanup completed
            final_debug = {
                "timestamp": datetime.now().isoformat(),
                "connection_id": connection_id,
                "cleanup_completed": True,
                "active_conversations_remaining": len(active_conversations)
            }
            logger.info(f"✅ DEBUG_WEBSOCKET_CLEANUP_COMPLETED: {cleanup_debug}")

async def start_frontend_streaming_mode(connection_id: str, conversation_system: ConversationIntelligenceSystem):
    """
    Initialize conversation system for frontend audio streaming

    ARCHITECTURE NOTE: Frontend streaming mode allows browser-captured audio to be processed
    by the backend STT service. This is essential for cloud deployments where the server
    cannot access local microphones.

    Key fixes implemented:
    1. Proper STT service state management (not agent wrapper)
    2. Correct audio queue access path
    3. Enhanced error handling and debugging
    """
    try:
        # 🔍 CRITICAL DEBUG: Function entry point
        entry_debug = {
            "timestamp": datetime.now().isoformat(),
            "connection_id": connection_id,
            "conversation_system_id": getattr(conversation_system, 'session_id', None)
        }
        logger.info(f"🚀 DEBUG_START_FRONTEND_STREAMING_ENTRY: {entry_debug}")

        # Start the conversation system but skip backend audio recording
        session_id = conversation_system.session_id or f"frontend_session_{int(time.time())}"

        # 🔍 CRITICAL DEBUG: Pre-initialization state
        pre_init_debug = {
            "timestamp": datetime.now().isoformat(),
            "connection_id": connection_id,
            "session_id": session_id,
            "conversation_system_available": conversation_system is not None
        }
        logger.info(f"🔍 DEBUG_FRONTEND_STREAMING_PRE_INIT: {pre_init_debug}")

        # Initialize STT agent for processing but don't start backend recording
        stt_agent = conversation_system.get_agent("stt")
        
        # 🔍 CRITICAL DEBUG: STT agent availability
        stt_agent_debug = {
            "timestamp": datetime.now().isoformat(),
            "connection_id": connection_id,
            "stt_agent_available": stt_agent is not None,
            "stt_agent_type": type(stt_agent).__name__ if stt_agent else None,
            "has_stt_service": hasattr(stt_agent, 'stt_service') if stt_agent else False
        }
        logger.info(f"🔍 DEBUG_STT_AGENT_AVAILABILITY: {stt_agent_debug}")

        if stt_agent and hasattr(stt_agent, 'stt_service'):
            # Use proper interface for frontend streaming initialization
            stt_service = stt_agent.stt_service
            
            # 🔍 CRITICAL DEBUG: STT service pre-initialization state
            pre_service_debug = {
                "timestamp": datetime.now().isoformat(),
                "connection_id": connection_id,
                "stt_service_type": type(stt_service).__name__,
                "is_recording": getattr(stt_service, '_is_recording', 'unknown'),
                "has_audio_queue": hasattr(stt_service, '_audio_queue'),
                "processing_thread_exists": hasattr(stt_service, '_processing_thread'),
                "processing_thread_alive": (hasattr(stt_service, '_processing_thread') and 
                                          stt_service._processing_thread and 
                                          stt_service._processing_thread.is_alive()) if hasattr(stt_service, '_processing_thread') else False
            }
            logger.info(f"🔍 DEBUG_STT_SERVICE_PRE_INIT: {pre_service_debug}")

            # Initialize frontend streaming
            logger.info(f"🎵 Initializing STT service for frontend streaming (connection: {connection_id})")
            init_result = stt_service.initialize_frontend_streaming()

            # 🔍 CRITICAL DEBUG: STT service initialization result
            init_result_debug = {
                "timestamp": datetime.now().isoformat(),
                "connection_id": connection_id,
                "init_result": init_result,
                "success": init_result.get("success") if init_result else False
            }
            logger.info(f"🔧 DEBUG_STT_SERVICE_INIT_RESULT: {init_result_debug}")

            if init_result.get("success"):
                logger.info("🎵 STT service initialized for frontend streaming")
                logger.debug(f"🔍 Initialization result: {init_result}")
                
                # 🔍 CRITICAL DEBUG: Post-initialization state verification
                post_init_debug = {
                    "timestamp": datetime.now().isoformat(),
                    "connection_id": connection_id,
                    "is_recording": getattr(stt_service, '_is_recording', 'unknown'),
                    "session_start_time": getattr(stt_service, '_session_start_time', None),
                    "processing_thread_alive": (hasattr(stt_service, '_processing_thread') and 
                                              stt_service._processing_thread and 
                                              stt_service._processing_thread.is_alive()) if hasattr(stt_service, '_processing_thread') else False,
                    "audio_queue_size": stt_service._audio_queue.qsize() if hasattr(stt_service, '_audio_queue') else 'N/A',
                    "chunk_counter": getattr(stt_service, '_chunk_counter', 'unknown')
                }
                logger.info(f"✅ DEBUG_STT_SERVICE_POST_INIT_SUCCESS: {post_init_debug}")
                
            else:
                logger.error(f"❌ Failed to initialize STT service for frontend streaming: {init_result.get('message')}")
                
                # 🔍 CRITICAL DEBUG: Initialization failure analysis
                failure_debug = {
                    "timestamp": datetime.now().isoformat(),
                    "connection_id": connection_id,
                    "failure_message": init_result.get('message'),
                    "init_result": init_result,
                    "stt_service_state": {
                        "is_recording": getattr(stt_service, '_is_recording', 'unknown'),
                        "has_processing_thread": hasattr(stt_service, '_processing_thread'),
                        "has_audio_queue": hasattr(stt_service, '_audio_queue')
                    }
                }
                logger.error(f"🔍 DEBUG_STT_INIT_FAILURE: {failure_debug}")
                
                return {
                    "success": False,
                    "message": f"STT initialization failed: {init_result.get('message')}",
                    "mode": "frontend_streaming",
                    "debug_info": failure_debug
                }
        else:
            logger.error("❌ STT agent or STT service not available for frontend streaming initialization")
            
            # 🔍 CRITICAL DEBUG: STT agent/service not available
            unavailable_debug = {
                "timestamp": datetime.now().isoformat(),
                "connection_id": connection_id,
                "stt_agent_is_none": stt_agent is None,
                "stt_agent_has_service": hasattr(stt_agent, 'stt_service') if stt_agent else False,
                "stt_agent_type": type(stt_agent).__name__ if stt_agent else None,
                "conversation_system_agents": [agent_name for agent_name in conversation_system._agents.keys()] if hasattr(conversation_system, '_agents') else []
            }
            logger.error(f"🔍 DEBUG_STT_UNAVAILABLE: {unavailable_debug}")
            
            return {
                "success": False,
                "message": "STT agent or service not available",
                "mode": "frontend_streaming",
                "debug_info": unavailable_debug
            }

        # 🔍 SUCCESS: Frontend streaming mode initialized
        success_debug = {
            "timestamp": datetime.now().isoformat(),
            "connection_id": connection_id,
            "session_id": session_id,
            "mode": "frontend_streaming",
            "stt_initialized": True
        }
        logger.info(f"✅ DEBUG_FRONTEND_STREAMING_SUCCESS: {success_debug}")

        return {
            "success": True,
            "message": "Frontend streaming mode initialized",
            "session_id": session_id,
            "mode": "frontend_streaming",
            "debug_info": success_debug
        }

    except Exception as e:
        logger.error(f"❌ Error starting frontend streaming mode: {e}")
        
        # 🔍 CRITICAL DEBUG: Exception analysis
        exception_debug = {
            "timestamp": datetime.now().isoformat(),
            "connection_id": connection_id,
            "error": {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": str(e.__traceback__) if hasattr(e, '__traceback__') else None
            },
            "conversation_system_available": conversation_system is not None
        }
        logger.error(f"🔍 DEBUG_FRONTEND_STREAMING_EXCEPTION: {exception_debug}")
        
        return {
            "success": False,
            "message": f"Failed to start frontend streaming: {str(e)}",
            "debug_info": exception_debug
        }

async def process_frontend_audio_chunk(connection_id: str, audio_data: str, mime_type: str, conversation_system: ConversationIntelligenceSystem):
    """
    Process audio chunk received from frontend

    CRITICAL FIXES:
    1. Enhanced audio format handling for WebM/MP4/WAV
    2. Proper fallback logic that doesn't attempt raw processing on encoded formats
    3. Correct STT service audio queue access (stt_agent.stt_service._audio_queue)
    4. Comprehensive error handling with debugging information
    """
    try:
        import base64
        import io
        import numpy as np

        # Decode base64 audio data
        audio_bytes = base64.b64decode(audio_data)

        # OBSERVABILITY: Get connection stream tracking info
        connection = websocket_manager.connections.get(connection_id)
        if connection:
            connection_stream_id = connection.connection_stream_id
            chunk_seq_number = connection.get_next_chunk_sequence()
        else:
            connection_stream_id = "unknown"
            chunk_seq_number = 0
            logger.warning(f"⚠️ Connection {connection_id} not found in websocket_manager")

        # STRUCTURED LOGGING: Audio pipeline entry point with observability
        pipeline_context = {
            "connection_id": connection_id,
            "connection_stream_id": connection_stream_id,
            "chunk_seq_number": chunk_seq_number,
            "mime_type": mime_type,
            "audio_bytes_length": len(audio_bytes),
            "base64_length": len(audio_data),
            "pipeline_stage": "decode",
            "timestamp": datetime.now().isoformat()
        }
        logger.info(f"🎵 AUDIO_PIPELINE_START: {pipeline_context}")

        # STRATEGY A: WebM Chunk Buffering & Muxing for headerless chunks
        if 'webm' in mime_type.lower() and 'opus' in mime_type.lower():
            try:
                # Import the WebM muxing module
                from .webm_muxer import get_or_create_buffer
                
                # Get or create buffer for this connection
                webm_buffer = get_or_create_buffer(connection_id)
                
                # Add chunk to buffer and check if ready for processing
                should_process, muxed_bytes = webm_buffer.add_chunk(audio_bytes, mime_type)
                
                if not should_process:
                    # Chunk is buffered, waiting for more chunks
                    buffer_stats = webm_buffer.get_buffer_stats()
                    logger.info(f"📦 WEBM_CHUNK_BUFFERED: {buffer_stats}")
                    return  # Exit early, chunk is buffered
                
                # Determine which bytes to process
                if muxed_bytes is not None:
                    # Use muxed bytes from buffer
                    processing_bytes = muxed_bytes
                    processing_strategy = "muxed_buffer"
                    logger.info(f"🔧 Processing muxed buffer ({len(muxed_bytes)} bytes)")
                else:
                    # Use original bytes (first chunk with header)
                    processing_bytes = audio_bytes
                    processing_strategy = "first_chunk_header"
                    logger.info(f"🔧 Processing first chunk with header ({len(audio_bytes)} bytes)")
                
                # Process with FFmpeg using headerless matroska strategy
                import subprocess

                # OBSERVABILITY: FFmpeg timing start
                ffmpeg_start_time = datetime.now()
                ffmpeg_start_timestamp = ffmpeg_start_time.timestamp() * 1000  # milliseconds

                # STRUCTURED LOGGING: FFmpeg processing stage
                ffmpeg_context = {
                    **pipeline_context,
                    "pipeline_stage": "ffmpeg_webm_opus_strategy_a",
                    "input_bytes": len(processing_bytes),
                    "processing_strategy": processing_strategy,
                    "ffmpeg_start_timestamp": ffmpeg_start_timestamp
                }
                logger.info(f"🔧 AUDIO_PIPELINE_FFMPEG_STRATEGY_A: {ffmpeg_context}")

                # Use headerless WebM parsing (Strategy A optimized)
                ffmpeg_cmd_headerless = [
                    'ffmpeg',
                    '-f', 'matroska',       # More lenient than 'webm' for headerless chunks
                    '-fflags', '+ignidx',   # Ignore index corruption
                    '-analyzeduration', '0', # Don't wait for complete headers
                    '-probesize', '32',     # Minimal probing for faster processing
                    '-i', 'pipe:0',         # Input from stdin
                    '-f', 's16le',          # Output format (PCM 16-bit little endian)
                    '-acodec', 'pcm_s16le', # PCM codec
                    '-ar', '16000',         # 16kHz sample rate
                    '-ac', '1',             # Mono channel
                    '-loglevel', 'error',   # Suppress FFmpeg logs
                    'pipe:1'                # Output to stdout
                ]

                # Process with FFmpeg
                process = subprocess.run(
                    ffmpeg_cmd_headerless,
                    input=processing_bytes,
                    capture_output=True,
                    timeout=10
                )

                # OBSERVABILITY: FFmpeg timing end
                ffmpeg_end_time = datetime.now()
                ffmpeg_end_timestamp = ffmpeg_end_time.timestamp() * 1000  # milliseconds
                ffmpeg_latency_ms = ffmpeg_end_timestamp - ffmpeg_start_timestamp

                if process.returncode == 0 and process.stdout:
                    # Strategy A succeeded
                    audio_array = np.frombuffer(process.stdout, dtype=np.int16).astype(np.float32)
                    audio_array = audio_array / 32768.0  # Normalize from int16 to float32
                    
                    # STRUCTURED LOGGING: FFmpeg success with Strategy A
                    success_context = {
                        **ffmpeg_context,
                        "pipeline_stage": "ffmpeg_success_strategy_a",
                        "strategy_used": "chunk_buffering_muxing",
                        "output_samples": len(audio_array),
                        "pcm_bytes": len(process.stdout),
                        "sample_rate": 16000,
                        "channels": 1,
                        "ffmpeg_end_timestamp": ffmpeg_end_timestamp,
                        "ffmpeg_latency_ms": round(ffmpeg_latency_ms, 2)
                    }
                    logger.info(f"✅ AUDIO_PIPELINE_FFMPEG_SUCCESS_STRATEGY_A: {success_context}")
                else:
                    # Strategy A failed - log detailed error
                    ffmpeg_error = process.stderr.decode('utf-8') if process.stderr else "Unknown FFmpeg error"
                    
                    # STRUCTURED LOGGING: FFmpeg failure
                    error_context = {
                        **ffmpeg_context,
                        "pipeline_stage": "ffmpeg_error_strategy_a",
                        "strategy_attempted": "chunk_buffering_muxing",
                        "return_code": process.returncode,
                        "stderr": ffmpeg_error,
                        "stdout_length": len(process.stdout) if process.stdout else 0,
                        "ffmpeg_end_timestamp": ffmpeg_end_timestamp,
                        "ffmpeg_latency_ms": round(ffmpeg_latency_ms, 2)
                    }
                    logger.error(f"❌ AUDIO_PIPELINE_FFMPEG_ERROR_STRATEGY_A: {error_context}")
                    raise Exception(f"FFmpeg WebM Strategy A processing failed: {ffmpeg_error}")

            except subprocess.TimeoutExpired:
                logger.error("❌ FFmpeg process timed out (Strategy A)")
                raise Exception("FFmpeg process timed out during WebM Strategy A processing")
            except Exception as ffmpeg_error:
                logger.error(f"❌ FFmpeg WebM Strategy A processing error: {ffmpeg_error}")
                raise Exception(f"FFmpeg WebM Strategy A processing failed: {str(ffmpeg_error)}")

        else:
            # Use pydub for other formats (MP4, WAV, etc.)
            try:
                from pydub import AudioSegment

                # Create a temporary file-like object
                audio_io = io.BytesIO(audio_bytes)

                # Process based on mime type
                if 'mp4' in mime_type.lower():
                    audio_segment = AudioSegment.from_file(audio_io, format="mp4")
                elif 'wav' in mime_type.lower():
                    audio_segment = AudioSegment.from_file(audio_io, format="wav")
                else:
                    # Try auto-detection for other formats
                    audio_segment = AudioSegment.from_file(audio_io)

                # Convert to mono 16kHz (required for speech recognition)
                audio_segment = audio_segment.set_channels(1).set_frame_rate(16000)

                # Convert to numpy array (float32, normalized to [-1, 1])
                audio_array = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)
                audio_array = audio_array / 32768.0  # Normalize from int16 to float32

                logger.debug(f"✅ pydub processing successful ({mime_type}): {len(audio_array)} samples")

            except Exception as pydub_error:
                logger.error(f"❌ pydub processing failed for {mime_type}: {pydub_error}")

                # FIXED: No unsafe raw fallback for encoded formats
                # Raw fallback is only safe for truly uncompressed PCM data
                if any(fmt in mime_type.lower() for fmt in ['webm', 'mp4', 'ogg', 'aac', 'm4a']):
                    logger.error(f"❌ Encoded format {mime_type} requires proper codec support - no raw fallback")
                    raise Exception(f"Audio format {mime_type} requires FFmpeg/pydub codec support. Raw processing would corrupt data.")

                # SAFE: Only attempt raw processing for explicitly uncompressed formats
                if mime_type.lower() in ['audio/pcm', 'audio/raw', 'audio/l16']:
                    try:
                        logger.info(f"🔄 Attempting raw PCM processing for {mime_type}")

                        # Only try int16 PCM (most common uncompressed format)
                        if len(audio_bytes) % 2 == 0:
                            audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
                            audio_array = audio_array / 32768.0  # Normalize from int16 to float32
                            logger.debug(f"✅ Raw PCM processing successful ({mime_type}): {len(audio_array)} samples")
                        else:
                            raise ValueError(f"PCM data length {len(audio_bytes)} not compatible with int16 format")

                    except Exception as raw_error:
                        logger.error(f"❌ Raw PCM processing failed: {raw_error}")
                        raise Exception(f"Raw PCM processing failed for {mime_type}: {str(raw_error)}")
                else:
                    # Unknown format - fail safely
                    logger.error(f"❌ Unknown audio format {mime_type} - cannot process safely")
                    raise Exception(f"Unsupported audio format {mime_type}. Supported: WebM/Opus (via FFmpeg), MP4, WAV, PCM.")

        # FIXED: Enhanced STT queue processing with lifecycle checks
        stt_agent = conversation_system.get_agent("stt")
        if stt_agent and hasattr(stt_agent, 'stt_service'):
            stt_service = stt_agent.stt_service

            # LIFECYCLE CHECK 1: Verify STT service is recording
            if hasattr(stt_service, '_is_recording') and not stt_service._is_recording:
                logger.warning("⚠️ STT service is not recording - chunk will be ignored")
                return

            # LIFECYCLE CHECK 2: Verify processing thread is active
            processing_thread_active = (
                hasattr(stt_service, '_processing_thread') and
                stt_service._processing_thread is not None and
                stt_service._processing_thread.is_alive()
            )

            if not processing_thread_active:
                logger.error("❌ STT processing thread is not active - chunks will not be processed")
                # FIXED: Enhanced thread restart logic with proper synchronization
                logger.info("🔄 Attempting to reinitialize STT frontend streaming...")
                try:
                    reinit_result = stt_service.initialize_frontend_streaming()
                    if reinit_result.get("success"):
                        logger.info("✅ STT frontend streaming reinitialized successfully")
                        # Verify thread is now active
                        processing_thread_active = (
                            hasattr(stt_service, '_processing_thread') and
                            stt_service._processing_thread is not None and
                            stt_service._processing_thread.is_alive()
                        )
                        if not processing_thread_active:
                            logger.error("❌ Thread still not active after reinitialization")
                            return
                    else:
                        logger.error(f"❌ Failed to reinitialize STT: {reinit_result.get('message')}")
                        return
                except Exception as restart_error:
                    logger.error(f"❌ Failed to restart processing thread: {restart_error}")
                    return

            # LIFECYCLE CHECK 3: Verify queue is not full
            if hasattr(stt_service, '_audio_queue'):
                queue_size = stt_service._audio_queue.qsize()
                max_size = getattr(stt_service, 'max_queue_size', 100)
                if queue_size >= max_size * 0.9:  # 90% full threshold
                    logger.warning(f"⚠️ STT queue nearly full: {queue_size}/{max_size}")

            # OBSERVABILITY: Queue timing start
            queue_enqueue_time = datetime.now()
            queue_enqueue_timestamp = queue_enqueue_time.timestamp() * 1000  # milliseconds

            # DEEP DEBUG: Log audio_array details before queuing for STT
            audio_array_debug = {
                **pipeline_context,
                "pipeline_stage": "stt_audio_array_debug",
                "audio_array_shape": audio_array.shape,
                "audio_array_dtype": str(audio_array.dtype),
                "audio_array_min": float(audio_array.min()),
                "audio_array_max": float(audio_array.max()),
                "audio_array_mean": float(audio_array.mean()),
                "audio_array_std": float(audio_array.std()),
                "has_non_zero_samples": bool(np.any(audio_array != 0)),
                "non_zero_sample_count": int(np.count_nonzero(audio_array)),
                "sample_rate_expected": 16000,  # What STT expects
                "timestamp": datetime.now().isoformat()
            }
            logger.info(f"🔍 DEBUG_STT_AUDIO_ARRAY: {audio_array_debug}")

            # STRUCTURED LOGGING: STT queue stage with timing
            queue_context = {
                **pipeline_context,
                "pipeline_stage": "stt_queue",
                "audio_samples": len(audio_array),
                "queue_size": stt_service._audio_queue.qsize() if hasattr(stt_service, '_audio_queue') else "unknown",
                "is_recording": getattr(stt_service, '_is_recording', False),
                "processing_thread_alive": processing_thread_active,
                "queue_enqueue_timestamp": queue_enqueue_timestamp
            }
            logger.info(f"📡 AUDIO_PIPELINE_STT_QUEUE: {queue_context}")

            # Use proper interface for queuing audio chunks
            if hasattr(stt_service, 'queue_audio_chunk'):
                success = stt_service.queue_audio_chunk(audio_array)
                if success:
                    # STRUCTURED LOGGING: Queue success
                    success_context = {
                        **queue_context,
                        "pipeline_stage": "stt_queue_success",
                        "queue_method": "interface"
                    }
                    logger.info(f"✅ AUDIO_PIPELINE_STT_QUEUE_SUCCESS: {success_context}")

                    # OBSERVABILITY: Record successful chunk processing
                    if connection:
                        connection.record_chunk_processed(success=True)
                else:
                    # STRUCTURED LOGGING: Queue failure
                    failure_context = {
                        **queue_context,
                        "pipeline_stage": "stt_queue_failure",
                        "queue_method": "interface",
                        "reason": "service_not_recording"
                    }
                    logger.warning(f"⚠️ AUDIO_PIPELINE_STT_QUEUE_FAILURE: {failure_context}")

                    # OBSERVABILITY: Record failed chunk processing
                    if connection:
                        connection.record_chunk_processed(success=False)
            else:
                # Fallback to direct access if interface not available
                if hasattr(stt_service, '_audio_queue'):
                    try:
                        stt_service._audio_queue.put(audio_array, block=False)
                        # STRUCTURED LOGGING: Fallback queue success
                        fallback_context = {
                            **queue_context,
                            "pipeline_stage": "stt_queue_success",
                            "queue_method": "fallback_direct"
                        }
                        logger.info(f"✅ AUDIO_PIPELINE_STT_QUEUE_SUCCESS: {fallback_context}")
                    except Exception as queue_error:
                        # STRUCTURED LOGGING: Fallback queue failure
                        fallback_error_context = {
                            **queue_context,
                            "pipeline_stage": "stt_queue_failure",
                            "queue_method": "fallback_direct",
                            "error": str(queue_error)
                        }
                        logger.error(f"❌ AUDIO_PIPELINE_STT_QUEUE_FAILURE: {fallback_error_context}")
                else:
                    # STRUCTURED LOGGING: No queue interface
                    no_interface_context = {
                        **queue_context,
                        "pipeline_stage": "stt_queue_failure",
                        "reason": "no_queue_interface"
                    }
                    logger.error(f"❌ AUDIO_PIPELINE_STT_QUEUE_FAILURE: {no_interface_context}")
        else:
            logger.error("❌ STT agent or service not available")
            if stt_agent:
                logger.debug(f"🔍 STT agent available: {stt_agent is not None}")
                logger.debug(f"🔍 STT service available: {hasattr(stt_agent, 'stt_service')}")
                if hasattr(stt_agent, 'stt_service'):
                    logger.debug(f"🔍 Queue interface available: {hasattr(stt_agent.stt_service, 'queue_audio_chunk')}")

            # OBSERVABILITY: Record failed chunk processing
            if connection:
                connection.record_chunk_processed(success=False)

        # OBSERVABILITY: Check for unprocessed chunk alerts
        if connection:
            unprocessed_count = connection.get_unprocessed_chunk_count(60)  # 60 second window
            if unprocessed_count >= 5:  # Alert threshold
                alert_context = {
                    **pipeline_context,
                    "pipeline_stage": "unprocessed_chunk_alert",
                    "unprocessed_chunks_60s": unprocessed_count,
                    "total_chunks_processed": connection.total_chunks_processed,
                    "total_chunks_dropped": connection.total_chunks_dropped,
                    "alert_threshold": 5,
                    "window_seconds": 60
                }
                logger.error(f"🚨 UNPROCESSED_CHUNK_ALERT: {alert_context}")

    except Exception as e:
        logger.error(f"❌ Error processing frontend audio chunk for {connection_id}: {e}")

        # Enhanced error response with debugging information
        error_response = {
            "type": "error",
            "message": f"Audio processing error: {str(e)}",
            "timestamp": datetime.now().isoformat(),
            "debug_info": {
                "connection_id": connection_id,
                "mime_type": mime_type,
                "audio_data_length": len(audio_data) if audio_data else 0,
                "error_type": type(e).__name__,
                "suggestions": []
            }
        }

        # Add specific suggestions based on error type
        if "ffmpeg" in str(e).lower():
            error_response["debug_info"]["suggestions"].append("Try Demo Mode - it works without microphone access")
            error_response["debug_info"]["suggestions"].append("Audio processing requires ffmpeg for WebM format")
        elif "audio_queue" in str(e).lower():
            error_response["debug_info"]["suggestions"].append("STT service may not be properly initialized")
            error_response["debug_info"]["suggestions"].append("Try refreshing the page and starting recording again")
        elif "buffer size" in str(e).lower():
            error_response["debug_info"]["suggestions"].append("Audio format incompatibility detected")
            error_response["debug_info"]["suggestions"].append("Try using a different browser or Demo Mode")

        await websocket_manager.send_to_connection(connection_id, error_response)

async def handle_websocket_command(connection_id: str, command: Dict[str, Any], conversation_system: ConversationIntelligenceSystem):
    """Handle WebSocket commands from frontend"""
    action = command.get("action")

    # 🔍 CRITICAL DEBUG: Command handling entry point
    command_debug = {
        "timestamp": datetime.now().isoformat(),
        "connection_id": connection_id,
        "action": action,
        "command_keys": list(command.keys()),
        "has_audio_data": "audio_data" in command,
        "audio_data_length": len(command.get("audio_data", "")) if "audio_data" in command else 0
    }
    logger.info(f"🔧 DEBUG_WEBSOCKET_COMMAND: {command_debug}")

    try:
        if action == "start_recording":
            # Handle both Safari and standard browsers with frontend or backend mode
            browser = command.get("browser", "unknown")
            mode = command.get("mode", "backend")
            streaming = command.get("streaming", False)

            # 🔍 CRITICAL DEBUG: Start recording request analysis
            start_debug = {
                "timestamp": datetime.now().isoformat(),
                "connection_id": connection_id,
                "browser": browser,
                "mode": mode,
                "streaming": streaming,
                "sample_rate": command.get("sample_rate"),
                "channels": command.get("channels"),
                "environment": command.get("environment")
            }
            logger.info(f"🎤 DEBUG_START_RECORDING_REQUEST: {start_debug}")

            logger.info(f"🎤 Starting recording for {browser} browser (mode: {mode}, streaming: {streaming})")

            if mode == "frontend_streaming":
                # Frontend streaming mode - initialize STT agent for real-time processing
                result = await start_frontend_streaming_mode(connection_id, conversation_system)
                
                # 🔍 DEBUG: Frontend streaming initialization result
                streaming_result_debug = {
                    "timestamp": datetime.now().isoformat(),
                    "connection_id": connection_id,
                    "result": result
                }
                logger.info(f"🔧 DEBUG_FRONTEND_STREAMING_RESULT: {streaming_result_debug}")
            else:
                # Backend microphone mode (fallback)
                result = conversation_system.start_conversation()
                
                # 🔍 DEBUG: Backend recording result
                backend_result_debug = {
                    "timestamp": datetime.now().isoformat(),
                    "connection_id": connection_id,
                    "result": result
                }
                logger.info(f"🖥️ DEBUG_BACKEND_RECORDING_RESULT: {backend_result_debug}")

            # Enhanced response with debugging information and cloud mode detection
            from src.speech_agent import AUDIO_AVAILABLE, CLOUD_RUN_MODE

            response_data = {
                "type": "recording_started",
                "success": result.get("success"),
                "message": result.get("message"),
                "browser": browser,
                "mode": mode,
                "streaming": streaming,
                "timestamp": datetime.now().isoformat(),
                # CRITICAL: Add cloud mode flags for frontend environment detection
                "environment": {
                    "cloud_run_mode": CLOUD_RUN_MODE,
                    "audio_available": AUDIO_AVAILABLE,
                    "mock_mode": result.get("mock_mode", False),
                    "recommended_mode": "frontend_streaming" if CLOUD_RUN_MODE else "backend"
                }
            }

            # Add debugging information for frontend streaming mode
            if mode == "frontend_streaming":
                stt_agent = conversation_system.get_agent("stt")
                if stt_agent and hasattr(stt_agent, 'stt_service'):
                    stt_service = stt_agent.stt_service
                    response_data.update({
                        "debug_info": {
                            "stt_service_available": True,
                            "audio_queue_available": hasattr(stt_service, '_audio_queue'),
                            "processing_thread_active": hasattr(stt_service, '_processing_thread') and
                                                      stt_service._processing_thread is not None,
                            "is_recording": getattr(stt_service, '_is_recording', False)
                        }
                    })
                else:
                    response_data.update({
                        "debug_info": {
                            "stt_service_available": False,
                            "error": "STT agent or service not properly initialized"
                        }
                    })

            # 🔍 CRITICAL DEBUG: Response data analysis
            response_debug = {
                "timestamp": datetime.now().isoformat(),
                "connection_id": connection_id,
                "response_type": response_data["type"],
                "success": response_data["success"],
                "environment": response_data["environment"],
                "debug_info": response_data.get("debug_info")
            }
            logger.info(f"📤 DEBUG_START_RECORDING_RESPONSE: {response_debug}")

            await websocket_manager.send_to_connection(connection_id, response_data)

            if result.get("success"):
                await websocket_manager.broadcast_system_status(
                    "recording",
                    f"Recording started for {browser} session {connection_id[:8]}... (mode: {mode})"
                )
        
        elif action == "audio_chunk":
            # Handle real-time audio chunks from frontend
            audio_data = command.get("audio_data")
            mime_type = command.get("mime_type", "audio/webm")
            timestamp = command.get("timestamp", datetime.now().timestamp() * 1000)

            # 🔍 CRITICAL DEBUG: Audio chunk received analysis
            chunk_debug = {
                "timestamp": datetime.now().isoformat(),
                "connection_id": connection_id,
                "audio_data_length": len(audio_data) if audio_data else 0,
                "mime_type": mime_type,
                "chunk_timestamp": timestamp,
                "time_since_chunk": datetime.now().timestamp() * 1000 - timestamp if timestamp else 0
            }
            logger.debug(f"🎵 DEBUG_AUDIO_CHUNK_RECEIVED: {chunk_debug}")

            if audio_data:
                # 🔍 VALIDATION: Check STT service state before processing
                stt_agent = conversation_system.get_agent("stt")
                if stt_agent and hasattr(stt_agent, 'stt_service'):
                    stt_service = stt_agent.stt_service
                    stt_state_debug = {
                        "timestamp": datetime.now().isoformat(),
                        "connection_id": connection_id,
                        "stt_is_recording": getattr(stt_service, '_is_recording', False),
                        "stt_session_start": getattr(stt_service, '_session_start_time', None),
                        "processing_thread_alive": hasattr(stt_service, '_processing_thread') and 
                                                  stt_service._processing_thread and 
                                                  stt_service._processing_thread.is_alive(),
                        "audio_queue_size": stt_service._audio_queue.qsize() if hasattr(stt_service, '_audio_queue') else "N/A"
                    }
                    logger.debug(f"🔍 DEBUG_STT_STATE_BEFORE_CHUNK: {stt_state_debug}")
                else:
                    logger.error(f"❌ CRITICAL: STT service not available for audio chunk processing (connection: {connection_id})")

                # Process the audio chunk through the conversation system
                try:
                    await process_frontend_audio_chunk(connection_id, audio_data, mime_type, conversation_system)
                    
                    # 🔍 SUCCESS: Audio chunk processed
                    process_success_debug = {
                        "timestamp": datetime.now().isoformat(),
                        "connection_id": connection_id,
                        "chunk_processed": True,
                        "audio_data_length": len(audio_data)
                    }
                    logger.debug(f"✅ DEBUG_AUDIO_CHUNK_PROCESSED: {process_success_debug}")
                    
                except Exception as chunk_error:
                    # 🔍 ERROR: Audio chunk processing failed
                    process_error_debug = {
                        "timestamp": datetime.now().isoformat(),
                        "connection_id": connection_id,
                        "chunk_processed": False,
                        "error": {
                            "type": type(chunk_error).__name__,
                            "message": str(chunk_error)
                        },
                        "audio_data_length": len(audio_data)
                    }
                    logger.error(f"❌ DEBUG_AUDIO_CHUNK_ERROR: {process_error_debug}")
                    raise chunk_error
            else:
                logger.warning(f"⚠️ Empty audio data received from {connection_id}")

        elif action == "stop_recording":
            # 🔍 DEBUG: Stop recording request
            stop_debug = {
                "timestamp": datetime.now().isoformat(),
                "connection_id": connection_id
            }
            logger.info(f"🛑 DEBUG_STOP_RECORDING_REQUEST: {stop_debug}")

            # Stop the conversation recording
            logger.info(f"🛑 Stopping recording for {connection_id}")
            result = await conversation_system.stop_conversation()

            # Send response
            await websocket_manager.send_to_connection(connection_id, {
                "type": "recording_stopped",
                "success": result.get("success", True),
                "message": result.get("message", "Recording stopped"),
                "session_duration": result.get("session_duration", 0),
                "chunks_processed": result.get("chunks_processed", 0),
                "timestamp": datetime.now().isoformat()
            })

            if result.get("success", True):
                await websocket_manager.broadcast_system_status(
                    "processing",
                    f"Processing conversation for session {connection_id[:8]}..."
                )

        elif action == "get_status":
            # Get system status
            status = conversation_system.get_conversation_status()
            await websocket_manager.send_to_connection(connection_id, {
                "type": "status_update",
                "status": status,
                "timestamp": datetime.now().isoformat()
            })

        else:
            # 🔍 DEBUG: Unknown action
            unknown_debug = {
                "timestamp": datetime.now().isoformat(),
                "connection_id": connection_id,
                "unknown_action": action,
                "all_keys": list(command.keys())
            }
            logger.warning(f"⚠️ DEBUG_UNKNOWN_ACTION: {unknown_debug}")

            await websocket_manager.send_to_connection(connection_id, {
                "type": "error",
                "message": f"Unknown action: {action}",
                "timestamp": datetime.now().isoformat()
            })

    except Exception as e:
        logger.error(f"❌ Error handling command {action} for {connection_id}: {e}")
        
        # 🔍 CRITICAL DEBUG: Command handling error analysis
        error_debug = {
            "timestamp": datetime.now().isoformat(),
            "connection_id": connection_id,
            "action": action,
            "error": {
                "type": type(e).__name__,
                "message": str(e)
            },
            "command_keys": list(command.keys())
        }
        logger.error(f"🔍 DEBUG_COMMAND_ERROR: {error_debug}")
        
        await websocket_manager.send_to_connection(connection_id, {
            "type": "error",
            "message": f"Command error: {str(e)}",
            "action": action,
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

async def periodic_state_dump():
    """
    OBSERVABILITY: Periodic internal state dump for system health monitoring
    Logs comprehensive system state every 60 seconds at DEBUG level
    """
    while True:
        try:
            await asyncio.sleep(60)  # 60 second interval

            # Get all active conversation systems
            active_systems = []
            for connection_id, connection in websocket_manager.connections.items():
                if hasattr(connection, 'conversation_session_id') and connection.conversation_session_id:
                    system_state = {
                        "connection_id": connection_id,
                        "connection_stream_id": connection.connection_stream_id,
                        "session_id": connection.conversation_session_id,
                        "connection_info": connection.get_connection_info()
                    }
                    active_systems.append(system_state)

            # STRUCTURED LOGGING: Periodic state dump
            state_dump_context = {
                "pipeline_stage": "periodic_state_dump",
                "dump_timestamp": datetime.now().timestamp() * 1000,
                "active_connections": len(websocket_manager.connections),
                "active_systems": len(active_systems),
                "websocket_manager_state": {
                    "total_connections": len(websocket_manager.connections),
                    "connection_details": active_systems
                }
            }

            # Log at DEBUG level for passive monitoring
            logger.debug(f"🔍 PERIODIC_STATE_DUMP: {state_dump_context}")

        except Exception as e:
            logger.error(f"❌ Error in periodic state dump: {e}")

# Start periodic state dump task
@app.on_event("startup")
async def startup_event():
    """Start background tasks on application startup"""
    asyncio.create_task(periodic_state_dump())
    logger.info("🚀 Periodic state dump task started (60s interval)")

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
