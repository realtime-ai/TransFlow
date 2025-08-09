#!/usr/bin/env python3
"""Test server integration with resampling"""

import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_server_audio_capture_config():
    """Test that server.py properly configures AudioCapture for resampling"""
    
    logger.info("Testing server.py AudioCapture configuration...")
    
    # Import server components
    from backend.audio.capture import AudioCapture
    
    # Initialize audio capture like server.py does
    audio_capture = AudioCapture()
    audio_capture.init(sample_rate=16000, channels=1, bit_depth=16)
    
    # Verify configuration
    output_format = audio_capture.get_output_audio_format()
    logger.info(f"AudioCapture output format: {output_format}")
    
    # Check compatibility with OpenAI Realtime API requirements
    assert output_format['sample_rate'] == 16000, "Sample rate must be 16kHz for OpenAI Realtime"
    assert output_format['channels'] == 1, "Must be mono for OpenAI Realtime" 
    assert output_format['bit_depth'] == 16, "Must be 16-bit for OpenAI Realtime"
    
    logger.info("✓ AudioCapture configured correctly for OpenAI Realtime API")
    
    # Test start_recording parameter format (like server.py does)
    config = {
        'capture_system_audio': True,
        'capture_microphone': True,
        'microphone_id': None,
        'selected_apps': [],  # Include the parameter that was causing issues
        'exclude_current_process': True
    }
    
    logger.info("Testing start_recording parameter passing...")
    try:
        # This should work without error (we won't actually start recording)
        # Just test that the parameters are accepted
        import inspect
        start_recording_sig = inspect.signature(audio_capture.start_recording)
        bound_args = start_recording_sig.bind(**config)
        logger.info(f"Parameters bound successfully: {bound_args.arguments}")
        logger.info("✓ start_recording parameter format is correct")
    except Exception as e:
        logger.error(f"Parameter binding failed: {e}")
        raise
    
    logger.info("🎉 Server integration test passed!")

def test_asr_capabilities():
    """Test ASR capabilities and compatibility"""
    
    logger.info("Testing ASR capabilities...")
    
    try:
        from backend.asr import create_asr
        
        # Test creating OpenAI Realtime ASR (without API key, just test instantiation)
        try:
            asr_client = create_asr('openai_realtime', api_key='dummy-key')
            capabilities = asr_client.get_capabilities()
            
            logger.info(f"OpenAI Realtime capabilities: {capabilities}")
            
            # Check key capabilities
            assert capabilities['realtime'] == True, "Should support realtime"
            assert capabilities['streaming'] == True, "Should support streaming"
            assert capabilities['required_sample_rate'] == 16000, "Should require 16kHz"
            assert capabilities['required_channels'] == 1, "Should require mono"
            assert capabilities['required_bit_depth'] == 16, "Should require 16-bit"
            
            logger.info("✓ OpenAI Realtime ASR capabilities are correct")
            
        except ImportError as e:
            logger.warning(f"OpenAI Realtime ASR not available: {e}")
        
        # Test Whisper fallback
        try:
            whisper_client = create_asr('whisper', api_key='dummy-key')
            whisper_capabilities = whisper_client.get_capabilities()
            
            logger.info(f"Whisper capabilities: {whisper_capabilities}")
            logger.info("✓ Whisper ASR available as fallback")
            
        except ImportError as e:
            logger.warning(f"Whisper ASR not available: {e}")
            
    except Exception as e:
        logger.error(f"ASR test failed: {e}")
        raise
    
    logger.info("🎉 ASR capabilities test passed!")

if __name__ == "__main__":
    try:
        test_server_audio_capture_config()
        test_asr_capabilities()
        logger.info("\n🎉 All server integration tests passed!")
    except Exception as e:
        logger.error(f"Server integration test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)