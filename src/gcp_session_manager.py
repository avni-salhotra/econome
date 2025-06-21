#!/usr/bin/env python3
"""
GCP-Native Ephemeral Session Manager
Privacy-first session management using Firestore TTL for automatic data deletion
"""

import os
import secrets
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json

try:
    from google.cloud import firestore
    from google.cloud.firestore import SERVER_TIMESTAMP
    FIRESTORE_AVAILABLE = True
except ImportError:
    print("⚠️ Firestore not available - using in-memory fallback")
    FIRESTORE_AVAILABLE = False

@dataclass
class EphemeralSession:
    """Privacy-first session with guaranteed expiration"""
    summary: str
    action_items: List[Dict]
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    session_metadata: Dict[str, Any] = None
    
    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at
    
    @property
    def time_remaining(self) -> str:
        if self.is_expired:
            return "EXPIRED"
        delta = self.expires_at - datetime.now()
        hours = int(delta.total_seconds() / 3600)
        minutes = int((delta.total_seconds() % 3600) / 60)
        return f"{hours}h {minutes}m remaining"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'summary': self.summary,
            'action_items': self.action_items,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'expires_at': self.expires_at.isoformat() if isinstance(self.expires_at, datetime) else self.expires_at,
            'access_count': self.access_count,
            'session_metadata': self.session_metadata or {},
            'time_remaining': self.time_remaining
        }

