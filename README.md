# TransFlow

TransFlow - Mac平台实时字幕以及同声传译产品

## 功能特性

- 录制系统声音和选定应用的声音
- 实时语音转文字 (ASR)
- 实时翻译
- Web 界面控制

## 项目结构

```
TransFlow/
├── frontend/          # Web 前端
│   ├── index.html    # 主页面
│   └── static/       # 静态资源
├── backend/          # 后端服务
│   ├── audio/        # 音频录制模块
│   ├── asr/          # 语音识别模块
│   ├── api/          # API 客户端
│   └── models/       # 数据模型
├── server.py         # Flask 服务器
└── main.py          # 命令行工具

```

## 使用说明

### 前端 (Frontend)

前端使用原生 HTML/CSS/JavaScript 构建，提供 Web 界面来控制音频录制和显示转录结果。

#### 启动前端

前端集成在 Flask 服务器中，启动服务器即可访问：

```bash
python server.py
```

然后在浏览器中访问 `http://localhost:5001`

#### 前端功能

- **音频源选择**: 选择系统音频、麦克风或特定应用
- **实时转录显示**: 显示语音识别结果
- **实时翻译**: 显示翻译结果
- **录制控制**: 开始/停止录制

### 后端 (Backend)

后端基于 Flask + SocketIO 提供实时通信，使用 ScreenCaptureKit 进行音频捕获。

#### 环境要求

- macOS 12.3+
- Python 3.8+
- 系统录音权限

#### 安装依赖

```bash
pip install -r requirements.txt
```

#### 配置

创建 `.env` 文件配置 OpenAI API：

```bash
OPENAI_API_KEY=your_api_key_here
```

#### 启动服务器

```bash
# 使用默认端口 5001
python server.py

# 或指定端口
PORT=8080 python server.py
```

#### API 端点

- **WebSocket 事件**:
  - `connect`: 客户端连接
  - `get_audio_sources`: 获取可用音频源
  - `start_recording`: 开始录制
  - `stop_recording`: 停止录制
  - `set_languages`: 设置语言
  
- **HTTP 端点**:
  - `GET /`: 主页面
  - `GET /test`: 测试端点

### 命令行工具

除了 Web 界面，还可以使用命令行工具：

```bash
# 录制所有系统音频
python main.py

# 录制将保存为 output.wav
```

## 开发说明

### 运行测试

```bash
python -m pytest tests/
```

### 调试模式

在 `config.py` 中设置 `DEBUG = True` 启用调试模式。

## 注意事项

1. 首次运行需要授予系统录音权限
2. 端口 5000 可能被 macOS 系统占用，默认使用 5001
3. 需要配置 OpenAI API Key 才能使用转录和翻译功能

