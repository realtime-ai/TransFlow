import logging
from typing import Optional, Dict, Any, List
from openai import OpenAI
from config import Config

logger = logging.getLogger(__name__)


class TranslationClient:
    """OpenAI GPT-4o-mini client for translation"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize translation client with API key
        
        Args:
            api_key: OpenAI API key, defaults to environment variable
        """
        self.api_key = api_key or Config.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY in .env file.")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = Config.OPENAI_MODEL_TRANSLATION
        
        # Context management
        self.context_window = []
        self.max_context_size = 10  # Keep last 10 translations for context
        
    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
        context: Optional[List[Dict[str, str]]] = None,
        use_context: bool = True
    ) -> Dict[str, Any]:
        """Translate text using GPT-4o-mini
        
        Args:
            text: Text to translate
            source_language: Source language code (e.g., 'zh', 'en')
            target_language: Target language code
            context: Optional context from previous translations
            use_context: Whether to use context for better translations
            
        Returns:
            Translation result dictionary
        """
        try:
            # Get language names
            source_lang_name = Config.SUPPORTED_LANGUAGES.get(source_language, source_language)
            target_lang_name = Config.SUPPORTED_LANGUAGES.get(target_language, target_language)
            
            # Build system prompt
            system_prompt = f"""You are a professional translator specializing in real-time speech translation.
Translate the following {source_lang_name} text to {target_lang_name}.
Maintain the natural flow and context of spoken language.
Keep technical terms consistent throughout the translation.
Only provide the translation, no explanations."""
            
            # Build messages
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add context if available and enabled
            if use_context and (context or self.context_window):
                context_items = context or self.context_window[-5:]  # Last 5 translations
                if context_items:
                    context_text = "\n".join([
                        f"Previous: {item.get('source', '')}\nTranslation: {item.get('translation', '')}"
                        for item in context_items
                    ])
                    messages.append({
                        "role": "system",
                        "content": f"Context from previous translations:\n{context_text}"
                    })
            
            # Add the text to translate
            messages.append({"role": "user", "content": text})
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,  # Lower temperature for more consistent translations
                max_tokens=1000
            )
            
            # Extract translation
            translation = response.choices[0].message.content.strip()
            
            # Update context window
            context_entry = {
                "source": text,
                "translation": translation,
                "source_language": source_language,
                "target_language": target_language
            }
            self.context_window.append(context_entry)
            
            # Keep context window size manageable
            if len(self.context_window) > self.max_context_size:
                self.context_window.pop(0)
            
            return {
                "translation": translation,
                "source_text": text,
                "source_language": source_language,
                "target_language": target_language,
                "model": self.model
            }
            
        except Exception as e:
            logger.error(f"Translation error: {str(e)}")
            raise
            
    def translate_batch(
        self,
        texts: List[str],
        source_language: str,
        target_language: str
    ) -> List[Dict[str, Any]]:
        """Translate multiple texts in batch
        
        Args:
            texts: List of texts to translate
            source_language: Source language code
            target_language: Target language code
            
        Returns:
            List of translation results
        """
        results = []
        
        for text in texts:
            try:
                result = self.translate(
                    text,
                    source_language,
                    target_language,
                    use_context=True
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Batch translation error for text '{text[:50]}...': {e}")
                results.append({
                    "translation": "",
                    "source_text": text,
                    "error": str(e)
                })
                
        return results
        
    def clear_context(self):
        """Clear the translation context"""
        self.context_window.clear()
        logger.info("Translation context cleared")
        
    def get_context(self) -> List[Dict[str, str]]:
        """Get current translation context
        
        Returns:
            List of context entries
        """
        return self.context_window.copy()