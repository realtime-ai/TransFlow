# TransFlow 前端详细分析与使用指南

## 技术栈概述

TransFlow 前端采用现代化的技术栈构建：

- **框架**: Next.js 15.4.5 (React 19.1.1)
- **语言**: TypeScript 5.8.3
- **样式**: Tailwind CSS 4.1.11
- **构建工具**: Next.js 内置构建系统
- **通信**: Socket.IO Client 4.8.1

## 项目结构

```
frontend/
├── app/                    # Next.js App Router 目录
│   ├── globals.css        # 全局样式文件
│   ├── layout.tsx         # 根布局组件
│   ├── page.tsx           # 首页
│   ├── record/            # 录制页面
│   │   └── page.tsx
│   ├── settings/          # 设置页面
│   │   └── page.tsx
│   └── transcriptions/    # 转录历史页面
│       └── page.tsx
├── components/            # 可复用组件
│   ├── Navigation.tsx     # 导航栏组件
│   ├── TranscriptionDisplay.tsx  # 转录显示组件
│   └── TranslationInterface.tsx  # 翻译界面组件
├── hooks/                 # 自定义 React Hooks
│   ├── useWebSocket.ts    # WebSocket 连接管理（已废弃）
│   └── useSocketIO.ts     # Socket.IO 连接管理
├── package.json           # 项目配置
├── next.config.js         # Next.js 配置
├── tailwind.config.js     # Tailwind CSS 配置
├── tsconfig.json          # TypeScript 配置
└── postcss.config.js      # PostCSS 配置
```

## 核心功能实现

### 1. Socket.IO 通信机制

`useSocketIO` Hook 提供了可靠的实时双向通信：

```typescript
// 使用示例
const { socket, isConnected, emit, on, off } = useSocketIO(
  'http://localhost:5001'
);

// 功能特性：
- 自动重连（最多5次尝试）
- 连接状态追踪
- 事件驱动通信
- 与后端 Flask-SocketIO 完全兼容
- 错误处理和断线重连
```

主要事件：
- `connect`: 连接成功
- `disconnect`: 断开连接
- `transcription`: 接收转录数据
- `translation`: 接收翻译数据
- `error`: 错误信息

### 2. 音频录制功能

录制页面 (`/record`) 提供完整的录制控制：

- **音频源选择**: 系统音频或麦克风
- **录制控制**: 开始、暂停、停止
- **实时计时**: 显示录制时长
- **Socket.IO 事件**: 
  - `get_audio_sources`: 获取可用音频源
  - `start_recording`: 开始录制
  - `stop_recording`: 停止录制
  - `set_languages`: 设置语言

### 3. 实时转录显示

`TranscriptionDisplay` 组件实现了：

- **实时更新**: Socket.IO 接收转录数据
- **事件监听**: 
  - `transcription`: 处理转录数据
  - `error`: 处理错误信息
- **用户功能**:
  - 清空转录内容
  - 导出为文本文件
  - 自动滚动到最新内容
- **统计信息**: 显示片段数和单词数

### 4. 翻译功能

`TranslationInterface` 组件提供多语言翻译支持。

## 编译说明

### 环境准备

1. **安装 Node.js** (推荐 v23.5.0)
   ```bash
   # 使用 nvm 安装
   nvm install 23.5.0
   nvm use 23.5.0
   ```

2. **进入前端目录**
   ```bash
   cd TransFlow/frontend
   ```

3. **安装依赖**
   ```bash
   npm install
   # 或使用 yarn
   yarn install
   ```

### 开发模式

```bash
# 启动开发服务器（热重载）
npm run dev
# 或
yarn dev

# 默认访问地址: http://localhost:3000
```

### 生产构建

```bash
# 构建优化后的生产版本
npm run build
# 或
yarn build

# 构建产物位于 .next 目录
```

### 生产运行

```bash
# 启动生产服务器
npm run start
# 或
yarn start

# 默认端口: 3000
```

### 代码检查

```bash
# 运行 ESLint 检查
npm run lint
# 或
yarn lint
```

## 使用说明

### 1. 首次使用

1. **启动后端服务器**（必须先启动）
   ```bash
   cd ..
   python server.py
   ```

2. **启动前端开发服务器**
   ```bash
   cd frontend
   npm run dev
   ```

