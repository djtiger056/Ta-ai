# LFBot - AI 聊天陪伴机器人项目思维导图

```
LFBot (AI 聊天陪伴机器人)
├── 🎯 核心定位
│   ├── 虚拟伴侣体验
│   ├── 多模态 AI 能力
│   ├── 全功能聊天机器人系统
│   └── 前后端分离架构
│
├── 🔧 技术栈
│   ├── 后端技术
│   │   ├── FastAPI (高性能 Web 框架)
│   │   ├── SQLAlchemy + AsyncPG (异步数据库 ORM)
│   │   ├── WebSocket (实时双向通信)
│   │   ├── Pydantic (数据验证)
│   │   ├── aiohttp (异步 HTTP 客户端)
│   │   ├── Loguru (结构化日志)
│   │   ├── ChromaDB (向量数据库)
│   │   ├── Sentence Transformers (文本嵌入)
│   │   └── jieba (中文分词)
│   │
│   ├── 前端技术
│   │   ├── React 19 (UI 框架)
│   │   ├── TypeScript (类型安全)
│   │   ├── Ant Design 6 (UI 组件库)
│   │   ├── Vite 7 (快速构建)
│   │   ├── React Router 7 (路由管理)
│   │   ├── Axios (HTTP 客户端)
│   │   ├── React Markdown (Markdown 渲染)
│   │   └── React Syntax Highlighter (代码高亮)
│   │
│   └── AI 集成
│       ├── OpenAI 兼容 API
│       ├── SiliconFlow (硅基流动)
│       ├── DeepSeek
│       ├── 云舞 AI
│       ├── 启航AI TTS
│       └── 魔搭社区 ModelScope
│
├── 🚀 核心功能模块
│   ├── 🤖 AI 对话聊天
│   │   ├── 支持多种 LLM 提供商
│   │   ├── 实时流式回复
│   │   ├── 多轮对话上下文
│   │   └── 自定义系统提示词
│   │
│   ├── 🔊 TTS 语音合成
│   │   ├── 启航AI 集成
│   │   ├── 文本清洗功能
│   │   ├── 分段发送配置
│   │   ├── 多音色支持
│   │   └── 概率触发控制
│   │
│   ├── 🎤 ASR 语音识别
│   │   ├── 硅基流动集成
│   │   ├── 自动语音转文本
│   │   ├── 支持私聊和群聊
│   │   └── 自动发送到 LLM
│   │
│   ├── 🎨 图像生成
│   │   ├── 魔搭社区集成
│   │   ├── 云舞 AI 集成
│   │   ├── 多模型支持
│   │   ├── 触发关键词配置
│   │   └── 提示词增强
│   │
│   ├── 👁️ 视觉识别
│   │   ├── 魔搭社区集成
│   │   ├── 智能图片内容识别
│   │   ├── 自动融入对话语境
│   │   └── 多模态理解
│   │
│   ├── 🧠 记忆系统
│   │   ├── 短期记忆 (最近对话轮数)
│   │   ├── 中期记忆 (对话摘要)
│   │   ├── 长期记忆 (向量检索)
│   │   ├── RAG 检索
│   │   ├── 记忆重要性评分
│   │   └── 多用户隔离
│   │
│   ├── ✂️ 文本分割器
│   │   ├── 智能分段策略
│   │   ├── 优先句子边界分割
│   │   ├── 可配置分段长度
│   │   ├── 分段发送延迟
│   │   └── 提升对话自然度
│   │
│   ├── ✨ 提示词增强器
│   │   ├── 本地词库支持
│   │   ├── 多预设切换
│   │   ├── 智能意图检测
│   │   ├── 自定义词库
│   │   └── 图像生成质量提升
│   │
│   ├── 😊 表情包系统
│   │   ├── 语境自动匹配
│   │   ├── 多分类管理
│   │   ├── 触发关键词配置
│   │   ├── 权重控制
│   │   └── 多格式支持
│   │
│   ├── ⏰ 主动聊天
│   │   ├── 定时窗口触发
│   │   ├── 空闲窗口触发
│   │   ├── 随机化机制
│   │   ├── 冷却时间控制
│   │   ├── 多目标配置
│   │   └── 个性化问候模板
│   │
│   ├── 🔌 MCP 扩展系统
│   │   ├── 插件化架构
│   │   ├── 插件管理 API
│   │   ├── 自动上下文注入
│   │   ├── 时钟插件
│   │   └── 日常作息插件
│   │
│   ├── 📅 待办事项提醒
│   │   ├── 智能时间识别
│   │   ├── 自动检测提醒
│   │   ├── 多平台发送
│   │   ├── 提醒消息自定义
│   │   └── 定时调度
│   │
│   └── 👥 用户系统
│       ├── 多用户支持
│       ├── 独立配置管理
│       ├── 用户认证 (JWT)
│       ├── 管理员接口
│       └── 配置覆盖机制
│
├── 📱 平台适配器
│   ├── QQ 机器人
│   │   ├── WebSocket 连接
│   │   ├── 私聊支持
│   │   ├── 群聊支持 (@触发)
│   │   ├── 访问控制 (白名单/黑名单)
│   │   └── 文本分段发送
│   │
│   ├── 控制台适配器
│   │   ├── 命令行交互
│   │   ├── 实时对话
│   │   └── 调试模式
│   │
│   └── Web 管理界面
│       ├── 可视化配置
│       ├── 实时监控
│       ├── 聊天界面
│       └── 响应式设计
│
├── 📂 项目结构
│   ├── backend/
│   │   ├── adapters/ (平台适配器)
│   │   │   ├── console.py (控制台)
│   │   │   └── qq.py (QQ 机器人)
│   │   ├── api/ (API 路由)
│   │   │   ├── chat.py (聊天)
│   │   │   ├── tts.py (语音合成)
│   │   │   ├── asr.py (语音识别)
│   │   │   ├── image_gen.py (图像生成)
│   │   │   ├── vision.py (视觉识别)
│   │   │   ├── memory.py (记忆系统)
│   │   │   ├── prompt_enhancer.py (提示词增强)
│   │   │   ├── emotes.py (表情包)
│   │   │   ├── proactive.py (主动聊天)
│   │   │   ├── reminder.py (待办事项)
│   │   │   ├── mcp.py (MCP 插件)
│   │   │   ├── user_auth.py (用户认证)
│   │   │   ├── user_config.py (用户配置)
│   │   │   ├── admin_users.py (管理员)
│   │   │   └── config.py (配置管理)
│   │   ├── core/ (核心业务)
│   │   │   ├── bot.py (Bot 核心类)
│   │   │   └── proactive.py (主动聊天逻辑)
│   │   ├── providers/ (LLM 提供商)
│   │   ├── tts/ (TTS 系统)
│   │   ├── asr/ (ASR 系统)
│   │   ├── image_gen/ (图像生成)
│   │   ├── vision/ (视觉识别)
│   │   ├── memory/ (记忆系统)
│   │   ├── prompt_enhancer/ (提示词增强)
│   │   ├── emote/ (表情包系统)
│   │   ├── mcp/ (MCP 插件)
│   │   ├── user/ (用户管理)
│   │   ├── utils/ (工具模块)
│   │   ├── config.py (配置管理)
│   │   └── main.py (应用入口)
│   │
│   ├── frontend/
│   │   ├── src/
│   │   │   ├── pages/ (页面组件)
│   │   │   │   ├── ChatPage.tsx (聊天)
│   │   │   │   ├── PersonalityPage.tsx (角色设定)
│   │   │   │   ├── SettingsPage.tsx (系统设置)
│   │   │   │   ├── TTSConfigPage.tsx (TTS 配置)
│   │   │   │   ├── ASRConfigPage.tsx (ASR 配置)
│   │   │   │   ├── ImageGenPage.tsx (图像生成)
│   │   │   │   ├── VisionPage.tsx (视觉识别)
│   │   │   │   ├── MemoryPage.tsx (记忆系统)
│   │   │   │   ├── PromptEnhancerPage.tsx (提示词增强)
│   │   │   │   ├── EmotePage.tsx (表情包)
│   │   │   │   ├── ProactiveChatPage.tsx (主动聊天)
│   │   │   │   └── DailyHabitsPage.tsx (日常作息)
│   │   │   ├── services/ (API 服务)
│   │   │   └── types/ (类型定义)
│   │   └── package.json
│   │
│   ├── data/ (数据存储)
│   │   ├── chroma/ (向量数据库)
│   │   ├── lfbot.db (SQLite 数据库)
│   │   ├── users.db (用户数据库)
│   │   ├── mcp_plugins.json (MCP 插件配置)
│   │   ├── custom_prompt_words.yaml (自定义词库)
│   │   ├── daily_habits.json (日常作息)
│   │   ├── emotes/ (表情包存储)
│   │   ├── tts/ (TTS 数据)
│   │   └── tts_audio/ (TTS 音频)
│   │
│   ├── config.yaml (主配置文件)
│   ├── requirements.txt (Python 依赖)
│   ├── run.py (启动脚本)
│   └── README.md (项目文档)
│
├── ⚙️ 配置管理
│   ├── LLM 配置
│   │   ├── 提供商选择
│   │   ├── API 密钥
│   │   ├── 模型选择
│   │   ├── 温度参数
│   │   ├── 最大 Token
│   │   └── 重试机制
│   │
│   ├── TTS 配置
│   │   ├── 启用/禁用
│   │   ├── 提供商选择
│   │   ├── 音色选择
│   │   ├── 触发概率
│   │   ├── 分段策略
│   │   └── 文本清洗
│   │
│   ├── ASR 配置
│   │   ├── 启用/禁用
│   │   ├── 提供商选择
│   │   ├── 模型选择
│   │   ├── 超时设置
│   │   └── 消息自定义
│   │
│   ├── 图像生成配置
│   │   ├── 启用/禁用
│   │   ├── 提供商选择
│   │   ├── 模型选择
│   │   ├── 触发关键词
│   │   └── 消息自定义
│   │
│   ├── 视觉识别配置
│   │   ├── 启用/禁用
│   │   ├── 提供商选择
│   │   ├── 模型选择
│   │   ├── 自动发送到 LLM
│   │   └── 识别指令
│   │
│   ├── 记忆系统配置
│   │   ├── 短期/中期/长期开关
│   │   ├── 记忆容量
│   │   ├── 摘要间隔
│   │   ├── RAG 参数
│   │   └── 嵌入模型
│   │
│   ├── 提示词增强配置
│   │   ├── 启用/禁用
│   │   ├── 词库路径
│   │   ├── 预设管理
│   │   ├── 意图检测
│   │   └── 分类配置
│   │
│   ├── 表情包配置
│   │   ├── 启用/禁用
│   │   ├── 发送概率
│   │   ├── 分类管理
│   │   ├── 关键词配置
│   │   └── 权重设置
│   │
│   ├── 主动聊天配置
│   │   ├── 启用/禁用
│   │   ├── 检查间隔
│   │   ├── 定时窗口
│   │   ├── 空闲窗口
│   │   ├── 目标配置
│   │   └── 消息模板
│   │
│   ├── 待办事项配置
│   │   ├── 启用/禁用
│   │   ├── 检查间隔
│   │   ├── 时间模式
│   │   ├── 自动检测
│   │   └── 时区设置
│   │
│   ├── 适配器配置
│   │   ├── QQ 机器人
│   │   │   ├── WebSocket 地址
│   │   │   ├── 访问令牌
│   │   │   ├── @ 触发设置
│   │   │   └── 访问控制
│   │   └── 控制台
│   │       └── 启用/禁用
│   │
│   ├── 服务器配置
│   │   ├── 主机地址
│   │   ├── 端口号
│   │   ├── 调试模式
│   │   └── CORS 设置
│   │
│   └── 系统提示词
│       ├── 角色设定
│       ├── 性格特征
│       ├── 语言风格
│       ├── 行为准则
│       └── 视觉交互协议
│
├── 🔌 API 接口
│   ├── WebSocket
│   │   └── /ws/chat (实时聊天流)
│   │
│   ├── 聊天相关
│   │   ├── POST /api/chat (非流式聊天)
│   │   └── GET /api/config (获取配置)
│   │
│   ├── TTS 相关
│   │   ├── POST /api/tts/generate (生成语音)
│   │   └── POST /api/tts/config (更新配置)
│   │
│   ├── ASR 相关
│   │   ├── POST /api/asr/transcribe (语音转文本)
│   │   ├── GET /api/asr/config (获取配置)
│   │   ├── POST /api/asr/config (更新配置)
│   │   └── POST /api/asr/test-connection (测试连接)
│   │
│   ├── 图像生成相关
│   │   ├── POST /api/image-gen/generate (生成图像)
│   │   ├── GET /api/image-gen/config (获取配置)
│   │   ├── POST /api/image-gen/config (更新配置)
│   │   └── POST /api/image-gen/test-connection (测试连接)
│   │
│   ├── 视觉识别相关
│   │   ├── POST /api/vision/recognize (识别图片)
│   │   ├── GET /api/vision/config (获取配置)
│   │   ├── POST /api/vision/config (更新配置)
│   │   └── POST /api/vision/test-connection (测试连接)
│   │
│   ├── 记忆系统相关
│   │   ├── GET /api/memory/config (获取配置)
│   │   ├── POST /api/memory/config (更新配置)
│   │   ├── POST /api/memory/search (检索记忆)
│   │   ├── POST /api/memory/clear (清除记忆)
│   │   └── GET /api/memory/stats (统计信息)
│   │
│   ├── 提示词增强相关
│   │   ├── GET /api/prompt-enhancer/config (获取配置)
│   │   ├── POST /api/prompt-enhancer/config (更新配置)
│   │   ├── POST /api/prompt-enhancer/enhance (增强提示词)
│   │   ├── POST /api/prompt-enhancer/preview (预览效果)
│   │   ├── GET /api/prompt-enhancer/categories (获取分类)
│   │   ├── POST /api/prompt-enhancer/categories (创建分类)
│   │   ├── PUT /api/prompt-enhancer/categories/{path} (更新分类)
│   │   ├── DELETE /api/prompt-enhancer/categories/{path} (删除分类)
│   │   ├── GET /api/prompt-enhancer/presets (获取预设)
│   │   ├── POST /api/prompt-enhancer/presets (创建预设)
│   │   ├── PUT /api/prompt-enhancer/presets/{name} (更新预设)
│   │   ├── DELETE /api/prompt-enhancer/presets/{name} (删除预设)
│   │   └── POST /api/prompt-enhancer/presets/{name}/activate (激活预设)
│   │
│   ├── 表情包相关
│   │   ├── GET /api/emotes/config (获取配置)
│   │   ├── POST /api/emotes/config (更新配置)
│   │   ├── GET /api/emotes/categories (获取分类)
│   │   └── POST /api/emotes/test (测试选择)
│   │
│   ├── 主动聊天相关
│   │   ├── GET /api/proactive/config (获取配置)
│   │   ├── POST /api/proactive/config (更新配置)
│   │   ├── POST /api/proactive/trigger (手动触发)
│   │   └── GET /api/proactive/status (获取状态)
│   │
│   ├── 待办事项相关
│   │   ├── GET /api/daily-habits/config (获取配置)
│   │   ├── POST /api/daily-habits/config (更新配置)
│   │   └── GET /api/daily-habits/status (获取状态)
│   │
│   ├── MCP 插件相关
│   │   ├── GET /api/mcp/plugins (获取插件列表)
│   │   ├── POST /api/mcp/plugins/install (安装插件)
│   │   ├── DELETE /api/mcp/plugins/{name} (卸载插件)
│   │   ├── POST /api/mcp/plugins/{name}/execute (执行工具)
│   │   └── GET /api/mcp/plugins/{name}/tools (获取工具列表)
│   │
│   └── 用户系统相关
│       ├── POST /api/auth/register (注册)
│       ├── POST /api/auth/login (登录)
│       ├── GET /api/user/config (获取个人配置)
│       ├── PUT /api/user/config (更新个人配置)
│       ├── DELETE /api/user/config (重置配置)
│       ├── GET /api/admin/users (列出用户)
│       ├── GET /api/admin/users/{qq_user_id}/config (获取用户配置)
│       └── PUT /api/admin/users/{qq_user_id}/config (更新用户配置)
│
├── 🚀 部署与运行
│   ├── 环境准备
│   │   ├── Python 3.11+
│   │   ├── Node.js 18+
│   │   ├── 虚拟环境创建
│   │   └── 依赖安装
│   │
│   ├── 启动方式
│   │   ├── 一键启动 (start.bat)
│   │   ├── Python 脚本 (run.py)
│   │   └── 分别启动前后端
│   │
│   ├── 访问地址
│   │   ├── 前端界面: http://localhost:3000
│   │   ├── 后端 API: http://localhost:8003
│   │   └── API 文档: http://localhost:8003/docs
│   │
│   └── 生产部署
│       ├── 反向代理 (Nginx/Caddy)
│       ├── 进程管理 (systemd/NSSM)
│       ├── 数据库优化 (PostgreSQL)
│       ├── HTTPS 配置
│       └── 时区设置
│
├── 📊 数据流架构
│   ├── 用户输入
│   │   ├── QQ 消息 (文本/语音/图片)
│   │   ├── 控制台输入
│   │   └── Web 界面输入
│   │
│   ├── 消息处理流程
│   │   ├── 1. 接收消息 (适配器)
│   │   ├── 2. 语音识别 (ASR, 如需要)
│   │   ├── 3. 视觉识别 (Vision, 如需要)
│   │   ├── 4. 记忆检索 (Memory)
│   │   ├── 5. MCP 上下文注入 (MCP)
│   │   ├── 6. LLM 生成回复 (Providers)
│   │   ├── 7. 图像生成 (Image Gen, 如需要)
│   │   ├── 8. 语音合成 (TTS, 如需要)
│   │   ├── 9. 表情包选择 (Emote, 如需要)
│   │   ├── 10. 文本分割 (Text Splitter)
│   │   └── 11. 发送回复 (适配器)
│   │
│   └── 记忆存储流程
│       ├── 短期记忆 (对话轮数)
│       ├── 中期记忆 (对话摘要)
│       └── → 长期记忆 (向量存储)
│
└── 🔧 扩展与开发
    ├── 添加新 LLM 提供商
    ├── 添加新平台适配器
    ├── 添加新 TTS 提供商
    ├── 添加新图像生成提供商
    ├── 扩展文本分割器
    ├── 扩展提示词增强器
    ├── 扩展表情包系统
    ├── 扩展主动聊天功能
    └── 开发自定义 MCP 插件
```

