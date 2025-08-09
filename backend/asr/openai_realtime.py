"""OpenAI Realtime API implementation for streaming ASR"""

import asyncio
import json
import logging
import queue
import threading
import time
import wave
import os
from datetime import datetime
from typing import Optional, Dict, Any, Callable
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
                - debug_dump_audio: bool - Whether to dump audio to WAV files for debugging (default: False)
                - debug_dump_dir: str - Directory to save debug audio files (default: "./debug_audio")
        """
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.api_key = api_key
        self.model = model
        self.ws_connection = None
        self.ws_thread = None
        self.audio_queue = queue.Queue()
        self.is_connected = False
        self.last_commit_time = 0  # Track when we last committed audio buffer
        self.audio_buffer_size = 0  # Track accumulated audio data size
        self.max_retries = kwargs.get("max_retries", 3)  # Connection retry attempts
        self.retry_delay = kwargs.get("retry_delay", 2.0)  # Delay between retries
        self.connection_timeout = kwargs.get("connection_timeout", 30.0)  # Connection timeout
        self.last_heartbeat = 0  # Track last successful communication
        
        # Audio debugging configuration
        self.debug_dump_audio = kwargs.get("debug_dump_audio", False)
        self.debug_dump_dir = kwargs.get("debug_dump_dir", "./debug_audio")
        self.debug_wav_file = None
        self.debug_audio_buffer = []
        self.session_config = {
            "model": model,
            "modalities": ["text"],  # Include both text and audio modalities  
            "instructions": "Listen carefully to the audio and provide accurate transcriptions of what is spoken. Transcribe clearly and completely.",
            "input_audio_format": 'pcm16',  # 16-bit PCM
            "input_audio_transcription": {
                "model": "gpt-4o-mini-transcribe",  # Use Whisper for transcription
                "language": "zh"
            },
            "turn_detection": {
                "type": "server_vad",  # Server-side voice activity detection handles commits automatically
                "threshold": kwargs.get("vad_threshold", 0.5),  # Moderate threshold for better reliability
                "prefix_padding_ms": kwargs.get("prefix_padding_ms", 300),
                "silence_duration_ms": kwargs.get("silence_duration_ms", 1000)  # Longer silence for more stable detection
            },
            "temperature": kwargs.get("temperature", 0.7),  # Default temperature for Realtime API
            "max_response_output_tokens": kwargs.get("max_tokens", 4096)
        }
        
        # Audio stream configuration
        self.stream_sample_rate = None
        self.stream_channels = None
        self.stream_sample_width = None
        
        logger.info(f"OpenAIRealtimeASR initialized with model: {model}")
        
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
        filename = f"openai_realtime_input_{timestamp}.wav"
        self.debug_wav_path = os.path.join(self.debug_dump_dir, filename)
        
        # Initialize WAV file
        self.debug_wav_file = wave.open(self.debug_wav_path, 'wb')
        self.debug_wav_file.setnchannels(1)  # Mono
        self.debug_wav_file.setsampwidth(2)  # 16-bit
        self.debug_wav_file.setframerate(16000)  # 16kHz
        
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
        
        # Close debug audio dump
        self._close_debug_audio_dump()
        
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
            # Wait briefly for any final results with server VAD
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
            audio_data: Raw audio bytes (must be 16-bit PCM at 16kHz mono)
            sample_rate: Sample rate (ignored, must be 16kHz)
            channels: Number of channels (ignored, must be 1)
            sample_width: Sample width (ignored, must be 2)
        """
        if not self.is_running:
            return
        
        if self.ws_connection and self.is_connected:
            # Write to debug file before sending to API
            self._write_debug_audio(audio_data)
            
            # Send audio data via WebSocket
            self._send_audio_data(audio_data)
            self.audio_buffer_size += len(audio_data)
            
            # With server_vad enabled, the server automatically handles buffer commits
            # when it detects speech activity, so we don't need to manually commit
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
        """Establish WebSocket connection to OpenAI Realtime API with retry mechanism"""
        import os
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"🔌 Connection attempt {attempt + 1}/{self.max_retries}")
                
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "OpenAI-Beta": "realtime=v1"
                }
                
                # Check for HTTP/HTTPS proxy (websockets supports these)
                proxy = None
                for proxy_key in ['https_proxy', 'HTTPS_PROXY', 'http_proxy', 'HTTP_PROXY']:
                    proxy_url = os.environ.get(proxy_key)
                    if proxy_url and proxy_url.startswith('http'):
                        proxy = proxy_url
                        logger.info(f"Using HTTP proxy from {proxy_key}: {proxy}")
                        break
                
                # If only SOCKS proxy is available, we need to bypass it
                # since websockets.sync doesn't support SOCKS
                if not proxy and ('all_proxy' in os.environ or 'ALL_PROXY' in os.environ):
                    socks_proxy = os.environ.get('all_proxy') or os.environ.get('ALL_PROXY')
                    if socks_proxy.startswith('socks'):
                        logger.warning(f"SOCKS proxy detected ({socks_proxy}), but websockets doesn't support it. Bypassing proxy.")
                        # Temporarily remove SOCKS proxy
                        env_backup = {}
                        for key in ['all_proxy', 'ALL_PROXY']:
                            if key in os.environ:
                                env_backup[key] = os.environ.pop(key)
                        
                        try:
                            logger.info("Connecting to OpenAI Realtime API...")
                            self.ws_connection = connect(
                                f"{self.REALTIME_API_URL}?model={self.model}",
                                additional_headers=headers
                            )
                        finally:
                            # Restore SOCKS proxy settings
                            for key, value in env_backup.items():
                                os.environ[key] = value
                        break  # Success, exit retry loop
                    else:
                        # Use non-SOCKS proxy from all_proxy
                        proxy = socks_proxy
                else:
                    # Connect with or without HTTP proxy
                    logger.info(f"Connecting to OpenAI Realtime API{' via proxy' if proxy else ''}...")
                    self.ws_connection = connect(
                        f"{self.REALTIME_API_URL}?model={self.model}",
                        additional_headers=headers,
                        proxy=proxy
                    )
                    break  # Success, exit retry loop
                    
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"⚠️ Connection attempt {attempt + 1} failed: {error_msg}")
                
                # Check if this is the last attempt
                if attempt == self.max_retries - 1:
                    logger.error(f"❌ All {self.max_retries} connection attempts failed!")
                    raise ASRError(f"Failed to connect to OpenAI Realtime API after {self.max_retries} attempts: {error_msg}")
                
                # Wait before retry
                logger.info(f"⏳ Waiting {self.retry_delay}s before retry...")
                time.sleep(self.retry_delay)
                continue
        
        # If we reach here (successful connection), initialize connection
        self.is_connected = True
        self.last_heartbeat = time.time()  # Initialize heartbeat timestamp
        
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
                # Validate audio data
                if not audio_data or len(audio_data) == 0:
                    logger.warning("⚠️ Received empty audio data, skipping")
                    return
                
                # Check if audio data length is reasonable (should be even for 16-bit audio)
                if len(audio_data) % 2 != 0:
                    logger.warning(f"⚠️ Audio data length {len(audio_data)} is odd, may indicate format issue")
                
                # Convert audio data to base64
                import base64
                audio_base64 = base64.b64encode(audio_data).decode('ascii')
                
                # Log audio data info occasionally for debugging
                if len(audio_data) > 0 and self.audio_buffer_size % 16000 == 0:  # Every ~500ms
                    logger.debug(f"📡 Sending audio: {len(audio_data)} bytes (total buffer: {self.audio_buffer_size} bytes)")
                    # Log first few audio samples for debugging
                    import struct
                    if len(audio_data) >= 4:
                        samples = struct.unpack('<hh', audio_data[:4])
                        logger.debug(f"   First samples: {samples}")
                
                # Send audio append message
                self._send_message({
                    "type": "input_audio_buffer.append",
                    "audio": audio_base64
                })
            except Exception as e:
                logger.error(f"Error sending audio data: {e}")
    
    def _receive_loop(self):
        """Receive messages from WebSocket with connection monitoring"""
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while self.is_connected:
            try:
                message = self.ws_connection.recv(timeout=1.0)  # Longer timeout for stability
                if message:
                    self._handle_message(json.loads(message))
                    self.last_heartbeat = time.time()  # Update heartbeat
                    consecutive_errors = 0  # Reset error counter on success
            except TimeoutError:
                # Check connection health
                current_time = time.time()
                if current_time - self.last_heartbeat > self.connection_timeout:
                    logger.warning(f"⚠️ No communication for {self.connection_timeout}s, connection may be stale")
                continue
            except websockets.exceptions.ConnectionClosed as e:
                # Connection closed
                logger.warning(f"🔌 WebSocket connection closed: {e}")
                if self.is_connected:
                    self.is_connected = False
                    logger.info("Attempting to reconnect...")
                    try:
                        self._connect_websocket()
                        logger.info("✅ Reconnection successful")
                        continue
                    except Exception as reconnect_error:
                        logger.error(f"❌ Reconnection failed: {reconnect_error}")
                break
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ Invalid JSON received: {e}")
                consecutive_errors += 1
            except Exception as e:
                if self.is_connected:
                    consecutive_errors += 1
                    logger.error(f"❌ Error in receive loop (#{consecutive_errors}): {e}")
                    
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"💥 Too many consecutive errors ({consecutive_errors}), stopping receive loop")
                        self.is_connected = False
                        break
                    
                    # Small delay before continuing
                    time.sleep(0.5)
                else:
                    break
    
    def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming WebSocket message"""
        msg_type = message.get("type")
        
        # Log all received messages for debugging
        logger.debug(f"Received message type: {msg_type}")
        
        # Only log important message types at INFO level
        important_messages = [
            "error", 
            "input_audio_buffer.speech_started", 
            "input_audio_buffer.speech_stopped",
            "conversation.item.input_audio_transcription.completed",
            "conversation.item.input_audio_transcription.failed",
            "conversation.item.input_audio_transcription.started"
        ]
        if msg_type in important_messages:
            logger.info(f"Realtime API message: {msg_type}")
        elif msg_type not in ["session.created", "session.updated", "response.created", "response.done"]:
            logger.debug(f"Realtime API message: {msg_type}")
        
        if msg_type == "error":
            logger.error(f"Realtime API error: {message.get('error', {})}")
            
        elif msg_type == "session.created" or msg_type == "session.updated":
            logger.info(f"Session {msg_type.split('.')[-1]} successfully")
            
        elif msg_type == "input_audio_buffer.speech_started":
            logger.info("🎙️ Speech started - audio detection activated")
            
        elif msg_type == "input_audio_buffer.speech_stopped":
            logger.info("🛑 Speech stopped - processing audio...")
            
        elif msg_type == "conversation.item.input_audio_transcription.completed":
            # Handle transcription result
            transcript = message.get("transcript", "")
            logger.info(f"✅ Transcription completed: '{transcript}'")
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
            else:
                logger.warning("No transcript received or no callback set")
        
        elif msg_type == "conversation.item.input_audio_transcription.failed":
            # Handle transcription failure
            error_info = message.get("error", {})
            item_id = message.get("item_id", "unknown")
            
            logger.error(f"❌ Transcription failed for item {item_id}: {error_info}")
            
            # Provide diagnostic information
            error_type = error_info.get("type", "unknown")
            error_code = error_info.get("code", "unknown") 
            error_message = error_info.get("message", "No message provided")
            
            if error_type == "server_error":
                logger.error("🔍 Server error detected. Possible causes:")
                logger.error("   - Audio data format issues (not 16-bit PCM)")
                logger.error("   - Audio data corruption during transmission")
                logger.error("   - Insufficient audio data for transcription")
                logger.error("   - OpenAI API temporary issues")
                logger.info(f"📊 Current audio buffer size: {self.audio_buffer_size} bytes")
            elif error_type == "invalid_request_error":
                logger.error("🔍 Invalid request error. Check audio format requirements:")
                logger.error("   - Must be 16kHz sample rate")
                logger.error("   - Must be mono (1 channel)")
                logger.error("   - Must be 16-bit PCM format")
            
            if self.callback:
                # Optionally notify callback of failure
                result = ASRResult(
                    text="",
                    language=None,
                    timestamp=time.time(),
                    is_final=True,
                    metadata={
                        "model": self.model,
                        "item_id": item_id,
                        "error": error_info,
                        "error_type": error_type,
                        "error_code": error_code,
                        "error_message": error_message,
                        "failed": True
                    }
                )
                # Only call callback if user wants error notifications
                # self.callback(result)
                
        elif msg_type == "conversation.item.input_audio_transcription.partial":
            # Handle partial transcription
            transcript = message.get("transcript", "")
            logger.info(f"⚡ Partial transcription: '{transcript}'")
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
                
        elif msg_type == "conversation.item.created":
            logger.info("📝 Conversation item created")
            
        elif msg_type == "conversation.item.input_audio_transcription.started":
            logger.info("🔄 Transcription started")
            
        elif msg_type == "response.audio_transcript.delta":
            # Handle response transcript (if any)
            delta = message.get("delta", "")
            if delta:
                logger.info(f"🎯 Response transcript delta: '{delta}'")
                
        elif msg_type == "input_audio_buffer.committed":
            logger.info("✅ Audio buffer committed for processing")
            
        elif msg_type == "input_audio_buffer.cleared":
            logger.info("🧹 Audio buffer cleared")
            
        elif msg_type == "response.created":
            # Server is creating a response (usually for audio output, not needed for ASR-only)
            logger.debug("📋 Response created")
            
        elif msg_type == "response.done":
            # Server finished processing a response
            logger.debug("✅ Response completed")
            
        else:
            logger.info(f"❓ Unhandled message type: {msg_type}")
            # Log the full message for unknown types to help debug
            logger.debug(f"Full message: {message}")