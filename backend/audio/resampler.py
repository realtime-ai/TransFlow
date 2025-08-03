import av
import numpy as np
from typing import Union, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class AudioResampler:
    """
    Audio resampler class using PyAV for high-quality audio resampling.
    
    Features:
    - Sample rate conversion (e.g., 48kHz -> 16kHz)
    - Channel conversion (e.g., stereo -> mono)
    - Format conversion (e.g., float32 -> int16)
    """
    
    def __init__(
        self, 
        input_sample_rate: int,
        output_sample_rate: int,
        input_channels: int = 1,
        output_channels: int = 1,
        input_format: str = 'flt',  # PyAV formats: 'flt'(float32), 's16'(int16), 's32'(int32)
        output_format: str = 's16',
        resample_method: str = 'swr'  # Resampling method: 'swr' (high quality)
    ):
        """
        Initialize audio resampler.
        
        Args:
            input_sample_rate: Input sample rate (Hz)
            output_sample_rate: Output sample rate (Hz)
            input_channels: Input channel count
            output_channels: Output channel count
            input_format: Input format ('flt', 's16', 's32', etc.)
            output_format: Output format ('flt', 's16', 's32', etc.)
            resample_method: Resampling method ('swr' for high quality)
        """
        self.input_sample_rate = input_sample_rate
        self.output_sample_rate = output_sample_rate
        self.input_channels = input_channels
        self.output_channels = output_channels
        self.input_format = input_format
        self.output_format = output_format
        
        # Create resampler
        self.resampler = av.AudioResampler(
            format=av.AudioFormat(output_format),
            layout=self._get_channel_layout(output_channels),
            rate=output_sample_rate,
        )
        
        # Store input parameters
        self.input_layout = self._get_channel_layout(input_channels)
        self.input_audio_format = av.AudioFormat(input_format)
        
        logger.info(
            f"AudioResampler initialized: "
            f"{input_sample_rate}Hz/{input_channels}ch/{input_format} -> "
            f"{output_sample_rate}Hz/{output_channels}ch/{output_format}"
        )
    
    def _get_channel_layout(self, channels: int) -> str:
        """Get channel layout string from channel count."""
        if channels == 1:
            return 'mono'
        elif channels == 2:
            return 'stereo'
        else:
            # Multi-channel layout
            return f'{channels}c'
    
    def resample(self, audio_data: Union[np.ndarray, bytes], 
                 input_pts: Optional[int] = None) -> Tuple[np.ndarray, int]:
        """
        Resample audio data.
        
        Args:
            audio_data: Input audio data as numpy array or bytes
            input_pts: Input presentation timestamp
            
        Returns:
            Tuple[np.ndarray, int]: (resampled audio data, output sample count)
        """
        # Convert bytes to numpy array if needed
        if isinstance(audio_data, bytes):
            audio_array = self._bytes_to_numpy(audio_data)
        else:
            audio_array = audio_data
            
        # Reshape audio data if needed
        if audio_array.ndim == 1:
            if self.input_channels > 1:
                # Interleaved multi-channel data, reshape to (samples, channels)
                samples = len(audio_array) // self.input_channels
                audio_array = audio_array.reshape(samples, self.input_channels)
            else:
                # Mono data, reshape to (samples, 1) for PyAV compatibility
                audio_array = audio_array.reshape(-1, 1)
        
        # Create PyAV AudioFrame using from_ndarray
        # PyAV from_ndarray expects different layouts for different cases
        try:
            if self.input_channels == 1:
                # For mono, use 1D array
                frame_array = audio_array.squeeze()
                frame = av.AudioFrame.from_ndarray(
                    frame_array,
                    format=self.input_format,
                    layout=self.input_layout
                )
            else:
                # For multi-channel, try planar format first (channels, samples)
                frame_array = audio_array.T  # Transpose to (channels, samples)
                frame = av.AudioFrame.from_ndarray(
                    frame_array,
                    format=self.input_format,
                    layout=self.input_layout
                )
        except ValueError:
            # If from_ndarray fails, try using interleaved/packed format
            if self.input_channels == 1:
                frame_array = audio_array.squeeze()
                frame = av.AudioFrame(
                    format=self.input_format,
                    layout=self.input_layout,
                    samples=len(frame_array)
                )
                frame.planes[0].update(frame_array.tobytes())
            else:
                # For multi-channel, try creating with packed format
                # Convert to 1D interleaved array
                frame_array = audio_array.flatten(order='C')  # Row-major order (sample1_ch1, sample1_ch2, sample2_ch1, ...)
                
                frame = av.AudioFrame(
                    format=self.input_format,
                    layout=self.input_layout,
                    samples=audio_array.shape[0]
                )
                
                # For packed format, all data goes to first plane
                if len(frame.planes) == 1:
                    # Packed format - all channels interleaved in one plane
                    frame.planes[0].update(frame_array.tobytes())
                else:
                    # Planar format - separate each channel
                    for i in range(min(self.input_channels, len(frame.planes))):
                        channel_data = audio_array[:, i].astype(audio_array.dtype)
                        frame.planes[i].update(channel_data.tobytes())
        frame.sample_rate = self.input_sample_rate
        
        if input_pts is not None:
            frame.pts = input_pts
        
        # Perform resampling
        resampled_frames = self.resampler.resample(frame)
        
        if not resampled_frames:
            # No output frames returned
            return np.array([]), 0
        
        # Combine output frames
        output_arrays = []
        total_samples = 0
        
        for out_frame in resampled_frames:
            out_array = out_frame.to_ndarray()
            
            # Ensure proper shape for output
            if self.output_channels == 1:
                # For mono output, flatten to 1D
                if out_array.ndim > 1:
                    out_array = out_array.flatten()
            else:
                # For multi-channel, ensure (samples, channels) shape
                if out_array.ndim == 1:
                    # If 1D, this shouldn't happen for multi-channel but handle it
                    samples_per_channel = len(out_array) // self.output_channels
                    out_array = out_array.reshape(samples_per_channel, self.output_channels)
                elif out_array.shape[0] == self.output_channels and out_array.shape[1] > self.output_channels:
                    # If planar format (channels, samples), transpose to (samples, channels)
                    out_array = out_array.T
            
            output_arrays.append(out_array)
            total_samples += out_frame.samples
        
        # Concatenate results
        if output_arrays:
            if self.output_channels == 1:
                output_data = np.concatenate(output_arrays, axis=0)
            else:
                output_data = np.concatenate(output_arrays, axis=0)
        else:
            output_data = np.array([])
        
        return output_data, total_samples
    
    def resample_batch(self, audio_chunks: list) -> np.ndarray:
        """
        Resample multiple audio chunks.
        
        Args:
            audio_chunks: List of audio chunks
            
        Returns:
            np.ndarray: Combined resampled audio data
        """
        resampled_chunks = []
        
        for chunk in audio_chunks:
            resampled_chunk, _ = self.resample(chunk)
            if len(resampled_chunk) > 0:
                resampled_chunks.append(resampled_chunk)
        
        if resampled_chunks:
            return np.concatenate(resampled_chunks, axis=0)
        else:
            return np.array([])
    
    def _bytes_to_numpy(self, data: bytes) -> np.ndarray:
        """Convert bytes to numpy array."""
        if self.input_format == 'flt':
            dtype = np.float32
        elif self.input_format == 's16':
            dtype = np.int16
        elif self.input_format == 's32':
            dtype = np.int32
        else:
            raise ValueError(f"Unsupported input format: {self.input_format}")
        
        return np.frombuffer(data, dtype=dtype)
    
    def flush(self) -> Optional[np.ndarray]:
        """
        Flush remaining audio data from resampler.
        
        Returns:
            Optional[np.ndarray]: Remaining audio data, or None if empty
        """
        try:
            # Flush resampler
            resampled_frames = self.resampler.resample(None)
            
            if not resampled_frames:
                return None
            
            # Combine frames
            output_arrays = []
            for frame in resampled_frames:
                output_arrays.append(frame.to_ndarray())
            
            if output_arrays:
                return np.concatenate(output_arrays, axis=0)
            else:
                return None
                
        except Exception as e:
            logger.warning(f"Error flushing resampler: {e}")
            return None
    
    def get_output_samples(self, input_samples: int) -> int:
        """
        Calculate expected output sample count for given input samples.
        
        Args:
            input_samples: Input sample count
            
        Returns:
            int: Expected output sample count
        """
        return int(input_samples * self.output_sample_rate / self.input_sample_rate)
    
    def get_delay(self) -> int:
        """
        Get resampler delay in samples.
        
        Returns:
            int: Delay in samples
        """
        # PyAV resampler has internal delay
        # Return conservative estimate
        return max(64, int(self.input_sample_rate * 0.01))  # ~10ms delay