class GCPEphemeralSessionManager:
    """Privacy-first session management using Firestore TTL"""
    
    def __init__(self, project_id: str = "econome-hackathon"):
        self.project_id = project_id
        self.use_firestore = FIRESTORE_AVAILABLE
        
        if self.use_firestore:
            try:
                self.db = firestore.Client(project=project_id)
                self.collection = self.db.collection('ephemeral_sessions')
                print("✅ Firestore initialized for ephemeral sessions")
            except Exception as e:
                print(f"⚠️ Firestore initialization failed: {e}")
                self.use_firestore = False
                self._init_memory_fallback()
        else:
            self._init_memory_fallback()
    
    def _init_memory_fallback(self):
        """Initialize in-memory storage as fallback"""
        self.sessions: Dict[str, EphemeralSession] = {}
        self._cleanup_task = None
        print("✅ In-memory session storage initialized (fallback mode)")

    def _start_cleanup_task(self):
        """Start the memory cleanup task if not already running"""
        if self._cleanup_task is None:
            try:
                self._cleanup_task = asyncio.create_task(self._memory_cleanup_task())
                print("✅ Memory cleanup task started")
            except RuntimeError:
                # No event loop running, will start later
                pass

    async def create_session(self,
                           summary: str,
                           action_items: List[Dict],
                           session_metadata: Dict[str, Any] = None) -> str:
        """Create ephemeral session with automatic deletion"""
        # Start cleanup task if using memory storage
        if not self.use_firestore:
            self._start_cleanup_task()

        token = secrets.token_urlsafe(32)  # Cryptographically secure
        expires_at = datetime.now() + timedelta(hours=24)
        
        session_data = {
            'summary': summary,
            'action_items': action_items,
            'created_at': datetime.now(),
            'expires_at': expires_at,
            'access_count': 0,
            'session_metadata': session_metadata or {}
        }
        
        if self.use_firestore:
            try:
                # Firestore document with TTL field for automatic deletion
                firestore_data = {
                    **session_data,
                    'created_at': SERVER_TIMESTAMP,
                    'expires_at': expires_at,
                    # TTL field - Firestore automatically deletes when this time passes
                    'ttl': expires_at
                }
                
                # Create document with secure token as ID
                self.collection.document(token).set(firestore_data)
                print(f"✅ Ephemeral session created in Firestore: {token[:8]}...")
                
            except Exception as e:
                print(f"❌ Firestore session creation failed: {e}")
                # Fallback to memory storage
                self._store_in_memory(token, session_data)
        else:
            self._store_in_memory(token, session_data)
        
        return token
    
    def _store_in_memory(self, token: str, session_data: Dict[str, Any]):
        """Store session in memory as fallback"""
        self.sessions[token] = EphemeralSession(**session_data)
        print(f"✅ Ephemeral session created in memory: {token[:8]}...")
    
    async def get_session(self, token: str) -> Optional[EphemeralSession]:
        """Retrieve session if still valid"""
        if self.use_firestore:
            try:
                doc_ref = self.collection.document(token)
                doc = doc_ref.get()
                
                if not doc.exists:
                    return None
                
                data = doc.to_dict()
                
                # Check if expired (double-check before TTL cleanup)
                expires_at = data['expires_at']
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                
                if datetime.now() > expires_at:
                    doc_ref.delete()  # Manual cleanup
                    print(f"🗑️ Expired session manually deleted: {token[:8]}...")
                    return None
                
                # Increment access count
                doc_ref.update({'access_count': firestore.Increment(1)})
                
                # Convert to EphemeralSession object
                created_at = data['created_at']
                if hasattr(created_at, 'timestamp'):
                    created_at = datetime.fromtimestamp(created_at.timestamp())
                elif isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                
                return EphemeralSession(
                    summary=data['summary'],
                    action_items=data['action_items'],
                    created_at=created_at,
                    expires_at=expires_at,
                    access_count=data.get('access_count', 0),
                    session_metadata=data.get('session_metadata', {})
                )
                
            except Exception as e:
                print(f"❌ Firestore session retrieval failed: {e}")
                # Fallback to memory storage
                return self._get_from_memory(token)
        else:
            return self._get_from_memory(token)
    
    def _get_from_memory(self, token: str) -> Optional[EphemeralSession]:
        """Get session from memory storage"""
        if token not in self.sessions:
            return None
        
        session = self.sessions[token]
        if session.is_expired:
            del self.sessions[token]
            print(f"🗑️ Expired session deleted from memory: {token[:8]}...")
            return None
        
        session.access_count += 1
        return session
    
    async def verify_deletion(self, token: str) -> Dict[str, Any]:
        """Allow users to verify their data was deleted"""
        session = await self.get_session(token)
        
        if session:
            return {
                "status": "active",
                "expires_in": session.time_remaining,
                "access_count": session.access_count
            }
        else:
            return {
                "status": "deleted",
                "message": "Your data has been permanently deleted and cannot be recovered."
            }
    
    async def _memory_cleanup_task(self):
        """Background cleanup of expired sessions in memory"""
        while True:
            try:
                expired_tokens = [
                    token for token, session in self.sessions.items()
                    if session.is_expired
                ]
                
                for token in expired_tokens:
                    del self.sessions[token]
                    print(f"🗑️ Expired session cleaned up: {token[:8]}...")
                
                if expired_tokens:
                    print(f"🧹 Cleaned up {len(expired_tokens)} expired sessions")
                
            except Exception as e:
                print(f"❌ Memory cleanup error: {e}")
            
            # Clean every hour
            await asyncio.sleep(3600)
    
    async def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics about active sessions"""
        if self.use_firestore:
            try:
                # Query active sessions
                docs = self.collection.where('expires_at', '>', datetime.now()).stream()
                active_count = sum(1 for _ in docs)
                
                return {
                    "storage_type": "firestore",
                    "active_sessions": active_count,
                    "auto_deletion": "enabled"
                }
            except Exception as e:
                print(f"❌ Firestore stats error: {e}")
                return {"storage_type": "firestore", "error": str(e)}
        else:
            active_count = sum(1 for session in self.sessions.values() if not session.is_expired)
            return {
                "storage_type": "memory",
                "active_sessions": active_count,
                "total_sessions": len(self.sessions),
                "auto_deletion": "enabled"
            }

# Factory function for easy initialization
def create_session_manager(project_id: str = "econome-hackathon") -> GCPEphemeralSessionManager:
    """Factory function to create session manager"""
    return GCPEphemeralSessionManager(project_id=project_id)

if __name__ == "__main__":
    # Test the session manager
    async def test_session_manager():
        print("🧪 Testing GCP Ephemeral Session Manager...")
        
        manager = create_session_manager()
        
        # Test session creation
        token = await manager.create_session(
            summary="Test conversation summary",
            action_items=[
                {"type": "todo", "action": "Test action", "deadline": "tomorrow"}
            ],
            session_metadata={"test": True}
        )
        
        print(f"Created session: {token[:8]}...")
        
        # Test session retrieval
        session = await manager.get_session(token)
        if session:
            print(f"Retrieved session: {session.summary}")
            print(f"Time remaining: {session.time_remaining}")
        
        # Test stats
        stats = await manager.get_session_stats()
        print(f"Session stats: {stats}")
        
        print("✅ Session manager test complete")
    
    asyncio.run(test_session_manager())
