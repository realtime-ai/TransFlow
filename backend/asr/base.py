"""Abstract base class for ASR (Automatic Speech Recognition) implementations"""

from abc import ABC, abstractmethod
from typing import Optional, Callable, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ASRResult:
    """Standardized ASR result format"""
    
    def __init__(self, 
                 text: str, 
                 language: Optional[str] = None,
                 confidence: Optional[float] = None,
                 timestamp: Optional[float] = None,
                 duration: Optional[float] = None,
                 is_final: bool = True,
                 metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize ASR result
        
        Args:
            text: Transcribed text
            language: Detected language (ISO-639-1 code)
            confidence: Confidence score (0.0 to 1.0)
            timestamp: Timestamp when the speech started
            duration: Duration of the speech segment
            is_final: Whether this is a final result (vs interim/partial)
            metadata: Additional metadata specific to the ASR provider
        """
        self.text = text
        self.language = language
        self.confidence = confidence
        self.timestamp = timestamp
        self.duration = duration
        self.is_final = is_final
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            'text': self.text,
            'language': self.language,
            'confidence': self.confidence,
            'timestamp': self.timestamp,
            'duration': self.duration,
            'is_final': self.is_final,
            'metadata': self.metadata
        }
    
    def __repr__(self):
        return f"ASRResult(text='{self.text[:50]}...', language={self.language}, is_final={self.is_final})"


class ASRError(Exception):
    """Base exception for ASR-related errors"""
    pass


class ASRBase(ABC):
    """Abstract base class for ASR implementations"""
    
    def __init__(self, **kwargs):
        """
        Initialize ASR base
        
        Args:
            **kwargs: Implementation-specific configuration
        """
        self.is_running = False
        self.callback: Optional[Callable[[ASRResult], None]] = None
        self._config = kwargs
        
    @abstractmethod
    def start(self) -> None:
        """
        Start the ASR service
        
        Raises:
            ASRError: If service fails to start
        """
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """
        Stop the ASR service
        """
        pass
    
    @abstractmethod
    def add_audio_data(self, audio_data: bytes, 
                      sample_rate: Optional[int] = None,
                      channels: Optional[int] = None,
                      sample_width: Optional[int] = None) -> None:
        """
        Add audio data for transcription
        
        Args:
            audio_data: Raw audio bytes
            sample_rate: Sample rate in Hz (if different from configured)
            channels: Number of channels (if different from configured)
            sample_width: Sample width in bytes (if different from configured)
        """
        pass
    
    def set_callback(self, callback: Callable[[ASRResult], None]) -> None:
        """
        Set callback function for ASR results
        
        Args:
            callback: Function that receives ASRResult objects
        """
        self.callback = callback
        logger.debug(f"{self.__class__.__name__}: Callback set")
    
    def set_language(self, language: Optional[str] = None) -> None:
        """
        Set the source language for recognition
        
        Args:
            language: ISO-639-1 language code (e.g., 'zh', 'en', 'ja')
                     None for auto-detection
        """
        # Default implementation - can be overridden
        logger.info(f"{self.__class__.__name__}: Language set to {language or 'auto-detect'}")
    
    def get_supported_languages(self) -> Optional[list[str]]:
        """
        Get list of supported languages
        
        Returns:
            List of ISO-639-1 language codes or None if all languages supported
        """
        return None  # Default: all languages supported
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get ASR capabilities
        
        Returns:
            Dictionary describing capabilities like:
            - realtime: bool
            - streaming: bool
            - max_audio_length: int (seconds)
            - supported_formats: list[str]
            - etc.
        """
        return {
            'realtime': False,
            'streaming': False,
            'max_audio_length': None,
            'supported_formats': ['wav', 'mp3', 'flac'],
        }
    
    def __enter__(self):
        """Context manager support"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        self.stop()
        return False


class StreamingASRBase(ASRBase):
    """Base class for streaming ASR implementations with real-time support"""
    
    @abstractmethod
    def start_stream(self, 
                    sample_rate: int,
                    channels: int = 1,
                    sample_width: int = 2,
                    **kwargs) -> None:
        """
        Start a new audio stream for real-time transcription
        
        Args:
            sample_rate: Sample rate in Hz
            channels: Number of audio channels
            sample_width: Sample width in bytes (e.g., 2 for 16-bit)
            **kwargs: Additional implementation-specific parameters
        """
        pass
    
    @abstractmethod
    def end_stream(self) -> Optional[ASRResult]:
        """
        End the current audio stream and get final result
        
        Returns:
            Final transcription result if available
        """
        pass
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get capabilities - streaming ASRs support real-time"""
        capabilities = super().get_capabilities()
        capabilities.update({
            'realtime': True,
            'streaming': True,
        })
        return capabilities