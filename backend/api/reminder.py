"""
待办事项 API 接口
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..config import config
from .bot_provider import get_bot

router = APIRouter(prefix="/api", tags=["reminder"])

# 共享调度器实例（由 main.py 设置）
scheduler_instance = None


def _reminder_feature_enabled() -> bool:
    reminder_config = config.get("reminder", {}) or {}
    return bool(reminder_config.get("enabled", False))


class ReminderListRequest(BaseModel):
    """待办事项列表请求"""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    status: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=500)


class ReminderCreateRequest(BaseModel):
    """创建待办事项请求"""
    user_id: str
    session_id: str
    content: str
    trigger_time: str  # ISO格式的时间字符串
    original_message: Optional[str] = None
    time_expression: Optional[str] = None
    reminder_message: Optional[str] = None
    metadata: Dict[str, Any] = {}


class ReminderUpdateRequest(BaseModel):
    """更新待办事项请求"""
    status: Optional[str] = None
    reminder_message: Optional[str] = None


class ReminderActionRequest(BaseModel):
    """待办事项操作请求"""
    action: str  # complete, cancel


async def _get_memory_manager():
    """获取记忆管理器实例"""
    if not _reminder_feature_enabled():
        raise HTTPException(status_code=503, detail="待办事项功能已暂时停用")

    bot = get_bot()
    if not bot or not bot.memory_manager:
        raise HTTPException(status_code=503, detail="记忆管理器未初始化")
    
    # 确保memory_manager已初始化
    if hasattr(bot.memory_manager, 'engine') and bot.memory_manager.engine is None:
        try:
            print("[Reminder API] 正在初始化MemoryManager...")
            await bot.memory_manager.initialize()
            print("[Reminder API] MemoryManager初始化成功")
        except Exception as e:
            print(f"[Reminder API] MemoryManager初始化失败: {e}")
            raise HTTPException(status_code=503, detail="记忆管理器初始化失败")
    
    return bot.memory_manager


@router.get("/reminder/list")
async def get_reminder_list(
    user_id: Optional[str] = Query(default=None, description="用户ID"),
    session_id: Optional[str] = Query(default=None, description="会话ID"),
    status: Optional[str] = Query(default=None, description="状态过滤"),
    limit: int = Query(default=100, ge=1, le=500, description="返回数量限制")
):
    """获取待办事项列表"""
    if not _reminder_feature_enabled():
        raise HTTPException(status_code=503, detail="待办事项功能已暂时停用")

    try:
        memory_manager = await _get_memory_manager()

        reminders = await memory_manager.get_all_reminders(
            user_id=user_id,
            session_id=session_id,
            status=status,
            limit=limit
        )

        return {
            "success": True,
            "data": reminders,
            "count": len(reminders)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取待办事项列表失败: {e}")


@router.post("/reminder/create")
async def create_reminder(req: ReminderCreateRequest):
    """创建待办事项"""
    if not _reminder_feature_enabled():
        raise HTTPException(status_code=503, detail="待办事项功能已暂时停用")

    try:
        memory_manager = await _get_memory_manager()

        # 解析触发时间
        try:
            trigger_time = datetime.fromisoformat(req.trigger_time)
        except ValueError:
            raise HTTPException(status_code=400, detail="触发时间格式错误，请使用ISO格式")

        success = await memory_manager.add_reminder(
            user_id=req.user_id,
            session_id=req.session_id,
            content=req.content,
            trigger_time=trigger_time,
            original_message=req.original_message,
            time_expression=req.time_expression,
            reminder_message=req.reminder_message,
            metadata=req.metadata
        )

        if success:
            return {
                "success": True,
                "message": "待办事项创建成功"
            }
        else:
            raise HTTPException(status_code=500, detail="待办事项创建失败")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建待办事项失败: {e}")


@router.post("/reminder/{reminder_id}/action")
async def reminder_action(reminder_id: int, req: ReminderActionRequest):
    """对待办事项执行操作（完成/取消）"""
    if not _reminder_feature_enabled():
        raise HTTPException(status_code=503, detail="待办事项功能已暂时停用")

    try:
        memory_manager = await _get_memory_manager()

        if req.action == "complete":
            success = await memory_manager.complete_reminder(reminder_id)
            if success:
                return {
                    "success": True,
                    "message": "待办事项已完成"
                }
            else:
                raise HTTPException(status_code=404, detail="待办事项不存在")

        elif req.action == "cancel":
            success = await memory_manager.cancel_reminder(reminder_id)
            if success:
                return {
                    "success": True,
                    "message": "待办事项已取消"
                }
            else:
                raise HTTPException(status_code=404, detail="待办事项不存在")

        else:
            raise HTTPException(status_code=400, detail=f"不支持的操作: {req.action}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行操作失败: {e}")


@router.get("/reminder/pending")
async def get_pending_reminders():
    """获取待处理的待办事项（触发时间已到且状态为pending）"""
    if not _reminder_feature_enabled():
        raise HTTPException(status_code=503, detail="待办事项功能已暂时停用")

    try:
        memory_manager = await _get_memory_manager()

        reminders = await memory_manager.get_pending_reminders()

        return {
            "success": True,
            "data": reminders,
            "count": len(reminders)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取待处理待办事项失败: {e}")


@router.get("/reminder/config")
async def get_reminder_config():
    """获取待办事项配置"""
    try:
        reminder_config = config.get("reminder", {})
        return {
            "success": True,
            "config": reminder_config
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取配置失败: {e}")


@router.post("/reminder/config")
async def update_reminder_config(cfg: Dict[str, Any]):
    """更新待办事项配置"""
    try:
        if not _reminder_feature_enabled() and cfg.get("enabled", False):
            raise HTTPException(status_code=403, detail="待办事项功能已暂时停用，无法启用")
        config.update_config("reminder", cfg)
        return {
            "success": True,
            "message": "配置已更新",
            "config": config.get("reminder", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新配置失败: {e}")


@router.post("/reminder/check")
async def check_reminders():
    """手动检查待办事项（触发一次检查）"""
    if not _reminder_feature_enabled():
        raise HTTPException(status_code=503, detail="待办事项功能已暂时停用")

    try:
        if scheduler_instance is None:
            raise HTTPException(status_code=503, detail="待办事项调度器未启动")

        await scheduler_instance.check_once()

        return {
            "success": True,
            "message": "待办事项检查已完成"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检查待办事项失败: {e}")


@router.get("/reminder/status")
async def get_reminder_status():
    """获取待办事项调度器状态"""
    try:
        return {
            "success": True,
            "running": False if not _reminder_feature_enabled() else (scheduler_instance is not None and scheduler_instance.is_running),
            "enabled": _reminder_feature_enabled(),
            "check_interval": scheduler_instance.check_interval_seconds if scheduler_instance else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取状态失败: {e}")
