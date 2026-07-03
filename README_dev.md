# LFBot - AI 聊天陪伴机器人

一个基于 FastAPI + React 的企业级 AI 聊天机器人系统，集成语音合成、图像生成、视觉识别、三层记忆架构、多用户管理等功能，提供完整的虚拟伴侣体验。支持多平台部署（QQ、控制台、Web），可扩展的插件架构。

## ✨ 核心特性

### 🤖 智能对话
- **多 LLM 支持** - OpenAI、SiliconFlow、DeepSeek、云舞等主流提供商
- **流式响应** - WebSocket 实时对话流，低延迟体验
- **上下文管理** - 智能对话历史管理，支持长对话

### 🎙️ 多模态交互
- **TTS 语音合成** - 启航AI/Qwen TTS，支持文本清洗和智能分段
- **ASR 语音识别** - 自动识别语音消息，转文本后处理
- **图像生成** - ModelScope/云舞集成，支持提示词增强
- **视觉识别** - 智能图片内容识别，自动融入对话语境

### 🧠 三层记忆架构
- **短期记忆** - 最近 50 轮对话历史
- **中期记忆** - 自动对话摘要（10 条摘要）
- **长期记忆** - 向量检索（ChromaDB + 本地/外部嵌入模型），支持 1000+ 条记忆

### 🎨 内容增强
- **提示词增强器** - 基于本地词库自动补充图像生成细节
- **表情包系统** - 根据语境自动发送表情包
- **文本分割器** - 智能分割长文本，提升对话自然度

### ⏰ 主动交互
- **定时问候** - 可配置时间窗口主动发送消息
- **空闲检测** - 长时间未聊天后主动问候
- **提醒系统** - 智能提醒检测和调度

### 🔌 扩展性
- **MCP 插件系统** - 插件化架构，支持自定义功能扩展
- **内置插件** - 时钟、日常作息、提醒管理
- **多平台适配** - QQ（WebSocket）、控制台、Web 管理界面

### 👥 多用户管理
- **用户认证** - JWT 认证，支持注册/登录
- **个性化配置** - 每个用户独立配置（系统提示词、LLM 参数、TTS 语音等）
- **管理员 API** - 统一管理多用户配置
- **访问控制** - 白名单/黑名单支持

### 🎛️ 可视化管理
- **Web 管理界面** - 基于 React + Ant Design 的现代化界面
- **实时配置** - 所有功能模块可视化配置
- **响应式设计** - 支持桌面和移动端访问

## 🛠️ 技术栈

### 后端技术
| 技术 | 版本 | 用途 |
|------|------|------|
| FastAPI | ≥0.109.1 | 高性能异步 Web 框架 |
| SQLAlchemy | ≥2.0.0 | 异步 ORM |
| aiosqlite | ≥0.20.0 | 异步 SQLite 支持 |
| WebSocket | ≥12.0 | 实时双向通信 |
| Pydantic | ≥2.5.3 | 数据验证和配置管理 |
| aiohttp | ≥3.10.2 | 异步 HTTP 客户端 |
| Loguru | ≥0.7.2 | 结构化日志系统 |
| ChromaDB | ≥0.4.22 | 向量数据库 |
| Sentence Transformers | ≥2.3.1 | 文本嵌入模型 |
| jieba | ≥0.42.1 | 中文分词 |
| PyJWT | ≥2.8.0 | JWT 认证 |
| passlib | ≥1.7.4 | 密码哈希 |

### 前端技术
| 技术 | 版本 | 用途 |
|------|------|------|
| React | 19 | 现代化 UI 框架 |
| TypeScript | 5.9 | 类型安全开发 |
| Ant Design | 6 | 企业级 UI 组件库 |
| Vite | 7 | 快速构建工具 |
| React Router | 7 | 路由管理 |
| Axios | - | HTTP 客户端 |
| React Markdown | - | Markdown 渲染 |
| React Syntax Highlighter | - | 代码高亮 |

### AI 服务集成
- **LLM** - OpenAI、SiliconFlow、DeepSeek（OpenAI 兼容 API）
- **TTS** - 启航AI、Qwen TTS
- **ASR** - SiliconFlow ASR（TeleAI/TeleSpeechASR）
- **图像生成** - ModelScope、云舞
- **视觉识别** - ModelScope（Qwen3-VL-30B）

## 📁 项目架构

