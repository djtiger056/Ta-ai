"""
每日作息生成器

在每天凌晨固定时间段（默认 00:00-06:00）调用 LLM，
根据提示词模板生成一整天的详细作息表，写入 data/generated_schedule.json。
DailyHabitsPlugin 优先读取该文件，实现"AI 有真实生活状态"的效果。
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
#  默认提示词模板
# --------------------------------------------------------------------------- #

DEFAULT_GENERATION_PROMPT = """\
今天是 {weekday_cn}（{date_str}），请你以"{persona_name}"的身份，
为今天生成一份真实、自然、有随机性的详细作息时间表。

要求：
1. 时间段覆盖全天 00:00-24:00，不留空白，相邻时间段首尾相接。
2. 每个时间段包含：开始时间、结束时间、活动名称（简短，4-10字）、活动描述（15-40字，第一人称，口语化，体现当下状态和心情）。
3. 作息要有真实感和随机性：
   - 睡眠时间可在 22:30-01:30 之间随机入睡，07:00-09:30 之间随机起床（周末可更晚）。
   - 三餐时间可在合理范围内浮动 ±30 分钟。
   - 加入 1-3 个"意外小插曲"（如突然刷到有趣视频、和室友聊天、出去买零食等）。
   - 今天是{weekday_cn}，{weekday_hint}。
4. 描述要符合"{persona_name}"的人设：{persona_desc}
5. 严格按照以下 JSON 格式输出，不要有任何额外文字：

