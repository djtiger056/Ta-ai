# 情绪系统 (Cerebellum Emotion Engine)

## 概述

情绪系统是一个轻量级、持续运行的情绪与动机引擎，区别于 LLM "大脑"负责复杂对话生成，它 7×24 小时不间断运行，模拟人类基本情绪波动和简单动机，为 AI 伴侣赋予真实感和主动性。

**核心价值**：
- 将基于规则的主动消息调度替换为由情感动机自然驱动的主动行为系统
- 情绪状态影响主动消息的触发时机、内容风格和频率
- 前端可视化实时展示 AI 的"内心世界"

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI 主线程                           │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │ REST API    │    │ WebSocket    │    │ ProactiveScheduler│   │
│  │ /api/cereb-*│    │ /ws/cereb-*  │    │ handle_motivation │   │
│  └──────┬──────┘    └──────┬───────┘    └─────────┬────────┘   │
│         │                  │                      │             │
│         └──────────────────┼──────────────────────┘             │
│                            │ 跨线程安全通信                       │
│                            ▼                                     │
├─────────────────────────────────────────────────────────────────┤
│                      后台线程 (asyncio 事件循环)                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   CerebellumEngine                       │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │   │
│  │  │ 情绪状态机   │  │ 动机系统    │  │ 外部刺激处理器   │  │   │
│  │  │ 6种基本情绪  │  │ 5种动机类型  │  │ 用户消息/系统事件│  │   │
│  │  │ 指数衰减    │  │ 冷却机制    │  │ 关键词情感分析   │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │   │
│  │                                                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │   │
│  │  │ 昼夜节律    │  │ 状态持久化  │  │ WebSocket 推送   │  │   │
│  │  │ 夜间疲倦    │  │ JSON 文件   │  │ call_soon_*     │  │   │
│  │  │ 白天波动    │  │ 衰减补偿    │  │ 跨线程安全      │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. 情绪状态机 (Emotion State Machine)

管理六种基本情绪，每种情绪具有独立的强度值（0.0 ~ 1.0）：

| 情绪 | 英文 Key | 默认基线 | 说明 |
|------|----------|----------|------|
| 喜悦 | joy | 0.32 | 正面互动、开心消息触发 |
| 愤怒 | anger | 0.08 | 边界被触碰、负面互动 |
| 悲伤 | sadness | 0.14 | 被忽略、负面消息 |
| 愉悦 | pleasure | 0.28 | 温馨互动、被关心 |
| 惊讶 | surprise | 0.12 | 意外事件、惊喜消息 |
| 疲倦 | fatigue | 0.22 | 夜间时段、长时间运行 |

**衰减公式**（指数衰减）：
```
factor = 1 - (1 - decay_rate) ^ ticks_equivalent
new_intensity = current + (baseline - current) × factor
```

**主导情绪判定**：
- 强度最高的情绪为主导情绪
- 平局时选择最近被触发的情绪

### 2. 动机系统 (Motivation System)

基于情绪状态生成行为动机信号：

| 情绪条件 | 动机类型 | 动机标签 | 建议行为 |
|----------|----------|----------|----------|
| joy/pleasure ≥ threshold | share | 想分享 | 发送轻松分享或关心近况的消息 |
| sadness ≥ threshold | confide | 想倾诉 | 发送不施压的倾诉式问候 |
| fatigue ≥ threshold | rest | 想休息 | 发送短消息，语气柔和克制 |
| surprise ≥ threshold | express | 想表达 | 发送带有即时感的小感叹 |
| anger ≥ threshold | express_boundary | 想表达边界 | 发送温和但有边界的消息 |

**动机冷却机制**：
- 成功推送动机后进入冷却期（默认 1800 秒）
- 冷却期内新动机标记为 `cooldown` 状态，不触发主动消息

### 3. 外部刺激处理器 (External Stimulus Handler)

接收并处理来自用户交互和系统事件的外部刺激：

**刺激来源**：
- 用户消息：自动提取情感倾向（正面/负面/中性）
- 系统事件：用户长时间未活跃触发"被忽略"刺激

**情感分析**：
- 使用外部词典文件 `backend/data/sentiment_words.yaml`
- 纯关键词匹配，不调用 LLM
- 支持中英文关键词，可扩展

**刺激影响映射**：
| 情感倾向 | 影响情绪 | 增量公式 |
|----------|----------|----------|
| positive | joy, pleasure | `step × intensity` |
| negative | sadness, anger | `step × intensity` |
| surprise | surprise | `step × intensity` |
| ignored | sadness, fatigue | `step × intensity` |

### 4. 昼夜节律 (Circadian Rhythm)

模拟真人的作息规律：

