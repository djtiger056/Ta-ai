# 需求文档：小脑情感引擎 (Cerebellum Emotion Engine)

## 简介

为现有 AI 情感陪伴聊天机器人增加一个"小脑"模块——一个轻量级、持续运行的情绪与动机引擎。区别于 LLM "大脑"负责复杂对话生成，小脑模块 7×24 小时不间断运行，模拟人类基本情绪波动和简单动机，为机器人赋予真实感和主动性。

该模块的核心价值在于：将现有基于规则的主动消息调度替换为由情感动机自然驱动的主动行为系统。情绪状态将影响主动消息的触发时机、内容风格和频率，并通过前端可视化页面实时展示 AI 的"内心世界"。

## 术语表

- **Cerebellum_Engine**：小脑情感引擎后端服务，负责情绪状态机运算、动机生成和主动行为驱动
- **Emotion_State_Machine**：情绪状态机，管理六种基本情绪（喜悦、愤怒、悲伤、愉悦、惊讶、疲倦）之间的转换
- **Motivation_System**：动机系统，基于情绪状态和时间因素生成行为动机信号
- **Emotion_State**：情绪状态数据结构，包含当前各情绪类型的强度值和主导情绪标识
- **Motivation_Signal**：动机信号，由动机系统输出的行为驱动信号，包含动机类型、强度和建议行为
- **Emotion_Visualizer**：前端情感动机可视化页面组件
- **Proactive_Scheduler**：现有主动聊天调度器模块（backend/core/proactive/scheduler.py）
- **Tick_Interval**：小脑引擎每次状态更新的时间间隔（单位：秒）
- **Emotion_Intensity**：情绪强度，取值范围 0.0 到 1.0 的浮点数
- **Decay_Rate**：情绪衰减速率，控制情绪随时间自然回落至基线的速度
- **Baseline_Value**：情绪基线值，情绪在无刺激时趋向的平衡点
- **External_Stimulus**：外部刺激，来自用户交互或系统事件的情绪触发因素
- **Action_Threshold**：行动阈值，Motivation_Signal 强度超过此值时触发主动行为
- **Circadian_Profile**：昼夜节律配置，定义一天中不同时段对情绪基线的影响

## 需求

### 需求 1：情绪状态机核心运算

**用户故事：** 作为 AI 聊天机器人的运营者，我希望机器人拥有持续运行的情绪状态机，以便机器人能模拟真实的情绪波动，增强用户的陪伴体验。

#### 验收标准

1. THE Cerebellum_Engine SHALL 维护一个包含六种基本情绪（喜悦、愤怒、悲伤、愉悦、惊讶、疲倦）的状态机，每种情绪具有独立的 Emotion_Intensity 值
2. WHEN Tick_Interval 到达时，THE Emotion_State_Machine SHALL 根据当前 Emotion_Intensity 和 Decay_Rate 计算新的情绪强度值
3. WHILE 无 External_Stimulus 输入时，THE Emotion_State_Machine SHALL 以配置的 Decay_Rate 将所有情绪强度逐步衰减至各自的 Baseline_Value
4. WHEN External_Stimulus 到达时，THE Emotion_State_Machine SHALL 根据刺激类型和强度更新对应情绪的 Emotion_Intensity
5. THE Cerebellum_Engine SHALL 在每次 Tick 完成后输出包含所有情绪强度值和主导情绪标识的 Emotion_State
6. IF 多种情绪的 Emotion_Intensity 相同且均为最高值，THEN THE Emotion_State_Machine SHALL 选择最近被激活的情绪作为主导情绪

### 需求 2：情绪自然波动与昼夜节律

**用户故事：** 作为用户，我希望 AI 伴侣的情绪不是完全静止的，而是像真人一样有自然的情绪起伏和作息规律，以便感受到更真实的陪伴。

#### 验收标准

1. THE Cerebellum_Engine SHALL 根据当前时间和配置的 Circadian_Profile 调整各情绪的 Baseline_Value
2. WHILE 处于 Circadian_Profile 定义的夜间时段时，THE Emotion_State_Machine SHALL 将疲倦情绪的 Baseline_Value 提升至配置的夜间基线
3. WHILE 处于 Circadian_Profile 定义的白天活跃时段时，THE Emotion_State_Machine SHALL 以配置的概率和幅度产生随机情绪微波动
4. THE Cerebellum_Engine SHALL 支持通过 config.yaml 的 cerebellum.circadian 配置节设定时段边界、基线调整值和波动参数
5. WHEN 系统启动时，THE Cerebellum_Engine SHALL 根据当前时间和 Circadian_Profile 初始化合理的情绪基线状态

