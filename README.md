# Ta - AI 伴侣聊天系统

一个基于 FastAPI + React 的 AI 伴侣聊天系统，集成语音通话、视频生成、图像生成、视觉识别、情绪引擎、三层记忆架构、多用户管理等功能，提供完整的虚拟伴侣体验。支持多平台部署（林语 IM、QQ、控制台、Web），可扩展的插件架构。

## 核心特性

### 智能对话
- **多 LLM 支持** - OpenAI、SiliconFlow、DeepSeek、云舞、Qwen 等主流提供商
- **流式响应** - WebSocket 实时对话流，低延迟体验
- **上下文管理** - 智能对话历史管理，支持长对话
- **伴侣模式** - 关系反思、自发分享、语气结束概率等拟人化增强

### 多模态交互
- **TTS 语音合成** - 启航AI/Qwen TTS，支持文本清洗和智能分段
- **ASR 语音识别** - SiliconFlow / Qwen ASR，自动识别语音消息
- **图像生成** - images-api / ModelScope / 云舞 / GPT Image / Kling 网页模式，支持提示词增强
- **视频生成** - Qwen 视频生成，支持关键词触发和异步轮询
- **视觉识别** - 智能图片内容识别，自动融入对话语境
- **实时语音通话** - 基于 WebRTC 的 AI 语音通话（林语 IM 信令）

### 小脑情绪引擎
- **情绪状态追踪** - 多维情绪值（开心、悲伤、焦虑、兴奋等），自动衰减和基线回归
- **昼夜节律** - 根据时间段自动调整情绪基线
- **动机信号** - 情绪超过阈值时触发主动行为（发消息、生图等）
- **外部刺激** - 对话内容、语义分析实时影响情绪状态
- **状态持久化** - 情绪状态跨重启保存

### 三层记忆架构
- **短期记忆** - 最近 30 轮对话历史
- **中期记忆** - 自动对话摘要（可配置条数）
- **长期记忆** - 向量检索（ChromaDB + 外部嵌入模型），支持 1000+ 条记忆
- **待办缓冲** - 待写入记忆的消息缓冲区，摘要后自动清理
- **外部记忆** - 支持 Memobase 等外部记忆服务

### 主动交互
- **定时问候** - 可配置时间窗口主动发送消息
- **空闲检测** - 长时间未聊天后主动问候
- **提醒系统** - 智能提醒检测和调度
- **日程生成** - 基于角色人设自动生成每日日程

### Agent 委派
- **Hermes 集成** - 将复杂任务委派给 Hermes Agent 执行
- **异步推送** - 任务完成后自动推送结果到对应聊天渠道
- **多渠道支持** - 支持林语、QQ、Web 等渠道的结果回推

### 提示词系统
- **独立提示词** - 每个用户独立的 system_prompt.md
- **版本管理** - 提示词变更历史记录，支持回溯
- **情景模式** - 视觉小说式角色扮演，独立提示词和回复格式
- **规则分离** - system_prompt.md / system_rules.md / roleplay_prompt.md 分离管理

### 内容增强
- **提示词增强器** - 基于本地词库自动补充图像生成细节（人像、美食等意图）
- **表情包系统** - 根据语境自动发送表情包
- **文本分割器** - 智能分割长文本，提升对话自然度
- **消息防抖** - 多条消息合并处理，避免频繁触发

### 扩展性
- **MCP 插件系统** - 插件化架构，支持自定义功能扩展
- **内置插件** - 时钟、日常作息、提醒管理、日程生成
- **多平台适配** - 林语 IM（WebSocket）、QQ（WebSocket）、控制台、Web 管理界面

### 多用户管理
- **用户认证** - JWT 认证，支持注册/登录
- **个性化配置** - 每个用户独立配置（系统提示词、LLM 参数、TTS 语音等）
- **管理员 API** - 统一管理多用户配置和全局配置
- **访问控制** - 白名单/黑名单支持

### 可视化管理
- **Web 管理界面** - 基于 React + Ant Design 的现代化界面
- **实时配置** - 所有功能模块可视化配置
- **响应式设计** - 支持桌面和移动端访问