**夜间时段（默认 23:00 ~ 06:00）**：
- 疲倦基线提升至 0.58
- 喜悦、愉悦基线略微下降

**白天活跃时段（默认 08:00 ~ 22:00）**：
- 以 35% 概率产生随机情绪微波动
- 波动幅度 ±0.05

### 5. 主动消息集成

情绪系统与 `ProactiveChatScheduler` 集成：

```python
# main.py 中的初始化
cerebellum_engine = CerebellumEngine(
    proactive_dispatcher=proactive_scheduler.handle_motivation_signal
)
```

**触发流程**：
1. 小脑 Tick 评估情绪 → 生成 MotivationSignal
2. 通过 `proactive_dispatcher` 推送到 ProactiveScheduler
3. ProactiveScheduler 构建指令（包含动机上下文）
4. 调用 Bot 生成回复并发送

**指令增强**：
```
当前小脑动机：想分享
当前主导情绪：喜悦（强度 0.85）
动机描述：情绪明亮，想把当下的开心分享给用户。
```

## 配置说明

### config.yaml 配置节

```yaml
cerebellum:
  # 是否启用情绪系统
  enabled: true
  
  # Tick 间隔（秒），最小 10，最大 86400
  tick_interval: 30
  
  # 衰减速率（每 Tick 衰减比例），0.0 ~ 1.0
  decay_rate: 0.015
  
  # 动机触发阈值，情绪强度超过此值才生成动机
  action_threshold: 0.68
  
  # 状态持久化间隔（秒）
  persistence_interval: 300
  
  # 状态文件路径
  state_file: "data/cerebellum_state.json"
  
  # 单次刺激最大影响步长
  max_stimulus_step: 0.18
  
  # 历史记录最大条数
  history_limit: 2880
  
  # 是否替换 ProactiveScheduler 的 time_windows 定时触发
  replace_time_windows: true
  
  # 动机冷却时间（秒）
  motivation_cooldown_seconds: 1800
  
  # 各情绪基线值
  baseline_values:
    joy: 0.32
    anger: 0.08
    sadness: 0.14
    pleasure: 0.28
    surprise: 0.12
    fatigue: 0.22
  
  # 昼夜节律配置
  circadian:
    timezone: "Asia/Shanghai"
    night:
      start: "23:00"
      end: "06:00"
      fatigue_baseline: 0.58
      baseline_adjustments:
        joy: -0.04
        pleasure: -0.05
    active:
      start: "08:00"
      end: "22:00"
      micro_wave_probability: 0.35
      micro_wave_amplitude: 0.05
  
  # 用户不活跃刺激
  inactivity_stimulus:
    enabled: true
    after_seconds: 21600  # 6 小时
    intensity: 0.22
```

## API 接口

### REST API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/cerebellum/state` | 获取当前情绪状态快照 |
| GET | `/api/cerebellum/motivation` | 获取当前活跃的动机列表 |
| GET | `/api/cerebellum/history` | 获取情绪历史记录（参数：hours, limit） |
| GET | `/api/cerebellum/config` | 获取当前配置 |
| POST | `/api/cerebellum/config` | 热更新配置（运行时生效，不回写文件） |
| POST | `/api/cerebellum/stimulus` | 手动提交外部刺激 |

### WebSocket

| 路径 | 说明 |
|------|------|
| `/ws/cerebellum/stream` | 实时情绪状态推送（每次 Tick 后推送） |

**推送数据格式**：
```json
{
  "event": "cerebellum.state",
  "payload": {
    "state": {
      "intensities": { "joy": 0.48, "anger": 0.08, ... },
      "dominant_emotion": "joy",
      "dominant_emotion_label": "喜悦",
      "last_updated_at": "2026-05-12T19:34:45+08:00"
    },
    "motivations": [...],
    "enabled": true,
    "running": true
  }
}
```

## 数据结构

### EmotionState

```python
@dataclass
class EmotionState:
    intensities: Dict[str, float]      # 各情绪强度
    baselines: Dict[str, float]         # 各情绪基线
    dominant_emotion: str               # 主导情绪 key
    last_updated_at: datetime           # 最后更新时间
    last_tick_duration_ms: float        # 上次 Tick 耗时
    last_triggered_emotion: Optional[str]  # 最近触发的情绪
```

### MotivationSignal

```python
@dataclass
class MotivationSignal:
    motivation_type: str                # 动机类型
    intensity: float                    # 动机强度
    description: str                    # 动机描述
    suggested_action: str               # 建议行为
    dominant_emotion: str               # 关联的主导情绪
    dominant_emotion_intensity: float   # 主导情绪强度
    status: str                         # 状态：active/dispatched/pending/cooldown
    created_at: Optional[datetime]      # 创建时间
    target_key: Optional[str]           # 目标用户标识
```