```
LFBot/
├── backend/                    # Python 后端
│   ├── adapters/              # 平台适配器
│   │   ├── console.py         # 控制台适配器
│   │   └── qq.py              # QQ 机器人适配器
│   ├── api/                   # REST API 路由（18+ 模块）
│   │   ├── chat.py            # 聊天 API
│   │   ├── tts.py             # TTS 语音合成
│   │   ├── asr.py             # ASR 语音识别
│   │   ├── image_gen.py       # 图像生成
│   │   ├── vision.py          # 视觉识别
│   │   ├── memory.py          # 记忆系统
│   │   ├── prompt_enhancer.py # 提示词增强
│   │   ├── emotes.py          # 表情包系统
│   │   ├── proactive.py       # 主动聊天
│   │   ├── mcp.py             # MCP 插件
│   │   ├── reminder.py        # 提醒系统
│   │   ├── user_auth.py       # 用户认证
│   │   ├── user_config.py     # 用户配置
│   │   └── admin_users.py     # 管理员 API
│   ├── core/                  # 核心业务逻辑
│   │   ├── bot.py             # Bot 核心类（55KB）
│   │   ├── proactive.py       # 主动聊天调度
│   │   └── gen_img_parser.py  # 图像生成解析
│   ├── providers/             # LLM 提供商
│   │   ├── openai_provider.py # OpenAI 兼容提供商
│   │   └── base.py            # 提供商基类
│   ├── tts/                   # TTS 系统
│   │   ├── manager.py         # TTS 管理器
│   │   ├── providers/         # TTS 提供商
│   │   └── text_cleaner.py    # 文本清洗
│   ├── asr/                   # ASR 系统
│   │   ├── manager.py         # ASR 管理器
│   │   └── providers/         # ASR 提供商
│   ├── image_gen/             # 图像生成系统
│   │   ├── manager.py         # 图像生成管理器
│   │   └── providers/         # 图像生成提供商
│   ├── vision/                # 视觉识别系统
│   │   ├── manager.py         # 视觉识别管理器
│   │   └── providers/         # 视觉识别提供商
│   ├── memory/                # 记忆系统
│   │   ├── manager.py         # 向量记忆管理器
│   │   ├── vector_store.py    # ChromaDB 向量存储
│   │   ├── summarizer.py      # 对话摘要
│   │   ├── reminder_scheduler.py # 提醒调度
│   │   └── reminder_detector.py  # 提醒检测
│   ├── prompt_enhancer/       # 提示词增强器
│   │   ├── enhancer.py        # 增强器核心
│   │   └── word_banks/        # 词库文件
│   ├── emote/                 # 表情包系统
│   │   └── manager.py         # 表情包管理器
│   ├── mcp/                   # MCP 插件系统
│   │   ├── manager.py         # 插件管理器
│   │   ├── clock.py           # 时钟插件
│   │   └── daily_habits.py    # 日常作息插件
│   ├── user/                  # 用户管理
│   │   ├── manager.py         # 用户管理器
│   │   ├── auth.py            # 认证逻辑
│   │   └── models.py          # 用户模型
│   ├── utils/                 # 工具模块
│   │   ├── text_splitter.py   # 文本分割器
│   │   ├── llm_payload_logger.py # LLM 请求审计
│   │   └── config_merger.py   # 配置合并
│   ├── config.py              # 配置管理
│   └── main.py                # FastAPI 应用入口
├── frontend/                  # React 前端
│   ├── src/
│   │   ├── pages/             # 页面组件（16+ 页面）
│   │   │   ├── ChatPage.tsx           # 聊天界面
│   │   │   ├── SettingsPage.tsx       # 系统设置
│   │   │   ├── PersonalityPage.tsx    # 角色设定
│   │   │   ├── TTSConfigPage.tsx      # TTS 配置
│   │   │   ├── ASRConfigPage.tsx      # ASR 配置
│   │   │   ├── ImageGenPage.tsx       # 图像生成配置
│   │   │   ├── VisionPage.tsx         # 视觉识别配置
│   │   │   ├── MemoryPage.tsx         # 记忆系统配置
│   │   │   ├── PromptEnhancerPage.tsx # 提示词增强器
│   │   │   ├── EmotePage.tsx          # 表情包配置
│   │   │   ├── ProactiveChatPage.tsx  # 主动聊天配置
│   │   │   ├── DailyHabitsPage.tsx    # 日常作息配置
│   │   │   ├── ReminderPage.tsx       # 提醒管理
│   │   │   ├── AdminUsersPage.tsx     # 多用户管理
│   │   │   └── LoginPage.tsx          # 登录界面
│   │   ├── services/          # API 服务层
│   │   └── types/             # TypeScript 类型定义
│   └── package.json           # 前端依赖
├── data/                      # 数据存储
│   ├── lfbot.db               # SQLite 数据库
│   ├── users.db               # 用户数据库
│   ├── chroma/                # ChromaDB 向量数据库
│   ├── emotes/                # 表情包存储
│   ├── tts/                   # TTS 音频缓存
│   ├── llm_payloads/          # LLM 请求日志
│   ├── custom_prompt_words.yaml # 自定义词库
│   ├── daily_habits.json      # 日常作息配置
│   └── mcp_plugins.json       # MCP 插件配置
├── config.yaml                # 主配置文件
├── requirements.txt           # Python 依赖
├── run.py                     # 启动脚本
└── README.md                  # 项目文档
```

