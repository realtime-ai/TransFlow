#!/usr/bin/env python3
"""
Test script to verify basic Socket.IO connection
"""
import socketio
import time

# Create a Socket.IO client
sio = socketio.Client()

@sio.event
def connect():
    print("Connected to server!")
    # Send a ping
    sio.emit('ping')

@sio.event
def pong(data):
    print(f"Received pong: {data}")

@sio.event
def disconnect():
    print("Disconnected from server!")

@sio.event
def connection_status(data):
    print(f"Connection status: {data}")

def main():
    try:
        # Connect to the server
        print("Connecting to server...")
        sio.connect('http://localhost:5000')
        
        # Wait a bit
        time.sleep(2)
        
        # Test recording start
        print("\nTesting recording start...")
        sio.emit('start_recording', {
            'sourceLanguage': 'zh',
            'targetLanguage': 'en'
        })
        
        time.sleep(2)
        
        # Test recording stop
        print("\nTesting recording stop...")
        sio.emit('stop_recording')
        
        time.sleep(1)
        
        # Disconnect
        sio.disconnect()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()