```json
[
  {{"start": "HH:MM", "end": "HH:MM", "activity": "活动名称", "desc": "活动描述"}},
  ...
]
```
"""

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
WEEKDAY_HINTS = {
    0: "工作日，有课，需要早起",
    1: "工作日，有课，需要早起",
    2: "工作日，有课，需要早起",
    3: "工作日，有课，需要早起",
    4: "工作日，明天就周末了，心情轻松一些",
    5: "周末，可以睡懒觉，不用上课",
    6: "周末，明天要上课了，可能有点小焦虑",
}


# --------------------------------------------------------------------------- #
#  生成结果存储路径
# --------------------------------------------------------------------------- #

def default_generated_path() -> Path:
    return Path("data") / "generated_schedule.json"


# --------------------------------------------------------------------------- #
#  核心生成器
# --------------------------------------------------------------------------- #

class DailyScheduleGenerator:
    """
    调用 LLM 生成当天作息表，并持久化到 data/generated_schedule.json。

    外部调用方式：
        generator = DailyScheduleGenerator(bot)
        await generator.generate_for_today()
    """

    def __init__(
        self,
        bot,
        output_path: Optional[Path] = None,
        timezone_name: str = "Asia/Shanghai",
    ):
        self.bot = bot
        self.output_path = Path(output_path or default_generated_path())
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._tz = self._resolve_tz(timezone_name)

    # ------------------------------------------------------------------ #
    #  公开接口
    # ------------------------------------------------------------------ #

    async def generate_for_today(self, force: bool = False) -> bool:
        """
        生成今天的作息表。

        Args:
            force: True 时忽略"今天已生成"检查，强制重新生成。

        Returns:
            True 表示成功生成并写入，False 表示跳过或失败。
        """
        today = self._today()

        if not force and self._already_generated(today):
            logger.info("[ScheduleGen] 今天（%s）已生成过作息表，跳过。", today)
            return False

        cfg = self._load_gen_config()
        if not cfg.get("enabled", True):
            logger.info("[ScheduleGen] 作息生成功能已禁用，跳过。")
            return False

        prompt = self._build_prompt(today, cfg)
        logger.info("[ScheduleGen] 开始为 %s 生成作息表…", today)

        try:
            raw = await self._call_llm(prompt, cfg)
        except Exception as exc:
            logger.error("[ScheduleGen] LLM 调用失败: %s", exc)
            return False

        slots = self._parse_slots(raw)
        if not slots:
            logger.error("[ScheduleGen] LLM 返回内容解析失败，原始内容:\n%s", raw[:500])
            return False

        self._write(today, slots)
        logger.info("[ScheduleGen] 作息表已生成，共 %d 个时间段。", len(slots))
        return True

    def get_today_slots(self) -> Optional[List[Dict[str, Any]]]:
        """读取今天已生成的作息槽位，若不存在返回 None。"""
        today = self._today()
        if not self._already_generated(today):
            return None
        try:
            data = json.loads(self.output_path.read_text(encoding="utf-8"))
            return data.get("slots") or []
        except Exception:
            return None

    def is_generated_today(self) -> bool:
        return self._already_generated(self._today())

    # ------------------------------------------------------------------ #
    #  内部方法
    # ------------------------------------------------------------------ #

    def _today(self) -> date:
        return datetime.now(self._tz).date()

    def _already_generated(self, today: date) -> bool:
        if not self.output_path.exists():
            return False
        try:
            data = json.loads(self.output_path.read_text(encoding="utf-8"))
            stored = data.get("date")
            return stored == str(today)
        except Exception:
            return False

    def _load_gen_config(self) -> Dict[str, Any]:
        """从全局 config 读取 daily_schedule_generation 节。"""
        try:
            from backend.config import config as global_config
            return global_config.get("daily_schedule_generation", {}) or {}
        except Exception:
            return {}

    def _build_prompt(self, today: date, cfg: Dict[str, Any]) -> str:
        weekday_idx = today.weekday()  # 0=Monday
        weekday_cn = WEEKDAY_CN[weekday_idx]
        weekday_hint = WEEKDAY_HINTS.get(weekday_idx, "")
        date_str = today.strftime("%Y年%m月%d日")

        # 从 system_prompt 里提取人设名称和描述（简单截取前 200 字）
        persona_name = cfg.get("persona_name", "小馨")
        persona_desc = cfg.get("persona_desc", "温柔黏人的大三女生，异地恋，校园生活")

        template = cfg.get("prompt_template") or DEFAULT_GENERATION_PROMPT
        return template.format(
            weekday_cn=weekday_cn,
            date_str=date_str,
            weekday_hint=weekday_hint,
            persona_name=persona_name,
            persona_desc=persona_desc,
        )

    async def _call_llm(self, prompt: str, cfg: Dict[str, Any]) -> str:
        """调用 LLM 生成作息表文本。"""
        # 优先使用专用 LLM 配置（可在 daily_schedule_generation.llm 中覆盖）
        llm_override = cfg.get("llm") or {}

        if llm_override:
            # 使用独立 provider
            from backend.providers import get_provider
            provider = get_provider(
                llm_override.get("provider", "openai"),
                llm_config=llm_override,
            )
        else:
            # 复用 bot 的默认 provider
            provider = getattr(self.bot, "provider", None)
            if provider is None:
                raise RuntimeError("Bot provider 未初始化")

        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个作息表生成助手，只输出 JSON 数组，不输出任何解释文字。"
                    "严格遵守格式要求，确保时间段覆盖全天且首尾相接。"
                ),
            },
            {"role": "user", "content": prompt},
        ]

        if hasattr(provider, "chat"):
            return await provider.chat(messages)
        raise RuntimeError(f"Provider {provider} 不支持 chat 方法")

    def _parse_slots(self, raw: str) -> List[Dict[str, Any]]:
        """从 LLM 输出中提取 JSON 数组。"""
        # 尝试提取 ```json ... ``` 代码块
        code_block = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.DOTALL)
        if code_block:
            json_str = code_block.group(1)
        else:
            # 直接找第一个 [ ... ] 数组
            arr_match = re.search(r"(\[.*\])", raw, re.DOTALL)
            if arr_match:
                json_str = arr_match.group(1)
            else:
                return []

        try:
            slots = json.loads(json_str)
        except json.JSONDecodeError:
            # 尝试修复常见问题：末尾多余逗号
            cleaned = re.sub(r",\s*([}\]])", r"\1", json_str)
            try:
                slots = json.loads(cleaned)
            except Exception:
                return []

        if not isinstance(slots, list):
            return []

        # 校验并规范化每个槽位
        valid = []
        for item in slots:
            if not isinstance(item, dict):
                continue
            start = str(item.get("start", "")).strip()
            end = str(item.get("end", "")).strip()
            activity = str(item.get("activity", "")).strip()
            if not start or not end or not activity:
                continue
            valid.append({
                "start": start,
                "end": end,
                "activity": activity,
                "desc": str(item.get("desc", "")).strip(),
            })

        return valid

    def _write(self, today: date, slots: List[Dict[str, Any]]):
        """将生成结果写入 JSON 文件。"""
        data = {
            "date": str(today),
            "generated_at": datetime.now(self._tz).isoformat(),
            "slots": slots,
        }
        self.output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _resolve_tz(tz_name: str):
        if ZoneInfo:
            try:
                return ZoneInfo(tz_name)
            except Exception:
                pass
        # fallback UTC+8
        return timezone(timedelta(hours=8))
