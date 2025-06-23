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
        super().__init__("orchestration")
        self.full_transcript: List[Dict] = []
        print(f"✅ OrchestrationAgent initialized for session {self.session_id}")

    def handle_transcript_segment(self, segment: TranscriptSegment):
        """Callback to handle a new transcript segment."""
        if segment.is_final:
            self.full_transcript.append(segment.to_dict())
        
        # Forward to frontend via SSE - FIX: Handle threading properly
        if self.sse_callback:
            try:
                # Try to get existing event loop from the main thread
                loop = asyncio.get_running_loop()
                asyncio.run_coroutine_threadsafe(
                    self.sse_callback(self.session_id, {
                        "type": "transcript",
                        "text": segment.text,
                        "is_final": segment.is_final,
                        "confidence": segment.confidence
                    }),
                    loop
                )
            except RuntimeError:
                # No event loop running - skip SSE for now
                # This happens when called from worker threads
                print(f"📝 Transcript segment: {segment.text[:50]}..." + (" (final)" if segment.is_final else " (interim)"))
                pass

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

    async def stop_conversation(self) -> Dict[str, Any]:
        """Stop conversation and get summary"""
        print("🛑 Stopping conversation...")
        
        full_transcript_text = " ".join([seg['text'] for seg in self.orchestration_agent.full_transcript])
        
        # Run analysis in parallel
        summary_task = summarize_conversation(full_transcript_text)
        actions_task = extract_action_items(full_transcript_text)
        
        summary, action_items = await asyncio.gather(summary_task, actions_task)
        
        # Stop the STT service
        self.stt_service.stop_recording()
        
        return {
            "final_summary": summary,
            "final_action_items": action_items,
            "ephemeral_url": f"http://example.com/results/{self.session_id}" # Placeholder
        }