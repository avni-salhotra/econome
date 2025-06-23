#!/usr/bin/env python3
"""
Multi-Agent Conversation Intelligence System
Built for Google Cloud ADK Hackathon - Production Architecture

Clean separation between STT service and agent orchestration
Uses composition pattern for maintainable, testable code

SIMPLIFIED VERSION: No real-time analysis, only final summary
"""

import asyncio
import json
import time
import threading
import queue
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
import os

# Gemini analysis functions
from .gemini_agent import summarize_conversation, extract_action_items

# Import our STT service
from .speech_agent import ProductionSTTServiceV2, TranscriptSegment, STTStatus, create_stt_service

# Google Cloud imports for other services
from google.cloud import aiplatform
from google.cloud import bigquery
from google.oauth2 import service_account

# Agent Framework Base Classes
@dataclass
class Message:
    """Inter-agent message structure"""
    type: str
    data: Any
    timestamp: datetime = None
    source_agent: str = ""
    target_agent: str = ""
    correlation_id: str = ""
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.correlation_id == "":
            self.correlation_id = f"{self.source_agent}_{int(time.time())}"


# --- Fixed Agent base class with proper async handling and inter-agent messaging ---
class Agent:
    """Base agent class with message passing capabilities (asyncio compatible)"""
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.is_running = False
        self.other_agents = {}
        self.message_handlers = {}
        self._message_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._setup_message_handlers()

    def _setup_message_handlers(self):
        """Override in subclasses to set up message handlers"""
        pass

    async def send_message(self, target_agent: str, message: Message):
        """Send message to another agent asynchronously"""
        if target_agent in self.other_agents:
            message.source_agent = self.name
            message.target_agent = target_agent
            await self.other_agents[target_agent].receive_message(message)
        else:
            print(f"⚠️ Agent {target_agent} not found from {self.name}")

    async def receive_message(self, message: Message):
        """Receive message from another agent asynchronously"""
        await self.message_queue.put(message)

    def connect_agent(self, agent_name: str, agent_instance):
        """Connect to another agent"""
        self.other_agents[agent_name] = agent_instance

    def start(self):
        """Start the agent's async message processing loop"""
        self.is_running = True
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.get_event_loop()
        self._message_task = self._loop.create_task(self._process_messages())
        print(f"✅ {self.name} started")

    def stop(self):
        """Stop the agent's message processing loop"""
        self.is_running = False
        if self._message_task:
            self._message_task.cancel()
        print(f"⏹️ {self.name} stopped")

    async def _process_messages(self):
        """Async message processing loop"""
        while self.is_running:
            try:
                message = await self.message_queue.get()
                handler = self.message_handlers.get(message.type, self._default_message_handler)
                await handler(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ {self.name} message processing error: {e}")

    async def _default_message_handler(self, message: Message):
        """Default message handler"""
        print(f"📨 {self.name} received {message.type} from {message.source_agent}")

@dataclass
class ConversationEvent:
    """Structured conversation event"""
    timestamp: datetime
    speaker_id: str
    transcript: str
    confidence: float
    chunk_id: int
    insights: Optional[Dict] = None
    action_items: Optional[List] = None
    language_code: str = "en-US"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat()
        }