---

## 项目核心特点总结

### 🎯 项目定位
- **类型**：全功能 AI 聊天陪伴机器人系统
- **架构**：前后端分离 (FastAPI + React)
- **特色**：多模态 AI 能力、虚拟伴侣体验、插件化扩展

### 💡 核心优势
1. **多模态集成**：文本、语音、图像、视觉识别一体化
2. **智能记忆系统**：三层记忆架构，支持长期记忆和检索
3. **插件化架构**：MCP 插件系统，易于扩展功能
4. **多平台支持**：QQ 机器人、控制台、Web 界面
5. **用户系统**：多用户独立配置，支持管理员管理
6. **可视化配置**：完整的 Web 管理界面，无需编辑配置文件

### 🚀 主要功能
- ✅ AI 对话聊天（多 LLM 提供商）
- ✅ TTS 语音合成（启航AI）
- ✅ ASR 语音识别（硅基流动）
- ✅ 图像生成（魔搭社区、云舞）
- ✅ 视觉识别（魔搭社区）
- ✅ 记忆系统（短期/中期/长期）
- ✅ 文本分割器
- ✅ 提示词增强器
- ✅ 表情包系统
- ✅ 主动聊天
- ✅ 待办事项提醒
- ✅ MCP 插件系统
- ✅ 用户管理系统

### 📊 技术亮点
- 异步架构（FastAPI + asyncio）
- 实时通信（WebSocket）
- 向量检索（ChromaDB）
- 类型安全（TypeScript）
- 现代化 UI（Ant Design 6）
- 插件化设计（MCP）

---

**创建时间**：2026年1月12日  
**项目名称**：LFBot - AI 聊天陪伴机器人  
**项目路径**：E:\MyProject\01_oldTa
