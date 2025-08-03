#!/usr/bin/env python3
"""
Test runner for audio device tests
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_all_tests(show_output=False):
    """Run all audio device tests"""
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(os.path.abspath(__file__))
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    # Use buffer=False to show print output if requested
    runner = unittest.TextTestRunner(verbosity=2, buffer=not show_output)
    result = runner.run(suite)
    
    return result.wasSuccessful()

def run_integration_tests(show_output=True):
    """Run only integration tests with device output"""
    from test_audio_devices import TestIntegrationTests
    
    suite = unittest.TestLoader().loadTestsFromTestCase(TestIntegrationTests)
    runner = unittest.TextTestRunner(verbosity=2, buffer=not show_output)
    result = runner.run(suite)
    
    return result.wasSuccessful()

def run_specific_test(test_name, show_output=True):
    """Run a specific test method"""
    from test_audio_devices import TestAudioDevices, TestIntegrationTests, TestSystemProfilerDevices, TestSwitchAudioSourceDevices
    
    # Map test classes
    test_classes = {
        'basic': TestAudioDevices,
        'integration': TestIntegrationTests,
        'system_profiler': TestSystemProfilerDevices,
        'switch_audio': TestSwitchAudioSourceDevices
    }
    
    if test_name in test_classes:
        suite = unittest.TestLoader().loadTestsFromTestCase(test_classes[test_name])
    else:
        # Try to load specific test method
        try:
            suite = unittest.TestLoader().loadTestsFromName(f'test_audio_devices.{test_name}')
        except:
            print(f"Test '{test_name}' not found")
            return False
    
    runner = unittest.TextTestRunner(verbosity=2, buffer=not show_output)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Run audio device tests')
    parser.add_argument('--integration', action='store_true', 
                       help='Run only integration tests with device output')
    parser.add_argument('--show-output', '-s', action='store_true',
                       help='Show print output during tests (like pytest -s)')
    parser.add_argument('--test', '-t', type=str,
                       help='Run specific test class or method (basic, integration, system_profiler, switch_audio)')
    parser.add_argument('--list-tests', action='store_true',
                       help='List available test options')
    
    args = parser.parse_args()
    
    if args.list_tests:
        print("Available test options:")
        print("  --test basic           : Run basic AudioCapture tests")
        print("  --test integration     : Run integration tests")
        print("  --test system_profiler : Run SystemProfiler tests")
        print("  --test switch_audio    : Run SwitchAudioSource tests")
        print("  --integration          : Run integration tests (same as --test integration)")
        print("  --show-output / -s     : Show print statements during tests")
        sys.exit(0)
    
    success = False
    
    if args.test:
        success = run_specific_test(args.test, show_output=args.show_output)
    elif args.integration:
        success = run_integration_tests(show_output=True)  # Always show output for integration
    else:
        success = run_all_tests(show_output=args.show_output)
    
    sys.exit(0 if success else 1)