## 技术栈

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
| cryptography | ≥42.0.0 | 加密（林语 WebRTC） |
| aiortc | ≥1.9.0 | WebRTC 音视频通话 |
| av | ≥12.0.0 | 音视频处理 |
| dashscope | ≥1.23.9 | Qwen API SDK |
| numpy | ≥1.24.0 | 数值计算 |

### 前端技术
| 技术 | 版本 | 用途 |
|------|------|------|
| React | 19.2 | 现代化 UI 框架 |
| TypeScript | 5.9 | 类型安全开发 |
| Ant Design | 6.1 | 企业级 UI 组件库 |
| Vite | 7.3 | 快速构建工具 |
| React Router | 7.0 | 路由管理 |
| Axios | 1.6 | HTTP 客户端 |
| React Markdown | 9.0 | Markdown 渲染 |
| React Syntax Highlighter | 15.5 | 代码高亮 |

### AI 服务集成
| 类别 | 提供商 |
|------|--------|
| LLM | OpenAI、SiliconFlow、DeepSeek、云舞、Qwen |
| TTS | 启航AI、Qwen TTS |
| ASR | SiliconFlow ASR、Qwen ASR |
| 图像生成 | images-api、ModelScope、云舞、GPT Image、Kling 网页模式 |
| 视频生成 | Qwen 视频生成 |
| 视觉识别 | ModelScope（Qwen3-VL-30B） |
| 嵌入模型 | 阿里云 text-embedding-v4 |
| 外部记忆 | Memobase |

## 项目架构

