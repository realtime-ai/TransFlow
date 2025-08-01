'use client'

import { useState, useEffect } from 'react'
import TranscriptionDisplay from '@/components/TranscriptionDisplay'
import TranslationInterface from '@/components/TranslationInterface'

export default function RecordPage() {
  const [isRecording, setIsRecording] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [recordingTime, setRecordingTime] = useState(0)
  const [audioSource, setAudioSource] = useState<'system' | 'microphone'>('system')

  useEffect(() => {
    let interval: NodeJS.Timeout | null = null
    
    if (isRecording && !isPaused) {
      interval = setInterval(() => {
        setRecordingTime((time) => time + 1)
      }, 1000)
    }
    
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [isRecording, isPaused])

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  const handleStartRecording = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/start-recording', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: audioSource })
      })
      
      if (response.ok) {
        setIsRecording(true)
        setRecordingTime(0)
      }
    } catch (error) {
      console.error('Failed to start recording:', error)
    }
  }

  const handleStopRecording = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/stop-recording', {
        method: 'POST'
      })
      
      if (response.ok) {
        setIsRecording(false)
        setIsPaused(false)
        setRecordingTime(0)
      }
    } catch (error) {
      console.error('Failed to stop recording:', error)
    }
  }

  const handlePauseResume = async () => {
    try {
      const endpoint = isPaused ? '/api/resume-recording' : '/api/pause-recording'
      const response = await fetch(`http://localhost:8000${endpoint}`, {
        method: 'POST'
      })
      
      if (response.ok) {
        setIsPaused(!isPaused)
      }
    } catch (error) {
      console.error('Failed to pause/resume recording:', error)
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-8">Audio Recording</h1>
      
      <div className="bg-white rounded-lg shadow-md p-8">
        {/* Audio Source Selection */}
        <div className="mb-8">
          <h2 className="text-lg font-semibold mb-4">Audio Source</h2>
          <div className="flex gap-4">
            <label className="flex items-center">
              <input
                type="radio"
                name="audioSource"
                value="system"
                checked={audioSource === 'system'}
                onChange={(e) => setAudioSource(e.target.value as 'system' | 'microphone')}
                disabled={isRecording}
                className="mr-2"
              />
              <span>System Audio</span>
            </label>
            <label className="flex items-center">
              <input
                type="radio"
                name="audioSource"
                value="microphone"
                checked={audioSource === 'microphone'}
                onChange={(e) => setAudioSource(e.target.value as 'system' | 'microphone')}
                disabled={isRecording}
                className="mr-2"
              />
              <span>Microphone</span>
            </label>
          </div>
        </div>

        {/* Recording Status */}
        <div className="text-center mb-8">
          <div className="text-6xl font-mono mb-4">{formatTime(recordingTime)}</div>
          {isRecording && (
            <div className="flex items-center justify-center gap-2">
              <div className={`w-3 h-3 rounded-full ${isPaused ? 'bg-yellow-500' : 'bg-red-500 animate-pulse'}`} />
              <span className="text-lg">{isPaused ? 'Paused' : 'Recording'}</span>
            </div>
          )}
        </div>

        {/* Control Buttons */}
        <div className="flex justify-center gap-4">
          {!isRecording ? (
            <button
              onClick={handleStartRecording}
              className="px-8 py-4 bg-red-500 text-white rounded-full font-semibold hover:bg-red-600 transition-colors flex items-center gap-2"
            >
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                <circle cx="10" cy="10" r="8" />
              </svg>
              Start Recording
            </button>
          ) : (
            <>
              <button
                onClick={handlePauseResume}
                className="px-6 py-3 bg-yellow-500 text-white rounded-full font-semibold hover:bg-yellow-600 transition-colors flex items-center gap-2"
              >
                {isPaused ? (
                  <>
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M5 4v12l10-6z" />
                    </svg>
                    Resume
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                      <rect x="5" y="4" width="3" height="12" />
                      <rect x="12" y="4" width="3" height="12" />
                    </svg>
                    Pause
                  </>
                )}
              </button>
              <button
                onClick={handleStopRecording}
                className="px-6 py-3 bg-gray-600 text-white rounded-full font-semibold hover:bg-gray-700 transition-colors flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <rect x="5" y="5" width="10" height="10" />
                </svg>
                Stop
              </button>
            </>
          )}
        </div>

        {/* Recording Settings */}
        <div className="mt-8 pt-8 border-t">
          <h3 className="text-lg font-semibold mb-4">Recording Settings</h3>
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium mb-2">Audio Quality</label>
              <select className="w-full px-3 py-2 border rounded-md" disabled={isRecording}>
                <option>High (48kHz, 24-bit)</option>
                <option>Medium (44.1kHz, 16-bit)</option>
                <option>Low (22kHz, 16-bit)</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Format</label>
              <select className="w-full px-3 py-2 border rounded-md" disabled={isRecording}>
                <option>WAV</option>
                <option>MP3</option>
                <option>FLAC</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Transcription Display */}
      <div className="mt-8">
        <TranscriptionDisplay />
      </div>

      {/* Translation Interface */}
      <div className="mt-8">
        <TranslationInterface />
      </div>
    </div>
  )
}