### 架构设计模式

**分层架构**
- **表现层** - React 前端 + Ant Design
- **API 层** - FastAPI REST + WebSocket
- **业务逻辑层** - Bot 核心 + 管理器
- **数据访问层** - SQLAlchemy ORM + ChromaDB
- **集成层** - 提供商适配器

**核心设计模式**
- **适配器模式** - 平台适配器（Console、QQ）、提供商适配器（LLM、TTS、ASR）
- **管理器模式** - 各子系统集中管理（TTS、ASR、Memory、Image Gen、Vision、Emote、MCP）
- **插件架构** - MCP 插件系统，支持第三方扩展
- **多用户配置** - 用户配置覆盖全局配置，支持配置合并
- **三层记忆** - 短期（50 轮）+ 中期（10 摘要）+ 长期（1000+ 向量）

## 🚀 快速开始

### 环境要求
- Python 3.9+
- Node.js 16+
- Windows/Linux/macOS

### 安装步骤

**1. 克隆项目**
```bash
git clone <repository-url>
cd LFBot
```

**2. 后端环境配置**
```bash
# 创建虚拟环境（Windows）
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

**3. 前端环境配置**
```bash
cd frontend
npm install
```

**4. 配置文件**

首次启动时，仓库会先从 [config.example.yaml](config.example.yaml) 复制生成 `config.yaml`。
然后编辑生成的 [config.yaml](config.yaml)，配置必要的 API 密钥：

```yaml
# LLM 配置
llm:
  provider: siliconflow
  api_base: https://api.siliconflow.cn/v1
  api_key: your-api-key-here
  model: deepseek-ai/DeepSeek-V3.2

# TTS 配置（可选）
tts:
  enabled: true
  provider: qihang
  qihang:
    api_key: your-tts-api-key

# 管理员配置
admin:
  api_key: your-admin-key-here
```

**5. 启动服务**

```bash
# 方式一：使用启动脚本（推荐）
python run.py

# 方式二：分别启动
# 终端 1 - 启动后端
python backend/main.py

# 终端 2 - 启动前端
cd frontend
npm run dev
```

### 访问应用

- **前端界面** - http://localhost:3000
- **后端 API** - http://localhost:8003
- **API 文档** - http://localhost:8003/docs
- **控制台模式** - `python run.py console`

## 👥 多用户管理

### 用户认证
```bash
# 注册用户
POST /api/auth/register

# 登录获取 Token
POST /api/auth/login

# 使用 Token
Authorization: Bearer <access_token>
```

### 个人配置
每个用户可独立配置：
- 系统提示词和角色设定
- LLM 参数（模型、温度等）
- TTS 语音角色
- 图像生成偏好
- 记忆系统设置

**API 端点**
- `GET /api/user/config` - 获取个人配置
- `PUT /api/user/config` - 更新个人配置
- `DELETE /api/user/config?config_type=tts` - 重置配置

**配置合并规则**：用户配置 > 全局配置

### 管理员 API

配置管理员密钥（[config.yaml](config.yaml)）：
```yaml
admin:
  api_key: "your-strong-random-key"
```

**管理员端点**（需要 `X-Admin-Token` 请求头）
- `GET /api/admin/users` - 列出所有用户
- `GET /api/admin/users/{qq_user_id}/config` - 获取用户配置
- `PUT /api/admin/users/{qq_user_id}/config` - 更新用户配置

## ⚙️ 核心配置

### LLM 配置
```yaml
llm:
  provider: siliconflow  # openai, deepseek, siliconflow, yunwu, qwen
  api_base: https://api.siliconflow.cn/v1
  api_key: sk-your-key
  model: deepseek-ai/DeepSeek-V3.2
  temperature: 0.7
  max_tokens: 2000
