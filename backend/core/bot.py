from typing import List, Dict, Any, AsyncGenerator, Optional, Set, Tuple
from datetime import datetime
import asyncio
import json
import copy
import logging
import re
import random
import time
from collections import defaultdict
from ..providers import get_provider
from ..config import config
from ..tts.manager import TTSManager
from ..image_gen import ImageGenerationManager, ImageGenerationConfig
from ..image_gen.base_image_service import BaseImageService
from ..video_gen import VideoGenerationManager, VideoGenerationConfig
from ..vision import VisionRecognitionManager, VisionRecognitionConfig
from ..asr import ASRManager, ASRConfig
from ..memory import MemoryManager, MemoryConfig
from ..mcp import MCPManager
from ..emote import EmoteManager, EmoteConfig
from ..agent_delegate import AgentDelegator, extract_delegate_tag
from ..agent_delegate.config import AgentDelegateConfig
from ..user import user_manager
from ..user.data_manager import user_data_manager
from ..utils.config_merger import config_merger
from ..utils.datetime_utils import get_now, from_isoformat
from .gen_img_parser import extract_gen_img_prompt
from .gen_video_parser import extract_gen_video_prompt
from .tts_tag_parser import extract_tts_tag
from .context_builder import ContextBuilder
from .history_manager import HistoryManager
from .user_cache import UserResourceCache


DEFAULT_ROLEPLAY_EXIT_SUMMARY_PROMPT = """你是 AI 伴侣模式的记忆整理助手。
请只基于输入内容，写一段适合存入 AI 伴侣短期记忆的摘要。
要求：
1. 不续写剧情，不扮演角色，不编造输入外的信息。
2. 保留用户在情景演绎中体现出的偏好、关系动态、重要剧情节点、未完成线索。
3. 用自然中文写成一段，避免列表过长。

本次情景演绎中期摘要：
{summaries}

本次情景演绎保留的对话原文：
{conversation}

当前时间：{current_time}
"""


