# Requirements Document

## Introduction

本项目是一个多模态 AI 伴侣聊天机器人后端系统，支持 LLM 对话、TTS 语音合成、图像生成、视觉识别、ASR 语音识别、记忆系统、MCP 扩展、表情包、主动聊天等功能。当前核心问题是 `bot.py`（69KB/1632行/40+方法）承担了过多职责，包括对话管理、记忆上下文构建、用户配置管理、多模态服务编排、提示词工程等。类似地，`qq.py`（61KB）和 `proactive.py`（37KB）也存在单文件过大、职责混杂的问题。

本次重构的目标是将这些庞大文件按照单一职责原则拆分为独立模块，提升代码的可维护性、可测试性和可扩展性，同时保持现有功能和外部接口不变。

## Glossary

- **Bot**: 核心对话引擎类，当前位于 `backend/core/bot.py`，负责协调所有子系统
- **Conversation_Manager**: 重构后负责对话历史管理和会话生命周期的模块
- **Context_Builder**: 重构后负责构建 LLM 上下文（记忆注入、MCP 上下文、伴侣模式提示等）的模块
- **User_Config_Manager**: 重构后负责用户配置加载、缓存和合并的模块
- **Service_Registry**: 重构后负责管理多模态服务实例（TTS、图像生成、视觉、ASR）生命周期的模块
- **Chat_Pipeline**: 重构后负责编排完整对话流程（从接收消息到返回回复）的模块
- **QQ_Adapter**: QQ 平台消息适配器，当前位于 `backend/adapters/qq.py`
- **Message_Processor**: 重构后从 QQ_Adapter 中拆分出的消息解析和处理模块
- **Proactive_Scheduler**: 主动聊天调度器，当前位于 `backend/core/proactive.py`

## Requirements

### Requirement 1: 对话历史管理模块拆分

**User Story:** As a developer, I want conversation history management to be in a dedicated module, so that I can modify history logic without touching the core bot orchestration code.

#### Acceptance Criteria

1. WHEN the system starts, THE Conversation_Manager SHALL initialize session history storage independently from other subsystems
2. WHEN a new message arrives, THE Conversation_Manager SHALL load persisted history from the memory backend if the session has not been loaded before
3. WHEN a conversation round completes, THE Conversation_Manager SHALL trim the history to the configured maximum length while preserving the system prompt
4. THE Conversation_Manager SHALL provide methods to get, clear, and append messages to session histories without depending on LLM provider or memory implementation details
5. IF the memory backend is unavailable, THEN THE Conversation_Manager SHALL continue operating with in-memory history only and log a warning

### Requirement 2: LLM 上下文构建模块拆分

**User Story:** As a developer, I want context building logic (memory injection, MCP context, companion hints) to be in a dedicated module, so that prompt engineering changes are isolated from conversation flow.

#### Acceptance Criteria

1. WHEN a chat request is being processed, THE Context_Builder SHALL assemble the enhanced message history by combining base history with long-term memory context, mid-term summaries, MCP auto-context, companion mode hints, and long-gap repeat hints
2. THE Context_Builder SHALL accept the base conversation history and return an enhanced copy without mutating the original history
3. WHEN building memory context, THE Context_Builder SHALL filter out memories that duplicate recent conversation content
4. WHEN companion mode is enabled, THE Context_Builder SHALL inject companion behavior hints based on configured probabilities and turn gap rules
5. THE Context_Builder SHALL be configurable independently, accepting memory manager, MCP manager, and companion mode settings as dependencies

### Requirement 3: 用户配置管理模块拆分

**User Story:** As a developer, I want user configuration loading, caching, and merging to be in a dedicated module, so that adding new per-user settings does not require modifying the bot core.

#### Acceptance Criteria

1. THE User_Config_Manager SHALL load user-specific configurations from the database with a configurable cache TTL
2. WHEN the cache TTL expires, THE User_Config_Manager SHALL reload the user configuration from the database on the next access
3. THE User_Config_Manager SHALL merge user configurations with global configurations using a defined priority order where user settings override global defaults
4. WHEN a user configuration is invalid or incomplete, THE User_Config_Manager SHALL fall back to the global configuration and log a warning
5. THE User_Config_Manager SHALL provide the merged LLM config, TTS config, image generation config, and system prompt for any given user ID

### Requirement 4: 多模态服务注册与生命周期管理

**User Story:** As a developer, I want multimodal service instances (TTS, image gen, vision, ASR) to be managed by a dedicated registry, so that adding new services or changing initialization logic does not require modifying the bot class.

#### Acceptance Criteria

1. THE Service_Registry SHALL initialize and cache per-user instances of LLM provider, TTS manager, and image generation manager based on user-specific merged configurations
2. WHEN a service configuration changes (detected by signature comparison), THE Service_Registry SHALL recreate the affected service instance
3. WHEN a user-specific service configuration is invalid, THE Service_Registry SHALL fall back to the global service instance and log a warning
4. THE Service_Registry SHALL provide a unified interface to retrieve any registered service instance by user ID and service type
5. WHEN the global configuration file changes, THE Service_Registry SHALL detect the change and refresh affected global service instances