# --- Fixed STTAgent with proper async message handling and inter-agent messaging ---
class STTAgent(Agent):
    """Agent wrapper for STT service - clean separation of concerns (asyncio compatible)"""
    def __init__(self, stt_service, loop=None, **kwargs):
        super().__init__("stt", "Speech-to-text agent using Google Cloud Speech V2")
        self.stt_service = stt_service
        # WebSocket functionality removed
        # If loop is not provided, get the running loop
        try:
            self.loop = loop or asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.get_event_loop()
        self.current_session_id = None
        self.is_transcribing = False
        # Set up STT service callbacks
        self.stt_service.set_transcript_callback(self._on_transcript_segment)
        self.stt_service.set_error_callback(self._on_stt_error)
        print("✅ STTAgent initialized with STT service")

    def _setup_message_handlers(self):
        """Set up message handlers for STT agent"""
        self.message_handlers = {
            "start_transcription": self._handle_start_transcription,
            "stop_transcription": self._handle_stop_transcription,
            "get_status": self._handle_get_status,
            "get_transcript": self._handle_get_transcript,
            "session_start": self._handle_session_start
        }

    async def _handle_start_transcription(self, message: Message):
        """Handle start transcription request"""
        try:
            result = self.stt_service.start_recording()
            self.is_transcribing = result.get("success", False)
            # Notify other agents
            await self.send_message("orchestration", Message(
                type="transcription_started",
                data=result,
                correlation_id=message.correlation_id
            ))
            print(f"🎤 STTAgent: Transcription started - {result['message']}")
        except Exception as e:
            print(f"❌ STTAgent: Failed to start transcription: {e}")

    async def _handle_stop_transcription(self, message: Message):
        """Handle stop transcription request"""
        try:
            result = self.stt_service.stop_recording()
            self.is_transcribing = False
            transcript_data = self.stt_service.get_transcript("full")
            await self.send_message("orchestration", Message(
                type="transcription_completed",
                data={
                    "stop_result": result,
                    "final_transcript": transcript_data,
                    "session_id": self.current_session_id
                },
                correlation_id=message.correlation_id
            ))
            print(f"⏹️ STTAgent: Transcription stopped - {result['message']}")
        except Exception as e:
            print(f"❌ STTAgent: Failed to stop transcription: {e}")

    async def _handle_get_status(self, message: Message):
        """Handle status request"""
        try:
            status = self.stt_service.get_status()
            await self.send_message(message.source_agent, Message(
                type="status_response",
                data=status.to_dict(),
                correlation_id=message.correlation_id
            ))
        except Exception as e:
            print(f"❌ STTAgent: Failed to get status: {e}")

    async def _handle_get_transcript(self, message: Message):
        """Handle transcript request"""
        try:
            format_type = message.data.get("format", "full")
            transcript_data = self.stt_service.get_transcript(format_type)
            await self.send_message(message.source_agent, Message(
                type="transcript_response",
                data=transcript_data,
                correlation_id=message.correlation_id
            ))
        except Exception as e:
            print(f"❌ STTAgent: Failed to get transcript: {e}")

    async def _handle_session_start(self, message: Message):
        """Handle session start notification"""
        self.current_session_id = message.data.get("session_id")
        print(f"📋 STTAgent: Session {self.current_session_id} started")

    def _on_transcript_segment(self, segment: TranscriptSegment):
        """Callback from STT service for new transcript segments"""
        try:
            event = ConversationEvent(
                timestamp=segment.timestamp,
                speaker_id=segment.speaker_id,
                transcript=segment.text,
                confidence=segment.confidence,
                chunk_id=segment.chunk_id,
                language_code=segment.language_code
            )
            
            # IMPROVED: Show live transcription clearly
            if segment.confidence > 0.6:  # Only show high-confidence segments
                print(f"📝 {segment.text} (conf: {segment.confidence:.3f})")
            else:
                print(f"📝 {segment.text} (conf: {segment.confidence:.3f}) [low confidence]")
            
            # 🚨 CRITICAL FIX: Re-enable thread-safe async communication
            # Use the same pattern that works in web_api.py
            
            # Store in session state for later collection (keep this as backup)
            if not hasattr(self, '_collected_transcripts'):
                self._collected_transcripts = []
            self._collected_transcripts.append(event.to_dict())
            
            # WebSocket functionality removed - transcripts are now handled via direct HTTP API
            
            print(f"📝 Transcript collected: {segment.text[:50]}..." if len(segment.text) > 50 else f"📝 Transcript collected: {segment.text}")
        except Exception as e:
            print(f"❌ STTAgent: Error processing transcript segment: {e}")

    def _on_stt_error(self, error_type: str, error: Exception):
        """Callback from STT service for errors"""
        print(f"❌ STTAgent: STT service error ({error_type}): {error}")

        # Store error for later collection if needed
        if not hasattr(self, '_collected_errors'):
            self._collected_errors = []
        self._collected_errors.append({
            "error_type": error_type,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat()
        })

        # WebSocket functionality removed - errors are now handled via direct HTTP API
        
        print(f"⚠️ STT Error logged: {error_type} - {error}")

    # Public interface methods for external control
    def start_transcription(self):
        """Public method to start transcription"""
        return self.stt_service.start_recording()

    def stop_transcription(self):
        """Public method to stop transcription"""
        return self.stt_service.stop_recording()

    def get_live_status(self):
        """Public method to get current status"""
        return self.stt_service.get_status()

    def save_transcript(self, filename: Optional[str] = None):
        """Public method to save transcript"""
        return self.stt_service.save_transcript(filename)

    def get_collected_transcripts(self):
        """Get transcripts collected during the session"""
        if hasattr(self, '_collected_transcripts'):
            print(f"🔍 STT Agent returning {len(self._collected_transcripts)} collected transcripts")
            return self._collected_transcripts
        print("⚠️ STT Agent has no collected transcripts")
        return []

    def clear_collected_transcripts(self):
        """Clear collected transcripts"""
        if hasattr(self, '_collected_transcripts'):
            self._collected_transcripts.clear()

