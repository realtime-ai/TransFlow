import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # OpenAI API Configuration
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
    OPENAI_MODEL_TRANSLATION = os.environ.get('OPENAI_MODEL_TRANSLATION', 'gpt-4o-mini')
    
    # Dashscope API Configuration (for Paraformer)
    DASHSCOPE_API_KEY = os.environ.get('DASHSCOPE_API_KEY', '')
    
    # Audio Configuration (optimized for OpenAI Realtime API)
    AUDIO_SAMPLE_RATE = 16000  # OpenAI Realtime requires 16kHz
    AUDIO_CHANNELS = 1  # OpenAI Realtime requires mono
    AUDIO_BIT_DEPTH = 16  # OpenAI Realtime requires 16-bit
    AUDIO_FORMAT = 'pcm16'  # Raw PCM 16-bit format
    
    # Translation Configuration
    DEFAULT_SOURCE_LANGUAGE = 'auto'  # auto-detect
    DEFAULT_TARGET_LANGUAGE = 'en'
    SUPPORTED_LANGUAGES = {
        'zh': '中文',
        'en': 'English',
        'ja': '日本語',
        'ko': '한국어',
        'auto': '自动检测'
    }
    
    # WebSocket Configuration
    SOCKETIO_ASYNC_MODE = 'threading'
    SOCKETIO_PING_TIMEOUT = 60
    SOCKETIO_PING_INTERVAL = 25
    
    # File paths
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
    TEMP_FOLDER = os.path.join(os.path.dirname(__file__), 'temp')
    
    @staticmethod
    def init_folders():
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.TEMP_FOLDER, exist_ok=True)

Config.init_folders()