def create_resampler(
    input_rate: int, 
    output_rate: int,
    channels: int = 1,
    format: str = 'flt'
) -> AudioResampler:
    """
    Create a simple resampler with same input/output channels and format.
    
    Args:
        input_rate: Input sample rate
        output_rate: Output sample rate
        channels: Channel count (same for input and output)
        format: Audio format (same for input and output)
        
    Returns:
        AudioResampler: Configured resampler instance
    """
    return AudioResampler(
        input_sample_rate=input_rate,
        output_sample_rate=output_rate,
        input_channels=channels,
        output_channels=channels,
        input_format=format,
        output_format=format
    )


if __name__ == "__main__":
    # Test example
    
    # Create resampler: 48kHz -> 16kHz, mono, float32
    resampler = AudioResampler(
        input_sample_rate=48000,
        output_sample_rate=16000,
        input_channels=1,
        output_channels=1,
        input_format='flt',
        output_format='s16'
    )
    
    # Generate test audio: 1 second 1kHz sine wave
    duration = 1.0
    frequency = 1000.0
    sample_rate = 48000
    
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    test_audio = np.sin(2 * np.pi * frequency * t).astype(np.float32)
    
    print(f"Input: {len(test_audio)} samples @ {sample_rate}Hz")
    
    # Perform resampling
    resampled_audio, output_samples = resampler.resample(test_audio)
    
    print(f"Output: {output_samples} samples @ 16000Hz")
    print(f"Expected output samples: {resampler.get_output_samples(len(test_audio))}")
    print(f"Actual output samples: {len(resampled_audio)}")
    
    # Test batch resampling
    chunk_size = 4800  # 100ms @ 48kHz
    chunks = [test_audio[i:i+chunk_size] for i in range(0, len(test_audio), chunk_size)]
    
    print(f"\nBatch resampling test: {len(chunks)} chunks")
    batch_resampled = resampler.resample_batch(chunks)
    print(f"Batch output: {len(batch_resampled)} samples")
    
    # Test channel conversion: stereo -> mono
    print("\nChannel conversion test: stereo -> mono")
    stereo_resampler = AudioResampler(
        input_sample_rate=48000,
        output_sample_rate=16000,
        input_channels=2,
        output_channels=1,
        input_format='flt',
        output_format='flt'
    )
    
    # Create stereo test audio
    stereo_audio = np.column_stack([test_audio, test_audio * 0.5])  # L/R channels
    print(f"Stereo input: {stereo_audio.shape}")
    
    mono_output, _ = stereo_resampler.resample(stereo_audio)
    print(f"Mono output: {mono_output.shape}")