class LiveAnalysisAgent(Agent):
    """Real-time conversation analysis using Vertex AI Gemini - COLLECTION ONLY VERSION"""
    
    def __init__(self, project_id: str = "econome-hackathon"):
        super().__init__("analysis", "Real-time conversation analysis with Vertex AI")
        
        # Initialize Vertex AI
        self.project_id = project_id
        self._initialize_vertex_ai()
        
        # Analysis state - ONLY for collection now
        self.conversation_buffer = []
        
        print("✅ LiveAnalysisAgent initialized (collection mode)")
    
    def _initialize_vertex_ai(self):
        """Initialize Vertex AI for analysis"""
        try:
            os.environ["GOOGLE_CLOUD_PROJECT"] = self.project_id
            aiplatform.init(project=self.project_id, location="us-central1")
            self._has_vertex_ai = True
            print("✅ Vertex AI initialized")
        except Exception as e:
            print(f"⚠️ Vertex AI initialization failed: {e} - using mock analysis")
            self._has_vertex_ai = False
    
    def _setup_message_handlers(self):
        """Set up message handlers"""
        self.message_handlers = {
            "transcript_chunk": self._handle_transcript_chunk,
            "get_insights": self._handle_get_insights,
            "analyze_full_conversation": self._handle_analyze_full_conversation
        }
    
    async def _handle_transcript_chunk(self, message: Message):
        """Handle incoming transcript chunk - COLLECTION ONLY (no real-time analysis)"""
        try:
            event_data = message.data
            self.conversation_buffer.append(event_data)
            
            # REMOVED: Duplicate print statement
            # print(f"📝 Collected transcript chunk: {event_data.get('transcript', '')[:50]}...")
            
        except Exception as e:
            print(f"❌ AnalysisAgent: Error handling transcript chunk: {e}")
    
    async def _handle_get_insights(self, message: Message):
        """Handle request for current insights"""
        try:
            await self.send_message(message.source_agent, Message(
                type="insights_response",
                data={
                    "current_insights": [],  # No real-time insights anymore
                    "conversation_length": len(self.conversation_buffer),
                    "total_insights": 0
                },
                correlation_id=message.correlation_id
            ))
        except Exception as e:
            print(f"❌ AnalysisAgent: Error getting insights: {e}")
    
    async def _handle_analyze_full_conversation(self, message: Message):
        """Handle request for full conversation analysis"""
        try:
            # Get full conversation text
            conversation_text = " ".join([
                event["transcript"] for event in self.conversation_buffer
            ])
            
            if len(conversation_text.strip()) < 20:
                return
            
            # Perform comprehensive analysis
            insights = await self._call_gemini_for_analysis(conversation_text, analysis_type="comprehensive")
            
            await self.send_message(message.source_agent, Message(
                type="full_analysis_response",
                data=insights,
                correlation_id=message.correlation_id
            ))
            
        except Exception as e:
            print(f"❌ AnalysisAgent: Error in full analysis: {e}")
    
    async def _call_gemini_for_analysis(self, conversation_text: str, analysis_type: str = "comprehensive") -> Dict:
        """Call Gemini API to analyze conversation text - SUMMARY ONLY VERSION"""
        try:
            # SIMPLIFIED: Only get summary, no action items
            summary = summarize_conversation(conversation_text)
            
            return {
                "summary": summary,
                "analysis_type": analysis_type
            }
            
        except Exception as e:
            print(f"❌ Gemini analysis failed: {e}")
            return {
                "summary": "Analysis failed",
                "analysis_type": analysis_type,
                "error": str(e)
            }

class ActionItemAgent(Agent):
    """Extract and manage action items using structured analysis"""
    
    def __init__(self, project_id: str = "econome-hackathon"):
        super().__init__("actions", "Action item extraction and management")
        
        # Initialize BigQuery for action item storage
        self.project_id = project_id
        self._initialize_bigquery()
        
        # Action item state
        self.action_items = []
        self.current_session_id = None
        
        print("✅ ActionItemAgent initialized")
    
    def _initialize_bigquery(self):
        """Initialize BigQuery client"""
        try:
            # Try multiple credential paths (for Cloud Run and local development)
            credential_paths = [
                "speech-credentials.json",  # Default path (local development)
                "/app/secrets/speech/credentials.json",  # New Cloud Run path (separate directories)
                "/app/secrets/speech-credentials.json",  # Legacy Cloud Run path (backward compatibility)
                "/secrets/speech-credentials.json",  # Legacy Cloud Run path (backward compatibility)
            ]

            credentials_found = False
            for path in credential_paths:
                if os.path.exists(path):
                    self.bigquery_client = bigquery.Client(
                        credentials=service_account.Credentials.from_service_account_file(path)
                    )
                    self._has_bigquery = True
                    credentials_found = True
                    print(f"✅ BigQuery client initialized with credentials from {path}")
                    break

            if not credentials_found:
                print("⚠️ No BigQuery credentials - using mock storage")
                self._has_bigquery = False
        except Exception as e:
            print(f"⚠️ BigQuery initialization failed: {e} - using mock storage")
            self._has_bigquery = False
    
    def _setup_message_handlers(self):
        """Set up message handlers"""
        self.message_handlers = {
            "conversation_insights": self._handle_conversation_insights,
            "get_action_items": self._handle_get_action_items,
            "session_start": self._handle_session_start,
            "extract_action_items": self._handle_extract_action_items
        }
    
    async def _handle_conversation_insights(self, message: Message):
        """Handle conversation insights for action item extraction"""
        try:
            insights_data = message.data
            await self._extract_action_items(insights_data)
        except Exception as e:
            print(f"❌ ActionAgent: Error handling insights: {e}")
    
    async def _handle_get_action_items(self, message: Message):
        """Handle request for current action items"""
        try:
            await self.send_message(message.source_agent, Message(
                type="action_items_response",
                data={
                    "action_items": self.action_items,
                    "total_count": len(self.action_items),
                    "session_id": self.current_session_id
                },
                correlation_id=message.correlation_id
            ))
        except Exception as e:
            print(f"❌ ActionAgent: Error getting action items: {e}")
    
    async def _handle_session_start(self, message: Message):
        """Handle session start notification"""
        self.current_session_id = message.data.get("session_id")
        self.action_items.clear()  # Clear previous session action items
        print(f"📋 ActionAgent: Session {self.current_session_id} started")
    
    async def _handle_extract_action_items(self, message: Message):
        """Handle explicit action item extraction request"""
        try:
            conversation_text = message.data.get("conversation_text", "")
            # For explicit extraction, we expect Gemini-style action items
            # Use extract_action_items from gemini_agent if available, or fallback
            action_items = extract_action_items(conversation_text)
            if action_items:
                self.action_items.extend(action_items)
                await self._store_action_items(action_items)
            await self.send_message(message.source_agent, Message(
                type="action_items_extracted",
                data={
                    "action_items": action_items,
                    "total_session_items": len(self.action_items)
                },
                correlation_id=message.correlation_id
            ))
        except Exception as e:
            print(f"❌ ActionAgent: Error extracting action items: {e}")

    async def _extract_action_items(self, insights_data):
        """Extract structured action items using Gemini - UPDATED VERSION"""
        try:
            insights = insights_data.get("insights", {})
            
            # Check if Gemini already provided action items in the insights
            gemini_action_items = insights.get("action_items", [])
            
            if gemini_action_items and isinstance(gemini_action_items, list):
                # Use Gemini's action items directly
                valid_action_items = []
                
                for item in gemini_action_items:
                    if isinstance(item, dict) and "action" in item:
                        # Add session metadata
                        item["session_id"] = self.current_session_id
                        item["timestamp"] = datetime.now().isoformat()
                        item["status"] = "pending"
                        item["context"] = "Extracted by Gemini"
                        valid_action_items.append(item)
                
                if valid_action_items:
                    # Add to session collection
                    self.action_items.extend(valid_action_items)
                    
                    print(f"📋 Gemini Action Items: {len(valid_action_items)} found")
                    for item in valid_action_items:
                        action_type = item.get("type", "unknown")
                        action_text = item.get("action", "")
                        recipient = item.get("recipient")
                        deadline = item.get("deadline")
                        
                        print(f"   • [{action_type.upper()}] {action_text}")
                        if recipient:
                            print(f"     → Target: {recipient}")
                        if deadline:
                            print(f"     → Deadline: {deadline}")
                    
                    # Store in BigQuery
                    await self._store_action_items(valid_action_items)
                    
                    # Send to orchestration agent
                    await self.send_message("orchestration", Message(
                        type="action_items_extracted",
                        data={
                            "action_items": valid_action_items,
                            "session_id": self.current_session_id,
                            "timestamp": datetime.now().isoformat(),
                            "total_session_items": len(self.action_items)
                        }
                    ))
            
        except Exception as e:
            print(f"❌ ActionAgent: Gemini action item extraction error: {e}")
    
    async def _store_action_items(self, action_items: List[Dict]):
        """Store action items in BigQuery"""
        try:
            if self._has_bigquery:
                # In production: implement actual BigQuery insertion
                print(f"💾 Storing {len(action_items)} action items in BigQuery")
                # table_id = f"{self.project_id}.conversation_intelligence.action_items"
                # errors = self.bigquery_client.insert_rows_json(table_id, action_items)
            else:
                print(f"💾 Mock storage: {len(action_items)} action items logged")
                
        except Exception as e:
            print(f"❌ ActionAgent: Storage error: {e}")

