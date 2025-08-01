'use client'

import { useState, useEffect, useRef } from 'react'
import { useWebSocket } from '@/hooks/useWebSocket'

interface TranscriptionSegment {
  id: string
  text: string
  timestamp: string
  language: string
  confidence: number
  isFinal: boolean
}

export default function TranscriptionDisplay() {
  const [transcriptions, setTranscriptions] = useState<TranscriptionSegment[]>([])
  const [currentSegment, setCurrentSegment] = useState<string>('')
  const scrollRef = useRef<HTMLDivElement>(null)

  const { isConnected, lastMessage } = useWebSocket({
    url: 'ws://localhost:8000/ws/transcription',
    onMessage: (message) => {
      if (message.type === 'transcription') {
        const { id, text, timestamp, language, confidence, is_final } = message.data
        
        if (is_final) {
          const newSegment: TranscriptionSegment = {
            id,
            text,
            timestamp,
            language,
            confidence,
            isFinal: true
          }
          setTranscriptions(prev => [...prev, newSegment])
          setCurrentSegment('')
        } else {
          setCurrentSegment(text)
        }
      }
    }
  })

  useEffect(() => {
    // Auto-scroll to bottom when new transcriptions are added
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [transcriptions])

  const handleClearTranscriptions = () => {
    setTranscriptions([])
    setCurrentSegment('')
  }

  const handleExportTranscriptions = () => {
    const text = transcriptions
      .filter(t => t.isFinal)
      .map(t => `[${t.timestamp}] ${t.text}`)
      .join('\n')
    
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `transcription_${new Date().toISOString()}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold">Transcription</h2>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-400'}`} />
            <span className="text-sm">{isConnected ? 'Connected' : 'Disconnected'}</span>
          </div>
          <button
            onClick={handleClearTranscriptions}
            className="px-3 py-1 text-sm bg-gray-200 hover:bg-gray-300 rounded transition-colors"
          >
            Clear
          </button>
          <button
            onClick={handleExportTranscriptions}
            className="px-3 py-1 text-sm bg-blue-500 text-white hover:bg-blue-600 rounded transition-colors"
            disabled={transcriptions.length === 0}
          >
            Export
          </button>
        </div>
      </div>

      <div 
        ref={scrollRef}
        className="h-96 overflow-y-auto border rounded-md p-4 bg-gray-50"
      >
        {transcriptions.length === 0 && !currentSegment ? (
          <p className="text-gray-500 text-center">Transcription will appear here...</p>
        ) : (
          <div className="space-y-2">
            {transcriptions.map((segment) => (
              <div 
                key={segment.id}
                className={`p-2 rounded ${segment.isFinal ? 'bg-white' : 'bg-blue-50'}`}
              >
                <div className="flex items-start gap-2">
                  <span className="text-xs text-gray-500 flex-shrink-0">
                    {segment.timestamp}
                  </span>
                  <p className={`text-sm ${segment.isFinal ? 'text-gray-800' : 'text-gray-600'}`}>
                    {segment.text}
                  </p>
                  {!segment.isFinal && (
                    <span className="text-xs text-blue-600 flex-shrink-0">
                      {Math.round(segment.confidence * 100)}%
                    </span>
                  )}
                </div>
              </div>
            ))}
            
            {currentSegment && (
              <div className="p-2 rounded bg-yellow-50 border border-yellow-200">
                <p className="text-sm text-gray-700 italic">{currentSegment}</p>
                <span className="text-xs text-yellow-600">Processing...</span>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="mt-4 flex justify-between text-sm text-gray-600">
        <span>Total segments: {transcriptions.filter(t => t.isFinal).length}</span>
        <span>Words: {transcriptions.filter(t => t.isFinal).reduce((acc, t) => acc + t.text.split(' ').length, 0)}</span>
      </div>
    </div>
  )
}