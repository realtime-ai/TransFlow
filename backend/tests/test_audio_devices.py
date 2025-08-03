#!/usr/bin/env python3
"""
Test suite for audio device detection functionality
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock, mock_open
import json
import logging

# Add parent directory to path to import audio modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audio.capture import AudioCapture

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")



class TestAudioDevices(unittest.TestCase):
    """Test cases for audio device detection"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.capture = AudioCapture()
    
    def test_audio_capture_configuration(self):
        """Test AudioCapture configuration options"""
        # Test default configuration
        default_capture = AudioCapture()
        self.assertEqual(default_capture.sample_rate, 48000)
        self.assertEqual(default_capture.channels, 2)
        self.assertEqual(default_capture.bit_depth, 16)
        
        # Test 16kHz mono configuration
        mono_capture = AudioCapture(sample_rate=16000, channels=1, bit_depth=16)
        self.assertEqual(mono_capture.sample_rate, 16000)
        self.assertEqual(mono_capture.channels, 1)
        self.assertEqual(mono_capture.bit_depth, 16)
        
        # Test custom configuration
        custom_capture = AudioCapture(sample_rate=22050, channels=2, bit_depth=16)
        self.assertEqual(custom_capture.sample_rate, 22050)
        self.assertEqual(custom_capture.channels, 2)
        self.assertEqual(custom_capture.bit_depth, 16)
    
    def test_list_audio_devices_basic(self):
        """Test that list_audio_devices returns a list"""
        devices = self.capture.list_audio_devices()
        print(f"Available audio devices: {devices}")
        self.assertIsInstance(devices, list)
    
    def test_list_audio_devices_structure(self):
        """Test that each device has required fields"""
        devices = self.capture.list_audio_devices()
        
        required_fields = ['name', 'id', 'type', 'source']
        
        for device in devices:
            self.assertIsInstance(device, dict)
            for field in required_fields:
                self.assertIn(field, device, f"Device missing required field: {field}")
                self.assertIsNotNone(device[field], f"Device field {field} is None")
    
    def test_device_types(self):
        """Test that devices have valid types"""
        devices = self.capture.list_audio_devices()
        valid_types = ['input', 'input/output', 'microphone', 'system_capture']
        
        for device in devices:
            device_type = device.get('type')
            self.assertIn(device_type, valid_types, 
                         f"Invalid device type: {device_type} for device: {device.get('name')}")
    
    def test_device_sources(self):
        """Test that devices have valid sources"""
        devices = self.capture.list_audio_devices()
        valid_sources = ['SystemProfiler', 'AVCapture', 'SwitchAudioSource', 'CoreAudio', 'ScreenCaptureKit']
        
        for device in devices:
            source = device.get('source')
            self.assertIn(source, valid_sources, 
                         f"Invalid device source: {source} for device: {device.get('name')}")
    
    def test_system_profiler_devices_structure(self):
        """Test SystemProfiler devices have expected fields"""
        devices = self.capture.list_audio_devices()
        system_profiler_devices = [d for d in devices if d.get('source') == 'SystemProfiler']
        
        for device in system_profiler_devices:
            # SystemProfiler devices should have additional fields
            expected_fields = ['manufacturer', 'has_input', 'has_output', 'sample_rate', 'transport']
            for field in expected_fields:
                self.assertIn(field, device, 
                             f"SystemProfiler device missing field: {field}")
    
    def test_avcapture_devices_structure(self):
        """Test AVCapture devices have expected fields"""
        devices = self.capture.list_audio_devices()
        avcapture_devices = [d for d in devices if d.get('source') == 'AVCapture']
        
        for device in avcapture_devices:
            # AVCapture devices should have specific fields
            expected_fields = ['model_id', 'is_connected']
            for field in expected_fields:
                self.assertIn(field, device, 
                             f"AVCapture device missing field: {field}")
            
            # Type should be 'microphone' for AVCapture devices
            self.assertEqual(device.get('type'), 'microphone')
    
    def test_device_names_not_empty(self):
        """Test that device names are not empty"""
        devices = self.capture.list_audio_devices()
        
        for device in devices:
            name = device.get('name')
            self.assertTrue(name and name.strip(), 
                           f"Device has empty or whitespace name: {device}")
    
    def test_device_ids_not_empty(self):
        """Test that device IDs are not empty"""
        devices = self.capture.list_audio_devices()
        
        for device in devices:
            device_id = device.get('id')
            self.assertTrue(device_id and device_id.strip(), 
                           f"Device has empty or whitespace ID: {device}")
    
    def test_no_duplicate_devices(self):
        """Test that there are no duplicate devices (same name and source)"""
        devices = self.capture.list_audio_devices()
        
        seen = set()
        for device in devices:
            key = (device.get('name'), device.get('source'))
            self.assertNotIn(key, seen, 
                           f"Duplicate device found: {device.get('name')} from {device.get('source')}")
            seen.add(key)
    
    def test_only_input_and_system_devices(self):
        """Test that only input devices and system audio capture are returned"""
        devices = self.capture.list_audio_devices()
        
        for device in devices:
            device_type = device.get('type')
            # Should only have input devices, input/output devices, microphones, and system capture
            valid_types = ['input', 'input/output', 'microphone', 'system_capture']
            self.assertIn(device_type, valid_types,
                         f"Device type '{device_type}' should not be returned for device: {device.get('name')}")
            
            # Should not have pure output devices
            self.assertNotEqual(device_type, 'output',
                               f"Pure output device should be filtered out: {device.get('name')}")
    
    def test_system_audio_device_present(self):
        """Test that system audio capture device is present"""
        devices = self.capture.list_audio_devices()
        
        system_audio_devices = [d for d in devices if d.get('type') == 'system_capture']
        self.assertGreater(len(system_audio_devices), 0, "System audio capture device should be present")
        
        # Check the system audio device properties
        system_device = system_audio_devices[0]
        self.assertEqual(system_device.get('name'), 'System Audio')
        self.assertEqual(system_device.get('id'), 'system_audio')
        self.assertEqual(system_device.get('source'), 'ScreenCaptureKit')
        self.assertIn('system_audio_capture', system_device.get('capabilities', []))


