import numpy as np
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class VoiceActivityDetector:
    """Simple Voice Activity Detection based on energy and zero-crossing rate"""
    
    def __init__(
        self,
        sample_rate: int = 48000,
        frame_duration_ms: int = 30,
        energy_threshold: float = 0.02,
        zcr_threshold: float = 0.1,
        speech_frames_threshold: int = 10,
        silence_frames_threshold: int = 30
    ):
        """Initialize VAD
        
        Args:
            sample_rate: Audio sample rate
            frame_duration_ms: Frame duration in milliseconds
            energy_threshold: Energy threshold for speech detection
            zcr_threshold: Zero-crossing rate threshold
            speech_frames_threshold: Consecutive frames to trigger speech start
            silence_frames_threshold: Consecutive frames to trigger speech end
        """
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        
        # Thresholds
        self.energy_threshold = energy_threshold
        self.zcr_threshold = zcr_threshold
        self.speech_frames_threshold = speech_frames_threshold
        self.silence_frames_threshold = silence_frames_threshold
        
        # State tracking
        self.is_speaking = False
        self.speech_frame_count = 0
        self.silence_frame_count = 0
        
        # Adaptive threshold
        self.energy_history = []
        self.adaptive_threshold = energy_threshold
        
    def process_frame(self, audio_frame: np.ndarray) -> Tuple[bool, bool]:
        """Process a single audio frame
        
        Args:
            audio_frame: Audio frame as numpy array
            
        Returns:
            Tuple of (is_speech, state_changed)
        """
        # Calculate features
        energy = self._calculate_energy(audio_frame)
        zcr = self._calculate_zcr(audio_frame)
        
        # Update adaptive threshold
        self._update_adaptive_threshold(energy)
        
        # Determine if frame contains speech
        is_speech_frame = (
            energy > self.adaptive_threshold and
            zcr < self.zcr_threshold
        )
        
        # Update state
        state_changed = False
        
        if is_speech_frame:
            self.speech_frame_count += 1
            self.silence_frame_count = 0
            
            if not self.is_speaking and self.speech_frame_count >= self.speech_frames_threshold:
                self.is_speaking = True
                state_changed = True
                logger.debug("Speech started")
                
        else:
            self.silence_frame_count += 1
            self.speech_frame_count = 0
            
            if self.is_speaking and self.silence_frame_count >= self.silence_frames_threshold:
                self.is_speaking = False
                state_changed = True
                logger.debug("Speech ended")
                
        return self.is_speaking, state_changed
        
    def process_audio(self, audio_data: bytes, channels: int = 2) -> Tuple[bool, bool]:
        """Process audio data and detect voice activity
        
        Args:
            audio_data: Raw PCM audio data (16-bit)
            channels: Number of audio channels
            
        Returns:
            Tuple of (is_speaking, state_changed)
        """
        # Convert to numpy array
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        # Convert to mono if stereo
        if channels == 2:
            audio_array = audio_array.reshape(-1, 2).mean(axis=1)
            
        # Normalize to [-1, 1]
        audio_array = audio_array.astype(np.float32) / 32768.0
        
        # Process frames
        is_speaking = False
        state_changed = False
        
        for i in range(0, len(audio_array) - self.frame_size, self.frame_size):
            frame = audio_array[i:i + self.frame_size]
            frame_speaking, frame_changed = self.process_frame(frame)
            
            if frame_changed:
                state_changed = True
                is_speaking = frame_speaking
                
        return self.is_speaking, state_changed
        
    def _calculate_energy(self, frame: np.ndarray) -> float:
        """Calculate frame energy (RMS)
        
        Args:
            frame: Audio frame
            
        Returns:
            Frame energy
        """
        return np.sqrt(np.mean(frame ** 2))
        
    def _calculate_zcr(self, frame: np.ndarray) -> float:
        """Calculate zero-crossing rate
        
        Args:
            frame: Audio frame
            
        Returns:
            Zero-crossing rate
        """
        # Count zero crossings
        signs = np.sign(frame)
        signs[signs == 0] = -1  # Treat zero as negative
        zcr = np.sum(signs[:-1] != signs[1:]) / (2 * len(frame))
        return zcr
        
    def _update_adaptive_threshold(self, energy: float):
        """Update adaptive energy threshold based on background noise
        
        Args:
            energy: Current frame energy
        """
        # Keep history of energy values
        self.energy_history.append(energy)
        
        # Limit history size
        max_history = int(1000 / self.frame_duration_ms)  # 1 second
        if len(self.energy_history) > max_history:
            self.energy_history.pop(0)
            
        # Calculate adaptive threshold as multiple of minimum energy
        if len(self.energy_history) >= 10:
            min_energy = np.percentile(self.energy_history, 20)
            self.adaptive_threshold = max(
                self.energy_threshold,
                min_energy * 3.0  # 3x minimum energy
            )
            
    def reset(self):
        """Reset VAD state"""
        self.is_speaking = False
        self.speech_frame_count = 0
        self.silence_frame_count = 0
        self.energy_history.clear()
        self.adaptive_threshold = self.energy_threshold