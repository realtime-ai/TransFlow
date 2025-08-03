#!/usr/bin/env python3
"""
Test audio mixer functionality
"""

import sys
import os
import numpy as np
import wave

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audio.mixer import AudioMixer, create_simple_mixer


def test_basic_mixing():
    """Test basic audio mixing functionality"""
    print("=" * 50)
    print("Basic Audio Mixing Test")
    print("=" * 50)
    
    # Create a simple mixer: 16kHz mono
    mixer = create_simple_mixer(
        sample_rate=16000,
        channels=1,
        format='flt',
        input1_volume=0.7,
        input2_volume=0.8
    )
    
    # Generate test signals
    duration = 2.0  # 2 seconds
    sample_rate = 16000
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Input 1: 440Hz sine wave (A4 note)
    freq1 = 440.0
    signal1 = np.sin(2 * np.pi * freq1 * t).astype(np.float32)
    
    # Input 2: 880Hz sine wave (A5 note) 
    freq2 = 880.0
    signal2 = np.sin(2 * np.pi * freq2 * t).astype(np.float32) * 0.5  # Lower amplitude
    
    print(f"Input 1: {signal1.shape} @ {freq1}Hz")
    print(f"Input 2: {signal2.shape} @ {freq2}Hz")
    
    # Mix signals
    mixed = mixer.mix(signal1, signal2)
    
    print(f"Mixed output: {mixed.shape}")
    print(f"Mixed peak level: {np.max(np.abs(mixed)):.3f}")
    
    # Test chunk mixing
    chunk_size = 1600  # 100ms chunks
    chunks1 = [signal1[i:i+chunk_size] for i in range(0, len(signal1), chunk_size)]
    chunks2 = [signal2[i:i+chunk_size] for i in range(0, len(signal2), chunk_size)]
    
    print(f"\nChunk mixing: {len(chunks1)} chunks")
    chunk_mixed = mixer.mix_batch(chunks1, chunks2)
    print(f"Chunk mixed output: {chunk_mixed.shape}")
    
    return True


def test_format_conversion():
    """Test different format conversions"""
    print("\n" + "=" * 50)
    print("Format Conversion Test")
    print("=" * 50)
    
    # Create mixer with different input/output formats
    mixer = AudioMixer(
        # Input 1: 48kHz stereo float32
        input1_sample_rate=48000,
        input1_channels=2, 
        input1_format='flt',
        input1_volume=1.0,
        
        # Input 2: 16kHz mono int16
        input2_sample_rate=16000,
        input2_channels=1,
        input2_format='s16',
        input2_volume=1.0,
        
        # Output: 24kHz stereo int16
        output_sample_rate=24000,
        output_channels=2,
        output_format='s16',
        
        mix_mode='average'
    )
    
    print("Mixer configuration:")
    info = mixer.get_info()
    print(f"  Input 1: {info['input1']}")
    print(f"  Input 2: {info['input2']}")
    print(f"  Output:  {info['output']}")
    
    # Generate test data
    duration = 1.0
    
    # Input 1: 48kHz stereo float32
    t1 = np.linspace(0, duration, int(48000 * duration), False)
    mono1 = np.sin(2 * np.pi * 1000 * t1).astype(np.float32)
    stereo1 = np.column_stack([mono1, mono1 * 0.8])
    
    # Input 2: 16kHz mono int16
    t2 = np.linspace(0, duration, int(16000 * duration), False)
    mono2 = (np.sin(2 * np.pi * 500 * t2) * 16383).astype(np.int16)
    
    print(f"\nInput 1 shape: {stereo1.shape}, dtype: {stereo1.dtype}")
    print(f"Input 2 shape: {mono2.shape}, dtype: {mono2.dtype}")
    
    # Mix
    result = mixer.mix(stereo1, mono2)
    
    print(f"Mixed result: {result.shape}, dtype: {result.dtype}")
    print(f"Expected output samples: {24000 * duration}")
    print(f"Actual output samples: {len(result)}")
    
    return True


