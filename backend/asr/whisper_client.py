import io
import wave
import struct
import numpy as np
from typing import Optional, Callable, Dict, Any
import logging
from openai import OpenAI
import queue
import threading
import time
from pathlib import Path
import tempfile

from .base import ASRBase, ASRResult, ASRError

logger = logging.getLogger(__name__)


class WhisperClient(ASRBase):
    """OpenAI Whisper API client for real-time speech recognition"""
    
    def __init__(self, api_key: str, model: str = "whisper-1", **kwargs):
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.audio_buffer = queue.Queue()
        self.is_processing = False
        self.processing_thread = None
        self.language = None  # Auto-detect by default
        
        # Audio parameters (can be overridden by kwargs)
        self.sample_rate = kwargs.get('sample_rate', 48000)
        self.channels = kwargs.get('channels', 2)
        self.sample_width = kwargs.get('sample_width', 2)  # 16-bit
        
        # Buffer settings
        self.buffer_duration = kwargs.get('buffer_duration', 5)  # seconds
        self.buffer_size = self.sample_rate * self.channels * self.sample_width * self.buffer_duration
        self.current_buffer = bytearray()
        
        logger.info(f"WhisperClient initialized with model: {model}")
    
    def set_language(self, language: Optional[str] = None):
        """Set the source language for recognition
        
        Args:
            language: ISO-639-1 language code (e.g., 'zh', 'en', 'ja')
                     None for auto-detection
        """
        self.language = language
        super().set_language(language)
    
    # set_callback is inherited from base class
    
    def add_audio_data(self, audio_data: bytes, 
                      sample_rate: Optional[int] = None,
                      channels: Optional[int] = None,
                      sample_width: Optional[int] = None) -> None:
        """Add audio data to the buffer for processing
        
        Args:
            audio_data: Raw audio bytes (16-bit PCM)
            sample_rate: Sample rate in Hz (if different from configured)
            channels: Number of channels (if different from configured)
            sample_width: Sample width in bytes (if different from configured)
        """
        if self.is_processing:
            # TODO: Handle different audio formats if provided
            self.audio_buffer.put(audio_data)
    
    def start(self):
        """Start the ASR processing thread"""
        if self.is_processing:
            logger.warning("WhisperClient is already running")
            return
        
        self.is_processing = True
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._process_audio_loop)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        logger.info("WhisperClient started")
    
    def stop(self):
        """Stop the ASR processing thread"""
        if not self.is_processing:
            return
        
        self.is_processing = False
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
        
        # Process any remaining audio
        if len(self.current_buffer) > 0:
            self._process_buffer(self.current_buffer)
        
        logger.info("WhisperClient stopped")
    
    def _process_audio_loop(self):
        """Main processing loop running in separate thread"""
        while self.is_processing:
            try:
                # Get audio data with timeout
                audio_data = self.audio_buffer.get(timeout=0.1)
                self.current_buffer.extend(audio_data)
                
                # Check if buffer is full
                if len(self.current_buffer) >= self.buffer_size:
                    # Process the buffer
                    buffer_to_process = bytes(self.current_buffer[:self.buffer_size])
                    self.current_buffer = self.current_buffer[self.buffer_size:]
                    
                    # Process in a separate thread to avoid blocking
                    threading.Thread(
                        target=self._process_buffer,
                        args=(buffer_to_process,)
                    ).start()
                    
            except queue.Empty:
                # Check if we have data waiting for a while
                if len(self.current_buffer) > self.sample_rate * self.sample_width:  # > 1 second
                    buffer_to_process = bytes(self.current_buffer)
                    self.current_buffer = bytearray()
                    
                    threading.Thread(
                        target=self._process_buffer,
                        args=(buffer_to_process,)
                    ).start()
                    
            except Exception as e:
                logger.error(f"Error in audio processing loop: {e}")
    
    def _process_buffer(self, audio_buffer: bytes):
        """Process audio buffer with Whisper API
        
        Args:
            audio_buffer: Audio data to process
        """
        if not audio_buffer or len(audio_buffer) < 1000:  # Skip very small buffers
            return
        
        try:
            # Create a temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
                
                # Write WAV file
                with wave.open(temp_path, 'wb') as wav_file:
                    wav_file.setnchannels(self.channels)
                    wav_file.setsampwidth(self.sample_width)
                    wav_file.setframerate(self.sample_rate)
                    wav_file.writeframes(audio_buffer)
                
                # Send to Whisper API
                with open(temp_path, 'rb') as audio_file:
                    params = {
                        "model": self.model,
                        "file": audio_file,
                        "response_format": "json",
                    }
                    
                    if self.language:
                        params["language"] = self.language
                    
                    response = self.client.audio.transcriptions.create(**params)
                
                # Process response
                if response.text:
                    result = ASRResult(
                        text=response.text,
                        language=getattr(response, 'language', self.language),
                        timestamp=time.time(),
                        is_final=True,
                        metadata={'model': self.model}
                    )
                    
                    logger.debug(f"Transcription: {result.text}")
                    
                    if self.callback:
                        self.callback(result)
                
                # Clean up
                Path(temp_path).unlink()
                
        except Exception as e:
            logger.error(f"Error processing audio with Whisper: {e}")
    
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get Whisper API capabilities"""
        return {
            'realtime': False,  # Whisper API is not real-time streaming
            'streaming': False,
            'max_audio_length': 25 * 1024 * 1024,  # 25MB file size limit
            'supported_formats': ['flac', 'mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'ogg', 'wav', 'webm'],
            'languages': ['af', 'ar', 'hy', 'az', 'be', 'bs', 'bg', 'ca', 'zh', 'hr', 'cs', 'da', 
                         'nl', 'en', 'et', 'fi', 'fr', 'gl', 'de', 'el', 'he', 'hi', 'hu', 'is', 
                         'id', 'it', 'ja', 'kn', 'kk', 'ko', 'lv', 'lt', 'mk', 'ms', 'mr', 'mi', 
                         'ne', 'no', 'fa', 'pl', 'pt', 'ro', 'ru', 'sr', 'sk', 'sl', 'es', 'sw', 
                         'sv', 'tl', 'ta', 'th', 'tr', 'uk', 'ur', 'vi', 'cy'],
            'models': ['whisper-1'],
            'features': {
                'language_detection': True,
                'timestamps': False,  # Word-level timestamps not available via API
                'speaker_diarization': False,
                'punctuation': True,
            }
        }
    
    def get_supported_languages(self) -> Optional[list[str]]:
        """Get list of supported languages"""
        return self.get_capabilities()['languages']