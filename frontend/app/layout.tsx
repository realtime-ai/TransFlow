import type { Metadata } from 'next'
import Navigation from '@/components/Navigation'
import './globals.css'

export const metadata: Metadata = {
  title: 'TransFlow - Real-time Audio Transcription & Translation',
  description: 'Record, transcribe, and translate audio in real-time',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="min-h-screen text-gray-900 overflow-x-hidden">
        <Navigation />
        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8 min-h-screen">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>
        
        {/* Background decorations */}
        <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-purple-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob"></div>
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-pink-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-2000"></div>
          <div className="absolute top-40 left-40 w-80 h-80 bg-blue-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-4000"></div>
        </div>
      </body>
    </html>
  )
}