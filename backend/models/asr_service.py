import queue
import threading
import time
import logging
from typing import Optional, Callable, Dict, Any
from backend.api.whisper_client import WhisperClient
from backend.utils.audio_converter import AudioConverter
from backend.utils.vad import VoiceActivityDetector
from config import Config

logger = logging.getLogger(__name__)


class ASRService:
    """Automatic Speech Recognition service with real-time processing"""
    
    def __init__(
        self,
        whisper_client: Optional[WhisperClient] = None,
        chunk_duration: float = 5.0,
        language: Optional[str] = None,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        use_vad: bool = True
    ):
        """Initialize ASR service
        
        Args:
            whisper_client: Whisper client instance
            chunk_duration: Duration of audio chunks to process
            language: Language code for transcription (None for auto-detect)
            callback: Callback function for transcription results
            use_vad: Whether to use Voice Activity Detection
        """
        self.whisper_client = whisper_client or WhisperClient()
        self.chunk_duration = chunk_duration
        self.language = language
        self.callback = callback
        self.use_vad = use_vad
        
        # Audio buffer and processing state
        self.audio_buffer = bytearray()
        self.speech_buffer = bytearray()  # Buffer for speech segments
        self.processing_queue = queue.Queue()
        self.is_running = False
        self.processing_thread = None
        
        # Configuration from config
        self.sample_rate = Config.AUDIO_SAMPLE_RATE
        self.channels = Config.AUDIO_CHANNELS
        
        # Voice Activity Detection
        if self.use_vad:
            self.vad = VoiceActivityDetector(sample_rate=self.sample_rate)
        else:
            self.vad = None
        
        # Timing and context
        self.last_transcript_time = 0
        self.context_prompt = ""
        self.transcript_history = []
        
    def start(self):
        """Start the ASR service"""
        if self.is_running:
            logger.warning("ASR service already running")
            return
            
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._process_audio_chunks)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        logger.info("ASR service started")
        
    def stop(self):
        """Stop the ASR service"""
        if not self.is_running:
            return
            
        self.is_running = False
        # Process any remaining audio
        if len(self.audio_buffer) > 0:
            self._process_buffer()
            
        # Wait for processing to complete
        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)
            
        logger.info("ASR service stopped")
        
    def add_audio_data(self, pcm_data: bytes):
        """Add audio data to the buffer
        
        Args:
            pcm_data: Raw PCM audio data (16-bit)
        """
        self.audio_buffer.extend(pcm_data)
        
        # Check if we have enough data for a chunk
        bytes_per_second = self.sample_rate * self.channels * 2  # 16-bit
        chunk_size = int(self.chunk_duration * bytes_per_second)
        
        if len(self.audio_buffer) >= chunk_size:
            # Extract chunk and add to processing queue
            chunk = bytes(self.audio_buffer[:chunk_size])
            self.audio_buffer = self.audio_buffer[chunk_size:]
            self.processing_queue.put(chunk)
            
    def _process_audio_chunks(self):
        """Background thread for processing audio chunks"""
        while self.is_running:
            try:
                # Get chunk from queue with timeout
                chunk = self.processing_queue.get(timeout=0.1)
                self._transcribe_chunk(chunk)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing audio chunk: {e}")
                
    def _transcribe_chunk(self, pcm_chunk: bytes):
        """Transcribe a single audio chunk
        
        Args:
            pcm_chunk: PCM audio data chunk
        """
        try:
            # Prepare audio for Whisper
            wav_data = AudioConverter.prepare_for_whisper(
                pcm_chunk,
                sample_rate=self.sample_rate,
                channels=self.channels
            )
            
            # Transcribe with context
            result = self.whisper_client.transcribe(
                wav_data,
                language=self.language,
                prompt=self._get_context_prompt(),
                temperature=0.0
            )
            
            # Process result
            if result and result.get('text', '').strip():
                self._handle_transcription_result(result)
                
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            
    def _get_context_prompt(self) -> str:
        """Generate context prompt from recent transcripts
        
        Returns:
            Context prompt string
        """
        # Use recent transcripts as context
        if self.transcript_history:
            # Take last 3 transcripts
            recent = self.transcript_history[-3:]
            return " ".join([t['text'] for t in recent])
        return ""
        
    def _handle_transcription_result(self, result: Dict[str, Any]):
        """Handle transcription result
        
        Args:
            result: Transcription result from Whisper
        """
        # Add timestamp
        result['timestamp'] = time.time()
        
        # Detect language if auto-detecting
        if self.language is None and 'language' not in result:
            result['language'] = 'unknown'
            
        # Add to history
        self.transcript_history.append(result)
        
        # Keep history size manageable
        if len(self.transcript_history) > 10:
            self.transcript_history.pop(0)
            
        # Call callback if provided
        if self.callback:
            self.callback(result)
            
        logger.info(f"Transcribed: {result['text'][:50]}...")
        
    def _process_buffer(self):
        """Process any remaining audio in the buffer"""
        if len(self.audio_buffer) > 0:
            # Pad with silence if needed to meet minimum duration
            min_duration = 1.0  # Minimum 1 second
            bytes_per_second = self.sample_rate * self.channels * 2
            min_size = int(min_duration * bytes_per_second)
            
            if len(self.audio_buffer) < min_size:
                # Pad with silence
                padding = bytes(min_size - len(self.audio_buffer))
                pcm_chunk = bytes(self.audio_buffer) + padding
            else:
                pcm_chunk = bytes(self.audio_buffer)
                
            self._transcribe_chunk(pcm_chunk)
            self.audio_buffer.clear()
            
    def set_language(self, language: Optional[str]):
        """Set the transcription language
        
        Args:
            language: Language code or None for auto-detect
        """
        self.language = language
        logger.info(f"ASR language set to: {language or 'auto-detect'}")
        
    def clear_history(self):
        """Clear transcript history"""
        self.transcript_history.clear()
        self.context_prompt = ""