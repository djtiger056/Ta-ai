import json
import os
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from .manager import MCPPlugin
from .schedule_generator import default_generated_path


DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "timezone": "Asia/Shanghai",
    "default_schedule": "weekday",
    "weekend_schedule": "weekend",
    "override": {
        "enabled": False,
        "activity": "",
        "desc": "",
        "expires_at": None,
    },
    "schedules": {
        "weekday": [
            {"start": "07:00", "end": "07:40", "activity": "起床洗漱", "desc": "刚醒，声音有点迷糊，正在刷牙收拾。"},
            {"start": "08:00", "end": "11:40", "activity": "上课", "desc": "在教室里上课，回复可能会慢一些。"},
            {"start": "12:00", "end": "13:00", "activity": "午饭", "desc": "在食堂排队打饭，周围有点吵。"},
            {"start": "14:00", "end": "17:30", "activity": "自习/作业", "desc": "安排自习和写作业，可能需要专注一会儿。"},
            {"start": "18:00", "end": "19:00", "activity": "晚饭&散步", "desc": "吃晚饭顺便出去走走，边走边聊没问题。"},
            {"start": "23:00", "end": "07:00", "activity": "睡觉", "desc": "已经睡了，可能要到早上才看到消息。"},
        ],
        "weekend": [
            {"start": "09:30", "end": "10:30", "activity": "赖床", "desc": "周末的被窝最香，再睡一小会儿。"},
            {"start": "10:30", "end": "12:00", "activity": "运动/逛街", "desc": "周末出去走走，随时可以回消息。"},
            {"start": "12:00", "end": "13:00", "activity": "午饭", "desc": "在吃午饭，边吃边聊没问题。"},
            {"start": "14:00", "end": "18:00", "activity": "娱乐/打游戏", "desc": "在做自己喜欢的事，心情不错。"},
            {"start": "23:30", "end": "09:00", "activity": "睡觉", "desc": "周末睡得晚起得晚，可能要等醒了再回复。"},
        ],
    },
}


