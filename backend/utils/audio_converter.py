import wave
import io
import numpy as np
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class AudioConverter:
    """Utility class for audio format conversion"""
    
    @staticmethod
    def pcm_to_wav(
        pcm_data: bytes,
        sample_rate: int = 48000,
        channels: int = 2,
        sample_width: int = 2
    ) -> bytes:
        """Convert raw PCM data to WAV format
        
        Args:
            pcm_data: Raw PCM audio data
            sample_rate: Sample rate in Hz
            channels: Number of channels
            sample_width: Sample width in bytes (2 for 16-bit)
            
        Returns:
            WAV file data as bytes
        """
        wav_buffer = io.BytesIO()
        
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
            
        wav_buffer.seek(0)
        return wav_buffer.read()
        
    @staticmethod
    def resample_audio(
        audio_data: np.ndarray,
        orig_sr: int,
        target_sr: int
    ) -> np.ndarray:
        """Resample audio to target sample rate
        
        Args:
            audio_data: Audio data as numpy array
            orig_sr: Original sample rate
            target_sr: Target sample rate
            
        Returns:
            Resampled audio data
        """
        if orig_sr == target_sr:
            return audio_data
            
        # Simple linear interpolation resampling
        duration = len(audio_data) / orig_sr
        target_length = int(duration * target_sr)
        
        # Create indices for interpolation
        indices = np.linspace(0, len(audio_data) - 1, target_length)
        
        # Interpolate
        resampled = np.interp(indices, np.arange(len(audio_data)), audio_data)
        
        return resampled.astype(audio_data.dtype)
        
    @staticmethod
    def stereo_to_mono(audio_data: np.ndarray) -> np.ndarray:
        """Convert stereo audio to mono
        
        Args:
            audio_data: Stereo audio data (interleaved L/R channels)
            
        Returns:
            Mono audio data
        """
        # Reshape to separate channels
        stereo = audio_data.reshape(-1, 2)
        # Average the channels
        mono = np.mean(stereo, axis=1)
        return mono.astype(audio_data.dtype)
        
    @staticmethod
    def prepare_for_whisper(
        pcm_data: bytes,
        sample_rate: int = 48000,
        channels: int = 2,
        target_sr: int = 16000
    ) -> bytes:
        """Prepare audio data for Whisper API
        
        Whisper works best with:
        - 16kHz sample rate
        - Mono channel
        - WAV format
        
        Args:
            pcm_data: Raw PCM audio data (16-bit)
            sample_rate: Original sample rate
            channels: Number of channels
            target_sr: Target sample rate for Whisper (default 16kHz)
            
        Returns:
            WAV file data optimized for Whisper
        """
        # Convert bytes to numpy array
        audio_array = np.frombuffer(pcm_data, dtype=np.int16)
        
        # Convert stereo to mono if needed
        if channels == 2:
            audio_array = AudioConverter.stereo_to_mono(audio_array)
            
        # Resample to target sample rate
        if sample_rate != target_sr:
            audio_array = AudioConverter.resample_audio(
                audio_array, sample_rate, target_sr
            )
            
        # Convert back to bytes
        processed_pcm = audio_array.tobytes()
        
        # Create WAV file
        return AudioConverter.pcm_to_wav(
            processed_pcm,
            sample_rate=target_sr,
            channels=1,  # Mono
            sample_width=2
        )
        
    @staticmethod
    def split_audio_chunks(
        pcm_data: bytes,
        chunk_duration: float = 5.0,
        sample_rate: int = 48000,
        channels: int = 2,
        overlap: float = 0.5
    ) -> list[bytes]:
        """Split audio into chunks for processing
        
        Args:
            pcm_data: Raw PCM audio data
            chunk_duration: Duration of each chunk in seconds
            sample_rate: Sample rate
            channels: Number of channels
            overlap: Overlap between chunks in seconds
            
        Returns:
            List of PCM data chunks
        """
        # Calculate chunk size in samples
        bytes_per_sample = 2 * channels  # 16-bit * channels
        chunk_size = int(chunk_duration * sample_rate * bytes_per_sample)
        overlap_size = int(overlap * sample_rate * bytes_per_sample)
        
        chunks = []
        offset = 0
        
        while offset < len(pcm_data):
            # Extract chunk
            end = min(offset + chunk_size, len(pcm_data))
            chunk = pcm_data[offset:end]
            
            # Only add if chunk is substantial (at least 1 second)
            if len(chunk) >= sample_rate * bytes_per_sample:
                chunks.append(chunk)
                
            # Move offset (with overlap)
            offset += chunk_size - overlap_size
            
            # Prevent infinite loop on last chunk
            if end >= len(pcm_data):
                break
                
        return chunks