3. **访问应用**
   打开浏览器访问 `http://localhost:3000`

### 2. 功能使用流程




### 3. 配置说明

#### Socket.IO 端点配置

目前 Socket.IO 端点硬编码在组件中：
- 后端服务器: `http://localhost:5001`

如需修改，需要更新以下文件：
- `app/record/page.tsx`
- `components/TranscriptionDisplay.tsx`
- 其他使用 Socket.IO 的组件

#### 环境变量配置

创建 `.env.local` 文件配置环境变量：

```bash
# Socket.IO 配置
NEXT_PUBLIC_SOCKET_URL=http://localhost:5001
```

## 部署说明

### 1. 构建 Docker 镜像

创建 `Dockerfile`:

```dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:18-alpine
WORKDIR /app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./
EXPOSE 3000
CMD ["npm", "start"]
```

### 2. 使用 PM2 部署

```bash
# 安装 PM2
npm install -g pm2

# 构建应用
npm run build

# 使用 PM2 启动
pm2 start npm --name "transflow-frontend" -- start
```

### 3. Nginx 反向代理配置

```nginx
server {
    listen 80;
    server_name transflow.example.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## 故障排查

### 常见问题

1. **Socket.IO 连接失败**
   - 检查后端 Flask-SocketIO 服务器是否运行
   - 确认端口 5001 没有被占用或防火墙阻止
   - 检查 Socket.IO URL 是否正确

2. **录制无声音**
   - 确认已授予浏览器录音权限
   - 检查音频源选择是否正确
   - 验证后端音频捕获服务是否正常

3. **转录不显示**
   - 检查 OpenAI API Key 是否配置
   - 查看浏览器控制台错误信息
   - 确认 WebSocket 连接状态

### 调试技巧

1. **开启 Next.js 调试模式**
   ```bash
   NODE_OPTIONS='--inspect' npm run dev
   ```

2. **查看 Socket.IO 消息**
   - 打开浏览器开发者工具
   - 进入 Network 标签
   - 筛选 WS 类型查看 Socket.IO 通信
   - 在控制台查看 Socket.IO 事件日志

3. **React DevTools**
   - 安装 React DevTools 浏览器扩展
   - 查看组件状态和 props

## 性能优化建议

1. **代码分割**
   - Next.js 自动进行路由级代码分割
   - 对大型组件使用动态导入

2. **图片优化**
   - 使用 Next.js Image 组件
   - 配置适当的图片格式和尺寸

3. **缓存策略**
   - 配置适当的 HTTP 缓存头
   - 使用 Service Worker 缓存静态资源

4. **Socket.IO 优化**
   - 使用房间（rooms）进行消息分组
   - 实现消息批处理
   - 利用 Socket.IO 的内置压缩
   - 控制事件发送频率

## 扩展开发

### 添加新页面

1. 在 `app/` 目录下创建新文件夹
2. 创建 `page.tsx` 文件
3. 导出默认组件

### 添加新组件

1. 在 `components/` 目录创建组件文件
2. 使用 TypeScript 定义 props 接口
3. 导出组件

### 集成新的 API

1. 在 `hooks/` 目录创建新的 Hook
2. 使用 `fetch` 或 `axios` 调用 API
3. 处理加载状态和错误

## Socket.IO 事件列表

### 客户端发送事件
- `connect`: 连接服务器
- `get_audio_sources`: 获取可用音频源
- `start_recording`: 开始录制（带配置参数）
- `stop_recording`: 停止录制
- `set_languages`: 设置语言偏好
- `ping`: 心跳检测

### 客户端接收事件
- `connection_status`: 连接状态更新
- `audio_sources`: 可用音频源列表
- `recording_started`: 录制开始确认
- `recording_stopped`: 录制停止确认
- `transcription`: 实时转录数据
- `translation`: 实时翻译数据
- `audio_data`: 音频数据流（用于可视化）
- `error`: 错误信息
- `pong`: 心跳响应

## 总结

TransFlow 前端是一个现代化的 Next.js 应用，提供了完整的音频录制、实时转录和翻译功能。通过 Socket.IO 实现与后端 Flask-SocketIO 的实时双向通信，使用 Tailwind CSS 构建响应式界面，为用户提供流畅的使用体验。