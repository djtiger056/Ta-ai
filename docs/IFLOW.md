# LFBot - iFlow 交互上下文指南

## 项目概述

LFBot 是一个基于 FastAPI + React 的全功能 AI 聊天机器人系统，提供虚拟伴侣体验。项目采用前后端分离架构，集成多模态 AI 能力。

**核心功能：**
- 🤖 AI 对话聊天（支持 OpenAI、SiliconFlow、DeepSeek、云舞等 LLM 提供商）
- 🔊 TTS 语音合成（启航AI集成）
- 🎨 图像生成（云舞、魔搭社区 ModelScope 集成）
- 👁️ 视觉识别（图片内容识别）
- 🧠 记忆系统（短期/中期/长期三层架构）
- 💬 多平台适配（QQ机器人、控制台、Web界面）
- 🔌 **MCP 扩展**（Model Context Protocol 插件系统）
- ⏰ **主动聊天**（定时/空闲触发主动问候）

**技术栈：**
- **后端：** FastAPI, Uvicorn, SQLAlchemy, ChromaDB, Sentence Transformers
- **前端：** React 19, TypeScript, Ant Design, Vite
- **AI 集成：** OpenAI 兼容 API, 启航AI TTS, 云舞, 魔搭社区 ModelScope
- **扩展系统：** MCP（Model Context Protocol）插件架构

## 项目结构

```
E:\MyProject\11ta\
├── backend/                 # Python 后端代码
│   ├── adapters/           # 平台适配器（QQ、控制台）
│   ├── api/                # API 路由（chat, tts, image_gen, vision, memory, config, mcp, proactive）
│   ├── core/               # 核心业务逻辑（Bot类、主动聊天）
│   ├── providers/          # LLM 提供商实现
│   ├── tts/                # TTS 语音合成系统
│   ├── image_gen/          # 图像生成系统
│   ├── vision/             # 视觉识别系统
│   ├── memory/             # 记忆系统
│   ├── mcp/                # MCP 插件管理系统
│   ├── utils/              # 工具模块（文本分割器等）
│   ├── config.py           # 配置管理
│   └── main.py             # FastAPI 应用入口
├── frontend/               # React 前端代码
│   ├── src/
│   │   ├── pages/          # 页面组件
│   │   │   ├── ChatPage.tsx        # 聊天界面
│   │   │   ├── PersonalityPage.tsx # 角色设定
│   │   │   ├── SettingsPage.tsx    # 系统设置
│   │   │   ├── TTSConfigPage.tsx   # TTS 配置
│   │   │   ├── ImageGenPage.tsx    # 图像生成配置
│   │   │   ├── VisionPage.tsx      # 视觉识别配置
│   │   │   ├── MemoryPage.tsx      # 记忆系统配置
│   │   │   ├── ProactiveChatPage.tsx # 主动聊天配置
│   │   ├── services/       # API 服务层
│   │   └── types/          # TypeScript 类型定义
│   └── package.json
├── data/                   # 数据存储目录
│   ├── chroma/             # 向量数据库
│   ├── lfbot.db            # SQLite 数据库
│   └── mcp_plugins.json    # MCP 插件配置
├── venv/                   # Python 虚拟环境
├── config.yaml             # 主配置文件
├── requirements.txt        # Python 依赖
├── run.py                  # Python 启动脚本（带虚拟环境检测）
├── setup.bat              # Windows 环境设置脚本
├── start.bat              # Windows 一键启动脚本（英文版）
├── oncestart.bat          # Windows 一键启动脚本（中文版）
├── README.md              # 详细项目文档
├── MCP_USAGE.md           # MCP 扩展使用说明
└── tests/                 # 测试文件目录
    ├── test_api.py
    ├── test_backend.py
    ├── test_custom_keywords.py
    ├── test_frontend.py
    ├── test_image_gen.py
    ├── test_memory_integration_simple.py
    ├── test_memory_integration.py
    ├── test_memory_system.py
    ├── test_yunwu_connection.py
    └── test_response.json
```

## 构建与运行

### 环境设置

**使用脚本（Windows）：**
```bash
# 设置虚拟环境和依赖
setup.bat

# 一键启动前后端（英文界面）
start.bat

# 一键启动前后端（中文界面）
oncestart.bat
```

**手动设置：**
```bash
# 1. 创建并激活虚拟环境
python -m venv venv
venv\Scripts\activate

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 进入前端目录安装 Node.js 依赖
cd frontend
npm install
cd ..
```

### 启动服务

**方式一：使用主启动脚本（推荐）**
```bash
python run.py
```
- 启动后端服务（默认端口：8003）
- 检查虚拟环境状态，提供引导

**方式二：分别启动前后端**

启动后端：
```bash
python run.py
# 或
python backend/main.py
```

启动前端（新终端）：
```bash
cd frontend
npm run dev
```

**方式三：使用 Windows 批处理脚本**
```bash
start.bat     # 英文界面启动
oncestart.bat # 中文界面启动
```