### Requirement 5: 对话流水线编排

**User Story:** As a developer, I want the chat processing pipeline (from message receipt to response delivery) to be a clear, linear orchestration, so that I can understand and modify the flow without navigating a 1600-line file.

#### Acceptance Criteria

1. WHEN a chat message is received, THE Chat_Pipeline SHALL execute steps in order: load user config, refresh providers, load history, build enhanced context, call LLM, record to history, persist to memory, process image tags, and return the response
2. THE Chat_Pipeline SHALL support both synchronous (full response) and streaming (chunk-by-chunk) execution modes using the same pipeline steps
3. WHEN any pipeline step fails, THE Chat_Pipeline SHALL return a user-friendly error message and log the detailed error
4. THE Chat_Pipeline SHALL delegate to Conversation_Manager, Context_Builder, User_Config_Manager, and Service_Registry rather than implementing their logic inline
5. THE Chat_Pipeline SHALL expose latency tracing for each pipeline stage in streaming mode

### Requirement 6: Bot 类瘦身为门面（Facade）

**User Story:** As a developer, I want the Bot class to be a thin facade that delegates to specialized modules, so that it remains easy to understand and serves as the single entry point for external callers.

#### Acceptance Criteria

1. THE Bot SHALL delegate conversation operations to Conversation_Manager, context building to Context_Builder, user config to User_Config_Manager, and service management to Service_Registry
2. THE Bot SHALL maintain the same public API signatures (chat, chat_stream, generate_image, synthesize_speech, recognize_image, transcribe_voice, etc.) to avoid breaking existing callers
3. THE Bot SHALL contain initialization logic that wires together all sub-modules with their dependencies
4. WHEN a new capability is added to the system, THE Bot SHALL require only the addition of a delegation method rather than inline implementation
5. THE Bot class file SHALL be reduced to fewer than 300 lines after refactoring

### Requirement 7: QQ 适配器消息处理拆分

**User Story:** As a developer, I want QQ message parsing, segmented sending, and media handling to be in separate modules, so that I can modify message formatting without risking the WebSocket connection logic.

#### Acceptance Criteria

1. THE Message_Processor SHALL handle CQ code parsing, image segment extraction, voice segment extraction, and text content normalization independently from the WebSocket event loop
2. WHEN a message needs to be sent in segments, THE Message_Processor SHALL split the text according to configured sentence limits and delay rules
3. THE QQ_Adapter SHALL retain only WebSocket connection management, event routing, and high-level message dispatch after refactoring
4. WHEN image generation or vision recognition is triggered, THE QQ_Adapter SHALL delegate the media processing workflow to a dedicated media handler module
5. THE QQ_Adapter file SHALL be reduced to fewer than 400 lines after refactoring

### Requirement 8: 主动聊天调度器拆分

**User Story:** As a developer, I want the proactive chat scheduler to have its time window logic, behavior rules, and message composition separated into focused modules, so that adjusting scheduling rules does not require understanding the entire 37KB file.

#### Acceptance Criteria

1. THE Proactive_Scheduler SHALL delegate time window resolution and scheduling calculations to a dedicated time window module
2. THE Proactive_Scheduler SHALL delegate behavior rule evaluation (inactivity rules, follow-up rules, cooldown checks) to a dedicated rules engine module
3. THE Proactive_Scheduler SHALL delegate message instruction composition to a dedicated instruction builder module
4. THE Proactive_Scheduler core file SHALL retain only the main event loop, target state management, and sender dispatch after refactoring
5. THE Proactive_Scheduler core file SHALL be reduced to fewer than 300 lines after refactoring

### Requirement 9: 接口兼容性保证

**User Story:** As a developer, I want the refactoring to preserve all existing public interfaces and behaviors, so that adapters, API routes, and tests continue to work without modification.

#### Acceptance Criteria

1. THE Bot SHALL maintain identical method signatures for all public methods that are called by adapters (QQ, console, linyu) and API routes
2. WHEN the refactored system processes a chat message, THE system SHALL produce identical responses compared to the pre-refactoring version given the same inputs and state
3. THE refactored modules SHALL maintain the same import paths for the Bot class (from backend.core.bot import Bot) through re-exports if the class is relocated
4. IF any internal module raises an exception, THEN THE Bot facade SHALL handle the exception and present the same error behavior as the current implementation
5. THE refactored system SHALL pass all existing tests without modification to test code

### Requirement 10: 代码组织与模块结构规范

**User Story:** As a developer, I want a clear, consistent module structure within the core package, so that new team members can quickly understand where to find and add functionality.

#### Acceptance Criteria

1. THE system SHALL organize the refactored core package with a clear directory structure: `core/conversation/`, `core/context/`, `core/pipeline/`, `core/config/`, `core/services/`
2. EACH refactored module SHALL have a single `__init__.py` that exports its public interface
3. EACH refactored module file SHALL contain fewer than 400 lines of code
4. THE system SHALL maintain a module dependency graph where lower-level modules (conversation, config) do not import from higher-level modules (pipeline, bot facade)
5. EACH refactored module SHALL include module-level docstrings describing its responsibility and public interface
