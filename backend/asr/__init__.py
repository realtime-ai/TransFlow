"""
ASR (Automatic Speech Recognition) module

This module provides an abstract base class for ASR implementations and 
several concrete implementations for different ASR services.

Available implementations:
- WhisperClient: OpenAI Whisper API for high-quality transcription
- OpenAIRealtimeASR: OpenAI Realtime API for low-latency streaming transcription

Usage:
    # Using Whisper API for file transcription
    from backend.asr import WhisperClient
    
    whisper = WhisperClient(api_key="your-api-key")
    result = whisper.transcribe_file("audio.wav")
    print(result.text)
    
    # Using Whisper API for streaming
    def on_result(result):
        print(f"Transcription: {result.text}")
    
    whisper.set_callback(on_result)
    with whisper:
        # Add audio data...
        whisper.add_audio_data(audio_bytes)
    
    # Using Realtime API for low-latency streaming
    from backend.asr import OpenAIRealtimeASR
    
    realtime = OpenAIRealtimeASR(api_key="your-api-key")
    realtime.set_callback(on_result)
    with realtime:
        realtime.start_stream(sample_rate=24000, channels=1)
        # Add audio data...
        realtime.add_audio_data(audio_bytes)
        realtime.end_stream()
"""

from .base import ASRBase, StreamingASRBase, ASRResult, ASRError
from .whisper_client import WhisperClient

# Optional import for OpenAI Realtime (requires websockets)
try:
    from .openai_realtime import OpenAIRealtimeASR
    _REALTIME_AVAILABLE = True
except ImportError as e:
    _REALTIME_AVAILABLE = False
    import logging
    logging.getLogger(__name__).info(
        f"OpenAI Realtime ASR not available: {e}. "
        "Install websockets package to enable: pip install websockets"
    )

__all__ = [
    # Base classes
    'ASRBase', 
    'StreamingASRBase',
    'ASRResult',
    'ASRError',
    
    # Implementations
    'WhisperClient',
]

# Add OpenAI Realtime if available
if _REALTIME_AVAILABLE:
    __all__.append('OpenAIRealtimeASR')


def get_available_asrs():
    """
    Get list of available ASR implementations
    
    Returns:
        dict: Dictionary mapping ASR names to their classes
    """
    asrs = {
        'whisper': WhisperClient,
    }
    
    if _REALTIME_AVAILABLE:
        asrs['openai_realtime'] = OpenAIRealtimeASR
    
    return asrs


def create_asr(asr_type: str, **kwargs):
    """
    Factory function to create ASR instances
    
    Args:
        asr_type: Type of ASR ('whisper', 'openai_realtime')
        **kwargs: Arguments to pass to the ASR constructor
        
    Returns:
        ASR instance
        
    Raises:
        ValueError: If asr_type is not supported
    """
    asrs = get_available_asrs()
    
    if asr_type not in asrs:
        available = ', '.join(asrs.keys())
        raise ValueError(f"Unsupported ASR type '{asr_type}'. Available: {available}")
    
    return asrs[asr_type](**kwargs)