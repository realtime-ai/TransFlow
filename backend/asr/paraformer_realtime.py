"""Paraformer Realtime API implementation for streaming ASR"""

import json
import logging
import threading
import time
import wave
import os
from datetime import datetime
from typing import Optional, Dict, Any, Callable


from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult
DASHSCOPE_AVAILABLE = True


from .base import StreamingASRBase, ASRResult, ASRError

logger = logging.getLogger(__name__)


class ParaformerRealtimeCallback(RecognitionCallback):
    """Callback handler for Paraformer real-time recognition"""
    
    def __init__(self, parent_asr):
        self.parent_asr = parent_asr
        
    def on_open(self):
        """Called when recognition starts"""
        logger.info("🔌 Paraformer recognition opened")
        self.parent_asr.is_connected = True
        
    def on_event(self, result: RecognitionResult):
        """Called when recognition result is received"""
        logger.debug(f"🔍 Raw result received: {result}")
        
        try:
            # Try to get sentence from result
            sentence = result.get_sentence() if hasattr(result, 'get_sentence') else None
            logger.debug(f"🔍 Sentence extracted: {sentence}")
            
            if sentence and sentence.get('text') and self.parent_asr.callback:
                # Extract transcription text
                text = sentence.get('text', '')
                
                # Skip empty or very short results
                if not text or len(text.strip()) == 0:
                    logger.debug("🔍 Skipping empty text result")
                    return
                
                # Determine if this is a final result
                is_final = sentence.get('end_time') is not None
                
                logger.info(f"📝 Paraformer result (final={is_final}): '{text}'")
                
                # Create ASR result
                asr_result = ASRResult(
                    text=text,
                    language=self.parent_asr.current_language or 'zh',
                    timestamp=time.time(),
                    is_final=is_final,
                    metadata={
                        "model": self.parent_asr.model,
                        "confidence": sentence.get('confidence', 0.0),
                        "start_time": sentence.get('begin_time', 0),
                        "end_time": sentence.get('end_time', 0),
                        "provider": "paraformer"
                    }
                )
                
                # Send result to callback
                self.parent_asr.callback(asr_result)
            else:
                logger.debug(f"🔍 No valid sentence or callback: sentence={bool(sentence)}, callback={bool(self.parent_asr.callback)}")
                
        except Exception as e:
            logger.error(f"❌ Error processing result: {e}")
            logger.debug(f"🔍 Result details: {result}")
    
    def on_complete(self):
        """Called when recognition completes"""
        logger.info("✅ Paraformer recognition completed")
        self.parent_asr.is_connected = False
    
    def on_error(self, error):
        """Called when recognition error occurs"""
        logger.error(f"❌ Paraformer recognition error: {error}")
        self.parent_asr.is_connected = False


