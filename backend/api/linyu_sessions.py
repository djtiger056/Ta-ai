from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from backend.api.admin_auth import require_admin
from backend.adapters.linyu_manager import get_linyu_session_manager


router = APIRouter(prefix="/api/admin/linyu-sessions", tags=["admin-linyu-sessions"])


@router.get("")
async def get_linyu_sessions() -> Dict[str, Any]:
    manager = get_linyu_session_manager()
    if not manager:
        return {"running": False, "sessions": {}}
    return {
        "running": manager.running,
        "sessions": manager.get_status_snapshot(),
    }


@router.post("/refresh", dependencies=[Depends(require_admin)])
async def refresh_all_linyu_sessions() -> Dict[str, Any]:
    manager = get_linyu_session_manager()
    if not manager:
        return {"success": False, "message": "LinyuSessionManager 未启动"}
    ok = manager.request_refresh_all()
    return {"success": ok, "message": "已提交 Linyu 会话全量热重载请求" if ok else "LinyuSessionManager 不可用"}


@router.post("/{owner_user_id}/refresh", dependencies=[Depends(require_admin)])
async def refresh_single_linyu_session(owner_user_id: str) -> Dict[str, Any]:
    manager = get_linyu_session_manager()
    if not manager:
        return {"success": False, "message": "LinyuSessionManager 未启动"}
    ok = manager.request_refresh_user(owner_user_id)
    return {"success": ok, "message": f"已提交用户 {owner_user_id} 的 Linyu 会话热重载请求" if ok else "LinyuSessionManager 不可用"}

