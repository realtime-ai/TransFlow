#!/usr/bin/env python3
"""Test real-time communication flow"""

import time
import logging
import asyncio
import socketio
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TransFlowTestClient:
    def __init__(self):
        self.sio = socketio.Client()
        self.connected = False
        self.setup_event_handlers()
        
    def setup_event_handlers(self):
        @self.sio.event
        def connect():
            logger.info("✓ Connected to server")
            self.connected = True
            
        @self.sio.event
        def disconnect():
            logger.info("Disconnected from server")
            self.connected = False
            
        @self.sio.event
        def connection_status(data):
            logger.info(f"✓ Connection status received: {data}")
            
        @self.sio.event
        def error(data):
            logger.error(f"Server error: {data}")
            
        @self.sio.event
        def audio_sources(data):
            logger.info(f"✓ Audio sources received: {len(data.get('applications', []))} apps, {len(data.get('devices', []))} devices")
            
        @self.sio.event
        def languages_updated(data):
            logger.info(f"✓ Languages updated: {data}")
            
        @self.sio.event
        def recording_started(data):
            logger.info(f"✓ Recording started: {data}")
            
        @self.sio.event
        def recording_stopped(data):
            logger.info(f"✓ Recording stopped: {data}")
            
        @self.sio.event
        def transcription(data):
            logger.info(f"✓ Transcription received: '{data.get('text', '')[:50]}...'")
            
        @self.sio.event
        def translation(data):
            logger.info(f"✓ Translation received: '{data.get('translation', '')[:50]}...'")
            
        @self.sio.event
        def heartbeat_response(data):
            logger.info(f"✓ Heartbeat response: latency={data.get('latency', 0)*1000:.1f}ms")
    
    def connect(self, url='http://localhost:5000'):
        try:
            self.sio.connect(url)
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    def disconnect(self):
        self.sio.disconnect()
    
    def test_basic_connection(self):
        """Test basic connection and disconnection"""
        logger.info("\n=== Testing Basic Connection ===")
        
        # Connect
        if not self.connect():
            return False
        
        # Wait for connection
        time.sleep(1)
        
        # Send ping
        self.sio.emit('ping')
        time.sleep(0.5)
        
        # Disconnect
        self.disconnect()
        time.sleep(0.5)
        
        return True
    
    def test_language_settings(self):
        """Test language configuration"""
        logger.info("\n=== Testing Language Settings ===")
        
        if not self.connect():
            return False
        
        time.sleep(0.5)
        
        # Set languages
        self.sio.emit('set_languages', {
            'sourceLanguage': 'zh',
            'targetLanguage': 'en'
        })
        
        time.sleep(1)
        
        # Change languages
        self.sio.emit('set_languages', {
            'sourceLanguage': 'en',
            'targetLanguage': 'zh'
        })
        
        time.sleep(1)
        
        self.disconnect()
        return True
    
    def test_audio_sources(self):
        """Test audio source retrieval"""
        logger.info("\n=== Testing Audio Sources ===")
        
        if not self.connect():
            return False
        
        time.sleep(0.5)
        
        # Request audio sources
        self.sio.emit('get_audio_sources')
        
        time.sleep(2)
        
        self.disconnect()
        return True
    
    def test_heartbeat(self):
        """Test heartbeat mechanism"""
        logger.info("\n=== Testing Heartbeat ===")
        
        if not self.connect():
            return False
        
        time.sleep(0.5)
        
        # Send heartbeat
        for i in range(3):
            self.sio.emit('heartbeat', {'timestamp': time.time()})
            time.sleep(1)
        
        self.disconnect()
        return True
    
    def test_error_handling(self):
        """Test error handling"""
        logger.info("\n=== Testing Error Handling ===")
        
        if not self.connect():
            return False
        
        time.sleep(0.5)
        
        # Send invalid data
        self.sio.emit('set_languages', {})  # Missing required fields
        time.sleep(0.5)
        
        # Send to non-existent event
        self.sio.emit('non_existent_event', {'test': 'data'})
        time.sleep(0.5)
        
        self.disconnect()
        return True
    
    def test_reconnection(self):
        """Test reconnection mechanism"""
        logger.info("\n=== Testing Reconnection ===")
        
        # Connect
        if not self.connect():
            return False
        
        time.sleep(0.5)
        logger.info("Connected, simulating network interruption...")
        
        # Force disconnect
        self.sio.disconnect()
        time.sleep(1)
        
        # Reconnect
        logger.info("Attempting reconnection...")
        if not self.connect():
            return False
        
        time.sleep(0.5)
        logger.info("✓ Reconnection successful")
        
        self.disconnect()
        return True

def main():
    """Run all tests"""
    logger.info("=== TransFlow Real-time Communication Test ===")
    logger.info("Make sure the server is running: python server.py")
    logger.info("")
    
    client = TransFlowTestClient()
    
    tests = [
        ("Basic Connection", client.test_basic_connection),
        ("Language Settings", client.test_language_settings),
        ("Audio Sources", client.test_audio_sources),
        ("Heartbeat", client.test_heartbeat),
        ("Error Handling", client.test_error_handling),
        ("Reconnection", client.test_reconnection),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            time.sleep(1)  # Pause between tests
        except Exception as e:
            logger.error(f"Test {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n=== Test Summary ===")
    passed = 0
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\nTotal: {passed}/{len(tests)} tests passed")
    
    return 0 if passed == len(tests) else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())