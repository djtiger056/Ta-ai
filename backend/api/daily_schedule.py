"""
每日作息生成 API

提供手动触发生成、查看当前状态、查看今日作息表等接口。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .bot_provider import get_bot
from ..mcp.schedule_generator import DailyScheduleGenerator, default_generated_path
from ..config import config

router = APIRouter(prefix="/api/daily-schedule", tags=["daily_schedule"])


# --------------------------------------------------------------------------- #
#  请求/响应模型
# --------------------------------------------------------------------------- #

class GenerateRequest(BaseModel):
    force: bool = False  # True 时强制重新生成（即使今天已生成）


# --------------------------------------------------------------------------- #
#  工具函数
# --------------------------------------------------------------------------- #

def _get_generator() -> DailyScheduleGenerator:
    bot = get_bot()
    gen_cfg = config.get("daily_schedule_generation", {}) or {}
    tz = gen_cfg.get("timezone") or config.get("proactive_chat", {}).get("timezone", "Asia/Shanghai")
    return DailyScheduleGenerator(bot=bot, timezone_name=tz)


def _read_generated_file() -> Optional[Dict[str, Any]]:
    path = default_generated_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# --------------------------------------------------------------------------- #
#  路由
# --------------------------------------------------------------------------- #

@router.get("/status")
async def get_status():
    """
    获取今日作息生成状态。

    返回：
    - generated: 今天是否已生成
    - date: 已生成的日期
    - generated_at: 生成时间
    - slot_count: 时间段数量
    - config_enabled: 配置中是否启用了自动生成
    """
    gen_cfg = config.get("daily_schedule_generation", {}) or {}
    data = _read_generated_file()
    generator = _get_generator()

    if data and generator.is_generated_today():
        return {
            "generated": True,
            "date": data.get("date"),
            "generated_at": data.get("generated_at"),
            "slot_count": len(data.get("slots", [])),
            "config_enabled": gen_cfg.get("enabled", True),
        }
    return {
        "generated": False,
        "date": data.get("date") if data else None,
        "generated_at": data.get("generated_at") if data else None,
        "slot_count": 0,
        "config_enabled": gen_cfg.get("enabled", True),
    }


@router.get("/today")
async def get_today_schedule():
    """
    获取今日完整作息表（LLM 生成的）。

    若今天尚未生成，返回 404。
    """
    data = _read_generated_file()
    if not data:
        raise HTTPException(status_code=404, detail="今日作息表尚未生成")

    generator = _get_generator()
    if not generator.is_generated_today():
        raise HTTPException(status_code=404, detail="今日作息表尚未生成（文件为昨天或更早）")

    return data


@router.post("/generate")
async def trigger_generate(req: GenerateRequest):
    """
    手动触发生成今日作息表。

    - force=false（默认）：若今天已生成则跳过
    - force=true：强制重新生成
    """
    try:
        generator = _get_generator()

        # 先检查是否已生成，给出更明确的提示
        if not req.force and generator.is_generated_today():
            data = _read_generated_file()
            return {
                "success": False,
                "message": "今日作息表已存在，如需重新生成请传 force=true",
                "slot_count": len(data.get("slots", [])) if data else 0,
                "generated_at": data.get("generated_at") if data else None,
            }

        success = await generator.generate_for_today(force=req.force)
        if success:
            data = _read_generated_file()
            return {
                "success": True,
                "message": "作息表生成成功",
                "slot_count": len(data.get("slots", [])) if data else 0,
                "generated_at": data.get("generated_at") if data else None,
            }
        else:
            # generate_for_today 返回 False 但不是因为已存在，说明是 enabled=False 或 LLM 失败
            gen_cfg = config.get("daily_schedule_generation", {}) or {}
            if not gen_cfg.get("enabled", True):
                return {
                    "success": False,
                    "message": "作息生成功能已禁用，请在配置中启用 daily_schedule_generation.enabled",
                    "slot_count": 0,
                    "generated_at": None,
                }
            return {
                "success": False,
                "message": "作息表生成失败（LLM 调用失败或返回格式异常），请检查后端日志",
                "slot_count": 0,
                "generated_at": None,
            }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成失败: {exc}")
