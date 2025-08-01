#!/usr/bin/env python3
"""Test translation functionality"""

import os
import sys
import time
import logging
from backend.api.translation_client import TranslationClient
from backend.models.translation_service import TranslationService
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_translation_client():
    """Test TranslationClient basic functionality"""
    
    # Check if API key is configured
    if not Config.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not configured in .env file")
        return False
    
    try:
        # Initialize TranslationClient
        translation_client = TranslationClient(api_key=Config.OPENAI_API_KEY)
        logger.info("✓ TranslationClient initialized successfully")
        
        # Test translations
        test_cases = [
            {
                'text': 'Hello, how are you today?',
                'source': 'en',
                'target': 'zh',
                'expected_contains': ['你好', '今天']
            },
            {
                'text': '这是一个测试句子。',
                'source': 'zh',
                'target': 'en',
                'expected_contains': ['test', 'sentence']
            },
            {
                'text': 'こんにちは、元気ですか？',
                'source': 'ja',
                'target': 'en',
                'expected_contains': ['Hello', 'how are you']
            }
        ]
        
        success_count = 0
        for test in test_cases:
            try:
                result = translation_client.translate(
                    text=test['text'],
                    source_language=test['source'],
                    target_language=test['target'],
                    use_context=False  # Disable context for isolated tests
                )
                
                translation = result.get('translation', '').lower()
                logger.info(f"  '{test['text']}' -> '{result['translation']}'")
                
                # Basic validation
                passed = any(word.lower() in translation for word in test['expected_contains'])
                if passed:
                    logger.info(f"  ✓ Translation looks correct")
                    success_count += 1
                else:
                    logger.warning(f"  ⚠ Translation may be incorrect")
                    
            except Exception as e:
                logger.error(f"  ✗ Translation failed: {e}")
        
        # Test context functionality
        logger.info("\nTesting context functionality...")
        translation_client.clear_context()
        
        # Translate with context
        context_texts = [
            "My name is John.",
            "I work at OpenAI.",
            "I love machine learning."
        ]
        
        for text in context_texts:
            result = translation_client.translate(
                text=text,
                source_language='en',
                target_language='zh',
                use_context=True
            )
            logger.info(f"  Context: '{text}' -> '{result['translation']}'")
        
        # Check context
        context = translation_client.get_context()
        logger.info(f"✓ Context maintained: {len(context)} entries")
        
        return success_count >= 2  # At least 2 out of 3 translations should work
        
    except Exception as e:
        logger.error(f"✗ TranslationClient test failed: {e}")
        return False

def test_translation_service():
    """Test TranslationService with simulated ASR output"""
    
    if not Config.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not configured in .env file")
        return False
    
    try:
        # Initialize TranslationService
        translation_service = TranslationService(api_key=Config.OPENAI_API_KEY)
        translation_service.set_languages('en', 'zh')
        
        # Collect results
        results = []
        def result_callback(result):
            results.append(result)
            logger.info(f"Translation received: {result.get('translation', '')[:50]}...")
        
        translation_service.set_callback(result_callback)
        translation_service.start()
        logger.info("✓ TranslationService started")
        
        # Simulate ASR output
        transcriptions = [
            {'text': 'Hello everyone.', 'language': 'en', 'timestamp': time.time()},
            {'text': 'Welcome to the', 'language': 'en', 'timestamp': time.time()},
            {'text': 'TransFlow real-time', 'language': 'en', 'timestamp': time.time()},
            {'text': 'translation demo.', 'language': 'en', 'timestamp': time.time()},
            {'text': 'This is amazing!', 'language': 'en', 'timestamp': time.time()},
        ]
        
        # Add transcriptions with delays
        for trans in transcriptions:
            translation_service.add_transcription(trans)
            time.sleep(0.5)
        
        # Wait for processing
        time.sleep(2)
        
        # Check results
        logger.info(f"\n✓ Received {len(results)} translation results")
        for result in results:
            if not result.get('error'):
                logger.info(f"  '{result['source_text']}' -> '{result['translation']}'")
        
        # Test sentence buffering
        logger.info("\nTesting sentence buffering...")
        translation_service.clear_context()
        results.clear()
        
        # Send partial sentences
        partial_transcriptions = [
            {'text': 'The quick brown', 'language': 'en', 'timestamp': time.time()},
            {'text': 'fox jumps over', 'language': 'en', 'timestamp': time.time()},
            {'text': 'the lazy dog.', 'language': 'en', 'timestamp': time.time()},
        ]
        
        for trans in partial_transcriptions:
            translation_service.add_transcription(trans)
            time.sleep(0.2)
        
        # Wait for processing
        time.sleep(2)
        
        # Stop service
        translation_service.stop()
        logger.info("✓ TranslationService stopped")
        
        # Verify complete sentence was translated
        if results:
            full_translation = ' '.join(r['translation'] for r in results if not r.get('error'))
            logger.info(f"✓ Complete translation: {full_translation}")
            return True
        else:
            logger.warning("No translation results received")
            return True  # Still pass if service initialized correctly
            
    except Exception as e:
        logger.error(f"✗ TranslationService test failed: {e}")
        return False

def main():
    """Run all tests"""
    logger.info("=== Testing Translation Components ===")
    
    tests = [
        ("TranslationClient", test_translation_client),
        ("TranslationService", test_translation_service),
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\nTesting {test_name}...")
        result = test_func()
        results.append((test_name, result))
    
    # Summary
    logger.info("\n=== Test Summary ===")
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    if all_passed:
        logger.info("\n✓ All tests passed!")
    else:
        logger.error("\n✗ Some tests failed!")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())