```

### TTS 语音合成
```yaml
tts:
  enabled: true
  provider: qihang  # qihang, qwen
  qihang:
    api_key: sk-your-key
    voice: 柔情萝莉
  segment_config:
    enabled: true
    max_segments: 1
    delay_range: [0.5, 2.0]
```

### ASR 语音识别
```yaml
asr:
  enabled: true
  provider: siliconflow
  siliconflow:
    api_key: sk-your-key
    model: TeleAI/TeleSpeechASR
  auto_send_to_llm: true
```

### 图像生成
```yaml
image_generation:
  enabled: true
  provider: modelscope
  modelscope:
    api_key: ms-your-key
    model: Tongyi-MAI/Z-Image-Turbo
  trigger_keywords:
    - 生成图片
    - 生图
    - 画
```

### 视觉识别
```yaml
vision:
  enabled: true
  provider: modelscope
  modelscope:
    api_key: ms-your-key
    model: Qwen/Qwen3-VL-30B-A3B-Instruct
  auto_send_to_llm: true
```

### 记忆系统
```yaml
memory:
  short_term_enabled: true
  mid_term_enabled: true
  long_term_enabled: true
  short_term_max_rounds: 50
  summary_interval: 10
  max_summaries: 10
  rag_enabled: true
  rag_top_k: 3
```

### QQ 机器人
```yaml
adapters:
  qq:
    enabled: true
    ws_host: 127.0.0.1
    ws_port: 3001
    need_at: true
    access_control:
      enabled: true
      mode: whitelist  # whitelist, blacklist
      whitelist: ['user_id_1', 'user_id_2']
```

完整配置请参考 [config.yaml](config.yaml)

## 📖 功能使用指南

### 图像生成

**触发方式**
在聊天中发送包含关键词的消息：
- `画一只可爱的小猫`
- `生成图片：美丽的风景`
- `生图，星空夜景`
- `看看穿搭，休闲风格`

**提示词增强**
系统会自动基于本地词库补充细节：
- 发型、面部特征、服装
- 姿势、表情、场景
- 光照、质量提升

### 语音识别（ASR）

**使用方式**
- **私聊** - 直接发送语音消息
- **群聊** - @机器人并发送语音消息

系统自动识别语音内容，转文本后由 LLM 处理并回复。

### 视觉识别

**使用方式**
发送图片消息，系统自动：
1. 识别图片内容
2. 生成描述文本
3. 结合对话语境回复

### 表情包系统

**配置步骤**
1. 在 `data/emotes/` 创建分类文件夹
2. 放入表情包图片（png、jpg、gif、webp）
3. 在 [config.yaml](config.yaml) 配置分类和关键词

系统根据对话内容自动匹配关键词发送表情包。

### 主动聊天

**工作模式**
- **定时窗口** - 在指定时间段主动问候
- **空闲窗口** - 长时间未聊天后主动问候

**配置建议**
- 合理设置时间段，避免打扰
- 调整冷却时间，控制频率
- 配合记忆系统，发送个性化问候

### MCP 插件系统

**内置插件**
- **clock** - 提供当前时间信息
- **daily_habits** - 根据作息表返回当前状态

**自定义插件**
```python
from backend.mcp.manager import MCPPlugin

class MyPlugin(MCPPlugin):
    name = "my_plugin"

    def list_tools(self):
        return [{"name": "my_tool", "description": "..."}]

    def run_tool(self, tool_name, params):
        return {"result": "..."}
```

安装插件：
```bash
curl -X POST http://localhost:8003/api/mcp/plugins/install \
  -H "Content-Type: application/json" \
  -d '{"name": "my_plugin", "module": "my_plugin.module"}'
```

## 🔌 API 接口

### WebSocket
- `ws://localhost:8003/ws/chat` - 实时聊天流式接口

