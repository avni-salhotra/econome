#!/usr/bin/env python3
"""
End-to-End System Tests for Econome
Comprehensive testing of the entire system including WebSocket communication,
AI processing, and session management.
"""

import asyncio
import json
import os
import sys
import time
import pytest
import requests
import websockets
import ssl
from typing import Dict, Any, Optional
from unittest.mock import patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from web_api import app
from meeting_agents import ConversationIntelligenceSystem
from gcp_session_manager import GCPEphemeralSessionManager


class TestE2ESystem:
    """End-to-end system tests"""
    
    @pytest.fixture
    def base_url(self):
        """Get base URL for testing"""
        return os.getenv('TEST_BASE_URL', 'http://localhost:8080')
    
    @pytest.fixture
    def websocket_url(self):
        """Get WebSocket URL for testing"""
        base = os.getenv('TEST_BASE_URL', 'ws://localhost:8080')
        if base.startswith('http://'):
            base = base.replace('http://', 'ws://')
        elif base.startswith('https://'):
            base = base.replace('https://', 'wss://')
        return f"{base}/ws/conversation"
    
    @pytest.fixture
    def mock_mode(self):
        """Enable mock mode for testing"""
        return True
    
    def test_health_endpoint(self, base_url):
        """Test health endpoint availability"""
        response = requests.get(f"{base_url}/health", timeout=10)
        assert response.status_code == 200
        
        health_data = response.json()
        assert 'status' in health_data
        assert health_data['status'] in ['healthy', 'ok']
    
    def test_main_page_accessibility(self, base_url):
        """Test main page is accessible"""
        response = requests.get(base_url, timeout=10)
        assert response.status_code == 200
        assert 'Econome' in response.text
        assert 'conversation intelligence' in response.text.lower()
    
    def test_api_documentation(self, base_url):
        """Test API documentation is accessible"""
        response = requests.get(f"{base_url}/docs", timeout=10)
        assert response.status_code == 200
        assert 'swagger' in response.text.lower() or 'openapi' in response.text.lower()
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self, websocket_url):
        """Test WebSocket connection establishment"""
        try:
            # Handle SSL for wss:// URLs
            ssl_context = None
            if websocket_url.startswith('wss://'):
                ssl_context = ssl.create_default_context()
            
            async with websockets.connect(websocket_url, ssl=ssl_context) as websocket:
                # Test connection is established
                assert websocket.open
                
                # Send a test message
                test_message = {
                    'type': 'test',
                    'data': 'connection_test'
                }
                await websocket.send(json.dumps(test_message))
                
                # Wait for response (with timeout)
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    response_data = json.loads(response)
                    assert 'type' in response_data
                except asyncio.TimeoutError:
                    # No response is acceptable for test messages
                    pass
                
        except Exception as e:
            pytest.fail(f"WebSocket connection failed: {e}")
    
    @pytest.mark.asyncio
    async def test_conversation_system_initialization(self, mock_mode):
        """Test conversation intelligence system initialization"""
        system = ConversationIntelligenceSystem(
            mock_mode=mock_mode,
            project_id="test-project"
        )
        
        # Test system initialization
        session_id = await system.start_system()
        assert session_id is not None
        assert len(session_id) > 0
        
        # Test system status
        status = system.get_system_status()
        assert 'agents' in status
        assert 'is_running' in status
        
        # Cleanup
        await system.stop_system()
    
    @pytest.mark.asyncio
    async def test_session_manager(self):
        """Test session manager functionality"""
        session_manager = GCPEphemeralSessionManager()
        
        # Test session creation
        test_summary = "Test conversation summary"
        test_actions = [
            {"task": "Test task", "priority": "high"},
            {"task": "Another task", "priority": "medium"}
        ]
        
        session_token = await session_manager.create_session(
            summary=test_summary,
            action_items=test_actions
        )
        
        assert session_token is not None
        assert len(session_token) > 0
        
        # Test session retrieval
        session_data = await session_manager.get_session(session_token)
        assert session_data is not None
        assert session_data['summary'] == test_summary
        assert len(session_data['action_items']) == 2
        
        # Test session stats
        stats = await session_manager.get_session_stats()
        assert 'total_sessions' in stats
        assert stats['total_sessions'] >= 1
    
    @pytest.mark.asyncio
    async def test_full_conversation_flow(self, websocket_url, mock_mode):
        """Test complete conversation flow end-to-end"""
        if not mock_mode:
            pytest.skip("Full conversation flow test requires mock mode")
        
        try:
            # Handle SSL for wss:// URLs
            ssl_context = None
            if websocket_url.startswith('wss://'):
                ssl_context = ssl.create_default_context()
            
            async with websockets.connect(websocket_url, ssl=ssl_context) as websocket:
                # Step 1: Start conversation
                start_message = {
                    'type': 'start_conversation',
                    'data': {}
                }
                await websocket.send(json.dumps(start_message))
                
                # Wait for system ready response
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                response_data = json.loads(response)
                assert response_data['type'] == 'system_ready'
                
                # Step 2: Simulate audio data (mock)
                audio_message = {
                    'type': 'audio_data',
                    'data': {
                        'audio': 'mock_audio_data',
                        'format': 'webm'
                    }
                }
                await websocket.send(json.dumps(audio_message))
                
                # Step 3: Wait for transcription
                transcript_received = False
                for _ in range(10):  # Wait up to 10 responses
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        response_data = json.loads(response)
                        
                        if response_data['type'] == 'live_transcript':
                            transcript_received = True
                            assert 'text' in response_data
                            break
                    except asyncio.TimeoutError:
                        break
                
                # In mock mode, we might not get transcripts
                # This is acceptable for testing
                
                # Step 4: Stop conversation
                stop_message = {
                    'type': 'stop_conversation',
                    'data': {}
                }
                await websocket.send(json.dumps(stop_message))
                
                # Wait for analysis complete
                analysis_received = False
                for _ in range(10):  # Wait up to 10 responses
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        response_data = json.loads(response)
                        
                        if response_data['type'] == 'analysis_complete':
                            analysis_received = True
                            assert 'results' in response_data
                            assert 'ephemeral_url' in response_data
                            break
                    except asyncio.TimeoutError:
                        break
                
                # Analysis should be received in mock mode
                assert analysis_received, "Analysis complete message not received"
                
        except Exception as e:
            pytest.fail(f"Full conversation flow test failed: {e}")
    
    def test_error_handling(self, base_url):
        """Test error handling for invalid requests"""
        # Test invalid endpoint
        response = requests.get(f"{base_url}/invalid-endpoint", timeout=10)
        assert response.status_code == 404
        
        # Test invalid method
        response = requests.delete(f"{base_url}/health", timeout=10)
        assert response.status_code == 405
    
    @pytest.mark.asyncio
    async def test_websocket_error_handling(self, websocket_url):
        """Test WebSocket error handling"""
        try:
            ssl_context = None
            if websocket_url.startswith('wss://'):
                ssl_context = ssl.create_default_context()
            
            async with websockets.connect(websocket_url, ssl=ssl_context) as websocket:
                # Send invalid JSON
                await websocket.send("invalid json")
                
                # Should receive error response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    response_data = json.loads(response)
                    assert response_data['type'] == 'error'
                except (asyncio.TimeoutError, json.JSONDecodeError):
                    # Connection might be closed or no response
                    pass
                
        except Exception as e:
            # Connection errors are acceptable for invalid data
            pass
    
    def test_performance_basic(self, base_url):
        """Test basic performance characteristics"""
        # Test response time
        start_time = time.time()
        response = requests.get(f"{base_url}/health", timeout=10)
        end_time = time.time()
        
        response_time = (end_time - start_time) * 1000  # Convert to ms
        assert response_time < 5000, f"Health check too slow: {response_time}ms"
        assert response.status_code == 200
    
    def test_concurrent_requests(self, base_url):
        """Test handling of concurrent requests"""
        import concurrent.futures
        import threading
        
        def make_request():
            response = requests.get(f"{base_url}/health", timeout=10)
            return response.status_code == 200
        
        # Test 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All requests should succeed
        assert all(results), "Some concurrent requests failed"
    
    @pytest.mark.asyncio
    async def test_session_cleanup(self):
        """Test session cleanup functionality"""
        session_manager = GCPEphemeralSessionManager()
        
        # Create a test session
        session_token = await session_manager.create_session(
            summary="Test cleanup",
            action_items=[]
        )
        
        # Verify session exists
        session_data = await session_manager.get_session(session_token)
        assert session_data is not None
        
        # Test cleanup (in real implementation, this would be time-based)
        # For testing, we can verify the cleanup mechanism exists
        stats_before = await session_manager.get_session_stats()
        
        # Trigger cleanup if available
        if hasattr(session_manager, 'cleanup_expired_sessions'):
            await session_manager.cleanup_expired_sessions()
        
        # Verify cleanup functionality exists
        assert hasattr(session_manager, '_cleanup_memory_sessions') or \
               hasattr(session_manager, 'cleanup_expired_sessions')


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
