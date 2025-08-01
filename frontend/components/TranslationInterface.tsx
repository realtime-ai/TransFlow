'use client'

import { useState, useEffect } from 'react'

interface Translation {
  id: string
  sourceText: string
  translatedText: string
  sourceLang: string
  targetLang: string
  timestamp: string
}

const SUPPORTED_LANGUAGES = [
  { code: 'en', name: 'English' },
  { code: 'es', name: 'Spanish' },
  { code: 'fr', name: 'French' },
  { code: 'de', name: 'German' },
  { code: 'it', name: 'Italian' },
  { code: 'pt', name: 'Portuguese' },
  { code: 'ru', name: 'Russian' },
  { code: 'ja', name: 'Japanese' },
  { code: 'ko', name: 'Korean' },
  { code: 'zh', name: 'Chinese' },
]

export default function TranslationInterface() {
  const [translations, setTranslations] = useState<Translation[]>([])
  const [sourceLang, setSourceLang] = useState('auto')
  const [targetLang, setTargetLang] = useState('en')
  const [isTranslating, setIsTranslating] = useState(false)
  const [manualText, setManualText] = useState('')

  const handleManualTranslate = async () => {
    if (!manualText.trim()) return

    setIsTranslating(true)
    try {
      const response = await fetch('http://localhost:8000/api/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: manualText,
          source_lang: sourceLang === 'auto' ? null : sourceLang,
          target_lang: targetLang
        })
      })

      if (response.ok) {
        const data = await response.json()
        const newTranslation: Translation = {
          id: Date.now().toString(),
          sourceText: manualText,
          translatedText: data.translated_text,
          sourceLang: data.detected_lang || sourceLang,
          targetLang: targetLang,
          timestamp: new Date().toLocaleTimeString()
        }
        setTranslations([newTranslation, ...translations])
        setManualText('')
      }
    } catch (error) {
      console.error('Translation error:', error)
    } finally {
      setIsTranslating(false)
    }
  }

  const handleClearTranslations = () => {
    setTranslations([])
  }

  const handleExportTranslations = () => {
    const content = translations
      .map(t => `[${t.timestamp}] ${t.sourceLang} → ${t.targetLang}\n${t.sourceText}\n→ ${t.translatedText}\n`)
      .join('\n')
    
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `translations_${new Date().toISOString()}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-semibold">Translation</h2>
        <div className="flex gap-2">
          <button
            onClick={handleClearTranslations}
            className="px-3 py-1 text-sm bg-gray-200 hover:bg-gray-300 rounded transition-colors"
          >
            Clear
          </button>
          <button
            onClick={handleExportTranslations}
            className="px-3 py-1 text-sm bg-blue-500 text-white hover:bg-blue-600 rounded transition-colors"
            disabled={translations.length === 0}
          >
            Export
          </button>
        </div>
      </div>

      {/* Language Selection */}
      <div className="grid md:grid-cols-2 gap-4 mb-6">
        <div>
          <label className="block text-sm font-medium mb-2">Source Language</label>
          <select 
            value={sourceLang} 
            onChange={(e) => setSourceLang(e.target.value)}
            className="w-full px-3 py-2 border rounded-md"
          >
            <option value="auto">Auto-detect</option>
            {SUPPORTED_LANGUAGES.map(lang => (
              <option key={lang.code} value={lang.code}>{lang.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-2">Target Language</label>
          <select 
            value={targetLang} 
            onChange={(e) => setTargetLang(e.target.value)}
            className="w-full px-3 py-2 border rounded-md"
          >
            {SUPPORTED_LANGUAGES.map(lang => (
              <option key={lang.code} value={lang.code}>{lang.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Manual Translation Input */}
      <div className="mb-6">
        <label className="block text-sm font-medium mb-2">Manual Translation</label>
        <div className="flex gap-2">
          <textarea
            value={manualText}
            onChange={(e) => setManualText(e.target.value)}
            placeholder="Enter text to translate..."
            className="flex-1 px-3 py-2 border rounded-md resize-none"
            rows={3}
          />
          <button
            onClick={handleManualTranslate}
            disabled={isTranslating || !manualText.trim()}
            className="px-4 py-2 bg-green-500 text-white rounded-md hover:bg-green-600 disabled:bg-gray-300 transition-colors"
          >
            {isTranslating ? 'Translating...' : 'Translate'}
          </button>
        </div>
      </div>

      {/* Translation History */}
      <div className="border-t pt-4">
        <h3 className="text-lg font-medium mb-4">Translation History</h3>
        <div className="space-y-4 max-h-96 overflow-y-auto">
          {translations.length === 0 ? (
            <p className="text-gray-500 text-center py-8">No translations yet...</p>
          ) : (
            translations.map((translation) => (
              <div key={translation.id} className="border rounded-md p-4 bg-gray-50">
                <div className="flex justify-between items-start mb-2">
                  <span className="text-xs text-gray-500">{translation.timestamp}</span>
                  <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
                    {translation.sourceLang} → {translation.targetLang}
                  </span>
                </div>
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm font-medium text-gray-600 mb-1">Original</p>
                    <p className="text-sm">{translation.sourceText}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-600 mb-1">Translation</p>
                    <p className="text-sm">{translation.translatedText}</p>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}