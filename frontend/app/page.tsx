export default function Home() {
  return (
    <>
      <h1 className="text-4xl font-bold text-center mb-8">Welcome to TransFlow</h1>
      <p className="text-center text-gray-600 mb-12">Real-time Audio Transcription & Translation Platform</p>
      
      <div className="grid md:grid-cols-3 gap-8 max-w-4xl mx-auto">
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h2 className="text-xl font-semibold mb-3">🎤 Record Audio</h2>
          <p className="text-gray-600 mb-4">Capture system audio or microphone input with high quality</p>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h2 className="text-xl font-semibold mb-3">📝 Transcribe</h2>
          <p className="text-gray-600 mb-4">Real-time speech-to-text with multiple language support</p>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h2 className="text-xl font-semibold mb-3">🌐 Translate</h2>
          <p className="text-gray-600 mb-4">Instant translation to multiple target languages</p>
        </div>
      </div>
    </>
  )
}