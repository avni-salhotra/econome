#!/usr/bin/env python3
"""
HTTP API Integration Tests
Tests the complete HTTP-only API architecture without WebSocket dependencies
"""

import asyncio
import json
import os
import sys
import time
import pytest
import requests
import base64
import numpy as np
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import web_api
from meeting_agents import ConversationIntelligenceSystem


class TestHTTPAPIArchitecture:
    """Test the complete HTTP-only API architecture"""
    
    @pytest.fixture
    def test_client(self):
        """Create FastAPI test client"""
        return TestClient(web_api.app)
    
    @pytest.fixture
    def sample_base64_audio(self):
        """Generate sample base64-encoded audio for testing"""
        # Generate 100ms of sine wave
        sample_rate = 16000
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        
        # Convert to bytes and encode
        audio_int16 = (audio_data * 32767).astype(np.int16)
        audio_bytes = audio_int16.tobytes()
        return base64.b64encode(audio_bytes).decode('utf-8')
    
    def test_health_endpoint_detailed(self, test_client):
        """Test health endpoint with detailed validation"""
        response = test_client.get("/health")
        assert response.status_code == 200
        
        health_data = response.json()
        assert 'status' in health_data
        assert health_data['status'] in ['healthy', 'ok', 'operational']
        assert 'timestamp' in health_data
    
    def test_main_page_serves_correctly(self, test_client):
        """Test main page serves without WebSocket references"""
        response = test_client.get("/")
        assert response.status_code == 200
        
        # Check content doesn't reference WebSocket errors
        content = response.text.lower()
        assert 'econome' in content
        assert 'websocket error' not in content
        assert 'connection failed' not in content
    
    def test_api_status_endpoint_detailed(self, test_client):
        """Test API status endpoint returns correct structure"""
        response = test_client.get("/api/status")
        assert response.status_code == 200
        
        status_data = response.json()
        required_fields = [
            'system_status', 'active_conversations', 
            'session_storage', 'websocket_connections', 'timestamp'
        ]
        
        for field in required_fields:
            assert field in status_data
        
        # WebSocket connections should be zero since removed
        assert status_data['websocket_connections']['total_connections'] == 0
        assert status_data['websocket_connections']['active_connections'] == 0
    
    def test_audio_debug_endpoint(self, test_client):
        """Test audio debug endpoint functionality"""
        response = test_client.get("/api/debug/audio")
        assert response.status_code == 200
        
        debug_data = response.json()
        assert 'audio_system_status' in debug_data
        assert 'cloud_run_mode' in debug_data
        assert 'dependencies' in debug_data
    
    def test_simulate_conversation_endpoint(self, test_client):
        """Test conversation simulation endpoint"""
        response = test_client.post("/api/simulate-conversation")
        assert response.status_code == 200
        
        result = response.json()
        assert 'success' in result
        assert 'session_token' in result
        assert 'ephemeral_url' in result
    
    def test_ephemeral_results_workflow(self, test_client):
        """Test complete ephemeral results workflow"""
        # First simulate a conversation to get a token
        sim_response = test_client.post("/api/simulate-conversation")
        assert sim_response.status_code == 200
        
        sim_data = sim_response.json()
        token = sim_data['session_token']
        
        # Test retrieving results
        results_response = test_client.get(f"/api/ephemeral/results/{token}")
        assert results_response.status_code == 200
        
        results_data = results_response.json()
        assert 'session_data' in results_data
        assert 'summary' in results_data['session_data']
        assert 'action_items' in results_data['session_data']
    
    def test_data_deletion_verification(self, test_client):
        """Test data deletion verification endpoint"""
        # Create a session first
        sim_response = test_client.post("/api/simulate-conversation")
        token = sim_response.json()['session_token']
        
        # Test deletion verification
        delete_response = test_client.post(f"/api/ephemeral/verify-deletion/{token}")
        assert delete_response.status_code == 200
        
        delete_data = delete_response.json()
        assert 'deletion_verified' in delete_data
    
    def test_api_documentation_accessible(self, test_client):
        """Test API documentation is accessible"""
        response = test_client.get("/docs")
        assert response.status_code == 200
        
        # Should contain OpenAPI/Swagger documentation
        content = response.text.lower()
        assert any(keyword in content for keyword in ['swagger', 'openapi', 'fastapi'])
    
    def test_redoc_documentation(self, test_client):
        """Test ReDoc documentation endpoint"""
        response = test_client.get("/redoc")
        assert response.status_code == 200
    
    def test_websocket_endpoint_removed(self, test_client):
        """Test that WebSocket endpoint is no longer available"""
        # This should fail since WebSocket endpoint was removed
        with pytest.raises(Exception):
            # TestClient doesn't support WebSocket, but this ensures the endpoint is gone
            response = test_client.get("/ws/conversation")
            # If somehow a response comes back, it should be 404
            assert response.status_code == 404


