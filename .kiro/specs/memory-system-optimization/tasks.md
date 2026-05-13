# Implementation Plan: 记忆系统优化 (Memory System Optimization)

## Overview

对记忆系统进行四处针对性修改：调整 config.yaml 参数、补全 MemoryConfig 模型字段、重写长期记忆注入 prompt、重写中期摘要注入 prompt 及配置访问方式。

## Tasks

- [x] 1. 配置与模型层修改
  - [x] 1.1 更新 config.yaml 中 memory 节的参数值
    - 将 `rag_score_threshold` 从 `0.72` 改为 `0.6`
    - 将 `mid_term_context_count` 从 `2` 改为 `5`
    - _Requirements: 1.1, 3.1_

  - [x] 1.2 在 MemoryConfig 中添加 mid_term_context_count 字段定义
    - 在 `backend/memory/models.py` 的 `MemoryConfig` 类中添加：`mid_term_context_count: int = Field(default=5, description="注入LLM上下文的中期摘要条数")`
    - 插入位置在 `rag_score_threshold` 字段之后
    - _Requirements: 4.1, 4.2_

- [x] 2. Bot 核心 prompt 重写
  - [x] 2.1 重写 _build_memory_context() 的 prompt 措辞
    - 在 `backend/core/bot.py` 中，将 `_build_memory_context` 方法末尾的 return 语句中的 prompt 前缀替换为：`"你记得关于对方的这些事（这是你自己的记忆，不要说"根据记忆"，像真正记得一样自然地在相关时提及，不要逐条列举，不相关就不提）：\n"`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 2.2 重写 _append_mid_term_context() 的配置访问和 prompt 措辞
    - 在 `backend/core/bot.py` 中，将 `count = int(getattr(config.memory_config, "mid_term_context_count", 0) or 0)` 替换为 `count = config.memory_config.mid_term_context_count`
    - 移除对应的 `try/except` 兜底块
    - 将 context 的 prompt 前缀替换为：`"你对最近和对方聊过的内容有印象（以下是你的回忆片段）。如果当前话题和之前聊过的有关，可以自然地接续；不要原文复述这些内容，不相关就不提：\n"`
    - _Requirements: 4.3, 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 3. Checkpoint - 验证修改
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 3.1 Write property test: RAG 阈值过滤保证
  - **Property 1: RAG 阈值过滤保证**
  - 生成随机相似度分数的记忆条目，验证过滤结果中所有条目的 similarity >= threshold
  - **Validates: Requirements 1.2**

- [ ]* 3.2 Write property test: 空记忆输入产生空上下文
  - **Property 2: 空记忆输入产生空上下文**
  - 对任意 history 和 limit 参数，空 relevant_memories 列表始终返回空字符串
  - **Validates: Requirements 2.5**

- [ ]* 3.3 Write property test: 中期摘要注入数量上限
  - **Property 3: 中期摘要注入数量上限**
  - 对任意 count 值和摘要列表，注入数量不超过配置值
  - **Validates: Requirements 3.2**

- [x] 4. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- 本次修改范围小，仅涉及 3 个文件：`config.yaml`、`backend/memory/models.py`、`backend/core/bot.py`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "2.2"] },
    { "id": 2, "tasks": ["3.1", "3.2", "3.3"] }
  ]
}
```