### ExternalStimulus

```python
@dataclass
class ExternalStimulus:
    stimulus_type: str                  # 刺激类型
    intensity: float                    # 刺激强度
    valence: str                        # 情感倾向：positive/negative/neutral/surprise
    source: str                         # 来源：user/system/api
    channel: Optional[str]              # 渠道
    user_id: Optional[str]              # 用户 ID
    session_id: Optional[str]           # 会话 ID
    message: str                        # 关联消息
    created_at: Optional[datetime]      # 创建时间
```

## 文件结构

```
backend/
├── core/
│   └── cerebellum/
│       ├── __init__.py          # 模块导出
│       ├── engine.py            # 核心引擎
│       └── models.py            # 数据模型
├── api/
│   └── cerebellum.py            # REST/WebSocket API
└── data/
    ├── cerebellum_state.json    # 持久化状态文件
    └── sentiment_words.yaml     # 情感关键词词典

frontend/
└── src/
    └── pages/
        └── CerebellumPage.tsx   # 可视化页面
```

## 前端可视化

访问路径：`/cerebellum`

**展示内容**：
- 当前情绪分布（环形图 + 进度条）
- 24 小时情绪趋势（折线图）
- 当前活跃动机列表
- 运行状态指标（Tick 间隔、衰减速率、动机阈值、Tick 耗时）
- 启用/关闭开关
- WebSocket 连接状态

**实时更新**：
- 通过 WebSocket 接收每次 Tick 后的状态推送
- 断线后 5 秒自动重连

## 扩展开发指南

### 添加新情绪类型

1. 在 `models.py` 中更新 `EMOTIONS` 元组和 `EMOTION_LABELS` 字典
2. 在 `DEFAULT_BASELINES` 中添加默认基线值
3. 更新 `CerebellumConfigData.baseline_values` 默认值
4. 在 `_apply_stimulus` 中添加情绪影响映射

### 添加新动机类型

1. 在 `models.py` 中更新 `MOTIVATION_LABELS` 字典
2. 在 `engine.py` 的 `_evaluate_motivations` 方法中添加判定逻辑

### 扩展情感词典

编辑 `backend/data/sentiment_words.yaml`：

```yaml
positive:
  - 新关键词1
  - 新关键词2
  
negative:
  - 新关键词1

surprise:
  - 新关键词1
```

### 自定义昼夜节律

在 `config.yaml` 中调整 `cerebellum.circadian` 配置：

```yaml
circadian:
  timezone: "Asia/Shanghai"
  night:
    start: "22:00"
    end: "07:00"
    fatigue_baseline: 0.65
    baseline_adjustments:
      joy: -0.08
      pleasure: -0.06
  active:
    start: "09:00"
    end: "21:00"
    micro_wave_probability: 0.45
    micro_wave_amplitude: 0.08
```

### 集成其他触发源

```python
from backend.core.cerebellum import CerebellumEngine, ExternalStimulus

# 获取引擎实例
engine = get_engine()

# 提交自定义刺激
await engine.submit_stimulus(ExternalStimulus(
    stimulus_type="custom_event",
    intensity=0.5,
    valence="positive",
    source="custom_module",
    message="触发原因描述",
))
```

## 性能指标

| 指标 | 目标值 | 实际值 |
|------|--------|--------|
| 单次 Tick 耗时 | < 50ms | ~0.03ms |
| 内存占用 | < 50MB | ~10MB |
| CPU 占用 | 可忽略 | 每分钟 < 0.1% |

## 故障排查

### WebSocket 显示"连接断开"

1. 检查 `frontend/vite.config.ts` 是否配置了 `/ws` 代理
2. 确认后端服务已启动且 `cerebellum.enabled: true`
3. 查看浏览器控制台是否有 WebSocket 错误

### 情绪不变化

1. 检查 `cerebellum.enabled` 是否为 `true`
2. 检查 `tick_interval` 是否过长
3. 确认用户消息正在触发 `submit_message_stimulus`

### 动机不触发主动消息

1. 检查 `action_threshold` 是否设置过高
2. 检查 `motivation_cooldown_seconds` 是否过长
3. 确认 `proactive_chat.enabled` 为 `true` 且配置了 `targets`
4. 查看 `replace_time_windows` 是否为 `true`

## 版本历史

- **v1.0** - 初始实现：情绪状态机、动机系统、外部刺激、昼夜节律
- **v1.1** - 新增动机冷却机制、指数衰减、WebSocket 重连、情感词典扩展
- **v1.2** - 修复跨线程 WebSocket 推送问题、前端启用开关、更名为"情绪系统"
