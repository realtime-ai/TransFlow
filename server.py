#!/usr/bin/env python3
import os
import time
import logging
from functools import wraps
from flask import Flask, render_template, send_from_directory, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS

from config import Config
from backend.audio.capture import AudioCapture
from backend.asr.whisper_client import WhisperClient as ASRWhisperClient
from backend.asr.audio_buffer import SmartAudioBuffer
from backend.models.translation_service import TranslationService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, 
            static_folder='frontend/static',
            template_folder='frontend')
app.config.from_object(Config)

CORS(app)

socketio = SocketIO(app, 
                    cors_allowed_origins="*",
                    logger=True,
                    engineio_logger=True,
                    ping_timeout=Config.SOCKETIO_PING_TIMEOUT,
                    ping_interval=Config.SOCKETIO_PING_INTERVAL)

# Initialize audio capture
audio_capture = AudioCapture()

# Initialize ASR components
whisper_client = None
audio_buffer = None
translation_service = None

# ASR configuration
asr_config = {
    'source_language': None,  # Auto-detect
    'target_language': 'en'
}

# Connected clients tracking
connected_clients = set()

def handle_socketio_error(f):
    """Decorator for handling SocketIO errors"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {str(e)}", exc_info=True)
            emit('error', {
                'message': f'Server error: {str(e)}',
                'function': f.__name__,
                'timestamp': time.time()
            })
            return None
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('frontend/static', path)

@socketio.on('connect')
@handle_socketio_error
def handle_connect():
    logger.info(f"Client connected: {request.sid}")
    connected_clients.add(request.sid)
    emit('connection_status', {
        'status': 'connected',
        'client_id': request.sid,
        'timestamp': time.time()
    })

@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f"Client disconnected: {request.sid}")
    connected_clients.discard(request.sid)
    # Clean up any client-specific resources if needed

@socketio.on('ping')
@handle_socketio_error
def handle_ping():
    emit('pong', {'timestamp': time.time()})

@socketio.on('get_audio_sources')
@handle_socketio_error
def handle_get_audio_sources():
    """Get available audio sources (apps and devices)"""
    try:
        apps = audio_capture.list_applications()
        devices = audio_capture.list_audio_devices()
        emit('audio_sources', {
            'applications': apps,
            'devices': devices
        })
    except Exception as e:
        logger.error(f"Error getting audio sources: {e}")
        emit('error', {'message': str(e)})

@socketio.on('start_recording')
@handle_socketio_error
def handle_start_recording(data):
    logger.info(f"Starting recording with config: {data}")
    try:
        # Configure audio capture
        config = {
            'capture_system_audio': data.get('captureSystemAudio', True),
            'capture_microphone': data.get('captureMicrophone', False),
            'microphone_id': data.get('microphoneId'),
            'selected_apps': data.get('selectedApps', []),
            'exclude_current_process': True
        }
        
        audio_capture.start_recording(config)
        emit('recording_started', {'status': 'success'})
        
        # Start audio streaming in background
        socketio.start_background_task(stream_audio_data)
        
    except Exception as e:
        logger.error(f"Error starting recording: {e}")
        emit('error', {'message': str(e)})

@socketio.on('stop_recording')
@handle_socketio_error
def handle_stop_recording():
    logger.info("Stopping recording")
    try:
        audio_capture.stop_recording()
        emit('recording_stopped', {'status': 'success'})
    except Exception as e:
        logger.error(f"Error stopping recording: {e}")
        emit('error', {'message': str(e)})

@socketio.on('audio_data')
def handle_audio_data(data):
    # TODO: Process audio data
    pass

@socketio.on('error')
def handle_error(error):
    logger.error(f"SocketIO error: {error}")

@socketio.on('heartbeat')
@handle_socketio_error
def handle_heartbeat(data):
    """Handle client heartbeat for connection monitoring"""
    client_timestamp = data.get('timestamp', 0)
    server_timestamp = time.time()
    latency = server_timestamp - client_timestamp if client_timestamp else 0
    
    emit('heartbeat_response', {
        'client_timestamp': client_timestamp,
        'server_timestamp': server_timestamp,
        'latency': latency
    })

@socketio.on('set_languages')
@handle_socketio_error
def handle_set_languages(data):
    """Set source and target languages for ASR and translation"""
    global asr_config, translation_service
    try:
        asr_config['source_language'] = data.get('sourceLanguage')
        asr_config['target_language'] = data.get('targetLanguage', 'en')
        
        # Update whisper client if it exists
        if whisper_client:
            whisper_client.set_language(asr_config['source_language'])
        
        # Update translation service if it exists
        if translation_service:
            translation_service.set_languages(
                asr_config['source_language'] or 'auto',
                asr_config['target_language']
            )
        
        emit('languages_updated', {
            'sourceLanguage': asr_config['source_language'],
            'targetLanguage': asr_config['target_language']
        })
        logger.info(f"Languages updated: {asr_config}")
    except Exception as e:
        logger.error(f"Error setting languages: {e}")
        emit('error', {'message': str(e)})

def on_transcription_result(result):
    """Callback for ASR transcription results"""
    logger.info(f"Transcription: {result['text']}")
    socketio.emit('transcription', {
        'text': result['text'],
        'language': result['language'],
        'timestamp': result['timestamp']
    })
    
    # Feed transcription to translation service
    if translation_service and translation_service.is_running:
        translation_service.add_transcription(result)

def on_translation_result(result):
    """Callback for translation results"""
    logger.info(f"Translation: {result.get('translation', '')[:50]}...")
    socketio.emit('translation', {
        'source_text': result.get('source_text', ''),
        'translation': result.get('translation', ''),
        'source_language': result.get('source_language', ''),
        'target_language': result.get('target_language', ''),
        'timestamp': result.get('timestamp', time.time()),
        'error': result.get('error')
    })

def on_audio_chunk(audio_data, timestamp):
    """Callback for audio buffer chunks"""
    if whisper_client:
        whisper_client.add_audio_data(audio_data)

def stream_audio_data():
    """Stream audio data to client and ASR"""
    global whisper_client, audio_buffer, translation_service
    
    # Initialize Whisper client if API key is available
    if Config.OPENAI_API_KEY and not whisper_client:
        try:
            whisper_client = ASRWhisperClient(
                api_key=Config.OPENAI_API_KEY,
                model=Config.OPENAI_MODEL_WHISPER
            )
            whisper_client.set_callback(on_transcription_result)
            whisper_client.set_language(asr_config['source_language'])
            whisper_client.start()
            logger.info("Whisper client initialized and started")
            
            # Initialize audio buffer
            audio_buffer = SmartAudioBuffer(
                sample_rate=Config.AUDIO_SAMPLE_RATE,
                channels=Config.AUDIO_CHANNELS,
                chunk_duration=Config.AUDIO_CHUNK_DURATION,
                overlap_duration=0.5
            )
            audio_buffer.set_chunk_callback(on_audio_chunk)
            audio_buffer.start()
            logger.info("Audio buffer initialized and started")
            
            # Initialize translation service
            translation_service = TranslationService(api_key=Config.OPENAI_API_KEY)
            translation_service.set_languages(
                asr_config.get('source_language', 'auto'),
                asr_config.get('target_language', 'en')
            )
            translation_service.set_callback(on_translation_result)
            translation_service.start()
            logger.info("Translation service initialized and started")
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            socketio.emit('error', {'message': f'Service initialization failed: {str(e)}'})
    
    while audio_capture.is_recording:
        audio_data = audio_capture.get_audio_data(timeout=0.1)
        if audio_data:
            # Send to audio buffer for ASR processing
            if audio_buffer:
                audio_buffer.add_audio(audio_data)
            
            # Send audio data to client for visualization
            socketio.emit('audio_data', {
                'data': audio_data.hex(),  # Convert bytes to hex for transmission
                'timestamp': time.time()
            })
        socketio.sleep(0.01)  # Small delay to prevent overwhelming
    
    # Stop services when recording stops
    if audio_buffer:
        audio_buffer.stop()
    if whisper_client:
        whisper_client.stop()
    if translation_service:
        translation_service.stop()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting TransFlow server on port {port}")
    socketio.run(app, 
                 host='0.0.0.0', 
                 port=port, 
                 debug=Config.DEBUG)