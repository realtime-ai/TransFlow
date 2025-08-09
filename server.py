#!/usr/bin/env python3
import os
import time
import logging
import json
import threading
from functools import wraps
from flask import Flask, render_template, send_from_directory, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS

from config import Config
from backend.audio.capture import AudioCapture
from backend.asr import create_asr
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
                    async_mode="threading",
                    engineio_logger=True,
                    ping_timeout=Config.SOCKETIO_PING_TIMEOUT,
                    ping_interval=Config.SOCKETIO_PING_INTERVAL)

# Initialize audio capture with 16kHz mono for OpenAI Realtime compatibility
audio_capture = AudioCapture()
audio_capture.init(sample_rate=16000, channels=1, bit_depth=16)

# Initialize ASR components
asr_client = None
translation_service = None

# ASR configuration
asr_config = {
    'source_language': None,  # Auto-detect
    'target_language': 'en'
}

# Connected clients tracking
connected_clients = set()

# Using Flask-SocketIO's start_background_task for thread-safe events
# No longer need manual queue management

def safe_emit(event_name, data, client_sid=None, namespace='/'):
    """Thread-safe emit function using start_background_task"""
    def emit_task():
        try:
            if client_sid and client_sid in connected_clients:
                # Emit to specific client
                socketio.emit(event_name, data, room=client_sid, namespace=namespace)
                logger.debug(f"✅ Event {event_name} sent to client {client_sid}")
            elif not client_sid:
                # Broadcast to all clients
                socketio.emit(event_name, data, namespace=namespace)
                logger.debug(f"✅ Event {event_name} broadcasted to all clients")
            else:
                logger.warning(f"⚠️ Client {client_sid} not connected, dropping event {event_name}")
        except Exception as e:
            logger.error(f"❌ Error emitting event {event_name}: {e}")
    
    # Use Flask-SocketIO's background task for thread-safe emission
    socketio.start_background_task(emit_task)
    logger.debug(f"🔄 Started background task for event {event_name}")

# Queue system removed - using socketio.start_background_task instead

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
    
    # If no clients connected, stop event worker
    if not connected_clients:
        logger.info("No connected clients, stopping event worker")
        ## stop_event_worker()
    
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
        
        audio_capture.start_recording(**config)
        emit('recording_started', {'status': 'success'})
        
        # 启动音频流处理任务，传递客户端 sid
        socketio.start_background_task(stream_audio_data, request.sid)
        
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

@socketio.on('test_rapid_event')
@handle_socketio_error
def handle_test_rapid_event(data):
    """Test handler for rapid events to test thread safety"""
    count = data.get('count', 0)
    timestamp = data.get('timestamp', time.time())
    
    # Simulate background thread emission
    def emit_response():
        time.sleep(0.05)  # Small delay to simulate processing
        safe_emit('test_event', {
            'original_count': count,
            'processed_timestamp': time.time(),
            'original_timestamp': timestamp
        }, request.sid)
    
    # Start background thread
    threading.Thread(target=emit_response, daemon=True).start()
    logger.info(f"🧪 Processed test event {count} for client {request.sid}")

@socketio.on('set_languages')
@handle_socketio_error
def handle_set_languages(data):
    """Set source and target languages for ASR and translation"""
    global asr_config, translation_service
    try:
        asr_config['source_language'] = data.get('sourceLanguage')
        asr_config['target_language'] = data.get('targetLanguage', 'en')
        
        # Update ASR client if it exists
        if asr_client:
            asr_client.set_language(asr_config['source_language'])
        
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

def create_transcription_callback(client_sid):
    """Create a transcription callback with client sid"""
    def on_transcription_result(result):
        """Callback for ASR transcription results"""
        logger.error(f"📝 Transcription callback for client {client_sid}: {result.text}")
        
        try:
            transcription_data = {
                'text': result.text,
                'language': result.language,
                'timestamp': result.timestamp
            }
            logger.error(f"📝 Emitting transcription event to {client_sid}: {transcription_data}")
            
            # Use thread-safe emit with client sid
            safe_emit('transcription', transcription_data, client_sid)
            logger.info(f"📝 Transcription event emitted successfully to {client_sid}")
        except Exception as e:
            logger.error(f"❌ Error emitting transcription to {client_sid}: {e}")
            import traceback
            traceback.print_exc()
        
        # Feed transcription to translation service
        if translation_service and translation_service.is_running:
            try:
                # Convert ASRResult to dictionary format for translation service
                transcription_dict = {
                    'text': result.text,
                    'language': result.language,
                    'timestamp': result.timestamp,
                    'is_final': getattr(result, 'is_final', True),
                    'metadata': getattr(result, 'metadata', {})
                }
                translation_service.add_transcription(transcription_dict)
                logger.info("📝 Fed transcription to translation service")
            except Exception as e:
                logger.error(f"❌ Error feeding transcription to translation service: {e}")
    
    return on_transcription_result

