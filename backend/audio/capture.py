import objc
from Foundation import NSObject, NSRunLoop, NSDate
from AVFoundation import AVCaptureDevice, AVMediaTypeAudio
from ScreenCaptureKit import (
    SCShareableContent,
    SCContentFilter,
    SCStreamConfiguration,
    SCStream,
    SCStreamOutputTypeAudio
)
import threading
import queue
import wave
import struct
import numpy as np
import logging

logger = logging.getLogger(__name__)

class AudioCapture:
    """Audio capture manager using ScreenCaptureKit"""
    
    def __init__(self):
        self.pcm_queue = queue.Queue()
        self.is_recording = False
        self.stream = None
        self.delegate = None
        
    def list_applications(self):
        """List all running applications that can be captured"""
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
            return []
        
        apps = content.applications() if hasattr(content, 'applications') else []
        
        # Extract app information
        app_list = []
        for app in apps:
            app_info = {
                'name': app.applicationName(),
                'bundle_id': app.bundleIdentifier(),
                'process_id': app.processID()
            }
            app_list.append(app_info)
            
        return app_list
    
    def list_audio_devices(self):
        """List available microphone devices"""
        devices = AVCaptureDevice.devicesWithMediaType_(AVMediaTypeAudio)
        
        device_list = []
        for device in devices:
            device_info = {
                'name': device.localizedName(),
                'id': device.uniqueID(),
                'model_id': device.modelID(),
                'is_connected': device.isConnected(),
            }
            device_list.append(device_info)
        
        return device_list
    
    def start_recording(self, config):
        """Start audio recording with given configuration
        
        Args:
            config: {
                'capture_system_audio': bool,
                'capture_microphone': bool,
                'microphone_id': str (optional),
                'selected_apps': list of bundle_ids (optional),
                'exclude_current_process': bool
            }
        """
        if self.is_recording:
            raise RuntimeError("Already recording")
        
        # Get displays and apps
        displays, apps = self._get_shareable_content()
        if not displays:
            raise RuntimeError("No displays found")
        
        # Setup content filter
        display = displays[0]
        
        # Filter applications if specified
        if config.get('selected_apps'):
            # Find applications to include
            selected_app_objects = []
            for app in apps:
                if app.bundleIdentifier() in config['selected_apps']:
                    selected_app_objects.append(app)
            
            # Create filter with only selected apps
            filter = SCContentFilter.alloc().initWithDisplay_includingApplications_exceptingWindows_(
                display, selected_app_objects, []
            )
        else:
            # Capture all applications
            filter = SCContentFilter.alloc().initWithDisplay_excludingApplications_exceptingWindows_(
                display, [], []
            )
        
        # Configure stream
        stream_config = SCStreamConfiguration.alloc().init()
        stream_config.setCapturesAudio_(config.get('capture_system_audio', True))
        stream_config.setExcludesCurrentProcessAudio_(config.get('exclude_current_process', True))
        
        if config.get('capture_microphone'):
            stream_config.setCaptureMicrophone_(True)
            if config.get('microphone_id'):
                stream_config.setMicrophoneCaptureDeviceID_(config['microphone_id'])
        
        # Create delegate and stream
        self.delegate = CaptureDelegate.alloc().initWithQueue_(self.pcm_queue)
        self.stream = SCStream.alloc().initWithFilter_configuration_delegate_(
            filter, stream_config, self.delegate
        )
        
        # Add audio output
        success, err = self.stream.addStreamOutput_type_sampleHandlerQueue_error_(
            self.delegate, SCStreamOutputTypeAudio, None, None
        )
        if not success:
            raise RuntimeError(f"Failed to add stream output: {err}")
        
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
    
    def save_to_file(self, filename):
        """Save all queued audio to WAV file"""
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(2)  # Stereo
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(48000)  # 48kHz
            while not self.pcm_queue.empty():
                wf.writeframes(self.pcm_queue.get())
    
    def _get_shareable_content(self):
        """Get displays and applications"""
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
        apps = content.applications() if hasattr(content, 'applications') else []
        return displays, apps


class CaptureDelegate(NSObject):
    """SCStreamDelegate implementation for receiving audio samples"""
    
    def initWithQueue_(self, audio_queue):
        self = objc.super(CaptureDelegate, self).init()
        if self:
            self.audio_queue = audio_queue
        return self
    
    def stream_didOutputSampleBuffer_ofType_(self, stream, sampleBuffer, bufferType):
        """Handle audio buffer callback"""
        # Only process audio
        if bufferType != SCStreamOutputTypeAudio:
            return
        
        try:
            # Import Core Media functions
            from CoreMedia import (
                CMSampleBufferGetDataBuffer,
                CMBlockBufferGetDataLength,
                CMBlockBufferGetDataPointer
            )
            
            # Get audio data buffer
            dataBuffer = CMSampleBufferGetDataBuffer(sampleBuffer)
            if not dataBuffer:
                return
            
            # Get data length
            length = CMBlockBufferGetDataLength(dataBuffer)
            if length == 0:
                return
            
            # Get data pointer
            result = CMBlockBufferGetDataPointer(
                dataBuffer, 0, None, None, None
            )
            
            if isinstance(result, tuple) and len(result) >= 4:
                err = result[0]
                data_pointer_info = result[3]
                if isinstance(data_pointer_info, tuple) and len(data_pointer_info) > 0:
                    data_pointer = data_pointer_info[0]
                else:
                    data_pointer = None
            else:
                logger.error(f"Unexpected result from CMBlockBufferGetDataPointer: {result}")
                return
            
            if err == 0 and data_pointer and length > 0:
                # Create buffer from pointer address
                import ctypes
                buffer = (ctypes.c_char * length).from_address(data_pointer)
                raw_data = bytes(buffer)
                
                # Convert 32-bit float to 16-bit integer
                float_data = struct.unpack(f'{length//4}f', raw_data)
                
                # Convert to 16-bit integer
                int_data = np.array(float_data) * 32767
                int_data = np.clip(int_data, -32768, 32767).astype(np.int16)
                
                # Put in queue
                self.audio_queue.put(int_data.tobytes())
                
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            import traceback
            traceback.print_exc()