"""提示词系统

独立管理每个用户的系统提示词，支持动态修改和变更记录。
"""

from backend.prompt_system.manager import DEFAULT_ROLEPLAY_PROMPT, PromptManager, prompt_manager

__all__ = ["DEFAULT_ROLEPLAY_PROMPT", "PromptManager", "prompt_manager"]
