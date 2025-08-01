import numpy as np
import queue
import threading
import time
import logging
from typing import Callable, Optional
from collections import deque
from .vad import HybridVAD

logger = logging.getLogger(__name__)


class AudioBuffer:
    """Manages audio buffering for ASR processing with overlap support"""
    
    def __init__(self, 
                 sample_rate: int = 48000,
                 channels: int = 2,
                 chunk_duration: float = 5.0,
                 overlap_duration: float = 0.5):
        """
        Initialize audio buffer
        
        Args:
            sample_rate: Audio sample rate in Hz
            channels: Number of audio channels
            chunk_duration: Duration of each chunk to process (seconds)
            overlap_duration: Overlap between chunks (seconds)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = 2  # 16-bit
        self.chunk_duration = chunk_duration
        self.overlap_duration = overlap_duration
        
        # Calculate sizes
        self.chunk_size = int(sample_rate * channels * self.sample_width * chunk_duration)
        self.overlap_size = int(sample_rate * channels * self.sample_width * overlap_duration)
        
        # Buffers
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        self.current_buffer = bytearray()
        self.overlap_buffer = bytearray()
        
        # Threading
        self.is_running = False
        self.processing_thread = None
        
        # Callback
        self.chunk_callback = None
        
        logger.info(f"AudioBuffer initialized: chunk={chunk_duration}s, overlap={overlap_duration}s")
    
    def set_chunk_callback(self, callback: Callable[[bytes, float], None]):
        """Set callback for when a chunk is ready
        
        Args:
            callback: Function(audio_data: bytes, timestamp: float)
        """
        self.chunk_callback = callback
    
    def start(self):
        """Start the buffer processing thread"""
        if self.is_running:
            return
        
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._process_loop)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        logger.info("AudioBuffer started")
    
    def stop(self):
        """Stop the buffer processing thread"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=2)
        
        # Process any remaining data
        if len(self.current_buffer) > 0:
            self._emit_chunk(bytes(self.current_buffer), time.time())
        
        logger.info("AudioBuffer stopped")
    
    def add_audio(self, audio_data: bytes):
        """Add audio data to the buffer
        
        Args:
            audio_data: Raw audio bytes (16-bit PCM)
        """
        if self.is_running:
            self.input_queue.put(audio_data)
    
    def _process_loop(self):
        """Main processing loop"""
        while self.is_running:
            try:
                # Get audio data with timeout
                audio_data = self.input_queue.get(timeout=0.1)
                self.current_buffer.extend(audio_data)
                
                # Process complete chunks
                while len(self.current_buffer) >= self.chunk_size:
                    # Extract chunk
                    chunk = self.current_buffer[:self.chunk_size]
                    
                    # Add overlap from previous chunk
                    if self.overlap_buffer:
                        chunk = self.overlap_buffer + chunk
                    
                    # Emit chunk
                    self._emit_chunk(bytes(chunk), time.time())
                    
                    # Save overlap for next chunk
                    if self.overlap_size > 0:
                        self.overlap_buffer = self.current_buffer[
                            self.chunk_size - self.overlap_size:self.chunk_size
                        ]
                    
                    # Remove processed data
                    self.current_buffer = self.current_buffer[self.chunk_size:]
                    
            except queue.Empty:
                # No new data, check if we should process partial buffer
                if len(self.current_buffer) > self.sample_rate * self.sample_width:
                    # More than 1 second of data waiting
                    chunk = bytes(self.current_buffer)
                    if self.overlap_buffer:
                        chunk = self.overlap_buffer + chunk
                    self._emit_chunk(chunk, time.time())
                    self.current_buffer = bytearray()
                    self.overlap_buffer = bytearray()
                    
            except Exception as e:
                logger.error(f"Error in buffer processing: {e}")
    
    def _emit_chunk(self, audio_data: bytes, timestamp: float):
        """Emit a chunk of audio data
        
        Args:
            audio_data: Audio chunk
            timestamp: Timestamp when chunk was created
        """
        if self.chunk_callback and audio_data:
            try:
                self.chunk_callback(audio_data, timestamp)
            except Exception as e:
                logger.error(f"Error in chunk callback: {e}")
    
    def get_buffered_duration(self) -> float:
        """Get the duration of buffered audio in seconds"""
        buffered_bytes = len(self.current_buffer)
        return buffered_bytes / (self.sample_rate * self.channels * self.sample_width)


