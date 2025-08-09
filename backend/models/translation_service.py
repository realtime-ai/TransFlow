import logging
import threading
import queue
import time
from typing import Optional, Dict, Any, Callable, List
from backend.api.translation_client import TranslationClient
from config import Config

logger = logging.getLogger(__name__)


class TranslationService:
    """Service to manage real-time translation of ASR output"""
    
    def __init__(self, api_key: Optional[str] = None, provider: str = "auto"):
        """Initialize translation service
        
        Args:
            api_key: API key (OpenAI or Dashscope), defaults to environment variable
            provider: Translation provider ('qwen', 'openai', or 'auto')
        """
        self.translation_client = TranslationClient(api_key=api_key, provider=provider)
        self.is_running = False
        self.processing_thread = None
        
        # Queues
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        
        # Settings
        self.source_language = 'auto'
        self.target_language = 'en'
        self.callback = None
        
        # Sentence buffering
        self.sentence_buffer = ""
        self.sentence_delimiters = ['.', '!', '?', '。', '！', '？', '；']
        self.max_buffer_size = 500  # Max characters before forcing translation
        self.buffer_timeout = 3.0  # Seconds to wait before translating partial sentence
        self.last_buffer_time = time.time()
        
        # Translation cache to avoid duplicate translations
        self.translation_cache = {}
        self.max_cache_size = 100
        
        logger.info("TranslationService initialized")
    
    def set_languages(self, source_language: str, target_language: str):
        """Set source and target languages
        
        Args:
            source_language: Source language code (e.g., 'zh', 'en', 'auto')
            target_language: Target language code
        """
        self.source_language = source_language
        self.target_language = target_language
        logger.info(f"Languages set: {source_language} -> {target_language}")
    
    def set_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback for translation results
        
        Args:
            callback: Function that receives translation results
        """
        self.callback = callback
    
    def start(self):
        """Start the translation service"""
        if self.is_running:
            logger.warning("TranslationService is already running")
            return
        
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._process_loop)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        logger.info("TranslationService started")
    
    def stop(self):
        """Stop the translation service"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
        
        # Process any remaining text
        if self.sentence_buffer:
            self._translate_text(self.sentence_buffer)
        
        logger.info("TranslationService stopped")
    
    def add_transcription(self, transcription: Dict[str, Any]):
        """Add ASR transcription for translation
        
        Args:
            transcription: ASR result with 'text' and 'language' fields
        """
        if self.is_running:
            self.input_queue.put(transcription)
    
    def _process_loop(self):
        """Main processing loop"""
        while self.is_running:
            try:
                # Check for new transcriptions
                try:
                    transcription = self.input_queue.get(timeout=0.1)
                    self._process_transcription(transcription)
                except queue.Empty:
                    # Check if we need to flush buffer due to timeout
                    if self.sentence_buffer and \
                       time.time() - self.last_buffer_time > self.buffer_timeout:
                        self._translate_text(self.sentence_buffer)
                        self.sentence_buffer = ""
                
            except Exception as e:
                logger.error(f"Error in translation processing loop: {e}")
    
    def _process_transcription(self, transcription: Dict[str, Any]):
        """Process a single transcription
        
        Args:
            transcription: ASR result
        """
        text = transcription.get('text', '').strip()
        if not text:
            return
        
        # Update last buffer time
        self.last_buffer_time = time.time()
        
        # Add to sentence buffer
        self.sentence_buffer += " " + text if self.sentence_buffer else text
        
        # Extract complete sentences
        sentences = self._extract_sentences(self.sentence_buffer)
        
        # Keep incomplete sentence in buffer
        if sentences['incomplete']:
            self.sentence_buffer = sentences['incomplete']
        else:
            self.sentence_buffer = ""
        
        # Translate complete sentences
        for sentence in sentences['complete']:
            self._translate_text(sentence)
        
        # Force translation if buffer is too large
        if len(self.sentence_buffer) > self.max_buffer_size:
            self._translate_text(self.sentence_buffer)
            self.sentence_buffer = ""
    
    def _extract_sentences(self, text: str) -> Dict[str, Any]:
        """Extract complete sentences from text
        
        Args:
            text: Input text
            
        Returns:
            Dict with 'complete' sentences list and 'incomplete' remainder
        """
        sentences = []
        current = ""
        
        i = 0
        while i < len(text):
            current += text[i]
            
            # Check if we hit a sentence delimiter
            if text[i] in self.sentence_delimiters:
                # Look ahead for quotes or parentheses
                if i + 1 < len(text) and text[i + 1] in ['"', "'", ')', ']', '}', '」', '』']:
                    i += 1
                    current += text[i]
                
                sentences.append(current.strip())
                current = ""
            
            i += 1
        
        return {
            'complete': sentences,
            'incomplete': current.strip()
        }
    
    def _translate_text(self, text: str):
        """Translate text and emit result
        
        Args:
            text: Text to translate
        """
        if not text or not text.strip():
            return
        
        # Check cache
        cache_key = f"{text}:{self.source_language}:{self.target_language}"
        if cache_key in self.translation_cache:
            cached_result = self.translation_cache[cache_key]
            cached_result['from_cache'] = True
            self._emit_result(cached_result)
            return
        
        try:
            # Translate without context
            result = self.translation_client.translate(
                text=text,
                source_language=self.source_language,
                target_language=self.target_language,
                use_context=False
            )
            
            # Add timestamp
            result['timestamp'] = time.time()
            
            # Cache result
            self.translation_cache[cache_key] = result
            
            # Limit cache size
            if len(self.translation_cache) > self.max_cache_size:
                # Remove oldest entries
                oldest_keys = list(self.translation_cache.keys())[:10]
                for key in oldest_keys:
                    del self.translation_cache[key]
            
            # Emit result
            self._emit_result(result)
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            error_result = {
                'source_text': text,
                'translation': '',
                'error': str(e),
                'timestamp': time.time()
            }
            self._emit_result(error_result)
    
    def _emit_result(self, result: Dict[str, Any]):
        """Emit translation result
        
        Args:
            result: Translation result
        """
        if self.callback:
            try:
                self.callback(result)
            except Exception as e:
                logger.error(f"Error in translation callback: {e}")
    
    def clear_cache(self):
        """Clear translation cache"""
        self.translation_cache.clear()
        self.sentence_buffer = ""
        logger.info("Translation cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            'is_running': self.is_running,
            'queue_size': self.input_queue.qsize(),
            'buffer_length': len(self.sentence_buffer),
            'cache_size': len(self.translation_cache),
            'languages': {
                'source': self.source_language,
                'target': self.target_language
            }
        }