#!/usr/bin/env python3
"""
Audio mixer for combining two PCM audio streams into one output stream.

Features:
- Two PCM audio inputs with independent format configuration
- One PCM audio output with configurable format
- Sample rate conversion using high-quality resampler
- Channel conversion (mono/stereo)
- Format conversion (int16/float32)
- Volume control per input channel
- Real-time mixing capability
"""

import numpy as np
from typing import Optional, Union, Tuple, Dict, Any
import logging
import time
from collections import deque

try:
    from .resampler import AudioResampler
except ImportError:
    # Handle when running as main module
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from resampler import AudioResampler

logger = logging.getLogger(__name__)


class AudioBuffer:
    """
    Advanced audio buffer with time alignment and jitter handling.
    
    Features:
    - Time-stamped audio chunks
    - Jitter buffering for smooth playback
    - Automatic buffer size adjustment
    - Latency compensation
    """
    
    def __init__(
        self,
        sample_rate: int,
        channels: int,
        format_str: str,
        target_buffer_ms: float = 100.0,  # Target buffer in milliseconds
        max_buffer_ms: float = 500.0,     # Maximum buffer in milliseconds
        min_buffer_ms: float = 20.0       # Minimum buffer in milliseconds
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.format_str = format_str
        
        # Buffer settings
        self.target_buffer_samples = int(sample_rate * target_buffer_ms / 1000.0)
        self.max_buffer_samples = int(sample_rate * max_buffer_ms / 1000.0)
        self.min_buffer_samples = int(sample_rate * min_buffer_ms / 1000.0)
        
        # Time-stamped buffer: (timestamp, audio_data)
        self.buffer = deque()
        self.total_samples = 0
        
        # Statistics
        self.underrun_count = 0
        self.overrun_count = 0
        self.last_timestamp = None
        
        # Adaptive buffer control
        self.adaptive_enabled = True
        self.buffer_health_history = deque(maxlen=100)
        
    def add_chunk(self, audio_data: np.ndarray, timestamp: Optional[float] = None):
        """Add audio chunk with timestamp."""
        if timestamp is None:
            timestamp = time.time()
            
        # Check for buffer overrun
        if self.total_samples > self.max_buffer_samples:
            # Remove old chunks to prevent excessive buffering
            while self.total_samples > self.target_buffer_samples and self.buffer:
                old_timestamp, old_data = self.buffer.popleft()
                self.total_samples -= len(old_data)
                self.overrun_count += 1
                logger.debug(f"Buffer overrun, dropped {len(old_data)} samples")
        
        self.buffer.append((timestamp, audio_data))
        self.total_samples += len(audio_data)
        self.last_timestamp = timestamp
        
        # Update buffer health
        buffer_health = self.total_samples / self.target_buffer_samples
        self.buffer_health_history.append(buffer_health)
        
    def get_samples(self, count: int) -> Tuple[np.ndarray, bool]:
        """
        Get specified number of samples from buffer.
        
        Returns:
            Tuple[np.ndarray, bool]: (audio_data, is_underrun)
        """
        if self.total_samples < count:
            # Buffer underrun
            self.underrun_count += 1
            
            # Return all available samples + padding
            available_data = []
            while self.buffer:
                timestamp, data = self.buffer.popleft()
                available_data.append(data)
                
            if available_data:
                available_audio = np.concatenate(available_data)
                self.total_samples = 0
                
                # Pad with zeros if needed
                shortfall = count - len(available_audio)
                if shortfall > 0:
                    if self.channels == 1:
                        padding = np.zeros(shortfall, dtype=available_audio.dtype)
                        result = np.concatenate([available_audio, padding])
                    else:
                        padding = np.zeros((shortfall, self.channels), dtype=available_audio.dtype)
                        result = np.concatenate([available_audio, padding], axis=0)
                else:
                    result = available_audio[:count]
                    
                logger.debug(f"Buffer underrun, padded {shortfall} samples")
                return result, True
            else:
                # Empty buffer, return zeros
                if self.channels == 1:
                    return np.zeros(count, dtype=self._get_numpy_dtype()), True
                else:
                    return np.zeros((count, self.channels), dtype=self._get_numpy_dtype()), True
        
        # Normal case: sufficient samples available
        extracted_data = []
        remaining_count = count
        
        while remaining_count > 0 and self.buffer:
            timestamp, data = self.buffer[0]
            
            if len(data) <= remaining_count:
                # Use entire chunk
                self.buffer.popleft()
                extracted_data.append(data)
                remaining_count -= len(data)
                self.total_samples -= len(data)
            else:
                # Split chunk
                needed_data = data[:remaining_count]
                remaining_data = data[remaining_count:]
                
                # Update buffer with remaining data
                self.buffer[0] = (timestamp, remaining_data)
                extracted_data.append(needed_data)
                self.total_samples -= remaining_count
                remaining_count = 0
        
        if extracted_data:
            result = np.concatenate(extracted_data)
        else:
            if self.channels == 1:
                result = np.zeros(count, dtype=self._get_numpy_dtype())
            else:
                result = np.zeros((count, self.channels), dtype=self._get_numpy_dtype())
                
        return result, False
    
    def get_buffer_level(self) -> float:
        """Get current buffer level as ratio of target."""
        return self.total_samples / self.target_buffer_samples if self.target_buffer_samples > 0 else 0.0
    
    def get_latency_ms(self) -> float:
        """Get current buffer latency in milliseconds."""
        return (self.total_samples / self.sample_rate) * 1000.0
    
    def adjust_target_buffer(self):
        """Adaptively adjust target buffer size based on performance."""
        if not self.adaptive_enabled or len(self.buffer_health_history) < 10:
            return
            
        # Calculate buffer health statistics
        health_values = list(self.buffer_health_history)
        avg_health = np.mean(health_values)
        health_variance = np.var(health_values)
        
        # Adjust target based on stability
        if health_variance > 0.5:  # High variance, increase buffer
            new_target = min(self.target_buffer_samples * 1.1, self.max_buffer_samples)
        elif health_variance < 0.1 and avg_health > 1.2:  # Stable and high, decrease buffer
            new_target = max(self.target_buffer_samples * 0.95, self.min_buffer_samples)
        else:
            return  # No adjustment needed
            
        self.target_buffer_samples = int(new_target)
        logger.debug(f"Adjusted target buffer to {self.target_buffer_samples} samples "
                    f"({self.target_buffer_samples/self.sample_rate*1000:.1f}ms)")
    
    def clear(self):
        """Clear all buffered data."""
        self.buffer.clear()
        self.total_samples = 0
        
    def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        return {
            'total_samples': self.total_samples,
            'buffer_level': self.get_buffer_level(),
            'latency_ms': self.get_latency_ms(),
            'target_buffer_samples': self.target_buffer_samples,
            'underrun_count': self.underrun_count,
            'overrun_count': self.overrun_count,
            'chunks_in_buffer': len(self.buffer)
        }
    
    def _get_numpy_dtype(self):
        """Get numpy dtype for format string."""
        if self.format_str == 'flt':
            return np.float32
        elif self.format_str == 's16':
            return np.int16
        elif self.format_str == 's32':
            return np.int32
        else:
            return np.float32


class AudioMixer:
    """
    Audio mixer for combining two PCM audio streams.
    
    Supports different input formats and converts to unified output format.
    """
    
    def __init__(
        self,
        # Input 1 configuration
        input1_sample_rate: int = 48000,
        input1_channels: int = 2,
        input1_format: str = 's16',  # 's16', 's32', 'flt'
        input1_volume: float = 1.0,
        
        # Input 2 configuration  
        input2_sample_rate: int = 48000,
        input2_channels: int = 2,
        input2_format: str = 's16',
        input2_volume: float = 1.0,
        
        # Output configuration
        output_sample_rate: int = 48000,
        output_channels: int = 2,
        output_format: str = 's16',
        
        # Mixing configuration
        mix_mode: str = 'add',  # 'add', 'average', 'weighted'
        auto_gain_control: bool = False,
        
        # Advanced buffering configuration
        enable_jitter_buffer: bool = True,
        target_buffer_ms: float = 100.0,  # Target buffer latency in milliseconds
        max_buffer_ms: float = 500.0,     # Maximum buffer latency
        min_buffer_ms: float = 20.0,      # Minimum buffer latency
        sync_tolerance_ms: float = 10.0   # Sync tolerance between inputs
    ):
        """
        Initialize audio mixer.
        
        Args:
            input1_sample_rate: Sample rate for input 1 (Hz)
            input1_channels: Channel count for input 1
            input1_format: Format for input 1 ('s16', 's32', 'flt')
            input1_volume: Volume multiplier for input 1 (0.0-2.0)
            
            input2_sample_rate: Sample rate for input 2 (Hz) 
            input2_channels: Channel count for input 2
            input2_format: Format for input 2 ('s16', 's32', 'flt')
            input2_volume: Volume multiplier for input 2 (0.0-2.0)
            
            output_sample_rate: Output sample rate (Hz)
            output_channels: Output channel count
            output_format: Output format ('s16', 's32', 'flt')
            
            mix_mode: Mixing algorithm ('add', 'average', 'weighted')
            auto_gain_control: Enable automatic gain control
            
            enable_jitter_buffer: Enable advanced jitter buffering
            target_buffer_ms: Target buffer latency in milliseconds
            max_buffer_ms: Maximum buffer latency in milliseconds
            min_buffer_ms: Minimum buffer latency in milliseconds
            sync_tolerance_ms: Tolerance for input synchronization
        """
        # Store configuration
        self.input1_config = {
            'sample_rate': input1_sample_rate,
            'channels': input1_channels,
            'format': input1_format,
            'volume': input1_volume
        }
        
        self.input2_config = {
            'sample_rate': input2_sample_rate,
            'channels': input2_channels,
            'format': input2_format,
            'volume': input2_volume
        }
        
        self.output_config = {
            'sample_rate': output_sample_rate,
            'channels': output_channels,
            'format': output_format
        }
        
        self.mix_mode = mix_mode
        self.auto_gain_control = auto_gain_control
        self.enable_jitter_buffer = enable_jitter_buffer
        self.sync_tolerance_ms = sync_tolerance_ms
        
        # Create resamplers for each input if needed
        self.resampler1 = None
        self.resampler2 = None
        
        if (input1_sample_rate != output_sample_rate or 
            input1_channels != output_channels or 
            input1_format != output_format):
            self.resampler1 = AudioResampler(
                input_sample_rate=input1_sample_rate,
                output_sample_rate=output_sample_rate,
                input_channels=input1_channels,
                output_channels=output_channels,
                input_format=input1_format,
                output_format=output_format
            )
            
        if (input2_sample_rate != output_sample_rate or 
            input2_channels != output_channels or 
            input2_format != output_format):
            self.resampler2 = AudioResampler(
                input_sample_rate=input2_sample_rate,
                output_sample_rate=output_sample_rate,
                input_channels=input2_channels,
                output_channels=output_channels,
                input_format=input2_format,
                output_format=output_format
            )
        
        # Advanced audio buffers
        if self.enable_jitter_buffer:
            self.input1_buffer = AudioBuffer(
                sample_rate=output_sample_rate,
                channels=output_channels,
                format_str=output_format,
                target_buffer_ms=target_buffer_ms,
                max_buffer_ms=max_buffer_ms,
                min_buffer_ms=min_buffer_ms
            )
            self.input2_buffer = AudioBuffer(
                sample_rate=output_sample_rate,
                channels=output_channels,
                format_str=output_format,
                target_buffer_ms=target_buffer_ms,
                max_buffer_ms=max_buffer_ms,
                min_buffer_ms=min_buffer_ms
            )
        else:
            # Fallback to simple list buffers
            self.input1_buffer = []
            self.input2_buffer = []
        
        # AGC state
        self.agc_gain = 1.0
        self.agc_peak_history = []
        self.agc_history_size = 100
        
        logger.info(
            f"AudioMixer initialized:\n"
            f"  Input 1: {input1_sample_rate}Hz/{input1_channels}ch/{input1_format} vol={input1_volume}\n"
            f"  Input 2: {input2_sample_rate}Hz/{input2_channels}ch/{input2_format} vol={input2_volume}\n"
            f"  Output:  {output_sample_rate}Hz/{output_channels}ch/{output_format}\n"
            f"  Mix mode: {mix_mode}, AGC: {auto_gain_control}"
        )
    
    def set_input_volume(self, input_id: int, volume: float):
        """
        Set volume for input channel.
        
        Args:
            input_id: Input channel (1 or 2)
            volume: Volume multiplier (0.0-2.0)
        """
        volume = max(0.0, min(2.0, volume))
        
        if input_id == 1:
            self.input1_config['volume'] = volume
        elif input_id == 2:
            self.input2_config['volume'] = volume
        else:
            raise ValueError("input_id must be 1 or 2")
        
        logger.debug(f"Set input {input_id} volume to {volume}")
    
    def get_input_volume(self, input_id: int) -> float:
        """Get volume for input channel."""
        if input_id == 1:
            return self.input1_config['volume']
        elif input_id == 2:
            return self.input2_config['volume']
        else:
            raise ValueError("input_id must be 1 or 2")
    
    def mix(
        self, 
        input1_data: Optional[Union[np.ndarray, bytes]] = None,
        input2_data: Optional[Union[np.ndarray, bytes]] = None,
        output_samples: Optional[int] = None
    ) -> np.ndarray:
        """
        Mix audio data from two inputs.
        
        Args:
            input1_data: Audio data for input 1
            input2_data: Audio data for input 2
            output_samples: Desired output sample count (optional)
            
        Returns:
            np.ndarray: Mixed audio output
        """
        # Process input 1
        processed1 = None
        if input1_data is not None:
            processed1 = self._process_input(input1_data, 1)
        
        # Process input 2
        processed2 = None
        if input2_data is not None:
            processed2 = self._process_input(input2_data, 2)
        
        # Add to buffers with timestamp
        current_timestamp = time.time()
        
        if self.enable_jitter_buffer:
            # Advanced buffering with jitter control
            if processed1 is not None:
                self.input1_buffer.add_chunk(processed1, current_timestamp)
            if processed2 is not None:
                self.input2_buffer.add_chunk(processed2, current_timestamp)
            
            # Adaptive buffer adjustment
            self.input1_buffer.adjust_target_buffer()
            self.input2_buffer.adjust_target_buffer()
            
            # Determine output length based on buffer state
            if output_samples is None:
                if input1_data is None and input2_data is None:
                    output_samples = 0
                elif input1_data is None:
                    output_samples = min(1024, self.input2_buffer.total_samples)  # Default chunk size
                elif input2_data is None:
                    output_samples = min(1024, self.input1_buffer.total_samples)
                else:
                    # Both inputs provided, use optimal chunk size
                    min_buffer_samples = min(
                        self.input1_buffer.total_samples,
                        self.input2_buffer.total_samples
                    )
                    output_samples = min(1024, max(256, min_buffer_samples))
            
            if output_samples <= 0:
                return np.array([], dtype=self._get_numpy_dtype(self.output_config['format']))
            
            # Extract samples with underrun detection
            samples1, underrun1 = self.input1_buffer.get_samples(output_samples)
            samples2, underrun2 = self.input2_buffer.get_samples(output_samples)
            
            # Log buffer issues
            if underrun1:
                logger.debug("Input 1 buffer underrun")
            if underrun2:
                logger.debug("Input 2 buffer underrun")
                
        else:
            # Simple buffering (backward compatibility)
            if processed1 is not None:
                self.input1_buffer.extend(processed1)
            if processed2 is not None:
                self.input2_buffer.extend(processed2)
            
            # Determine output length
            if output_samples is None:
                if input1_data is None and input2_data is None:
                    output_samples = 0
                elif input1_data is None:
                    output_samples = len(self.input2_buffer) if self.input2_buffer else 0
                elif input2_data is None:
                    output_samples = len(self.input1_buffer) if self.input1_buffer else 0
                else:
                    # Both inputs provided, use minimum
                    output_samples = min(
                        len(self.input1_buffer) if self.input1_buffer else 0,
                        len(self.input2_buffer) if self.input2_buffer else 0
                    )
            
            if output_samples <= 0:
                return np.array([], dtype=self._get_numpy_dtype(self.output_config['format']))
            
            # Extract samples from simple buffers
            samples1 = self._extract_samples(self.input1_buffer, output_samples)
            samples2 = self._extract_samples(self.input2_buffer, output_samples)
        
        # Perform mixing
        mixed_output = self._mix_samples(samples1, samples2)
        
        # Apply AGC if enabled
        if self.auto_gain_control:
            mixed_output = self._apply_agc(mixed_output)
        
        return mixed_output
    
    def mix_batch(
        self,
        input1_chunks: list,
        input2_chunks: list
    ) -> np.ndarray:
        """
        Mix multiple audio chunks.
        
        Args:
            input1_chunks: List of audio chunks for input 1
            input2_chunks: List of audio chunks for input 2
            
        Returns:
            np.ndarray: Combined mixed audio output
        """
        output_chunks = []
        
        # Ensure same number of chunks
        max_chunks = max(len(input1_chunks), len(input2_chunks))
        
        for i in range(max_chunks):
            chunk1 = input1_chunks[i] if i < len(input1_chunks) else None
            chunk2 = input2_chunks[i] if i < len(input2_chunks) else None
            
            mixed_chunk = self.mix(chunk1, chunk2)
            if len(mixed_chunk) > 0:
                output_chunks.append(mixed_chunk)
        
        if output_chunks:
            return np.concatenate(output_chunks, axis=0)
        else:
            return np.array([], dtype=self._get_numpy_dtype(self.output_config['format']))
    
    def flush(self) -> np.ndarray:
        """
        Flush remaining data from internal buffers.
        
        Returns:
            np.ndarray: Remaining mixed audio data
        """
        if self.enable_jitter_buffer:
            # Get remaining samples from advanced buffers
            remaining_samples = max(
                self.input1_buffer.total_samples,
                self.input2_buffer.total_samples
            )
            
            if remaining_samples == 0:
                return np.array([], dtype=self._get_numpy_dtype(self.output_config['format']))
            
            # Extract all remaining samples
            samples1, _ = self.input1_buffer.get_samples(remaining_samples)
            samples2, _ = self.input2_buffer.get_samples(remaining_samples)
        else:
            # Simple buffer handling
            remaining_samples = max(
                len(self.input1_buffer),
                len(self.input2_buffer)
            )
            
            if remaining_samples == 0:
                return np.array([], dtype=self._get_numpy_dtype(self.output_config['format']))
            
            # Mix remaining data
            samples1 = self._extract_samples(self.input1_buffer, remaining_samples)
            samples2 = self._extract_samples(self.input2_buffer, remaining_samples)
        
        mixed_output = self._mix_samples(samples1, samples2)
        
        # Flush resamplers
        if self.resampler1:
            flushed1 = self.resampler1.flush()
            if flushed1 is not None and len(flushed1) > 0:
                # Add flushed data to output
                if len(mixed_output) > 0:
                    mixed_output = np.concatenate([mixed_output, flushed1])
                else:
                    mixed_output = flushed1
        
        if self.resampler2:
            flushed2 = self.resampler2.flush()
            if flushed2 is not None and len(flushed2) > 0:
                # Mix with existing output
                if len(mixed_output) > 0:
                    min_len = min(len(mixed_output), len(flushed2))
                    mixed_output[:min_len] = self._mix_samples(
                        mixed_output[:min_len], 
                        flushed2[:min_len]
                    )
                    if len(flushed2) > min_len:
                        mixed_output = np.concatenate([mixed_output, flushed2[min_len:]])
                else:
                    mixed_output = flushed2
        
        return mixed_output
    
    def _process_input(self, data: Union[np.ndarray, bytes], input_id: int) -> np.ndarray:
        """Process input data through resampler if needed."""
        # Convert to numpy array
        if isinstance(data, bytes):
            if input_id == 1:
                format_str = self.input1_config['format']
            else:
                format_str = self.input2_config['format']
            data = self._bytes_to_numpy(data, format_str)
        
        # Apply volume
        if input_id == 1:
            volume = self.input1_config['volume']
            resampler = self.resampler1
        else:
            volume = self.input2_config['volume']
            resampler = self.resampler2
        
        if volume != 1.0:
            data = data * volume
        
        # Resample if needed
        if resampler:
            resampled_data, _ = resampler.resample(data)
            return resampled_data
        else:
            return data
    
    def _extract_samples(self, buffer: list, count: int) -> np.ndarray:
        """Extract samples from buffer."""
        if not buffer or count <= 0:
            # Return zeros with proper shape
            output_channels = self.output_config['channels']
            if output_channels == 1:
                return np.zeros(count, dtype=self._get_numpy_dtype(self.output_config['format']))
            else:
                return np.zeros((count, output_channels), dtype=self._get_numpy_dtype(self.output_config['format']))
        
        # Concatenate all buffer data first
        if len(buffer) > 0:
            if isinstance(buffer[0], np.ndarray) and buffer[0].ndim > 1:
                # Multi-dimensional arrays
                full_data = np.concatenate(buffer, axis=0)
            else:
                # 1D arrays or scalars
                full_data = np.concatenate([np.atleast_1d(x) for x in buffer])
        else:
            output_channels = self.output_config['channels']
            if output_channels == 1:
                return np.zeros(count, dtype=self._get_numpy_dtype(self.output_config['format']))
            else:
                return np.zeros((count, output_channels), dtype=self._get_numpy_dtype(self.output_config['format']))
        
        # Extract requested samples
        if len(full_data) >= count:
            samples = full_data[:count]
            # Update buffer with remaining data
            remaining = full_data[count:]
            buffer.clear()
            if len(remaining) > 0:
                buffer.extend(remaining)
        else:
            # Not enough samples, pad with zeros
            samples = full_data
            buffer.clear()
            
            # Add padding if needed
            shortfall = count - len(samples)
            if shortfall > 0:
                if samples.ndim == 1:
                    padding = np.zeros(shortfall, dtype=samples.dtype)
                    samples = np.concatenate([samples, padding])
                else:
                    padding = np.zeros((shortfall, samples.shape[1]), dtype=samples.dtype)
                    samples = np.concatenate([samples, padding], axis=0)
        
        return samples
    
    def _mix_samples(self, samples1: np.ndarray, samples2: np.ndarray) -> np.ndarray:
        """Mix two sample arrays."""
        # Handle empty inputs
        if len(samples1) == 0 and len(samples2) == 0:
            return np.array([], dtype=self._get_numpy_dtype(self.output_config['format']))
        elif len(samples1) == 0:
            return samples2
        elif len(samples2) == 0:
            return samples1
        
        # Ensure proper shapes for mixing
        output_channels = self.output_config['channels']
        
        # Convert to output shape if needed
        if samples1.ndim == 1 and output_channels > 1:
            if len(samples1) % output_channels == 0:
                # Interleaved format
                samples1 = samples1.reshape(-1, output_channels)
            else:
                # Mono to multi-channel (duplicate)
                samples1 = np.tile(samples1.reshape(-1, 1), (1, output_channels))
        elif samples1.ndim == 2 and output_channels == 1:
            # Multi-channel to mono (average)
            samples1 = np.mean(samples1, axis=1)
        
        if samples2.ndim == 1 and output_channels > 1:
            if len(samples2) % output_channels == 0:
                # Interleaved format
                samples2 = samples2.reshape(-1, output_channels)
            else:
                # Mono to multi-channel (duplicate)
                samples2 = np.tile(samples2.reshape(-1, 1), (1, output_channels))
        elif samples2.ndim == 2 and output_channels == 1:
            # Multi-channel to mono (average)
            samples2 = np.mean(samples2, axis=1)
        
        # Now both arrays should have compatible shapes
        len1 = len(samples1)
        len2 = len(samples2)
        min_len = min(len1, len2)
        max_len = max(len1, len2)
        
        # Create output array with proper shape
        if output_channels == 1:
            mixed = np.zeros(max_len, dtype=self._get_numpy_dtype(self.output_config['format']))
        else:
            mixed = np.zeros((max_len, output_channels), dtype=self._get_numpy_dtype(self.output_config['format']))
        
        # Mix the overlapping portion
        if self.mix_mode == 'add':
            mixed[:min_len] = samples1[:min_len] + samples2[:min_len]
        elif self.mix_mode == 'average':
            mixed[:min_len] = (samples1[:min_len] + samples2[:min_len]) / 2.0
        elif self.mix_mode == 'weighted':
            # Use volumes as weights
            vol1 = self.input1_config['volume']
            vol2 = self.input2_config['volume']
            total_vol = vol1 + vol2
            if total_vol > 0:
                w1 = vol1 / total_vol
                w2 = vol2 / total_vol
                mixed[:min_len] = samples1[:min_len] * w1 + samples2[:min_len] * w2
            else:
                mixed[:min_len] = (samples1[:min_len] + samples2[:min_len]) / 2.0
        
        # Add remaining samples from longer input
        if len1 > min_len:
            mixed[min_len:len1] = samples1[min_len:]
        elif len2 > min_len:
            mixed[min_len:len2] = samples2[min_len:]
        
        return mixed
    
    def _apply_agc(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply automatic gain control."""
        if len(audio_data) == 0:
            return audio_data
        
        # Calculate peak level
        peak_level = np.max(np.abs(audio_data))
        
        # Update peak history
        self.agc_peak_history.append(peak_level)
        if len(self.agc_peak_history) > self.agc_history_size:
            self.agc_peak_history.pop(0)
        
        # Calculate average peak
        avg_peak = np.mean(self.agc_peak_history)
        
        # Target level (prevent clipping)
        target_level = 0.8
        
        if avg_peak > 0:
            # Calculate required gain
            required_gain = target_level / avg_peak
            
            # Smooth gain changes
            gain_change_rate = 0.1
            self.agc_gain = self.agc_gain * (1 - gain_change_rate) + required_gain * gain_change_rate
            
            # Limit gain range
            self.agc_gain = np.clip(self.agc_gain, 0.1, 2.0)
            
            # Apply gain
            return audio_data * self.agc_gain
        
        return audio_data
    
    def _bytes_to_numpy(self, data: bytes, format_str: str) -> np.ndarray:
        """Convert bytes to numpy array."""
        dtype = self._get_numpy_dtype(format_str)
        return np.frombuffer(data, dtype=dtype)
    
    def _get_numpy_dtype(self, format_str: str) -> np.dtype:
        """Get numpy dtype for format string."""
        if format_str == 'flt':
            return np.float32
        elif format_str == 's16':
            return np.int16
        elif format_str == 's32':
            return np.int32
        else:
            raise ValueError(f"Unsupported format: {format_str}")
    
    def get_info(self) -> Dict[str, Any]:
        """Get mixer configuration info."""
        info = {
            'input1': self.input1_config,
            'input2': self.input2_config,
            'output': self.output_config,
            'mix_mode': self.mix_mode,
            'auto_gain_control': self.auto_gain_control,
            'agc_gain': self.agc_gain if self.auto_gain_control else None,
            'jitter_buffer_enabled': self.enable_jitter_buffer
        }
        
        if self.enable_jitter_buffer:
            # Advanced buffer statistics
            info['buffer_stats'] = {
                'input1': self.input1_buffer.get_stats(),
                'input2': self.input2_buffer.get_stats()
            }
        else:
            # Simple buffer sizes
            info['buffer_sizes'] = {
                'input1': len(self.input1_buffer),
                'input2': len(self.input2_buffer)
            }
            
        return info


def create_simple_mixer(
    sample_rate: int = 48000,
    channels: int = 2,
    format: str = 's16',
    input1_volume: float = 1.0,
    input2_volume: float = 1.0
) -> AudioMixer:
    """
    Create a simple mixer with same format for all inputs/outputs.
    
    Args:
        sample_rate: Sample rate for all inputs/outputs
        channels: Channel count for all inputs/outputs
        format: Format for all inputs/outputs
        input1_volume: Volume for input 1
        input2_volume: Volume for input 2
        
    Returns:
        AudioMixer: Configured mixer instance
    """
    return AudioMixer(
        input1_sample_rate=sample_rate,
        input1_channels=channels,
        input1_format=format,
        input1_volume=input1_volume,
        
        input2_sample_rate=sample_rate,
        input2_channels=channels,
        input2_format=format,
        input2_volume=input2_volume,
        
        output_sample_rate=sample_rate,
        output_channels=channels,
        output_format=format,
        enable_jitter_buffer=False  # Simple mixer uses basic buffering
    )


def create_professional_mixer(
    sample_rate: int = 48000,
    channels: int = 2,
    format: str = 's16',
    input1_volume: float = 1.0,
    input2_volume: float = 1.0,
    target_latency_ms: float = 50.0,
    max_latency_ms: float = 200.0
) -> AudioMixer:
    """
    Create a professional-grade mixer with advanced jitter buffering.
    
    Args:
        sample_rate: Sample rate for all inputs/outputs
        channels: Channel count for all inputs/outputs  
        format: Format for all inputs/outputs
        input1_volume: Volume for input 1
        input2_volume: Volume for input 2
        target_latency_ms: Target buffer latency in milliseconds
        max_latency_ms: Maximum buffer latency in milliseconds
        
    Returns:
        AudioMixer: Professional mixer with jitter buffering
    """
    return AudioMixer(
        input1_sample_rate=sample_rate,
        input1_channels=channels,
        input1_format=format,
        input1_volume=input1_volume,
        
        input2_sample_rate=sample_rate,
        input2_channels=channels,
        input2_format=format,
        input2_volume=input2_volume,
        
        output_sample_rate=sample_rate,
        output_channels=channels,
        output_format=format,
        
        # Advanced buffering
        enable_jitter_buffer=True,
        target_buffer_ms=target_latency_ms,
        max_buffer_ms=max_latency_ms,
        min_buffer_ms=max(10.0, target_latency_ms / 5),
        sync_tolerance_ms=5.0,
        auto_gain_control=True
    )


if __name__ == "__main__":
    # Test example
    print("Audio Mixer Test")
    print("=" * 40)
    
    # Create mixer: mix 48kHz stereo + 16kHz mono -> 48kHz stereo
    mixer = AudioMixer(
        # Input 1: 48kHz stereo
        input1_sample_rate=48000,
        input1_channels=2,
        input1_format='flt',
        input1_volume=0.7,
        
        # Input 2: 16kHz mono
        input2_sample_rate=16000,
        input2_channels=1,
        input2_format='flt',
        input2_volume=0.8,
        
        # Output: 48kHz stereo
        output_sample_rate=48000,
        output_channels=2,
        output_format='flt',
        
        mix_mode='add',
        auto_gain_control=True
    )
    
    print(f"Mixer info: {mixer.get_info()}")
    
    # Generate test audio
    duration = 1.0
    
    # Input 1: 48kHz stereo sine wave (1kHz)
    t1 = np.linspace(0, duration, int(48000 * duration), False)
    freq1 = 1000.0
    input1_mono = np.sin(2 * np.pi * freq1 * t1).astype(np.float32)
    input1_stereo = np.column_stack([input1_mono, input1_mono * 0.5])
    
    # Input 2: 16kHz mono sine wave (500Hz)
    t2 = np.linspace(0, duration, int(16000 * duration), False)
    freq2 = 500.0
    input2_mono = np.sin(2 * np.pi * freq2 * t2).astype(np.float32) * 0.5
    
    print(f"Input 1: {input1_stereo.shape} @ 48kHz stereo")
    print(f"Input 2: {input2_mono.shape} @ 16kHz mono")
    
    # Mix audio
    mixed_output = mixer.mix(input1_stereo, input2_mono)
    
    print(f"Mixed output: {mixed_output.shape} @ 48kHz stereo")
    print(f"Output peak level: {np.max(np.abs(mixed_output)):.3f}")
    
    # Test batch mixing
    chunk_size1 = 4800  # 100ms @ 48kHz
    chunk_size2 = 1600  # 100ms @ 16kHz
    
    chunks1 = [input1_stereo[i:i+chunk_size1] for i in range(0, len(input1_stereo), chunk_size1)]
    chunks2 = [input2_mono[i:i+chunk_size2] for i in range(0, len(input2_mono), chunk_size2)]
    
    print(f"\nBatch mixing test: {len(chunks1)} + {len(chunks2)} chunks")
    batch_output = mixer.mix_batch(chunks1, chunks2)
    print(f"Batch output: {batch_output.shape}")
    
    # Test volume control
    print(f"\nVolume control test:")
    print(f"Input 1 volume: {mixer.get_input_volume(1)}")
    print(f"Input 2 volume: {mixer.get_input_volume(2)}")
    
    mixer.set_input_volume(1, 0.3)
    mixer.set_input_volume(2, 1.5)
    
    print(f"After adjustment:")
    print(f"Input 1 volume: {mixer.get_input_volume(1)}")
    print(f"Input 2 volume: {mixer.get_input_volume(2)}")
    
    # Test simple mixer
    print(f"\nSimple mixer test:")
    simple_mixer = create_simple_mixer(
        sample_rate=16000,
        channels=1,
        format='s16',
        input1_volume=0.6,
        input2_volume=0.8
    )
    
    # Generate 16kHz mono test data
    t = np.linspace(0, 0.5, int(16000 * 0.5), False)
    test1 = (np.sin(2 * np.pi * 440 * t) * 16383).astype(np.int16)  # 440Hz
    test2 = (np.sin(2 * np.pi * 880 * t) * 16383).astype(np.int16)  # 880Hz
    
    simple_output = simple_mixer.mix(test1, test2)
    print(f"Simple mixer output: {simple_output.shape} @ 16kHz mono")
    print(f"Simple output peak: {np.max(np.abs(simple_output))}")
    
    print("\nTest completed!")