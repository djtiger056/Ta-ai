"""提示词管理器

负责每个用户提示词的读取、写入、变更记录。
存储位置：user_data/{username}/system_prompt.md
变更记录：user_data/{username}/prompt_history.json
"""

import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from backend.prompt_system.models import PromptChangeRecord, PromptData, PromptHistory
from backend.user.data_manager import user_data_manager
from backend.utils.datetime_utils import get_now
from backend.config import config

logger = logging.getLogger(__name__)

PROMPT_FILE = "system_prompt.md"
RULES_FILE = "system_rules.md"
ROLEPLAY_PROMPT_FILE = "roleplay_prompt.md"
HISTORY_FILE = "prompt_history.json"
MAX_HISTORY_RECORDS = 50  # 最多保留最近 50 条变更记录

DEFAULT_ROLEPLAY_PROMPT = """# 情景演绎模式
你正在与用户进行视觉小说式的情景演绎。只使用纯文本，不触发语音、图片、工具、代理或现实任务。

回复要求：
- 始终沉浸在当前剧情中，延续上一轮情境。
- 可以描写动作、环境、表情、心理活动和细腻情绪。
- 不要跳出角色解释“我是 AI”或说明规则。
- 不要替用户决定关键行动；可以描写对方行为带来的感受，并把选择权留给用户。
- 每次回复使用下面的 Markdown 结构：

### 状态
- 心情：
- 目前状态：
- 关系氛围：

### 动作

### 心理

### 台词
"""