```
Ta/
├── backend/                        # Python 后端
│   ├── adapters/                  # 平台适配器
│   │   ├── console.py             # 控制台适配器
│   │   ├── qq.py                  # QQ 机器人适配器
│   │   ├── linyu.py               # 林语 IM 适配器（WebSocket + HTTP）
│   │   ├── linyu_manager.py       # 林语多会话管理器
│   │   └── debouncer.py           # 消息防抖器
│   ├── api/                       # REST API 路由（27 模块）
│   │   ├── chat.py                # 聊天 API
│   │   ├── tts.py                 # TTS 语音合成
│   │   ├── asr.py                 # ASR 语音识别
│   │   ├── image_gen.py           # 图像生成
│   │   ├── video_gen.py           # 视频生成
│   │   ├── vision.py              # 视觉识别
│   │   ├── memory.py              # 记忆系统
│   │   ├── cerebellum.py          # 小脑情绪引擎
│   │   ├── prompt.py              # 提示词管理
│   │   ├── prompt_enhancer.py     # 提示词增强
│   │   ├── emotes.py              # 表情包系统
│   │   ├── proactive.py           # 主动聊天
│   │   ├── mcp.py                 # MCP 插件
│   │   ├── reminder.py            # 提醒系统
│   │   ├── daily_schedule.py      # 日程生成
│   │   ├── agent_delegate.py      # Agent 委派配置
│   │   ├── voice_session.py       # 语音通话会话
│   │   ├── linyu_sessions.py      # 林语会话管理
│   │   ├── access_control.py      # 访问控制
│   │   ├── user_auth.py           # 用户认证
│   │   ├── user_config.py         # 用户配置
│   │   ├── admin_users.py         # 管理员 API
│   │   ├── admin_auth.py          # 管理员认证
│   │   ├── config.py              # 全局配置 API
│   │   ├── bot_provider.py        # Bot 单例提供者
│   │   └── deps.py                # API 依赖注入
│   ├── core/                      # 核心业务逻辑
│   │   ├── bot.py                 # Bot 核心类
│   │   ├── context_builder.py     # 上下文构建器
│   │   ├── user_cache.py          # 用户缓存
│   │   ├── gen_img_parser.py      # 图像生成解析
│   │   ├── gen_video_parser.py    # 视频生成解析
│   │   ├── tts_tag_parser.py      # TTS 标签解析
│   │   ├── cerebellum/            # 小脑情绪引擎
│   │   │   ├── engine.py          # 引擎核心（情绪衰减、动机触发）
│   │   │   └── models.py          # 情绪模型定义
│   │   └── proactive/             # 主动聊天调度
│   │       └── scheduler.py       # 调度器
│   ├── providers/                 # LLM 提供商
│   │   ├── openai_provider.py     # OpenAI 兼容提供商
│   │   └── base.py                # 提供商基类
│   ├── tts/                       # TTS 系统
│   │   ├── manager.py             # TTS 管理器
│   │   ├── config.py              # TTS 配置
│   │   └── providers/             # TTS 提供商
│   ├── asr/                       # ASR 系统
│   │   └── providers/             # ASR 提供商
│   ├── image_gen/                 # 图像生成系统
│   │   ├── manager.py             # 图像生成管理器
│   │   └── providers/             # 图像生成提供商（含 image_api）
│   ├── video_gen/                 # 视频生成系统
│   │   ├── manager.py             # 视频生成管理器
│   │   └── config.py              # 视频生成配置
│   ├── vision/                    # 视觉识别系统
│   │   ├── manager.py             # 视觉识别管理器
│   │   └── providers/             # 视觉识别提供商
│   ├── voice_call/                # 语音通话系统
│   │   ├── manager.py             # WebRTC 通话管理器
│   │   ├── config.py              # 通话配置
│   │   └── session.py             # 通话会话
│   ├── voice_gateway/             # 语音网关
│   ├── memory/                    # 记忆系统
│   │   ├── manager.py             # 向量记忆管理器
│   │   ├── vector_store.py        # ChromaDB 向量存储
│   │   ├── base.py                # 记忆基类
│   │   ├── summarizer.py          # 对话摘要
│   │   ├── reminder_scheduler.py  # 提醒调度
│   │   └── reminder_detector.py   # 提醒检测
│   ├── prompt_enhancer/           # 提示词增强器
│   │   ├── enhancer.py            # 增强器核心
│   │   └── word_banks/            # 词库文件
│   ├── prompt_system/             # 提示词管理系统
│   │   ├── manager.py             # 提示词读写、版本记录
│   │   └── models.py              # 提示词数据模型
│   ├── emote/                     # 表情包系统
│   │   └── manager.py             # 表情包管理器
│   ├── mcp/                       # MCP 插件系统
│   │   ├── manager.py             # 插件管理器
│   │   ├── clock.py               # 时钟插件
│   │   ├── daily_habits.py        # 日常作息插件
│   │   └── schedule_generator.py  # 日程生成插件
│   ├── agent_delegate/            # Agent 委派系统
│   │   └── __init__.py            # 委派标签解析、Hermes 客户端
│   ├── user/                      # 用户管理
│   │   ├── manager.py             # 用户管理器
│   │   ├── data_manager.py        # 用户数据文件管理
│   │   └── models.py              # 用户模型
│   ├── utils/                     # 工具模块
│   │   ├── text_splitter.py       # 文本分割器
│   │   ├── datetime_utils.py      # 时间工具
│   │   └── config_merger.py       # 配置合并
│   ├── config.py                  # 配置管理
│   └── main.py                    # FastAPI 应用入口
├── frontend/                      # React 前端
│   ├── src/
│   │   ├── pages/                 # 页面组件（20+ 页面）
│   │   │   ├── ChatPage.tsx               # 聊天界面
│   │   │   ├── SettingsPage.tsx           # 系统设置
│   │   │   ├── UserSettingsPage.tsx       # 用户个人设置
│   │   │   ├── PersonalityPage.tsx        # 角色设定
│   │   │   ├── RoleplayModePage.tsx       # 情景模式
│   │   │   ├── TTSConfigPage.tsx          # TTS 配置
│   │   │   ├── ImageGenPage.tsx           # 图像生成配置
│   │   │   ├── VideoGenPage.tsx           # 视频生成配置
│   │   │   ├── VisionPage.tsx             # 视觉识别配置
│   │   │   ├── MemoryPage.tsx             # 记忆系统配置
│   │   │   ├── MemoryManagePage.tsx       # 记忆数据管理
│   │   │   ├── CerebellumPage.tsx         # 情绪系统面板
│   │   │   ├── PromptEnhancerPage.tsx     # 提示词增强器
│   │   │   ├── EmotePage.tsx              # 表情包配置
│   │   │   ├── DailySchedulePage.tsx      # 日程生成
│   │   │   ├── ReminderPage.tsx           # 提醒管理
│   │   │   ├── ReminderManagePage.tsx     # 提醒数据管理
│   │   │   ├── AgentDelegatePage.tsx      # Agent 委派配置
│   │   │   ├── AdminUsersPage.tsx         # 多用户管理
│   │   │   ├── AdminGlobalConfigPage.tsx  # 全局配置管理
│   │   │   └── LoginPage.tsx              # 登录界面
│   │   ├── contexts/              # React Context
│   │   │   └── AuthContext.tsx     # 认证上下文
│   │   ├── components/            # 通用组件
│   │   │   └── ProtectedRoute.tsx # 路由守卫
│   │   ├── services/              # API 服务层
│   │   └── types/                 # TypeScript 类型定义
│   └── package.json               # 前端依赖
├── user_data/                     # 用户独立数据
│   └── {username}/                # 每用户目录
│       ├── system_prompt.md       # 用户提示词
│       ├── system_rules.md        # 用户规则
│       ├── roleplay_prompt.md     # 情景模式提示词
│       ├── prompt_history.json    # 提示词变更历史
│       ├── base_image/            # 用户基础图片
│       └── config.yaml            # 用户覆盖配置
├── data/                          # 全局数据存储
│   ├── ta.db                      # SQLite 数据库
│   ├── chroma/                    # ChromaDB 向量数据库
│   ├── emotes/                    # 表情包存储
│   ├── tts/                       # TTS 音频缓存
│   ├── cerebellum_state.json      # 情绪引擎状态
│   ├── daily_habits.json          # 日常作息配置
│   └── mcp_plugins.json           # MCP 插件配置
├── config.yaml                    # 主配置文件
├── config.example.yaml            # 配置模板
├── requirements.txt               # Python 依赖
├── run.py                         # 启动脚本
└── README.md                      # 项目文档
```

