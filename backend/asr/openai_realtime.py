"""OpenAI Realtime API implementation for streaming ASR"""

import asyncio
import json
import logging
import queue
import threading
import time
from typing import Optional, Dict, Any, Callable
import websocket
import websockets
from websockets.sync.client import connect

from .base import StreamingASRBase, ASRResult, ASRError

logger = logging.getLogger(__name__)


class OpenAIRealtimeASR(StreamingASRBase):
    """
    OpenAI Realtime API implementation for streaming speech recognition
    
    This implementation uses WebSocket connection for real-time audio streaming
    and transcription with low latency.
    """
    
    # API endpoint
    REALTIME_API_URL = "wss://api.openai.com/v1/realtime"
    
    def __init__(self, api_key: str, model: str = "gpt-4o-realtime-preview", **kwargs):
        """
        Initialize OpenAI Realtime ASR
        
        Args:
            api_key: OpenAI API key
            model: Model to use (default: gpt-4o-realtime-preview)
            **kwargs: Additional configuration
        """
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.api_key = api_key
        self.model = model
        self.ws_connection = None
        self.ws_thread = None
        self.audio_queue = queue.Queue()
        self.is_connected = False
        self.session_config = {
            "model": model,
            "modalities": ["text"],  # Only text output for ASR
            "instructions": kwargs.get("instructions", "Transcribe the audio accurately."),
            "voice": None,  # No voice output needed for ASR
            "input_audio_format": "pcm16",  # 16-bit PCM
            "output_audio_format": None,  # No audio output
            "input_audio_transcription": {
                "model": "gpt-4o-transcribe"  # Use GPT-4o for transcription
            },
            "turn_detection": {
                "type": "server_vad",  # Server-side voice activity detection
                "threshold": kwargs.get("vad_threshold", 0.5),
                "prefix_padding_ms": kwargs.get("prefix_padding_ms", 300),
                "silence_duration_ms": kwargs.get("silence_duration_ms", 500)
            },
            "temperature": kwargs.get("temperature", 0.1),  # Low temperature for accurate transcription
            "max_response_output_tokens": kwargs.get("max_tokens", 4096)
        }
        
        # Audio stream configuration
        self.stream_sample_rate = None
        self.stream_channels = None
        self.stream_sample_width = None
        
        logger.info(f"OpenAIRealtimeASR initialized with model: {model}")
    
    def start(self) -> None:
        """Start the ASR service"""
        if self.is_running:
            raise ASRError("OpenAI Realtime ASR is already running")
        
        self.is_running = True
        logger.info("OpenAI Realtime ASR started")
    
    def stop(self) -> None:
        """Stop the ASR service"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Close WebSocket connection if active
        if self.ws_connection:
            self._close_websocket()
        
        logger.info("OpenAI Realtime ASR stopped")
    
    def start_stream(self, 
                    sample_rate: int,
                    channels: int = 1,
                    sample_width: int = 2,
                    **kwargs) -> None:
        """
        Start a new audio stream for real-time transcription
        
        Args:
            sample_rate: Sample rate in Hz (must be 16000 for Realtime API)
            channels: Number of audio channels (must be 1 for mono)
            sample_width: Sample width in bytes (must be 2 for 16-bit)
            **kwargs: Additional parameters
        """
        if not self.is_running:
            raise ASRError("ASR service is not running. Call start() first.")
        
        # Validate audio parameters for Realtime API
        if sample_rate != 16000:
            raise ASRError(f"OpenAI Realtime API requires 16kHz sample rate, got {sample_rate}Hz")
        if channels != 1:
            raise ASRError(f"OpenAI Realtime API requires mono audio, got {channels} channels")
        if sample_width != 2:
            raise ASRError(f"OpenAI Realtime API requires 16-bit audio, got {sample_width*8}-bit")
        
        self.stream_sample_rate = sample_rate
        self.stream_channels = channels
        self.stream_sample_width = sample_width
        
        # Connect to WebSocket
        self._connect_websocket()
        
        logger.info(f"Audio stream started: {sample_rate}Hz, {channels}ch, {sample_width*8}-bit")
    
    def end_stream(self) -> Optional[ASRResult]:
        """
        End the current audio stream and get final result
        
        Returns:
            Final transcription result if available
        """
        if self.ws_connection:
            # Send end of stream signal
            self._send_message({
                "type": "input_audio_buffer.commit"
            })
            
            # Wait briefly for final results
            time.sleep(0.5)
            
            # Close connection
            self._close_websocket()
        
        return None  # Final result will be sent via callback
    
    def add_audio_data(self, audio_data: bytes, 
                      sample_rate: Optional[int] = None,
                      channels: Optional[int] = None,
                      sample_width: Optional[int] = None) -> None:
        """
        Add audio data for transcription
        
        Args:
            audio_data: Raw audio bytes (must be 16-bit PCM at 24kHz mono)
            sample_rate: Sample rate (ignored, must be 24kHz)
            channels: Number of channels (ignored, must be 1)
            sample_width: Sample width (ignored, must be 2)
        """
        if not self.is_running:
            return
        
        if self.ws_connection and self.is_connected:
            # Send audio data via WebSocket
            self._send_audio_data(audio_data)
        else:
            # Queue audio data if not yet connected
            self.audio_queue.put(audio_data)
    
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get OpenAI Realtime API capabilities"""
        capabilities = super().get_capabilities()
        capabilities.update({
            'realtime': True,
            'streaming': True,
            'required_sample_rate': 16000,
            'required_channels': 1,
            'required_bit_depth': 16,
            'max_audio_length': None,  # Continuous streaming
            'supported_formats': ['pcm16'],  # Raw 16-bit PCM only
            'languages': None,  # Supports all languages that Whisper supports
            'features': {
                'language_detection': True,
                'voice_activity_detection': True,
                'interim_results': True,
                'low_latency': True,
                'speaker_diarization': False,
            }
        })
        return capabilities
    
    def _connect_websocket(self):
        """Establish WebSocket connection to OpenAI Realtime API"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
            
            # Create WebSocket connection
            self.ws_connection = connect(
                f"{self.REALTIME_API_URL}?model={self.model}",
                additional_headers=headers
            )
            
            self.is_connected = True
            
            # Send session configuration
            self._send_message({
                "type": "session.update",
                "session": self.session_config
            })
            
            # Start receiving thread
            self.ws_thread = threading.Thread(target=self._receive_loop)
            self.ws_thread.daemon = True
            self.ws_thread.start()
            
            # Send any queued audio
            while not self.audio_queue.empty():
                audio_data = self.audio_queue.get()
                self._send_audio_data(audio_data)
            
            logger.info("Connected to OpenAI Realtime API")
            
        except Exception as e:
            self.is_connected = False
            raise ASRError(f"Failed to connect to OpenAI Realtime API: {e}")
    
    def _close_websocket(self):
        """Close WebSocket connection"""
        if self.ws_connection:
            try:
                self.is_connected = False
                self.ws_connection.close()
                if self.ws_thread:
                    self.ws_thread.join(timeout=2)
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
            finally:
                self.ws_connection = None
                self.ws_thread = None
    
    def _send_message(self, message: Dict[str, Any]):
        """Send a message to the WebSocket"""
        if self.ws_connection and self.is_connected:
            try:
                self.ws_connection.send(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                self.is_connected = False
    
    def _send_audio_data(self, audio_data: bytes):
        """Send audio data to the WebSocket"""
        if self.ws_connection and self.is_connected:
            try:
                # Convert audio data to base64
                import base64
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                
                # Send audio append message
                self._send_message({
                    "type": "input_audio_buffer.append",
                    "audio": audio_base64
                })
            except Exception as e:
                logger.error(f"Error sending audio data: {e}")
    
    def _receive_loop(self):
        """Receive messages from WebSocket"""
        while self.is_connected:
            try:
                message = self.ws_connection.recv(timeout=0.1)
                if message:
                    self._handle_message(json.loads(message))
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as e:
                if self.is_connected:
                    logger.error(f"Error in receive loop: {e}")
                break
    
    def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming WebSocket message"""
        msg_type = message.get("type")
        
        if msg_type == "error":
            logger.error(f"Realtime API error: {message.get('error', {})}")
            
        elif msg_type == "session.created" or msg_type == "session.updated":
            logger.debug(f"Session {msg_type.split('.')[-1]}")
            
        elif msg_type == "input_audio_buffer.speech_started":
            logger.debug("Speech started")
            
        elif msg_type == "input_audio_buffer.speech_stopped":
            logger.debug("Speech stopped")
            
        elif msg_type == "conversation.item.input_audio_transcription.completed":
            # Handle transcription result
            transcript = message.get("transcript", "")
            if transcript and self.callback:
                result = ASRResult(
                    text=transcript,
                    language=None,  # Language detection not provided in this event
                    timestamp=time.time(),
                    is_final=True,
                    metadata={
                        "model": self.model,
                        "item_id": message.get("item_id"),
                        "content_index": message.get("content_index", 0)
                    }
                )
                self.callback(result)
                
        elif msg_type == "conversation.item.input_audio_transcription.partial":
            # Handle partial transcription
            transcript = message.get("transcript", "")
            if transcript and self.callback:
                result = ASRResult(
                    text=transcript,
                    language=None,
                    timestamp=time.time(),
                    is_final=False,
                    metadata={
                        "model": self.model,
                        "item_id": message.get("item_id"),
                        "content_index": message.get("content_index", 0)
                    }
                )
                self.callback(result)
                
        elif msg_type == "response.audio_transcript.delta":
            # Handle response transcript (if any)
            delta = message.get("delta", "")
            if delta:
                logger.debug(f"Response transcript delta: {delta}")
                
        else:
            logger.debug(f"Unhandled message type: {msg_type}")