class ParaformerRealtimeASR(StreamingASRBase):
    """
    Paraformer Realtime API implementation for streaming speech recognition
    
    This implementation uses Alibaba Cloud's Paraformer model for real-time
    Chinese and multilingual speech recognition with high accuracy.
    """
    
    # Supported models
    SUPPORTED_MODELS = [
        "paraformer-realtime-v2",
        "paraformer-realtime-8k-v2"
    ]
    
    def __init__(self, api_key: str, model: str = "paraformer-realtime-v2", **kwargs):
        """
        Initialize Paraformer Realtime ASR
        
        Args:
            api_key: Dashscope API key
            model: Model to use (default: paraformer-realtime-v2)
            **kwargs: Additional configuration
                - debug_dump_audio: bool - Whether to dump audio to WAV files for debugging (default: False)
                - debug_dump_dir: str - Directory to save debug audio files (default: "./debug_audio")
                - sample_rate: int - Audio sample rate (8000 or 16000, default: 16000)
                - enable_punctuation: bool - Enable automatic punctuation (default: True)
                - enable_itn: bool - Enable inverse text normalization (default: True)
                - language: str - Recognition language (default: 'auto')
        """
        if not DASHSCOPE_AVAILABLE:
            raise ASRError("dashscope package not installed. Install with: pip install dashscope")
        
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.api_key = api_key
        self.model = model
        
        # Set dashscope API key
        try:
            import dashscope
            dashscope.api_key = api_key
            logger.info(f"Dashscope API key configured")
        except Exception as e:
            logger.warning(f"Failed to set dashscope API key: {e}")
        
        if model not in self.SUPPORTED_MODELS:
            logger.warning(f"Model {model} not in supported models: {self.SUPPORTED_MODELS}")
        
        # Recognition configuration
        self.sample_rate = kwargs.get("sample_rate", 16000)
        self.enable_punctuation = kwargs.get("enable_punctuation", True)
        self.enable_itn = kwargs.get("enable_itn", True)
        self.language = kwargs.get("language", "auto")
        self.current_language = None
        
        # Audio debugging configuration
        self.debug_dump_audio = kwargs.get("debug_dump_audio", False)
        self.debug_dump_dir = kwargs.get("debug_dump_dir", "./debug_audio")
        self.debug_wav_file = None
        
        # Recognition objects
        self.recognition = None
        self.callback_handler = None
        self.is_connected = False
        
        # Audio stream configuration
        self.stream_sample_rate = None
        self.stream_channels = None
        self.stream_sample_width = None
        
        logger.info(f"ParaformerRealtimeASR initialized with model: {model}")
        
        # Initialize debug audio dump if enabled
        if self.debug_dump_audio:
            self._init_debug_audio_dump()
    
    def _init_debug_audio_dump(self):
        """Initialize debug audio dump to WAV file"""
        if not os.path.exists(self.debug_dump_dir):
            os.makedirs(self.debug_dump_dir)
            logger.info(f"Created debug audio directory: {self.debug_dump_dir}")
        
        # Create unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"paraformer_input_{timestamp}.wav"
        self.debug_wav_path = os.path.join(self.debug_dump_dir, filename)
        
        # Initialize WAV file (will be opened when stream starts)
        logger.info(f"🎵 Debug audio dump enabled: {self.debug_wav_path}")
    
    def _write_debug_audio(self, audio_data: bytes):
        """Write audio data to debug WAV file"""
        if self.debug_dump_audio and self.debug_wav_file:
            try:
                self.debug_wav_file.writeframes(audio_data)
            except Exception as e:
                logger.warning(f"Failed to write debug audio: {e}")
    
    def _close_debug_audio_dump(self):
        """Close debug audio dump file"""
        if self.debug_wav_file:
            try:
                self.debug_wav_file.close()
                self.debug_wav_file = None
                logger.info(f"🎵 Debug audio saved to: {self.debug_wav_path}")
            except Exception as e:
                logger.warning(f"Failed to close debug audio file: {e}")
    
    def start(self) -> None:
        """Start the ASR service"""
        if self.is_running:
            raise ASRError("Paraformer Realtime ASR is already running")
        
        self.is_running = True
        logger.info("Paraformer Realtime ASR started")
    
    def stop(self) -> None:
        """Stop the ASR service"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Stop recognition if running
        if self.recognition and self.is_connected:
            try:
                self.recognition.stop()
            except Exception as e:
                logger.error(f"Error stopping recognition: {e}")
        
        # Close debug audio dump
        self._close_debug_audio_dump()
        
        logger.info("Paraformer Realtime ASR stopped")
    
    def start_stream(self, 
                    sample_rate: int,
                    channels: int = 1,
                    sample_width: int = 2,
                    **kwargs) -> None:
        """
        Start a new audio stream for real-time transcription
        
        Args:
            sample_rate: Sample rate in Hz (8000 or 16000)
            channels: Number of audio channels (must be 1 for mono)
            sample_width: Sample width in bytes (must be 2 for 16-bit)
            **kwargs: Additional parameters
        """
        if not self.is_running:
            raise ASRError("ASR service is not running. Call start() first.")
        
        # Validate audio parameters
        if sample_rate not in [8000, 16000]:
            raise ASRError(f"Paraformer supports 8kHz or 16kHz sample rate, got {sample_rate}Hz")
        if channels != 1:
            raise ASRError(f"Paraformer requires mono audio, got {channels} channels")
        if sample_width != 2:
            raise ASRError(f"Paraformer requires 16-bit audio, got {sample_width*8}-bit")
        
        self.stream_sample_rate = sample_rate
        self.stream_channels = channels
        self.stream_sample_width = sample_width
        
        # Initialize debug WAV file with actual stream parameters
        if self.debug_dump_audio and not self.debug_wav_file:
            self.debug_wav_file = wave.open(self.debug_wav_path, 'wb')
            self.debug_wav_file.setnchannels(channels)
            self.debug_wav_file.setsampwidth(sample_width)
            self.debug_wav_file.setframerate(sample_rate)
        
        # Create recognition instance
        self.callback_handler = ParaformerRealtimeCallback(self)
        
        # Configure recognition parameters
        recognition_params = {
            'model': self.model,
            'sample_rate': sample_rate,
            'format': 'pcm',
            'callback': self.callback_handler
        }
        
        # Add optional parameters
        if self.enable_punctuation:
            recognition_params['enable_disfluency'] = True
        if self.enable_itn:
            recognition_params['enable_itn'] = True
        if self.language != 'auto':
            recognition_params['language'] = self.language
        
        try:
            # Create recognition instance with callback as required parameter
            self.recognition = Recognition(
                model=self.model,
                format='pcm',
                sample_rate=sample_rate,
                callback=self.callback_handler  # Required parameter
            )
            
            # Start recognition
            self.recognition.start()
            
            logger.info(f"Audio stream started: {sample_rate}Hz, {channels}ch, {sample_width*8}-bit")
            logger.info(f"Paraformer model: {self.model}")
            
        except Exception as e:
            logger.error(f"Failed to start Paraformer recognition: {e}")
            raise ASRError(f"Failed to start Paraformer recognition: {e}")
    
    def end_stream(self) -> Optional[ASRResult]:
        """
        End the current audio stream and get final result
        
        Returns:
            Final transcription result if available
        """
        if self.recognition and self.is_connected:
            try:
                # Stop recognition
                self.recognition.stop()
                
                # Wait briefly for final results
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error ending stream: {e}")
        
        return None  # Final result will be sent via callback
    
    def add_audio_data(self, audio_data: bytes, 
                      sample_rate: Optional[int] = None,
                      channels: Optional[int] = None,
                      sample_width: Optional[int] = None) -> None:
        """
        Add audio data for transcription
        
        Args:
            audio_data: Raw audio bytes (must be 16-bit PCM)
            sample_rate: Sample rate (ignored, uses stream parameters)
            channels: Number of channels (ignored, uses stream parameters)
            sample_width: Sample width (ignored, uses stream parameters)
        """
        if not self.is_running:
            return
        
        if not audio_data:
            return
        
        # Write to debug file
        self._write_debug_audio(audio_data)
        
        if self.recognition and self.is_connected:
            try:
                # Send audio frame to Paraformer
                self.recognition.send_audio_frame(audio_data)
                
            except Exception as e:
                logger.error(f"Error sending audio data: {e}")
                self.is_connected = False
    
    def set_language(self, language: Optional[str]) -> None:
        """Set the source language for recognition"""
        if language:
            self.current_language = language
            logger.info(f"Language set to: {language}")
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get Paraformer capabilities"""
        capabilities = super().get_capabilities()
        capabilities.update({
            'realtime': True,
            'streaming': True,
            'required_sample_rate': [8000, 16000],
            'required_channels': 1,
            'required_bit_depth': 16,
            'max_audio_length': None,  # Continuous streaming
            'supported_formats': ['pcm16'],  # Raw 16-bit PCM only
            'languages': ['zh', 'en', 'ja', 'ko', 'auto'],  # Supported languages
            'features': {
                'language_detection': True,
                'voice_activity_detection': True,
                'interim_results': True,
                'low_latency': True,
                'speaker_diarization': False,
                'punctuation': self.enable_punctuation,
                'inverse_text_normalization': self.enable_itn,
            }
        })
        return capabilities