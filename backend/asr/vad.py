import numpy as np
import logging
from typing import Optional, Tuple
from collections import deque

logger = logging.getLogger(__name__)


class VoiceActivityDetector:
    """Advanced Voice Activity Detection using energy and zero-crossing rate"""
    
    def __init__(self,
                 sample_rate: int = 48000,
                 frame_duration: float = 0.02,  # 20ms frames
                 energy_threshold: float = 0.01,
                 zcr_threshold: float = 0.1,
                 speech_frames: int = 10,
                 silence_frames: int = 30):
        """
        Initialize VAD
        
        Args:
            sample_rate: Audio sample rate
            frame_duration: Duration of each frame for analysis
            energy_threshold: Energy threshold for speech detection
            zcr_threshold: Zero-crossing rate threshold
            speech_frames: Number of frames to confirm speech start
            silence_frames: Number of frames to confirm speech end
        """
        self.sample_rate = sample_rate
        self.frame_size = int(sample_rate * frame_duration)
        self.energy_threshold = energy_threshold
        self.zcr_threshold = zcr_threshold
        self.speech_frames = speech_frames
        self.silence_frames = silence_frames
        
        # State tracking
        self.is_speech = False
        self.frame_buffer = deque(maxlen=max(speech_frames, silence_frames))
        self.energy_history = deque(maxlen=100)
        self.adaptive_threshold = energy_threshold
        
        logger.info(f"VAD initialized: frame_size={self.frame_size}, thresholds=(energy={energy_threshold}, zcr={zcr_threshold})")
    
    def process_frame(self, audio_frame: np.ndarray) -> Tuple[bool, float]:
        """
        Process an audio frame and detect voice activity
        
        Args:
            audio_frame: Audio frame as numpy array
            
        Returns:
            Tuple of (is_speech, confidence)
        """
        # Calculate frame features
        energy = self._calculate_energy(audio_frame)
        zcr = self._calculate_zcr(audio_frame)
        
        # Update adaptive threshold
        self.energy_history.append(energy)
        if len(self.energy_history) > 50:
            noise_floor = np.percentile(list(self.energy_history), 20)
            self.adaptive_threshold = max(self.energy_threshold, noise_floor * 2)
        
        # Determine if frame contains speech
        is_speech_frame = (energy > self.adaptive_threshold) and (zcr < self.zcr_threshold)
        
        # Add to frame buffer
        self.frame_buffer.append(is_speech_frame)
        
        # State machine for speech detection
        if not self.is_speech:
            # Check for speech start
            recent_frames = list(self.frame_buffer)[-self.speech_frames:]
            if len(recent_frames) == self.speech_frames:
                speech_ratio = sum(recent_frames) / len(recent_frames)
                if speech_ratio > 0.7:
                    self.is_speech = True
                    logger.debug(f"Speech started: energy={energy:.4f}, zcr={zcr:.4f}")
        else:
            # Check for speech end
            recent_frames = list(self.frame_buffer)[-self.silence_frames:]
            if len(recent_frames) == self.silence_frames:
                speech_ratio = sum(recent_frames) / len(recent_frames)
                if speech_ratio < 0.2:
                    self.is_speech = False
                    logger.debug(f"Speech ended: energy={energy:.4f}, zcr={zcr:.4f}")
        
        # Calculate confidence
        confidence = min(1.0, energy / self.adaptive_threshold) if is_speech_frame else 0.0
        
        return self.is_speech, confidence
    
    def _calculate_energy(self, frame: np.ndarray) -> float:
        """Calculate frame energy (RMS)"""
        return np.sqrt(np.mean(frame.astype(float) ** 2)) / 32768.0
    
    def _calculate_zcr(self, frame: np.ndarray) -> float:
        """Calculate zero-crossing rate"""
        signs = np.sign(frame)
        signs[signs == 0] = -1
        zcr = np.sum(signs[:-1] != signs[1:]) / (2 * len(frame))
        return zcr
    
    def reset(self):
        """Reset VAD state"""
        self.is_speech = False
        self.frame_buffer.clear()
        self.energy_history.clear()
        self.adaptive_threshold = self.energy_threshold


class WebRTCVAD:
    """Wrapper for WebRTC VAD (if available)"""
    
    def __init__(self, mode: int = 2):
        """
        Initialize WebRTC VAD
        
        Args:
            mode: Aggressiveness mode (0-3, 3 being most aggressive)
        """
        self.mode = mode
        self.vad = None
        
        try:
            import webrtcvad
            self.vad = webrtcvad.Vad(mode)
            self.available = True
            logger.info(f"WebRTC VAD initialized with mode {mode}")
        except ImportError:
            self.available = False
            logger.warning("WebRTC VAD not available, install with: pip install webrtcvad")
    
    def is_speech(self, audio_frame: bytes, sample_rate: int) -> bool:
        """
        Check if frame contains speech
        
        Args:
            audio_frame: Audio frame (10, 20, or 30ms of 16-bit PCM)
            sample_rate: Sample rate (8000, 16000, 32000, or 48000)
            
        Returns:
            True if speech detected
        """
        if not self.available or not self.vad:
            return True  # Default to speech if VAD not available
        
        try:
            return self.vad.is_speech(audio_frame, sample_rate)
        except Exception as e:
            logger.error(f"WebRTC VAD error: {e}")
            return True


class HybridVAD:
    """Hybrid VAD combining multiple detection methods"""
    
    def __init__(self, sample_rate: int = 48000, use_webrtc: bool = True):
        """
        Initialize hybrid VAD
        
        Args:
            sample_rate: Audio sample rate
            use_webrtc: Whether to use WebRTC VAD if available
        """
        self.sample_rate = sample_rate
        
        # Initialize detectors
        self.energy_vad = VoiceActivityDetector(sample_rate=sample_rate)
        self.webrtc_vad = WebRTCVAD() if use_webrtc else None
        
        # Frame size for WebRTC (30ms)
        self.webrtc_frame_size = int(sample_rate * 0.03) * 2  # 2 bytes per sample
        
    def process(self, audio_data: bytes) -> Tuple[bool, float]:
        """
        Process audio data and detect voice activity
        
        Args:
            audio_data: Raw audio bytes (16-bit PCM)
            
        Returns:
            Tuple of (is_speech, confidence)
        """
        # Convert to numpy array
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        # Energy-based VAD
        energy_speech, energy_confidence = self.energy_vad.process_frame(audio_array)
        
        # WebRTC VAD (if available and data is correct size)
        webrtc_speech = True
        if self.webrtc_vad and self.webrtc_vad.available:
            if len(audio_data) == self.webrtc_frame_size:
                webrtc_speech = self.webrtc_vad.is_speech(audio_data, self.sample_rate)
        
        # Combine results
        is_speech = energy_speech and webrtc_speech
        confidence = energy_confidence if webrtc_speech else energy_confidence * 0.5
        
        return is_speech, confidence
    
    def reset(self):
        """Reset VAD state"""
        self.energy_vad.reset()