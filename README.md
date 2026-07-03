# Ta - AI 伴侣聊天系统

> 一个具备情绪引擎、三层记忆架构、多模态交互能力的 AI 陪伴型聊天机器人。

**技术栈：** Python (FastAPI) + React (TypeScript) + WebSocket + ChromaDB  
**代码规模：** 后端 31,376 行 / 前端 16,189 行

---

## 产品演示


---

## 核心技术能力

### 智能对话引擎
- 多 LLM 提供商支持（OpenAI / SiliconFlow / DeepSeek / Qwen / 云舞等）
- WebSocket 流式响应，实时推送
- 上下文窗口智能管理，支持 1000+ 轮历史

### 小脑情绪引擎
- 7 维情绪状态实时追踪（开心、悲伤、焦虑、兴奋等）
- 情绪自动衰减 + 基线回归机制
- 动机信号触发主动行为（自发消息、图片生成等）
- 昼夜节律自适应调整

### 三层记忆架构
- **短期**：最近 30 轮对话
- **中期**：自动摘要（可配置条数）
- **长期**：ChromaDB 向量检索，支持 1000+ 条记忆持久化

### 多模态交互
| 能力 | 说明 |
|------|------|
| TTS 语音合成 | 启航AI / Qwen TTS，智能分段 |
| ASR 语音识别 | 语音消息转文字 |
| 图像生成 | images-api / ModelScope / GPT Image / Kling 网页模式 |
| 视频生成 | Qwen 视频生成，异步任务队列 |
| 视觉识别 | 图片内容理解与对话融合 |
| 实时语音通话 | WebRTC + 林语 IM 信令 |

### 主动交互系统
- 定时问候 / 空闲检测 / 提醒调度 / 日程生成

### Agent 委派
- 将复杂任务异步委派给 Hermes Agent，完成后自动推送结果到聊天渠道

---

## 系统架构

```
Ta/
├── backend/                    # Python 后端（31k 行）
│   ├── api/                    # 27 个 REST API 模块
│   ├── adapters/               # 平台适配器（林语 IM / QQ / 控制台）
│   ├── core/                   # Bot 核心、上下文构建
│   ├── providers/              # LLM 提供商抽象
│   ├── tts/ asr/               # 语音子系统
│   ├── image_gen/ video_gen/   # 生成子系统
│   ├── vision/                 # 视觉识别
│   ├── voice_call/             # WebRTC 通话
│   ├── memory/                 # 三层记忆系统
│   ├── cerebellum/             # 情绪引擎
│   ├── mcp/                    # 插件系统
│   └── prompt_system/          # 提示词版本管理
├── frontend/                   # React 前端（16k 行，25 个页面）
│   └── src/pages/             # 20+ 功能配置页面
├── data/                       # SQLite + ChromaDB 数据存储
└── user_data/                  # 多用户独立配置
```

---

## 技术亮点

1. **适配器模式** - 同一套业务逻辑，切换聊天平台只需配置适配器
2. **配置合并策略** - 用户配置覆盖全局配置，支持细粒度override
3. **消息防抖** - 多条消息合并处理，减少 LLM 调用成本
4. **提示词版本管理** - 每次变更记录历史，支持回溯
5. **插件化架构** - MCP 插件机制，业务功能可插拔扩展

---

## 快速启动

```bash
# 后端
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python backend/main.py

# 前端构建
cd frontend && npm install && npm run build
```

服务端口：**8003**（生产模式前端由后端直接服务）

---

## 项目亮点总结

| 维度 | 数据 |
|------|------|
| 后端代码行数 | 31,376 |
| 前端代码行数 | 16,189 |
| Python 模块数 | 146 |
| React 页面数 | 25 |
| API 路由模块 | 27 |
| 支持聊天平台 | 林语 IM / QQ / Web |
| 情绪维度 | 7 维 |
| 长期记忆容量 | 1000+ 条向量 |

---

> 本项目为个人全栈开发作品，涵盖 AI 工程、后端架构、前端交互、数据库设计的完整能力体现。