### 架构设计模式

**分层架构**
- 表现层 - React 前端 + Ant Design
- API 层 - FastAPI REST + WebSocket
- 业务逻辑层 - Bot 核心 + 管理器 + 情绪引擎
- 数据访问层 - SQLAlchemy ORM + ChromaDB + 文件系统
- 集成层 - 提供商适配器 + 平台适配器

**核心设计模式**
- **适配器模式** - 平台适配器（林语、QQ、Console）、提供商适配器（LLM、TTS、ASR）
- **管理器模式** - 各子系统集中管理（TTS、ASR、Memory、Image Gen、Video Gen、Vision、Emote、MCP）
- **插件架构** - MCP 插件系统，支持第三方扩展
- **情绪驱动** - 小脑引擎根据情绪状态触发主动行为
- **多用户配置** - 用户配置覆盖全局配置，支持配置合并
- **三层记忆** - 短期（30 轮）+ 中期（摘要）+ 长期（1000+ 向量）
- **防抖合并** - 多条消息合并处理，减少 LLM 调用

## 快速开始

### 环境要求
- Python 3.9+（推荐 3.12）
- Node.js 16+
- Windows/Linux/macOS

### 安装步骤

**1. 克隆项目**
```bash
git clone <repository-url>
cd Ta
```

**2. 后端环境配置**
```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
```

**3. 前端环境配置**
```bash
cd frontend
npm install
npm run build  # 生产构建，输出到 frontend/dist/
```

**4. 配置文件**

首次启动时，从 `config.example.yaml` 复制生成 `config.yaml`：
```bash
cp config.example.yaml config.yaml
```

编辑 `config.yaml`，配置必要的 API 密钥：

```yaml
# LLM 配置
llm:
  provider: yunwu
  api_base: https://yunwu.ai/v1
  api_key: your-api-key-here
  model: gemini-3.1-flash-lite
  temperature: 0.8
  max_tokens: 900

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

# 方式二：直接启动后端
python backend/main.py
```

