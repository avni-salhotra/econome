#!/usr/bin/env python3
"""
REWRITTEN FOR HACKATHON DEADLINE - MINIMAL AND CORRECT
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable

from .speech_agent import ProductionSTTServiceV2, create_stt_service, TranscriptSegment
from .gemini_agent import summarize_conversation, extract_action_items

class Agent:
    def __init__(self, name: str):
        self.name = name
        print(f"✅ Agent '{name}' created.")

class STTAgent(Agent):
    def __init__(self, stt_service: ProductionSTTServiceV2):
        super().__init__("stt")
        self.stt_service = stt_service

class OrchestrationAgent(Agent):
    def __init__(self, session_id: str, sse_callback: Optional[Callable] = None):
        # THE FIX: Assign all instance variables BEFORE calling super().__init__
        self.session_id = session_id
        self.sse_callback = sse_callback
        self.main_loop = None  # Will store reference to main asyncio loop
        super().__init__("orchestration")
        self.full_transcript: List[Dict] = []
        
        # Try to get the current event loop for later use
        try:
            self.main_loop = asyncio.get_running_loop()
            print(f"✅ OrchestrationAgent captured main event loop for session {self.session_id}")
        except RuntimeError:
            print(f"⚠️ No event loop running during OrchestrationAgent init for session {self.session_id}")
        
        print(f"✅ OrchestrationAgent initialized for session {self.session_id}")

    def set_event_loop(self, loop):
        """Allow setting the event loop from the web API"""
        self.main_loop = loop
        print(f"✅ Event loop set for OrchestrationAgent {self.session_id}")

    def handle_transcript_segment(self, segment: TranscriptSegment):
        """Callback to handle a new transcript segment."""
        if segment.is_final:
            self.full_transcript.append(segment.to_dict())
        
        # Always log the transcript for debugging
        print(f"📝 Transcript segment: {segment.text[:50]}..." + (" (final)" if segment.is_final else " (interim)"))
        
        # Forward to frontend via SSE - FIX: Handle threading properly
        if self.sse_callback and self.main_loop:
            try:
                print(f"🚀 Forwarding to SSE: {segment.text[:30]}...")
                future = asyncio.run_coroutine_threadsafe(
                    self.sse_callback(self.session_id, {
                        "type": "transcript",
                        "text": segment.text,
                        "is_final": segment.is_final,
                        "confidence": segment.confidence,
                        "timestamp": segment.timestamp.isoformat(),
                        "chunk_index": getattr(segment, 'chunk_index', -1)
                    }),
                    self.main_loop
                )
                print(f"✅ SSE forwarding scheduled successfully")
            except Exception as e:
                print(f"❌ Error forwarding to SSE: {e}")
        elif not self.sse_callback:
            print(f"⚠️ No SSE callback available for forwarding")
        elif not self.main_loop:
            print(f"⚠️ No event loop available for SSE forwarding")

class ConversationIntelligenceSystem:
    """Manages the entire conversation intelligence system"""

    def __init__(self, session_id: str, sse_callback: Optional[Callable] = None):
        self.session_id = session_id
        self.sse_callback = sse_callback
        self.stt_service: ProductionSTTServiceV2 = create_stt_service()
        
        # Create agents
        self.stt_agent = STTAgent(stt_service=self.stt_service)
        self.orchestration_agent = OrchestrationAgent(
            session_id=self.session_id,
            sse_callback=self.sse_callback
        )
        
        # Wire up callbacks
        self.stt_service.set_transcript_callback(self.orchestration_agent.handle_transcript_segment)
        
        print(f"✅ ConversationIntelligenceSystem initialized for session {self.session_id}")

    def start(self):
        """Starts the STT processing."""
        print("🚀 Starting ConversationIntelligenceSystem...")
        self.stt_service.initialize_frontend_streaming()
        print("✅ STT Service Initialized for frontend streaming.")

    def get_audio_queue(self):
        """Provides access to the audio queue for the web API."""
        return self.stt_service._audio_queue

    def get_agent(self, agent_name: str):
        """Get agent by name for web API integration"""
        if agent_name == "stt":
            return self.stt_agent
        elif agent_name == "orchestration":
            return self.orchestration_agent
        else:
            return None

    async def stop_conversation(self) -> Dict[str, Any]:
        """Stop conversation and run parallel Gemini agent analysis"""
        print("🛑 Stopping conversation...")
        
        full_transcript_text = " ".join([seg['text'] for seg in self.orchestration_agent.full_transcript])
        
        # Send initial progress updates via SSE
        if self.sse_callback:
            await self.sse_callback(self.session_id, {
                "type": "agent_progress",
                "agent": "summary",
                "status": "started",
                "progress": 0,
                "message": "🔍 Summary agent reading transcript..."
            })
            
            await self.sse_callback(self.session_id, {
                "type": "agent_progress", 
                "agent": "action_items",
                "status": "started",
                "progress": 0,
                "message": "🔍 Action items agent scanning for tasks..."
            })
        
        # Create enhanced tasks with progress tracking
        async def enhanced_summarize_conversation(text):
            """Enhanced summary task with progress updates"""
            if self.sse_callback:
                await self.sse_callback(self.session_id, {
                    "type": "agent_progress",
                    "agent": "summary", 
                    "progress": 25,
                    "message": "📊 Analyzing conversation structure..."
                })
            
            # Wait a moment to simulate real processing
            await asyncio.sleep(0.5)
            
            if self.sse_callback:
                await self.sse_callback(self.session_id, {
                    "type": "agent_progress",
                    "agent": "summary",
                    "progress": 60,
                    "message": "🧠 Identifying key themes..."
                })
            
            # Call actual Gemini function
            result = await summarize_conversation(text)
            
            if self.sse_callback:
                await self.sse_callback(self.session_id, {
                    "type": "agent_progress",
                    "agent": "summary",
                    "progress": 100,
                    "message": "✅ Summary generated successfully!"
                })
            
            return result
        
        async def enhanced_extract_action_items(text):
            """Enhanced action items task with progress updates"""
            if self.sse_callback:
                await self.sse_callback(self.session_id, {
                    "type": "agent_progress",
                    "agent": "action_items",
                    "progress": 30,
                    "message": "📋 Extracting action items..."
                })
            
            # Wait a moment to simulate real processing
            await asyncio.sleep(0.3)
            
            if self.sse_callback:
                await self.sse_callback(self.session_id, {
                    "type": "agent_progress", 
                    "agent": "action_items",
                    "progress": 70,
                    "message": "👤 Identifying responsible parties..."
                })
            
            # Call actual Gemini function
            result = await extract_action_items(text)
            
            if self.sse_callback:
                await self.sse_callback(self.session_id, {
                    "type": "agent_progress",
                    "agent": "action_items", 
                    "progress": 100,
                    "message": "✅ Action items extracted successfully!"
                })
            
            return result
        
        # Run enhanced analysis in parallel - MUST remain parallel for performance
        print("🧠 Running parallel Gemini agent analysis...")
        summary, action_items = await asyncio.gather(
            enhanced_summarize_conversation(full_transcript_text),
            enhanced_extract_action_items(full_transcript_text)
        )
        print("✅ Parallel Gemini agent analysis complete")
        
        # Stop the STT service
        self.stt_service.stop_recording()
        
        return {
            "final_summary": summary,
            "final_action_items": action_items,
            "ephemeral_url": f"http://example.com/results/{self.session_id}" # Placeholder
        }