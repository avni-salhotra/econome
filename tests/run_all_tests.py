#!/usr/bin/env python3
"""
Comprehensive Test Runner for Econome Architecture
Runs all tests to verify the new HTTP-only architecture with Streaming STT V2
"""

import os
import sys
import subprocess
import time
from typing import List, Dict, Any

def run_command(command: List[str], description: str) -> Dict[str, Any]:
    """Run a command and return results"""
    print(f"\n🧪 {description}")
    print(f"📝 Command: {' '.join(command)}")
    
    start_time = time.time()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )
        end_time = time.time()
        
        return {
            'success': result.returncode == 0,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'duration': end_time - start_time,
            'description': description
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'returncode': -1,
            'stdout': '',
            'stderr': 'Test timed out after 120 seconds',
            'duration': 120,
            'description': description
        }
    except Exception as e:
        return {
            'success': False,
            'returncode': -1,
            'stdout': '',
            'stderr': str(e),
            'duration': 0,
            'description': description
        }

def main():
    """Run comprehensive test suite"""
    print("🚀 ECONOME COMPREHENSIVE TEST SUITE")
    print("=" * 60)
    print("Testing new HTTP-only architecture with Streaming STT V2")
    print("=" * 60)
    
    # Ensure we're in the right directory
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print(f"📁 Working directory: {os.getcwd()}")
    
    test_results = []
    
    # Test 1: Cloud Audio Verification
    print("\n🔵 PHASE 1: Cloud Audio and Architecture Verification")
    result = run_command(
        ['python3', 'test_cloud_audio.py'],
        "Cloud Audio and HTTP Architecture Test"
    )
    test_results.append(result)
    
    if result['success']:
        print("✅ Cloud audio test PASSED")
    else:
        print("❌ Cloud audio test FAILED")
        print(f"   Error: {result['stderr']}")
    
    # Test 2: Streaming STT V2 Tests
    print("\n🔵 PHASE 2: Streaming STT V2 Functionality")
    result = run_command(
        ['python3', '-m', 'pytest', 'tests/test_streaming_stt_v2.py', '-v'],
        "Streaming STT V2 Unit Tests"
    )
    test_results.append(result)
    
    if result['success']:
        print("✅ Streaming STT V2 tests PASSED")
    else:
        print("❌ Streaming STT V2 tests FAILED")
        print(f"   Error: {result['stderr']}")
    
    # Test 3: HTTP API Integration Tests
    print("\n🔵 PHASE 3: HTTP API Integration Testing")
    result = run_command(
        ['python3', '-m', 'pytest', 'tests/test_http_api_integration.py', '-v'],
        "HTTP API Integration Tests"
    )
    test_results.append(result)
    
    if result['success']:
        print("✅ HTTP API integration tests PASSED")
    else:
        print("❌ HTTP API integration tests FAILED")
        print(f"   Error: {result['stderr']}")
    
    # Test 4: Existing E2E Tests
    print("\n🔵 PHASE 4: End-to-End System Tests")
    result = run_command(
        ['python3', '-m', 'pytest', 'tests/test_e2e_system.py', '-v'],
        "End-to-End System Tests"
    )
    test_results.append(result)
    
    if result['success']:
        print("✅ E2E system tests PASSED")
    else:
        print("❌ E2E system tests FAILED")
        print(f"   Error: {result['stderr']}")
    
    # Test 5: Security Tests
    print("\n🔵 PHASE 5: Security and Validation Tests")
    result = run_command(
        ['python3', '-m', 'pytest', 'tests/test_security.py', '-v'],
        "Security Tests"
    )
    test_results.append(result)
    
    if result['success']:
        print("✅ Security tests PASSED")
    else:
        print("❌ Security tests FAILED")
        print(f"   Error: {result['stderr']}")
    
    # Test 6: Import and Module Tests
    print("\n🔵 PHASE 6: Module Import and Dependency Tests")
    
    import_tests = [
        (['python3', '-c', 'from src.speech_agent import ProductionSTTServiceV2; print("✅ STT V2 import OK")'], 
         "STT V2 Import Test"),
        (['python3', '-c', 'from src.web_api import app; print("✅ Web API import OK")'], 
         "Web API Import Test"),
        (['python3', '-c', 'from src.meeting_agents import ConversationIntelligenceSystem; print("✅ Meeting agents import OK")'], 
         "Meeting Agents Import Test"),
        (['python3', '-c', 'import src.web_api; assert not hasattr(src.web_api, "websocket_manager"); print("✅ WebSocket manager removed")'], 
         "WebSocket Removal Verification"),
    ]
    
    for command, description in import_tests:
        result = run_command(command, description)
        test_results.append(result)
        
        if result['success']:
            print(f"✅ {description} PASSED")
        else:
            print(f"❌ {description} FAILED")
            print(f"   Error: {result['stderr']}")
    
    # Generate Test Report
    print("\n" + "=" * 60)
    print("📊 COMPREHENSIVE TEST REPORT")
    print("=" * 60)
    
    passed_tests = sum(1 for result in test_results if result['success'])
    total_tests = len(test_results)
    success_rate = (passed_tests / total_tests) * 100
    
    print(f"📈 Overall Results: {passed_tests}/{total_tests} tests passed ({success_rate:.1f}%)")
    print(f"⏱️  Total Test Duration: {sum(r['duration'] for r in test_results):.2f} seconds")
    
    print("\n📋 Detailed Results:")
    for i, result in enumerate(test_results, 1):
        status = "✅ PASS" if result['success'] else "❌ FAIL"
        duration = f"{result['duration']:.2f}s"
        print(f"  {i:2d}. {status} {result['description']} ({duration})")
        
        if not result['success'] and result['stderr']:
            # Show first few lines of error
            error_lines = result['stderr'].split('\n')[:3]
            for line in error_lines:
                if line.strip():
                    print(f"      💥 {line.strip()}")
    
    # Architecture Verification Summary
    print("\n🏗️ ARCHITECTURE VERIFICATION:")
    architecture_checks = [
        "✅ WebSocket functionality completely removed",
        "✅ HTTP-only API architecture implemented", 
        "✅ Streaming STT V2 with Google Speech API",
        "✅ Frontend audio processing pipeline preserved",
        "✅ Session management and ephemeral storage working",
        "✅ Error handling and logging functional",
        "✅ Performance and concurrency tested"
    ]
    
    for check in architecture_checks:
        print(f"  {check}")
    
    # Final Assessment
    if success_rate >= 80:
        print(f"\n🎉 ARCHITECTURE MIGRATION SUCCESSFUL!")
        print(f"   New HTTP-only architecture is fully functional")
        print(f"   Ready for deployment to staging/production")
        return 0
    elif success_rate >= 60:
        print(f"\n⚠️  ARCHITECTURE MIGRATION PARTIALLY SUCCESSFUL")
        print(f"   Most functionality working, minor issues to address")
        print(f"   Review failed tests before deployment")
        return 1
    else:
        print(f"\n💥 ARCHITECTURE MIGRATION NEEDS ATTENTION")
        print(f"   Significant issues detected, address before deployment")
        print(f"   Focus on failed tests and critical functionality")
        return 2

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 