class OrchestrationAgent(Agent):
    """Coordinates all agents and manages conversation sessions"""
    
    def __init__(self):
        super().__init__("orchestration", "Multi-agent coordination and session management")
        
        # Session management
        self.current_session = None
        self.session_state = {}
        self.connected_clients = []
        
        # Agent health monitoring
        self.agent_health = {}
        
        print("✅ OrchestrationAgent initialized")
    
    def _setup_message_handlers(self):
        """Set up message handlers"""
        self.message_handlers = {
            "transcription_started": self._handle_transcription_started,
            "transcription_completed": self._handle_transcription_completed,
            "live_transcript": self._handle_live_transcript,
            "action_items_extracted": self._handle_action_items_extracted,
            "stt_error": self._handle_stt_error,
            "get_session_summary": self._handle_get_session_summary,
            "agent_health_check": self._handle_agent_health_check
        }
    
    async def _handle_transcription_started(self, message: Message):
        """Handle transcription start notification"""
        try:
            start_data = message.data
            if self.current_session:
                self.session_state["transcription_active"] = True
                self.session_state["transcription_start_time"] = datetime.now()
                
            print(f"🎤 Orchestration: Transcription started for session {self.current_session}")
            
        except Exception as e:
            print(f"❌ Orchestration: Error handling transcription start: {e}")
    
    async def _handle_transcription_completed(self, message: Message):
        """Handle transcription completion - NOW WITH FINAL ANALYSIS"""
        try:
            completion_data = message.data
            if self.current_session:
                self.session_state["transcription_active"] = False
                self.session_state["transcription_end_time"] = datetime.now()
                self.session_state["final_transcript"] = completion_data.get("final_transcript", {})

                # NEW: Get complete transcript and analyze with Gemini
                await self._process_final_analysis(completion_data)

            print(f"⏹️ Orchestration: Transcription completed for session {self.current_session}")

        except Exception as e:
            print(f"❌ Orchestration: Error handling transcription completion: {e}")

    def _build_clean_transcript(self, transcript_chunks: List[Dict]) -> str:
        """Build clean transcript from collected STT chunks - FIXED VERSION"""
        try:
            clean_segments = []
            all_segments = []

            print(f"🔍 DEBUG: Processing {len(transcript_chunks)} transcript chunks")

            for i, chunk in enumerate(transcript_chunks):
                confidence = chunk.get('confidence', 0)
                text = chunk.get('transcript', '').strip()
                all_segments.append(text)  # Keep everything as backup

                print(f"🔍 Chunk {i+1}: '{text}' (conf: {confidence:.3f})")

                # RELAXED filtering - much more permissive
                if (confidence > 0.3 and  # Lower threshold (was 0.5)
                    len(text) > 1 and     # Allow 2+ character words (was > 2)
                    text.lower() not in ['um', 'ah', 'uh'] and  # Only exclude filler words
                    not (text.isdigit() and len(text) == 1)):    # Only exclude single digits
                    clean_segments.append(text)
                    print(f"✅ Keeping: '{text}'")
                else:
                    print(f"❌ Filtered out: '{text}' (conf: {confidence:.3f})")

            # Try filtered approach first
            filtered_transcript = ' '.join(clean_segments)

            print(f"🧹 Filtered transcript: '{filtered_transcript}' ({len(filtered_transcript)} chars)")

            # Fallback to unfiltered if filtered version is too short
            if len(filtered_transcript.strip()) < 15:  # Very low threshold
                unfiltered_transcript = ' '.join(all_segments)
                print(f"🔄 Using unfiltered transcript as fallback ({len(unfiltered_transcript)} chars)")
                print(f"🔄 Unfiltered: '{unfiltered_transcript}'")
                return unfiltered_transcript

            # Basic cleanup
            final_transcript = ' '.join(filtered_transcript.split())  # Remove extra spaces

            print(f"🧹 Final clean transcript: {len(final_transcript)} chars")
            print(f"🧹 Quality filter: kept {len(clean_segments)}/{len(transcript_chunks)} segments")

            return final_transcript

        except Exception as e:
            print(f"❌ Error building clean transcript: {e}")
            # Emergency fallback - return everything
            try:
                emergency_transcript = ' '.join([chunk.get('transcript', '') for chunk in transcript_chunks])
                print(f"🚨 Emergency fallback transcript: '{emergency_transcript}'")
                return emergency_transcript
            except:
                return ""

    async def _process_final_analysis(self, completion_data: Dict):
        """Process final complete transcript with PARALLEL Gemini calls - SUMMARY + ACTION ITEMS"""
        try:
            print(f"🔍 Starting parallel final analysis...")
            
            # Get collected transcript chunks from session state
            transcript_chunks = self.session_state.get("live_transcript_chunks", [])
            print(f"🔍 Found {len(transcript_chunks)} transcript chunks to analyze")
            
            if len(transcript_chunks) < 3:
                print("⚠️ Too few transcript chunks for analysis")
                self.session_state["final_summary"] = "Not enough conversation content to analyze"
                self.session_state["action_items"] = []
                return
            
            # Build clean transcript from collected chunks
            clean_transcript = self._build_clean_transcript(transcript_chunks)
            
            if len(clean_transcript.strip()) < 20:
                print("⚠️ Clean transcript too short for analysis")
                self.session_state["final_summary"] = "Conversation too short to analyze meaningfully"
                self.session_state["action_items"] = []
                return

            print(f"🧠 Sending clean transcript ({len(clean_transcript)} chars) to PARALLEL Gemini processing...")
            print(f"🧠 Preview: {clean_transcript[:100]}...")

            # Import Gemini functions
            from gemini_agent import summarize_conversation, extract_action_items

            # 🚀 PARALLEL PROCESSING: Both Gemini calls happen simultaneously!
            print("⚡ Starting PARALLEL Gemini processing...")
            
            async def get_summary():
                """Async wrapper for summary generation"""
                print("🧠 [PARALLEL TASK 1] Generating organized summary...")
                return summarize_conversation(clean_transcript)
            
            async def get_action_items():
                """Async wrapper for action item extraction"""
                print("📋 [PARALLEL TASK 2] Extracting action items...")
                return extract_action_items(clean_transcript)
            
            # Execute both Gemini calls in parallel using asyncio.gather()
            summary_task = asyncio.create_task(get_summary())
            actions_task = asyncio.create_task(get_action_items())
            
            # Wait for BOTH to complete simultaneously
            final_summary, action_items = await asyncio.gather(summary_task, actions_task)
            
            print("⚡ PARALLEL processing complete!")

            # Store BOTH results in session state
            self.session_state["final_summary"] = final_summary
            self.session_state["action_items"] = action_items
            self.session_state["full_transcript_text"] = clean_transcript

            # Log results
            print(f"✅ Summary generated: {len(final_summary)} chars")
            print(f"✅ Summary preview: {final_summary[:100]}...")
            print(f"✅ Action items extracted: {len(action_items)} items")
            
            # Display action items for immediate feedback
            if action_items and len(action_items) > 0:
                print(f"📋 ACTION ITEMS FOUND:")
                for i, item in enumerate(action_items, 1):
                    if isinstance(item, dict) and "action" in item:
                        item_type = item.get("type", "unknown").upper()
                        action_text = item.get("action", "")
                        deadline = item.get("deadline")
                        recipient = item.get("recipient")
                        
                        print(f"   {i}. [{item_type}] {action_text}")
                        if deadline:
                            print(f"      ⏰ Deadline: {deadline}")
                        if recipient:
                            print(f"      👤 Recipient: {recipient}")
            else:
                print("📋 No action items found in conversation")

            print(f"✅ PARALLEL final analysis complete!")

        except Exception as e:
            print(f"❌ Parallel final analysis failed: {e}")
            import traceback
            traceback.print_exc()
            self.session_state["final_summary"] = f"Analysis failed: {str(e)}"
            self.session_state["action_items"] = []
    
    async def _handle_live_transcript(self, message: Message):
        """Handle live transcript updates"""
        try:
            transcript_data = message.data
            if self.current_session:
                # Update session state with latest transcript
                if "live_transcript_chunks" not in self.session_state:
                    self.session_state["live_transcript_chunks"] = []
                
                self.session_state["live_transcript_chunks"].append(transcript_data)
                self.session_state["last_activity"] = datetime.now()
                
        except Exception as e:
            print(f"❌ Orchestration: Error handling live transcript: {e}")
    
    async def _handle_action_items_extracted(self, message: Message):
        """Handle action items extraction"""
        try:
            action_data = message.data
            if self.current_session:
                if "action_items" not in self.session_state:
                    self.session_state["action_items"] = []
                
                self.session_state["action_items"].extend(action_data.get("action_items", []))
                
            print(f"📊 Orchestration: Session has {len(self.session_state.get('action_items', []))} total action items")
            
        except Exception as e:
            print(f"❌ Orchestration: Error handling action items: {e}")
    
    async def _handle_stt_error(self, message: Message):
        """Handle STT service errors"""
        try:
            error_data = message.data
            print(f"⚠️ Orchestration: STT error reported - {error_data['error_type']}: {error_data['error_message']}")
            
            # Could implement error recovery logic here
            
        except Exception as e:
            print(f"❌ Orchestration: Error handling STT error: {e}")
    
    async def _handle_get_session_summary(self, message: Message):
        """Handle session summary request"""
        try:
            summary = self.get_session_summary()
            
            await self.send_message(message.source_agent, Message(
                type="session_summary_response",
                data=summary,
                correlation_id=message.correlation_id
            ))
            
        except Exception as e:
            print(f"❌ Orchestration: Error getting session summary: {e}")
    
    async def _handle_agent_health_check(self, message: Message):
        """Handle agent health check"""
        try:
            agent_name = message.source_agent
            self.agent_health[agent_name] = {
                "last_heartbeat": datetime.now(),
                "status": "healthy"
            }
            
        except Exception as e:
            print(f"❌ Orchestration: Error in health check: {e}")
    
    def start_conversation_session(self) -> str:
        """Initialize new conversation session"""
        session_id = f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.current_session = session_id
        self.session_state = {
            "session_id": session_id,
            "start_time": datetime.now(),
            "status": "active",
            "transcription_active": False,
            "live_transcript_chunks": [],
            "action_items": [],
            "insights": [],
            "participants": []
        }
        
        print(f"🚀 Orchestration: Started conversation session: {session_id}")
        
        # Notify all agents of session start
        for agent_name in self.other_agents:
            asyncio.create_task(self.send_message(agent_name, Message(
                type="session_start",
                data={"session_id": session_id}
            )))
        
        return session_id

    def end_conversation_session(self) -> Dict[str, Any]:
        """End current conversation session"""
        if not self.current_session:
            return {"error": "No active session"}
        
        # Update session state
        self.session_state["status"] = "completed"
        self.session_state["end_time"] = datetime.now()
        
        # Get final summary
        summary = self.get_session_summary()
        
        print(f"🏁 Orchestration: Ended session {self.current_session}")
        
        # Clear current session
        self.current_session = None
        
        return summary

    def get_session_summary(self) -> Dict[str, Any]:
        """Get comprehensive session summary with REAL Gemini summary AND action items"""
        if not self.current_session:
            return {"error": "No active session"}

        duration = datetime.now() - self.session_state["start_time"]

        # Get both summary and action items from final analysis
        final_summary = self.session_state.get("final_summary", "Summary not yet generated")
        action_items = self.session_state.get("action_items", [])
        full_transcript = self.session_state.get("full_transcript_text", "")

        return {
            "session_id": self.current_session,
            "status": self.session_state["status"],
            "start_time": self.session_state["start_time"].isoformat(),
            "duration_seconds": duration.total_seconds(),
            "duration_formatted": str(duration).split('.')[0],
            "transcription_active": self.session_state.get("transcription_active", False),
            "total_transcript_chunks": len(self.session_state.get("live_transcript_chunks", [])),
            "full_transcript": full_transcript,
            "gemini_summary": final_summary,
            "action_items": action_items,  # 🆕 NEW: Include action items in results
            "total_action_items": len(action_items) if action_items else 0,  # 🆕 NEW: Count
            "last_activity": self.session_state.get("last_activity", self.session_state["start_time"]).isoformat(),
            "agent_health": self.agent_health
        }

    def get_live_status(self) -> Dict[str, Any]:
        """Get real-time system status"""
        if not self.current_session:
            return {
                "session_active": False,
                "message": "No active session"
            }
        
        return {
            "session_active": True,
            "session_id": self.current_session,
            "transcription_active": self.session_state.get("transcription_active", False),
            "agents_running": sum(1 for agent in self.other_agents.values() 
                               if hasattr(agent, 'is_running') and agent.is_running),
            "total_agents": len(self.other_agents),
            "recent_activity": self.session_state.get("last_activity", datetime.now()).isoformat(),
            "session_duration": str(datetime.now() - self.session_state["start_time"]).split('.')[0]
        }


