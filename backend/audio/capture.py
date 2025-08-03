import objc
from Foundation import NSObject, NSRunLoop, NSDate
from AVFoundation import AVCaptureDevice, AVMediaTypeAudio
from ScreenCaptureKit import (
    SCShareableContent,
    SCContentFilter,
    SCStreamConfiguration,
    SCStream,
    SCStreamOutputTypeAudio,
    SCStreamOutputTypeMicrophone
)
import threading
import queue
import wave
import logging

logger = logging.getLogger(__name__)

class AudioCapture(NSObject):
    """Audio capture manager using ScreenCaptureKit"""
    
    def __init__(self, sample_rate=48000, channels=1, bit_depth=16):

        self = objc.super(AudioCapture, self).init()
        
        self.pcm_queue = queue.Queue()
        self.mic_queue = queue.Queue()  # Separate queue for microphone audio
        self.is_recording = False
        self.stream = None
        self.delegate = None
        
        # Audio format configuration
        self.sample_rate = sample_rate
        self.channels = channels
        self.bit_depth = bit_depth

        self.system_audio_format = None
        self.microphone_audio_format = None
    
    def list_audio_devices(self, include_system_audio=True, include_microphones=True):
        """List available audio devices and system audio capture capability"""
        device_list = []
        
        # Add system audio capture capability as a special device
        if include_system_audio:
            system_audio_device = {
                'name': 'System Audio',
                'id': 'system_audio',
                'type': 'system_capture',
                'source': 'ScreenCaptureKit',
                'description': 'Capture all system audio output',
                'capabilities': ['system_audio_capture']
            }
            device_list.append(system_audio_device)
        
        # Get microphone devices using AVCaptureDevice (same as main.py)
        if include_microphones:
            try:
                devices = AVCaptureDevice.devicesWithMediaType_(AVMediaTypeAudio)
                for device in devices:
                    mic_info = {
                        'name': device.localizedName(),
                        'id': device.uniqueID(),
                        'unique_id': device.uniqueID(),  # For compatibility
                        'model_id': device.modelID(),
                        'is_connected': device.isConnected(),
                        'type': 'microphone',
                        'source': 'AVCapture',
                        'capabilities': ['microphone_input']
                    }
                    device_list.append(mic_info)
            except Exception as e:
                logger.error(f"Error getting microphone devices: {e}")
        
        return device_list
    
    def list_microphones(self):
        """List available microphone devices (same as main.py implementation)"""
        # Get all audio input devices
        devices = AVCaptureDevice.devicesWithMediaType_(AVMediaTypeAudio)
        
        microphones = []
        for device in devices:
            mic_info = {
                'name': device.localizedName(),
                'unique_id': device.uniqueID(),
                'model_id': device.modelID(),
                'is_connected': device.isConnected(),
            }
            microphones.append(mic_info)
        
        return microphones
    
    def start_recording(self, capture_system_audio=True, capture_microphone=False, 
                       microphone_id=None, exclude_current_process=True):
        """Start audio recording with given configuration
        
        Args:
            capture_system_audio: bool - Whether to capture system audio
            capture_microphone: bool - Whether to capture microphone
            microphone_id: str (optional) - Specific microphone device ID
            exclude_current_process: bool - Whether to exclude current process audio
        """
        if self.is_recording:
            raise RuntimeError("Already recording")
        
        # Get displays only (no app filtering needed)
        displays, _ = self._get_shareable_content()
        if not displays:
            raise RuntimeError("No displays found")
        
        # Setup content filter - capture all applications
        display = displays[0]
        filter = SCContentFilter.alloc().initWithDisplay_excludingApplications_exceptingWindows_(
            display, [], []
        )
        
        # Configure stream
        stream_config = SCStreamConfiguration.alloc().init()
        stream_config.setCapturesAudio_(capture_system_audio)
        stream_config.setExcludesCurrentProcessAudio_(exclude_current_process)
        stream_config.setChannelCount_(self.channels)
        
        # Enable microphone capture if requested
        if capture_microphone:
            stream_config.setCaptureMicrophone_(True)
            if microphone_id:
                stream_config.setMicrophoneCaptureDeviceID_(microphone_id)
        else:
            stream_config.setCaptureMicrophone_(False)
        
        # Create single delegate (like main.py) - handles both system and mic audio
        self.delegate = self

        # Create stream
        self.stream = SCStream.alloc().initWithFilter_configuration_delegate_(
            filter, stream_config, self.delegate
        )
        
        # Add system audio output
        if capture_system_audio:
            success, err = self.stream.addStreamOutput_type_sampleHandlerQueue_error_(
                self.delegate, SCStreamOutputTypeAudio, None, None
            )
            if not success:
                raise RuntimeError(f"Failed to add audio stream output: {err}")
        
        # Add microphone output (using same delegate)
        if capture_microphone:
            success, err = self.stream.addStreamOutput_type_sampleHandlerQueue_error_(
                self.delegate, SCStreamOutputTypeMicrophone, None, None
            )
            if not success:
                logger.warning(f"Failed to add microphone stream output: {err}")
        
        # Start capture
        capture_started = [False]
        capture_error = [None]
        semaphore = threading.Semaphore(0)
        
        def start_handler(error):
            if error:
                capture_error[0] = error
            else:
                capture_started[0] = True
            semaphore.release()
        
        self.stream.startCaptureWithCompletionHandler_(start_handler)
        semaphore.acquire()
        
        if capture_error[0]:
            raise RuntimeError(f"Failed to start capture: {capture_error[0]}")
        
        self.is_recording = True
        logger.info("Audio recording started")
        
    def stop_recording(self):
        """Stop audio recording"""
        if not self.is_recording:
            return
        
        stop_semaphore = threading.Semaphore(0)
        
        def stop_handler(error):
            if error:
                logger.error(f"Error stopping capture: {error}")
            stop_semaphore.release()
        
        self.stream.stopCaptureWithCompletionHandler_(stop_handler)
        stop_semaphore.acquire()
        
        self.is_recording = False
        self.stream = None
        self.delegate = None
        logger.info("Audio recording stopped")
    
    def get_audio_data(self, timeout=0.1):
        """Get audio data from queue
        
        Returns:
            bytes: Audio data or None if queue is empty
        """
        try:
            return self.pcm_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_mic_data(self, timeout=0.1):
        """Get microphone audio data from separate queue
        
        Returns:
            bytes: Microphone audio data or None if queue is empty
        """
        try:
            return self.mic_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def save_to_file(self, filename):
        """Save all queued audio to WAV file"""
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.bit_depth // 8)  # Convert bits to bytes
            wf.setframerate(self.sample_rate)
            while not self.pcm_queue.empty():
                wf.writeframes(self.pcm_queue.get())

    # delegate method
    def stream_didOutputSampleBuffer_ofType_(self, stream, sampleBuffer, bufferType):
        """Handle audio buffer callback (simplified like main.py)"""
        # Process only audio and microphone types
        if bufferType not in (SCStreamOutputTypeAudio, SCStreamOutputTypeMicrophone):
            return
        
        try:
            # Import Core Media functions
            from CoreMedia import (
                CMSampleBufferGetDataBuffer,
                CMBlockBufferGetDataLength,
                CMBlockBufferCopyDataBytes
            )
            from Foundation import NSMutableData

            # 获取真实的 音频参数
            if bufferType == SCStreamOutputTypeAudio and self.system_audio_format is None:
                self._analyze_audio_format(sampleBuffer, bufferType)

            if bufferType == SCStreamOutputTypeMicrophone and self.mic_audio_format is None:
                self._analyze_audio_format(sampleBuffer, bufferType)
            
            # Get audio data buffer
            dataBuffer = CMSampleBufferGetDataBuffer(sampleBuffer)
            if not dataBuffer:
                return
            
            # Get data length
            length = CMBlockBufferGetDataLength(dataBuffer)
            if length == 0:
                return
            
            # Use safer data copy method (like main.py)
            destinationBuffer = NSMutableData.dataWithLength_(length)
            if not destinationBuffer:
                return
            
            # Copy data
            result = CMBlockBufferCopyDataBytes(dataBuffer, 0, length, destinationBuffer.mutableBytes())
            
            # Handle return value
            error_code = 0
            if isinstance(result, tuple):
                error_code = result[0] if len(result) > 0 else 0
            else:
                error_code = result
            
            if error_code == 0:  # Success
                # Get raw data
                raw_data = destinationBuffer.bytes().tobytes()
                
                # Put data in appropriate queue based on buffer type
                if bufferType == SCStreamOutputTypeMicrophone:
                    self.mic_queue.put(raw_data)
                elif bufferType == SCStreamOutputTypeAudio:
                    self.pcm_queue.put(raw_data)
                
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            import traceback
            traceback.print_exc()


    def _analyze_audio_format(self, sampleBuffer, bufferType):
        """分析音频格式信息"""
        try:
            from CoreMedia import (
                CMSampleBufferGetFormatDescription,
                CMAudioFormatDescriptionGetStreamBasicDescription
            )
            
            # 确定流类型
            stream_type = "麦克风" if bufferType == SCStreamOutputTypeMicrophone else "系统音频"
            format_key = "microphone" if bufferType == SCStreamOutputTypeMicrophone else "system"
            
            # 初始化计数器
            if not hasattr(self, 'format_analyzed'):
                self.format_analyzed = {}
            
            # 每种类型只分析一次
            if stream_type not in self.format_analyzed:
                self.format_analyzed[stream_type] = True
                
                print(f"\n[音频格式分析] {stream_type}")
                
                # 获取格式描述
                formatDesc = CMSampleBufferGetFormatDescription(sampleBuffer)
                if formatDesc:
                    try:
                        # 使用Core Media API获取AudioStreamBasicDescription
                        asbd = CMAudioFormatDescriptionGetStreamBasicDescription(formatDesc)
                        if asbd:
                            # 直接访问AudioStreamBasicDescription结构体的字段
                            sample_rate = int(asbd.mSampleRate) if hasattr(asbd, 'mSampleRate') else 44100
                            channels = int(asbd.mChannelsPerFrame) if hasattr(asbd, 'mChannelsPerFrame') else 1
                            bit_depth = int(asbd.mBitsPerChannel) if hasattr(asbd, 'mBitsPerChannel') else 16

                            # 保存系统音频格式
                            if format_key == 'system':
                                self.system_audio_format = {
                                    'sample_rate': sample_rate,
                                    'channels': channels,
                                    'bit_depth': bit_depth
                                }

                            # 保存麦克风音频格式
                            if format_key == 'microphone':
                                self.microphone_audio_format = {
                                    'sample_rate': sample_rate,
                                    'channels': channels,
                                    'bit_depth': bit_depth
                                }
                            
                            print(f"[格式] {stream_type}: {sample_rate}Hz, {channels}声道, {bit_depth}位")

                            
                    except Exception as parse_error:
                        print(f"格式解析失败: {parse_error}")
                
        except Exception as e:
            print(f"格式分析错误: {e}")

    
    def _get_shareable_content(self):
        """Get displays for capture"""
        content_ref = [None]
        semaphore = threading.Semaphore(0)
        
        def completion_handler(content, error):
            if error:
                logger.error(f"Error getting shareable content: {error}")
            content_ref[0] = content
            semaphore.release()
        
        SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(
            False, True, completion_handler
        )
        
        semaphore.acquire()
        content = content_ref[0]
        
        if content is None:
            return [], []
        
        displays = content.displays() if hasattr(content, 'displays') else []
        return displays, []