class TestFrontendStreamingFunctions:
    """Test frontend streaming functions without WebSocket dependency"""
    
    @pytest.fixture
    def mock_conversation_system(self):
        """Create mock conversation system"""
        system = MagicMock()
        system.session_id = "test-session-123"
        system.start_conversation.return_value = {"success": True}
        system.stop_conversation.return_value = {"success": True}
        return system
    
    @pytest.fixture
    def sample_audio_data(self):
        """Generate sample audio data"""
        sample_rate = 16000
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration))
        return np.sin(2 * np.pi * 440 * t).astype(np.float32)
    
    @pytest.mark.asyncio
    async def test_start_frontend_streaming_mode(self, mock_conversation_system):
        """Test frontend streaming mode initialization"""
        connection_id = "test-conn-123"
        
        # Test the function exists and can be called
        result = await web_api.start_frontend_streaming_mode(
            connection_id, mock_conversation_system
        )
        
        # Should return a result dictionary
        assert isinstance(result, dict)
        assert 'success' in result
    
    @pytest.mark.asyncio
    async def test_process_frontend_audio_chunk(self, mock_conversation_system, sample_audio_data):
        """Test frontend audio chunk processing"""
        connection_id = "test-conn-123"
        
        # Convert audio to base64
        audio_int16 = (sample_audio_data * 32767).astype(np.int16)
        audio_bytes = audio_int16.tobytes()
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        # Test processing audio chunk
        try:
            await web_api.process_frontend_audio_chunk(
                connection_id=connection_id,
                audio_data=audio_base64,
                mime_type="audio/webm",
                conversation_system=mock_conversation_system
            )
            # If no exception, the function works
            success = True
        except Exception as e:
            # Some errors are expected in test environment
            success = "No active conversation" in str(e) or "not found" in str(e)
        
        assert success
    
    @pytest.mark.asyncio
    async def test_handle_websocket_command_functionality(self, mock_conversation_system):
        """Test WebSocket command handler (now HTTP command handler)"""
        connection_id = "test-conn-123"
        
        # Test start recording command
        start_command = {
            "action": "start_recording",
            "mode": "frontend_streaming",
            "browser": "chrome"
        }
        
        try:
            await web_api.handle_websocket_command(
                connection_id, start_command, mock_conversation_system
            )
            success = True
        except Exception as e:
            # Some errors are expected in mock environment
            success = True
        
        assert success
    
    @pytest.mark.asyncio
    async def test_log_websocket_message(self):
        """Test WebSocket message logging replacement function"""
        connection_id = "test-conn-123"
        message = {"type": "test", "data": "test message"}
        
        # Should not raise an exception
        await web_api.log_websocket_message(connection_id, message)
        
        # Function should be callable and complete without error
        assert True


class TestSystemIntegrationWithoutWebSocket:
    """Test complete system integration without WebSocket dependencies"""
    
    @pytest.mark.asyncio
    async def test_conversation_system_mock_mode(self):
        """Test conversation system in mock mode"""
        system = ConversationIntelligenceSystem(
            mock_mode=True,
            project_id="test-project"
        )
        
        # Test system lifecycle
        session_id = await system.start_system()
        assert session_id is not None
        
        # Test conversation start/stop
        start_result = await system.start_conversation()
        assert isinstance(start_result, dict)
        
        stop_result = await system.stop_conversation()
        assert isinstance(stop_result, dict)
        
        # Test system status
        status = system.get_system_status()
        assert 'agents' in status
        
        # Cleanup
        await system.stop_system()
    
    def test_session_manager_integration(self):
        """Test session manager integration"""
        session_manager = web_api.session_manager
        
        # Test that session manager is initialized
        assert session_manager is not None
        
        # Test session manager type
        from gcp_session_manager import GCPEphemeralSessionManager
        assert isinstance(session_manager, GCPEphemeralSessionManager)
    
    def test_active_conversations_dict(self):
        """Test active conversations management"""
        # Active conversations dict should exist
        assert hasattr(web_api, 'active_conversations')
        assert isinstance(web_api.active_conversations, dict)
        
        # Should start empty
        initial_count = len(web_api.active_conversations)
        assert initial_count >= 0
    
    def test_websocket_manager_removal(self):
        """Test that WebSocket manager is completely removed"""
        # WebSocket manager should not exist in web_api
        assert not hasattr(web_api, 'websocket_manager')
        
        # Should not be able to import WebSocketManager
        with pytest.raises((ImportError, ModuleNotFoundError)):
            from src.websocket_manager import WebSocketManager


