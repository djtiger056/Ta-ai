# 小脑情感引擎技术设计文档

## 目标与边界

小脑情感引擎（Cerebellum Emotion Engine）作为后端常驻轻量服务运行，负责维护六类基础情绪、根据昼夜节律和外部刺激更新状态、生成动机信号，并把高强度动机推送给现有主动聊天调度器。LLM 仍只负责最终自然语言生成，小脑本身不调用 LLM 或外部 AI 服务。

本次设计采用增量接入方式：新增 `backend/core/cerebellum` 独立模块，新增 `/api/cerebellum/*` 与 `/ws/cerebellum/stream`，并在 `ProactiveChatScheduler` 增加动机信号入口。`cerebellum.enabled=false` 时旧主动聊天时间窗口逻辑保持不变；启用后默认由小脑动机替代 `time_windows` 定时触发。

## 后端架构

### 模块划分

- `backend/core/cerebellum/models.py`：定义 `EmotionState`、`ExternalStimulus`、`MotivationSignal`、配置对象和常量。
- `backend/core/cerebellum/engine.py`：实现状态机 Tick、昼夜节律、自然波动、持久化恢复、历史缓存、WebSocket 广播和动机生成。
- `backend/api/cerebellum.py`：提供 REST API、WebSocket 端点、聊天模块内部刺激提交入口。
- `backend/core/proactive/scheduler.py`：新增 `handle_motivation_signal`、动机指令拼接和冷却期挂起逻辑。

### 数据流

1. 用户发送消息后，聊天/适配器调用 `proactive_api.record_user_activity`，该入口同步把消息以轻量规则转换为 `ExternalStimulus` 提交给小脑。
2. 小脑每个 Tick 根据当前基线、衰减速率、昼夜节律和外部刺激更新 `EmotionState`。
3. Tick 后 `MotivationSystem` 根据阈值生成活跃 `MotivationSignal`。
4. 高于行动阈值的动机信号推送到 `ProactiveChatScheduler.handle_motivation_signal`。
5. 调度器保留全局冷却和发送器注册机制；若冷却中，则把信号挂起到目标状态，冷却结束后重新发送。
6. 前端通过 REST 初始加载，通过 WebSocket 接收实时状态，并用历史接口绘制趋势。

## 情绪状态机

六种情绪固定为：

- `joy`：喜悦
- `anger`：愤怒
- `sadness`：悲伤
- `pleasure`：愉悦
- `surprise`：惊讶
- `fatigue`：疲倦

每个 Tick 对每个情绪执行：

```text
next = current + (baseline - current) * decay_rate * elapsed_seconds
```

结果裁剪到 `[0.0, 1.0]`。如果多种情绪强度并列最高，按最近被刺激激活的情绪作为主导情绪。

昼夜节律在 Tick 前动态计算当前基线：夜间提升 `fatigue` 基线，白天活跃时段按配置概率产生微波动。微波动幅度也受 `max_stimulus_step` 限制。

## 动机系统

动机映射如下：

- `joy` 或 `pleasure` 超过阈值：`share`（想分享）
- `sadness` 超过阈值：`confide`（想倾诉）
- `fatigue` 超过阈值：`rest`（想休息）
- `surprise` 超过阈值：`express`（想表达）
- `anger` 超过阈值：`express_boundary`（想表达边界）

同一 Tick 可生成多个动机信号，主动消息触发选择强度最高的信号。信号包含动机类型、强度、主导情绪、主导情绪强度、描述文本、建议行为和状态（`active` / `pending` / `dispatched`）。

## API 设计

- `GET /api/cerebellum/state`：返回当前 `EmotionState`、配置摘要、运行状态。
- `GET /api/cerebellum/motivation`：返回当前活跃/挂起动机信号列表。
- `GET /api/cerebellum/history?hours=24&limit=500`：返回时间范围内情绪历史。
- `POST /api/cerebellum/stimulus`：提交外部刺激，供内部和调试使用。
- `GET /api/cerebellum/config`：返回当前小脑配置。
- `POST /api/cerebellum/config`：热更新配置并持久化到 `config.yaml`。
- `WebSocket /ws/cerebellum/stream`：连接后立即推送当前状态，每次 Tick 后继续推送最新状态。

## 前端设计

新增独立页面 `frontend/src/pages/CerebellumPage.tsx`，路由 `/cerebellum`，菜单名“情感小脑”。页面包含：

- 六情绪环形/雷达式可视化。
- 主导情绪、Tick 间隔、运行状态摘要。
- 活跃动机信号列表。
- 最近 24 小时情绪趋势折线。
- 移动端 320px 以上响应式布局。

不引入大型图表依赖，使用 CSS/SVG 原生绘制，保持前端轻量。

## 配置默认值

`config.yaml` 的 `cerebellum` 支持：

- `enabled`
- `tick_interval`
- `decay_rate`
- `baseline_values`
- `action_threshold`
- `persistence_interval`
- `state_file`
- `max_stimulus_step`
- `history_limit`
- `replace_time_windows`
- `inactivity_stimulus`
- `circadian`

配置校验失败时使用默认值并记录警告，避免服务启动失败。

## 测试策略

- 单元测试状态机衰减、刺激归一化、主导情绪并列规则、持久化恢复补偿、动机生成。
- 单元测试主动调度器接收动机信号后能构建包含情绪和动机上下文的指令，并保留 Web 队列。
- 编译/类型检查后端与前端，确保新增 API 和页面可构建。
