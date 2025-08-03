#!/usr/bin/env python3
"""
Test audio recording functionality with different configurations
"""

import sys
import os
import time
import wave
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audio.capture import AudioCapture


def test_16k_mono_recording(duration=5, output_file="test_16k_mono.wav"):
    """Test 16kHz mono audio recording
    
    Args:
        duration: Recording duration in seconds
        output_file: Output filename
    """
    print("=" * 50)
    print("Testing 16kHz Mono Audio Recording")
    print("=" * 50)
    
    # Create 16kHz mono recorder
    capture = AudioCapture(sample_rate=16000, channels=1, bit_depth=16)
    
    print(f"Audio Configuration:")
    print(f"  Sample rate: {capture.sample_rate}Hz")
    print(f"  Channels: {capture.channels} (Mono)")
    print(f"  Bit depth: {capture.bit_depth} bits")
    print(f"  Duration: {duration} seconds")
    
    # Recording configuration
    config = {
        'capture_system_audio': True,
        'capture_microphone': False,
        'exclude_current_process': True
    }
    
    try:
        print(f"\n▶ Starting recording...")
        capture.start_recording(config)
        
        # Show progress
        for i in range(duration):
            print(f"  Recording... {i+1}/{duration} seconds", end='\r')
            time.sleep(1)
        print(f"  Recording... {duration}/{duration} seconds")
        
        print("■ Stopping recording...")
        capture.stop_recording()
        
        # Save to file
        print(f"💾 Saving to {output_file}...")
        capture.save_to_file(output_file)
        
        # Verify the output
        verify_audio_file(output_file)
        
        return True
        
    except Exception as e:
        print(f"❌ Error during recording: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_default_recording(duration=5, output_file="test_48k_stereo.wav"):
    """Test default 48kHz stereo audio recording
    
    Args:
        duration: Recording duration in seconds
        output_file: Output filename
    """
    print("=" * 50)
    print("Testing Default Audio Recording (48kHz Stereo)")
    print("=" * 50)
    
    # Create default recorder
    capture = AudioCapture()  # Default: 48kHz, stereo, 16-bit
    
    print(f"Audio Configuration:")
    print(f"  Sample rate: {capture.sample_rate}Hz")
    print(f"  Channels: {capture.channels} (Stereo)")
    print(f"  Bit depth: {capture.bit_depth} bits")
    print(f"  Duration: {duration} seconds")
    
    # Recording configuration
    config = {
        'capture_system_audio': True,
        'capture_microphone': False,
        'exclude_current_process': True
    }
    
    try:
        print(f"\n▶ Starting recording...")
        capture.start_recording(config)
        
        # Show progress
        for i in range(duration):
            print(f"  Recording... {i+1}/{duration} seconds", end='\r')
            time.sleep(1)
        print(f"  Recording... {duration}/{duration} seconds")
        
        print("■ Stopping recording...")
        capture.stop_recording()
        
        # Save to file
        print(f"💾 Saving to {output_file}...")
        capture.save_to_file(output_file)
        
        # Verify the output
        verify_audio_file(output_file)
        
        return True
        
    except Exception as e:
        print(f"❌ Error during recording: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_microphone_recording(duration=5, output_file="test_microphone.wav"):
    """Test microphone recording with 16kHz mono
    
    Args:
        duration: Recording duration in seconds
        output_file: Output filename
    """
    print("=" * 50)
    print("Testing Microphone Recording (16kHz Mono)")
    print("=" * 50)
    
    # Create 16kHz mono recorder for microphone
    capture = AudioCapture(sample_rate=16000, channels=1, bit_depth=16)
    
    # List available microphones
    devices = capture.list_audio_devices()
    mic_devices = [d for d in devices if d.get('type') in ['microphone', 'input']]
    
    if not mic_devices:
        print("❌ No microphone devices found!")
        return False
    
    print("Available microphones:")
    for i, device in enumerate(mic_devices):
        print(f"  {i+1}. {device['name']} ({device['source']})")
    
    # Use default microphone
    default_mic = next((d for d in mic_devices if 'default' in str(d.get('flags', []))), mic_devices[0])
    print(f"\nUsing microphone: {default_mic['name']}")
    
    # Recording configuration
    config = {
        'capture_system_audio': False,
        'capture_microphone': True,
        'microphone_id': default_mic.get('id'),
        'exclude_current_process': True
    }
    
    try:
        print(f"\n▶ Starting microphone recording...")
        print("  (Speak into your microphone)")
        capture.start_recording(config)
        
        # Show progress
        for i in range(duration):
            print(f"  Recording... {i+1}/{duration} seconds", end='\r')
            time.sleep(1)
        print(f"  Recording... {duration}/{duration} seconds")
        
        print("■ Stopping recording...")
        capture.stop_recording()
        
        # Save to file
        print(f"💾 Saving to {output_file}...")
        capture.save_to_file(output_file)
        
        # Verify the output
        verify_audio_file(output_file)
        
        return True
        
    except Exception as e:
        print(f"❌ Error during recording: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mixed_recording(duration=5, output_file="test_mixed.wav"):
    """Test recording both system audio and microphone
    
    Args:
        duration: Recording duration in seconds
        output_file: Output filename
    """
    print("=" * 50)
    print("Testing Mixed Recording (System + Microphone)")
    print("=" * 50)
    
    # Create recorder
    capture = AudioCapture(sample_rate=16000, channels=1, bit_depth=16)
    
    print(f"Audio Configuration:")
    print(f"  Sample rate: {capture.sample_rate}Hz")
    print(f"  Channels: {capture.channels} (Mono)")
    print(f"  Bit depth: {capture.bit_depth} bits")
    print(f"  Sources: System Audio + Microphone")
    
    # Recording configuration
    config = {
        'capture_system_audio': True,
        'capture_microphone': True,
        'exclude_current_process': True
    }
    
    try:
        print(f"\n▶ Starting mixed recording...")
        capture.start_recording(config)
        
        # Show progress
        for i in range(duration):
            print(f"  Recording... {i+1}/{duration} seconds", end='\r')
            time.sleep(1)
        print(f"  Recording... {duration}/{duration} seconds")
        
        print("■ Stopping recording...")
        capture.stop_recording()
        
        # Save to file
        print(f"💾 Saving to {output_file}...")
        capture.save_to_file(output_file)
        
        # Verify the output
        verify_audio_file(output_file)
        
        return True
        
    except Exception as e:
        print(f"❌ Error during recording: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_audio_file(filename):
    """Verify and display audio file properties"""
    if not os.path.exists(filename):
        print(f"❌ File not found: {filename}")
        return
    
    print(f"\n📊 Audio file properties:")
    try:
        with wave.open(filename, 'rb') as wf:
            print(f"  File: {filename}")
            print(f"  Sample rate: {wf.getframerate()}Hz")
            print(f"  Channels: {wf.getnchannels()}")
            print(f"  Bit depth: {wf.getsampwidth() * 8} bits")
            print(f"  Duration: {wf.getnframes() / wf.getframerate():.2f} seconds")
            print(f"  Frames: {wf.getnframes()}")
            
            file_size = os.path.getsize(filename)
            print(f"  File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
            
            # Calculate bitrate
            duration = wf.getnframes() / wf.getframerate()
            bitrate = (file_size * 8) / duration / 1000  # kbps
            print(f"  Bitrate: {bitrate:.0f} kbps")
            
    except Exception as e:
        print(f"❌ Error reading file: {e}")


def compare_recordings():
    """Compare different recording configurations"""
    print("\n" + "=" * 50)
    print("Comparing Recording Configurations")
    print("=" * 50)
    
    files = [
        ("test_48k_stereo.wav", "48kHz Stereo"),
        ("test_16k_mono.wav", "16kHz Mono"),
        ("test_microphone.wav", "Microphone 16kHz"),
        ("test_mixed.wav", "Mixed 16kHz")
    ]
    
    results = []
    for filename, label in files:
        if os.path.exists(filename):
            try:
                with wave.open(filename, 'rb') as wf:
                    file_size = os.path.getsize(filename)
                    duration = wf.getnframes() / wf.getframerate()
                    results.append({
                        'label': label,
                        'filename': filename,
                        'size': file_size,
                        'duration': duration,
                        'rate': wf.getframerate(),
                        'channels': wf.getnchannels()
                    })
            except:
                pass
    
    if not results:
        print("No recordings found to compare.")
        return
    
    print("\nFile size comparison:")
    baseline = results[0]['size'] if results else 1
    for r in results:
        ratio = baseline / r['size'] if r['size'] > 0 else 0
        print(f"  {r['label']:20} {r['size']:>10,} bytes  " + 
              f"({r['size']/1024:>6.1f} KB)  " +
              (f"{ratio:>4.1f}x" if ratio != 1 else "    "))
    
    print("\nConfiguration details:")
    for r in results:
        print(f"  {r['label']:20} {r['rate']}Hz, {r['channels']}ch, {r['duration']:.1f}s")


def cleanup_test_files():
    """Remove test audio files"""
    test_files = [
        "test_48k_stereo.wav",
        "test_16k_mono.wav", 
        "test_microphone.wav",
        "test_mixed.wav"
    ]
    
    removed = 0
    for filename in test_files:
        if os.path.exists(filename):
            os.remove(filename)
            removed += 1
    
    if removed > 0:
        print(f"\n🧹 Cleaned up {removed} test files")


def main():
    parser = argparse.ArgumentParser(description='Test audio recording functionality')
    parser.add_argument('--duration', type=int, default=5,
                       help='Recording duration in seconds (default: 5)')
    parser.add_argument('--test', choices=['16k', 'default', 'mic', 'mixed', 'all'],
                       default='all', help='Which test to run')
    parser.add_argument('--compare', action='store_true',
                       help='Compare recording configurations')
    parser.add_argument('--cleanup', action='store_true',
                       help='Remove test files after completion')
    
    args = parser.parse_args()
    
    print("Audio Recording Test Suite")
    print("=" * 50)
    
    success = True
    
    if args.test in ['16k', 'all']:
        success &= test_16k_mono_recording(args.duration)
        print()
    
    if args.test in ['default', 'all']:
        success &= test_default_recording(args.duration)
        print()
    
    if args.test in ['mic', 'all']:
        success &= test_microphone_recording(args.duration)
        print()
    
    if args.test in ['mixed', 'all']:
        success &= test_mixed_recording(args.duration)
        print()
    
    if args.compare or args.test == 'all':
        compare_recordings()
    
    if args.cleanup:
        cleanup_test_files()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ All tests completed successfully!")
    else:
        print("❌ Some tests failed!")
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())