### 需求 3：动机系统与主动消息驱动

**用户故事：** 作为 AI 聊天机器人的运营者，我希望小脑能基于情绪状态产生行为动机并直接驱动主动消息的发送，以便机器人的主动行为更加自然且有情感依据。

#### 验收标准

1. THE Motivation_System SHALL 在每次 Tick 时基于当前 Emotion_State 评估并生成 Motivation_Signal
2. WHEN 喜悦或愉悦情绪的 Emotion_Intensity 超过配置的 Action_Threshold 时，THE Motivation_System SHALL 生成"想分享"类型的 Motivation_Signal
3. WHEN 悲伤情绪的 Emotion_Intensity 超过配置的 Action_Threshold 时，THE Motivation_System SHALL 生成"想倾诉"类型的 Motivation_Signal
4. WHEN 疲倦情绪的 Emotion_Intensity 超过配置的 Action_Threshold 时，THE Motivation_System SHALL 生成"想休息"类型的 Motivation_Signal
5. WHEN 惊讶情绪的 Emotion_Intensity 超过配置的 Action_Threshold 时，THE Motivation_System SHALL 生成"想表达"类型的 Motivation_Signal
6. THE Motivation_System SHALL 为每个 Motivation_Signal 附带动机强度值（0.0 到 1.0）和建议行为描述文本
7. IF Motivation_Signal 强度超过配置的 Action_Threshold，THEN THE Motivation_System SHALL 将该信号推送至 Proactive_Scheduler 触发主动消息发送

### 需求 4：替换现有主动消息触发机制

**用户故事：** 作为 AI 聊天机器人的运营者，我希望现有的基于时间窗口和规则的主动消息触发机制被情感动机系统替代，以便主动消息的发送时机更加自然和拟人化。

#### 验收标准

1. WHEN Motivation_Signal 被推送至 Proactive_Scheduler 时，THE Proactive_Scheduler SHALL 将动机类型、主导情绪和 Emotion_Intensity 纳入消息生成指令
2. THE Cerebellum_Engine SHALL 替代现有 Proactive_Scheduler 中基于 time_windows 的定时触发逻辑，改为由 Motivation_Signal 驱动触发
3. WHILE Proactive_Scheduler 构建主动消息指令时，THE Proactive_Scheduler SHALL 在指令中包含当前主导情绪名称、强度值和动机描述
4. THE Cerebellum_Engine SHALL 保留现有 Proactive_Scheduler 的全局冷却机制和发送器注册机制
5. IF Proactive_Scheduler 处于全局冷却期内，THEN THE Motivation_System SHALL 将 Motivation_Signal 标记为待处理状态，待冷却结束后重新评估
6. THE Cerebellum_Engine SHALL 保留现有 Proactive_Scheduler 的 Web 端消息队列功能，主动消息仍通过 poll_pending_messages 接口推送至前端

### 需求 5：外部刺激接口

**用户故事：** 作为 AI 聊天机器人的运营者，我希望用户的聊天行为和系统事件能作为外部刺激影响小脑的情绪状态，以便情绪变化与用户互动相关联。

#### 验收标准

1. WHEN 用户发送消息时，THE Cerebellum_Engine SHALL 接收包含消息情感倾向（正面、负面、中性）和强度的 External_Stimulus
2. WHEN 用户超过配置时长未发送消息时，THE Cerebellum_Engine SHALL 自动生成"被忽略"类型的 External_Stimulus
3. THE Cerebellum_Engine SHALL 提供内部方法供聊天模块和 Proactive_Scheduler 提交 External_Stimulus
4. THE Cerebellum_Engine SHALL 对 External_Stimulus 进行强度归一化处理，单次刺激对情绪的影响增量不超过配置的最大步长值
5. WHEN 收到正面情感倾向的 External_Stimulus 时，THE Cerebellum_Engine SHALL 增加喜悦和愉悦情绪的 Emotion_Intensity
6. WHEN 收到负面情感倾向的 External_Stimulus 时，THE Cerebellum_Engine SHALL 增加悲伤情绪的 Emotion_Intensity
7. THE Cerebellum_Engine SHALL 使用轻量级关键词匹配或规则判断消息情感倾向，不调用 LLM 推理

### 需求 6：轻量化与低耗能运行

**用户故事：** 作为系统运维人员，我希望小脑模块占用极少的计算资源，以便它能在现有服务器上 7×24 小时持续运行而不影响其他服务。

