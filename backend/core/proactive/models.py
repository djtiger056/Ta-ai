"""主动聊天数据模型

从 core/proactive.py 中提取的 dataclass 定义。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class WindowState:
    """时间窗口状态"""
    scheduled_time: Optional[datetime] = None
    scheduled_date: Optional[datetime] = None
    sent_today: int = 0
    last_sent: Optional[datetime] = None


@dataclass
class ProactiveTargetState:
    """主动聊天目标状态"""
    last_sent: Optional[datetime] = None
    windows: Dict[str, WindowState] = field(default_factory=dict)
    images_sent_today: int = 0
    image_quota_date: Optional[datetime] = None
    activity: Dict[str, Any] = field(default_factory=dict)
    web_pending_messages: List[Dict[str, Any]] = field(default_factory=list)
    next_web_message_id: int = 1
    pending_motivation: Optional[Dict[str, Any]] = None