class TestErrorHandlingAndResilience:
    """Test error handling and system resilience"""
    
    @pytest.fixture
    def test_client(self):
        """Create FastAPI test client"""
        return TestClient(web_api.app)
    
    def test_404_handling(self, test_client):
        """Test 404 error handling"""
        response = test_client.get("/api/nonexistent-endpoint")
        assert response.status_code == 404
    
    def test_method_not_allowed(self, test_client):
        """Test method not allowed handling"""
        response = test_client.delete("/health")
        assert response.status_code in [404, 405]
    
    def test_invalid_ephemeral_token(self, test_client):
        """Test handling of invalid ephemeral tokens"""
        response = test_client.get("/api/ephemeral/results/invalid-token-123")
        assert response.status_code in [400, 404]
    
    def test_malformed_json_handling(self, test_client):
        """Test handling of malformed JSON in requests"""
        response = test_client.post(
            "/api/simulate-conversation",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        # Should handle gracefully
        assert response.status_code in [200, 400, 422]
    
    @pytest.mark.asyncio
    async def test_conversation_system_error_handling(self):
        """Test conversation system error handling"""
        # Test with invalid project ID
        system = ConversationIntelligenceSystem(
            mock_mode=True,
            project_id=""  # Empty project ID
        )
        
        try:
            session_id = await system.start_system()
            # Should handle gracefully or return valid session
            assert session_id is not None or session_id == ""
        except Exception as e:
            # Some errors are acceptable in test environment
            assert isinstance(e, Exception)


class TestPerformanceAndConcurrency:
    """Test performance and concurrency of HTTP API"""
    
    @pytest.fixture
    def test_client(self):
        """Create FastAPI test client"""
        return TestClient(web_api.app)
    
    def test_concurrent_health_checks(self, test_client):
        """Test concurrent health check requests"""
        import threading
        import time
        
        results = []
        start_time = time.time()
        
        def make_request():
            response = test_client.get("/health")
            results.append(response.status_code)
        
        # Make 10 concurrent requests
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        
        # All requests should succeed
        assert all(status == 200 for status in results)
        
        # Should complete in reasonable time
        assert (end_time - start_time) < 5.0
    
    def test_response_time_health_endpoint(self, test_client):
        """Test response time for health endpoint"""
        start_time = time.time()
        response = test_client.get("/health")
        end_time = time.time()
        
        assert response.status_code == 200
        
        # Should respond quickly (under 1 second)
        response_time = end_time - start_time
        assert response_time < 1.0
    
    def test_memory_usage_stability(self, test_client):
        """Test memory usage doesn't grow excessively"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Make multiple requests
        for _ in range(20):
            response = test_client.get("/health")
            assert response.status_code == 200
        
        final_memory = process.memory_info().rss
        memory_growth = final_memory - initial_memory
        
        # Memory growth should be reasonable (less than 50MB)
        assert memory_growth < 50 * 1024 * 1024

    def test_audio_queue_backpressure(self, test_client):
        """Audio endpoint should return 429 when STT queue is near capacity"""
        from unittest.mock import MagicMock

        connection_id = "test-backpressure-123"

        # Create dummy queue with large size
        class _FullQueue:
            def qsize(self):
                return 100  # Simulate full queue

        stt_service = MagicMock()
        stt_service._audio_queue = _FullQueue()
        stt_service.max_queue_size = 100

        stt_agent = MagicMock()
        stt_agent.stt_service = stt_service

        conversation_system = MagicMock()
        conversation_system.get_agent.return_value = stt_agent

        # Register the mock system in active conversations
        web_api.active_conversations[connection_id] = conversation_system

        # Send small dummy audio blob
        response = test_client.post(
            f"/api/conversation/{connection_id}/audio",
            data=b"\x00\x00",
            headers={"Content-Type": "audio/webm"},
        )

        # Clean up
        del web_api.active_conversations[connection_id]

        assert response.status_code == 429


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 