class PromptManager:
    """提示词管理器"""

    def __init__(self):
        self._cache: Dict[str, str] = {}  # username -> prompt content 缓存

    def _get_prompt_path(self, username: str) -> Path:
        """获取用户提示词文件路径"""
        user_dir = user_data_manager._get_user_dir(username)
        return user_dir / PROMPT_FILE

    def _get_rules_path(self, username: str) -> Path:
        """获取用户功能协议文件路径"""
        user_dir = user_data_manager._get_user_dir(username)
        return user_dir / RULES_FILE

    def _get_roleplay_prompt_path(self, username: str) -> Path:
        """获取用户情景演绎提示词文件路径"""
        user_dir = user_data_manager._get_user_dir(username)
        return user_dir / ROLEPLAY_PROMPT_FILE

    def _get_history_path(self, username: str) -> Path:
        """获取用户提示词变更历史文件路径"""
        user_dir = user_data_manager._get_user_dir(username)
        return user_dir / HISTORY_FILE

    def get_prompt(self, username: str) -> Optional[str]:
        """获取用户的系统提示词
        
        优先级：
        1. 内存缓存
        2. 用户提示词文件 (system_prompt.md)
        3. 返回 None（由调用方决定是否回退到全局配置）
        
        Args:
            username: 用户名
            
        Returns:
            提示词内容，如果用户没有独立提示词则返回 None
        """
        # 检查缓存
        if username in self._cache:
            return self._cache[username]

        # 从文件读取
        prompt_path = self._get_prompt_path(username)
        if not prompt_path.exists():
            return None

        try:
            content = prompt_path.read_text(encoding="utf-8").strip()
            if content:
                self._cache[username] = content
                return content
            return None
        except Exception as e:
            logger.error(f"读取用户提示词失败 username={username}: {e}")
            return None

    def get_prompt_data(self, username: str) -> PromptData:
        """获取用户提示词完整数据（含元信息）"""
        content = self.get_prompt(username)
        prompt_path = self._get_prompt_path(username)

        if content is None:
            return PromptData(content="", updated_at=None, source="system")

        # 读取文件修改时间
        updated_at = None
        if prompt_path.exists():
            try:
                from datetime import datetime
                mtime = prompt_path.stat().st_mtime
                updated_at = datetime.fromtimestamp(mtime).isoformat()
            except Exception:
                pass

        # 从历史记录中获取最后修改来源
        history = self.get_history(username)
        source = "system"
        if history.records:
            source = history.records[-1].source

        return PromptData(content=content, updated_at=updated_at, source=source)

    def set_prompt(
        self,
        username: str,
        content: str,
        source: str = "user",
        summary: str = "",
    ) -> bool:
        """设置用户的系统提示词
        
        Args:
            username: 用户名
            content: 新的提示词内容
            source: 变更来源 (user / ai / system / migration)
            summary: 变更摘要
            
        Returns:
            是否成功
        """
        try:
            # 确保用户目录存在
            user_data_manager._ensure_user_dirs(username)

            # 读取旧内容用于记录
            old_content = self.get_prompt(username) or ""

            # 写入新提示词
            prompt_path = self._get_prompt_path(username)
            prompt_path.write_text(content, encoding="utf-8")

            # 更新缓存
            self._cache[username] = content

            # 记录变更历史
            self._add_history_record(
                username=username,
                source=source,
                summary=summary,
                previous_length=len(old_content),
                new_length=len(content),
            )

            logger.info(
                f"提示词已更新 username={username} source={source} "
                f"length={len(old_content)}->{len(content)}"
            )
            return True
        except Exception as e:
            logger.error(f"设置用户提示词失败 username={username}: {e}")
            return False

    def delete_prompt(self, username: str, source: str = "user") -> bool:
        """删除用户的独立提示词（回退到全局默认）
        
        Args:
            username: 用户名
            source: 操作来源
            
        Returns:
            是否成功
        """
        try:
            prompt_path = self._get_prompt_path(username)
            old_content = self.get_prompt(username) or ""

            if prompt_path.exists():
                prompt_path.unlink()

            # 清除缓存
            self._cache.pop(username, None)

            # 记录变更
            self._add_history_record(
                username=username,
                source=source,
                summary="删除独立提示词，回退到全局默认",
                previous_length=len(old_content),
                new_length=0,
            )

            logger.info(f"提示词已删除 username={username}")
            return True
        except Exception as e:
            logger.error(f"删除用户提示词失败 username={username}: {e}")
            return False

    def get_history(self, username: str, limit: int = 20) -> PromptHistory:
        """获取提示词变更历史
        
        Args:
            username: 用户名
            limit: 返回最近 N 条记录
            
        Returns:
            变更历史
        """
        history_path = self._get_history_path(username)
        if not history_path.exists():
            return PromptHistory()

        try:
            data = json.loads(history_path.read_text(encoding="utf-8"))
            records = [PromptChangeRecord(**r) for r in data.get("records", [])]
            # 返回最近的 limit 条
            return PromptHistory(records=records[-limit:])
        except Exception as e:
            logger.error(f"读取提示词历史失败 username={username}: {e}")
            return PromptHistory()

    def invalidate_cache(self, username: str) -> None:
        """清除指定用户的提示词缓存（配置变更时调用）"""
        self._cache.pop(username, None)

    def invalidate_all_cache(self) -> None:
        """清除所有缓存"""
        self._cache.clear()

    def migrate_from_config(self, username: str) -> bool:
        """从全局 config.yaml 迁移提示词到用户独立文件
        
        仅在用户没有独立提示词文件时执行。
        
        Args:
            username: 用户名
            
        Returns:
            是否执行了迁移
        """
        # 如果已有独立提示词，不迁移
        if self.get_prompt(username) is not None:
            return False

        # 先检查用户 config.yaml 中是否有 system_prompt
        user_config = user_data_manager.load_user_config(username)
        user_prompt = None
        if user_config and isinstance(user_config, dict):
            user_prompt = user_config.get("system_prompt")

        # 如果用户配置中有提示词，优先迁移用户的
        if user_prompt and isinstance(user_prompt, str) and user_prompt.strip():
            return self.set_prompt(
                username=username,
                content=user_prompt.strip(),
                source="migration",
                summary="从用户 config.yaml 迁移",
            )

        # 否则使用全局提示词
        global_prompt = config.system_prompt
        if global_prompt and global_prompt.strip():
            return self.set_prompt(
                username=username,
                content=global_prompt.strip(),
                source="migration",
                summary="从全局 config.yaml 迁移",
            )

        return False

    def get_effective_prompt(self, username: str) -> str:
        """获取用户最终生效的提示词
        
        优先级：
        1. 用户独立提示词文件
        2. 全局 config.yaml 中的 system_prompt
        
        Args:
            username: 用户名
            
        Returns:
            最终生效的提示词
        """
        user_prompt = self.get_prompt(username)
        if user_prompt:
            return user_prompt
        return config.system_prompt or ""

    # ---- system_rules（功能协议层）----

    def get_rules(self, username: str) -> Optional[str]:
        """获取用户的功能协议（system_rules）。

        优先级：
        1. 用户独立文件 (system_rules.md)
        2. 返回 None（由调用方决定是否回退到全局配置）

        Args:
            username: 用户名

        Returns:
            功能协议内容，如果用户没有独立配置则返回 None
        """
        rules_path = self._get_rules_path(username)
        if not rules_path.exists():
            return None
        try:
            content = rules_path.read_text(encoding="utf-8").strip()
            return content if content else None
        except Exception as e:
            logger.error(f"读取用户功能协议失败 username={username}: {e}")
            return None

    def set_rules(
        self,
        username: str,
        content: str,
        source: str = "user",
        summary: str = "",
    ) -> bool:
        """设置用户的功能协议（system_rules）。

        Args:
            username: 用户名
            content: 新的功能协议内容
            source: 变更来源
            summary: 变更摘要

        Returns:
            是否成功
        """
        try:
            user_data_manager._ensure_user_dirs(username)
            rules_path = self._get_rules_path(username)
            rules_path.write_text(content, encoding="utf-8")
            logger.info(f"功能协议已更新 username={username} source={source} length={len(content)}")
            return True
        except Exception as e:
            logger.error(f"设置用户功能协议失败 username={username}: {e}")
            return False

    def delete_rules(self, username: str) -> bool:
        """删除用户的独立功能协议（回退到全局默认）。"""
        try:
            rules_path = self._get_rules_path(username)
            if rules_path.exists():
                rules_path.unlink()
            logger.info(f"功能协议已删除 username={username}")
            return True
        except Exception as e:
            logger.error(f"删除用户功能协议失败 username={username}: {e}")
            return False

    def get_effective_rules(self, username: str) -> str:
        """获取用户最终生效的功能协议。

        优先级：
        1. 用户独立文件 (system_rules.md)
        2. 全局 config.yaml 中的 system_rules

        Args:
            username: 用户名

        Returns:
            最终生效的功能协议，可能为空字符串
        """
        user_rules = self.get_rules(username)
        if user_rules is not None:
            return user_rules
        return config.system_rules or ""

    # ---- roleplay_prompt（情景演绎模式人设层）----

    def get_roleplay_prompt(self, username: str) -> Optional[str]:
        """获取用户独立情景演绎提示词。"""
        prompt_path = self._get_roleplay_prompt_path(username)
        if not prompt_path.exists():
            return None
        try:
            content = prompt_path.read_text(encoding="utf-8").strip()
            return content if content else None
        except Exception as e:
            logger.error(f"读取用户情景演绎提示词失败 username={username}: {e}")
            return None

    def get_effective_roleplay_prompt(self, username: str) -> str:
        """获取用户最终生效的情景演绎提示词。"""
        return self.get_roleplay_prompt(username) or DEFAULT_ROLEPLAY_PROMPT

    def set_roleplay_prompt(self, username: str, content: str) -> bool:
        """设置用户情景演绎提示词。"""
        try:
            user_data_manager._ensure_user_dirs(username)
            prompt_path = self._get_roleplay_prompt_path(username)
            prompt_path.write_text(content, encoding="utf-8")
            logger.info(f"情景演绎提示词已更新 username={username} length={len(content)}")
            return True
        except Exception as e:
            logger.error(f"设置用户情景演绎提示词失败 username={username}: {e}")
            return False

    def delete_roleplay_prompt(self, username: str) -> bool:
        """删除用户独立情景演绎提示词，回退到默认。"""
        try:
            prompt_path = self._get_roleplay_prompt_path(username)
            if prompt_path.exists():
                prompt_path.unlink()
            logger.info(f"情景演绎提示词已删除 username={username}")
            return True
        except Exception as e:
            logger.error(f"删除用户情景演绎提示词失败 username={username}: {e}")
            return False

    def _add_history_record(
        self,
        username: str,
        source: str,
        summary: str,
        previous_length: int,
        new_length: int,
    ) -> None:
        """添加变更记录"""
        try:
            history_path = self._get_history_path(username)

            # 读取已有记录
            records: List[Dict[str, Any]] = []
            if history_path.exists():
                try:
                    data = json.loads(history_path.read_text(encoding="utf-8"))
                    records = data.get("records", [])
                except Exception:
                    records = []

            # 添加新记录
            record = PromptChangeRecord(
                timestamp=get_now().isoformat(),
                source=source,
                summary=summary,
                previous_length=previous_length,
                new_length=new_length,
            )
            records.append(record.model_dump())

            # 限制记录数量
            if len(records) > MAX_HISTORY_RECORDS:
                records = records[-MAX_HISTORY_RECORDS:]

            # 写入文件
            history_path.write_text(
                json.dumps({"records": records}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"写入提示词变更记录失败 username={username}: {e}")


# 全局实例
prompt_manager = PromptManager()