class TestSystemProfilerDevices(unittest.TestCase):
    """Test cases for system_profiler device detection"""
    
    def setUp(self):
        self.capture = AudioCapture()
    
    @patch('subprocess.run')
    def test_system_profiler_success(self, mock_run):
        """Test successful system_profiler parsing"""
        mock_data = {
            'SPAudioDataType': [{
                '_name': 'coreaudio_device',
                '_items': [
                    {
                        '_name': 'Test Speakers',
                        'coreaudio_device_manufacturer': 'Test Corp',
                        'coreaudio_device_output': 2,
                        'coreaudio_device_srate': 48000,
                        'coreaudio_device_transport': 'coreaudio_device_type_builtin'
                    },
                    {
                        '_name': 'Test Microphone',
                        'coreaudio_device_manufacturer': 'Test Corp',
                        'coreaudio_device_input': 1,
                        'coreaudio_device_srate': 48000,
                        'coreaudio_device_transport': 'coreaudio_device_type_builtin',
                        'coreaudio_default_audio_input_device': 'spaudio_yes'
                    }
                ]
            }]
        }
        
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = json.dumps(mock_data)
        
        devices = self.capture._get_system_profiler_devices()
        
        self.assertEqual(len(devices), 2)
        
        # Check speaker device
        speaker = next((d for d in devices if d['name'] == 'Test Speakers'), None)
        self.assertIsNotNone(speaker)
        self.assertEqual(speaker['type'], 'output')
        self.assertTrue(speaker['has_output'])
        self.assertFalse(speaker['has_input'])
        self.assertEqual(speaker['output_channels'], 2)
        
        # Check microphone device
        mic = next((d for d in devices if d['name'] == 'Test Microphone'), None)
        self.assertIsNotNone(mic)
        self.assertEqual(mic['type'], 'input')
        self.assertTrue(mic['has_input'])
        self.assertFalse(mic['has_output'])
        self.assertEqual(mic['input_channels'], 1)
        self.assertIn('default_input', mic['flags'])
    
    @patch('subprocess.run')
    def test_system_profiler_error(self, mock_run):
        """Test system_profiler error handling"""
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        
        devices = self.capture._get_system_profiler_devices()
        self.assertEqual(devices, [])
    
    @patch('subprocess.run')
    def test_system_profiler_timeout(self, mock_run):
        """Test system_profiler timeout handling"""
        mock_run.side_effect = Exception("Timeout")
        
        devices = self.capture._get_system_profiler_devices()
        self.assertEqual(devices, [])


