# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TransFlow is a macOS audio recording application that uses Python and Apple's ScreenCaptureKit framework to capture system audio and application-specific audio. The project uses PyObjC (Python-Objective-C bridge) to interface with macOS APIs.

## Running the Application

```bash
python main.py
```

This starts the audio recording application which will:
1. List available displays and running applications
2. Create an audio recording of all system audio (excluding the script's own audio)
3. Save the recording to `output.wav` when stopped with Ctrl+C

## Architecture

The project consists of a single `main.py` file that contains:

- **CaptureDelegate** (main.py:18-80): NSObject subclass implementing SCStreamDelegate for receiving audio samples
  - Handles 32-bit float to 16-bit integer audio conversion
  - Queues audio data for saving to WAV file

- **Core Functions**:
  - `list_displays()` (main.py:82): Lists available displays
  - `list_applications()` (main.py:87): Lists running applications  
  - `save_audio_queue()` (main.py:92): Saves queued audio data to WAV file
  - `record_audio()` (main.py:108): Main recording function that sets up SCStream

## Key Technical Details

- **Audio Processing**: The system captures audio in 32-bit float format which must be converted to 16-bit integer for WAV file output
- **Prevent Feedback**: Uses `excludesCurrentProcessAudio = True` to prevent recording the script's own audio output
- **macOS Frameworks Used**:
  - ScreenCaptureKit: For screen and audio capture
  - AVFoundation: For audio format conversion
  - Foundation: For Objective-C runtime and threading

## Dependencies

The project requires PyObjC but has no formal dependency management. Required imports:
- `objc`
- `Foundation` 
- `AVFoundation`
- `ScreenCaptureKit`

## Notes

- The project is macOS-specific and requires macOS 12.3+ for ScreenCaptureKit
- Screen recording permissions must be granted for the application to work
- Currently only supports recording all system audio; application-specific recording is documented but not implemented


## TESTS
Add tests in `tests` directory


## DOCS

docs in `docs` directory

todo in `docs/TODO.md`