def test_realtime_mixing():
    """Test real-time chunk-by-chunk mixing"""
    print("\n" + "=" * 50)
    print("Real-time Mixing Test")
    print("=" * 50)
    
    # Create mixer for real-time processing
    mixer = AudioMixer(
        input1_sample_rate=48000,
        input1_channels=1,
        input1_format='s16',
        input1_volume=0.6,
        
        input2_sample_rate=16000,
        input2_channels=1, 
        input2_format='s16',
        input2_volume=0.8,
        
        output_sample_rate=48000,
        output_channels=1,
        output_format='s16',
        
        mix_mode='add',
        auto_gain_control=True
    )
    
    # Simulate real-time processing
    chunk_duration = 0.02  # 20ms chunks
    total_duration = 1.0   # 1 second total
    
    input1_chunk_size = int(48000 * chunk_duration)
    input2_chunk_size = int(16000 * chunk_duration)
    output_chunk_size = int(48000 * chunk_duration)
    
    print(f"Chunk sizes: Input1={input1_chunk_size}, Input2={input2_chunk_size}, Output={output_chunk_size}")
    
    output_chunks = []
    
    for i in range(int(total_duration / chunk_duration)):
        # Generate chunks
        t1 = np.linspace(i * chunk_duration, (i + 1) * chunk_duration, input1_chunk_size, False)
        chunk1 = (np.sin(2 * np.pi * 600 * t1) * 16383).astype(np.int16)
        
        t2 = np.linspace(i * chunk_duration, (i + 1) * chunk_duration, input2_chunk_size, False)  
        chunk2 = (np.sin(2 * np.pi * 300 * t2) * 16383).astype(np.int16)
        
        # Mix chunk
        mixed_chunk = mixer.mix(chunk1, chunk2, output_samples=output_chunk_size)
        output_chunks.append(mixed_chunk)
        
        if i % 10 == 0:
            print(f"  Processed chunk {i}, output shape: {mixed_chunk.shape}")
    
    # Combine all chunks
    final_output = np.concatenate(output_chunks)
    print(f"\nFinal output: {final_output.shape}")
    print(f"AGC gain: {mixer.get_info()['agc_gain']:.3f}")
    
    return True


def test_volume_control():
    """Test volume control functionality"""
    print("\n" + "=" * 50)
    print("Volume Control Test")
    print("=" * 50)
    
    mixer = create_simple_mixer(16000, 1, 's16')
    
    # Generate test signal
    t = np.linspace(0, 1, 16000, False)
    signal = (np.sin(2 * np.pi * 440 * t) * 16383).astype(np.int16)
    
    # Test different volume levels
    volumes = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
    
    print("Volume level tests:")
    for vol in volumes:
        mixer.set_input_volume(1, vol)
        mixer.set_input_volume(2, 0.0)  # Mute input 2
        
        result = mixer.mix(signal, None)
        peak = np.max(np.abs(result)) if len(result) > 0 else 0
        
        print(f"  Volume {vol:0.2f}: Peak = {peak:5.0f} ({peak/16383*100:0.1f}%)")
    
    return True


def save_test_audio():
    """Save test audio files for verification"""
    print("\n" + "=" * 50)
    print("Saving Test Audio Files")
    print("=" * 50)
    
    mixer = create_simple_mixer(16000, 1, 's16', 0.7, 0.8)
    
    # Generate 3-second test signals
    duration = 3.0
    sample_rate = 16000
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Input 1: 440Hz tone
    signal1 = (np.sin(2 * np.pi * 440 * t) * 16383).astype(np.int16)
    
    # Input 2: 880Hz tone  
    signal2 = (np.sin(2 * np.pi * 880 * t) * 16383).astype(np.int16)
    
    # Mix signals
    mixed = mixer.mix(signal1, signal2)
    
    # Save individual signals
    with wave.open("test_input1_440hz.wav", "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(signal1.tobytes())
    
    with wave.open("test_input2_880hz.wav", "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(signal2.tobytes())
    
    # Save mixed signal
    with wave.open("test_mixed_output.wav", "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(mixed.tobytes())
    
    print(f"Saved test files:")
    print(f"  test_input1_440hz.wav ({len(signal1)} samples)")
    print(f"  test_input2_880hz.wav ({len(signal2)} samples)")  
    print(f"  test_mixed_output.wav ({len(mixed)} samples)")
    
    return True


def cleanup_test_files():
    """Remove test audio files"""
    test_files = [
        "test_input1_440hz.wav",
        "test_input2_880hz.wav", 
        "test_mixed_output.wav"
    ]
    
    removed = 0
    for filename in test_files:
        if os.path.exists(filename):
            os.remove(filename)
            removed += 1
    
    if removed > 0:
        print(f"\n🧹 Cleaned up {removed} test files")


def main():
    print("Audio Mixer Test Suite")
    print("=" * 50)
    
    success = True
    
    try:
        success &= test_basic_mixing()
        success &= test_format_conversion()
        success &= test_realtime_mixing()
        success &= test_volume_control()
        success &= save_test_audio()
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    finally:
        cleanup_test_files()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ All mixer tests completed successfully!")
    else:
        print("❌ Some tests failed!")
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())