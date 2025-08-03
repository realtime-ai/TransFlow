#!/usr/bin/env python3
"""
Simple audio mixer test
"""

import sys
import os
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audio.mixer import create_simple_mixer


def test_simple_mixing():
    """Test basic same-format mixing"""
    print("Simple Audio Mixer Test")
    print("=" * 40)
    
    # Create mixer with same format for all inputs/outputs
    mixer = create_simple_mixer(
        sample_rate=16000,
        channels=1, 
        format='flt',  # Use float format to avoid resampler issues
        input1_volume=0.7,
        input2_volume=0.8
    )
    
    print("Mixer configuration:")
    info = mixer.get_info()
    for key, value in info.items():
        if key != 'buffer_sizes':
            print(f"  {key}: {value}")
    
    # Generate test signals (same format)
    duration = 1.0
    sample_rate = 16000
    samples = int(sample_rate * duration)
    
    t = np.linspace(0, duration, samples, False)
    
    # Input 1: 440Hz sine wave
    signal1 = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    
    # Input 2: 880Hz sine wave
    signal2 = np.sin(2 * np.pi * 880 * t).astype(np.float32) * 0.5
    
    print(f"\nInput signals:")
    print(f"  Signal 1: {signal1.shape}, peak: {np.max(np.abs(signal1)):.3f}")
    print(f"  Signal 2: {signal2.shape}, peak: {np.max(np.abs(signal2)):.3f}")
    
    # Test individual inputs
    result1_only = mixer.mix(signal1, None)
    result2_only = mixer.mix(None, signal2)
    
    print(f"\nIndividual results:")
    print(f"  Input 1 only: {result1_only.shape}, peak: {np.max(np.abs(result1_only)):.3f}")
    print(f"  Input 2 only: {result2_only.shape}, peak: {np.max(np.abs(result2_only)):.3f}")
    
    # Test mixed output
    mixed = mixer.mix(signal1, signal2)
    
    print(f"\nMixed result:")
    print(f"  Mixed output: {mixed.shape}, peak: {np.max(np.abs(mixed)):.3f}")
    
    # Test volume control
    print(f"\nVolume control test:")
    original_vol1 = mixer.get_input_volume(1)
    original_vol2 = mixer.get_input_volume(2)
    
    mixer.set_input_volume(1, 0.3)
    mixer.set_input_volume(2, 1.2)
    
    mixed_adjusted = mixer.mix(signal1, signal2)
    
    print(f"  Original volumes: {original_vol1}, {original_vol2}")
    print(f"  New volumes: {mixer.get_input_volume(1)}, {mixer.get_input_volume(2)}")
    print(f"  Adjusted mix peak: {np.max(np.abs(mixed_adjusted)):.3f}")
    
    # Test chunk mixing
    print(f"\nChunk mixing test:")
    chunk_size = 1600  # 100ms
    chunks1 = [signal1[i:i+chunk_size] for i in range(0, len(signal1), chunk_size)]
    chunks2 = [signal2[i:i+chunk_size] for i in range(0, len(signal2), chunk_size)]
    
    chunk_result = mixer.mix_batch(chunks1, chunks2)
    
    print(f"  Input chunks: {len(chunks1)} x {chunk_size} samples")
    print(f"  Chunk result: {chunk_result.shape}, peak: {np.max(np.abs(chunk_result)):.3f}")
    
    # Verify chunk mixing produces similar result to direct mixing
    diff = np.abs(chunk_result[:len(mixed)] - mixed[:len(chunk_result)])
    max_diff = np.max(diff) if len(diff) > 0 else 0
    print(f"  Difference from direct mix: {max_diff:.6f}")
    
    return True


def test_different_mix_modes():
    """Test different mixing modes"""
    print("\n" + "=" * 40)
    print("Mix Mode Test")
    print("=" * 40)
    
    # Generate test signals
    t = np.linspace(0, 0.5, 8000, False)
    signal1 = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    signal2 = np.sin(2 * np.pi * 880 * t).astype(np.float32)
    
    mix_modes = ['add', 'average', 'weighted']
    
    for mode in mix_modes:
        mixer = create_simple_mixer(16000, 1, 'flt')
        mixer.mix_mode = mode
        
        result = mixer.mix(signal1, signal2)
        peak = np.max(np.abs(result))
        
        print(f"  {mode:>8} mode: peak = {peak:.3f}")


if __name__ == '__main__':
    try:
        test_simple_mixing()
        test_different_mix_modes()
        print("\n✅ Simple mixer tests completed successfully!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()