### 核心 API
| 功能 | 端点 | 说明 |
|------|------|------|
| 聊天 | `POST /api/chat` | 非流式聊天 |
| TTS | `POST /api/tts/generate` | 语音合成 |
| ASR | `POST /api/asr/transcribe` | 语音识别 |
| 图像生成 | `POST /api/image-gen/generate` | 生成图片 |
| 视觉识别 | `POST /api/vision/recognize` | 识别图片 |
| 记忆系统 | `POST /api/memory/search` | 记忆检索 |
| 提示词增强 | `POST /api/prompt-enhancer/enhance` | 增强提示词 |
| 表情包 | `POST /api/emotes/test` | 测试表情包选择 |
| 主动聊天 | `POST /api/proactive/trigger` | 手动触发主动聊天 |
| MCP 插件 | `POST /api/mcp/plugins/{name}/execute` | 执行插件工具 |

### 配置 API
所有功能模块都提供配置 API：
- `GET /api/{module}/config` - 获取配置
- `POST /api/{module}/config` - 更新配置
- `POST /api/{module}/test-connection` - 测试连接

完整 API 文档：http://localhost:8003/docs

## 🔧 开发指南

### 添加新的 LLM 提供商
1. 在 `backend/providers/` 创建提供商类
2. 继承 `BaseLLMProvider` 接口
3. 在 `providers/__init__.py` 注册

### 添加新的平台适配器
1. 在 `backend/adapters/` 创建适配器类
2. 实现适配器接口
3. 在 `main.py` 注册

### 开发自定义 MCP 插件
```python
from backend.mcp.manager import MCPPlugin
from typing import Dict, List, Any

class MyPlugin(MCPPlugin):
    name = "my_plugin"
    description = "我的自定义插件"

    def list_tools(self) -> List[Dict[str, Any]]:
        return [{
            "name": "my_tool",
            "description": "我的工具",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {"type": "string"}
                },
                "required": ["param1"]
            }
        }]

    def run_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "my_tool":
            return {"result": f"处理结果: {params['param1']}"}
        raise ValueError(f"未知工具: {tool_name}")

    def auto_context_block(self) -> str:
        return "当前插件状态：正常"
```

## 🐛 故障排除

### 常见问题

**端口占用**
- 检查 8003（后端）和 3000（前端）端口
- 修改 [config.yaml](config.yaml) 中的 `server.port`

**API 连接失败**
- 检查网络连接
- 验证 API 密钥是否正确
- 查看后端日志获取详细错误

**TTS 不工作**
- 检查 `tts.enabled: true`
- 验证 API 密钥
- 查看浏览器控制台和后台日志

**前端无法访问后端**
- 确保后端服务正在运行
- 检查 CORS 设置
- 查看浏览器开发者工具

### LLM 请求审计
开启环境变量 `LLM_TRACE=1` 记录所有 LLM 请求：
```bash
# Windows
set LLM_TRACE=1
python run.py

# Linux/macOS
export LLM_TRACE=1
python run.py
```

日志位置：`backend/data/llm_payloads/YYYYMMDD.log`

## 📊 项目统计

- **代码规模** - 15,000+ 行代码
- **后端模块** - 85+ Python 文件
- **前端页面** - 16+ React 页面
- **API 端点** - 50+ REST 端点 + WebSocket
- **配置选项** - 100+ 可配置参数
- **支持平台** - Console、QQ（可扩展）
- **AI 提供商** - 5+ 主流提供商

## 📚 相关文档

- [IFLOW.md](IFLOW.md) - 项目详细交互上下文指南
- [MCP_USAGE.md](MCP_USAGE.md) - MCP 扩展使用说明
- [ASR功能说明.md](ASR功能说明.md) - ASR 语音识别详细说明
- [记忆功能优化.txt](记忆功能优化.txt) - 记忆系统优化说明

## 🔗 快速链接

**前端界面**
- [聊天界面](http://localhost:3000)
- [系统设置](http://localhost:3000/settings)
- [角色设定](http://localhost:3000/personality)
- [TTS 配置](http://localhost:3000/tts)
- [ASR 配置](http://localhost:3000/asr)
- [图像生成](http://localhost:3000/image-gen)
- [视觉识别](http://localhost:3000/vision)
- [记忆系统](http://localhost:3000/memory)
- [提示词增强](http://localhost:3000/prompt-enhancer)
- [表情包配置](http://localhost:3000/emotes)
- [主动聊天](http://localhost:3000/proactive)
- [日常作息](http://localhost:3000/daily-habits)
- [提醒管理](http://localhost:3000/reminders)
- [多用户管理](http://localhost:3000/admin-users)

**后端服务**
- [API 文档](http://localhost:8003/docs)
- [配置文件](config.yaml)

## 📄 许可证

MIT License

---

**LFBot** - 企业级 AI 聊天陪伴机器人系统
