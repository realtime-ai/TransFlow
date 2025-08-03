#!/usr/bin/env python3
import os
import time
import logging
import json
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
app.debug = Config.DEBUG

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


@app.route('/test')
def test():
    return 'Test'

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('frontend/static', path)

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors gracefully"""
    # For service worker requests, return a minimal response
    if 'serviceWorker' in request.path or request.path.endswith('sw.js'):
        logger.info(f"Service worker request ignored: {request.path}")
        return '', 404
    
    # For other 404s, you can customize the response
    logger.warning(f"404 Not Found: {request.path}")
    return {'error': 'Not found'}, 404

@socketio.on('connect')
def handle_connect():
    try:
        logger.info(f"Client connected: {request.sid}")
        connected_clients.add(request.sid)
        emit('connection_status', {
            'status': 'connected',
            'client_id': request.sid,
            'timestamp': time.time()
        })
    except Exception as e:
        logger.error(f"Error in handle_connect: {str(e)}", exc_info=True)

@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f"Client disconnected: {request.sid}")
    connected_clients.discard(request.sid)
    # Clean up any client-specific resources if needed

@socketio.on('ping')
@handle_socketio_error
def handle_ping(data=None):
    emit('pong', {'timestamp': time.time()})


@socketio.on('get_audio_devices')
@handle_socketio_error
def handle_get_audio_devices(data=None):
    """Get available audio input devices for settings page"""
    logger.info("Requesting audio devices")
    try:
        devices = audio_capture.list_audio_devices()
        logger.info(f"Available audio devices: {devices}")
        
        # Format devices for frontend
        formatted_devices = []
        
        # Always add default system device first
        formatted_devices.append({
            'id': 'default',
            'name': '系统默认麦克风',
            'type': 'builtin'
        })
        
        for device in devices:
            if isinstance(device, dict):
                device_name = device.get('name', 'Unknown Device')
                device_id = device.get('id')
                
                # Determine device type based on various fields
                device_type = 'builtin'
                if device.get('type') == 'system_capture':
                    device_type = 'builtin'
                elif device.get('source') == 'AVCapture':
                    device_type = 'builtin'
                elif 'bluetooth' in device_name.lower() or 'airpods' in device_name.lower():
                    device_type = 'bluetooth'
                elif 'usb' in device_name.lower() or device.get('transport') == 'USB':
                    device_type = 'usb'
                elif device.get('type') == 'microphone':
                    device_type = 'builtin'
                
                formatted_devices.append({
                    'id': device_id,
                    'name': device_name,
                    'type': device_type
                })
            else:
                # Device is likely a string, create structure
                device_str = str(device)
                formatted_devices.append({
                    'id': device_str,
                    'name': device_str,
                    'type': 'builtin'
                })

        print(json.dumps(formatted_devices, indent=4, ensure_ascii=False))
        emit('audio_devices', formatted_devices)
       
    except Exception as e:
        logger.error(f"Error getting audio devices: {e}")
        emit('audio_devices_error', {'error': str(e)})

@socketio.on('start_recording')
@handle_socketio_error
def handle_start_recording(data):
    logger.info(f"Starting recording with config: {data}")
    try:
        # 从前端接收的参数
        audio_device_id = data.get('audioDevice', 'default')
        capture_system_audio = data.get('captureSystemAudio', True)
        source_language = data.get('sourceLanguage', 'zh')
        target_language = data.get('targetLanguage', 'en')
        
        # 根据选择的音频设备决定捕获模式
        if audio_device_id == 'system_audio':
            # 只捕获系统音频
            capture_microphone = False
            microphone_id = None
        elif audio_device_id == 'default':
            # 使用默认麦克风
            capture_microphone = True
            microphone_id = None  # None 表示使用系统默认麦克风
        else:
            # 使用特定的麦克风设备
            capture_microphone = True
            microphone_id = audio_device_id
        
        # 配置音频捕获
        config = {
            'capture_system_audio': capture_system_audio,
            'capture_microphone': capture_microphone,
            'microphone_id': microphone_id,
            'selected_apps': [],  # 暂时捕获所有应用
            'exclude_current_process': True
        }
        
        # 存储语言设置用于 ASR/翻译
        global asr_config
        asr_config['source_language'] = source_language
        asr_config['target_language'] = target_language

        logger.info(f"Audio capture config: {json.dumps(config, indent=2)}")
        logger.info(f"Language settings - Source: {source_language}, Target: {target_language}")
        
        audio_capture.start_recording(config)
        emit('recording_started', {'status': 'success'})
        
        # 启动音频流处理任务
        socketio.start_background_task(stream_audio_data)
        
    except Exception as e:
        logger.error(f"Error starting recording: {e}")
        emit('error', {'message': str(e)})

@socketio.on('stop_recording')
@handle_socketio_error
def handle_stop_recording(data=None):
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
    port = int(os.environ.get('PORT', 5001))
    logger.info(f"Starting TransFlow server on port {port}")
    socketio.run(app, 
                 host='0.0.0.0', 
                 port=port, 
                 debug=Config.DEBUG)