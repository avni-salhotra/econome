#!/usr/bin/env python3
"""
WebSocket Connection Manager for Real-time Communication
Handles live transcription streaming and system status updates
"""

import asyncio
import json
import time
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebSocketConnection:
    """Individual WebSocket connection wrapper"""
    
    def __init__(self, websocket: WebSocket, connection_id: str):
        self.websocket = websocket
        self.connection_id = connection_id
        self.connected_at = datetime.now()
        self.last_activity = datetime.now()
        self.is_active = True
        self.conversation_session_id: Optional[str] = None
        self.user_metadata: Dict[str, Any] = {}
    
    async def send_message(self, message: Dict[str, Any]) -> bool:
        """Send message to this connection"""
        try:
            await self.websocket.send_text(json.dumps(message))
            self.last_activity = datetime.now()
            return True
        except Exception as e:
            logger.error(f"Failed to send message to {self.connection_id}: {e}")
            self.is_active = False
            return False
    
    async def send_error(self, error_message: str, error_type: str = "general"):
        """Send error message to this connection"""
        await self.send_message({
            "type": "error",
            "error_type": error_type,
            "message": error_message,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information"""
        return {
            "connection_id": self.connection_id,
            "connected_at": self.connected_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "is_active": self.is_active,
            "conversation_session_id": self.conversation_session_id,
            "duration_seconds": (datetime.now() - self.connected_at).total_seconds()
        }

class WebSocketManager:
    """Manages multiple WebSocket connections for real-time communication"""
    
    def __init__(self):
        self.connections: Dict[str, WebSocketConnection] = {}
        self.connection_counter = 0
        self.message_handlers: Dict[str, Callable] = {}
        self.broadcast_history: List[Dict[str, Any]] = []
        self.max_history = 100
        self._cleanup_task = None

        logger.info("✅ WebSocket Manager initialized")

    def start_cleanup_task(self):
        """Start the background cleanup task"""
        if self._cleanup_task is None:
            try:
                self._cleanup_task = asyncio.create_task(self._cleanup_inactive_connections())
                logger.info("✅ WebSocket cleanup task started")
            except RuntimeError:
                # No event loop running, will start later
                logger.info("⏳ WebSocket cleanup task will start when event loop is available")

    async def connect(self, websocket: WebSocket) -> str:
        """Accept new WebSocket connection"""
        await websocket.accept()

        # Start cleanup task if not already running
        if self._cleanup_task is None:
            self.start_cleanup_task()

        # Generate unique connection ID
        self.connection_counter += 1
        connection_id = f"conn_{self.connection_counter}_{int(time.time())}"

        # Create connection wrapper
        connection = WebSocketConnection(websocket, connection_id)
        self.connections[connection_id] = connection

        logger.info(f"🔗 New WebSocket connection: {connection_id}")

        # Send welcome message
        await connection.send_message({
            "type": "connection_established",
            "connection_id": connection_id,
            "timestamp": datetime.now().isoformat(),
            "message": "WebSocket connection established"
        })

        return connection_id
    
    def disconnect(self, connection_id: str):
        """Remove WebSocket connection"""
        if connection_id in self.connections:
            connection = self.connections[connection_id]
            connection.is_active = False
            del self.connections[connection_id]
            logger.info(f"🔌 WebSocket disconnected: {connection_id}")
    
    async def send_to_connection(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """Send message to specific connection"""
        if connection_id not in self.connections:
            logger.warning(f"Connection {connection_id} not found")
            return False
        
        connection = self.connections[connection_id]
        return await connection.send_message(message)
    
    async def broadcast(self, message: Dict[str, Any], exclude_connection: Optional[str] = None):
        """Broadcast message to all active connections"""
        message["broadcast_timestamp"] = datetime.now().isoformat()
        
        # Add to broadcast history
        self.broadcast_history.append(message)
        if len(self.broadcast_history) > self.max_history:
            self.broadcast_history.pop(0)
        
        # Send to all active connections
        disconnected_connections = []
        
        for connection_id, connection in self.connections.items():
            if connection_id == exclude_connection:
                continue
                
            if not connection.is_active:
                disconnected_connections.append(connection_id)
                continue
            
            success = await connection.send_message(message)
            if not success:
                disconnected_connections.append(connection_id)
        
        # Clean up disconnected connections
        for connection_id in disconnected_connections:
            self.disconnect(connection_id)
        
        logger.info(f"📡 Broadcast sent to {len(self.connections)} connections")
    
    async def broadcast_live_transcript(self, text: str, confidence: float, speaker_id: str = "Speaker_1"):
        """Broadcast live transcription update"""
        await self.broadcast({
            "type": "live_transcript",
            "text": text,
            "confidence": confidence,
            "speaker_id": speaker_id,
            "timestamp": datetime.now().isoformat()
        })
    
    async def broadcast_system_status(self, status: str, message: str, details: Dict[str, Any] = None):
        """Broadcast system status update"""
        await self.broadcast({
            "type": "system_status",
            "status": status,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        })
    
    async def broadcast_processing_update(self, stage: str, progress: float = None, message: str = ""):
        """Broadcast processing progress update"""
        await self.broadcast({
            "type": "processing_update",
            "stage": stage,
            "progress": progress,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })
    
    async def send_analysis_results(self, connection_id: str, results: Dict[str, Any], ephemeral_url: str):
        """Send analysis results to specific connection"""
        await self.send_to_connection(connection_id, {
            "type": "analysis_complete",
            "results": results,
            "ephemeral_url": ephemeral_url,
            "expires_in_hours": 24,
            "privacy_note": "This link will automatically expire and delete your data in 24 hours.",
            "timestamp": datetime.now().isoformat()
        })
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get statistics about active connections"""
        active_connections = [conn for conn in self.connections.values() if conn.is_active]
        
        return {
            "total_connections": len(self.connections),
            "active_connections": len(active_connections),
            "broadcast_history_count": len(self.broadcast_history),
            "connections": [conn.get_connection_info() for conn in active_connections]
        }
    
    async def _cleanup_inactive_connections(self):
        """Background task to clean up inactive connections"""
        while True:
            try:
                inactive_connections = []
                current_time = datetime.now()
                
                for connection_id, connection in self.connections.items():
                    # Mark as inactive if no activity for 5 minutes
                    if (current_time - connection.last_activity).total_seconds() > 300:
                        inactive_connections.append(connection_id)
                
                for connection_id in inactive_connections:
                    logger.info(f"🧹 Cleaning up inactive connection: {connection_id}")
                    self.disconnect(connection_id)
                
                if inactive_connections:
                    logger.info(f"🧹 Cleaned up {len(inactive_connections)} inactive connections")
                
            except Exception as e:
                logger.error(f"❌ Connection cleanup error: {e}")
            
            # Clean every 2 minutes
            await asyncio.sleep(120)
    
    def register_message_handler(self, message_type: str, handler: Callable):
        """Register handler for specific message types"""
        self.message_handlers[message_type] = handler
        logger.info(f"📝 Registered handler for message type: {message_type}")
    
    async def handle_message(self, connection_id: str, message: Dict[str, Any]):
        """Handle incoming message from WebSocket"""
        message_type = message.get("type", "unknown")
        
        if message_type in self.message_handlers:
            try:
                await self.message_handlers[message_type](connection_id, message)
            except Exception as e:
                logger.error(f"❌ Message handler error for {message_type}: {e}")
                await self.send_to_connection(connection_id, {
                    "type": "error",
                    "message": f"Error handling {message_type}: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
        else:
            logger.warning(f"⚠️ No handler for message type: {message_type}")
            await self.send_to_connection(connection_id, {
                "type": "error",
                "message": f"Unknown message type: {message_type}",
                "timestamp": datetime.now().isoformat()
            })

# Global WebSocket manager instance
websocket_manager = WebSocketManager()

# Convenience functions for easy integration
async def broadcast_live_transcript(text: str, confidence: float, speaker_id: str = "Speaker_1"):
    """Convenience function to broadcast live transcript"""
    await websocket_manager.broadcast_live_transcript(text, confidence, speaker_id)

async def broadcast_system_status(status: str, message: str, details: Dict[str, Any] = None):
    """Convenience function to broadcast system status"""
    await websocket_manager.broadcast_system_status(status, message, details)

async def broadcast_processing_update(stage: str, progress: float = None, message: str = ""):
    """Convenience function to broadcast processing update"""
    await websocket_manager.broadcast_processing_update(stage, progress, message)

if __name__ == "__main__":
    # Test the WebSocket manager
    async def test_websocket_manager():
        print("🧪 Testing WebSocket Manager...")
        
        manager = WebSocketManager()
        
        # Test broadcast
        await manager.broadcast({
            "type": "test",
            "message": "Test broadcast message"
        })
        
        # Test stats
        stats = manager.get_connection_stats()
        print(f"Connection stats: {stats}")
        
        print("✅ WebSocket manager test complete")
    
    asyncio.run(test_websocket_manager())