后端启动后自动服务前端静态文件（SPA），无需单独启动前端开发服务器。

### 生产部署（systemd）

```bash
# 创建 systemd 服务
sudo vim /etc/systemd/system/ta.service
```

```ini
[Unit]
Description=Ta AI Companion Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/Ta
ExecStart=/path/to/Ta/venv/bin/python backend/main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable ta
sudo systemctl start ta
```

### 访问应用

- **Web 界面** - http://localhost:8003（生产模式，前端由后端服务）
- **前端开发** - http://localhost:5173（`cd frontend && npm run dev`）
- **后端 API** - http://localhost:8003
- **API 文档** - http://localhost:8003/docs
- **控制台模式** - 在 config.yaml 中启用 `adapters.console.enabled: true`

## 多平台适配

### 林语 IM（推荐）

林语 IM 是主要的聊天平台适配器，通过 WebSocket + HTTP API 直连：

```yaml
adapters:
  linyu:
    enabled: true
    ws_host: your-linyu-server
    ws_port: 9100
    http_host: your-linyu-server
    http_port: 9200
    account: 'your-account'
    password: 'your-password'
    auto_bind_first_user: true
    segment_config:
      enabled: true
      strategy: sentence
      max_segment_length: 100
    voice_call:
      enabled: true
      auto_answer: true
      audio_only: true
```

### QQ 机器人

```yaml
adapters:
  qq:
    enabled: true
    ws_host: 127.0.0.1
    ws_port: 3001
    need_at: true
    debounce:
      enabled: true
      delay: 5
      max_wait: 10
```

### 访问控制

```yaml
adapters:
  linyu:
    access_control:
      enabled: true
      mode: whitelist  # whitelist, blacklist
      whitelist: ['user_id_1', 'user_id_2']
```

## 多用户管理

### 用户认证
```bash
# 注册用户
POST /api/auth/register

# 登录获取 Token
POST /api/auth/login

# 使用 Token
Authorization: Bearer <token>
```

### 个人配置
每个用户可独立配置：
- 系统提示词和角色设定
- LLM 参数（模型、温度等）
- TTS 语音角色
- 图像生成偏好
- 记忆系统设置

**配置合并规则**：用户配置 > 全局配置

### 管理员 API

配置管理员密钥（config.yaml）：
```yaml
admin:
  api_key: "your-strong-random-key"
```

**管理员端点**（需要 `X-Admin-Token` 请求头）
- `GET /api/admin/users` - 列出所有用户
- `GET /api/admin/users/{user_id}/config` - 获取用户配置
- `PUT /api/admin/users/{user_id}/config` - 更新用户配置

## 核心配置

### LLM 配置
```yaml
llm:
  provider: yunwu        # openai, deepseek, siliconflow, yunwu, qwen
  api_base: https://yunwu.ai/v1
  api_key: sk-your-key
  model: gemini-3.1-flash-lite
  temperature: 0.8
  max_tokens: 900
  frequency_penalty: 0.25
  presence_penalty: 0.2
  # 伴侣模式
  companion_mode:
    enabled: true
    min_turn_gap: 2
    spontaneous_share_probability: 0.35
    relationship_reflection_probability: 0.18
```

### TTS 语音合成
```yaml
tts:
  enabled: true
  provider: qihang
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
  provider: image_api    # image_api, modelscope, yunwu, gpt_image, kling_api
  image_api:
    api_base: http://your-images-api:8006
    api_key: your-key
    model: doubao-seedream-4.5
  trigger_keywords:
    - 生成图片
    - 看看穿搭
    - ootd
```

### 视频生成
```yaml
video_generation:
  enabled: true
  provider: qwen
  trigger_keywords:
    - 生成视频
    - 录个视频
```

### 小脑情绪引擎
```yaml
cerebellum:
  enabled: true
  tick_interval: 30           # 情绪更新间隔（秒）
  decay_rate: 0.008           # 情绪衰减速率
  action_threshold: 0.52      # 动机触发阈值
  motivation_cooldown_seconds: 1800
  proactive_chat:
    enabled: true
    check_interval_seconds: 60
    image_generation:
      enabled: true
      max_per_day: 3
```

