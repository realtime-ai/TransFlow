#!/usr/bin/env python3
"""
Test advanced audio mixer with jitter buffering capabilities
"""

import sys
import os
import numpy as np
import time
import threading
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audio.mixer import AudioMixer, create_professional_mixer, create_simple_mixer


def test_jitter_buffer_basic():
    """Test basic jitter buffer functionality"""
    print("=" * 50)
    print("Jitter Buffer Basic Test")
    print("=" * 50)
    
    # Create professional mixer with jitter buffering
    mixer = create_professional_mixer(
        sample_rate=16000,
        channels=1,
        format='flt',
        input1_volume=0.8,
        input2_volume=0.9,
        target_latency_ms=50.0,
        max_latency_ms=200.0
    )
    
    print("Mixer configuration:")
    info = mixer.get_info()
    print(f"  Jitter buffer enabled: {info['jitter_buffer_enabled']}")
    print(f"  Input 1: {info['input1']}")
    print(f"  Input 2: {info['input2']}")
    print(f"  Output: {info['output']}")
    
    # Generate test signals
    duration = 1.0
    sample_rate = 16000
    samples = int(sample_rate * duration)
    
    t = np.linspace(0, duration, samples, False)
    signal1 = np.sin(2 * np.pi * 440 * t).astype(np.float32)  # 440Hz
    signal2 = np.sin(2 * np.pi * 880 * t).astype(np.float32)  # 880Hz
    
    print(f"\nTest signals:")
    print(f"  Signal 1: {signal1.shape}, 440Hz")
    print(f"  Signal 2: {signal2.shape}, 880Hz")
    
    # Add signals to mixer with timestamps
    start_time = time.time()
    
    # Simulate chunks arriving at different times
    chunk_size = 1600  # 100ms chunks
    chunks1 = [signal1[i:i+chunk_size] for i in range(0, len(signal1), chunk_size)]
    chunks2 = [signal2[i:i+chunk_size] for i in range(0, len(signal2), chunk_size)]
    
    mixed_output = []
    
    for i, (chunk1, chunk2) in enumerate(zip(chunks1, chunks2)):
        # Simulate slight timing variations
        if i % 3 == 0:
            # Sometimes delay input 2
            mixed_chunk = mixer.mix(chunk1, None)
            time.sleep(0.001)  # 1ms delay
            mixed_chunk2 = mixer.mix(None, chunk2)
            if len(mixed_chunk2) > 0:
                mixed_output.append(mixed_chunk2)
        else:
            # Normal simultaneous mixing
            mixed_chunk = mixer.mix(chunk1, chunk2)
        
        if len(mixed_chunk) > 0:
            mixed_output.append(mixed_chunk)
    
    # Get buffer statistics
    print(f"\nBuffer statistics after processing:")
    stats = mixer.get_info()['buffer_stats']
    print(f"  Input 1 buffer: {stats['input1']}")
    print(f"  Input 2 buffer: {stats['input2']}")
    
    # Flush remaining data
    remaining = mixer.flush()
    if len(remaining) > 0:
        mixed_output.append(remaining)
    
    # Combine final output
    if mixed_output:
        final_output = np.concatenate(mixed_output)
        print(f"\nFinal output: {final_output.shape}")
        print(f"Output peak level: {np.max(np.abs(final_output)):.3f}")
    
    return True


def test_underrun_recovery():
    """Test buffer underrun recovery"""
    print("\n" + "=" * 50)
    print("Buffer Underrun Recovery Test")
    print("=" * 50)
    
    mixer = create_professional_mixer(
        sample_rate=16000,
        channels=1,
        format='s16',
        target_latency_ms=30.0,  # Small buffer for easier underrun
        max_latency_ms=100.0
    )
    
    # Generate test data
    chunk_size = 160  # 10ms chunks
    t_chunk = np.linspace(0, 0.01, chunk_size, False)
    
    mixed_chunks = []
    
    print("Simulating intermittent input streams...")
    
    for i in range(20):  # 200ms total
        # Generate chunks
        chunk1 = (np.sin(2 * np.pi * 440 * (t_chunk + i * 0.01)) * 16383).astype(np.int16)
        chunk2 = (np.sin(2 * np.pi * 880 * (t_chunk + i * 0.01)) * 16383).astype(np.int16)
        
        # Simulate missing chunks (network jitter simulation)
        if i % 7 == 0:
            # Skip input 1
            result = mixer.mix(None, chunk2)
            print(f"  Chunk {i:2d}: Input 1 missing")
        elif i % 11 == 0:
            # Skip input 2  
            result = mixer.mix(chunk1, None)
            print(f"  Chunk {i:2d}: Input 2 missing")
        elif i % 13 == 0:
            # Skip both (severe network issue)
            result = mixer.mix(None, None)
            print(f"  Chunk {i:2d}: Both inputs missing")
        else:
            # Normal operation
            result = mixer.mix(chunk1, chunk2)
            print(f"  Chunk {i:2d}: Normal operation")
        
        if len(result) > 0:
            mixed_chunks.append(result)
        
        # Small delay to simulate real-time processing
        time.sleep(0.001)
    
    # Final statistics
    stats = mixer.get_info()['buffer_stats']
    print(f"\nFinal buffer statistics:")
    print(f"  Input 1 underruns: {stats['input1']['underrun_count']}")
    print(f"  Input 1 overruns: {stats['input1']['overrun_count']}")
    print(f"  Input 2 underruns: {stats['input2']['underrun_count']}")
    print(f"  Input 2 overruns: {stats['input2']['overrun_count']}")
    
    # Combine output
    if mixed_chunks:
        combined_output = np.concatenate(mixed_chunks)
        print(f"Combined output: {combined_output.shape} samples")
    
    return True