### 访问应用

- **前端管理界面：** http://localhost:3000
- **后端 API：** http://localhost:8003
- **API 文档（Swagger UI）：** http://localhost:8003/docs
- **控制台模式：** 运行 `python run.py console`（如果适配器启用）

### 服务端口配置

后端端口在 `config.yaml` 中配置：
```yaml
server:
  port: 8003  # 修改此端口号
```

前端端口在 `frontend/vite.config.ts` 中配置，代理指向后端端口：
```typescript
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://localhost:8003',  # 与此处保持一致
      changeOrigin: true,
    },
  },
}
```

## 配置管理

### 主配置文件
`config.yaml` - 包含所有模块的配置

**关键配置项：**
- `llm`: LLM 提供商设置（API密钥、模型、温度等）
- `tts`: 语音合成配置（启航AI API设置）
- `image_generation`: 图像生成配置（云舞、魔搭社区 API）
- `vision`: 视觉识别配置
- `memory`: 记忆系统配置
- `proactive_chat`: 主动聊天配置（定时/空闲触发）
- `clock`: 时钟插件配置（时区设置）
- `adapters`: 平台适配器设置（QQ、控制台）
- `system_prompt`: 系统角色设定
- `server`: 服务器设置（端口、主机）

**新增配置示例：**
```yaml
# 主动聊天配置
proactive_chat:
  enabled: true
  check_interval_seconds: 60
  daily_window:
    enabled: true
    start: "08:00"
    end: "10:00"
    max_messages_per_window: 2
    randomize: true
  idle_window:
    enabled: true
    min_minutes_after_chat: 60
    max_minutes_after_chat: 120
    cooldown_minutes: 180

# 时钟插件配置
clock:
  timezone: Asia/Shanghai
```

### 配置更新方式

**通过前端界面：**
- 访问 http://localhost:3000 的各配置页面
- 修改后自动保存到 `config.yaml`
- **新增页面：** 主动聊天配置（ProactiveChatPage）

**直接编辑配置文件：**
- 修改 `config.yaml` 文件
- 重启服务生效

**通过 API：**
```bash
# 获取配置
curl http://localhost:8003/api/config

# 更新配置
curl -X PUT http://localhost:8003/api/config -H "Content-Type: application/json" -d '{"section": "llm", "config": {...}}'
```

## MCP 扩展系统

### 功能概览
- 内置 MCP 管理器，支持列出、安装、执行插件
- 自带时钟插件 `clock`，提供 `now` 工具，自动向对话注入当前本地/UTC 时间
- 插件配置持久化在 `data/mcp_plugins.json`，重启后自动加载
- 支持对话自动上下文：Bot 每次聊天会从开启 `auto_context` 的插件收集上下文

### API 接口
- 列出插件：`GET /api/mcp/plugins`
- 安装插件：`POST /api/mcp/plugins/install`
- 执行插件工具：`POST /api/mcp/plugins/{plugin_name}/execute`

### 时钟插件使用
```bash
# 调用内置时钟插件
curl -X POST http://localhost:8003/api/mcp/plugins/clock/execute \
  -H "Content-Type: application/json" \
  -d '{"tool": "now", "params": {"include_timezone": true}}'
```

### 安装自定义插件
1. 确保 pip 包可用，且暴露模块与类（默认类名 `Plugin`）
2. 实现 `list_tools` 和 `run_tool` 方法，可选 `auto_context_block`
3. 调用安装接口注册
4. 重启后端服务加载插件

详细说明请参考 `MCP_USAGE.md` 文件。

## 开发惯例

### Python 后端
- **代码风格：** 使用类型注解，遵循 PEP 8
- **配置管理：** 通过 `backend/config.py` 的 `Config` 类统一管理
- **错误处理：** 使用 Loguru 进行结构化日志记录
- **API 设计：** FastAPI 路由，使用 Pydantic 模型进行数据验证
- **异步处理：** 尽可能使用 `async/await` 提高并发性能

### React 前端
- **代码风格：** TypeScript 严格模式，函数组件 + Hooks
- **UI 组件：** Ant Design 组件库，保持一致性
- **状态管理：** 使用 React 状态和上下文，无外部状态库
- **API 调用：** 通过 `src/services/` 中的服务模块封装
- **路由：** React Router v7

### 模块扩展模式

**添加新的 LLM 提供商：**
1. 在 `backend/providers/` 创建新类，继承 `BaseLLMProvider`
2. 实现 `generate_response` 等方法
3. 在 `providers/__init__.py` 中注册

**添加新的适配器：**
1. 在 `backend/adapters/` 创建适配器类
2. 实现 `start`, `stop`, `send_message` 等方法
3. 在 `main.py` 的 `start_adapters()` 中集成

**添加新的 AI 功能模块：**
1. 创建模块目录（如 `backend/new_module/`）
2. 实现配置类、管理器、提供商接口
3. 添加 API 路由（`backend/api/new_module.py`）
4. 在前端添加配置页面
5. 更新 `config.yaml` 结构

