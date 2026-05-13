# Design Document

## Overview

本设计文档描述记忆系统优化的技术实现方案。变更范围小且集中，涉及配置值调整、Pydantic 模型字段补全、以及两处 prompt 措辞重写。核心目标是让 AI 更自然地运用记忆内容，同时提升 RAG 召回率和中期摘要注入深度。

## Architecture

本次优化不引入新的架构组件，仅对现有记忆注入管线进行参数调优和措辞改进：

```
config.yaml (memory section)
    │
    ▼
Config → MemoryConfig (Pydantic model)
    │
    ├─→ _build_memory_context()  [长期记忆注入]
    │       ├─ RAG 检索 (rag_score_threshold: 0.6)
    │       └─ Prompt 措辞 (自然化)
    │
    └─→ _append_mid_term_context()  [中期摘要注入]
            ├─ 摘要数量 (mid_term_context_count: 5)
            └─ Prompt 措辞 (连续性)
```

## Components and Interfaces

### 1. Config_YAML 参数调整

**文件**: `config.yaml` → `memory` 节

| 参数 | 旧值 | 新值 | 说明 |
|------|------|------|------|
| `rag_score_threshold` | 0.72 | 0.6 | 降低阈值以提升召回率 |
| `mid_term_context_count` | 2 | 5 | 增加中期摘要注入数量 |

### 2. MemoryConfig 模型补全

**文件**: `backend/memory/models.py`

新增字段定义：

```python
mid_term_context_count: int = Field(default=5, description="注入LLM上下文的中期摘要条数")
```

该字段此前在 `config.yaml` 中已存在但未在 Pydantic 模型中正式定义，导致代码中使用 `getattr` 兜底访问。补全后可获得类型校验、默认值和 JSON Schema 文档支持。

### 3. Memory_Injector 措辞重写

**文件**: `backend/core/bot.py` → `_build_memory_context()` 方法

重写返回的 prompt 前缀，从当前的"可参考的关系记忆"风格改为更自然的"你记得的关于对方的事"风格：

```python
return (
    "你记得关于对方的这些事（这是你自己的记忆，不要说"根据记忆"，"
    "像真正记得一样自然地在相关时提及，不要逐条列举，不相关就不提）：\n"
    + "\n".join(selected_lines)
)
```

关键措辞原则：
- 将记忆定位为"你自己记得的事"而非"可参考的信息"
- 明确禁止元引用（"根据记忆"、"我记得你说过"等）
- 鼓励主动关联但不强制引用
- 禁止逐条列举式回复

### 4. MidTerm_Injector 措辞重写与配置直连

**文件**: `backend/core/bot.py` → `_append_mid_term_context()` 方法

#### 4.1 配置访问方式改进

将 `getattr` 兜底改为直接属性访问：

```python
# 旧代码
count = int(getattr(config.memory_config, "mid_term_context_count", 0) or 0)

# 新代码
count = config.memory_config.mid_term_context_count
```

由于 `mid_term_context_count` 已在 MemoryConfig 中定义为 `int` 类型且有默认值，不再需要 `getattr` 和类型转换兜底。

#### 4.2 Prompt 措辞重写

重写中期摘要注入的 prompt 前缀：

```python
context = (
    "你对最近和对方聊过的内容有印象（以下是你的回忆片段）。"
    "如果当前话题和之前聊过的有关，可以自然地接续；"
    "不要原文复述这些内容，不相关就不提：\n"
    + "\n".join(lines)
)
```

关键措辞原则：
- 将摘要定位为"你的回忆片段"而非"对话摘要"
- 强调话题连续性和自然接续
- 禁止原文复述
- 不相关时允许忽略

### 接口说明

#### MemoryConfig 接口变更

```python
class MemoryConfig(BaseModel):
    # ... 现有字段 ...
    mid_term_context_count: int = Field(default=5, description="注入LLM上下文的中期摘要条数")
    # ... 其余字段不变 ...
```

#### _build_memory_context 签名不变

```python
def _build_memory_context(self, relevant_memories: List[Dict[str, Any]],
                          history: List[Dict[str, str]], limit: int = 3) -> str:
```

输入输出接口不变，仅内部 prompt 文本变更。

#### _append_mid_term_context 签名不变

```python
async def _append_mid_term_context(self, enhanced_history: List[Dict[str, str]],
                                   user_id: str, session_id: str):
```

输入输出接口不变，内部配置访问方式和 prompt 文本变更。

## Data Models

### MemoryConfig 字段新增

| 字段名 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| `mid_term_context_count` | `int` | `5` | 注入 LLM 上下文的中期摘要条数 |

该字段插入位置建议在 `rag_score_threshold` 之后，与其他 RAG/检索相关配置相邻。

### config.yaml 变更

```yaml
memory:
  rag_score_threshold: 0.6        # 从 0.72 降低
  mid_term_context_count: 5       # 从 2 增加
  # 其余字段不变
```

## Error Handling

### 配置加载容错

- `MemoryConfig` 使用 Pydantic 的 `Field(default=5)` 确保即使 YAML 中缺失该字段也有合理默认值
- `mid_term_context_count` 定义为 `int` 类型，Pydantic 会自动进行类型校验和转换

### _append_mid_term_context 容错

- 当 `mid_term_context_count <= 0` 时直接返回，不执行摘要查询
- 摘要查询失败时 catch exception 并打印错误，不影响主流程
- 空摘要列表时直接返回

### _build_memory_context 容错

- 空 `relevant_memories` 列表时返回空字符串
- 单条记忆内容为空时跳过
- 与近期对话重复的记忆被过滤

## Testing Strategy

### 单元测试（Example-based）

- 验证 `MemoryConfig` 默认值：`rag_score_threshold` 为 0.6，`mid_term_context_count` 为 5
- 验证 `_build_memory_context()` 返回的 prompt 包含关键措辞指令
- 验证 `_append_mid_term_context()` 返回的 prompt 包含关键措辞指令
- 验证 `_append_mid_term_context()` 中不再使用 `getattr` 访问 `mid_term_context_count`
- 验证 config.yaml 中 `rag_score_threshold` 和 `mid_term_context_count` 的值

### 属性测试（Property-based）

- RAG 阈值过滤：生成随机相似度分数的记忆条目，验证过滤结果一致性
- 空输入安全性：对任意 history 和 limit 参数，空记忆列表始终返回空字符串
- 摘要数量上限：对任意 count 值和摘要列表，注入数量不超过配置值

### 集成测试

- 前端配置页面能正确读写 `mid_term_context_count` 字段

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: RAG 阈值过滤保证

*For any* set of memory items with varying similarity scores and *for any* configured `rag_score_threshold` value T, all memory items returned by RAG retrieval SHALL have a similarity score >= T, and no item with similarity < T SHALL appear in the results.

**Validates: Requirements 1.2**

### Property 2: 空记忆输入产生空上下文

*For any* call to `_build_memory_context` where `relevant_memories` is an empty list, the returned string SHALL be empty (length 0), regardless of the `history` or `limit` parameters.

**Validates: Requirements 2.5**

### Property 3: 中期摘要注入数量上限

*For any* configured `mid_term_context_count` value N (where N > 0) and *for any* available set of summaries S, the MidTerm_Injector SHALL inject at most N summaries into the LLM context, i.e., the number of summary items in the injected context SHALL be <= min(N, |S|).

**Validates: Requirements 3.2**
