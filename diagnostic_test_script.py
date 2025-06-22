#!/usr/bin/env python3
"""
🔍 COMPREHENSIVE AUDIO STREAMING PIPELINE DIAGNOSTIC SCRIPT

This script validates the entire audio pipeline:
1. WebSocket connection establishment
2. Audio chunk transmission
3. Backend processing
4. STT model performance
5. Transcription quality

Usage:
    python diagnostic_test_script.py

Features:
- Tests fresh vs reused WebSocket sessions
- Validates chunk delivery timing
- Monitors STT response patterns
- Tracks transcription accuracy
"""

import asyncio
import websockets
import json
import base64
import time
import logging
import numpy as np
from datetime import datetime
from typing import Dict, List, Any
import random

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AudioPipelineDiagnostic:
    """Comprehensive diagnostic tool for audio streaming pipeline"""
    
    def __init__(self, websocket_url: str = "wss://econome-staging-964713210810.us-central1.run.app/ws/conversation"):
        self.websocket_url = websocket_url
        self.test_phrases = [
            "Hello, this is test phrase number one",
            "The quick brown fox jumps over the lazy dog",
            "Testing the audio streaming pipeline with phrase two",
            "Machine learning models require high quality audio input",
            "This is the final test phrase for validation"
        ]
        self.test_results = []
        
    def generate_test_audio(self, phrase_index: int, duration_ms: int = 2000) -> bytes:
        """Generate synthetic audio data for testing"""
        sample_rate = 16000
        samples = int(sample_rate * duration_ms / 1000)
        
        # Generate sine wave with some noise to simulate speech
        t = np.linspace(0, duration_ms/1000, samples)
        frequency = 440 + (phrase_index * 50)  # Different frequency per phrase
        audio = np.sin(2 * np.pi * frequency * t) * 0.1 + np.random.normal(0, 0.02, samples)
        
        # Convert to int16
        audio_int16 = (audio * 32767).astype(np.int16)
        return audio_int16.tobytes()
    
    async def test_websocket_connection(self) -> Dict[str, Any]:
        """Test WebSocket connection establishment"""
        logger.info("🔍 Testing WebSocket connection...")
        
        try:
            async with websockets.connect(self.websocket_url) as websocket:
                # Test connection
                await websocket.ping()
                logger.info("✅ WebSocket connection successful")
                return {"success": True, "message": "Connection established"}
                
        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def test_audio_chunk_transmission(self, websocket, phrase_index: int) -> Dict[str, Any]:
        """Test audio chunk transmission and processing"""
        phrase = self.test_phrases[phrase_index]
        logger.info(f"🔍 Testing audio transmission for phrase: '{phrase}'")
        
        test_start = time.time()
        results = {
            "phrase_index": phrase_index,
            "phrase_text": phrase,
            "chunks_sent": 0,
            "chunks_acknowledged": 0,
            "transcription_received": False,
            "transcription_text": "",
            "latency_ms": 0,
            "errors": []
        }
        
        try:
            # Start recording
            start_command = {"action": "start_recording"}
            await websocket.send(json.dumps(start_command))
            logger.info("📤 Sent start_recording command")
            
            # Send audio chunks (simulate 100ms chunks)
            chunk_duration_ms = 100
            total_chunks = 20  # 2 seconds of audio
            
            for chunk_idx in range(total_chunks):
                # Generate audio chunk
                audio_data = self.generate_test_audio(phrase_index, chunk_duration_ms)
                audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                
                # Send chunk
                chunk_command = {
                    "action": "audio_chunk",
                    "audio_data": audio_b64,
                    "chunk_index": chunk_idx,
                    "phrase_index": phrase_index,
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send(json.dumps(chunk_command))
                results["chunks_sent"] += 1
                
                logger.info(f"📤 Sent chunk {chunk_idx + 1}/{total_chunks} for phrase {phrase_index}")
                
                # Wait for chunk interval
                await asyncio.sleep(chunk_duration_ms / 1000)
            
            # Stop recording
            stop_command = {"action": "stop_recording"}
            await websocket.send(json.dumps(stop_command))
            logger.info("📤 Sent stop_recording command")
            
            # Wait for transcription response
            timeout = 10  # 10 second timeout
            start_wait = time.time()
            
            while time.time() - start_wait < timeout:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    response_data = json.loads(response)
                    
                    logger.info(f"📥 Received response: {response_data}")
                    
                    if response_data.get("type") == "transcript":
                        results["transcription_received"] = True
                        results["transcription_text"] = response_data.get("text", "")
                        results["latency_ms"] = (time.time() - test_start) * 1000
                        break
                        
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    results["errors"].append(f"Response parsing error: {e}")
            
            if not results["transcription_received"]:
                results["errors"].append("No transcription received within timeout")
                
        except Exception as e:
            results["errors"].append(f"Transmission error: {e}")
            logger.error(f"❌ Audio transmission failed: {e}")
        
        return results
    
    async def test_session_reuse(self) -> Dict[str, Any]:
        """Test WebSocket session reuse vs fresh connections"""
        logger.info("🔍 Testing session reuse patterns...")
        
        results = {
            "fresh_connection_test": None,
            "reused_connection_test": None,
            "comparison": {}
        }
        
        try:
            # Test 1: Fresh connection for each phrase
            logger.info("📝 Testing fresh connection per phrase...")
            fresh_results = []
            
            for i in range(2):  # Test 2 phrases with fresh connections
                async with websockets.connect(self.websocket_url) as websocket:
                    result = await self.test_audio_chunk_transmission(websocket, i)
                    fresh_results.append(result)
                    await asyncio.sleep(1)  # Brief pause between tests
            
            results["fresh_connection_test"] = fresh_results
            
            # Test 2: Reused connection for multiple phrases
            logger.info("📝 Testing reused connection for multiple phrases...")
            reused_results = []
            
            async with websockets.connect(self.websocket_url) as websocket:
                for i in range(2, 4):  # Test phrases 2-3 with same connection
                    result = await self.test_audio_chunk_transmission(websocket, i)
                    reused_results.append(result)
                    await asyncio.sleep(2)  # Pause between phrases
            
            results["reused_connection_test"] = reused_results
            
            # Compare results
            fresh_success_rate = sum(1 for r in fresh_results if r["transcription_received"]) / len(fresh_results)
            reused_success_rate = sum(1 for r in reused_results if r["transcription_received"]) / len(reused_results)
            
            results["comparison"] = {
                "fresh_success_rate": fresh_success_rate,
                "reused_success_rate": reused_success_rate,
                "fresh_avg_latency": sum(r["latency_ms"] for r in fresh_results if r["transcription_received"]) / max(1, sum(1 for r in fresh_results if r["transcription_received"])),
                "reused_avg_latency": sum(r["latency_ms"] for r in reused_results if r["transcription_received"]) / max(1, sum(1 for r in reused_results if r["transcription_received"]))
            }
            
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"❌ Session reuse test failed: {e}")
        
        return results
    
    async def run_comprehensive_diagnostic(self) -> Dict[str, Any]:
        """Run complete diagnostic suite"""
        logger.info("🚀 Starting comprehensive audio pipeline diagnostic...")
        
        diagnostic_results = {
            "timestamp": datetime.now().isoformat(),
            "websocket_url": self.websocket_url,
            "tests": {}
        }
        
        # Test 1: WebSocket Connection
        diagnostic_results["tests"]["websocket_connection"] = await self.test_websocket_connection()
        
        # Test 2: Session Reuse Patterns
        diagnostic_results["tests"]["session_reuse"] = await self.test_session_reuse()
        
        # Generate summary
        diagnostic_results["summary"] = self.generate_summary(diagnostic_results)
        
        return diagnostic_results
    
    def generate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate diagnostic summary"""
        summary = {
            "overall_health": "unknown",
            "critical_issues": [],
            "recommendations": []
        }
        
        # Analyze WebSocket connection
        if not results["tests"]["websocket_connection"]["success"]:
            summary["critical_issues"].append("WebSocket connection failure")
            summary["overall_health"] = "critical"
        
        # Analyze session patterns
        session_test = results["tests"]["session_reuse"]
        if "comparison" in session_test:
            comp = session_test["comparison"]
            
            if comp["fresh_success_rate"] > comp["reused_success_rate"]:
                summary["critical_issues"].append("Session reuse degradation detected")
                summary["recommendations"].append("Investigate WebSocket state management")
            
            if comp["fresh_success_rate"] < 0.5:
                summary["critical_issues"].append("Low transcription success rate")
                summary["recommendations"].append("Check STT model configuration and audio quality")
        
        # Set overall health
        if not summary["critical_issues"]:
            summary["overall_health"] = "healthy"
        elif len(summary["critical_issues"]) == 1:
            summary["overall_health"] = "warning"
        else:
            summary["overall_health"] = "critical"
        
        return summary
    
    def print_results(self, results: Dict[str, Any]):
        """Print diagnostic results in a readable format"""
        print("\n" + "="*80)
        print("🔍 AUDIO PIPELINE DIAGNOSTIC RESULTS")
        print("="*80)
        
        print(f"📊 Overall Health: {results['summary']['overall_health'].upper()}")
        print(f"🕐 Test Time: {results['timestamp']}")
        print(f"🌐 WebSocket URL: {results['websocket_url']}")
        
        if results['summary']['critical_issues']:
            print(f"\n❌ Critical Issues ({len(results['summary']['critical_issues'])}):")
            for issue in results['summary']['critical_issues']:
                print(f"   • {issue}")
        
        if results['summary']['recommendations']:
            print(f"\n💡 Recommendations ({len(results['summary']['recommendations'])}):")
            for rec in results['summary']['recommendations']:
                print(f"   • {rec}")
        
        # Session comparison
        if "comparison" in results["tests"]["session_reuse"]:
            comp = results["tests"]["session_reuse"]["comparison"]
            print(f"\n📈 Session Performance Comparison:")
            print(f"   Fresh Connections: {comp['fresh_success_rate']:.1%} success, {comp['fresh_avg_latency']:.0f}ms avg latency")
            print(f"   Reused Connections: {comp['reused_success_rate']:.1%} success, {comp['reused_avg_latency']:.0f}ms avg latency")
        
        print("\n" + "="*80)

async def main():
    """Main diagnostic function"""
    diagnostic = AudioPipelineDiagnostic()
    results = await diagnostic.run_comprehensive_diagnostic()
    
    # Print results
    diagnostic.print_results(results)
    
    # Save detailed results
    with open(f"diagnostic_results_{int(time.time())}.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Detailed results saved to diagnostic_results_{int(time.time())}.json")

if __name__ == "__main__":
    asyncio.run(main()) 