class CaptureDelegate(NSObject):
    """SCStreamDelegate implementation for receiving audio samples (simplified like main.py)"""
    
    def initWithPcmQueue_micQueue_(self, pcm_queue, mic_queue):
        self = objc.super(CaptureDelegate, self).init()
        if self:
            self.pcm_queue = pcm_queue
            self.mic_queue = mic_queue
        return self
    
    def stream_didOutputSampleBuffer_ofType_(self, stream, sampleBuffer, bufferType):
        """Handle audio buffer callback (simplified like main.py)"""
        # Process only audio and microphone types
        if bufferType not in (SCStreamOutputTypeAudio, SCStreamOutputTypeMicrophone):
            return
        
        try:
            # Import Core Media functions
            from CoreMedia import (
                CMSampleBufferGetDataBuffer,
                CMBlockBufferGetDataLength,
                CMBlockBufferCopyDataBytes
            )
            from Foundation import NSMutableData
            
            # Get audio data buffer
            dataBuffer = CMSampleBufferGetDataBuffer(sampleBuffer)
            if not dataBuffer:
                return
            
            # Get data length
            length = CMBlockBufferGetDataLength(dataBuffer)
            if length == 0:
                return
            
            # Use safer data copy method (like main.py)
            destinationBuffer = NSMutableData.dataWithLength_(length)
            if not destinationBuffer:
                return
            
            # Copy data
            result = CMBlockBufferCopyDataBytes(dataBuffer, 0, length, destinationBuffer.mutableBytes())
            
            # Handle return value
            error_code = 0
            if isinstance(result, tuple):
                error_code = result[0] if len(result) > 0 else 0
            else:
                error_code = result
            
            if error_code == 0:  # Success
                # Get raw data
                raw_data = destinationBuffer.bytes().tobytes()
                
                # Put data in appropriate queue based on buffer type
                if bufferType == SCStreamOutputTypeMicrophone:
                    self.mic_queue.put(raw_data)
                elif bufferType == SCStreamOutputTypeAudio:
                    self.pcm_queue.put(raw_data)
                
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            import traceback
            traceback.print_exc()
