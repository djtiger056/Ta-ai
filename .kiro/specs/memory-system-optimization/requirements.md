# Requirements Document

## Introduction

本特性对记忆系统进行优化，目标是提升 RAG 检索召回率、改善长期记忆注入措辞使模型更自然地运用记忆内容，以及增强中期摘要注入的深度和可配置性。优化后，AI 角色应表现得像一个真正记得对方信息的人，而非机械地引用记忆条目。

## Glossary

- **System**: 指整个 AI 伴侣后端系统，包括 Bot 核心、记忆管理器和配置层
- **MemoryConfig**: 位于 `backend/memory/models.py` 的 Pydantic 配置模型，定义记忆系统所有可配置参数
- **RAG_Retrieval**: 基于向量相似度的长期记忆检索模块，通过 `rag_score_threshold` 和 `rag_top_k` 控制检索行为
- **Memory_Injector**: `backend/core/bot.py` 中 `_build_memory_context()` 方法，负责将检索到的长期记忆格式化并注入 LLM 上下文
- **MidTerm_Injector**: `backend/core/bot.py` 中 `_append_mid_term_context()` 方法，负责将中期摘要注入 LLM 上下文
- **Config_YAML**: 项目根目录 `config.yaml` 文件中的 `memory` 配置节
- **Frontend_Config**: 前端配置页面，允许用户通过 UI 修改系统配置参数

## Requirements

### Requirement 1: 降低 RAG 检索阈值

**User Story:** As a system administrator, I want to lower the RAG retrieval score threshold, so that more relevant memories are recalled during conversations and the AI can reference a broader range of remembered information.

#### Acceptance Criteria

1. WHEN the System loads configuration, THE Config_YAML SHALL set `rag_score_threshold` to `0.6`
2. THE RAG_Retrieval SHALL use the configured `rag_score_threshold` value of `0.6` as the minimum similarity score for returning memory results
3. THE MemoryConfig SHALL retain `rag_score_threshold` as a configurable field with the updated default value of `0.6`

### Requirement 2: 优化长期记忆注入措辞

**User Story:** As a user, I want the AI to naturally incorporate remembered information into conversations like a real person who remembers things about their partner, so that interactions feel genuine and emotionally connected rather than robotic.

#### Acceptance Criteria

1. THE Memory_Injector SHALL use prompt wording that instructs the model to treat memory content as personal knowledge it genuinely remembers about the user
2. THE Memory_Injector SHALL guide the model to weave memory content naturally into responses without explicitly stating "according to memory" or similar meta-references
3. THE Memory_Injector SHALL encourage the model to proactively reference relevant memories when they relate to the current conversation topic, rather than only when directly asked
4. THE Memory_Injector SHALL instruct the model to avoid listing or enumerating memory items in its response
5. IF no retrieved memories are relevant to the current conversation context, THEN THE Memory_Injector SHALL allow the model to respond without forcing memory references

### Requirement 3: 增加中期摘要注入数量

**User Story:** As a user, I want the system to inject more historical conversation summaries into context, so that the AI maintains better topic continuity across conversations and remembers what we recently discussed.

#### Acceptance Criteria

1. WHEN the System loads configuration, THE Config_YAML SHALL set `mid_term_context_count` to `5`
2. THE MidTerm_Injector SHALL retrieve up to the configured `mid_term_context_count` number of recent summaries for injection into LLM context

### Requirement 4: 将 mid_term_context_count 定义为 MemoryConfig 正式字段

**User Story:** As a developer, I want `mid_term_context_count` to be a properly defined field in the MemoryConfig Pydantic model, so that it benefits from type validation, default values, and schema documentation instead of relying on getattr fallback.

#### Acceptance Criteria

1. THE MemoryConfig SHALL define `mid_term_context_count` as an integer field with a default value of `5`
2. THE MemoryConfig SHALL include a description for the `mid_term_context_count` field indicating it controls the number of mid-term summaries injected into context
3. THE MidTerm_Injector SHALL access `mid_term_context_count` directly as a typed attribute of MemoryConfig without using getattr fallback
4. THE Frontend_Config SHALL expose `mid_term_context_count` as a configurable parameter on the memory settings page

### Requirement 5: 优化中期摘要注入措辞

**User Story:** As a user, I want the AI to use historical conversation summaries more effectively for topic continuity, so that it can naturally pick up previous topics and maintain conversational flow across sessions.

#### Acceptance Criteria

1. THE MidTerm_Injector SHALL use prompt wording that instructs the model to treat conversation summaries as its own recollection of recent interactions
2. THE MidTerm_Injector SHALL guide the model to use summaries for maintaining topic continuity, enabling natural follow-ups on previously discussed subjects
3. THE MidTerm_Injector SHALL instruct the model to reference prior conversations naturally, as a person would recall what was discussed earlier
4. THE MidTerm_Injector SHALL instruct the model to avoid verbatim repetition of summary content in its responses
5. IF the current conversation topic has no relation to any injected summaries, THEN THE MidTerm_Injector SHALL allow the model to respond without forcing references to prior conversations