class DailyHabitsPlugin(MCPPlugin):
    """根据作息表返回当前生活状态的 MCP 插件"""

    name = "daily_habits"
    description = "根据自定义日常作息表返回当前生活状态，并为对话提供贴近生活的上下文。"
    auto_context = True

    def __init__(self, schedule_path: Optional[Path] = None):
        self.schedule_path = Path(schedule_path or self.default_config_path())
        self.schedule_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_cache: Dict[str, Any] = {}
        self._last_mtime: Optional[float] = None
        self._timezone = self._resolve_timezone()
        self._ensure_config_file()

    @staticmethod
    def default_config_path() -> Path:
        return Path("data") / "daily_habits.json"

    @classmethod
    def _default_config(cls) -> Dict[str, Any]:
        return json.loads(json.dumps(DEFAULT_CONFIG, ensure_ascii=False))

    def _ensure_config_file(self):
        if not self.schedule_path.exists():
            self.save_config(self._default_config(), self.schedule_path)

    @classmethod
    def save_config(cls, config_data: Dict[str, Any], path: Optional[Path] = None):
        target = Path(path or cls.default_config_path())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(config_data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load_config_from_disk(cls, path: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(path or cls.default_config_path())
        if not target.exists():
            cls.save_config(cls._default_config(), target)
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        # 回退到默认配置，避免因文件损坏导致中断
        fallback = cls._default_config()
        cls.save_config(fallback, target)
        return fallback

    def invalidate_cache(self):
        """在配置热更新时手动触发缓存失效"""
        self._last_mtime = None

    def _resolve_timezone(self):
        tz_preference = None
        try:
            from backend.config import config as global_config

            cfg = global_config.get("clock", {}) or {}
            tz_preference = cfg.get("timezone") or os.getenv("CLOCK_TIMEZONE")
            if not tz_preference:
                tz_preference = global_config.proactive_chat_config.get("timezone")
        except Exception:
            tz_preference = os.getenv("CLOCK_TIMEZONE")

        tz = self._parse_timezone(tz_preference)
        if tz:
            return tz
        try:
            return datetime.now().astimezone().tzinfo or timezone.utc
        except Exception:
            return timezone.utc

    def _parse_timezone(self, tz_name: Optional[str]):
        if not tz_name:
            return None
        tz_name = tz_name.strip()
        if ZoneInfo:
            try:
                return ZoneInfo(tz_name)
            except Exception:
                pass
        if tz_name.upper().startswith("UTC"):
            try:
                sign = 1 if "+" in tz_name else -1
                parts = tz_name.replace("UTC", "").replace("+", "").replace("-", "").split(":")
                hours = int(parts[0]) if parts and parts[0] else 0
                minutes = int(parts[1]) if len(parts) > 1 else 0
                delta = timedelta(hours=hours, minutes=minutes)
                if sign < 0:
                    delta = -delta
                return timezone(delta, name=tz_name)
            except Exception:
                return None
        return None

    def _load_config(self) -> Dict[str, Any]:
        stat = None
        try:
            stat = self.schedule_path.stat()
        except FileNotFoundError:
            self._ensure_config_file()
            stat = self.schedule_path.stat()

        if self._last_mtime and stat and stat.st_mtime == self._last_mtime and self._config_cache:
            return self._config_cache

        config_data = self.load_config_from_disk(self.schedule_path)
        self._config_cache = config_data
        self._last_mtime = stat.st_mtime if stat else None

        # 如果配置中指定了时区，则覆盖默认
        cfg_tz = config_data.get("timezone")
        tz_obj = self._parse_timezone(cfg_tz)
        if tz_obj:
            self._timezone = tz_obj

        return config_data

    def _parse_hhmm(self, hhmm: str) -> time:
        hour, minute = hhmm.split(":")
        return time(hour=int(hour), minute=int(minute))

    def _slot_intervals(self, slot: Dict[str, Any], anchor: datetime) -> List[Tuple[datetime, datetime]]:
        start_time = self._parse_hhmm(slot["start"])
        end_time = self._parse_hhmm(slot["end"])
        start_dt = datetime.combine(anchor.date(), start_time, tzinfo=anchor.tzinfo)
        end_dt = datetime.combine(anchor.date(), end_time, tzinfo=anchor.tzinfo)

        if end_dt > start_dt:
            return [(start_dt, end_dt)]

        # 跨午夜的时间段，提供前后两种覆盖区间
        return [
            (start_dt - timedelta(days=1), end_dt),  # 覆盖凌晨时间
            (start_dt, end_dt + timedelta(days=1)),  # 覆盖深夜时间
        ]

    def _pick_schedule(self, cfg: Dict[str, Any], now: datetime) -> Tuple[str, List[Dict[str, Any]]]:
        # 优先使用 LLM 生成的当日作息
        generated_slots = self._load_generated_slots(now)
        if generated_slots is not None:
            return "generated", generated_slots

        # fallback：静态配置
        schedules = cfg.get("schedules") or {}
        schedule_name = cfg.get("default_schedule") or "default"

        weekend_name = cfg.get("weekend_schedule") or "weekend"
        if now.weekday() >= 5 and weekend_name in schedules:
            schedule_name = weekend_name
        elif schedule_name not in schedules and schedules:
            schedule_name = next(iter(schedules.keys()))

        return schedule_name, schedules.get(schedule_name, [])

    def _load_generated_slots(self, now: datetime) -> Optional[List[Dict[str, Any]]]:
        """读取今天 LLM 生成的作息槽位，若不存在或日期不符则返回 None。"""
        gen_path = default_generated_path()
        if not gen_path.exists():
            return None
        try:
            data = json.loads(gen_path.read_text(encoding="utf-8"))
            stored_date = data.get("date")
            today_str = now.date().isoformat()
            if stored_date != today_str:
                return None
            slots = data.get("slots")
            if isinstance(slots, list) and slots:
                return slots
        except Exception:
            pass
        return None

    def _active_override(self, cfg: Dict[str, Any], now: datetime) -> Optional[Dict[str, Any]]:
        override = cfg.get("override") or {}
        if not override.get("enabled"):
            return None
        expires_at = override.get("expires_at")
        if expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=self._timezone)
                if now >= exp_dt:
                    return None
            except Exception:
                # 解析失败时忽略过期检查
                pass
        return {
            "activity": override.get("activity") or "临时状态",
            "desc": override.get("desc") or "",
            "source": "override",
            "start": None,
            "end": None,
            "schedule": "override",
        }

    def _current_status(self, at: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        cfg = self._load_config()
        if not cfg.get("enabled", True):
            return None

        now = at.astimezone(self._timezone) if at else datetime.now(self._timezone)

        override_status = self._active_override(cfg, now)
        if override_status:
            return override_status

        schedule_name, slots = self._pick_schedule(cfg, now)
        for slot in slots:
            try:
                intervals = self._slot_intervals(slot, now)
            except Exception:
                continue
            for start_dt, end_dt in intervals:
                if start_dt <= now < end_dt:
                    return {
                        "activity": slot.get("activity", ""),
                        "desc": slot.get("desc", ""),
                        "start": start_dt.isoformat(),
                        "end": end_dt.isoformat(),
                        "schedule": schedule_name,
                        "source": "schedule",
                    }
        return None

    def _build_context(self, status: Dict[str, Any], now: datetime) -> str:
        activity = status.get("activity", "").strip()
        desc = status.get("desc", "").strip()
        start = status.get("start")
        end = status.get("end")

        window = ""
        if start and end:
            try:
                start_dt = datetime.fromisoformat(start)
                end_dt = datetime.fromisoformat(end)
                window = f"（{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}）"
            except Exception:
                pass

        if status.get("source") == "override":
            prefix = "当前临时状态"
        elif status.get("schedule") == "generated":
            prefix = "当前生活状态（今日作息）"
        else:
            prefix = "当前生活状态"

        main = f"{prefix}：现在是 {now.strftime('%H:%M')}，正在{activity}{window}。"
        if desc:
            main += desc
        return main + " 回复时请自然融入这个状态，语气与情景保持一致。"

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "current_status",
                "description": "返回当前的生活作息状态，以及可直接注入系统提示的文本。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "at": {
                            "type": "string",
                            "description": "ISO 格式时间（可不带时区），默认使用配置的时区的当前时间。",
                        },
                        "include_context": {
                            "type": "boolean",
                            "description": "是否返回用于 System Prompt 的上下文文本。",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "get_schedule",
                "description": "获取完整的日常作息配置，用于前端或调试。",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        ]

    async def run_tool(self, tool_name: str, params: Optional[Dict[str, Any]] = None) -> Any:
        params = params or {}
        if tool_name == "current_status":
            at_param = params.get("at")
            parsed_at = None
            if at_param:
                try:
                    parsed_at = datetime.fromisoformat(at_param)
                    if parsed_at.tzinfo is None:
                        parsed_at = parsed_at.replace(tzinfo=self._timezone)
                except Exception:
                    parsed_at = None
            status = self._current_status(parsed_at)
            include_context = params.get("include_context", True)
            now = parsed_at or datetime.now(self._timezone)
            context = self._build_context(status, now) if status and include_context else ""
            return {"status": status, "context": context, "timezone": str(self._timezone)}

        if tool_name == "get_schedule":
            return self._load_config()

        raise ValueError(f"daily_habits 不支持的工具: {tool_name}")

    async def auto_context_block(self, user_message: str) -> Optional[str]:
        status = self._current_status()
        if not status:
            return None
        now = datetime.now(self._timezone)
        return self._build_context(status, now)

    def get_status(self) -> Dict[str, Any]:
        """提供给内部 API 使用的同步状态查询"""
        now = datetime.now(self._timezone)
        status = self._current_status(now)
        if not status:
            return {"active": False, "timezone": str(self._timezone)}
        return {
            "active": True,
            "timezone": str(self._timezone),
            "status": status,
            "context": self._build_context(status, now),
            "now": now.isoformat(),
        }