### 记忆系统
```yaml
memory:
  short_term_enabled: true
  short_term_max_rounds: 30
  mid_term_enabled: true
  mid_term_context_count: 5
  long_term_enabled: true
  long_term_strategy: local    # local, external
  max_long_term_memories: 1000
  summarizer_enabled: true
  summary_interval: 10
  pending_enabled: true
  pending_chunk_rounds: 20
  # 外部记忆（可选）
  external_memory_provider: memobase
  external_memory_base_url: http://your-memobase:8019
```

### Agent 委派
```yaml
agent_delegate:
  enabled: true
  hermes:
    api_base: http://your-hermes:8642
    api_key: your-key
    timeout: 300
    poll_interval: 3
    max_concurrent_tasks: 5
    instructions: '你是一个能干的助理。简洁高效地完成任务。'
```

完整配置请参考 [config.example.yaml](config.example.yaml)

## 功能使用指南

### 图像生成

**触发方式**
在聊天中发送包含关键词的消息：
- `生成图片：美丽的风景`
- `看看穿搭，休闲风格`
- `ootd 今天穿什么`

**提示词增强**
系统会自动基于本地词库补充细节：
- 发型、面部特征、服装
- 姿势、表情、场景
- 光照、质量提升

### 视频生成

发送包含视频生成关键词的消息，系统异步提交任务并轮询结果。

### 实时语音通话（林语 IM）

林语适配器支持 WebRTC 语音通话：
- 用户发起通话邀请
- AI 自动接听（可配置延迟）
- 支持纯音频模式
- 最大通话时长可配置

### 情景模式

在前端「情景模式」页面启用，进入视觉小说式角色扮演：
- 独立的 roleplay_prompt.md
- 结构化回复格式（状态/动作/心理/台词）
- 不触发语音、图片、工具等现实功能

### 提示词管理

每个用户拥有独立的提示词文件：
- `user_data/{username}/system_prompt.md` - 主提示词
- `user_data/{username}/system_rules.md` - 规则约束
- `user_data/{username}/roleplay_prompt.md` - 情景模式提示词
- `user_data/{username}/prompt_history.json` - 变更历史

通过前端「人格设定」页面或 API 管理。

### 表情包系统

**配置步骤**
1. 在 `data/emotes/` 创建分类文件夹
2. 放入表情包图片（png、jpg、gif、webp）
3. 在 config.yaml 配置分类和关键词

系统根据对话内容自动匹配关键词发送表情包。

### 主动聊天

**工作模式**
- **定时窗口** - 在指定时间段主动问候
- **空闲窗口** - 长时间未聊天后主动问候
- **情绪驱动** - 小脑引擎根据情绪状态触发主动行为

### MCP 插件系统

**内置插件**
- **clock** - 提供当前时间信息
- **daily_habits** - 根据作息表返回当前状态
- **schedule_generator** - 日程生成

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

## API 接口

### WebSocket
- `ws://localhost:8003/ws/chat` - 实时聊天流式接口

### 核心 API
| 功能 | 端点 | 说明 |
|------|------|------|
| 聊天 | `POST /api/chat` | 非流式聊天 |
| TTS | `POST /api/tts/generate` | 语音合成 |
| ASR | `POST /api/asr/transcribe` | 语音识别 |
| 图像生成 | `POST /api/image-gen/generate` | 生成图片 |
| 视频生成 | `POST /api/video-gen/generate` | 生成视频 |
| 视觉识别 | `POST /api/vision/recognize` | 识别图片 |
| 记忆系统 | `POST /api/memory/search` | 记忆检索 |
| 提示词 | `GET/PUT /api/prompt` | 提示词管理 |
| 情绪系统 | `GET /api/cerebellum/state` | 情绪状态 |
| 提示词增强 | `POST /api/prompt-enhancer/enhance` | 增强提示词 |
| 表情包 | `POST /api/emotes/test` | 测试表情包选择 |
| 主动聊天 | `POST /api/proactive/trigger` | 手动触发主动聊天 |
| MCP 插件 | `POST /api/mcp/plugins/{name}/execute` | 执行插件工具 |
| 日程生成 | `POST /api/daily-schedule/generate` | 生成日程 |
| Agent 委派 | `GET/PUT /api/agent-delegate/config` | 委派配置 |
| 语音通话 | `POST /api/voice-session/call` | 发起通话 |

