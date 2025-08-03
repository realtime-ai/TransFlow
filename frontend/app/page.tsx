import Link from 'next/link'

export default function Home() {
  return (
    <div className="animate-fade-in">
      {/* Hero Section */}
      <div className="text-center mb-20">
        <div className="mb-12">
          <h1 className="text-7xl font-bold bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent mb-6">
            TransFlow
          </h1>
          <h2 className="text-3xl font-semibold text-gray-700 mb-6">
            同声传译平台
          </h2>
          <div className="w-32 h-1 bg-gradient-to-r from-purple-500 to-pink-500 mx-auto rounded-full"></div>
        </div>
        <p className="text-2xl text-gray-700 mb-8 max-w-3xl mx-auto leading-relaxed">
          体验专业的AI驱动同声传译服务
        </p>
        <p className="text-lg text-gray-600 max-w-4xl mx-auto">
          实时音频转写与翻译，支持中英文双语对照显示，
          为会议、采访和多语言交流提供专业解决方案。
        </p>
      </div>

      {/* Main Action Button */}
      <div className="text-center mb-20">
        <Link href="/settings" className="group inline-block">
          <button className="btn-secondary text-white px-16 py-8 rounded-3xl font-bold text-2xl flex items-center gap-4 shadow-xl mx-auto">
            <div className="w-12 h-12 bg-white bg-opacity-20 rounded-full flex items-center justify-center">
              <svg className="w-7 h-7" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M7 2a1 1 0 011 1v1h3a1 1 0 110 2H9.578a18.87 18.87 0 01-1.724 4.78c.29.354.596.696.914 1.026a1 1 0 11-1.44 1.389c-.188-.196-.373-.396-.554-.6a19.098 19.098 0 01-3.107 3.567 1 1 0 01-1.334-1.49 17.087 17.087 0 003.13-3.733 18.992 18.992 0 01-1.487-2.494 1 1 0 111.79-.89c.234.47.489.928.764 1.372.417-.934.752-1.913.997-2.927H3a1 1 0 110-2h3V3a1 1 0 011-1z" clipRule="evenodd" />
              </svg>
            </div>
            开始同声传译
          </button>
        </Link>
        <p className="text-gray-500 mt-6 text-lg">
          点击开始配置语言设置并启动同声传译服务
        </p>
      </div>

      {/* Feature Highlights */}
      <div className="max-w-6xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* 实时转写 */}
          <div className="group card-gradient p-8 rounded-2xl hover:scale-105 transition-all duration-300 border border-white border-opacity-20">
            <div className="flex items-center justify-center w-16 h-16 bg-gradient-to-r from-blue-500 to-cyan-500 rounded-2xl mb-6 mx-auto group-hover:scale-110 transition-transform duration-300">
              <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M7 4a3 3 0 616 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 715 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z" clipRule="evenodd" />
              </svg>
            </div>
            <h3 className="text-2xl font-bold text-gray-800 mb-4 text-center">实时转写</h3>
            <p className="text-gray-600 text-center leading-relaxed">
              将说话内容实时转换为文字，支持多语言识别和高准确度输出
            </p>
          </div>

          {/* 双语对照 */}
          <div className="group card-gradient p-8 rounded-2xl hover:scale-105 transition-all duration-300 border border-white border-opacity-20">
            <div className="flex items-center justify-center w-16 h-16 bg-gradient-to-r from-purple-500 to-pink-500 rounded-2xl mb-6 mx-auto group-hover:scale-110 transition-transform duration-300">
              <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M7 2a1 1 0 011 1v1h3a1 1 0 110 2H9.578a18.87 18.87 0 01-1.724 4.78c.29.354.596.696.914 1.026a1 1 0 11-1.44 1.389c-.188-.196-.373-.396-.554-.6a19.098 19.098 0 01-3.107 3.567 1 1 0 01-1.334-1.49 17.087 17.087 0 003.13-3.733 18.992 18.992 0 01-1.487-2.494 1 1 0 111.79-.89c.234.47.489.928.764 1.372.417-.934.752-1.913.997-2.927H3a1 1 0 110-2h3V3a1 1 0 011-1z" clipRule="evenodd" />
              </svg>
            </div>
            <h3 className="text-2xl font-bold text-gray-800 mb-4 text-center">双语对照</h3>
            <p className="text-gray-600 text-center leading-relaxed">
              实时显示源语言和翻译结果，支持中英文同步对照查看
            </p>
          </div>

          {/* 智能翻译 */}
          <div className="group card-gradient p-8 rounded-2xl hover:scale-105 transition-all duration-300 border border-white border-opacity-20">
            <div className="flex items-center justify-center w-16 h-16 bg-gradient-to-r from-green-500 to-emerald-500 rounded-2xl mb-6 mx-auto group-hover:scale-110 transition-transform duration-300">
              <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
              </svg>
            </div>
            <h3 className="text-2xl font-bold text-gray-800 mb-4 text-center">智能翻译</h3>
            <p className="text-gray-600 text-center leading-relaxed">
              基于AI的专业级翻译引擎，支持上下文理解和精准语义转换
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}