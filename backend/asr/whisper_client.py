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

logger = logging.getLogger(__name__)


class WhisperClient:
    """OpenAI Whisper API client for real-time speech recognition"""
    
    def __init__(self, api_key: str, model: str = "whisper-1"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.audio_buffer = queue.Queue()
        self.is_processing = False
        self.processing_thread = None
        self.callback = None
        self.language = None  # Auto-detect by default
        
        # Audio parameters
        self.sample_rate = 48000
        self.channels = 2
        self.sample_width = 2  # 16-bit
        
        # Buffer settings
        self.buffer_duration = 5  # seconds
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
        logger.info(f"Language set to: {language or 'auto-detect'}")
    
    def set_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback function for recognition results
        
        Args:
            callback: Function that receives recognition results
                     Format: {'text': str, 'language': str, 'timestamp': float}
        """
        self.callback = callback
    
    def add_audio_data(self, audio_data: bytes):
        """Add audio data to the buffer for processing
        
        Args:
            audio_data: Raw audio bytes (16-bit PCM)
        """
        if self.is_processing:
            self.audio_buffer.put(audio_data)
    
    def start(self):
        """Start the ASR processing thread"""
        if self.is_processing:
            logger.warning("WhisperClient is already running")
            return
        
        self.is_processing = True
        self.processing_thread = threading.Thread(target=self._process_audio_loop)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        logger.info("WhisperClient started")
    
    def stop(self):
        """Stop the ASR processing thread"""
        if not self.is_processing:
            return
        
        self.is_processing = False
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
                    result = {
                        'text': response.text,
                        'language': getattr(response, 'language', self.language or 'unknown'),
                        'timestamp': time.time()
                    }
                    
                    logger.debug(f"Transcription: {result['text']}")
                    
                    if self.callback:
                        self.callback(result)
                
                # Clean up
                Path(temp_path).unlink()
                
        except Exception as e:
            logger.error(f"Error processing audio with Whisper: {e}")
    
    def transcribe_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Transcribe an audio file
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            Transcription result or None if failed
        """
        try:
            with open(file_path, 'rb') as audio_file:
                params = {
                    "model": self.model,
                    "file": audio_file,
                    "response_format": "json",
                }
                
                if self.language:
                    params["language"] = self.language
                
                response = self.client.audio.transcriptions.create(**params)
                
                return {
                    'text': response.text,
                    'language': getattr(response, 'language', self.language or 'unknown'),
                    'timestamp': time.time()
                }
                
        except Exception as e:
            logger.error(f"Error transcribing file {file_path}: {e}")
            return None