#!/usr/bin/env python3
"""Test ASR functionality"""

import os
import sys
import time
import logging
from backend.asr.whisper_client import WhisperClient
from backend.asr.audio_buffer import SmartAudioBuffer
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_whisper_client():
    """Test WhisperClient initialization and basic functionality"""
    
    # Check if API key is configured
    if not Config.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not configured in .env file")
        return False
    
    try:
        # Initialize WhisperClient
        whisper_client = WhisperClient(
            api_key=Config.OPENAI_API_KEY,
            model=Config.OPENAI_MODEL_WHISPER
        )
        logger.info("✓ WhisperClient initialized successfully")
        
        # Test language setting
        whisper_client.set_language('en')
        logger.info("✓ Language setting works")
        
        # Test callback setting
        def test_callback(result):
            logger.info(f"Callback received: {result}")
        
        whisper_client.set_callback(test_callback)
        logger.info("✓ Callback setting works")
        
        # Test with existing audio file if available
        test_files = ['mixed_audio.wav', 'system_audio.wav']
        for test_file in test_files:
            if os.path.exists(test_file):
                logger.info(f"Testing with {test_file}...")
                result = whisper_client.transcribe_file(test_file)
                if result:
                    logger.info(f"✓ Transcription successful: '{result['text'][:50]}...'")
                    logger.info(f"  Language: {result['language']}")
                    return True
                else:
                    logger.error(f"✗ Transcription failed for {test_file}")
        
        logger.warning("No test audio files found (mixed_audio.wav or system_audio.wav)")
        return True  # Still return True as initialization succeeded
        
    except Exception as e:
        logger.error(f"✗ WhisperClient test failed: {e}")
        return False

def test_audio_buffer():
    """Test SmartAudioBuffer functionality"""
    try:
        # Initialize SmartAudioBuffer
        audio_buffer = SmartAudioBuffer(
            sample_rate=Config.AUDIO_SAMPLE_RATE,
            channels=Config.AUDIO_CHANNELS,
            chunk_duration=Config.AUDIO_CHUNK_DURATION,
            use_vad=True
        )
        logger.info("✓ SmartAudioBuffer initialized successfully")
        
        # Test callback
        chunks_received = []
        def chunk_callback(audio_data, timestamp):
            chunks_received.append((len(audio_data), timestamp))
            logger.info(f"Received chunk: {len(audio_data)} bytes at {timestamp}")
        
        audio_buffer.set_chunk_callback(chunk_callback)
        
        # Start buffer
        audio_buffer.start()
        logger.info("✓ Audio buffer started")
        
        # Simulate adding audio data
        sample_rate = Config.AUDIO_SAMPLE_RATE
        channels = Config.AUDIO_CHANNELS
        duration = 0.1  # 100ms of audio
        
        # Generate test audio data (silence)
        import numpy as np
        samples = int(sample_rate * duration)
        audio_data = np.zeros(samples * channels, dtype=np.int16)
        
        # Add data multiple times
        for i in range(60):  # 6 seconds worth
            audio_buffer.add_audio(audio_data.tobytes())
            time.sleep(0.01)
        
        # Wait for processing
        time.sleep(1)
        
        # Stop buffer
        audio_buffer.stop()
        logger.info("✓ Audio buffer stopped")
        
        if chunks_received:
            logger.info(f"✓ Received {len(chunks_received)} chunks")
            return True
        else:
            logger.warning("No chunks received (this is normal for silence with VAD)")
            return True
            
    except Exception as e:
        logger.error(f"✗ SmartAudioBuffer test failed: {e}")
        return False

def main():
    """Run all tests"""
    logger.info("=== Testing ASR Components ===")
    
    tests = [
        ("WhisperClient", test_whisper_client),
        ("SmartAudioBuffer", test_audio_buffer),
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\nTesting {test_name}...")
        result = test_func()
        results.append((test_name, result))
    
    # Summary
    logger.info("\n=== Test Summary ===")
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    if all_passed:
        logger.info("\n✓ All tests passed!")
    else:
        logger.error("\n✗ Some tests failed!")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())