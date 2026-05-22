from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..config import config
from ..core.proactive import ProactiveChatScheduler
from . import cerebellum as cerebellum_api

router = APIRouter(prefix="/api", tags=["proactive"])

# 调度器实例（由 main.py 设置），便于跨模块共享
scheduler_instance: Optional[ProactiveChatScheduler] = None


class ProactiveConfigRequest(BaseModel):
    enabled: Optional[bool] = None
    timezone: Optional[str] = None
    check_interval_seconds: Optional[int] = None
    default_prompt: Optional[str] = None
    targets: Optional[list] = None
    daily_window: Optional[Dict[str, Any]] = None
    idle_window: Optional[Dict[str, Any]] = None
    message_templates: Optional[list] = None
    image_generation: Optional[Dict[str, Any]] = None
    behavior_rules: Optional[Dict[str, Any]] = None


class ProactiveTriggerRequest(BaseModel):
    channel: str
    user_id: str
    session_id: Optional[str] = None
    display_name: Optional[str] = None
    instruction: Optional[str] = None


def record_user_activity(channel: str, user_id: str, session_id: Optional[str], message: Optional[str]):
    scheduler = scheduler_instance
    if not scheduler:
        cerebellum_api.record_user_message_stimulus(channel, user_id, session_id, message)
        return
    try:
        scheduler.record_user_activity(channel, user_id, session_id, message)
        cerebellum_api.record_user_message_stimulus(channel, user_id, session_id, message)
    except Exception as e:
        print(f"[Proactive] 记录用户活跃失败: {e}")


def record_assistant_activity(
    channel: str,
    user_id: str,
    session_id: Optional[str],
    message: Optional[str],
    allow_follow_up: bool = True,
):
    scheduler = scheduler_instance
    if not scheduler:
        return
    try:
        scheduler.record_assistant_activity(channel, user_id, session_id, message, allow_follow_up=allow_follow_up)
    except Exception as e:
        print(f"[Proactive] 记录助手活跃失败: {e}")


def _require_scheduler() -> ProactiveChatScheduler:
    """
    仅在调度器已由 main.py 初始化时返回，否则直接报错，避免缺少发送器导致“未找到发送器”。
    """
    if scheduler_instance:
        return scheduler_instance
    raise HTTPException(status_code=503, detail="主动聊天调度器未运行，请启用配置并重启后端适配器。")


def _get_cerebellum_proactive_config() -> Dict[str, Any]:
    cerebellum_cfg = config.get("cerebellum", {}) or {}
    if isinstance(cerebellum_cfg, dict):
        proactive_cfg = cerebellum_cfg.get("proactive_chat")
        if isinstance(proactive_cfg, dict):
            return proactive_cfg
    return config.proactive_chat_config or {}


def _update_cerebellum_proactive_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    cerebellum_cfg = config.get("cerebellum", {}) or {}
    if not isinstance(cerebellum_cfg, dict):
        cerebellum_cfg = {}
    from ..utils.config_merger import config_merger

    proactive_cfg = config_merger.deep_merge(_get_cerebellum_proactive_config(), payload)
    cerebellum_cfg["proactive_chat"] = proactive_cfg
    config.update_config("cerebellum", cerebellum_cfg)
    return proactive_cfg


@router.get("/proactive/config")
async def get_proactive_config():
    try:
        return {"config": _get_cerebellum_proactive_config()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取配置失败: {e}")


@router.post("/proactive/config")
async def update_proactive_config(cfg: ProactiveConfigRequest):
    try:
        payload = {k: v for k, v in cfg.dict(exclude_none=True).items()}
        _update_cerebellum_proactive_config(payload)

        scheduler = scheduler_instance
        if scheduler:
            try:
                future = scheduler.run_coro_threadsafe(scheduler.reload_config())
                future.result(timeout=3)
            except Exception as e:
                print(f"[Proactive] 调度器热更新失败: {e}")
        return {"message": "配置已更新", "config": _get_cerebellum_proactive_config()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新配置失败: {e}")


@router.get("/proactive/status")
async def proactive_status():
    scheduler = scheduler_instance
    if not scheduler:
        proactive_cfg = _get_cerebellum_proactive_config()
        return {
            "running": False,
            "enabled": bool(proactive_cfg.get("enabled", False)),
            "config_loaded": True,
            "message": "调度器未初始化，通常说明后端仍在运行旧版本代码或需要重启适配器线程。",
        }
    try:
        return scheduler.status_snapshot()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取状态失败: {e}")


@router.post("/proactive/trigger")
async def trigger_proactive(req: ProactiveTriggerRequest):
    scheduler = _require_scheduler()
    if req.channel not in scheduler.senders:
        raise HTTPException(status_code=400, detail=f"未找到发送器 {req.channel}，请确认对应适配器已启动。")
    target = {
        "channel": req.channel,
        "user_id": req.user_id,
        "session_id": req.session_id or req.user_id,
        "display_name": req.display_name or "",
    }
    try:
        if scheduler.loop and scheduler.loop.is_running():
            future = scheduler.run_coro_threadsafe(scheduler.trigger_once(target, req.instruction))
            reply = future.result(timeout=15)
        else:
            reply = await scheduler.trigger_once(target, req.instruction)
        return {"message": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"触发主动聊天失败: {e}")


@router.get("/proactive/messages")
async def poll_proactive_messages(
    channel: str = Query(default="web"),
    user_id: str = Query(...),
    session_id: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    scheduler = scheduler_instance
    if not scheduler:
        return {"messages": []}
    try:
        messages = scheduler.poll_pending_messages(channel, user_id, session_id, limit=limit)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取主动消息失败: {e}")
