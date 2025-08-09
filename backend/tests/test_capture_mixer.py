#!/usr/bin/env python3
"""
Test combining AudioCapture with AudioMixer for dual-stream recording
"""

import sys
import os
import time
import wave
import numpy as np
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audio.capture import AudioCapture
from audio.mixer import create_simple_mixer


def test_dual_stream_recording(duration=5, output_file="mixed_recording.wav"):
    """
    Test recording system audio and microphone separately, then mixing them.
    
    Args:
        duration: Recording duration in seconds
        output_file: Output filename
    """
    print("=" * 50)
    print("Dual Stream Recording + Mixing Test")
    print("=" * 50)
    
    # Create two separate AudioCapture instances for different sources
    system_capture = AudioCapture(sample_rate=16000, channels=1, bit_depth=16)
    mic_capture = AudioCapture(sample_rate=16000, channels=1, bit_depth=16)
    
    # Create professional mixer with jitter buffering for combining the streams
    from audio.mixer import create_professional_mixer
    mixer = create_professional_mixer(
        sample_rate=16000,
        channels=1,
        format='s16',
        input1_volume=0.8,  # System audio volume
        input2_volume=1.2,  # Microphone volume
        target_latency_ms=50.0,  # 50ms target latency
        max_latency_ms=200.0     # 200ms max latency
    )
    
    print("Configuration:")
    print(f"  System audio: {system_capture.sample_rate}Hz, {system_capture.channels}ch")
    print(f"  Microphone: {mic_capture.sample_rate}Hz, {mic_capture.channels}ch")
    print(f"  Mixer volumes: System={mixer.get_input_volume(1)}, Mic={mixer.get_input_volume(2)}")
    print(f"  Jitter buffer enabled: {mixer.get_info()['jitter_buffer_enabled']}")
    
    # Configuration for system audio recording
    system_config = {
        'capture_system_audio': True,
        'capture_microphone': False,
        'exclude_current_process': True
    }
    
    # Configuration for microphone recording
    mic_config = {
        'capture_system_audio': False,
        'capture_microphone': True,
        'exclude_current_process': True
    }
    
    try:
        print(f"\n▶ Starting dual recording for {duration} seconds...")
        
        # Start both recordings
        system_capture.start_recording(system_config)
        mic_capture.start_recording(mic_config)
        
        # Collect audio data
        system_chunks = []
        mic_chunks = []
        
        start_time = time.time()
        chunk_duration = 0.1  # 100ms chunks
        
        while time.time() - start_time < duration:
            # Get data from both sources
            system_data = system_capture.get_system_audio_data(timeout=chunk_duration)
            mic_data = mic_capture.get_mic_audio_data(timeout=chunk_duration)
            
            if system_data:
                # Convert bytes to int16 array
                system_array = np.frombuffer(system_data, dtype=np.int16)
                system_chunks.append(system_array)
            
            if mic_data:
                # Convert bytes to int16 array
                mic_array = np.frombuffer(mic_data, dtype=np.int16)
                mic_chunks.append(mic_array)
            
            elapsed = time.time() - start_time
            print(f"  Recording... {elapsed:.1f}/{duration}s", end='\r')
        
        print(f"  Recording... {duration:.1f}/{duration}s")
        
        print("■ Stopping recordings...")
        system_capture.stop_recording()
        mic_capture.stop_recording()
        
        # Get remaining data
        while True:
            system_data = system_capture.get_system_audio_data(timeout=0.01)
            if system_data:
                system_array = np.frombuffer(system_data, dtype=np.int16)
                system_chunks.append(system_array)
            else:
                break
        
        while True:
            mic_data = mic_capture.get_mic_audio_data(timeout=0.01)
            if mic_data:
                mic_array = np.frombuffer(mic_data, dtype=np.int16)
                mic_chunks.append(mic_array)
            else:
                break
        
        print(f"\nCollected data:")
        print(f"  System chunks: {len(system_chunks)}")
        print(f"  Microphone chunks: {len(mic_chunks)}")
        
        # Mix the audio streams
        print("🎛 Mixing audio streams...")
        mixed_output = mixer.mix_batch(system_chunks, mic_chunks)
        
        print(f"Mixed output: {mixed_output.shape}")
        print(f"Mixed peak level: {np.max(np.abs(mixed_output)) if len(mixed_output) > 0 else 0}")
        
        # Show buffer statistics
        mixer_info = mixer.get_info()
        if 'buffer_stats' in mixer_info:
            print(f"\n📊 Buffer Statistics:")
            for input_name, stats in mixer_info['buffer_stats'].items():
                print(f"  {input_name}:")
                print(f"    Buffer level: {stats['buffer_level']:.2f}x target")
                print(f"    Latency: {stats['latency_ms']:.1f}ms")
                print(f"    Underruns: {stats['underrun_count']}")
                print(f"    Overruns: {stats['overrun_count']}")
                print(f"    Chunks in buffer: {stats['chunks_in_buffer']}")
        
        # Save to file
        print(f"💾 Saving to {output_file}...")
        with wave.open(output_file, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(mixed_output.tobytes())
        
        # Verify file
        with wave.open(output_file, 'rb') as wf:
            print(f"\n📊 Output file properties:")
            print(f"  Sample rate: {wf.getframerate()}Hz")
            print(f"  Channels: {wf.getnchannels()}")
            print(f"  Bit depth: {wf.getsampwidth() * 8} bits")
            print(f"  Duration: {wf.getnframes() / wf.getframerate():.2f} seconds")
            
            file_size = os.path.getsize(output_file)
            print(f"  File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during recording: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_system_audio_only(duration=3, output_file="system_only.wav"):
    """Test system audio recording with mixer (single input)"""
    print("\n" + "=" * 50)
    print("System Audio Only Test")
    print("=" * 50)
    
    capture = AudioCapture(sample_rate=16000, channels=1, bit_depth=16)
    mixer = create_simple_mixer(16000, 1, 's16', input1_volume=1.0, input2_volume=0.0)
    
    config = {
        'capture_system_audio': True,
        'capture_microphone': False,
        'exclude_current_process': True
    }
    
    try:
        print(f"▶ Recording system audio for {duration} seconds...")
        capture.start_recording(config)
        time.sleep(duration)
        capture.stop_recording()
        
        # Get all data
        chunks = []
        while True:
            data = capture.get_system_audio_data(timeout=0.01)
            if data:
                array = np.frombuffer(data, dtype=np.int16)
                chunks.append(array)
            else:
                break
        
        print(f"Collected {len(chunks)} chunks")
        
        # Mix (only input 1 used)
        mixed = mixer.mix_batch(chunks, [])
        
        print(f"Mixed output: {mixed.shape}")
        
        # Save
        with wave.open(output_file, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(mixed.tobytes())
        
        print(f"💾 Saved to {output_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_volume_adjustment_recording(duration=3):
    """Test recording with dynamic volume adjustment"""
    print("\n" + "=" * 50)
    print("Dynamic Volume Adjustment Test")
    print("=" * 50)
    
    capture = AudioCapture(sample_rate=16000, channels=1, bit_depth=16)
    mixer = create_simple_mixer(16000, 1, 's16')
    
    config = {
        'capture_system_audio': True,
        'capture_microphone': False,
        'exclude_current_process': True
    }
    
    try:
        print(f"▶ Recording with volume changes...")
        capture.start_recording(config)
        
        chunks = []
        start_time = time.time()
        
        while time.time() - start_time < duration:
            elapsed = time.time() - start_time
            
            # Change volume dynamically
            volume = 0.5 + 0.5 * np.sin(2 * np.pi * elapsed / duration)
            mixer.set_input_volume(1, volume)
            mixer.set_input_volume(2, 0.0)  # Mute input 2
            
            # Get audio data
            data = capture.get_system_audio_data(timeout=0.1)
            if data:
                array = np.frombuffer(data, dtype=np.int16)
                
                # Mix with current volume
                mixed_chunk = mixer.mix(array, None)
                chunks.append(mixed_chunk)
                
                print(f"  Volume: {volume:.2f}, {elapsed:.1f}s", end='\r')
        
        capture.stop_recording()
        
        print(f"\nProcessed {len(chunks)} chunks with dynamic volume")
        
        # Combine all chunks
        if chunks:
            final_output = np.concatenate(chunks)
            print(f"Final output: {final_output.shape}")
            
            # Save
            with wave.open("volume_test.wav", "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(final_output.tobytes())
            
            print("💾 Saved to volume_test.wav")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def cleanup_test_files():
    """Clean up test files"""
    test_files = [
        "mixed_recording.wav",
        "system_only.wav",
        "volume_test.wav"
    ]
    
    removed = 0
    for filename in test_files:
        if os.path.exists(filename):
            os.remove(filename)
            removed += 1
    
    if removed > 0:
        print(f"\n🧹 Cleaned up {removed} test files")


def main():
    parser = argparse.ArgumentParser(description='Test AudioCapture + AudioMixer')
    parser.add_argument('--duration', type=int, default=3,
                       help='Recording duration in seconds (default: 3)')
    parser.add_argument('--test', choices=['dual', 'system', 'volume', 'all'],
                       default='all', help='Which test to run')
    parser.add_argument('--cleanup', action='store_true',
                       help='Remove test files after completion')
    
    args = parser.parse_args()
    
    print("AudioCapture + AudioMixer Test Suite")
    print("=" * 50)
    
    success = True
    
    try:
        if args.test in ['dual', 'all']:
            success &= test_dual_stream_recording(args.duration)
        
        if args.test in ['system', 'all']:
            success &= test_system_audio_only(args.duration)
        
        if args.test in ['volume', 'all']:
            success &= test_volume_adjustment_recording(args.duration)
            
    except KeyboardInterrupt:
        print("\n\n⏹ Test interrupted by user")
        success = False
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    if args.cleanup:
        cleanup_test_files()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ All capture+mixer tests completed successfully!")
    else:
        print("❌ Some tests failed!")
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())