class SmartAudioBuffer(AudioBuffer):
    """Enhanced audio buffer with VAD-based dynamic chunking"""
    
    def __init__(self, 
                 sample_rate: int = 48000,
                 channels: int = 2,
                 chunk_duration: float = 5.0,
                 overlap_duration: float = 0.5,
                 use_vad: bool = True):
        """
        Initialize smart audio buffer with VAD
        
        Args:
            use_vad: Whether to use voice activity detection
        """
        super().__init__(sample_rate, channels, chunk_duration, overlap_duration)
        
        # VAD configuration
        self.use_vad = use_vad
        self.vad = HybridVAD(sample_rate=sample_rate) if use_vad else None
        
        # Speech detection state
        self.is_speech_active = False
        self.speech_start_time = None
        self.silence_start_time = None
        self.min_speech_duration = 0.5  # Minimum speech duration before processing
        self.max_silence_duration = 1.0  # Maximum silence before ending speech
    
    def _process_loop(self):
        """Enhanced processing loop with VAD"""
        while self.is_running:
            try:
                # Get audio data with timeout
                audio_data = self.input_queue.get(timeout=0.1)
                self.current_buffer.extend(audio_data)
                
                # VAD processing
                if self.use_vad and self.vad and len(audio_data) > 0:
                    is_speech, confidence = self.vad.process(audio_data)
                    
                    if not self.is_speech_active and is_speech:
                        # Speech started
                        self.is_speech_active = True
                        self.speech_start_time = time.time()
                        self.silence_start_time = None
                        logger.debug(f"Speech detected (confidence: {confidence:.2f})")
                        
                    elif self.is_speech_active and not is_speech:
                        # Potential speech end - start silence timer
                        if self.silence_start_time is None:
                            self.silence_start_time = time.time()
                        elif time.time() - self.silence_start_time > self.max_silence_duration:
                            # Speech ended - emit buffer if it's long enough
                            speech_duration = time.time() - self.speech_start_time
                            if speech_duration >= self.min_speech_duration and len(self.current_buffer) > 0:
                                chunk = bytes(self.current_buffer)
                                if self.overlap_buffer:
                                    chunk = self.overlap_buffer + chunk
                                self._emit_chunk(chunk, self.speech_start_time)
                                self.current_buffer = bytearray()
                                self.overlap_buffer = bytearray()
                            
                            self.is_speech_active = False
                            self.speech_start_time = None
                            self.silence_start_time = None
                            logger.debug(f"Speech ended (duration: {speech_duration:.2f}s)")
                    
                    elif self.is_speech_active and is_speech:
                        # Speech continues - reset silence timer
                        self.silence_start_time = None
                
                # Also check for maximum chunk size
                if len(self.current_buffer) >= self.chunk_size:
                    chunk = self.current_buffer[:self.chunk_size]
                    if self.overlap_buffer:
                        chunk = self.overlap_buffer + chunk
                    
                    self._emit_chunk(bytes(chunk), time.time())
                    
                    if self.overlap_size > 0:
                        self.overlap_buffer = self.current_buffer[
                            self.chunk_size - self.overlap_size:self.chunk_size
                        ]
                    
                    self.current_buffer = self.current_buffer[self.chunk_size:]
                    
            except queue.Empty:
                # Check timeout for active speech
                if self.is_speech_active and self.speech_start_time:
                    duration = time.time() - self.speech_start_time
                    if duration > self.chunk_duration:
                        # Force emit after max duration
                        if len(self.current_buffer) > 0:
                            chunk = bytes(self.current_buffer)
                            if self.overlap_buffer:
                                chunk = self.overlap_buffer + chunk
                            self._emit_chunk(chunk, self.speech_start_time)
                            self.current_buffer = bytearray()
                            self.overlap_buffer = bytearray()
                            self.is_speech_active = False
                            self.speech_start_time = None
                            self.silence_start_time = None
                            
            except Exception as e:
                logger.error(f"Error in smart buffer processing: {e}")