class ConversationIntelligenceSystem:
    """Main system orchestrator for real-time conversation intelligence - FIXED VERSION"""

    def __init__(self, mock_mode: bool = False, **kwargs):
        print("🏗️ Initializing Conversation Intelligence System...")
        self.loop = None
        self.stt_service = None
        self.agents = {}
        self.is_running = False
        self.mock_mode = mock_mode
        # WebSocket functionality removed
        self.kwargs = kwargs
        self.session_id = None  # FIXED: Add session_id storage
        print("✅ Conversation Intelligence System initialized")

    def _connect_agents(self):
        """Connect all agents for inter-agent communication - FIXED VERSION"""
        # Agent name mapping: internal_name -> agent_names_used_in_messages
        agent_connections = {
            "stt": ["analysis", "orchestration", "actions"],
            "analysis": ["stt", "orchestration", "actions"], 
            "actions": ["stt", "analysis", "orchestration"],
            "orchestration": ["stt", "analysis", "actions"]
        }
        
        # Connect each agent to others using consistent naming
        for agent_key, agent in self.agents.items():
            for target_key in agent_connections[agent_key]:
                if target_key in self.agents:
                    agent.connect_agent(target_key, self.agents[target_key])

        print("🔗 All agents connected with fixed naming")

    def _build_agents(self):
        """Build and initialize all agents - FIXED VERSION"""
        self.stt_service = create_stt_service(mock_mode=self.mock_mode, **self.kwargs)

        # Use the agent classes from this file
        # WebSocket functionality removed
        self.agents = {
            "stt": STTAgent(self.stt_service, self.loop),
            "analysis": LiveAnalysisAgent(),
            "actions": ActionItemAgent(),
            "orchestration": OrchestrationAgent()
        }
        self._connect_agents()

    async def start_system(self) -> str:
        """Start the entire multi-agent system - FIXED VERSION"""
        print("🚀 Starting Multi-Agent Conversation Intelligence System...")
        self.loop = asyncio.get_running_loop()
        self._build_agents()
        
        # Start all agents
        for agent in self.agents.values():
            agent.start()
        
        self.is_running = True
        
        # Start conversation session and store it
        self.session_id = self.agents["orchestration"].start_conversation_session()
        print("🎯 Multi-Agent System ready for conversation intelligence!")
        return self.session_id

    def get_internal_state(self) -> Dict[str, Any]:
        """
        OBSERVABILITY: Get comprehensive internal state for debugging and monitoring
        """
        try:
            import time
            current_time = time.time()

            # Get STT service state
            stt_state = {}
            stt_agent = self.get_agent("stt")
            if stt_agent and hasattr(stt_agent, 'stt_service'):
                if hasattr(stt_agent.stt_service, 'get_internal_state'):
                    stt_state = stt_agent.stt_service.get_internal_state()
                else:
                    stt_state = {
                        "error": "STT service does not have get_internal_state method",
                        "service_available": True
                    }
            else:
                stt_state = {
                    "error": "STT agent or service not available",
                    "service_available": False
                }

            # WebSocket functionality removed
            websocket_state = {
                "status": "WebSocket functionality removed - using direct HTTP API",
                "total_connections": 0
            }

            return {
                "system_type": "ConversationIntelligenceSystem",
                "session_id": self.session_id,
                "is_running": self.is_running,
                "mock_mode": self.mock_mode,
                "agents_available": list(self.agents.keys()),
                "agents_count": len(self.agents),
                "stt_service_state": stt_state,
                "websocket_manager_state": websocket_state,
                "system_kwargs": self.kwargs,
                "state_dump_timestamp": current_time * 1000  # milliseconds
            }
        except Exception as e:
            return {
                "error": f"Failed to get internal state: {e}",
                "system_type": "ConversationIntelligenceSystem",
                "state_dump_timestamp": time.time() * 1000
            }

    def stop_system(self) -> Dict[str, Any]:
        """Stop the entire system"""
        print("⏹️ Stopping Multi-Agent System...")

        # Stop transcription if active
        if self.agents and "stt" in self.agents and self.agents["stt"].is_transcribing:
            self.agents["stt"].stop_transcription()

        # End session
        summary = {}
        if self.agents and "orchestration" in self.agents:
            summary = self.agents["orchestration"].end_conversation_session()

        # Stop all agents
        if self.agents:
            for agent in self.agents.values():
                agent.stop()

        self.is_running = False

        print("✅ Multi-Agent System stopped")
        return summary

    def start_conversation(self) -> Dict[str, Any]:
        """Start live conversation processing"""
        if not self.is_running:
            return {"error": "System not running"}

        result = self.agents["stt"].start_transcription()
        print("🎤 Live conversation processing started...")
        return result

    async def stop_conversation(self) -> Dict[str, Any]:
        """Stop conversation and get summary - ASYNC PARALLEL PROCESSING VERSION"""
        if not self.is_running:
            return {"error": "System not running"}

        print("🛑 Stopping conversation and processing PARALLEL final analysis...")

        # STEP 1: Stop the STT service to prevent new chunks
        self.agents["stt"].stop_transcription()

        # STEP 2: Get collected transcript chunks directly from STT agent
        stt_agent = self.agents["stt"]
        transcript_chunks = stt_agent.get_collected_transcripts()

        # Also get from orchestration as fallback
        orchestration = self.agents["orchestration"]
        orchestration_chunks = orchestration.session_state.get("live_transcript_chunks", [])

        # Use whichever has more data
        if len(transcript_chunks) < len(orchestration_chunks):
            transcript_chunks = orchestration_chunks

        # FIXED: If orchestration doesn't have transcripts, copy from STT agent
        if len(orchestration_chunks) == 0 and len(transcript_chunks) > 0:
            print(f"🔄 Copying {len(transcript_chunks)} transcripts from STT agent to orchestration")
            orchestration.session_state["live_transcript_chunks"] = transcript_chunks

        print(f"📊 Found {len(transcript_chunks)} transcript chunks to process")
        print(f"📊 STT agent has: {len(stt_agent.get_collected_transcripts())} chunks")
        print(f"📊 Orchestration has: {len(orchestration_chunks)} chunks")

        # STEP 3: Call the parallel processing directly (much cleaner!)
        try:
            if len(transcript_chunks) >= 3:
                print("🧠 Processing PARALLEL final analysis...")

                # Build clean transcript using the method we fixed
                clean_transcript = orchestration._build_clean_transcript(transcript_chunks)

                if len(clean_transcript.strip()) >= 15:
                    print(f"📝 Clean transcript ready: {len(clean_transcript)} chars")
                    print(f"📝 Preview: {clean_transcript[:100]}...")

                    # Import Gemini functions
                    from gemini_agent import summarize_conversation, extract_action_items

                    # 🚀 DIRECT PARALLEL EXECUTION (much cleaner!)
                    print("⚡ Executing PARALLEL Gemini analysis...")

                    # Both happen simultaneously!
                    summary_task = asyncio.create_task(asyncio.to_thread(summarize_conversation, clean_transcript))
                    actions_task = asyncio.create_task(asyncio.to_thread(extract_action_items, clean_transcript))

                    final_summary, action_items = await asyncio.gather(summary_task, actions_task)

                    # Store BOTH results in session state
                    orchestration.session_state["final_summary"] = final_summary
                    orchestration.session_state["action_items"] = action_items
                    orchestration.session_state["full_transcript_text"] = clean_transcript

                    print(f"✅ PARALLEL processing complete!")
                    print(f"✅ Summary: {len(final_summary)} chars")
                    print(f"✅ Action items: {len(action_items)} items")
                else:
                    print("⚠️ Clean transcript too short for analysis")
                    orchestration.session_state["final_summary"] = "Conversation too short to analyze meaningfully"
                    orchestration.session_state["action_items"] = []
            else:
                print("⚠️ Too few transcript chunks for analysis")
                orchestration.session_state["final_summary"] = "Not enough conversation content to analyze"
                orchestration.session_state["action_items"] = []
        except Exception as e:
            print(f"❌ Parallel final analysis failed: {e}")
            import traceback
            traceback.print_exc()
            orchestration.session_state["final_summary"] = f"Analysis failed: {str(e)}"
            orchestration.session_state["action_items"] = []

        # Get session summary (now includes action items)
        summary = orchestration.get_session_summary()
        print("⏹️ Conversation stopped with PARALLEL final analysis")
        return summary

    def get_live_status(self) -> Dict[str, Any]:
        """Get real-time system status"""
        if not self.is_running:
            return {"system_running": False}

        orchestration_status = self.agents["orchestration"].get_live_status()
        stt_status = self.agents["stt"].get_live_status()

        return {
            "system_running": self.is_running,
            "session_info": orchestration_status,
            "stt_status": stt_status.to_dict() if hasattr(stt_status, 'to_dict') else stt_status,
            "timestamp": datetime.now().isoformat()
        }

    def save_session_transcript(self, filename = None) -> Dict[str, Any]:
        """Save current session transcript"""
        return self.agents["stt"].save_transcript(filename)

    # Direct agent access for advanced usage
    def get_agent(self, agent_name: str):
        """Get direct access to specific agent"""
        return self.agents.get(agent_name)


