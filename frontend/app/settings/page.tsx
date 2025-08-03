'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useSocketIO } from '@/hooks/useSocketIO'

const languages = {
  source: [
    { code: 'zh', name: '中文', flag: '🇨🇳' },
    { code: 'en', name: 'English', flag: '🇺🇸' },
    { code: 'ja', name: '日本語', flag: '🇯🇵' },
    { code: 'ko', name: '한국어', flag: '🇰🇷' },
  ],
  target: [
    { code: 'en', name: 'English', flag: '🇺🇸' },
    { code: 'zh', name: '中文', flag: '🇨🇳' },
    { code: 'ja', name: '日本語', flag: '🇯🇵' },
    { code: 'ko', name: '한국어', flag: '🇰🇷' },
  ]
}

interface AudioDevice {
  id: string
  name: string
  type: 'builtin' | 'usb' | 'bluetooth' | 'external'
}

const meetingDomains = [
  '商务会议',
  '技术讨论',
  '学术会议',
  '医疗会议',
  '法律会议',
  '教育培训',
  '金融会议',
  '其他'
]

export default function SettingsPage() {
  const router = useRouter()
  const { emit, on, off, isConnected } = useSocketIO('http://localhost:5001')
  
  const [settings, setSettings] = useState({
    sourceLanguage: 'zh',
    targetLanguage: 'en',
    audioDevice: 'default',
    meetingDomain: '商务会议',
    meetingName: '',
  })

  const [audioDevices, setAudioDevices] = useState<AudioDevice[]>([
    { id: 'default', name: '系统默认麦克风', type: 'builtin' }
  ])
  const [loadingDevices, setLoadingDevices] = useState(false)

  // Fetch audio devices when connected
  useEffect(() => {
    if (isConnected) {
      setLoadingDevices(true)
      emit('get_audio_devices')
    }

    const handleAudioDevices = (devices: AudioDevice[]) => {
      setAudioDevices(devices)
      setLoadingDevices(false)
      
      // If current selected device is not in the list, reset to default
      if (!devices.find(d => d.id === settings.audioDevice)) {
        setSettings(prev => ({ ...prev, audioDevice: devices[0]?.id || 'default' }))
      }
    }

    const handleAudioDevicesError = (error: any) => {
      console.error('Failed to fetch audio devices:', error)
      setLoadingDevices(false)
      // Keep default device on error
    }

    on('audio_devices', handleAudioDevices)
    on('audio_devices_error', handleAudioDevicesError)

    return () => {
      off('audio_devices', handleAudioDevices)
      off('audio_devices_error', handleAudioDevicesError)
    }
  }, [isConnected, emit, on, off, settings.audioDevice])

  const handleLanguageChange = (type: 'source' | 'target', value: string) => {
    setSettings(prev => ({
      ...prev,
      [`${type}Language`]: value
    }))
  }

  const refreshAudioDevices = () => {
    if (isConnected) {
      setLoadingDevices(true)
      emit('get_audio_devices')
    }
  }

  const handleStartInterpreting = () => {
    if (!isConnected) {
      alert('请等待服务器连接')
      return
    }

    if (!settings.meetingName.trim()) {
      alert('请输入会议名称')
      return
    }

    // 发送设置到后端
    emit('set_languages', {
      sourceLanguage: settings.sourceLanguage,
      targetLanguage: settings.targetLanguage
    })

    // 保存设置到本地存储
    localStorage.setItem('transflow-settings', JSON.stringify(settings))

    // 跳转到录制页面
    router.push('/record')
  }

  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      {/* 页面标题 */}
      <div className="text-center mb-12">
        <h1 className="text-5xl font-bold bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent mb-4">
          同声传译设置
        </h1>
        <p className="text-gray-600 text-lg">配置您的实时翻译参数</p>
      </div>

      <div className="card-gradient rounded-3xl p-8 space-y-8">
        {/* 语言设置 */}
        <div className="space-y-6">
          <h2 className="text-2xl font-bold text-gray-800 flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-r from-blue-500 to-purple-500 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M7 2a1 1 0 011 1v1h3a1 1 0 110 2H9.578a18.87 18.87 0 01-1.724 4.78c.29.354.596.696.914 1.026a1 1 0 11-1.44 1.389c-.188-.196-.373-.396-.554-.6a19.098 19.098 0 01-3.107 3.567 1 1 0 01-1.334-1.49 17.087 17.087 0 003.13-3.733 18.992 18.992 0 01-1.487-2.494 1 1 0 111.79-.89c.234.47.489.928.764 1.372.417-.934.752-1.913.997-2.927H3a1 1 0 110-2h3V3a1 1 0 011-1z" clipRule="evenodd" />
              </svg>
            </div>
            语言设置
          </h2>
          
          <div className="grid md:grid-cols-2 gap-6">
            {/* 源语言 */}
            <div className="space-y-3">
              <label className="block text-sm font-medium text-gray-700">源语言（说话语言）</label>
              <div className="grid grid-cols-2 gap-2">
                {languages.source.map((lang) => (
                  <button
                    key={lang.code}
                    onClick={() => handleLanguageChange('source', lang.code)}
                    className={`p-4 rounded-xl border-2 transition-all duration-200 flex items-center gap-3 ${
                      settings.sourceLanguage === lang.code
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-blue-300'
                    }`}
                  >
                    <span className="text-2xl">{lang.flag}</span>
                    <span className="font-medium">{lang.name}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* 目标语言 */}
            <div className="space-y-3">
              <label className="block text-sm font-medium text-gray-700">目标语言（翻译语言）</label>
              <div className="grid grid-cols-2 gap-2">
                {languages.target.map((lang) => (
                  <button
                    key={lang.code}
                    onClick={() => handleLanguageChange('target', lang.code)}
                    className={`p-4 rounded-xl border-2 transition-all duration-200 flex items-center gap-3 ${
                      settings.targetLanguage === lang.code
                        ? 'border-purple-500 bg-purple-50'
                        : 'border-gray-200 hover:border-purple-300'
                    }`}
                  >
                    <span className="text-2xl">{lang.flag}</span>
                    <span className="font-medium">{lang.name}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* 音频输入配置 */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-gray-800 flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-r from-pink-500 to-red-500 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 015 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z" clipRule="evenodd" />
              </svg>
            </div>
              音频输入配置
            </h2>
            <button
              onClick={refreshAudioDevices}
              disabled={!isConnected || loadingDevices}
              className="btn-primary text-white px-4 py-2 rounded-xl text-sm font-medium flex items-center gap-2"
            >
              {loadingDevices ? (
                <>
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="m4 12a8 8 0 718-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 714 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  刷新中...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clipRule="evenodd" />
                  </svg>
                  刷新设备
                </>
              )}
            </button>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="block text-sm font-medium text-gray-700">选择音频输入设备</label>
              {!isConnected && (
                <span className="text-sm text-orange-600 bg-orange-50 px-3 py-1 rounded-lg border border-orange-200">
                  🔌 请连接服务器以获取设备列表
                </span>
              )}
            </div>
            <div className="space-y-2">
              {audioDevices.map((device) => (
                <label
                  key={device.id}
                  className={`flex items-center p-4 rounded-xl border-2 cursor-pointer transition-all duration-200 ${
                    settings.audioDevice === device.id
                      ? 'border-pink-500 bg-pink-50'
                      : 'border-gray-200 hover:border-pink-300'
                  }`}
                >
                  <input
                    type="radio"
                    name="audioDevice"
                    value={device.id}
                    checked={settings.audioDevice === device.id}
                    onChange={(e) => setSettings(prev => ({ ...prev, audioDevice: e.target.value }))}
                    className="sr-only"
                  />
                  <div className="flex items-center gap-4 w-full">
                    <div className={`w-4 h-4 rounded-full border-2 ${
                      settings.audioDevice === device.id
                        ? 'bg-pink-500 border-pink-500'
                        : 'border-gray-300'
                    }`}>
                      {settings.audioDevice === device.id && (
                        <div className="w-2 h-2 bg-white rounded-full m-0.5"></div>
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="font-medium text-gray-800">{device.name}</div>
                      <div className="text-sm text-gray-500 capitalize">{device.type}</div>
                    </div>
                    {device.type === 'bluetooth' && (
                      <div className="text-blue-500">
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 1a1 1 0 011 1v6.5l3.293-3.293a1 1 0 011.414 1.414L12.414 10l3.293 3.293a1 1 0 01-1.414 1.414L11 11.414V18a1 1 0 11-2 0v-6.5L5.707 14.707a1 1 0 01-1.414-1.414L7.586 10 4.293 6.707a1 1 0 011.414-1.414L9 8.586V2a1 1 0 011-1z" clipRule="evenodd" />
                        </svg>
                      </div>
                    )}
                  </div>
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* 会议信息 */}
        <div className="space-y-6">
          <h2 className="text-2xl font-bold text-gray-800 flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-r from-green-500 to-emerald-500 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z" clipRule="evenodd" />
              </svg>
            </div>
            会议信息
          </h2>

          <div className="grid md:grid-cols-2 gap-6">
            {/* 专业领域 */}
            <div className="space-y-3">
              <label className="block text-sm font-medium text-gray-700">专业领域</label>
              <select
                value={settings.meetingDomain}
                onChange={(e) => setSettings(prev => ({ ...prev, meetingDomain: e.target.value }))}
                className="w-full p-4 border-2 border-gray-200 rounded-xl focus:border-green-500 focus:ring-0 transition-colors"
              >
                {meetingDomains.map((domain) => (
                  <option key={domain} value={domain}>{domain}</option>
                ))}
              </select>
            </div>

            {/* 会议名称 */}
            <div className="space-y-3">
              <label className="block text-sm font-medium text-gray-700">会议名称</label>
              <input
                type="text"
                value={settings.meetingName}
                onChange={(e) => setSettings(prev => ({ ...prev, meetingName: e.target.value }))}
                placeholder="请输入会议名称"
                className="w-full p-4 border-2 border-gray-200 rounded-xl focus:border-green-500 focus:ring-0 transition-colors"
              />
            </div>
          </div>
        </div>

        {/* 连接状态 */}
        <div className="flex justify-center">
          <div className={`inline-flex items-center gap-3 px-6 py-3 rounded-full ${
            isConnected ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
          }`}>
            <div className={`w-3 h-3 rounded-full animate-pulse ${
              isConnected ? 'status-connected' : 'status-disconnected'
            }`} />
            <span className={`text-sm font-medium ${
              isConnected ? 'text-green-700' : 'text-red-700'
            }`}>
              {isConnected ? '🟢 服务器已连接' : '🔴 服务器未连接'}
            </span>
          </div>
        </div>

        {/* 开始按钮 */}
        <div className="flex justify-center pt-6">
          <button
            onClick={handleStartInterpreting}
            disabled={!isConnected || !settings.meetingName.trim()}
            className="btn-secondary text-white px-12 py-6 rounded-2xl font-bold text-xl flex items-center gap-4 shadow-xl"
          >
            <div className="w-8 h-8 bg-white bg-opacity-20 rounded-full flex items-center justify-center">
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
              </svg>
            </div>
            开始同声传译
          </button>
        </div>
      </div>
    </div>
  )
}