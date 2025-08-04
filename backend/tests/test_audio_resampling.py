#!/usr/bin/env python3
"""Test audio resampling functionality in capture.py"""

import sys
import os
import numpy as np
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.audio.resampler import AudioResampler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_resampling():
    """Test basic audio resampling functionality"""
    
    # Test 1: 48kHz float32 to 16kHz int16
    logger.info("Test 1: 48kHz float32 → 16kHz int16")
    resampler1 = AudioResampler(
        input_sample_rate=48000,
        output_sample_rate=16000,
        input_channels=1,
        output_channels=1,
        input_format='flt',
        output_format='s16'
    )
    
    # Generate test audio: 1 second 1kHz sine wave at 48kHz
    duration = 1.0
    frequency = 1000.0
    t = np.linspace(0, duration, int(48000 * duration), False)
    test_audio = np.sin(2 * np.pi * frequency * t).astype(np.float32)
    
    logger.info(f"Input: {len(test_audio)} samples @ 48kHz")
    
    # Resample
    resampled_audio, output_samples = resampler1.resample(test_audio)
    
    logger.info(f"Output: {len(resampled_audio)} samples @ 16kHz")
    logger.info(f"Expected samples: {resampler1.get_output_samples(len(test_audio))}")
    
    # Verify output
    expected_samples = int(len(test_audio) * 16000 / 48000)
    assert abs(len(resampled_audio) - expected_samples) < 100, f"Sample count mismatch: expected ~{expected_samples}, got {len(resampled_audio)}"
    assert resampled_audio.dtype == np.int16, f"Wrong output dtype: expected int16, got {resampled_audio.dtype}"
    
    logger.info("✓ Test 1 passed")
    
    # Test 2: Stereo to mono conversion with resampling
    logger.info("\nTest 2: 44.1kHz stereo → 16kHz mono")
    resampler2 = AudioResampler(
        input_sample_rate=44100,
        output_sample_rate=16000,
        input_channels=2,
        output_channels=1,
        input_format='s16',
        output_format='s16'
    )
    
    # Generate stereo test data
    t_stereo = np.linspace(0, duration, int(44100 * duration), False)
    left_channel = np.sin(2 * np.pi * 800 * t_stereo).astype(np.float32)
    right_channel = np.sin(2 * np.pi * 1200 * t_stereo).astype(np.float32)
    
    # Convert to int16 and interleave channels
    stereo_audio = np.column_stack([left_channel * 32767, right_channel * 32767]).astype(np.int16)
    
    logger.info(f"Stereo input: {stereo_audio.shape} @ 44.1kHz")
    
    # Resample
    mono_output, _ = resampler2.resample(stereo_audio)
    
    logger.info(f"Mono output: {mono_output.shape} @ 16kHz")
    
    # Verify output
    expected_mono_samples = int(stereo_audio.shape[0] * 16000 / 44100)
    assert abs(len(mono_output) - expected_mono_samples) < 100, f"Mono sample count mismatch"
    assert mono_output.dtype == np.int16, f"Wrong mono output dtype"
    
    logger.info("✓ Test 2 passed")
    
    # Test 3: Byte input conversion (like from ScreenCaptureKit)
    logger.info("\nTest 3: Bytes input handling")
    resampler3 = AudioResampler(
        input_sample_rate=24000,
        output_sample_rate=16000,
        input_channels=1,
        output_channels=1,
        input_format='s16',
        output_format='s16' 
    )
    
    # Generate test audio as bytes (like from ScreenCaptureKit)
    t_bytes = np.linspace(0, 0.1, int(24000 * 0.1), False)  # 100ms
    test_audio_samples = (np.sin(2 * np.pi * 440 * t_bytes) * 32767).astype(np.int16)
    test_audio_bytes = test_audio_samples.tobytes()
    
    logger.info(f"Bytes input: {len(test_audio_bytes)} bytes ({len(test_audio_samples)} samples)")
    
    # Resample from bytes
    resampled_from_bytes, _ = resampler3.resample(test_audio_bytes)
    
    logger.info(f"Bytes output: {len(resampled_from_bytes)} samples @ 16kHz")
    
    # Verify output
    expected_bytes_samples = int(len(test_audio_samples) * 16000 / 24000)
    logger.info(f"Expected: {expected_bytes_samples}, Got: {len(resampled_from_bytes)}")
    assert abs(len(resampled_from_bytes) - expected_bytes_samples) < 50, f"Bytes sample count mismatch: expected ~{expected_bytes_samples}, got {len(resampled_from_bytes)}"
    
    logger.info("✓ Test 3 passed")
    
    logger.info("\n🎉 All resampling tests passed!")

def test_capture_configuration():
    """Test that capture.py configuration matches resampler requirements"""
    
    # Import after path setup
    from backend.audio.capture import AudioCapture
    
    logger.info("Test 4: AudioCapture configuration compatibility")
    
    # Test default configuration
    audio_capture = AudioCapture()
    audio_capture.init(sample_rate=16000, channels=1, bit_depth=16)
    
    # Get output format
    output_format = audio_capture.get_output_audio_format()
    logger.info(f"AudioCapture target format: {output_format}")
    
    # Verify format is suitable for OpenAI Realtime
    assert output_format['sample_rate'] == 16000, f"Sample rate should be 16000Hz for OpenAI Realtime"
    assert output_format['channels'] == 1, f"Should be mono for OpenAI Realtime"
    assert output_format['bit_depth'] == 16, f"Should be 16-bit for OpenAI Realtime"
    
    logger.info("✓ Test 4 passed - AudioCapture configuration is compatible with OpenAI Realtime")
    
    logger.info("\n🎉 All tests passed!")

if __name__ == "__main__":
    try:
        test_resampling()
        test_capture_configuration()
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)