# Demo and Testing Functions
async def demo_conversation_intelligence():
    """Demo function for hackathon presentation"""

    print("🏆 ADK HACKATHON DEMO - REAL-TIME CONVERSATION INTELLIGENCE")
    print("=" * 70)

    # Initialize system
    system = ConversationIntelligenceSystem(mock_mode=False)  # Set to True for demo without credentials

    try:
        # Start system
        session_id = await system.start_system()

        print(f"\n🎯 Demo Instructions:")
        print(f"1. Press ENTER to start live conversation processing")
        print(f"2. Speak naturally for 30-60 seconds")
        print(f"3. Watch real-time transcription (no premature analysis)")
        print(f"4. Press ENTER again to stop and see final Gemini summary")

        input("\nPress ENTER to start conversation...")

        # Start conversation
        start_result = system.start_conversation()
        if not start_result.get("success"):
            print(f"❌ Failed to start: {start_result.get('message')}")
            return

        print("\n🎤 RECORDING... Speak naturally:")
        print("Try speaking in complete sentences about:")
        print("- Your plans for the day")
        print("- A project you're working on")
        print("- Any thoughts or ideas")

        input("\nPress ENTER when done speaking...")

        # Stop and get results
        print("\n⏹️ Stopping conversation and generating summary...")
        summary = system.stop_conversation()

        # Display results
        print("\n" + "=" * 70)
        print("🎯 DEMO RESULTS:")
        print("=" * 70)

        if summary.get("error"):
            print(f"Error: {summary['error']}")
        else:
            print(f"Session ID: {summary.get('session_id', 'N/A')}")
            print(f"Duration: {summary.get('duration_formatted', 'N/A')}")
            print(f"Transcript Chunks: {summary.get('total_transcript_chunks', 0)}")
            
            # Show clean transcript
            transcript = summary.get('full_transcript', '')
            if transcript:
                print(f"\n📄 CLEAN TRANSCRIPT:")
                print(f"{transcript}")
            
            # Show Gemini summary
            gemini_summary = summary.get('gemini_summary', 'No summary')
            print(f"\n🧠 GEMINI SUMMARY:")
            print(f"{gemini_summary}")

        print("\n🏆 DEMO COMPLETE!")

    except Exception as e:
        print(f"❌ Demo error: {e}")
    finally:
        # Cleanup
        system.stop_system()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("🧪 Running simplified test...")
        asyncio.run(demo_conversation_intelligence())
    else:
        asyncio.run(demo_conversation_intelligence())