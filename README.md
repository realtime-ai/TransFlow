# TransFlow

TransFlow - macOS 平台实时语音转写与同声传译系统

## 功能特性

- 🎙️ **音频捕获**: 支持系统音频、麦克风、特定应用音频捕获
- 🗣️ **实时语音识别**: 支持多种 ASR 引擎
  - OpenAI Realtime API（多语言）
  - 阿里云 Paraformer（中文优化）
- 🌍 **实时翻译**: 支持多种翻译引擎
  - 阿里云 qwen-mt-turbo（高质量翻译）
  - OpenAI GPT-4o-mini（备选）
- 🖥️ **Web 界面**: 现代化的 Next.js + TypeScript 前端
- 🔄 **智能引擎选择**: 根据语言自动选择最优的 ASR 和翻译引擎

## 项目结构

```
TransFlow/
├── frontend/              # Next.js 前端应用
│   ├── app/              # 应用路由和页面
│   │   ├── page.tsx      # 主页
│   │   ├── record/       # 录制页面
│   │   └── settings/     # 设置页面
│   ├── components/       # React 组件
│   ├── hooks/           # 自定义 Hooks
│   └── package.json     # 前端依赖
├── backend/             # Python 后端服务
│   ├── audio/          # 音频处理模块
│   │   ├── capture.py  # 音频捕获（ScreenCaptureKit）
│   │   └── resampler.py # 音频重采样
│   ├── asr/            # 语音识别模块
│   │   ├── base.py     # ASR 基类
│   │   ├── openai_realtime.py    # OpenAI Realtime ASR
│   │   └── paraformer_realtime.py # Paraformer ASR
│   ├── api/            # API 客户端
│   │   └── translation_client.py  # 翻译客户端
│   └── models/         # 数据模型
│       └── translation_service.py # 翻译服务
├── server.py           # Flask-SocketIO 服务器
├── config.py          # 配置文件
├── requirements.txt   # Python 依赖
└── .env              # 环境变量配置
```

## 环境要求

- macOS 12.3 或更高版本
- Python 3.8 或更高版本
- Node.js 16 或更高版本（前端开发）
- 系统录音权限

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/TransFlow.git
cd TransFlow
```

### 2. 安装后端依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # macOS/Linux

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置 API Keys

创建 `.env` 文件并配置必要的 API Keys：

```bash
# OpenAI API（用于多语言 ASR 和备选翻译）
OPENAI_API_KEY=your_openai_api_key_here

# 阿里云 DashScope API（用于 Paraformer ASR 和 qwen-mt-turbo 翻译）
DASHSCOPE_API_KEY=your_dashscope_api_key_here
```

> 注意：至少需要配置一个 API Key。推荐配置 DASHSCOPE_API_KEY 以获得更好的中文支持。

### 4. 启动后端服务

```bash
python server.py
```

服务器将在 `http://localhost:5001` 启动。

### 5. 安装并启动前端（开发模式）

在新的终端窗口中：

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器将在 `http://localhost:3000` 启动。

## 使用指南

### Web 界面功能

1. **主页** (`/`)
   - 快速开始录制
   - 查看系统状态

2. **录制页面** (`/record`)
   - 🎙️ 开始/停止录制
   - 📝 实时查看转写结果
   - 🌍 实时查看翻译结果
   - 💾 导出转写记录
   - 🔍 支持双语/单语显示模式

3. **设置页面** (`/settings`)
   - 🎤 选择音频输入设备
   - 🌐 设置源语言和目标语言
   - 🔧 配置系统参数

### API 接口

#### WebSocket 事件

**客户端发送：**
- `start_recording`: 开始录制
  ```javascript
  {
    audioDevice: 'default',  // 音频设备 ID
    captureSystemAudio: true,  // 是否捕获系统音频
    sourceLanguage: 'zh',  // 源语言
    targetLanguage: 'en'   // 目标语言
  }
  ```
- `stop_recording`: 停止录制
- `get_audio_devices`: 获取音频设备列表
- `set_languages`: 设置语言

**服务器发送：**
- `transcription`: 转写结果
  ```javascript
  {
    text: '转写文本',
    language: 'zh',
    timestamp: 1234567890
  }
  ```
- `translation`: 翻译结果
  ```javascript
  {
    source_text: '源文本',
    translation: '翻译文本',
    source_language: 'zh',
    target_language: 'en',
    timestamp: 1234567890
  }
  ```

### 智能引擎选择

系统会根据设置的源语言智能选择最优的 ASR 和翻译引擎：

- **中文优先**：
  - ASR: Paraformer（如果配置了 DASHSCOPE_API_KEY）
  - 翻译: qwen-mt-turbo

- **其他语言或回退**：
  - ASR: OpenAI Realtime
  - 翻译: OpenAI GPT-4o-mini

## 高级配置

### 音频参数

在 `config.py` 中可以配置：

```python
AUDIO_SAMPLE_RATE = 16000  # 采样率（Hz）
AUDIO_CHANNELS = 1         # 声道数（单声道）
AUDIO_BIT_DEPTH = 16      # 位深度
```

### 调试模式

启用调试模式以查看详细日志：

```bash
# 在 .env 中设置
DEBUG=True

# 或通过环境变量
DEBUG=True python server.py
```

### 音频调试

系统支持将输入音频保存为 WAV 文件用于调试：

```python
# ASR 客户端会在 debug_audio/ 目录保存音频
# 文件名格式：paraformer_input_YYYYMMDD_HHMMSS.wav
```

## 开发指南

### 项目架构

- **前端**: Next.js + TypeScript + Socket.IO Client
- **后端**: Flask + Flask-SocketIO + PyObjC
- **音频处理**: ScreenCaptureKit + AVFoundation
- **实时通信**: WebSocket (Socket.IO)

### 添加新的 ASR 引擎

1. 在 `backend/asr/` 创建新文件
2. 继承 `StreamingASRBase` 基类
3. 实现必要的方法
4. 在 `backend/asr/__init__.py` 注册

### 运行测试

```bash
# 运行所有测试
python -m pytest tests/

# 测试特定模块
python test_server_asr_selection.py
python test_qwen_translation.py
```

## 故障排查

### 常见问题

1. **无法获取系统音频**
   - 确保在系统设置中授予录音权限
   - 重启应用后再试

2. **前端无法连接后端**
   - 检查后端是否正在运行
   - 确认端口 5001 未被占用
   - 检查防火墙设置

3. **无转写/翻译结果**
   - 检查 API Keys 是否正确配置
   - 查看后端日志中的错误信息
   - 确认音频输入设备正常工作

4. **音频质量问题**
   - 检查音频输入设备设置
   - 调整音频采样参数
   - 查看 debug_audio/ 目录中的录制音频

## 贡献指南

欢迎提交 Issue 和 Pull Request！

## 许可证

[MIT License](LICENSE)

