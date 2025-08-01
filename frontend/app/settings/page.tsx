'use client'

import { useState, useEffect } from 'react'

interface Settings {
  api: {
    openai_key: string
    google_key: string
    azure_key: string
  }
  audio: {
    sample_rate: number
    channels: number
    format: string
  }
  transcription: {
    language: string
    model: string
    enable_punctuation: boolean
    enable_speaker_diarization: boolean
  }
  translation: {
    default_target: string
    auto_translate: boolean
  }
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings>({
    api: {
      openai_key: '',
      google_key: '',
      azure_key: ''
    },
    audio: {
      sample_rate: 44100,
      channels: 2,
      format: 'wav'
    },
    transcription: {
      language: 'auto',
      model: 'whisper-large',
      enable_punctuation: true,
      enable_speaker_diarization: false
    },
    translation: {
      default_target: 'en',
      auto_translate: false
    }
  })
  
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    fetchSettings()
  }, [])

  const fetchSettings = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/settings')
      if (response.ok) {
        const data = await response.json()
        setSettings(data)
      }
    } catch (error) {
      console.error('Failed to fetch settings:', error)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const response = await fetch('http://localhost:8000/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      })
      
      if (response.ok) {
        setSaved(true)
        setTimeout(() => setSaved(false), 3000)
      }
    } catch (error) {
      console.error('Failed to save settings:', error)
    } finally {
      setSaving(false)
    }
  }

  const updateSettings = (section: keyof Settings, key: string, value: any) => {
    setSettings(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value
      }
    }))
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-8">Settings</h1>

      <div className="space-y-8">
        {/* API Keys */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4">API Keys</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">OpenAI API Key</label>
              <input
                type="password"
                value={settings.api.openai_key}
                onChange={(e) => updateSettings('api', 'openai_key', e.target.value)}
                placeholder="sk-..."
                className="w-full px-3 py-2 border rounded-md"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Google Cloud API Key</label>
              <input
                type="password"
                value={settings.api.google_key}
                onChange={(e) => updateSettings('api', 'google_key', e.target.value)}
                placeholder="AIza..."
                className="w-full px-3 py-2 border rounded-md"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Azure API Key</label>
              <input
                type="password"
                value={settings.api.azure_key}
                onChange={(e) => updateSettings('api', 'azure_key', e.target.value)}
                placeholder="Enter Azure API key"
                className="w-full px-3 py-2 border rounded-md"
              />
            </div>
          </div>
        </div>

        {/* Audio Settings */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4">Audio Settings</h2>
          <div className="grid md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Sample Rate</label>
              <select
                value={settings.audio.sample_rate}
                onChange={(e) => updateSettings('audio', 'sample_rate', parseInt(e.target.value))}
                className="w-full px-3 py-2 border rounded-md"
              >
                <option value={22050}>22.05 kHz</option>
                <option value={44100}>44.1 kHz</option>
                <option value={48000}>48 kHz</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Channels</label>
              <select
                value={settings.audio.channels}
                onChange={(e) => updateSettings('audio', 'channels', parseInt(e.target.value))}
                className="w-full px-3 py-2 border rounded-md"
              >
                <option value={1}>Mono</option>
                <option value={2}>Stereo</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Format</label>
              <select
                value={settings.audio.format}
                onChange={(e) => updateSettings('audio', 'format', e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
              >
                <option value="wav">WAV</option>
                <option value="mp3">MP3</option>
                <option value="flac">FLAC</option>
              </select>
            </div>
          </div>
        </div>

        {/* Transcription Settings */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4">Transcription Settings</h2>
          <div className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">Language</label>
                <select
                  value={settings.transcription.language}
                  onChange={(e) => updateSettings('transcription', 'language', e.target.value)}
                  className="w-full px-3 py-2 border rounded-md"
                >
                  <option value="auto">Auto-detect</option>
                  <option value="en">English</option>
                  <option value="es">Spanish</option>
                  <option value="fr">French</option>
                  <option value="de">German</option>
                  <option value="zh">Chinese</option>
                  <option value="ja">Japanese</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Model</label>
                <select
                  value={settings.transcription.model}
                  onChange={(e) => updateSettings('transcription', 'model', e.target.value)}
                  className="w-full px-3 py-2 border rounded-md"
                >
                  <option value="whisper-tiny">Whisper Tiny (Fastest)</option>
                  <option value="whisper-base">Whisper Base</option>
                  <option value="whisper-small">Whisper Small</option>
                  <option value="whisper-medium">Whisper Medium</option>
                  <option value="whisper-large">Whisper Large (Most Accurate)</option>
                </select>
              </div>
            </div>
            <div className="space-y-2">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={settings.transcription.enable_punctuation}
                  onChange={(e) => updateSettings('transcription', 'enable_punctuation', e.target.checked)}
                  className="mr-2"
                />
                <span className="text-sm">Enable automatic punctuation</span>
              </label>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={settings.transcription.enable_speaker_diarization}
                  onChange={(e) => updateSettings('transcription', 'enable_speaker_diarization', e.target.checked)}
                  className="mr-2"
                />
                <span className="text-sm">Enable speaker diarization</span>
              </label>
            </div>
          </div>
        </div>

        {/* Translation Settings */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4">Translation Settings</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Default Target Language</label>
              <select
                value={settings.translation.default_target}
                onChange={(e) => updateSettings('translation', 'default_target', e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
              >
                <option value="en">English</option>
                <option value="es">Spanish</option>
                <option value="fr">French</option>
                <option value="de">German</option>
                <option value="it">Italian</option>
                <option value="pt">Portuguese</option>
                <option value="ru">Russian</option>
                <option value="ja">Japanese</option>
                <option value="ko">Korean</option>
                <option value="zh">Chinese</option>
              </select>
            </div>
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={settings.translation.auto_translate}
                onChange={(e) => updateSettings('translation', 'auto_translate', e.target.checked)}
                className="mr-2"
              />
              <span className="text-sm">Automatically translate transcriptions</span>
            </label>
          </div>
        </div>

        {/* Save Button */}
        <div className="flex justify-end">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-3 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:bg-gray-300 transition-colors flex items-center gap-2"
          >
            {saving ? 'Saving...' : 'Save Settings'}
            {saved && (
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}