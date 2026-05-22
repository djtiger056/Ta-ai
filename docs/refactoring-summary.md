# 主动消息系统重构总结

## 重构目标

将基于时间窗口的主动消息系统整合到情绪系统中，移除冗余代码，简化架构。

## 架构变化

### 旧架构（已废弃）
```
主动消息触发方式：
├── 时间窗口触发（time_windows）
│   ├── 每天固定时间段（如 8:00-10:00）
│   ├── 随机时间点
│   └── 每日消息上限
├── 行为规则触发（behavior_rules）
│   ├── 长期未聊问候（inactive_greeting）
│   └── 话题未完续聊（conversation_follow_up）
└── 手动触发（trigger_once）
```

### 新架构（当前）
```
主动消息触发方式：
└── 情绪动机触发（cerebellum）
    ├── 情绪达到阈值（action_threshold: 0.68）
    ├── 动机冷却机制（motivation_cooldown: 1800s）
    └── 全局冷却机制（global_cooldown: 1800s）
```

## 已删除的功能

### 前端
- ✅ **删除**：`frontend/src/pages/ProactiveChatPage.tsx`（主动聊天配置页面）
- ✅ **删除**：`/proactive` 路由和菜单项
- ✅ **整合**：主动消息配置（提示词、模板、生图）整合到情绪系统页面

### 后端
- ⚠️ **保留但简化**：`ProactiveChatScheduler`
  - 保留原因：
    1. 接收小脑动机信号（`handle_motivation_signal`）
    2. 管理 Web 消息队列（`poll_pending_messages`）
    3. 记录用户/助手活动（`record_user_activity`）
  - 已废弃功能：
    - 时间窗口调度（`_resolve_time_windows`）
    - 行为规则检查（`_check_behavior_rules`）
    - 定时 Tick 循环（`_tick`）

### 配置文件
- ⚠️ **保留但部分废弃**：`config.yaml` 中的 `proactive_chat` 配置
  - 仍在使用：
    - `default_prompt`：默认提示词
    - `message_templates`：话术模板
    - `image_generation`：主动生图配置
  - 已废弃（不再生效）：
    - `enabled`：由 `cerebellum.enabled` 替代
    - `check_interval_seconds`：不再需要定时检查
    - `time_windows`：时间窗口配置
    - `behavior_rules`：行为规则配置
    - `targets`：目标用户配置（由适配器管理）

## 保留的功能

### 1. 动机信号处理
```python
# backend/core/proactive/scheduler.py
async def handle_motivation_signal(self, signal: MotivationSignal) -> bool:
    """接收小脑动机信号并转化为主动消息"""
    # 1. 检查全局冷却
    # 2. 构建提示词（包含动机上下文）
    # 3. 调用 Bot 生成回复
    # 4. 发送消息
```

### 2. 提示词构建
```python
# backend/core/proactive/message_builder.py
def build_instruction(
    target: Dict[str, Any],
    motivation_context: Optional[Dict[str, Any]] = None,
) -> str:
    """构建主动聊天的 instruction"""
    # 基础提示词 + 动机上下文
    # 当前小脑动机：分享
    # 当前主导情绪：喜悦（强度 0.72）
    # 动机描述：情绪明亮，想把当下的开心分享给用户
```

### 3. Web 消息队列
```python
# backend/core/proactive/web_queue.py
def enqueue_message(state: ProactiveTargetState, payload, now: datetime):
    """将主动消息加入队列，供前端轮询"""

def poll_messages(state: Optional[ProactiveTargetState], limit: int):
    """前端轮询获取主动消息"""
```

### 4. 活动记录
```python
# backend/api/proactive.py
def record_user_activity(channel, user_id, session_id, message):
    """记录用户活动，同时提交到小脑作为刺激"""

def record_assistant_activity(channel, user_id, session_id, message):
    """记录助手活动"""
```

## 配置迁移指南

### 旧配置（已废弃）
```yaml
proactive_chat:
  enabled: true  # ❌ 废弃，使用 cerebellum.enabled
  check_interval_seconds: 60  # ❌ 废弃
  targets:  # ❌ 废弃
    - channel: qq_private
      user_id: "123456"
      time_windows:  # ❌ 废弃
        - start: "08:00"
          end: "10:00"
          max_messages: 1
  behavior_rules:  # ❌ 废弃
    enabled: true
    inactive_greeting:
      enabled: true
      after_seconds: 21600
```

### 新配置（推荐）
```yaml
cerebellum:
  enabled: true  # ✅ 启用情绪系统
  action_threshold: 0.68  # ✅ 动机触发阈值
  motivation_cooldown_seconds: 1800  # ✅ 动机冷却时间
  replace_time_windows: true  # ✅ 替代时间窗口（默认）

proactive_chat:
  default_prompt: "主动问候"  # ✅ 仍在使用
  message_templates:  # ✅ 仍在使用
    - "今天过得怎么样呀？"
    - "想你了，在干嘛呢？"
  image_generation:  # ✅ 仍在使用
    enabled: true
    max_per_day: 3
```