### 配置 API
所有功能模块都提供配置 API：
- `GET /api/{module}/config` - 获取配置
- `POST /api/{module}/config` - 更新配置
- `POST /api/{module}/test-connection` - 测试连接

完整 API 文档：http://localhost:8003/docs

## 开发指南

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

## 故障排除

### 常见问题

**端口占用**
- 检查 8003 端口：`lsof -i :8003` 或 `netstat -tlnp | grep 8003`
- 修改 config.yaml 中的 `server.port`

**API 连接失败**
- 检查网络连接
- 验证 API 密钥是否正确
- 查看后端日志获取详细错误

**TTS 不工作**
- 检查 `tts.enabled: true`
- 验证 API 密钥
- 查看后台日志

**前端无法访问后端**
- 确保后端服务正在运行
- 检查 CORS 设置
- 查看浏览器开发者工具

**林语连接失败**
- 检查 WebSocket 地址和端口
- 验证账号密码
- 查看重连日志（默认最多重连 10 次）

### LLM 请求审计
开启环境变量 `LLM_TRACE=1` 记录所有 LLM 请求：
```bash
export LLM_TRACE=1
python run.py
```

日志位置：`backend/data/llm_payloads/YYYYMMDD.log`

## 项目统计

- **后端模块** - 27 个 API 路由模块
- **前端页面** - 20+ React 页面
- **适配平台** - 林语 IM、QQ、控制台、Web
- **AI 提供商** - 10+ 主流提供商
- **情绪维度** - 7 维情绪状态追踪
- **记忆容量** - 1000+ 长期向量记忆

## 相关文档

- [docs/IFLOW.md](docs/IFLOW.md) - 项目详细交互上下文指南
- [docs/MCP_USAGE.md](docs/MCP_USAGE.md) - MCP 扩展使用说明
- [docs/cerebellum-emotion-system.md](docs/cerebellum-emotion-system.md) - 小脑情绪系统说明
- [docs/agent-delegation-guide.md](docs/agent-delegation-guide.md) - Agent 委派使用指南
- [docs/linyu详细说明.md](docs/linyu详细说明.md) - 林语 IM 适配器详细说明
- [docs/记忆系统复刻设计文档.md](docs/记忆系统复刻设计文档.md) - 记忆系统设计文档
- [DEPLOY.md](DEPLOY.md) - 部署文档
- [Ubuntu部署文档.md](Ubuntu部署文档.md) - Ubuntu 部署指南

## 快速链接

**前端界面**
- [聊天界面](http://localhost:8003/chat)
- [系统设置](http://localhost:8003/settings)
- [角色设定](http://localhost:8003/personality)
- [情景模式](http://localhost:8003/roleplay-mode)
- [TTS 配置](http://localhost:8003/tts)
- [图像生成](http://localhost:8003/image-gen)
- [视频生成](http://localhost:8003/video-gen)
- [视觉识别](http://localhost:8003/vision)
- [记忆管理](http://localhost:8003/memory)
- [情绪系统](http://localhost:8003/cerebellum)
- [提示词增强](http://localhost:8003/prompt-enhancer)
- [表情包配置](http://localhost:8003/emotes)
- [日程生成](http://localhost:8003/daily-schedule)
- [提醒管理](http://localhost:8003/reminder)
- [Agent 委派](http://localhost:8003/agent-delegate)
- [多用户管理](http://localhost:8003/admin-users)

**后端服务**
- [API 文档](http://localhost:8003/docs)
- [健康检查](http://localhost:8003/api/health)

## 许可证

MIT License

---

**Ta** - AI 伴侣聊天系统
