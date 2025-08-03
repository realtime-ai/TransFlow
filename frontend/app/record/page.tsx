'use client'

import { useState, useEffect } from 'react'
import { useSocketIO } from '@/hooks/useSocketIO'

interface TranscriptionData {
  id: string
  sourceText: string
  translatedText: string
  timestamp: string
  confidence: number
}

export default function RecordPage() {
  const [isRecording, setIsRecording] = useState(false)
  const [recordingTime, setRecordingTime] = useState(0)
  const [displayMode, setDisplayMode] = useState<'dual' | 'source' | 'target'>('dual')
  const [transcriptions, setTranscriptions] = useState<TranscriptionData[]>([])
  const [currentTranscription, setCurrentTranscription] = useState<string>('')
  const [currentTranslation, setCurrentTranslation] = useState<string>('')
  
  const { emit, on, off, isConnected } = useSocketIO('http://localhost:5001')

  useEffect(() => {
    let interval: NodeJS.Timeout | null = null
    
    if (isRecording) {
      interval = setInterval(() => {
        setRecordingTime((time) => time + 1)
      }, 1000)
    }
    
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [isRecording])

  useEffect(() => {
    const handleTranscription = (data: any) => {
      const { text, translation, timestamp } = data
      
      if (text && translation) {
        const newTranscription: TranscriptionData = {
          id: Date.now().toString(),
          sourceText: text,
          translatedText: translation,
          timestamp: timestamp || new Date().toISOString(),
          confidence: 1.0
        }
        setTranscriptions(prev => [...prev, newTranscription])
        setCurrentTranscription('')
        setCurrentTranslation('')
      } else {
        // Partial transcription
        if (text) setCurrentTranscription(text)
        if (translation) setCurrentTranslation(translation)
      }
    }

    const handleRecordingStarted = (data: any) => {
      if (data.status === 'success') {
        setIsRecording(true)
        setRecordingTime(0)
        setTranscriptions([])
      }
    }

    const handleRecordingStopped = (data: any) => {
      if (data.status === 'success') {
        setIsRecording(false)
        setCurrentTranscription('')
        setCurrentTranslation('')
      }
    }

    const handleError = (error: any) => {
      console.error('Socket.IO error:', error)
    }

    on('transcription', handleTranscription)
    on('recording_started', handleRecordingStarted)
    on('recording_stopped', handleRecordingStopped)
    on('error', handleError)

    // Load settings from localStorage
    const savedSettings = localStorage.getItem('transflow-settings')
    if (savedSettings) {
      const settings = JSON.parse(savedSettings)
      emit('set_languages', {
        sourceLanguage: settings.sourceLanguage,
        targetLanguage: settings.targetLanguage
      })
    }

    return () => {
      off('transcription', handleTranscription)
      off('recording_started', handleRecordingStarted)
      off('recording_stopped', handleRecordingStopped)
      off('error', handleError)
    }
  }, [emit, on, off])

  const formatTime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60
    
    if (hours > 0) {
      return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
    }
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  const handleStartRecording = () => {
    const savedSettings = localStorage.getItem('transflow-settings')
    const settings = savedSettings ? JSON.parse(savedSettings) : {
      sourceLanguage: 'zh',
      targetLanguage: 'en',
      audioDevice: 'default'
    }
    
    emit('start_recording', {
      captureSystemAudio: true,
      sourceLanguage: settings.sourceLanguage,
      targetLanguage: settings.targetLanguage,
      audioDevice: settings.audioDevice
    })
  }

  const handleStopRecording = () => {
    emit('stop_recording')
  }

  const getDisplayModeLabel = (mode: string) => {
    switch (mode) {
      case 'dual': return '双语'
      case 'source': return '中文'
      case 'target': return 'English'
      default: return '双语'
    }
  }

  const exportTranscription = () => {
    const content = transcriptions.map(t => {
      const time = new Date(t.timestamp).toLocaleTimeString()
      return `[${time}]\n源语言: ${t.sourceText}\n翻译: ${t.translatedText}\n\n`
    }).join('')
    
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `transcription_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="max-w-6xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent mb-4">
          同声传译结果
        </h1>
        <p className="text-gray-600 text-lg">实时音频转写与翻译</p>
      </div>

      {/* Audio Controls Bar */}
      <div className="card-gradient rounded-3xl p-6 mb-8">
        <div className="flex items-center justify-between">
          {/* Recording Time and Status */}
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-3">
              <div className={`w-4 h-4 rounded-full ${
                isRecording ? 'bg-red-500 recording-pulse' : 'bg-gray-400'
              }`} />
              <span className="text-3xl font-mono font-bold text-gray-800">
                {formatTime(recordingTime)}
              </span>
            </div>
            
            {/* Connection Status */}
            <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm ${
              isConnected ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'
            }`}>
              <div className={`w-2 h-2 rounded-full ${
                isConnected ? 'status-connected' : 'status-disconnected'
              }`} />
              {isConnected ? '已连接' : '未连接'}
            </div>
          </div>
          
          {/* Control Buttons */}
          <div className="flex items-center gap-4">
            {!isRecording ? (
              <button
                onClick={handleStartRecording}
                disabled={!isConnected}
                className="btn-secondary text-white px-8 py-4 rounded-xl font-semibold flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <circle cx="10" cy="10" r="6" />
                </svg>
                开始录制
              </button>
            ) : (
              <button
                onClick={handleStopRecording}
                className="btn-neutral text-white px-8 py-4 rounded-xl font-semibold flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <rect x="6" y="6" width="8" height="8" />
                </svg>
                停止录制
              </button>
            )}
            
            <button
              onClick={exportTranscription}
              disabled={transcriptions.length === 0}
              className="btn-primary text-white px-6 py-4 rounded-xl font-semibold flex items-center gap-2"
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
              导出
            </button>
          </div>
        </div>
        
        {/* Audio Waveform Visualization Placeholder */}
        <div className="mt-6 h-20 bg-gradient-to-r from-blue-100 to-purple-100 rounded-xl flex items-center justify-center relative overflow-hidden">
          {isRecording ? (
            <div className="flex items-center gap-1 h-full w-full px-4">
              {Array.from({ length: 50 }).map((_, i) => (
                <div
                  key={i}
                  className="bg-blue-500 opacity-60 rounded-full animate-pulse"
                  style={{
                    width: '3px',
                    height: `${Math.random() * 80 + 20}%`,
                    animationDelay: `${i * 0.1}s`
                  }}
                />
              ))}
            </div>
          ) : (
            <div className="text-gray-500 flex items-center gap-2">
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 015 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z" clipRule="evenodd" />
              </svg>
              <span>音频波形显示</span>
            </div>
          )}
        </div>
      </div>
      
      {/* Language View Switcher */}
      <div className="flex justify-center mb-6">
        <div className="glass rounded-2xl p-2">
          <div className="flex gap-2">
            {[{ key: 'dual', label: '双语' }, { key: 'source', label: '中文' }, { key: 'target', label: 'English' }].map((mode) => (
              <button
                key={mode.key}
                onClick={() => setDisplayMode(mode.key as 'dual' | 'source' | 'target')}
                className={`px-6 py-3 rounded-xl font-semibold transition-all duration-300 ${
                  displayMode === mode.key
                    ? 'bg-gradient-to-r from-blue-500 to-purple-500 text-white shadow-lg'
                    : 'text-gray-600 hover:bg-white hover:bg-opacity-50'
                }`}
              >
                {mode.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Dual Language Transcription Display */}
      <div className="card-gradient rounded-3xl p-8">
        <div className="h-96 overflow-y-auto space-y-4">
          {transcriptions.length === 0 && !currentTranscription && (
            <div className="flex flex-col items-center justify-center h-full text-gray-500">
              <div className="w-16 h-16 bg-gradient-to-r from-blue-100 to-purple-100 rounded-2xl flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 015 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z" clipRule="evenodd" />
                </svg>
              </div>
              <p className="text-xl font-medium mb-2">等待音频输入...</p>
              <p className="text-sm">开始录制以查看实时转写和翻译结果</p>
            </div>
          )}
          
          {/* Completed transcriptions */}
          {transcriptions.map((transcription) => (
            <div key={transcription.id} className="glass rounded-2xl p-6 border border-white border-opacity-20">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-3 h-3 bg-gradient-to-r from-green-400 to-blue-500 rounded-full" />
                <span className="text-sm text-gray-500">
                  {new Date(transcription.timestamp).toLocaleTimeString()}
                </span>
              </div>
              
              {(displayMode === 'dual' || displayMode === 'source') && (
                <div className="mb-4">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-medium text-blue-600 bg-blue-100 px-3 py-1 rounded-lg">
                      🇨🇳 中文
                    </span>
                  </div>
                  <p className="text-gray-800 text-lg leading-relaxed">{transcription.sourceText}</p>
                </div>
              )}
              
              {(displayMode === 'dual' || displayMode === 'target') && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-medium text-purple-600 bg-purple-100 px-3 py-1 rounded-lg">
                      🇺🇸 English
                    </span>
                  </div>
                  <p className="text-gray-800 text-lg leading-relaxed">{transcription.translatedText}</p>
                </div>
              )}
            </div>
          ))}
          
          {/* Current live transcription */}
          {(currentTranscription || currentTranslation) && (
            <div className="glass rounded-2xl p-6 border-2 border-yellow-300 border-opacity-50 bg-yellow-50 bg-opacity-30">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-3 h-3 bg-yellow-400 rounded-full animate-pulse" />
                <span className="text-sm text-yellow-600 bg-yellow-100 px-3 py-1 rounded-lg">
                  ⚡ 实时处理中...
                </span>
              </div>
              
              {currentTranscription && (displayMode === 'dual' || displayMode === 'source') && (
                <div className="mb-4">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-medium text-blue-600 bg-blue-100 px-3 py-1 rounded-lg">
                      🇨🇳 中文
                    </span>
                  </div>
                  <p className="text-gray-700 text-lg leading-relaxed italic">{currentTranscription}</p>
                </div>
              )}
              
              {currentTranslation && (displayMode === 'dual' || displayMode === 'target') && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-medium text-purple-600 bg-purple-100 px-3 py-1 rounded-lg">
                      🇺🇸 English
                    </span>
                  </div>
                  <p className="text-gray-700 text-lg leading-relaxed italic">{currentTranslation}</p>
                </div>
              )}
            </div>
          )}
        </div>
        
        {/* Statistics */}
        <div className="mt-6 pt-6 border-t border-gray-200 grid grid-cols-3 gap-4">
          <div className="glass p-4 rounded-xl text-center">
            <div className="text-2xl font-bold text-blue-600">
              {transcriptions.length}
            </div>
            <div className="text-sm text-gray-600">转写段落</div>
          </div>
          <div className="glass p-4 rounded-xl text-center">
            <div className="text-2xl font-bold text-purple-600">
              {transcriptions.reduce((acc, t) => acc + t.sourceText.length, 0)}
            </div>
            <div className="text-sm text-gray-600">源语言字符</div>
          </div>
          <div className="glass p-4 rounded-xl text-center">
            <div className="text-2xl font-bold text-pink-600">
              {transcriptions.reduce((acc, t) => acc + t.translatedText.split(' ').length, 0)}
            </div>
            <div className="text-sm text-gray-600">翻译词汇</div>
          </div>
        </div>
      </div>
    </div>
  )
}