**添加 MCP 插件：**
1. 创建符合 MCP 规范的 Python 包
2. 实现 `list_tools` 和 `run_tool` 方法
3. 通过 `/api/mcp/plugins/install` API 安装
4. 或直接编辑 `data/mcp_plugins.json` 注册

## 测试与调试

### 后端测试
```bash
# 运行所有测试
pytest

# 运行特定测试模块
pytest test_backend.py
pytest test_image_gen.py
pytest test_memory_integration.py
pytest test_api.py
pytest test_yunwu_connection.py

# 带详细输出
pytest -v
```

### 前端开发
```bash
cd frontend

# 开发模式（热重载）
npm run dev

# 构建生产版本
npm run build

# 代码检查
npm run lint

# 预览构建结果
npm run preview
```

### 日志查看

**后端日志：**
- 控制台输出（启动时）
- 日志文件：`backend_output.log`, `backend_error.log`

**前端日志：**
- 浏览器开发者工具控制台
- 构建日志：`frontend/build.log`

### 常见问题排查

1. **端口冲突：**
   - 修改 `config.yaml` 中的 `server.port`（默认8003）
   - 检查是否有其他进程占用端口
   - 确保前端 `vite.config.ts` 中的代理端口与后端一致

2. **API 连接失败：**
   - 检查 `config.yaml` 中的 API 密钥配置
   - 验证网络连接
   - 查看后端错误日志

3. **虚拟环境问题：**
   - 运行 `setup.bat` 重新设置环境
   - 确保已激活虚拟环境：`venv\Scripts\activate`
   - `run.py` 脚本会自动检测并提供引导

4. **前端无法访问后端：**
   - 检查 CORS 设置（已在 `main.py` 中配置）
   - 验证后端服务是否运行（端口8003）
   - 查看浏览器控制台网络请求
   - 确认代理配置正确（`vite.config.ts`）

5. **MCP 插件加载失败：**
   - 检查 `data/mcp_plugins.json` 文件格式
   - 验证插件模块路径和类名
   - 查看后端启动日志中的插件加载信息

## 部署说明

### 生产环境建议
1. **反向代理：** 使用 Nginx 或 Caddy 代理前端和后端
2. **进程管理：** 使用 systemd (Linux) 或 NSSM (Windows) 管理服务
3. **数据库：** 考虑使用 PostgreSQL 替代 SQLite
4. **安全：** 配置 HTTPS，保护 API 密钥
5. **时区设置：** 确保服务器时区正确，或配置 `clock.timezone`

### 环境变量
项目支持通过环境变量覆盖配置：
```bash
# 设置 LLM API 密钥
set LFBOT_LLM_API_KEY=sk-...

# 设置服务器端口
set LFBOT_SERVER_PORT=8003

# 设置时区
set CLOCK_TIMEZONE=Asia/Shanghai
```

## 维护任务

### 定期维护
- 更新 Python 依赖：`pip install -r requirements.txt --upgrade`
- 更新 Node.js 依赖：`cd frontend && npm update`
- 清理日志文件
- 备份数据库（`data/` 目录）
- 检查 MCP 插件更新

### 数据管理
- **数据库位置：** `data/lfbot.db`
- **向量数据库：** `data/chroma/`
- **TF-IDF 数据：** 已移除（仅保留向量存储）
- **MCP 插件配置：** `data/mcp_plugins.json`

### 重置系统
1. 停止所有服务
2. 删除 `data/` 目录（会清除所有记忆、数据库和插件配置）
3. 重新启动服务

## 快速命令参考

```bash
# 设置环境
setup.bat

# 启动所有服务（英文界面）
start.bat

# 启动所有服务（中文界面）
oncestart.bat

# 仅启动后端
python run.py

# 进入前端目录
cd frontend

# 前端开发
npm run dev

# 运行测试
pytest

# 激活虚拟环境
venv\Scripts\activate

# 停用虚拟环境
deactivate
```

## 注意事项

1. **配置文件安全：** `config.yaml` 包含 API 密钥，不应提交到版本控制
2. **虚拟环境：** 确保在虚拟环境中运行 Python 代码
3. **端口配置：** 前后端端口需对应，默认为 3000（前端）和 8003（后端）
4. **依赖版本：** 保持 `requirements.txt` 和 `package.json` 中的依赖版本一致
5. **Windows 路径：** 项目使用 Windows 路径分隔符，如需在 Linux/macOS 运行需调整路径处理
6. **时区设置：** 云端部署时注意时区配置，避免时钟插件时间不准
7. **MCP 插件：** 自定义插件需确保模块路径正确，重启后生效

---

**最后更新：** 2025年12月24日  
**项目状态：** 活跃开发中  
**维护者：** 项目开发者

**相关文档：**
- [README.md](README.md) - 详细功能说明
- [MCP_USAGE.md](MCP_USAGE.md) - MCP扩展使用说明
- [config.yaml](config.yaml) - 配置文件参考
