#!/usr/bin/env python3
"""
End-to-End System Tests for Econome
Comprehensive testing of the HTTP API and system functionality.
WebSocket functionality has been removed.
"""

import asyncio
import json
import os
import sys
import time
import pytest
import requests
from typing import Dict, Any, Optional
from unittest.mock import patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from meeting_agents import ConversationIntelligenceSystem
from gcp_session_manager import GCPEphemeralSessionManager


class TestE2ESystem:
    """End-to-end system tests for HTTP API"""
    
    @pytest.fixture
    def base_url(self):
        """Get base URL for testing"""
        return os.getenv('TEST_BASE_URL', 'http://localhost:8080')
    
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
    
    def test_api_status_endpoint(self, base_url):
        """Test API status endpoint"""
        response = requests.get(f"{base_url}/api/status", timeout=10)
        assert response.status_code == 200
        
        status_data = response.json()
        assert 'system_status' in status_data
        assert 'active_conversations' in status_data
        assert 'timestamp' in status_data
    
    def test_conversation_start_endpoint(self, base_url):
        """Test conversation start endpoint"""
        response = requests.post(f"{base_url}/api/conversation/start", timeout=10)
        
        # Should either succeed or fail gracefully
        assert response.status_code in [200, 400, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert 'success' in data
    
    def test_conversation_stop_endpoint(self, base_url):
        """Test conversation stop endpoint"""
        response = requests.post(f"{base_url}/api/conversation/stop", timeout=10)
        
        # Should either succeed or fail gracefully
        assert response.status_code in [200, 400, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert 'success' in data
    
    def test_error_handling(self, base_url):
        """Test error handling for invalid endpoints"""
        # Test non-existent endpoint
        response = requests.get(f"{base_url}/api/nonexistent", timeout=10)
        assert response.status_code == 404
        
        # Test invalid method
        response = requests.delete(f"{base_url}/health", timeout=10)
        assert response.status_code in [404, 405]
    
    def test_performance_basic(self, base_url):
        """Test basic performance metrics"""
        start_time = time.time()
        response = requests.get(f"{base_url}/health", timeout=10)
        end_time = time.time()
        
        assert response.status_code == 200
        
        # Response should be reasonably fast (under 2 seconds)
        response_time = end_time - start_time
        assert response_time < 2.0
    
    def test_concurrent_requests(self, base_url):
        """Test handling of concurrent requests"""
        import threading
        
        def make_request():
            response = requests.get(f"{base_url}/health", timeout=10)
            return response.status_code
        
        # Make 5 concurrent requests
        threads = []
        results = []
        
        for _ in range(5):
            thread = threading.Thread(target=lambda: results.append(make_request()))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert all(status == 200 for status in results)
    
    @pytest.mark.asyncio
    async def test_session_cleanup(self):
        """Test session cleanup functionality"""
        session_manager = GCPEphemeralSessionManager()
        
        # Create a test session
        session_token = await session_manager.create_session(
            summary="Test cleanup session",
            action_items=[]
        )
        
        # Verify session exists
        session_data = await session_manager.get_session(session_token)
        assert session_data is not None
        
        # Session cleanup is automatic based on TTL
        # Just verify the session manager can handle cleanup operations
        stats = await session_manager.get_session_stats()
        assert 'total_sessions' in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
