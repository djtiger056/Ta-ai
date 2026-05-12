from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ..core.cerebellum import CerebellumEngine, ExternalStimulus

router = APIRouter(tags=["cerebellum"])

engine_instance: Optional[CerebellumEngine] = None


class StimulusRequest(BaseModel):
    stimulus_type: str = Field(default="manual")
    intensity: float = Field(default=0.2, ge=0.0, le=1.0)
    valence: str = Field(default="neutral")
    source: str = Field(default="api")
    channel: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    message: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CerebellumConfigRequest(BaseModel):
    enabled: Optional[bool] = None
    tick_interval: Optional[int] = None
    decay_rate: Optional[float] = None
    action_threshold: Optional[float] = None
    persistence_interval: Optional[int] = None
    state_file: Optional[str] = None
    max_stimulus_step: Optional[float] = None
    history_limit: Optional[int] = None
    replace_time_windows: Optional[bool] = None
    motivation_cooldown_seconds: Optional[int] = None
    baseline_values: Optional[Dict[str, float]] = None
    circadian: Optional[Dict[str, Any]] = None
    inactivity_stimulus: Optional[Dict[str, Any]] = None


def set_engine(engine: CerebellumEngine) -> None:
    global engine_instance
    engine_instance = engine


def get_engine() -> CerebellumEngine:
    global engine_instance
    if engine_instance is None:
        engine_instance = CerebellumEngine()
    return engine_instance


def record_user_message_stimulus(
    channel: str,
    user_id: str,
    session_id: Optional[str],
    message: Optional[str],
) -> None:
    engine = engine_instance
    if not engine:
        return
    try:
        coro = engine.submit_message_stimulus(message, channel, user_id, session_id)
        if engine.loop and engine.loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, engine.loop)
        else:
            asyncio.create_task(coro)
    except RuntimeError:
        # 没有运行中的事件循环时静默跳过，避免影响聊天主流程。
        return
    except Exception as exc:
        print(f"[Cerebellum] 记录用户刺激失败: {exc}")


@router.get("/api/cerebellum/state")
async def get_state():
    return get_engine().snapshot()


@router.get("/api/cerebellum/motivation")
async def get_motivation():
    return {"motivations": get_engine().motivations_snapshot()}


@router.get("/api/cerebellum/history")
async def get_history(
    hours: float = Query(default=24.0, ge=0.1, le=720.0),
    limit: int = Query(default=500, ge=1, le=5000),
):
    return {"history": get_engine().history_snapshot(hours=hours, limit=limit)}


@router.get("/api/cerebellum/config")
async def get_config():
    return {"config": get_engine().config.to_dict()}


@router.post("/api/cerebellum/config")
async def update_config(req: CerebellumConfigRequest):
    try:
        payload = {key: value for key, value in req.dict(exclude_none=True).items()}
        cfg = get_engine().reload_config(payload)
        return {"message": "配置已更新", "config": cfg.to_dict()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"更新小脑配置失败: {exc}")


@router.post("/api/cerebellum/stimulus")
async def submit_stimulus(req: StimulusRequest):
    try:
        await get_engine().submit_stimulus(ExternalStimulus(**req.dict()))
        return {"message": "刺激已提交"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"提交刺激失败: {exc}")


@router.websocket("/ws/cerebellum/stream")
async def cerebellum_stream(websocket: WebSocket):
    await websocket.accept()
    engine = get_engine()
    queue = await engine.subscribe()
    try:
        while True:
            payload = await queue.get()
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        pass
    finally:
        engine.unsubscribe(queue)