class Bot:
    """Bot 核心类，处理对话与多模态协作，支持多用户配置"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.provider_name = config.llm_config.get('provider', 'openai')
        self.provider = get_provider(self.provider_name)
        self.system_prompt = config.system_prompt
        self._provider_signature = None
        self._tts_signature = None
        self._history_manager = HistoryManager()
        # 向后兼容：让旧引用指向 HistoryManager 内部存储
        self.session_histories = self._history_manager.session_histories
        self._history_loaded_sessions = self._history_manager._history_loaded_sessions
        self.mcp_manager = MCPManager()

        # 用户资源缓存（配置、Provider、TTS、ImageGen 实例）
        self._user_cache = UserResourceCache()
        # 向后兼容：保留旧属性引用
        self._user_configs = self._user_cache._user_configs
        self._user_providers = self._user_cache._user_providers
        self._user_provider_signatures = self._user_cache._user_provider_signatures
        self._user_tts_managers = self._user_cache._user_tts_managers
        self._user_tts_signatures = self._user_cache._user_tts_signatures
        self._user_image_gen_managers = self._user_cache._user_image_gen_managers
        self._user_image_gen_signatures = self._user_cache._user_image_gen_signatures
        self._user_video_gen_managers = self._user_cache._user_video_gen_managers
        self._user_video_gen_signatures = self._user_cache._user_video_gen_signatures
        self._session_last_companion_hint_turn: Dict[str, int] = {}
        self._roleplay_memory_managers: Dict[str, MemoryManager] = {}
        self._roleplay_memory_signatures: Dict[str, str] = {}
        self._last_mode_command: Optional[Dict[str, Any]] = None

        # 存储最近生成的图片（用于API返回）
        self._last_generated_image: Optional[Dict[str, Any]] = None
        self._last_generated_video: Optional[Dict[str, Any]] = None
        self._video_intent_sessions: Dict[str, str] = {}

        # 存储 AI 主动触发的 TTS 文本（用于API返回）
        self._last_tts_forced_text: Optional[Dict[str, Any]] = None
        
        # 初始化TTS管理器
        self.tts_manager: Optional[TTSManager] = None
        try:
            tts_config = config.tts_config if hasattr(config, 'tts_config') else {}
            self.tts_manager = TTSManager(tts_config)
            self._tts_signature = json.dumps(tts_config, sort_keys=True, ensure_ascii=False)
        except Exception as e:
            print(f"TTS初始化失败: {str(e)}")
        
        # 初始化图像生成管理器
        self.image_gen_manager: Optional[ImageGenerationManager] = None
        try:
            image_gen_config = config.image_gen_config if hasattr(config, 'image_gen_config') else ImageGenerationConfig()
            self.image_gen_manager = ImageGenerationManager(image_gen_config)
        except Exception as e:
            print(f"图像生成初始化失败: {str(e)}")

        # 初始化视频生成管理器
        self.video_gen_manager: Optional[VideoGenerationManager] = None
        try:
            video_gen_config = config.video_gen_config if hasattr(config, 'video_gen_config') else VideoGenerationConfig()
            self.video_gen_manager = VideoGenerationManager(video_gen_config)
        except Exception as e:
            print(f"视频生成初始化失败: {str(e)}")
        self.video_base_image_service = BaseImageService(
            user_data_manager=user_data_manager,
            fallback_image_path=config.get("image_generation", {}).get(
                "default_base_image_path", "backend/data/default_base_image.jpg"
            ),
        )
        
        # 初始化视觉识别管理器
        self.vision_manager: Optional[VisionRecognitionManager] = None
        try:
            vision_config = config.vision_config if hasattr(config, 'vision_config') else VisionRecognitionConfig()
            self.vision_manager = VisionRecognitionManager(vision_config)
        except Exception as e:
            print(f"视觉识别初始化失败: {str(e)}")

        # 初始化ASR语音识别管理器
        self.asr_manager: Optional[ASRManager] = None
        try:
            asr_config = config.asr_config if hasattr(config, 'asr_config') else ASRConfig()
            self.asr_manager = ASRManager(asr_config)
        except Exception as e:
            print(f"ASR初始化失败: {str(e)}")

        # 初始化记忆管理器
        self.memory_manager = None
        try:
            memory_config = config.memory_config if hasattr(config, 'memory_config') else MemoryConfig()
            
            from ..memory.manager import MemoryManager
            self.logger.info("使用向量记忆系统（需要嵌入模型）")
            self.memory_manager = MemoryManager(memory_config)
            
            self._memory_manager_init_failed = False
            # 注意：记忆管理器需要异步初始化，将在第一次使用时初始化
        except Exception as e:
            print(f"记忆管理器初始化失败: {str(e)}")
            self._memory_manager_init_failed = True

        # 初始化表情包管理器
        self.emote_manager: Optional[EmoteManager] = None
        self._emote_signature = None
        try:
            emote_config = config.emote_config if hasattr(config, 'emote_config') else EmoteConfig()
            self.emote_manager = EmoteManager(emote_config)
            self._emote_signature = json.dumps(emote_config.dict(), sort_keys=True, ensure_ascii=False)
        except Exception as e:
            print(f"表情包功能初始化失败: {str(e)}")
            self._emote_signature = None
        
        # 初始化时记录提供商签名
        self._refresh_provider(force=True)

        # 上下文构建器（消除 chat/chat_stream/generate_proactive_reply 中的重复逻辑）
        self._context_builder = ContextBuilder(self)

        # 初始化 Agent 委派器
        self.agent_delegator: Optional[AgentDelegator] = None
        # session/user -> channel 映射，由 adapter 注册
        self._session_channel_map: Dict[str, str] = {}
        try:
            delegate_config = config.agent_delegate_config
            if delegate_config.enabled:
                self.agent_delegator = AgentDelegator(delegate_config)
                print("🤖 Agent 委派器已初始化（等待启动）")
        except Exception as e:
            print(f"Agent 委派器初始化失败: {str(e)}")

    def _get_session_history(self, session_id: str, user_id: str = "default") -> List[Dict[str, str]]:
        """获取或初始化指定会话的对话历史"""
        system_prompt = self._get_user_system_prompt(user_id)
        return self._history_manager.get_session_history(session_id, system_prompt)

    def _history_limit(self) -> int:
        """获取历史记录保留上限"""
        if self.memory_manager and hasattr(self.memory_manager, "config"):
            try:
                return max(2, self.memory_manager.config.short_term_max_rounds * 2)
            except Exception:
                pass
        return 20

    def _trim_conversation_history(self, session_id: str, user_id: str = "default"):
        """保持对话历史在配置上限内"""
        system_prompt = self._get_user_system_prompt(user_id)
        self._history_manager.trim(session_id, self._history_limit(), system_prompt)

    async def _load_history_from_memory(self, user_id: str, session_id: Optional[str] = None):
        """从持久化存储中恢复短期对话历史，避免重启丢失上下文"""
        if not self.memory_manager:
            return
        session_id = session_id or user_id
        if not await self._ensure_memory_manager_initialized():
            return
        await self._history_manager.load_from_memory(
            user_id=user_id,
            session_id=session_id,
            memory_manager=self.memory_manager,
            system_prompt=self.system_prompt or "",
            limit=self._history_limit(),
        )

    def _refresh_provider(self, force: bool = False):
        """检测LLM配置是否变化，必要时刷新provider"""
        try:
            config.refresh_from_file()
        except Exception as e:
            print(f"刷新配置失败: {e}")
            # 即便刷新失败也继续使用当前配置

        llm_cfg = config.llm_config or {}
        signature = json.dumps(llm_cfg, sort_keys=True, ensure_ascii=False)

        if force or signature != self._provider_signature:
            self.provider_name = llm_cfg.get('provider', 'openai')
            self.provider = get_provider(self.provider_name, llm_config=llm_cfg)
            self.system_prompt = config.system_prompt
            self._provider_signature = signature
        
        # 同步TTS配置，支持热更新
        self._refresh_tts_manager()
        # 同步表情包配置
        self._refresh_emote_manager()
    
    async def _ensure_memory_manager_initialized(self):
        """确保MemoryManager已初始化"""
        if self.memory_manager is None:
            return False
        
        # 如果已经尝试初始化但失败了，不再尝试
        if hasattr(self, '_memory_manager_init_failed') and self._memory_manager_init_failed:
            return False
        
        # 检查是否已初始化（简化：检查engine是否存在）
        if hasattr(self.memory_manager, 'engine') and self.memory_manager.engine is None:
            try:
                await self.memory_manager.initialize()
                self.logger.info("MemoryManager已初始化")
            except Exception as e:
                print(f"MemoryManager初始化失败: {e}")
                self._memory_manager_init_failed = True
                return False
        
        return True
    
    async def _get_relevant_memories(self, user_id: str, query: str) -> List[Dict[str, Any]]:
        """获取相关记忆（长期记忆）"""
        if not self.memory_manager or not await self._ensure_memory_manager_initialized():
            return []
        
        try:
            memories = await self.memory_manager.search_long_term_memories(
                user_id=user_id,
                query=query
            )
            return memories
        except Exception as e:
            print(f"获取相关记忆失败: {e}")
            return []

    async def _append_mid_term_context(self, enhanced_history: List[Dict[str, str]],
                                      user_id: str, session_id: str):
        """将中期摘要注入到LLM上下文中（用于连续性）"""
        if not self.memory_manager or not await self._ensure_memory_manager_initialized():
            return

        count = config.memory_config.mid_term_context_count
        if count <= 0:
            return
        if not getattr(config.memory_config, "mid_term_enabled", True):
            return

        try:
            summaries = await self.memory_manager.get_mid_term_summaries(
                user_id=user_id,
                session_id=session_id,
                limit=count
            )
        except Exception as e:
            print(f"获取中期摘要失败: {e}")
            return

        if not summaries:
            return

        summaries = list(reversed(summaries))
        lines: List[str] = []
        for item in summaries:
            text = str(item.get("summary") or "").strip()
            if not text:
                continue
            range_info = item.get("conversation_range")
            if range_info:
                lines.append(f"- {text} (范围 {range_info})")
            else:
                lines.append(f"- {text}")

        if not lines:
            return

        context = (
            "你对最近和对方聊过的内容有印象（以下是你的回忆片段）。"
            "如果当前话题和之前聊过的有关，可以自然地接续；不要原文复述这些内容，不相关就不提：\n"
            + "\n".join(lines)
        )
        if enhanced_history and enhanced_history[0]["role"] == "system":
            base_content = str(enhanced_history[0].get("content", "") or "")
            enhanced_history[0]["content"] = base_content + "\n\n" + context if base_content else context
        else:
            enhanced_history.insert(0, {
                "role": "system",
                "content": context
            })
    
    def _normalize_text_for_compare(self, text: str) -> str:
        """归一化文本，便于进行轻量去重匹配。"""
        raw = str(text or "").strip().lower()
        if not raw:
            return ""
        compact = re.sub(r"\s+", "", raw)
        compact = re.sub(r"[^\w\u4e00-\u9fff]", "", compact)
        return compact

    def _to_llm_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """清洗消息结构，避免将内部字段（如timestamp）传给LLM接口。"""
        cleaned: List[Dict[str, str]] = []
        for message in messages:
            role = str(message.get("role", "") or "").strip()
            if not role:
                continue
            cleaned.append({
                "role": role,
                "content": str(message.get("content", "") or "")
            })
        return cleaned

    def _extract_message_timestamp(self, message: Dict[str, Any]) -> Optional[datetime]:
        """从历史消息中解析时间戳。"""
        raw_ts = message.get("timestamp")
        if not raw_ts:
            return None
        if isinstance(raw_ts, datetime):
            return raw_ts
        if isinstance(raw_ts, str):
            try:
                return from_isoformat(raw_ts)
            except Exception:
                return None
        return None

    def _is_same_question(self, current_message: str, previous_message: str) -> bool:
        """判断两条用户消息是否属于同类重复问法。"""
        current = self._normalize_text_for_compare(current_message)
        previous = self._normalize_text_for_compare(previous_message)
        if not current or not previous:
            return False
        if current == previous:
            return True
        if min(len(current), len(previous)) >= 4 and max(len(current), len(previous)) <= 16:
            if current in previous or previous in current:
                return True
        return False

    def _build_long_gap_repeat_hint(self, history: List[Dict[str, Any]], current_message: str) -> str:
        """当同类问题间隔较久时，提示模型按“新一轮状态”回答。"""
        if not history or not current_message:
            return ""

        threshold = getattr(config.memory_config, "same_question_reset_minutes", 45)
        try:
            threshold_minutes = max(1, int(threshold))
        except Exception:
            threshold_minutes = 45

        last_user_message: Optional[Dict[str, Any]] = None
        for item in reversed(history):
            if item.get("role") == "user":
                last_user_message = item
                break

        if not last_user_message:
            return ""
        if not self._is_same_question(current_message, str(last_user_message.get("content", "") or "")):
            return ""

        last_ts = self._extract_message_timestamp(last_user_message)
        if not last_ts:
            return ""

        gap_seconds = (get_now() - last_ts).total_seconds()
        if gap_seconds < threshold_minutes * 60:
            return ""

        gap_minutes = int(gap_seconds // 60)
        return (
            f"用户这次同类提问与上次已间隔约 {gap_minutes} 分钟，"
            "应视为新的时间点，请按当前状态重新回答；不要说“刚说过/你又问了”。"
        )

    def _build_companion_mode_hint(self, session_id: str,
                                   history: List[Dict[str, Any]],
                                   current_message: str) -> str:
        """构建“AI伴侣化”动态提示，降低纯问答感。"""
        llm_cfg = config.llm_config or {}
        mode_cfg = llm_cfg.get("companion_mode", {})
        if not isinstance(mode_cfg, dict):
            mode_cfg = {}

        enabled = mode_cfg.get("enabled", llm_cfg.get("companion_mode_enabled", True))
        if not bool(enabled):
            return ""

        try:
            share_prob = float(mode_cfg.get(
                "spontaneous_share_probability",
                llm_cfg.get("companion_spontaneous_share_probability", 0.35)
            ))
        except Exception:
            share_prob = 0.35
        share_prob = max(0.0, min(1.0, share_prob))

        try:
            relation_prob = float(mode_cfg.get(
                "relationship_reflection_probability",
                llm_cfg.get("companion_relationship_reflection_probability", 0.18)
            ))
        except Exception:
            relation_prob = 0.18
        relation_prob = max(0.0, min(1.0, relation_prob))

        try:
            min_turn_gap = int(mode_cfg.get("min_turn_gap", llm_cfg.get("companion_min_turn_gap", 2)))
        except Exception:
            min_turn_gap = 2
        min_turn_gap = max(1, min_turn_gap)

        try:
            statement_end_prob = float(mode_cfg.get(
                "statement_end_probability",
                llm_cfg.get("companion_statement_end_probability", 0.7)
            ))
        except Exception:
            statement_end_prob = 0.7
        statement_end_prob = max(0.0, min(1.0, statement_end_prob))

        if not hasattr(self, "_session_last_companion_hint_turn"):
            self._session_last_companion_hint_turn = {}

        current_turn = sum(1 for item in history if item.get("role") == "user") + 1
        last_hint_turn = int(self._session_last_companion_hint_turn.get(session_id, 0) or 0)
        if current_turn - last_hint_turn < min_turn_gap:
            return ""

        if random.random() > share_prob:
            return ""

        self._session_last_companion_hint_turn[session_id] = current_turn
        include_relation = random.random() < relation_prob
        statement_end = random.random() < statement_end_prob

        hint_parts = [
            "本轮回复请避免只做问答式复述：先正常回应用户，再自然补1句你自己的近况/想法/情绪（10-30字）。",
            "像真实伴侣聊天，允许轻微跑题和碎碎念，但保持温柔、简短。"
        ]

        if include_relation:
            hint_parts.append(
                "可偶尔提一句关系里的真实感受或小需求（温和不指责），如想被多陪陪、异地见面安排、轻微没安全感。"
            )

        if statement_end:
            hint_parts.append("这轮优先用陈述句收尾，不必每次都反问。")

        if len(current_message.strip()) <= 4:
            hint_parts.append("用户这句很短，你的回复依然可以短，但要保留一点‘你自己的状态’。")

        return " ".join(hint_parts)

    def _build_memory_context(self, relevant_memories: List[Dict[str, Any]],
                              history: List[Dict[str, str]], limit: int = 3) -> str:
        """构建长期记忆上下文，过滤与近期对话重复的内容。"""
        if not relevant_memories:
            return ""

        try:
            limit = max(1, int(limit))
        except Exception:
            limit = 3

        recent_norms: List[str] = []
        for message in history[-10:]:
            normalized = self._normalize_text_for_compare(message.get("content", ""))
            if normalized:
                recent_norms.append(normalized)

        selected_lines: List[str] = []
        seen_contents: Set[str] = set()

        sorted_memories = sorted(
            relevant_memories,
            key=lambda mem: float(mem.get("similarity", 0) or 0),
            reverse=True
        )

        for mem in sorted_memories:
            content = str(mem.get("content", "") or "").strip()
            if not content:
                continue

            normalized = self._normalize_text_for_compare(content)
            if not normalized or normalized in seen_contents:
                continue

            if any(
                len(normalized) >= 10 and (normalized in recent or recent in normalized)
                for recent in recent_norms if recent
            ):
                continue

            seen_contents.add(normalized)
            try:
                similarity = float(mem.get("similarity", 0) or 0)
            except Exception:
                similarity = 0.0
            selected_lines.append(f"{len(selected_lines) + 1}. {content} (相关度: {similarity:.2f})")

            if len(selected_lines) >= limit:
                break

        if not selected_lines:
            return ""

        return (
            "你记得关于对方的这些事（这是你自己的记忆，不要说'根据记忆'，"
            "像真正记得一样自然地在相关时提及，不要逐条列举，不相关就不提）：\n"
            + "\n".join(selected_lines)
        )
    
    def _refresh_tts_manager(self):
        """检测TTS配置变化，必要时热更新TTS管理器"""
        try:
            # 确保最新配置（即便LLM未变化也刷新）
            try:
                config.refresh_from_file()
            except Exception:
                pass

            tts_cfg = config.tts_config if hasattr(config, 'tts_config') else {}
            signature = json.dumps(tts_cfg, sort_keys=True, ensure_ascii=False)
            if self.tts_manager is None or signature != self._tts_signature:
                self.tts_manager = TTSManager(tts_cfg)
                self._tts_signature = signature
        except Exception as e:
            print(f"刷新TTS配置失败: {str(e)}")

    def _refresh_emote_manager(self):
        """检测表情包配置变化，必要时刷新管理器"""
        try:
            try:
                config.refresh_from_file()
            except Exception:
                pass
            emote_cfg = config.emote_config if hasattr(config, 'emote_config') else EmoteConfig()
            signature = json.dumps(emote_cfg.dict(), sort_keys=True, ensure_ascii=False)
            if self.emote_manager is None or signature != self._emote_signature:
                self.emote_manager = EmoteManager(emote_cfg)
                self._emote_signature = signature
        except Exception as e:
            print(f"刷新表情包配置失败: {str(e)}")
    
    async def _add_conversation_to_memory(self, user_id: str, session_id: str, 
                                        user_message: str, assistant_response: str):
        """添加对话到记忆系统"""
        if not self.memory_manager or not await self._ensure_memory_manager_initialized():
            return
        
        try:
            from ..memory.models import ConversationMessage
            from datetime import datetime

            # 记忆中存储精简版，避免CQ码/过长描述污染上下文
            memory_user_message = self._sanitize_for_memory(user_message)
            memory_assistant_response = self._sanitize_for_memory(assistant_response)

            # 过滤空内容，避免脏数据写入记忆库污染后续摘要
            if not memory_user_message.strip():
                self.logger.debug("跳过空用户消息，不写入记忆")
                return
            if not memory_assistant_response.strip():
                self.logger.debug("跳过空助手回复，不写入记忆")
                return

            # 添加用户消息
            user_msg = ConversationMessage(
                role="user",
                content=memory_user_message,
                timestamp=get_now()
            )
            await self.memory_manager.add_short_term_memory(user_id, session_id, user_msg)
            
            # 添加助手回复
            assistant_msg = ConversationMessage(
                role="assistant",
                content=memory_assistant_response,
                timestamp=get_now()
            )
            await self.memory_manager.add_short_term_memory(user_id, session_id, assistant_msg)
        except Exception as e:
            print(f"添加对话到记忆失败: {e}")
    
    async def _get_user_config(self, user_id: str) -> Dict[str, Any]:
        """获取用户配置（带缓存），委托到 UserResourceCache。"""
        return await self._user_cache.get_user_config(user_id)

    def _get_merged_config(self, user_id: str) -> Dict[str, Any]:
        """获取合并后的用户配置，委托到 UserResourceCache。"""
        return self._user_cache.get_merged_config(user_id)

    def _get_user_llm_provider(self, user_id: str) -> Any:
        """获取该用户的 LLM Provider，委托到 UserResourceCache。"""
        return self._user_cache.get_llm_provider(user_id, fallback_provider=self.provider)

    def _get_user_tts_manager(self, user_id: str) -> Optional[TTSManager]:
        """获取该用户的 TTSManager，委托到 UserResourceCache。"""
        return self._user_cache.get_tts_manager(user_id)

    def _get_user_image_gen_manager(self, user_id: str) -> Optional[ImageGenerationManager]:
        """获取该用户的 ImageGenerationManager，委托到 UserResourceCache。"""
        return self._user_cache.get_image_gen_manager(user_id)

    def _get_user_video_gen_manager(self, user_id: str) -> Optional[VideoGenerationManager]:
        """获取该用户的 VideoGenerationManager，委托到 UserResourceCache。"""
        return self._user_cache.get_video_gen_manager(user_id)

    def invalidate_user_cache(self, user_id: str) -> None:
        """清除指定用户的配置和资源缓存。"""
        self._user_cache.invalidate_user(user_id)

    def _get_user_system_prompt(self, user_id: str) -> str:
        """获取用户的系统提示词，委托到 UserResourceCache。"""
        return self._user_cache.get_system_prompt(user_id)

    def invalidate_user_cache(self, user_id: str) -> None:
        """清理用户级资源缓存。"""
        uid = str(user_id)
        self._user_cache.invalidate_user(uid)
        self._roleplay_memory_managers.pop(uid, None)
        self._roleplay_memory_signatures.pop(uid, None)

    def pop_last_mode_command(self, user_id: Optional[str] = None, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """取出本轮模式控制命令标记，用于适配器跳过多模态后处理。"""
        marker = self._last_mode_command
        if not marker:
            return None
        if user_id is not None and str(marker.get("user_id")) != str(user_id):
            return None
        if session_id is not None and str(marker.get("session_id")) != str(session_id):
            return None
        self._last_mode_command = None
        return marker

    def get_default_roleplay_exit_summary_prompt(self) -> str:
        return DEFAULT_ROLEPLAY_EXIT_SUMMARY_PROMPT

    async def _resolve_config_user(self, user_id: str):
        try:
            return await self._user_cache.resolve_user(user_id)
        except Exception as e:
            self.logger.warning(f"解析用户失败 user_id={user_id}: {e}")
            return None

    async def _get_user_preferences_for_update(self, user_id: str) -> Optional[Dict[str, Any]]:
        user = await self._resolve_config_user(user_id)
        if not user:
            return None
        try:
            cfg = await user_manager.get_user_config_dict(user.id)
        except Exception as e:
            self.logger.warning(f"读取用户配置失败 user_id={user_id}: {e}")
            return None
        prefs = cfg.get("preferences") if isinstance(cfg, dict) else {}
        return dict(prefs or {})

    async def _update_user_preferences(self, user_id: str, preferences: Dict[str, Any]) -> bool:
        user = await self._resolve_config_user(user_id)
        if not user:
            return False
        success = await user_manager.update_user_config(user.id, {"preferences": preferences})
        if success:
            self.invalidate_user_cache(str(user_id))
            try:
                from backend.adapters.linyu_manager import get_linyu_session_manager
                manager = get_linyu_session_manager()
                if manager:
                    manager.request_refresh_user(str(user_id))
            except Exception:
                pass
        return success

    async def _get_roleplay_message_index(self, memory_manager: Optional[MemoryManager], user_id: str, session_id: str) -> int:
        if not memory_manager:
            return 0
        try:
            state = await memory_manager._get_session_state(session_id, user_id)
            return int(state.get("message_count", 0) or 0)
        except Exception:
            return 0

    def _session_episode_key(self, session_id: str) -> str:
        return str(session_id or "default")

    async def _set_roleplay_episode_start(self, user_id: str, session_id: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
        roleplay_user_id = self._roleplay_user_id(user_id)
        roleplay_session_id = self._roleplay_session_id(session_id)
        memory_manager = await self._get_roleplay_memory_manager(user_id)
        start_index = await self._get_roleplay_message_index(memory_manager, roleplay_user_id, roleplay_session_id)
        episodes = dict(preferences.get("roleplay_active_episodes") or {})
        episodes[self._session_episode_key(session_id)] = {
            "started_at": get_now().isoformat(),
            "start_message_index": start_index,
        }
        preferences["roleplay_active_episodes"] = episodes
        return preferences

    def _get_roleplay_exit_summary_prompt(self, preferences: Dict[str, Any]) -> str:
        prompt = str((preferences or {}).get("roleplay_exit_summary_prompt") or "").strip()
        return prompt or DEFAULT_ROLEPLAY_EXIT_SUMMARY_PROMPT

    def _render_roleplay_exit_summary_prompt(
        self,
        prompt: str,
        conversation: str,
        summaries: str,
    ) -> str:
        values = {
            "conversation": conversation or "（无）",
            "summaries": summaries or "（无）",
            "current_time": get_now().isoformat(),
        }
        rendered = prompt
        used = False
        for key, value in values.items():
            token = "{" + key + "}"
            if token in rendered:
                rendered = rendered.replace(token, value)
                used = True
        if not used:
            rendered += (
                "\n\n本次情景演绎中期摘要：\n"
                + values["summaries"]
                + "\n\n本次情景演绎保留的对话原文：\n"
                + values["conversation"]
                + "\n\n当前时间："
                + values["current_time"]
            )
        return rendered

    def _message_index_from_memory(self, item: Dict[str, Any]) -> int:
        meta = item.get("metadata") or item.get("meta_data") or {}
        try:
            return int(meta.get("message_index") or 0)
        except Exception:
            return 0

    async def _get_roleplay_raw_memories_since(
        self,
        memory_manager: MemoryManager,
        user_id: str,
        session_id: str,
        start_index: int,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        if not memory_manager or memory_manager.async_session is None:
            return items
        try:
            from ..memory.models import MemoryItemDB
            from sqlalchemy.future import select

            async with memory_manager.async_session() as session:
                stmt = select(MemoryItemDB).where(
                    MemoryItemDB.user_id == user_id,
                    MemoryItemDB.session_id == session_id,
                    MemoryItemDB.memory_type.in_(["short_term", "pending", "pending_processing", "archived"]),
                ).order_by(MemoryItemDB.id.asc()).limit(limit)
                result = await session.execute(stmt)
                rows = result.scalars().all()
                for row in rows:
                    item = row.to_dict()
                    try:
                        item["message"] = json.loads(item.get("content") or "{}")
                    except Exception:
                        item["message"] = {"role": "unknown", "content": item.get("content") or ""}
                    if self._message_index_from_memory(item) > int(start_index or 0):
                        items.append(item)
        except Exception as e:
            print(f"读取情景演绎保留原文失败: {e}")
        return items

    async def _get_roleplay_summaries_since(
        self,
        memory_manager: MemoryManager,
        user_id: str,
        session_id: str,
        start_index: int,
    ) -> List[Dict[str, Any]]:
        try:
            summaries = await memory_manager.get_mid_term_summaries(user_id=user_id, session_id=session_id, limit=100)
        except Exception as e:
            print(f"读取情景演绎摘要失败: {e}")
            return []

        kept = []
        for item in summaries or []:
            rng = str(item.get("conversation_range") or "")
            end = 0
            if "-" in rng:
                try:
                    end = int(rng.split("-")[-1])
                except Exception:
                    end = 0
            if not start_index or end == 0 or end > int(start_index or 0):
                kept.append(item)
        return list(reversed(kept))

    def _format_roleplay_conversation(self, memories: List[Dict[str, Any]]) -> str:
        lines = []
        for item in memories:
            msg = item.get("message") or {}
            role = str(msg.get("role") or "unknown")
            content = str(msg.get("content") or "").strip()
            if not content:
                continue
            label = "用户" if role == "user" else "AI" if role == "assistant" else role
            lines.append(f"{label}: {content}")
        return "\n".join(lines).strip()

    def _format_roleplay_summaries(self, summaries: List[Dict[str, Any]]) -> str:
        lines = []
        for item in summaries:
            text = str(item.get("summary") or "").strip()
            if text:
                lines.append(f"- {text}")
        return "\n".join(lines).strip()

    async def _write_roleplay_exit_summary_to_companion_memory(
        self,
        user_id: str,
        session_id: str,
        summary: str,
    ) -> bool:
        if not summary.strip():
            return False
        if not self.memory_manager or not await self._ensure_memory_manager_initialized():
            return False
        try:
            from ..memory.models import ConversationMessage
            content = "【情景演绎结束摘要】" + summary.strip()
            ok = await self.memory_manager.add_short_term_memory(
                user_id=user_id,
                session_id=session_id,
                message=ConversationMessage(role="assistant", content=content, timestamp=get_now()),
            )
            if ok:
                history = self._get_session_history(session_id, user_id)
                history.append({"role": "assistant", "content": content, "timestamp": get_now().isoformat()})
                self._trim_conversation_history(session_id)
            return bool(ok)
        except Exception as e:
            print(f"写入情景结束摘要到伴侣记忆失败: {e}")
            return False

    async def _summarize_roleplay_episode_to_companion_memory(
        self,
        user_id: str,
        session_id: str,
        preferences: Dict[str, Any],
    ) -> bool:
        roleplay_user_id = self._roleplay_user_id(user_id)
        roleplay_session_id = self._roleplay_session_id(session_id)
        episode = (preferences.get("roleplay_active_episodes") or {}).get(self._session_episode_key(session_id)) or {}
        try:
            start_index = int(episode.get("start_message_index") or 0)
        except Exception:
            start_index = 0

        memory_manager = await self._get_roleplay_memory_manager(user_id)
        if not memory_manager:
            return False

        try:
            await memory_manager.summarize_pending_now(
                user_id=roleplay_user_id,
                session_id=roleplay_session_id,
                force=True,
            )
        except Exception as e:
            print(f"强制摘要情景待处理区失败: {e}")

        raw_memories = await self._get_roleplay_raw_memories_since(
            memory_manager=memory_manager,
            user_id=roleplay_user_id,
            session_id=roleplay_session_id,
            start_index=start_index,
        )
        mid_summaries = await self._get_roleplay_summaries_since(
            memory_manager=memory_manager,
            user_id=roleplay_user_id,
            session_id=roleplay_session_id,
            start_index=start_index,
        )
        conversation_text = self._format_roleplay_conversation(raw_memories)
        summaries_text = self._format_roleplay_summaries(mid_summaries)
        if not conversation_text and not summaries_text:
            return False

        prompt = self._render_roleplay_exit_summary_prompt(
            prompt=self._get_roleplay_exit_summary_prompt(preferences),
            conversation=conversation_text,
            summaries=summaries_text,
        )
        provider = self._get_user_llm_provider(user_id)
        summary = await provider.chat([
            {"role": "system", "content": "你负责把情景演绎内容整理成 AI 伴侣模式可用的短期记忆。"},
            {"role": "user", "content": prompt},
        ])
        return await self._write_roleplay_exit_summary_to_companion_memory(user_id, session_id, summary)

    async def _handle_mode_switch_command(self, message: str, user_id: str, session_id: str) -> Optional[str]:
        command = (message or "").strip()
        if command not in {"/情景", "/伴侣"}:
            return None

        self._last_tts_forced_text = None
        self._last_generated_image = None
        preferences = await self._get_user_preferences_for_update(user_id)
        if preferences is None:
            self._last_mode_command = {"user_id": str(user_id), "session_id": str(session_id), "command": command, "ok": False}
            return "模式切换失败：没有找到当前用户配置。"

        current_mode = str(preferences.get("chat_mode", "companion") or "companion").strip().lower()
        if command == "/情景":
            preferences["chat_mode"] = "roleplay"
            preferences = await self._set_roleplay_episode_start(user_id, session_id, preferences)
            ok = await self._update_user_preferences(user_id, preferences)
            self._last_mode_command = {"user_id": str(user_id), "session_id": str(session_id), "command": command, "mode": "roleplay", "ok": ok}
            if not ok:
                return "模式切换失败：用户配置写入失败。"
            return "已切换到情景演绎模式。"

        wrote_summary = False
        if current_mode == "roleplay":
            wrote_summary = await self._summarize_roleplay_episode_to_companion_memory(user_id, session_id, preferences)

        episodes = dict(preferences.get("roleplay_active_episodes") or {})
        episodes.pop(self._session_episode_key(session_id), None)
        preferences["roleplay_active_episodes"] = episodes
        preferences["chat_mode"] = "companion"
        ok = await self._update_user_preferences(user_id, preferences)
        self._last_mode_command = {
            "user_id": str(user_id),
            "session_id": str(session_id),
            "command": command,
            "mode": "companion",
            "ok": ok,
            "summary_written": wrote_summary,
        }
        if not ok:
            return "模式切换失败：用户配置写入失败。"
        if current_mode == "roleplay" and wrote_summary:
            return "已切换到 AI 伴侣模式，并整理了本次情景演绎记忆。"
        return "已切换到 AI 伴侣模式。"

    async def is_roleplay_mode(self, user_id: str) -> bool:
        """判断用户当前是否处于情景演绎模式。"""
        await self._get_user_config(user_id)
        return self._user_cache.get_chat_mode(user_id) == "roleplay"

    def _roleplay_user_id(self, user_id: str) -> str:
        return f"{user_id}::roleplay"

    def _roleplay_session_id(self, session_id: str) -> str:
        return f"roleplay::{session_id}"

    def _build_roleplay_memory_config(self, user_id: str) -> MemoryConfig:
        """构建情景演绎专用记忆配置，强制关闭长期记忆。"""
        base = config.memory_config.model_dump()
        overrides = self._user_cache.get_roleplay_memory_config(user_id)
        if isinstance(overrides, dict):
            base = self._deep_merge_config(base, overrides)

        forced = {
            "short_term_enabled": True,
            "mid_term_enabled": True,
            "long_term_enabled": False,
            "legacy_auto_extract_enabled": False,
            "max_long_term_memories": 0,
        }
        base.update(forced)
        return MemoryConfig(**base)

    async def _get_roleplay_memory_manager(self, user_id: str) -> Optional[MemoryManager]:
        """获取情景演绎专用 MemoryManager。"""
        try:
            memory_config = self._build_roleplay_memory_config(user_id)
            signature = json.dumps(memory_config.model_dump(), sort_keys=True, ensure_ascii=False)
            manager = self._roleplay_memory_managers.get(user_id)
            if manager is None or self._roleplay_memory_signatures.get(user_id) != signature:
                manager = MemoryManager(memory_config)
                await manager.initialize()
                self._roleplay_memory_managers[user_id] = manager
                self._roleplay_memory_signatures[user_id] = signature
            return manager
        except Exception as e:
            print(f"情景演绎记忆管理器初始化失败: {e}")
            return None

    async def _build_roleplay_history(
        self,
        user_id: str,
        session_id: str,
        message: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[MemoryManager], str, str]:
        """构建情景演绎 LLM 上下文，只包含情景提示词、短期记忆和中期摘要。"""
        roleplay_user_id = self._roleplay_user_id(user_id)
        roleplay_session_id = self._roleplay_session_id(session_id)
        system_prompt = self._user_cache.get_roleplay_prompt(user_id)

        memory_manager = await self._get_roleplay_memory_manager(user_id)
        history: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        if memory_manager:
            try:
                restored = await memory_manager.get_short_term_memories(
                    user_id=roleplay_user_id,
                    session_id=roleplay_session_id,
                    limit=max(2, memory_manager.config.short_term_max_rounds * 2),
                )
                for mem in restored:
                    msg = mem.get("message") or {}
                    role = msg.get("role")
                    content = msg.get("content")
                    if role in {"user", "assistant"} and content:
                        history.append({"role": role, "content": content})
            except Exception as e:
                print(f"情景演绎短期记忆恢复失败: {e}")

            try:
                summaries = await memory_manager.get_mid_term_summaries(
                    user_id=roleplay_user_id,
                    session_id=roleplay_session_id,
                    limit=memory_manager.config.mid_term_context_count,
                )
                summary_lines = [
                    str(item.get("summary") or "").strip()
                    for item in reversed(summaries or [])
                    if str(item.get("summary") or "").strip()
                ]
                if summary_lines:
                    history[0]["content"] += (
                        "\n\n以下是这段情景演绎的中期回忆摘要，只用于保持剧情连续，不要逐条复述：\n"
                        + "\n".join(f"- {line}" for line in summary_lines)
                    )
            except Exception as e:
                print(f"情景演绎中期记忆注入失败: {e}")

        if message is not None:
            history.append({"role": "user", "content": message})

        return history, memory_manager, roleplay_user_id, roleplay_session_id

    async def _chat_roleplay(self, message: str, user_id: str, session_id: str) -> str:
        """情景演绎模式：纯文本、独立提示词、独立短/中期记忆、无长期记忆。"""
        self._last_tts_forced_text = None
        self._last_generated_image = None

        provider = self._get_user_llm_provider(user_id)
        history, memory_manager, roleplay_user_id, roleplay_session_id = await self._build_roleplay_history(
            user_id=user_id,
            session_id=session_id,
            message=message,
        )
        response = await provider.chat(self._to_llm_messages(history))

        if memory_manager:
            try:
                from ..memory.models import ConversationMessage
                await memory_manager.batch_add_short_term_memories(
                    user_id=roleplay_user_id,
                    session_id=roleplay_session_id,
                    messages=[
                        ConversationMessage(role="user", content=self._sanitize_for_memory(message), timestamp=get_now()),
                        ConversationMessage(role="assistant", content=self._sanitize_for_memory(response), timestamp=get_now()),
                    ],
                )
            except Exception as e:
                print(f"情景演绎写入记忆失败: {e}")

        return response

    async def _generate_roleplay_proactive_reply(self, user_id: str, session_id: str) -> str:
        """情景演绎模式下的主动消息不注入作息表/MCP/伴侣模式提示。"""
        self._last_tts_forced_text = None
        self._last_generated_image = None

        provider = self._get_user_llm_provider(user_id)
        history, memory_manager, roleplay_user_id, roleplay_session_id = await self._build_roleplay_history(
            user_id=user_id,
            session_id=session_id,
        )
        response = await provider.chat(self._to_llm_messages(history))

        if memory_manager:
            try:
                from ..memory.models import ConversationMessage
                await memory_manager.add_short_term_memory(
                    user_id=roleplay_user_id,
                    session_id=roleplay_session_id,
                    message=ConversationMessage(role="assistant", content=self._sanitize_for_memory(response), timestamp=get_now()),
                )
            except Exception as e:
                print(f"情景演绎主动回复写入记忆失败: {e}")

        return response

    async def _chat_roleplay_stream(
        self,
        message: str,
        user_id: str,
        session_id: str,
    ) -> AsyncGenerator[str, None]:
        """情景演绎模式流式回复。"""
        self._last_tts_forced_text = None
        self._last_generated_image = None

        provider = self._get_user_llm_provider(user_id)
        history, memory_manager, roleplay_user_id, roleplay_session_id = await self._build_roleplay_history(
            user_id=user_id,
            session_id=session_id,
            message=message,
        )

        full_response = ""
        async for chunk in provider.chat_stream(self._to_llm_messages(history)):
            full_response += chunk
            yield chunk

        if memory_manager:
            try:
                from ..memory.models import ConversationMessage
                await memory_manager.batch_add_short_term_memories(
                    user_id=roleplay_user_id,
                    session_id=roleplay_session_id,
                    messages=[
                        ConversationMessage(role="user", content=self._sanitize_for_memory(message), timestamp=get_now()),
                        ConversationMessage(role="assistant", content=self._sanitize_for_memory(full_response), timestamp=get_now()),
                    ],
                )
            except Exception as e:
                print(f"情景演绎写入记忆失败: {e}")

    async def chat(self, message: str, user_id: str = "default", session_id: Optional[str] = None) -> str:
        """发送消息并获取回复"""
        try:
            session_id = session_id or user_id
            
            # 加载用户配置
            await self._get_user_config(user_id)

            # 确保全局配置热更新（但真正调用用用户 provider）
            self._refresh_provider()
            provider = self._get_user_llm_provider(user_id)

            mode_command_response = await self._handle_mode_switch_command(message, user_id, session_id)
            if mode_command_response is not None:
                return mode_command_response

            if self._user_cache.get_chat_mode(user_id) == "roleplay":
                return await self._chat_roleplay(message, user_id, session_id)

            # 检测待办事项意图
            reminder_confirmation = await self._check_reminder_intent(message, user_id, session_id)

            # 恢复最近的对话历史作为短期上下文
            await self._load_history_from_memory(user_id, session_id)
            history = self._get_session_history(session_id, user_id)

            # 获取相关记忆（长期记忆）作为上下文
            relevant_memories = []
            if self.memory_manager:
                relevant_memories = await self._get_relevant_memories(user_id, message)

            # 使用 ContextBuilder 构建增强的对话历史
            enhanced_history = await self._context_builder.build(
                message=message,
                user_id=user_id,
                session_id=session_id,
                history=history,
                relevant_memories=relevant_memories,
            )

            # 调用LLM API（使用增强的历史）
            response = await provider.chat(self._to_llm_messages(enhanced_history))
            
            # 记录到当前会话的基础对话历史（不包含扩展上下文）
            now_ts = get_now().isoformat()
            history.append({
                "role": "user",
                "content": message,
                "timestamp": now_ts
            })
            history.append({
                "role": "assistant",
                "content": response,
                "timestamp": get_now().isoformat()
            })
            
            # 保持历史记录在合理范围内
            self._trim_conversation_history(session_id)
            
            # 将对话添加到记忆系统
            await self._add_conversation_to_memory(user_id, session_id, message, response)

            # 如果有待办事项确认消息，附加到回复中
            if reminder_confirmation:
                response = response + "\n\n" + reminder_confirmation

            # 处理回复中的 TTS 标签 [TTS]...[/TTS]
            cleaned_response, tts_forced_text = extract_tts_tag(response)
            if tts_forced_text:
                self._last_tts_forced_text = {
                    "user_id": user_id,
                    "session_id": session_id,
                    "text": tts_forced_text,
                }
                print(f"[Bot] AI主动触发TTS: {tts_forced_text[:60]}...")
            else:
                self._last_tts_forced_text = None

            # 处理回复中的图片标签 [GEN_IMG: ...]
            cleaned_response, image_data = await self._process_image_in_response(cleaned_response, user_id, session_id)

            # 如果有图片生成，将图片数据存储到实例中供API调用
            if image_data:
                self._last_generated_image = {
                    "user_id": user_id,
                    "session_id": session_id,
                    "image_data": image_data
                }
                print(f"[Bot] 图片已生成，大小: {len(image_data)} bytes")

            cleaned_response, video_url = await self._process_video_in_response(cleaned_response, user_id, session_id)
            if video_url:
                self._last_generated_video = {
                    "user_id": user_id,
                    "session_id": session_id,
                    "video_url": video_url
                }
                print(f"[Bot] 视频已生成: {video_url}")

            # 处理回复中的委派标签 [DELEGATE: ...]
            cleaned_response, delegate_task = extract_delegate_tag(cleaned_response)
            if delegate_task and self.agent_delegator and self.agent_delegator.enabled:
                # 异步提交任务，不阻塞回复
                asyncio.create_task(
                    self.agent_delegator.submit(
                        task_description=delegate_task,
                        user_id=user_id,
                        session_id=session_id or user_id,
                        channel=self._resolve_channel(user_id, session_id),
                    )
                )
                print(f"[Bot] 委派任务已提交: {delegate_task[:80]}...")

            return cleaned_response
            
        except Exception as e:
            error_msg = f"对话处理失败: {str(e)}"
            print(error_msg)
            return error_msg
    
    async def chat_stream(self, message: str, user_id: str = "default", session_id: Optional[str] = None) -> AsyncGenerator[str, None]:
        """流式对话回复"""
        trace_start = time.perf_counter()
        stage_marks: Dict[str, float] = {}

        def mark(stage: str):
            stage_marks[stage] = round((time.perf_counter() - trace_start) * 1000, 2)

        try:
            session_id = session_id or user_id
            mark("session_ready")

            await self._get_user_config(user_id)
            mark("user_config_loaded")
            self._refresh_provider()
            provider = self._get_user_llm_provider(user_id)
            mark("provider_ready")

            mode_command_response = await self._handle_mode_switch_command(message, user_id, session_id)
            if mode_command_response is not None:
                yield mode_command_response
                mark("mode_command_done")
                print(
                    f"[Latency][bot.chat_stream][mode_command] user_id={user_id} session_id={session_id} "
                    f"stages_ms={json.dumps(stage_marks, ensure_ascii=False)}"
                )
                return

            if self._user_cache.get_chat_mode(user_id) == "roleplay":
                async for chunk in self._chat_roleplay_stream(message, user_id, session_id):
                    yield chunk
                mark("roleplay_stream_done")
                print(
                    f"[Latency][bot.chat_stream][roleplay] user_id={user_id} session_id={session_id} "
                    f"stages_ms={json.dumps(stage_marks, ensure_ascii=False)}"
                )
                return

            # 恢复最近的对话历史作为短期上下文
            await self._load_history_from_memory(user_id, session_id)
            history = self._get_session_history(session_id, user_id)
            mark("history_loaded")

            # 获取相关记忆（长期记忆）作为上下文
            relevant_memories = []
            if self.memory_manager:
                relevant_memories = await self._get_relevant_memories(user_id, message)
            mark("relevant_memories_loaded")

            # 使用 ContextBuilder 构建增强的对话历史
            enhanced_history = await self._context_builder.build(
                message=message,
                user_id=user_id,
                session_id=session_id,
                history=history,
                relevant_memories=relevant_memories,
            )
            mark("prompt_ready")
            
            # 同时添加用户消息到原始历史（不包含记忆上下文）
            now_ts = get_now().isoformat()
            history.append({
                "role": "user",
                "content": message,
                "timestamp": now_ts
            })
            
            # 调用LLM流式API（使用增强的历史）
            full_response = ""
            first_chunk_seen = False
            mark("llm_stream_start")
            async for chunk in provider.chat_stream(self._to_llm_messages(enhanced_history)):
                if chunk is None:
                    continue
                if not first_chunk_seen:
                    mark("llm_first_chunk")
                    first_chunk_seen = True
                chunk_text = str(chunk)
                full_response += chunk_text
                yield chunk_text
            mark("llm_stream_done")

            # 处理回复中的 TTS 标签 [TTS]...[/TTS]
            cleaned_tts, tts_forced_text = extract_tts_tag(full_response)
            if tts_forced_text:
                self._last_tts_forced_text = {
                    "user_id": user_id,
                    "session_id": session_id,
                    "text": tts_forced_text,
                }
                full_response = cleaned_tts
                print(f"[Bot Stream] AI主动触发TTS: {tts_forced_text[:60]}...")
            else:
                self._last_tts_forced_text = None

            # 处理回复中的图片标签 [GEN_IMG: ...]
            cleaned_response, image_data = await self._process_image_in_response(full_response, user_id, session_id)
            mark("image_processed")

            # 如果有图片生成，将图片数据存储到实例中供API调用
            if image_data:
                self._last_generated_image = {
                    "user_id": user_id,
                    "session_id": session_id,
                    "image_data": image_data
                }
                print(f"[Bot Stream] 图片已生成，大小: {len(image_data)} bytes")

            cleaned_response, video_url = await self._process_video_in_response(cleaned_response, user_id, session_id)
            mark("video_processed")
            if video_url:
                self._last_generated_video = {
                    "user_id": user_id,
                    "session_id": session_id,
                    "video_url": video_url
                }
                print(f"[Bot Stream] 视频已生成: {video_url}")

            # 如果清理后的响应与原始响应不同，需要重新记录到历史
            if cleaned_response != full_response:
                full_response = cleaned_response

            # 处理回复中的委派标签 [DELEGATE: ...]
            cleaned_delegate, delegate_task = extract_delegate_tag(full_response)
            if delegate_task and self.agent_delegator and self.agent_delegator.enabled:
                full_response = cleaned_delegate
                asyncio.create_task(
                    self.agent_delegator.submit(
                        task_description=delegate_task,
                        user_id=user_id,
                        session_id=session_id or user_id,
                        channel=self._resolve_channel(user_id, session_id),
                    )
                )
                print(f"[Bot Stream] 委派任务已提交: {delegate_task[:80]}...")

            # 添加完整回复到原始历史（不包含记忆上下文）
            history.append({
                "role": "assistant",
                "content": full_response,
                "timestamp": get_now().isoformat()
            })

            # 保持历史记录在合理范围内
            self._trim_conversation_history(session_id)

            # 将对话添加到记忆系统
            await self._add_conversation_to_memory(user_id, session_id, message, full_response)
            mark("conversation_persisted")

            print(
                f"[Latency][bot.chat_stream] user_id={user_id} session_id={session_id} "
                f"stages_ms={json.dumps(stage_marks, ensure_ascii=False)} "
                f"metrics={json.dumps({'relevant_memories': len(relevant_memories), 'history_messages': len(history)}, ensure_ascii=False)}"
            )

        except Exception as e:
            mark("error")
            print(
                f"[Latency][bot.chat_stream][error] user_id={user_id} session_id={session_id} "
                f"stages_ms={json.dumps(stage_marks, ensure_ascii=False)} error={str(e)}"
            )
            error_msg = f"流式对话处理失败: {str(e)}"
            print(error_msg)
            yield error_msg

    async def generate_proactive_reply(self, instruction: str, user_id: str = "default") -> str:
        """在没有用户输入的情况下生成一条主动问候的内容"""
        try:
            session_id = user_id
            self._refresh_provider()
            await self._get_user_config(user_id)
            provider = self._get_user_llm_provider(user_id)

            if self._user_cache.get_chat_mode(user_id) == "roleplay":
                return await self._generate_roleplay_proactive_reply(user_id, session_id)

            await self._load_history_from_memory(user_id, session_id)
            history = self._get_session_history(session_id, user_id)

            relevant_memories = []
            if self.memory_manager:
                relevant_memories = await self._get_relevant_memories(user_id, instruction)

            # 使用 ContextBuilder 构建增强的对话历史
            enhanced_history = await self._context_builder.build(
                message=instruction,
                user_id=user_id,
                session_id=session_id,
                history=history,
                relevant_memories=relevant_memories,
            )

            response = await provider.chat(self._to_llm_messages(enhanced_history))

            history.append({
                "role": "assistant",
                "content": response,
                "timestamp": get_now().isoformat()
            })
            self._trim_conversation_history(session_id)

            await self._record_proactive_memory(user_id, response)
            return response
        except Exception as e:
            error_msg = f"主动对话处理失败: {str(e)}"
            print(error_msg)
            return error_msg

    async def _record_proactive_memory(self, user_id: str, assistant_response: str):
        """仅记录一次主动问候的助手回复，避免写入虚构的用户内容"""
        if not self.memory_manager:
            return
        if not await self._ensure_memory_manager_initialized():
            return
        try:
            from ..memory.models import ConversationMessage
            msg = ConversationMessage(
                role="assistant",
                content=self._sanitize_for_memory(assistant_response),
                timestamp=get_now()
            )
            await self.memory_manager.add_short_term_memory(user_id, user_id, msg)
        except Exception as e:
            print(f"记录主动对话到记忆失败: {e}")

    async def run_mcp_tool(
        self, plugin_name: str, tool_name: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """执行 MCP 扩展中的指定工具"""
        if not self.mcp_manager:
            raise ValueError("MCP 扩展未初始化")
        return await self.mcp_manager.execute_tool(plugin_name, tool_name, params or {})
    
    async def test_connection(self) -> bool:
        """测试LLM连接"""
        self._refresh_provider()
        return await self.provider.test_connection()
    
    async def synthesize_speech(self, text: str, voice: Optional[str] = None, user_id: str = "default") -> Optional[bytes]:
        """合成语音"""
        await self._get_user_config(user_id)

        tts_manager = self._get_user_tts_manager(user_id) or self.tts_manager
        if not tts_manager:
            return None

        tts_text = tts_manager.select_text_for_tts(text)
        if not tts_text:
            return None
        
        try:
            return await tts_manager.synthesize(tts_text, voice)
        except Exception as e:
            print(f"TTS合成失败: {str(e)}")
            return None

    async def synthesize_speech_forced(self, text: str, voice: Optional[str] = None, user_id: str = "default") -> Optional[bytes]:
        """强制合成语音（AI 主动触发，跳过概率判断）

        Args:
            text: 要合成的文本（已由 AI 通过 [TTS] 标签指定）
            voice: 语音角色，可选
            user_id: 用户 ID

        Returns:
            bytes: 音频数据，失败返回 None
        """
        await self._get_user_config(user_id)

        tts_manager = self._get_user_tts_manager(user_id) or self.tts_manager
        if not tts_manager:
            return None

        if not tts_manager.config.enabled:
            return None

        # 检查是否允许 AI 主动触发 TTS
        if not getattr(tts_manager.config, "proactive_enabled", True):
            print(f"[Bot] AI主动触发TTS已禁用，跳过合成")
            return None

        # 文本清洗但跳过概率判断
        cleaned_text = tts_manager.text_cleaner.clean(text)
        if not cleaned_text.strip():
            return None

        try:
            return await tts_manager.synthesize(cleaned_text, voice)
        except Exception as e:
            print(f"TTS强制合成失败: {str(e)}")
            return None

    def get_last_tts_forced(self) -> Optional[Dict[str, Any]]:
        """获取并清除 AI 主动触发的 TTS 文本信息

        Returns:
            包含 user_id, session_id, text 的字典，如果没有则返回 None
        """
        data = getattr(self, '_last_tts_forced_text', None)
        self._last_tts_forced_text = None
        return data

    def maybe_get_emote_payload(self, user_message: str, assistant_response: str) -> Optional[Dict[str, Any]]:
        """根据上下文与概率返回一张表情包（前端/适配器可用）"""
        if not self.emote_manager:
            return None
        try:
            selection = self.emote_manager.select_emote(user_message, assistant_response)
            if not selection:
                return None
            return selection.to_public_dict()
        except Exception as e:
            print(f"选择表情包失败: {str(e)}")
            return None
    
    def is_voice_only_mode(self, user_id: str = "default") -> bool:
        """是否开启仅语音回复模式（有音频时不发送文本）"""
        tts_manager = self._user_tts_managers.get(user_id) or self._get_user_tts_manager(user_id) or self.tts_manager
        if not tts_manager:
            return False
        try:
            return bool(getattr(tts_manager.config, "voice_only_when_tts", False))
        except Exception:
            return False

    def strip_tts_text(self, text: str, user_id: str = "default") -> str:
        """移除已用于TTS的文本，避免重复"""
        tts_manager = self._user_tts_managers.get(user_id) or self._get_user_tts_manager(user_id) or self.tts_manager
        if not tts_manager:
            return text
        try:
            return tts_manager.get_remaining_text(text)
        except Exception:
            return text

    def get_last_tts_text(self, user_id: str = "default") -> Optional[str]:
        """获取最近一次真正送入TTS引擎的文本。"""
        tts_manager = self._user_tts_managers.get(user_id) or self._get_user_tts_manager(user_id) or self.tts_manager
        if not tts_manager:
            return None
        try:
            return tts_manager.get_last_synthesized_text()
        except Exception:
            return None

    def _sanitize_for_memory(self, text: str, max_length: int = 400) -> str:
        """存入记忆前的轻量清洗，去掉CQ码/冗长提示，做长度压缩。"""
        if not text:
            return ""
        cleaned = text.replace("\r", "")
        # 去掉CQ码等富文本标签
        cleaned = re.sub(r"\[CQ:[^\]]+\]", "", cleaned)
        # 图片生成请求/结果：只保留精简提示
        if cleaned.startswith("[图片生成请求]") or cleaned.startswith("[图片生成结果]"):
            try:
                prefix, prompt = cleaned.split("]", 1)
                prompt = prompt.strip()
                short_prompt = prompt[:120] + ("..." if len(prompt) > 120 else "")
                cleaned = f"{prefix}] {short_prompt}"
            except ValueError:
                cleaned = cleaned.strip()
        if cleaned.startswith("[视频生成请求]") or cleaned.startswith("[视频生成结果]"):
            try:
                prefix, prompt = cleaned.split("]", 1)
                prompt = prompt.strip()
                short_prompt = prompt[:120] + ("..." if len(prompt) > 120 else "")
                cleaned = f"{prefix}] {short_prompt}"
            except ValueError:
                cleaned = cleaned.strip()
        # 图片描述：缩成摘要，避免长段堆入记忆
        markers = [
            "这是一个图片的描述",
            "这是一张图片的描述",
            "以下是对这张图片的详细描述",
            "好的，这是一幅"
        ]
        for marker in markers:
            if marker in cleaned:
                before, after = cleaned.split(marker, 1)
                summary = after.strip()
                summary = summary[:180] + ("..." if len(summary) > 180 else "")
                cleaned = (before + "\n[图片描述摘要] " + summary).strip()
                break
        # 压缩多余空行/空白
        cleaned = re.sub(r"\n{2,}", "\n", cleaned).strip()
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length].rstrip() + "..."
        return cleaned

    async def _check_reminder_intent(self, message: str, user_id: str, session_id: str) -> str:
        """检测待办事项意图并创建待办事项"""
        reminder_config = config.get("reminder", {}) or {}
        if not reminder_config.get("enabled", False):
            return ""

        if not self.memory_manager:
            return ""

        try:
            # 确保记忆管理器已初始化
            if not await self._ensure_memory_manager_initialized():
                print("[Bot] 记忆管理器初始化失败，无法创建待办事项")
                return ""

            # 检查是否启用待办事项功能
            # 创建待办事项检测器
            from ..memory.reminder_detector import ReminderDetector
            timezone = reminder_config.get("timezone", "Asia/Shanghai")
            llm_fallback_enabled = bool(reminder_config.get("llm_fallback_enabled", False))
            detector = None
            try:
                detector = ReminderDetector(
                    self.provider,
                    timezone,
                    enable_llm_fallback=llm_fallback_enabled,
                )
                print(f"[Bot] 待办事项检测器创建成功，时区: {timezone}")
            except Exception as e:
                print(f"[Bot] 创建待办事项检测器失败（时区问题）: {e}")
                # 使用本地时间
                try:
                    detector = ReminderDetector(
                        self.provider,
                        None,
                        enable_llm_fallback=llm_fallback_enabled,
                    )
                    print(f"[Bot] 使用本地时间创建检测器成功")
                except Exception as e2:
                    print(f"[Bot] 创建本地时间检测器也失败: {e2}")
                    return ""

            # 检测待办事项意图
            if not detector:
                return ""
            reminder_data = await detector.detect_reminder_intent(message)

            if reminder_data:
                # 创建待办事项
                success = await self.memory_manager.add_reminder(
                    user_id=user_id,
                    session_id=session_id,
                    content=reminder_data.get("content", ""),
                    trigger_time=reminder_data.get("trigger_time"),
                    original_message=message,
                    time_expression=reminder_data.get("time_expression"),
                    reminder_message=reminder_data.get("reminder_message"),
                    metadata={"source": "auto_detect"}
                )

                if success:
                    print(f"[Bot] 已创建待办事项: {reminder_data.get('content')}")
                    # 不返回确认消息，由 LLM 自然回复
                    return ""

        except Exception as e:
            print(f"[Bot] 检测待办事项意图失败: {e}")

        return ""
    
    def _resolve_channel(self, user_id: str, session_id: Optional[str] = None) -> str:
        """根据 session_id 推断推送通道。

        优先从已注册的 channel 映射中查找，否则按规则推断。
        """
        sid = session_id or user_id

        # 优先从注册映射中查找
        if sid in self._session_channel_map:
            return self._session_channel_map[sid]
        if user_id in self._session_channel_map:
            return self._session_channel_map[user_id]

        # 按规则推断
        if sid.startswith("qq_group_"):
            return "qq_group"
        elif sid.startswith("qq_private_"):
            return "qq_private"
        elif sid.startswith("linyu_"):
            return "linyu_private"
        elif sid.isdigit():
            return "qq_private"
        return "web"

    def register_session_channel(self, session_id: str, channel: str) -> None:
        """注册 session/user 到 channel 的映射（由 adapter 调用）"""
        self._session_channel_map[session_id] = channel

    def clear_history(self, session_id: str = "default", user_id: str = "default"):
        """清空指定会话的对话历史"""
        system_prompt = self._get_user_system_prompt(user_id)
        self._history_manager.clear(session_id, system_prompt)
    
    def get_history(self, session_id: str = "default", user_id: str = "default") -> List[Dict[str, str]]:
        """获取指定会话的对话历史"""
        system_prompt = self._get_user_system_prompt(user_id)
        return self._history_manager.get_copy(session_id, system_prompt)
    
    def should_generate_image(self, message: str, user_id: str = "default") -> Optional[str]:
        """检查是否应该生成图像
        
        Args:
            message: 用户消息
            
        Returns:
            提取的提示词，如果不触发则返回None
        """
        image_mgr = self._user_image_gen_managers.get(user_id) or self._get_user_image_gen_manager(user_id) or self.image_gen_manager
        if image_mgr is None:
            return None
        return image_mgr.should_trigger_image_generation(message)

    def should_generate_video(self, message: str, user_id: str = "default") -> Optional[str]:
        """检查用户是否主动提出视频生成。"""
        video_mgr = self._user_video_gen_managers.get(user_id) or self._get_user_video_gen_manager(user_id) or self.video_gen_manager
        if video_mgr is None:
            return None
        return video_mgr.should_trigger_video_generation(message)

    def _video_intent_key(self, user_id: str, session_id: Optional[str]) -> str:
        return f"{user_id}:{session_id or user_id}"

    def _build_video_generation_hint(self, user_id: str, session_id: Optional[str], message: str) -> str:
        """命中用户视频意图时，为本轮 LLM 调用注入可配置视频提示。"""
        video_mgr = self._get_user_video_gen_manager(user_id) or self.video_gen_manager
        if not video_mgr:
            self._video_intent_sessions.pop(self._video_intent_key(user_id, session_id), None)
            return ""

        user_intent = video_mgr.should_trigger_video_generation(message)
        key = self._video_intent_key(user_id, session_id)
        if not user_intent:
            self._video_intent_sessions.pop(key, None)
            return ""

        self._video_intent_sessions[key] = user_intent
        return video_mgr.build_prompt_instruction(user_intent)
     
    async def generate_image(
        self,
        prompt: str,
        user_id: str = "default",
        session_id: Optional[str] = None,
    ) -> Optional[bytes]:
        """生成图像
        
        Args:
            prompt: 图像生成提示词
            
        Returns:
            图像二进制数据，失败返回None
        """
        session_id = session_id or user_id
        await self._get_user_config(user_id)

        image_mgr = self._get_user_image_gen_manager(user_id) or self.image_gen_manager
        if not image_mgr:
            return None
        enhanced_prompt = prompt
        try:
            # 使用本地词库增强提示词，提升人像细节
            from ..prompt_enhancer import get_enhancer

            enhancer = get_enhancer()
            enhanced_prompt = enhancer.enhance_prompt(prompt)
            # 控制台直出，方便后台确认生图实际使用的提示词
            print(f"[PromptEnhancer] 原始: {prompt} | 增强后: {enhanced_prompt}")
            self.logger.info("[PromptEnhancer] 原始: %s | 增强后: %s", prompt, enhanced_prompt)
        except Exception as e:
            print(f"[DEBUG] 提示词增强失败，使用原始提示词: {e}")

        # 底图按 username 存储，需要将数字 user_id 解析为 username
        effective_user_id = self._user_cache._resolve_username(user_id) or user_id
        image = await image_mgr.generate_image(enhanced_prompt, user_id=effective_user_id)
        if image:
            await self._record_image_generation(user_id, session_id, enhanced_prompt)
        return image
 
    async def _record_image_generation(self, user_id: str, session_id: str, prompt: str):
        """把图片生成事件写入对话上下文和记忆，方便后续追问"""
        try:
            await self._load_history_from_memory(user_id, session_id)
        except Exception as e:
            print(f"[DEBUG] 加载历史用于图片记录失败: {e}")

        short_prompt = self._sanitize_for_memory(prompt, max_length=160)
        note = f"[图片生成] 提示词：{short_prompt}"
        history = self._get_session_history(session_id, user_id)
        history.append({
            "role": "assistant",
            "content": note,
            "timestamp": get_now().isoformat()
        })
        self._trim_conversation_history(session_id, user_id)

        try:
            await self._add_conversation_to_memory(
                user_id,
                session_id,
                f"[图片生成请求] {short_prompt}",
                f"[图片生成结果] {short_prompt}"
            )
        except Exception as e:
            print(f"[DEBUG] 图片生成写入记忆失败: {e}")

    def _extract_image_prompt_from_response(self, response: str) -> Tuple[str, Optional[str]]:
        """解析回复中的 [GEN_IMG: ...] 标签

        Args:
            response: LLM返回的原始回复

        Returns:
            (清理后的文本, 图片提示词)，如果没有图片标签则返回 (原始文本, None)
        """
        return extract_gen_img_prompt(response)

    def _extract_video_prompt_from_response(self, response: str) -> Tuple[str, Optional[str]]:
        """解析回复中的 [GEN_VIDEO: ...] 标签。"""
        return extract_gen_video_prompt(response)

    async def _process_image_in_response(
        self,
        response: str,
        user_id: str,
        session_id: Optional[str] = None
    ) -> Tuple[str, Optional[bytes]]:
        """处理回复中的图片标签并生成图片

        Args:
            response: LLM返回的原始回复
            user_id: 用户ID
            session_id: 会话ID

        Returns:
            (清理后的文本, 图片数据)，如果没有图片或生成失败则返回 (清理后的文本, None)
        """
        cleaned_text, image_prompt = self._extract_image_prompt_from_response(response)

        if not image_prompt:
            return response, None

        # 检查图片生成是否启用
        image_mgr = self._get_user_image_gen_manager(user_id) or self.image_gen_manager
        if not image_mgr:
            print(f"[DEBUG] 图片生成管理器未启用，忽略生图请求")
            return cleaned_text or response, None

        # 生成图片
        try:
            image_bytes = await self.generate_image(image_prompt, user_id=user_id, session_id=session_id)
            if image_bytes:
                print(f"[Bot] 成功生成图片: {image_prompt}")
                return cleaned_text or response, image_bytes
            else:
                print(f"[Bot] 图片生成失败，返回纯文本")
                return cleaned_text or response, None
        except Exception as e:
            print(f"[Bot] 处理图片生成时出错: {e}")
            return cleaned_text or response, None

    def get_last_generated_image(self) -> Optional[Dict[str, Any]]:
        """获取并清除最近生成的图片数据

        Returns:
            包含图片数据的字典，如果没有图片则返回None
        """
        image_data = self._last_generated_image
        self._last_generated_image = None
        return image_data

    async def generate_video(
        self,
        prompt: str,
        user_id: str = "default",
        session_id: Optional[str] = None,
    ) -> Optional[str]:
        """生成视频并返回视频 URL。"""
        session_id = session_id or user_id
        await self._get_user_config(user_id)

        video_mgr = self._get_user_video_gen_manager(user_id) or self.video_gen_manager
        if not video_mgr:
            return None

        effective_user_id = self._user_cache._resolve_username(user_id) or user_id
        base_image_url = await self.video_base_image_service.get_base_image_data_url(effective_user_id)
        reference_images = [base_image_url] if base_image_url else None
        if reference_images:
            self.logger.info("[VideoGen] 使用用户上传底图生成参考图视频, user_id=%s", user_id)
        else:
            self.logger.warning(
                "[VideoGen] 用户 %s 未上传可用底图，自动回退到文生视频",
                user_id,
            )

        video_url = await video_mgr.generate_video(prompt, images=reference_images)
        if video_url:
            await self._record_video_generation(user_id, session_id, prompt, video_url)
        return video_url

    async def _record_video_generation(self, user_id: str, session_id: str, prompt: str, video_url: str):
        """把视频生成事件写入对话上下文和记忆，方便后续追问。"""
        try:
            await self._load_history_from_memory(user_id, session_id)
        except Exception as e:
            print(f"[DEBUG] 加载历史用于视频记录失败: {e}")

        short_prompt = self._sanitize_for_memory(prompt, max_length=160)
        note = f"[视频生成] 提示词：{short_prompt}\n视频地址：{video_url}"
        history = self._get_session_history(session_id, user_id)
        history.append({
            "role": "assistant",
            "content": note,
            "timestamp": get_now().isoformat()
        })
        self._trim_conversation_history(session_id, user_id)

        try:
            await self._add_conversation_to_memory(
                user_id,
                session_id,
                f"[视频生成请求] {short_prompt}",
                f"[视频生成结果] {short_prompt} {video_url}"
            )
        except Exception as e:
            print(f"[DEBUG] 视频生成写入记忆失败: {e}")

    async def _process_video_in_response(
        self,
        response: str,
        user_id: str,
        session_id: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        """处理回复中的视频标签并生成视频。"""
        cleaned_text, video_prompt = self._extract_video_prompt_from_response(response)
        if not video_prompt:
            return response, None

        key = self._video_intent_key(user_id, session_id)
        if key not in self._video_intent_sessions:
            print("[DEBUG] 当前轮未检测到用户视频生成意图，忽略 GEN_VIDEO 标签")
            return cleaned_text or response, None
        self._video_intent_sessions.pop(key, None)

        video_mgr = self._get_user_video_gen_manager(user_id) or self.video_gen_manager
        if not video_mgr:
            print("[DEBUG] 视频生成管理器未启用，忽略视频请求")
            return cleaned_text or response, None

        try:
            video_url = await self.generate_video(video_prompt, user_id=user_id, session_id=session_id)
            if video_url:
                print(f"[Bot] 成功生成视频: {video_prompt}")
                return cleaned_text or response, video_url
            print("[Bot] 视频生成失败，返回纯文本")
            return cleaned_text or response, None
        except Exception as e:
            print(f"[Bot] 处理视频生成时出错: {e}")
            return cleaned_text or response, None

    def get_last_generated_video(self) -> Optional[Dict[str, Any]]:
        """获取并清除最近生成的视频数据。"""
        video_data = self._last_generated_video
        self._last_generated_video = None
        return video_data

    def get_image_gen_config(self) -> Dict[str, Any]:
        """获取图像生成配置"""
        if not self.image_gen_manager:
            return {}
        return self.image_gen_manager.config.dict()

    def get_video_gen_config(self) -> Dict[str, Any]:
        """获取视频生成配置"""
        if not self.video_gen_manager:
            return {}
        return self.video_gen_manager.config.dict()
    
    def update_image_gen_config(self, config_dict: Dict[str, Any]):
        """更新图像生成配置"""
        if not self.image_gen_manager:
            return
        try:
            # 获取当前配置
            current_config = self.image_gen_manager.config.dict()
            
            # 深度合并配置：用新配置更新当前配置，但保留新配置中未提供的字段
            merged_config = self._deep_merge_config(current_config, config_dict)
            
            # 更新内存中的配置
            new_config = ImageGenerationConfig(**merged_config)
            self.image_gen_manager.update_config(new_config)
            
            # 持久化配置到文件
            config.update_config('image_generation', merged_config)
            print(f"图像生成配置已更新并保存: {merged_config}")
        except Exception as e:
            print(f"更新图像生成配置失败: {str(e)}")
            raise e

    def update_video_gen_config(self, config_dict: Dict[str, Any]):
        """更新视频生成配置"""
        if not self.video_gen_manager:
            self.video_gen_manager = VideoGenerationManager(VideoGenerationConfig())
        try:
            current_config = self.video_gen_manager.config.dict()
            merged_config = self._deep_merge_config(current_config, config_dict)
            new_config = VideoGenerationConfig(**merged_config)
            self.video_gen_manager.update_config(new_config)
            config.update_config('video_generation', merged_config)
            print(f"视频生成配置已更新并保存: {merged_config}")
        except Exception as e:
            print(f"更新视频生成配置失败: {str(e)}")
            raise e

    async def test_video_gen_connection(self, user_id: Optional[str] = None) -> bool:
        """测试视频生成连接。传入 user_id 时使用该用户的覆盖配置。"""
        video_mgr = self.video_gen_manager
        if user_id:
            await self._get_user_config(user_id)
            video_mgr = self._get_user_video_gen_manager(user_id) or self.video_gen_manager
        if not video_mgr:
            return False
        return await video_mgr.test_connection()
    
    async def test_image_gen_connection(self) -> bool:
        """测试图像生成连接"""
        if not self.image_gen_manager:
            return False
        return await self.image_gen_manager.test_connection()
    
    def should_recognize_image(self, message_segments: list) -> bool:
        """检查是否应该识别图片
        
        Args:
            message_segments: 消息段列表
            
        Returns:
            是否触发识别
        """
        if not self.vision_manager:
            return False
        return self.vision_manager.should_trigger_vision_recognition(message_segments)
    
    async def recognize_image(self, image_url: Optional[str] = None, image_data: Optional[bytes] = None,
                             prompt: Optional[str] = None) -> str:
        """识别图片

        Args:
            image_url: 图片URL
            image_data: 图片二进制数据
            prompt: 识别提示词

        Returns:
            识别结果文本
        """
        if not self.vision_manager:
            return ""
        return await self.vision_manager.recognize_image(image_url, image_data, prompt)

    async def transcribe_voice(self, audio_data: bytes, filename: str = "audio.mp3") -> str:
        """语音转文本

        Args:
            audio_data: 音频二进制数据
            filename: 文件名

        Returns:
            识别结果文本
        """
        if not self.asr_manager:
            return ""
        return await self.asr_manager.transcribe_audio(audio_data, filename)

    def get_vision_config(self) -> Dict[str, Any]:
        """获取视觉识别配置"""
        if not self.vision_manager:
            return {}
        config = self.vision_manager.config.dict()
        print(f"[DEBUG] Bot实例ID: {id(self)}, get_vision_config返回: follow_up_timeout={config.get('follow_up_timeout', 'NOT FOUND')}")
        return config
    
    def update_vision_config(self, config_dict: Dict[str, Any]):
        """更新视觉识别配置"""
        if not self.vision_manager:
            return
        try:
            # 获取当前配置
            current_config = self.vision_manager.config.dict()
            print(f"[DEBUG] 更新视觉识别配置 - 当前配置: {list(current_config.keys())}")
            print(f"[DEBUG] 当前配置包含modelscope: {'modelscope' in current_config}")
            if 'modelscope' in current_config:
                print(f"[DEBUG] modelscope包含字段: {list(current_config['modelscope'].keys())}")
            
            print(f"[DEBUG] 收到的新配置: {list(config_dict.keys())}")
            if 'modelscope' in config_dict:
                print(f"[DEBUG] 新配置包含modelscope: {config_dict['modelscope']}")
            if 'follow_up_timeout' in config_dict:
                print(f"[DEBUG] 新配置follow_up_timeout值: {config_dict['follow_up_timeout']}")
            
            # 深度合并配置：用新配置更新当前配置，但保留新配置中未提供的字段
            merged_config = self._deep_merge_config(current_config, config_dict)
            print(f"[DEBUG] 合并后配置: {list(merged_config.keys())}")
            if 'modelscope' in merged_config:
                print(f"[DEBUG] 合并后modelscope包含字段: {list(merged_config['modelscope'].keys())}")
            if 'follow_up_timeout' in merged_config:
                print(f"[DEBUG] 合并后follow_up_timeout值: {merged_config['follow_up_timeout']}")
                # 安全地检查api_key是否存在
                if 'api_key' in merged_config['modelscope']:
                    api_key = merged_config['modelscope']['api_key']
                    if api_key:
                        print(f"[DEBUG] modelscope api_key存在，长度: {len(api_key)}")
                    else:
                        print(f"[WARNING] modelscope api_key为空!")
                else:
                    print(f"[ERROR] modelscope缺少api_key字段!")
            
            # 更新内存中的配置
            new_config = VisionRecognitionConfig(**merged_config)
            self.vision_manager.update_config(new_config)
            
            # 持久化配置到文件
            config.update_config('vision', merged_config)
            print(f"视觉识别配置已更新并保存")
        except Exception as e:
            print(f"更新视觉识别配置失败: {str(e)}")
            raise e
    
    def _deep_merge_config(self, current: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """深度合并配置字典
        
        Args:
            current: 当前配置字典
            new: 新配置字典
            
        Returns:
            合并后的配置字典
        """
        result = current.copy()
        
        for key, value in new.items():
            if key not in result:
                # 新键，直接添加
                result[key] = value
            elif isinstance(result[key], dict) and isinstance(value, dict):
                # 递归合并嵌套字典
                result[key] = self._deep_merge_config(result[key], value)
            elif value is not None and value != "" and value != {} and value != []:
                # 非空值，更新
                result[key] = value
            # 空值保持不变，避免覆盖现有配置
        
        return result
    
    async def test_vision_connection(self) -> bool:
        """测试视觉识别连接"""
        if not self.vision_manager:
            return False
        return await self.vision_manager.test_connection()
