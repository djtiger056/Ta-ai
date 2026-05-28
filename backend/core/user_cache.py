"""用户资源缓存

负责管理每个用户的配置缓存、LLM Provider 实例缓存、TTS Manager 缓存、
ImageGen Manager 缓存等。从 bot.py 中提取，降低 Bot 类的复杂度。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from ..config import config
from ..providers import get_provider
from ..tts.manager import TTSManager
from ..image_gen import ImageGenerationManager, ImageGenerationConfig
from ..video_gen import VideoGenerationManager, VideoGenerationConfig
from ..user import user_manager
from ..utils.config_merger import config_merger
from ..utils.datetime_utils import get_now
from ..prompt_system import prompt_manager


logger = logging.getLogger(__name__)


class UserResourceCache:
    """管理用户级别的配置和资源实例缓存。

    每个用户可以有独立的 LLM/TTS/ImageGen 配置，此类负责：
    - 从数据库加载用户配置（带 TTL 缓存）
    - 合并用户配置与全局配置
    - 按配置签名缓存 Provider/Manager 实例，配置变化时自动重建
    """

    def __init__(self, config_cache_ttl: int = 300):
        """
        Args:
            config_cache_ttl: 配置缓存有效期（秒）
        """
        self._config_cache_ttl = config_cache_ttl

        # 用户配置缓存
        self._user_configs: Dict[str, Dict[str, Any]] = {}
        self._user_config_cache_time: Dict[str, datetime] = {}

        # user_id -> username 映射缓存（用于提示词系统）
        self._user_id_to_username: Dict[str, str] = {}

        # 用户级别的 LLM Provider 实例缓存
        self._user_providers: Dict[str, Any] = {}
        self._user_provider_signatures: Dict[str, str] = {}

        # 用户级别的 TTS Manager 实例缓存
        self._user_tts_managers: Dict[str, TTSManager] = {}
        self._user_tts_signatures: Dict[str, str] = {}

        # 用户级别的 ImageGen Manager 实例缓存
        self._user_image_gen_managers: Dict[str, ImageGenerationManager] = {}
        self._user_image_gen_signatures: Dict[str, str] = {}

        # 用户级别的 VideoGen Manager 实例缓存
        self._user_video_gen_managers: Dict[str, VideoGenerationManager] = {}
        self._user_video_gen_signatures: Dict[str, str] = {}

    async def get_user_config(self, user_id: str) -> Dict[str, Any]:
        """获取用户配置（带缓存）。

        Args:
            user_id: 用户 ID

        Returns:
            用户配置字典
        """
        current_time = get_now()
        if user_id in self._user_config_cache_time:
            cache_time = self._user_config_cache_time[user_id]
            if (current_time - cache_time).total_seconds() < self._config_cache_ttl:
                return self._user_configs.get(user_id, {})

        user_config = {}
        try:
            user = await self.resolve_user(user_id)
            if user:
                user_config = await user_manager.get_user_config_dict(user.id)
                # 缓存 user_id -> username 映射（供提示词系统使用）
                self._user_id_to_username[user_id] = user.username
        except Exception as e:
            logger.warning(f"获取用户配置失败: {e}")

        # 更新缓存
        self._user_configs[user_id] = user_config
        self._user_config_cache_time[user_id] = current_time

        return user_config

    async def resolve_user(self, user_id: str):
        """按 Web 数字 ID、QQ ID、Linyu ID、username 解析真实用户。"""
        user = None
        user_id_str = str(user_id)

        if user_id_str.isdigit():
            user = await user_manager.get_user_by_id(int(user_id_str))

        if user is None:
            user = await user_manager.get_user_by_qq_id(user_id_str)

        if user is None:
            user = await user_manager.get_user_by_linyu_id(user_id_str)

        # 数字 ID 和 QQ/Linyu 都没找到，尝试按 username 精确匹配
        if user is None:
            user = await user_manager.get_user_by_username(user_id_str)

        if user is None and not user_id_str.isdigit():
            is_uuid = len(user_id_str) == 36 and user_id_str.count("-") == 4
            if not is_uuid:
                try:
                    user = await user_manager.get_or_create_user_by_qq_id(user_id_str)
                except Exception as e:
                    logger.warning(f"自动创建 QQ 用户失败 user_id={user_id}: {e}")

        if user:
            self._user_id_to_username[user_id_str] = user.username
        return user

    def get_merged_config(self, user_id: str) -> Dict[str, Any]:
        """获取合并后的用户配置（全局 + 用户覆盖）。

        注意：此方法是同步的，依赖 get_user_config 已被调用过（缓存已填充）。

        Args:
            user_id: 用户 ID

        Returns:
            合并后的配置字典
        """
        user_config = self._user_configs.get(user_id, {})

        global_config = {
            'system_prompt': config.system_prompt,
            'llm': config.llm_config,
            'tts': config.tts_config,
            'image_generation': config.image_gen_config.dict() if hasattr(config.image_gen_config, 'dict') else {},
            'video_generation': config.video_gen_config.dict() if hasattr(config.video_gen_config, 'dict') else {},
            'vision': config.vision_config.dict() if hasattr(config.vision_config, 'dict') else {},
            'emotes': config.emote_config.dict() if hasattr(config.emote_config, 'dict') else {},
            'prompt_enhancer': config.prompt_enhancer_config.dict() if hasattr(config.prompt_enhancer_config, 'dict') else {},
            'proactive_chat': config.proactive_chat_config,
        }

        return config_merger.get_user_config(global_config, user_config, skip_empty=True)

    def get_llm_provider(self, user_id: str, fallback_provider=None) -> Any:
        """获取该用户的 LLM Provider（按用户配置缓存）。

        Args:
            user_id: 用户 ID
            fallback_provider: 配置无效时的回退 provider

        Returns:
            LLM Provider 实例
        """
        merged = self.get_merged_config(user_id)
        llm_cfg = merged.get("llm", {}) or {}
        signature = json.dumps(llm_cfg, sort_keys=True, ensure_ascii=False)

        cached = self._user_providers.get(user_id)
        if cached is not None and self._user_provider_signatures.get(user_id) == signature:
            return cached

        try:
            provider_name = llm_cfg.get("provider", "openai")
            provider = get_provider(provider_name, llm_config=llm_cfg)
        except Exception as e:
            logger.warning(f"用户 LLM 配置无效，回退全局配置 user_id={user_id}: {e}")
            provider = fallback_provider

        self._user_providers[user_id] = provider
        self._user_provider_signatures[user_id] = signature
        return provider

    def get_tts_manager(self, user_id: str) -> Optional[TTSManager]:
        """获取该用户的 TTSManager（按用户配置缓存）。"""
        merged = self.get_merged_config(user_id)
        tts_cfg = merged.get("tts", {}) or {}
        signature = json.dumps(tts_cfg, sort_keys=True, ensure_ascii=False)

        cached = self._user_tts_managers.get(user_id)
        if cached is not None and self._user_tts_signatures.get(user_id) == signature:
            return cached

        try:
            manager = TTSManager(tts_cfg)
        except Exception as e:
            logger.warning(f"用户 TTS 配置无效，禁用 TTS user_id={user_id}: {e}")
            manager = None

        if manager is not None:
            self._user_tts_managers[user_id] = manager
            self._user_tts_signatures[user_id] = signature

        return manager

    def get_image_gen_manager(self, user_id: str) -> Optional[ImageGenerationManager]:
        """获取该用户的 ImageGenerationManager（按用户配置缓存）。"""
        merged = self.get_merged_config(user_id)
        image_cfg = merged.get("image_generation", {}) or {}
        signature = json.dumps(image_cfg, sort_keys=True, ensure_ascii=False)

        cached = self._user_image_gen_managers.get(user_id)
        if cached is not None and self._user_image_gen_signatures.get(user_id) == signature:
            return cached

        try:
            manager = ImageGenerationManager(ImageGenerationConfig(**image_cfg))
        except Exception as e:
            logger.warning(f"用户图像生成配置无效，禁用图像生成 user_id={user_id}: {e}")
            return None

        self._user_image_gen_managers[user_id] = manager
        self._user_image_gen_signatures[user_id] = signature
        return manager

    def get_video_gen_manager(self, user_id: str) -> Optional[VideoGenerationManager]:
        """获取该用户的 VideoGenerationManager（按用户配置缓存）。"""
        merged = self.get_merged_config(user_id)
        video_cfg = merged.get("video_generation", {}) or {}
        signature = json.dumps(video_cfg, sort_keys=True, ensure_ascii=False)

        cached = self._user_video_gen_managers.get(user_id)
        if cached is not None and self._user_video_gen_signatures.get(user_id) == signature:
            return cached

        try:
            manager = VideoGenerationManager(VideoGenerationConfig(**video_cfg))
        except Exception as e:
            logger.warning(f"用户视频生成配置无效，禁用视频生成 user_id={user_id}: {e}")
            return None

        self._user_video_gen_managers[user_id] = manager
        self._user_video_gen_signatures[user_id] = signature
        return manager

    def invalidate_user(self, user_id: str) -> None:
        """清除指定用户的配置和派生资源缓存。"""
        self._user_configs.pop(user_id, None)
        self._user_config_cache_time.pop(user_id, None)
        self._user_id_to_username.pop(user_id, None)

        self._user_providers.pop(user_id, None)
        self._user_provider_signatures.pop(user_id, None)

        self._user_tts_managers.pop(user_id, None)
        self._user_tts_signatures.pop(user_id, None)

        self._user_image_gen_managers.pop(user_id, None)
        self._user_image_gen_signatures.pop(user_id, None)

        self._user_video_gen_managers.pop(user_id, None)
        self._user_video_gen_signatures.pop(user_id, None)

    def get_system_prompt(self, user_id: str) -> str:
        """获取用户的系统提示词（人设层）。

        优先级：
        1. 提示词系统（user_data/{username}/system_prompt.md）
        2. 用户配置中的 system_prompt（旧路径兼容）
        3. 全局 config.yaml 中的 system_prompt
        """
        # 尝试通过提示词系统获取
        username = self._resolve_username(user_id)
        if username:
            prompt = prompt_manager.get_prompt(username)
            if prompt:
                return prompt

        # 回退到旧逻辑（用户配置 > 全局配置）
        user_config = self._user_configs.get(user_id, {})
        return config_merger.get_system_prompt(config.system_prompt, user_config.get('system_prompt'))

    def get_system_rules(self, user_id: str) -> str:
        """获取用户的功能协议层提示词（视觉/语音/委派等协议）。

        优先级：
        1. 提示词系统（user_data/{username}/system_rules.md）
        2. 全局 config.yaml 中的 system_rules

        Returns:
            功能协议内容，可能为空字符串（表示不注入）
        """
        username = self._resolve_username(user_id)
        if username:
            return prompt_manager.get_effective_rules(username)
        return config.system_rules or ""

    def get_roleplay_prompt(self, user_id: str) -> str:
        """获取用户情景演绎模式提示词。"""
        username = self._resolve_username(user_id)
        if username:
            return prompt_manager.get_effective_roleplay_prompt(username)
        from ..prompt_system import DEFAULT_ROLEPLAY_PROMPT
        return DEFAULT_ROLEPLAY_PROMPT

    def get_chat_mode(self, user_id: str) -> str:
        """获取用户聊天模式，默认 companion。"""
        user_config = self._user_configs.get(user_id, {}) or {}
        preferences = user_config.get("preferences", {}) or {}
        mode = str(preferences.get("chat_mode", "companion") or "companion").strip().lower()
        return "roleplay" if mode == "roleplay" else "companion"

    def get_roleplay_memory_config(self, user_id: str) -> Dict[str, Any]:
        """获取用户情景演绎记忆配置覆盖项。"""
        user_config = self._user_configs.get(user_id, {}) or {}
        preferences = user_config.get("preferences", {}) or {}
        roleplay_memory = preferences.get("roleplay_memory", {}) or {}
        return roleplay_memory if isinstance(roleplay_memory, dict) else {}

    def invalidate_user(self, user_id: str) -> None:
        """清理指定用户缓存，使配置变更立即生效。"""
        self._user_configs.pop(user_id, None)
        self._user_config_cache_time.pop(user_id, None)
        self._user_providers.pop(user_id, None)
        self._user_provider_signatures.pop(user_id, None)
        self._user_tts_managers.pop(user_id, None)
        self._user_tts_signatures.pop(user_id, None)
        self._user_image_gen_managers.pop(user_id, None)
        self._user_image_gen_signatures.pop(user_id, None)

    def _resolve_username(self, user_id: str) -> Optional[str]:
        """从 user_id 解析出 username（用于提示词系统文件路径）。

        user_id 可能是数字 ID 或 QQ 号，需要映射到 username。
        优先使用 get_user_config 时缓存的映射。
        """
        if not user_id or user_id == "default":
            return None

        # 优先使用已缓存的映射（最准确）
        if user_id in self._user_id_to_username:
            return self._user_id_to_username[user_id]

        # 如果 user_id 不是纯数字，可能本身就是 username
        if not user_id.isdigit():
            return user_id

        # 纯数字时构造 qq_{user_id} 格式（与自动建档逻辑一致）
        return f"qq_{user_id}"