def create_translation_callback(client_sid):
    """Create a translation callback with client sid"""
    def on_translation_result(result):
        """Callback for translation results"""
        logger.info(f"🌍 Translation callback for client {client_sid}: {result.get('translation', '')[:50]}...")
        
        try:
            translation_data = {
                'source_text': result.get('source_text', ''),
                'translation': result.get('translation', ''),
                'source_language': result.get('source_language', ''),
                'target_language': result.get('target_language', ''),
                'timestamp': result.get('timestamp', time.time()),
                'error': result.get('error')
            }
            logger.info(f"🌍 Emitting translation event to {client_sid}: {translation_data}")
            
            # Use thread-safe emit with client sid
            safe_emit('translation', translation_data, client_sid)
            logger.info(f"🌍 Translation event emitted successfully to {client_sid}")
            
        except Exception as e:
            logger.error(f"❌ Error emitting translation to {client_sid}: {e}")
            import traceback
            traceback.print_exc()
    
    return on_translation_result

# on_audio_chunk function not needed with direct streaming

def stream_audio_data(client_sid):
    """Stream audio data to client and ASR"""
    global asr_client, translation_service
    
    logger.info(f"🎙️ Starting audio stream for client {client_sid}")
    
    # Priority 1: Use Paraformer for Chinese if available
    if Config.DASHSCOPE_API_KEY and not asr_client:
        # Check if source language is Chinese or auto
        source_lang = asr_config.get('source_language', 'zh')
        if source_lang in ['zh', 'auto', None]:
            try:
                # Use Paraformer for Chinese real-time transcription
                asr_client = create_asr(
                    'paraformer_realtime', 
                    api_key=Config.DASHSCOPE_API_KEY,
                    model='paraformer-realtime-v2',
                    debug_dump_audio=True,
                    enable_punctuation=True,
                    enable_itn=True,
                    language='zh'
                )
                # Set callback with client sid
                transcription_callback = create_transcription_callback(client_sid)
                asr_client.set_callback(transcription_callback)
                asr_client.set_language(source_lang)
                asr_client.start()
                logger.info("Paraformer Realtime ASR client initialized and started")
                
                # Start streaming with 16kHz mono audio
                asr_client.start_stream(
                    sample_rate=16000,
                    channels=1,
                    sample_width=2
                )
                logger.info("Paraformer Realtime ASR stream started")
                logger.info("Using Paraformer for Chinese real-time transcription")
                
                # Initialize translation service (auto-select provider)
                translation_service = TranslationService(provider="auto")
                translation_service.set_languages(
                    asr_config.get('source_language', 'zh'),
                    asr_config.get('target_language', 'en')
                )
                # Set callback with client sid
                translation_callback = create_translation_callback(client_sid)
                translation_service.set_callback(translation_callback)
                translation_service.start()
                logger.info("Translation service initialized and started")
                    
            except Exception as e:
                logger.error(f"Failed to initialize Paraformer ASR: {e}")
                # Don't exit, fall back to OpenAI Realtime
                asr_client = None
    
    # Priority 2: Fallback to OpenAI Realtime if Paraformer not available or failed
    if Config.OPENAI_API_KEY and not asr_client:
        try:
            # Use OpenAI Realtime for multilingual transcription
            asr_client = create_asr('openai_realtime', api_key=Config.OPENAI_API_KEY, debug_dump_audio=True)
            # Set callback with client sid
            transcription_callback = create_transcription_callback(client_sid)
            asr_client.set_callback(transcription_callback)
            asr_client.set_language(asr_config['source_language'])
            asr_client.start()
            logger.info("OpenAI Realtime ASR client initialized and started (fallback)")
            
            # Start streaming with 16kHz mono audio
            asr_client.start_stream(
                sample_rate=16000,
                channels=1,
                sample_width=2
            )
            logger.info("OpenAI Realtime ASR stream started")
            logger.info("Using OpenAI Realtime API for transcription")
            
            # Initialize translation service (auto-select provider)
            translation_service = TranslationService(provider="auto")
            translation_service.set_languages(
                asr_config.get('source_language', 'auto'),
                asr_config.get('target_language', 'en')
            )
            # Set callback with client sid
            translation_callback = create_translation_callback(client_sid)
            translation_service.set_callback(translation_callback)
            translation_service.start()
            logger.info("Translation service initialized and started")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI Realtime ASR: {e}")
            # Use thread-safe emit for error
            safe_emit('error', {'message': f'ASR initialization failed: {str(e)}'}, client_sid)
            # Exit early if both ASR services fail
            return
    
    # If no ASR service available, exit
    if not asr_client:
        error_msg = "No ASR service available. Please configure DASHSCOPE_API_KEY or OPENAI_API_KEY."
        logger.error(error_msg)
        # Use thread-safe emit for error
        safe_emit('error', {'message': error_msg}, client_sid)
        return
    
    # Stream audio data
    while audio_capture.is_recording:
        audio_data = audio_capture.get_mic_audio_data(timeout=0.1)
        if audio_data and asr_client:
            # Send directly to OpenAI Realtime ASR
            asr_client.add_audio_data(audio_data)

            # Send audio data to client for visualization
            # socketio.emit('audio_data', {
            #     'data': audio_data.hex(),  # Convert bytes to hex for transmission
            #     'timestamp': time.time()
            # })
        socketio.sleep(0.01)  # Small delay to prevent overwhelming
    
    # Stop services when recording stops
    if asr_client:
        asr_client.end_stream()
        asr_client.stop()
    if translation_service:
        translation_service.stop()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    logger.info(f"Starting TransFlow server on port {port}")
    socketio.run(app, 
                 host='0.0.0.0', 
                 port=port, 
                 debug=Config.DEBUG)