class TestSwitchAudioSourceDevices(unittest.TestCase):
    """Test cases for SwitchAudioSource device detection"""
    
    def setUp(self):
        self.capture = AudioCapture()
    
    @patch('subprocess.run')
    def test_switchaudiosource_available(self, mock_run):
        """Test SwitchAudioSource when available"""
        # Mock 'which' command returning success (SwitchAudioSource is installed)
        mock_run.side_effect = [
            MagicMock(returncode=0),  # which command succeeds
            MagicMock(returncode=0, stdout="Built-in Microphone\nExternal Microphone\n"),  # input devices
            MagicMock(returncode=0, stdout="Built-in Speakers\nHeadphones\n")  # output devices
        ]
        
        devices = self.capture._get_switchaudiosource_devices()
        
        self.assertEqual(len(devices), 4)
        
        # Check input devices
        input_devices = [d for d in devices if d['type'] == 'input']
        self.assertEqual(len(input_devices), 2)
        self.assertIn('Built-in Microphone', [d['name'] for d in input_devices])
        
        # Check output devices  
        output_devices = [d for d in devices if d['type'] == 'output']
        self.assertEqual(len(output_devices), 2)
        self.assertIn('Built-in Speakers', [d['name'] for d in output_devices])
    
    @patch('subprocess.run')
    def test_switchaudiosource_not_available(self, mock_run):
        """Test SwitchAudioSource when not available"""
        # Mock 'which' command returning failure (not installed)
        mock_run.return_value.returncode = 1
        
        devices = self.capture._get_switchaudiosource_devices()
        self.assertEqual(devices, [])


class TestIntegrationTests(unittest.TestCase):
    """Integration tests for the complete audio device listing"""
    
    def setUp(self):
        self.capture = AudioCapture()
    
    def test_real_device_detection(self):
        """Integration test with real device detection"""
        devices = self.capture.list_audio_devices()
        
        # Should have at least one device (built-in microphone/speakers)
        self.assertGreater(len(devices), 0)
        
        # Should have both SystemProfiler, AVCapture, and ScreenCaptureKit devices
        sources = set(d.get('source') for d in devices)
        self.assertIn('ScreenCaptureKit', sources)  # System audio device
        # Note: SystemProfiler and AVCapture may not always be present depending on available devices
        
        # Print device summary for manual verification
        print(f"\nDetected {len(devices)} audio devices:")
        for device in devices:
            print(f"  - {device['name']} ({device['type']}) from {device['source']}")
    
    def test_built_in_devices_present(self):
        """Test that built-in macOS devices are detected"""
        devices = self.capture.list_audio_devices()
        device_names = [d.get('name', '').lower() for d in devices]
        
        # Should find MacBook Pro built-in devices (or similar)
        builtin_keywords = ['macbook', 'built-in', 'internal']
        found_builtin = any(any(keyword in name for keyword in builtin_keywords) 
                           for name in device_names)
        
        self.assertTrue(found_builtin, 
                       "No built-in devices found. Available devices: " + 
                       str([d.get('name') for d in devices]))
    
    def test_device_capabilities_consistency(self):
        """Test that device capabilities are consistent"""
        devices = self.capture.list_audio_devices()
        
        for device in devices:
            # SystemProfiler devices should have has_input/has_output flags
            if device.get('source') == 'SystemProfiler':
                self.assertIn('has_input', device)
                self.assertIn('has_output', device)
                
                # Device type should match capabilities - only input devices should be returned
                has_input = device.get('has_input', False)
                has_output = device.get('has_output', False)
                device_type = device.get('type')
                
                # Only input devices should be present (no pure output devices)
                self.assertTrue(has_input, f"SystemProfiler device should have input capability: {device.get('name')}")
                
                if has_input and has_output:
                    self.assertEqual(device_type, 'input/output')
                elif has_input:
                    self.assertEqual(device_type, 'input')
            
            # ScreenCaptureKit devices should have capabilities
            if device.get('source') == 'ScreenCaptureKit':
                self.assertIn('capabilities', device)
                capabilities = device.get('capabilities', [])
                self.assertGreater(len(capabilities), 0, "ScreenCaptureKit device should have capabilities")
            
            # AVCapture devices should have microphone capability
            if device.get('source') == 'AVCapture':
                self.assertEqual(device.get('type'), 'microphone')
                capabilities = device.get('capabilities', [])
                self.assertIn('microphone_input', capabilities)


if __name__ == '__main__':
    # Configure test runner
    unittest.main(verbosity=2, buffer=True)