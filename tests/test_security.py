#!/usr/bin/env python3
"""
Security Tests for Econome
Comprehensive security testing including input validation,
authentication, and data protection.
"""

import os
import sys
import json
import pytest
import requests
import asyncio
# WebSocket functionality removed - security tests updated for HTTP-only API
from unittest.mock import patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestSecurity:
    """Security-focused tests"""
    
    @pytest.fixture
    def base_url(self):
        """Get base URL for testing"""
        return os.getenv('TEST_BASE_URL', 'http://localhost:8080')
    
    # WebSocket functionality removed - no longer needed
    
    def test_no_hardcoded_secrets(self):
        """Test that no hardcoded secrets exist in the codebase"""
        import glob
        
        # Patterns that might indicate hardcoded secrets
        secret_patterns = [
            'sk-',  # OpenAI API keys
            'AIza',  # Google API keys
            'AKIA',  # AWS access keys
            'password',
            'secret',
            'token',
            'key'
        ]
        
        # Files to check
        python_files = glob.glob('../src/**/*.py', recursive=True)
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                    
                    # Skip checking for common variable names in comments
                    lines = content.split('\n')
                    for line_num, line in enumerate(lines, 1):
                        line = line.strip()
                        
                        # Skip comments and docstrings
                        if line.startswith('#') or line.startswith('"""') or line.startswith("'''"):
                            continue
                        
                        # Check for potential secrets
                        for pattern in secret_patterns:
                            if pattern in line and '=' in line:
                                # Check if it's actually a hardcoded value
                                if any(suspicious in line for suspicious in ['"sk-', "'sk-", '"AIza', "'AIza"]):
                                    pytest.fail(f"Potential hardcoded secret in {file_path}:{line_num}: {line}")
            except Exception:
                # Skip files that can't be read
                continue
    
    # WebSocket input validation test removed - functionality no longer exists
    
    def test_http_security_headers(self, base_url):
        """Test HTTP security headers"""
        response = requests.get(base_url, timeout=10)
        
        # Check for security headers (if implemented)
        headers = response.headers
        
        # These are recommended but not required for this application
        security_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options',
            'X-XSS-Protection',
            'Strict-Transport-Security',
            'Content-Security-Policy'
        ]
        
        # Log which headers are present (for informational purposes)
        present_headers = [h for h in security_headers if h in headers]
        missing_headers = [h for h in security_headers if h not in headers]
        
        print(f"Present security headers: {present_headers}")
        print(f"Missing security headers: {missing_headers}")
        
        # For now, just ensure the response is valid
        assert response.status_code == 200
    
    def test_cors_configuration(self, base_url):
        """Test CORS configuration"""
        # Test preflight request
        headers = {
            'Origin': 'https://example.com',
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'Content-Type'
        }
        
        response = requests.options(base_url, headers=headers, timeout=10)
        
        # CORS should be configured appropriately
        # For a public application, some CORS headers are expected
        if 'Access-Control-Allow-Origin' in response.headers:
            cors_origin = response.headers['Access-Control-Allow-Origin']
            # Should not be overly permissive in production
            if os.getenv('ENVIRONMENT') == 'production':
                assert cors_origin != '*' or cors_origin.startswith('https://')
    
    def test_sql_injection_protection(self, base_url):
        """Test SQL injection protection (if applicable)"""
        # Since this application doesn't use SQL directly,
        # test that malicious inputs don't cause issues
        
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "' UNION SELECT * FROM users --"
        ]
        
        for malicious_input in malicious_inputs:
            # Test in query parameters
            response = requests.get(
                f"{base_url}/health",
                params={'test': malicious_input},
                timeout=10
            )
            
            # Should not cause server errors
            assert response.status_code in [200, 400, 404]
            
            # Response should not contain SQL error messages
            response_text = response.text.lower()
            sql_error_indicators = ['sql', 'syntax error', 'mysql', 'postgresql']
            for indicator in sql_error_indicators:
                assert indicator not in response_text
    
    def test_xss_protection(self, base_url):
        """Test XSS protection"""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "';alert('xss');//"
        ]
        
        for payload in xss_payloads:
            # Test in query parameters
            response = requests.get(
                f"{base_url}/health",
                params={'test': payload},
                timeout=10
            )
            
            # Should not execute scripts or return unescaped content
            assert response.status_code in [200, 400, 404]
            
            # Response should not contain unescaped script tags
            response_text = response.text
            assert '<script>' not in response_text
            assert 'javascript:' not in response_text
    
    def test_file_upload_security(self, base_url):
        """Test file upload security (if applicable)"""
        # Test malicious file uploads
        malicious_files = [
            ('test.php', b'<?php system($_GET["cmd"]); ?>'),
            ('test.jsp', b'<% Runtime.getRuntime().exec(request.getParameter("cmd")); %>'),
            ('test.exe', b'MZ\x90\x00'),  # PE header
        ]
        
        for filename, content in malicious_files:
            files = {'file': (filename, content)}
            
            # Try to upload to common endpoints
            upload_endpoints = ['/upload', '/api/upload', '/files']
            
            for endpoint in upload_endpoints:
                try:
                    response = requests.post(
                        f"{base_url}{endpoint}",
                        files=files,
                        timeout=10
                    )
                    
                    # Should reject malicious files or endpoint should not exist
                    assert response.status_code in [400, 404, 405, 413]
                    
                except requests.exceptions.RequestException:
                    # Connection errors are acceptable
                    pass
    
    def test_rate_limiting(self, base_url):
        """Test rate limiting (if implemented)"""
        # Make rapid requests to test rate limiting
        responses = []
        
        for i in range(20):
            try:
                response = requests.get(f"{base_url}/health", timeout=5)
                responses.append(response.status_code)
            except requests.exceptions.RequestException:
                # Timeouts or connection errors might indicate rate limiting
                responses.append(429)
        
        # Check if any rate limiting is in place
        rate_limited = any(status == 429 for status in responses)
        
        # Rate limiting is optional but good to have
        print(f"Rate limiting detected: {rate_limited}")
        
        # Ensure at least some requests succeed
        successful_requests = sum(1 for status in responses if status == 200)
        assert successful_requests > 0
    
    def test_information_disclosure(self, base_url):
        """Test for information disclosure"""
        # Test error pages don't reveal sensitive information
        error_endpoints = [
            '/nonexistent',
            '/admin',
            '/config',
            '/debug',
            '/.env',
            '/secrets'
        ]
        
        for endpoint in error_endpoints:
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            
            # Should not reveal sensitive information
            response_text = response.text.lower()
            
            sensitive_info = [
                'password',
                'secret',
                'key',
                'token',
                'database',
                'connection string',
                'stack trace',
                'traceback'
            ]
            
            for info in sensitive_info:
                assert info not in response_text, f"Sensitive info '{info}' found in {endpoint}"
    
    def test_session_security(self):
        """Test session security"""
        # Test session token generation
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        
        try:
            from gcp_session_manager import GCPEphemeralSessionManager
            
            session_manager = GCPEphemeralSessionManager()
            
            # Generate multiple session tokens
            tokens = []
            for _ in range(10):
                # Use async context for testing
                async def create_test_session():
                    return await session_manager.create_session(
                        summary="Test",
                        action_items=[]
                    )
                
                token = asyncio.run(create_test_session())
                tokens.append(token)
            
            # Tokens should be unique
            assert len(set(tokens)) == len(tokens), "Session tokens are not unique"
            
            # Tokens should be sufficiently long
            for token in tokens:
                assert len(token) >= 16, f"Session token too short: {token}"
                
                # Tokens should not be predictable
                assert not token.isdigit(), "Session token is only digits"
                assert token != "test", "Session token is predictable"
                
        except ImportError:
            # Skip if session manager not available
            pytest.skip("Session manager not available for testing")
    
    def test_environment_variable_security(self):
        """Test environment variable security"""
        # Check that sensitive environment variables are not exposed
        import os
        
        # These should not be set in test environment
        sensitive_env_vars = [
            'GOOGLE_APPLICATION_CREDENTIALS',
            'GCP_CREDENTIALS',
            'SECRET_KEY',
            'DATABASE_PASSWORD'
        ]
        
        for var in sensitive_env_vars:
            value = os.getenv(var)
            if value:
                # Should not contain obvious secrets
                assert not value.startswith('sk-'), f"{var} contains potential API key"
                assert not value.startswith('AIza'), f"{var} contains potential Google API key"
                
                # Should not be a file path in test environment
                if var.endswith('_CREDENTIALS'):
                    # In test environment, should be mock or empty
                    assert value in ['mock', 'test', ''] or 'test' in value.lower()


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
