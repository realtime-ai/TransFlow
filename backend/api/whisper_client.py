import os
import io
import tempfile
from typing import Optional, Dict, Any
from openai import OpenAI
import logging
from config import Config

logger = logging.getLogger(__name__)


class WhisperClient:
    """OpenAI Whisper API wrapper for speech recognition"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Whisper client with API key
        
        Args:
            api_key: OpenAI API key, defaults to environment variable
        """
        self.api_key = api_key or Config.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY in .env file.")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = Config.OPENAI_MODEL_WHISPER
        
    def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        response_format: str = "json",
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        """Transcribe audio using Whisper API
        
        Args:
            audio_data: Audio data in bytes (WAV format)
            language: ISO-639-1 language code (e.g., 'en', 'zh'), None for auto-detection
            prompt: Optional text to guide the model's style
            response_format: Output format ('json', 'text', 'srt', 'vtt')
            temperature: Sampling temperature (0-1), lower is more deterministic
            
        Returns:
            Transcription result dictionary with 'text' and optionally 'language'
        """
        try:
            # Create a temporary file for the audio data
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.wav', delete=False) as tmp_file:
                tmp_file.write(audio_data)
                tmp_file_path = tmp_file.name
            
            # Open the file for the API
            with open(tmp_file_path, 'rb') as audio_file:
                # Prepare parameters
                params = {
                    "model": self.model,
                    "file": audio_file,
                    "response_format": response_format,
                    "temperature": temperature
                }
                
                if language:
                    params["language"] = language
                    
                if prompt:
                    params["prompt"] = prompt
                
                # Call Whisper API
                response = self.client.audio.transcriptions.create(**params)
                
                # Clean up temporary file
                os.unlink(tmp_file_path)
                
                # Format response based on response_format
                if response_format == "json":
                    return {
                        "text": response.text,
                        "language": getattr(response, 'language', language or 'unknown')
                    }
                else:
                    return {"text": response}
                    
        except Exception as e:
            logger.error(f"Whisper transcription error: {str(e)}")
            # Clean up temporary file if it exists
            if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
            raise
            
    def transcribe_stream(
        self,
        audio_stream: io.BytesIO,
        **kwargs
    ) -> Dict[str, Any]:
        """Transcribe audio from a BytesIO stream
        
        Args:
            audio_stream: Audio data as BytesIO stream
            **kwargs: Additional arguments passed to transcribe()
            
        Returns:
            Transcription result
        """
        audio_data = audio_stream.getvalue()
        return self.transcribe(audio_data, **kwargs)
        
    def detect_language(self, audio_data: bytes) -> str:
        """Detect the language of the audio
        
        Args:
            audio_data: Audio data in bytes
            
        Returns:
            Detected ISO-639-1 language code
        """
        result = self.transcribe(
            audio_data,
            response_format="json",
            temperature=0.0
        )
        return result.get('language', 'unknown')