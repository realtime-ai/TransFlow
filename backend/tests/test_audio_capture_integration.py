#!/usr/bin/env python3
"""Integration test for AudioCapture with resampling"""

import sys
import os
import time
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.audio.capture import AudioCapture

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_audio_capture_with_resampling():
    """Test AudioCapture with resampling enabled"""
    
    logger.info("Testing AudioCapture with resampling...")
    
    # Initialize AudioCapture with 16kHz target for OpenAI Realtime
    audio_capture = AudioCapture()
    audio_capture.init(sample_rate=16000, channels=1, bit_depth=16)
    
    # Get available devices
    devices = audio_capture.list_audio_devices()
    logger.info(f"Available devices: {len(devices)}")
    
    for device in devices:
        logger.info(f"  - {device}")
    
    # Get output format
    output_format = audio_capture.get_output_audio_format()
    logger.info(f"Target output format: {output_format}")
    
    try:
        # Test starting recording (mic only, short duration)
        logger.info("Starting microphone recording for 3 seconds...")
        audio_capture.start_recording(
            capture_system_audio=False,  # Only mic to avoid permission issues
            capture_microphone=True,
            exclude_current_process=True
        )
        logger.info("Recording started")
        
        # Collect some samples
        samples_collected = 0
        start_time = time.time()
        max_duration = 3.0  # seconds
        
        while time.time() - start_time < max_duration:
            # Get microphone data (should be resampled)
            mic_data = audio_capture.get_mic_data(timeout=0.1)
            if mic_data:
                samples_collected += len(mic_data) // 2  # 2 bytes per 16-bit sample
                logger.info(f"Collected {len(mic_data)} bytes ({len(mic_data)//2} samples)")
                
                # Check first few samples to verify it's not all zeros
                if len(mic_data) >= 10:
                    import struct
                    first_samples = struct.unpack('<5h', mic_data[:10])  # 5 int16 samples
                    logger.info(f"Sample values: {first_samples}")
            
            time.sleep(0.1)
        
        # Stop recording
        logger.info("Stopping recording...")
        audio_capture.stop_recording()
        
        # Get detected formats
        mic_format = audio_capture.get_microphone_audio_format()
        system_format = audio_capture.get_system_audio_format()
        
        logger.info(f"Detected microphone format: {mic_format}")
        logger.info(f"Detected system format: {system_format}")
        
        # Verify results
        logger.info(f"Total samples collected: {samples_collected}")
        
        if samples_collected > 0:
            logger.info("✓ Successfully collected resampled audio data")
            
            # Verify sample rate makes sense
            expected_samples = int(16000 * max_duration * 0.8)  # Allow some margin
            if samples_collected > expected_samples * 0.1:  # At least 10% of expected
                logger.info("✓ Sample count appears reasonable for 16kHz target")
            else:
                logger.warning(f"Low sample count: got {samples_collected}, expected ~{expected_samples}")
        else:
            logger.warning("No audio data collected - microphone may not be available")
            
        # Test format detection
        if mic_format:
            logger.info("✓ Microphone format was detected and parsed")
            logger.info(f"  Original: {mic_format['sample_rate']}Hz, {mic_format['channels']}ch, {mic_format['bit_depth']}bit")
            logger.info(f"  Target:   {output_format['sample_rate']}Hz, {output_format['channels']}ch, {output_format['bit_depth']}bit")
        else:
            logger.warning("Microphone format was not detected")
        
        logger.info("🎉 Integration test completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Try to clean up
        try:
            audio_capture.stop_recording()
        except:
            pass
        
        raise

if __name__ == "__main__":
    try:
        test_audio_capture_with_resampling()
    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        sys.exit(1)