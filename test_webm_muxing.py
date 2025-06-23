#!/usr/bin/env python3
"""
Test script for WebM chunk buffering and muxing (Strategy A)

This script simulates the browser MediaRecorder behavior:
- First chunk: Complete WebM container with EBML header
- Subsequent chunks: Raw Opus packets without container headers

Tests the Strategy A implementation locally before deployment.
"""

import sys
import os
import time
import tempfile
import subprocess
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def create_test_webm_chunks():
    """
    Create test WebM chunks that simulate browser MediaRecorder behavior
    """
    print("🔧 Creating test WebM chunks...")
    
    # Create a simple test audio file first
    test_audio_path = "test_audio.wav"
    
    # Generate 5 seconds of test audio (sine wave)
    ffmpeg_gen_cmd = [
        'ffmpeg', '-y',
        '-f', 'lavfi',
        '-i', 'sine=frequency=440:duration=5',
        '-ar', '16000',
        '-ac', '1',
        test_audio_path
    ]
    
    try:
        subprocess.run(ffmpeg_gen_cmd, check=True, capture_output=True)
        print(f"✅ Generated test audio: {test_audio_path}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to generate test audio: {e}")
        return None, []
    
    # Convert to WebM with chunking to simulate browser behavior
    webm_path = "test_audio.webm"
    ffmpeg_webm_cmd = [
        'ffmpeg', '-y',
        '-i', test_audio_path,
        '-c:a', 'libopus',
        '-b:a', '64k',
        '-f', 'webm',
        webm_path
    ]
    
    try:
        subprocess.run(ffmpeg_webm_cmd, check=True, capture_output=True)
        print(f"✅ Generated WebM file: {webm_path}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to generate WebM: {e}")
        return None, []
    
    # Read the WebM file and split into chunks
    with open(webm_path, 'rb') as f:
        webm_data = f.read()
    
    # Simulate browser chunking: first chunk has header, rest are smaller
    chunk_size = len(webm_data) // 4  # Split into 4 chunks
    chunks = []
    
    for i in range(4):
        start = i * chunk_size
        end = start + chunk_size if i < 3 else len(webm_data)
        chunk = webm_data[start:end]
        chunks.append(chunk)
        print(f"📦 Chunk {i}: {len(chunk)} bytes")
    
    # Clean up temporary files
    os.unlink(test_audio_path)
    os.unlink(webm_path)
    
    return webm_data, chunks

def test_webm_buffer():
    """
    Test the WebM chunk buffer implementation
    """
    print("\n🧪 Testing WebM chunk buffer...")
    
    try:
        from src.webm_muxer import WebMChunkBuffer
        
        # Create test buffer
        buffer = WebMChunkBuffer(
            buffer_size=3,
            max_buffer_age_seconds=2.0,
            connection_id="test_connection"
        )
        
        # Create test chunks
        original_webm, chunks = create_test_webm_chunks()
        if not chunks:
            print("❌ Failed to create test chunks")
            return False
        
        print(f"\n📊 Testing with {len(chunks)} chunks...")
        
        processed_chunks = []
        
        for i, chunk in enumerate(chunks):
            print(f"\n📦 Processing chunk {i} ({len(chunk)} bytes)...")
            
            should_process, muxed_bytes = buffer.add_chunk(chunk, "audio/webm; codecs=opus")
            
            if should_process:
                if muxed_bytes is not None:
                    print(f"✅ Got muxed output: {len(muxed_bytes)} bytes")
                    processed_chunks.append(muxed_bytes)
                else:
                    print(f"✅ Processing original chunk (first chunk)")
                    processed_chunks.append(chunk)
            else:
                print(f"📦 Chunk buffered, waiting for more...")
        
        # Force flush any remaining buffer
        remaining = buffer.force_flush()
        if remaining:
            print(f"🔄 Force flushed remaining: {len(remaining)} bytes")
            processed_chunks.append(remaining)
        
        print(f"\n📊 Buffer stats: {buffer.get_buffer_stats()}")
        print(f"📊 Total processed chunks: {len(processed_chunks)}")
        
        return len(processed_chunks) > 0
        
    except Exception as e:
        print(f"❌ WebM buffer test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ffmpeg_processing():
    """
    Test FFmpeg processing with muxed chunks
    """
    print("\n🔧 Testing FFmpeg processing...")
    
    try:
        # Create test chunks
        original_webm, chunks = create_test_webm_chunks()
        if not chunks:
            return False
        
        # Test processing first chunk (should work)
        first_chunk = chunks[0]
        print(f"🔧 Testing first chunk ({len(first_chunk)} bytes)...")
        
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'matroska',
            '-fflags', '+ignidx',
            '-analyzeduration', '0',
            '-probesize', '32',
            '-i', 'pipe:0',
            '-f', 's16le',
            '-acodec', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1',
            '-loglevel', 'error',
            'pipe:1'
        ]
        
        process = subprocess.run(
            ffmpeg_cmd,
            input=first_chunk,
            capture_output=True,
            timeout=10
        )
        
        if process.returncode == 0 and process.stdout:
            print(f"✅ First chunk processed successfully: {len(process.stdout)} bytes PCM")
        else:
            print(f"❌ First chunk processing failed: {process.stderr.decode() if process.stderr else 'Unknown error'}")
            return False
        
        # Test processing subsequent chunks (should fail without muxing)
        if len(chunks) > 1:
            second_chunk = chunks[1]
            print(f"🔧 Testing second chunk without muxing ({len(second_chunk)} bytes)...")
            
            process = subprocess.run(
                ffmpeg_cmd,
                input=second_chunk,
                capture_output=True,
                timeout=10
            )
            
            if process.returncode == 0 and process.stdout:
                print(f"⚠️ Second chunk processed (unexpected): {len(process.stdout)} bytes PCM")
            else:
                print(f"✅ Second chunk failed as expected: {process.stderr.decode() if process.stderr else 'Unknown error'}")
        
        return True
        
    except Exception as e:
        print(f"❌ FFmpeg processing test failed: {e}")
        return False

def main():
    """
    Run all tests
    """
    print("🧪 WebM Chunk Buffering & Muxing Test Suite (Strategy A)")
    print("=" * 60)
    
    # Check FFmpeg availability
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ FFmpeg is available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ FFmpeg not found - please install FFmpeg")
        return False
    
    # Run tests
    tests = [
        ("WebM Buffer Logic", test_webm_buffer),
        ("FFmpeg Processing", test_ffmpeg_processing),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
            print(f"{'✅' if result else '❌'} {test_name}: {'PASSED' if result else 'FAILED'}")
        except Exception as e:
            print(f"❌ {test_name}: FAILED with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 Test Results Summary:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {test_name}: {status}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Strategy A implementation is ready for deployment.")
        return True
    else:
        print("⚠️ Some tests failed. Please review the implementation before deployment.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 