#### 验收标准

1. THE Cerebellum_Engine SHALL 使用纯 Python 数值运算实现状态机逻辑，不依赖任何 LLM 推理调用或外部 AI 服务
2. THE Cerebellum_Engine SHALL 将 Tick_Interval 默认配置为 30 秒，最小允许值为 10 秒
3. THE Cerebellum_Engine SHALL 单次 Tick 运算耗时不超过 50 毫秒
4. THE Cerebellum_Engine SHALL 运行时额外内存占用不超过 50MB
5. THE Cerebellum_Engine SHALL 以 asyncio 协程方式运行，与现有 FastAPI 事件循环共享进程

### 需求 7：情绪状态持久化与恢复

**用户故事：** 作为系统运维人员，我希望小脑的情绪状态在服务重启后能恢复，以便机器人的情绪连续性不被中断。

#### 验收标准

1. THE Cerebellum_Engine SHALL 以配置的间隔（默认 300 秒）将当前 Emotion_State 持久化到本地 JSON 文件
2. WHEN 系统启动时，THE Cerebellum_Engine SHALL 从持久化文件加载上次保存的 Emotion_State
3. IF 持久化文件不存在或 JSON 解析失败，THEN THE Cerebellum_Engine SHALL 使用默认 Baseline_Value 初始化所有情绪状态并记录警告日志
4. WHEN 从持久化文件恢复状态时，THE Cerebellum_Engine SHALL 根据保存时间戳与当前时间的差值，按 Decay_Rate 补偿情绪衰减

### 需求 8：配置管理

**用户故事：** 作为 AI 聊天机器人的运营者，我希望能通过配置文件灵活调整小脑的各项参数，以便根据不同角色人设定制情绪行为。

#### 验收标准

1. THE Cerebellum_Engine SHALL 从项目 config.yaml 文件的 cerebellum 配置节读取所有运行参数
2. THE Cerebellum_Engine SHALL 支持通过 POST /api/cerebellum/config 接口热更新配置参数而无需重启服务
3. THE Cerebellum_Engine SHALL 提供以下可配置项：tick_interval、decay_rate、circadian 时段配置、各情绪的 baseline_value、action_threshold、持久化间隔、最大刺激步长
4. IF 配置参数值超出合理范围（如 tick_interval 小于 10 或 decay_rate 为负数），THEN THE Cerebellum_Engine SHALL 使用默认值替代并记录警告日志

### 需求 9：状态查询 API

**用户故事：** 作为前端开发者，我希望能通过 REST API 和 WebSocket 获取小脑的实时情绪状态和动机信息，以便在前端进行可视化展示。

#### 验收标准

1. THE Cerebellum_Engine SHALL 提供 GET /api/cerebellum/state 接口返回当前完整的 Emotion_State（包含所有情绪强度值和主导情绪标识）
2. THE Cerebellum_Engine SHALL 提供 GET /api/cerebellum/motivation 接口返回当前活跃的 Motivation_Signal 列表
3. THE Cerebellum_Engine SHALL 提供 GET /api/cerebellum/history 接口返回指定时间范围内的情绪变化记录
4. WHEN API 请求到达时，THE Cerebellum_Engine SHALL 在 100 毫秒内返回响应
5. THE Cerebellum_Engine SHALL 提供 WebSocket /ws/cerebellum/stream 端点，在每次 Tick 完成后向已连接的客户端推送最新 Emotion_State

### 需求 10：前端情感动机可视化

**用户故事：** 作为用户，我希望能在前端页面看到 AI 伴侣当前的情绪状态和动机，以便更直观地感受 AI 的"内心世界"。

#### 验收标准

1. THE Emotion_Visualizer SHALL 以雷达图或环形图展示当前六种情绪的 Emotion_Intensity 分布
2. THE Emotion_Visualizer SHALL 通过 WebSocket 连接接收实时状态推送，显示延迟不超过 Tick_Interval 的两倍
3. THE Emotion_Visualizer SHALL 展示当前活跃的 Motivation_Signal 列表，包含动机类型和强度指示
4. THE Emotion_Visualizer SHALL 提供情绪变化趋势的时间线图表，展示过去可配置时间段（默认 24 小时）内的情绪波动曲线
5. THE Emotion_Visualizer SHALL 以独立页面形式集成到现有前端路由中，路径为 /cerebellum
6. THE Emotion_Visualizer SHALL 采用响应式布局，在移动端（宽度 320px 以上）和桌面端均可正常显示和交互