## 前端变化

### 情绪系统页面新增功能
```typescript
// frontend/src/pages/CerebellumPage.tsx

// 新增：主动消息配置面板
<Card title="主动消息配置">
  <Form>
    <Form.Item label="默认提示词" name="default_prompt">
      <TextArea />
    </Form.Item>
    <Form.Item label="话术模板" name="message_templates_text">
      <TextArea />
    </Form.Item>
    <Form.Item label="启用主动生图" name="image_generation_enabled">
      <Switch />
    </Form.Item>
  </Form>
</Card>
```

### 删除的页面
- ❌ `ProactiveChatPage.tsx`：完整的主动聊天配置页面
- ❌ `/proactive` 路由
- ❌ 侧边栏"主动聊天"菜单项

## 数据流对比

### 旧流程（时间窗口）
```
定时器 Tick (每 60 秒)
  ↓
检查时间窗口（8:00-10:00）
  ↓
随机选择时间点
  ↓
构建提示词
  ↓
生成并发送消息
```

### 新流程（情绪驱动）
```
用户发送消息
  ↓
情绪系统接收刺激
  ↓
情绪值变化（joy +0.15）
  ↓
每 30 秒 Tick 检查
  ↓
joy ≥ 0.68 → 生成"分享"动机
  ↓
检查冷却期（30 分钟）
  ↓
构建提示词（包含动机上下文）
  ↓
生成并发送消息
```

## 优势对比

| 特性 | 旧方式（时间窗口） | 新方式（情绪驱动） |
|------|-------------------|-------------------|
| **触发时机** | 固定时间段 | 情绪达到阈值 |
| **自然度** | 机械、可预测 | 自然、不可预测 |
| **上下文感知** | 无 | 基于情绪状态 |
| **频率控制** | 每日上限 | 动机冷却 + 全局冷却 |
| **配置复杂度** | 高（多时间段、多用户） | 低（全局阈值） |
| **可视化** | 无 | 实时情绪图表 |
| **扩展性** | 难（需添加规则） | 易（调整情绪参数） |

## 测试建议

### 1. 验证情绪触发
```bash
# 1. 启用情绪系统
curl -X POST http://localhost:8003/api/cerebellum/config \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'

# 2. 发送正面消息触发 joy 情绪
# 在聊天界面发送："太开心了！谢谢你！"

# 3. 观察情绪系统页面
# joy 情绪应该上升，达到 0.68 后触发"分享"动机

# 4. 检查主动消息
# 应该在 Web 聊天页面收到主动消息
```

### 2. 验证冷却机制
```bash
# 1. 触发第一次主动消息（如上）
# 2. 立即再次发送正面消息
# 3. 观察动机状态应为 "cooldown"
# 4. 等待 30 分钟后再次触发
```

### 3. 验证配置整合
```bash
# 1. 打开情绪系统页面
# 2. 点击"主动消息配置"按钮
# 3. 修改默认提示词和话术模板
# 4. 保存配置
# 5. 触发主动消息，验证新配置生效
```

## 回滚方案

如果需要回滚到旧的时间窗口方式：

1. **禁用情绪系统**：
   ```yaml
   cerebellum:
     enabled: false
     replace_time_windows: false
   ```

2. **启用主动聊天**：
   ```yaml
   proactive_chat:
     enabled: true
     targets:
       - channel: qq_private
         user_id: "123456"
         time_windows:
           - start: "08:00"
             end: "10:00"
   ```

3. **恢复前端页面**：
   - 从 Git 历史恢复 `ProactiveChatPage.tsx`
   - 恢复 `/proactive` 路由和菜单项

## 后续优化建议

1. **完全移除时间窗口代码**：
   - 删除 `scheduler.py` 中的 `_resolve_time_windows`、`_tick` 等方法
   - 删除 `models.py` 中的 `WindowState` 类
   - 简化 API 端点

2. **增强情绪系统**：
   - 添加更多情绪类型（如"期待"、"焦虑"）
   - 支持情绪组合触发（如"悲伤+疲倦"）
   - 添加情绪历史分析

3. **优化提示词构建**：
   - 根据情绪强度调整语气
   - 根据动机类型选择不同模板
   - 支持多轮对话上下文

4. **前端增强**：
   - 添加情绪阈值可视化调整
   - 添加动机历史记录查看
   - 添加主动消息效果统计

## 总结

本次重构成功将主动消息系统从"基于规则的定时触发"升级为"基于情绪的自然触发"，大幅提升了 AI 伴侣的真实感和自然度。同时简化了配置和代码结构，为后续功能扩展奠定了基础。

**核心改进**：
- ✅ 移除了复杂的时间窗口配置
- ✅ 移除了冗余的前端页面
- ✅ 整合了配置到情绪系统页面
- ✅ 保留了必要的基础设施（消息队列、活动记录）
- ✅ 提供了清晰的配置迁移指南

**用户体验提升**：
- 主动消息更自然、更符合情境
- 配置更简单、更直观
- 可视化更丰富、更实时