def test_adaptive_buffering():
    """Test adaptive buffer size adjustment"""
    print("\n" + "=" * 50)
    print("Adaptive Buffering Test") 
    print("=" * 50)
    
    mixer = create_professional_mixer(
        sample_rate=16000,
        channels=1,
        format='flt',
        target_latency_ms=50.0
    )
    
    # Generate continuous test signal
    chunk_size = 1600  # 100ms
    
    print("Testing buffer adaptation over time...")
    
    target_history = []
    
    for phase in range(3):
        print(f"\nPhase {phase + 1}:")
        
        if phase == 0:
            print("  Stable input timing")
            jitter_range = 0.001  # 1ms jitter
        elif phase == 1:
            print("  High jitter input timing")
            jitter_range = 0.020  # 20ms jitter
        else:
            print("  Returning to stable timing")
            jitter_range = 0.002  # 2ms jitter
        
        for i in range(20):  # 2 seconds per phase
            # Generate chunk
            t = np.linspace(i * 0.1, (i + 1) * 0.1, chunk_size, False)
            signal = np.sin(2 * np.pi * 440 * t).astype(np.float32)
            
            # Add random jitter
            jitter = np.random.uniform(-jitter_range, jitter_range)
            time.sleep(max(0.001, 0.100 + jitter))  # 100ms base + jitter
            
            # Mix
            result = mixer.mix(signal, None)
            
            # Record buffer target size
            stats = mixer.get_info()['buffer_stats']['input1']
            target_samples = stats['target_buffer_samples']
            target_history.append(target_samples)
            
            if i % 5 == 0:
                print(f"    Chunk {i:2d}: Target buffer = {target_samples} samples "
                      f"({target_samples/16000*1000:.1f}ms)")
    
    print(f"\nBuffer adaptation summary:")
    print(f"  Initial target: {target_history[0]} samples")
    print(f"  Final target: {target_history[-1]} samples")
    print(f"  Min target: {min(target_history)} samples")
    print(f"  Max target: {max(target_history)} samples")
    
    return True


def test_comparison_simple_vs_professional():
    """Compare simple mixer vs professional mixer performance"""
    print("\n" + "=" * 50)
    print("Simple vs Professional Mixer Comparison")
    print("=" * 50)
    
    # Create both types of mixers
    simple_mixer = create_simple_mixer(16000, 1, 's16', 0.8, 0.8)
    pro_mixer = create_professional_mixer(16000, 1, 's16', 0.8, 0.8, 50.0)
    
    # Generate test data
    duration = 0.5
    sample_rate = 16000
    samples = int(sample_rate * duration)
    
    t = np.linspace(0, duration, samples, False)
    signal1 = (np.sin(2 * np.pi * 440 * t) * 16383).astype(np.int16)
    signal2 = (np.sin(2 * np.pi * 880 * t) * 16383).astype(np.int16)
    
    # Test both mixers
    chunk_size = 1600  # 100ms
    chunks1 = [signal1[i:i+chunk_size] for i in range(0, len(signal1), chunk_size)]
    chunks2 = [signal2[i:i+chunk_size] for i in range(0, len(signal2), chunk_size)]
    
    print("Processing with simple mixer...")
    simple_start = time.time()
    simple_output = simple_mixer.mix_batch(chunks1, chunks2)
    simple_time = time.time() - simple_start
    
    print("Processing with professional mixer...")
    pro_start = time.time()
    pro_output = pro_mixer.mix_batch(chunks1, chunks2)
    pro_time = time.time() - pro_start
    
    print(f"\nResults:")
    print(f"  Simple mixer:")
    print(f"    Processing time: {simple_time*1000:.2f}ms")
    print(f"    Output shape: {simple_output.shape}")
    print(f"    Peak level: {np.max(np.abs(simple_output))}")
    
    print(f"  Professional mixer:")
    print(f"    Processing time: {pro_time*1000:.2f}ms") 
    print(f"    Output shape: {pro_output.shape}")
    print(f"    Peak level: {np.max(np.abs(pro_output))}")
    
    # Compare output quality
    if simple_output.shape == pro_output.shape:
        diff = np.abs(simple_output.astype(np.float32) - pro_output.astype(np.float32))
        max_diff = np.max(diff)
        avg_diff = np.mean(diff)
        print(f"    Output difference: max={max_diff:.1f}, avg={avg_diff:.3f}")
    
    # Buffer statistics for professional mixer
    pro_stats = pro_mixer.get_info()
    if 'buffer_stats' in pro_stats:
        print(f"  Professional mixer buffer stats:")
        for input_name, stats in pro_stats['buffer_stats'].items():
            print(f"    {input_name}: {stats['total_samples']} samples, "
                  f"{stats['latency_ms']:.1f}ms latency")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Test advanced audio mixer jitter buffering')
    parser.add_argument('--test', choices=['basic', 'underrun', 'adaptive', 'comparison', 'all'],
                       default='all', help='Which test to run')
    
    args = parser.parse_args()
    
    print("Advanced Audio Mixer Jitter Buffer Test Suite")
    print("=" * 60)
    
    success = True
    
    try:
        if args.test in ['basic', 'all']:
            success &= test_jitter_buffer_basic()
        
        if args.test in ['underrun', 'all']:
            success &= test_underrun_recovery()
        
        if args.test in ['adaptive', 'all']:
            success &= test_adaptive_buffering()
        
        if args.test in ['comparison', 'all']:
            success &= test_comparison_simple_vs_professional()
            
    except KeyboardInterrupt:
        print("\n\n⏹ Test interrupted by user")
        success = False
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✅ All jitter buffer tests completed successfully!")
    else:
        print("❌ Some tests failed!")
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())