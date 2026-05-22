"""管理员：多用户配置管理 API

目标：面向 QQ 多用户使用时，由管理员统一查看/下发每个用户的配置覆盖；用户未设置的字段默认继承全局 config.yaml。
"""

from __future__ import annotations

from typing import Any, Dict, Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.admin_auth import require_admin
from backend.user import user_manager
from backend.utils.config_merger import config_merger
from backend.config import config as global_config


router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminUserSummary(BaseModel):
    id: int
    username: str
    nickname: Optional[str] = None
    qq_user_id: Optional[str] = None
    linyu_user_id: Optional[str] = None
    is_active: int
    is_admin: int
    created_at: str


class AdminUserListResponse(BaseModel):
    users: List[AdminUserSummary]


class AdminUpsertQQUserRequest(BaseModel):
    qq_user_id: str = Field(..., description="QQ用户ID")
    nickname: Optional[str] = Field(default=None, description="昵称（可选）")
    avatar: Optional[str] = Field(default=None, description="头像URL（可选）")


class AdminUserConfigResponse(BaseModel):
    user_id: int
    qq_user_id: Optional[str] = None
    linyu_user_id: Optional[str] = None
    overrides: Dict[str, Any] = Field(default_factory=dict)
    merged: Optional[Dict[str, Any]] = None


class AdminUpdateUserConfigRequest(BaseModel):
    system_prompt: Optional[str] = None
    llm: Optional[Dict[str, Any]] = None
    tts: Optional[Dict[str, Any]] = None
    image_generation: Optional[Dict[str, Any]] = None
    video_generation: Optional[Dict[str, Any]] = None
    vision: Optional[Dict[str, Any]] = None
    prompt_enhancer: Optional[Dict[str, Any]] = None
    emotes: Optional[Dict[str, Any]] = None
    adapters: Optional[Dict[str, Any]] = None
    preferences: Optional[Dict[str, Any]] = None


def _build_global_config() -> Dict[str, Any]:
    return {
        "system_prompt": global_config.system_prompt,
        "llm": global_config.llm_config,
        "tts": global_config.tts_config,
        "image_generation": global_config.image_gen_config.dict() if hasattr(global_config.image_gen_config, "dict") else {},
        "video_generation": global_config.video_gen_config.dict() if hasattr(global_config.video_gen_config, "dict") else {},
        "vision": global_config.vision_config.dict() if hasattr(global_config.vision_config, "dict") else {},
        "emotes": global_config.emote_config.dict() if hasattr(global_config.emote_config, "dict") else {},
        "prompt_enhancer": global_config.prompt_enhancer_config.dict() if hasattr(global_config.prompt_enhancer_config, "dict") else {},
        "adapters": global_config.adapters_config,
    }


async def _resolve_user(user_key: str):
    # 优先按 qq_user_id 查
    user = await user_manager.get_user_by_qq_id(user_key)
    if user:
        return user

    # 按 linyu_user_id 查
    user = await user_manager.get_user_by_linyu_id(user_key)
    if user:
        return user

    if user_key.isdigit():
        user_by_id = await user_manager.get_user_by_id(int(user_key))
        if user_by_id:
            return user_by_id

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")


@router.get("/users", response_model=AdminUserListResponse, dependencies=[Depends(require_admin)])
async def list_users(limit: int = 200, skip: int = 0):
    users = await user_manager.list_users(skip=skip, limit=limit)
    payload: List[AdminUserSummary] = []
    for u in users:
        payload.append(
            AdminUserSummary(
                id=u.id,
                username=u.username,
                nickname=u.nickname,
                qq_user_id=u.qq_user_id,
                linyu_user_id=u.linyu_user_id,
                is_active=u.is_active,
                is_admin=u.is_admin,
                created_at=u.created_at.isoformat() if getattr(u, "created_at", None) else "",
            )
        )
    return AdminUserListResponse(users=payload)


@router.post("/users/qq/upsert", response_model=AdminUserSummary, dependencies=[Depends(require_admin)])
async def upsert_qq_user(request: AdminUpsertQQUserRequest):
    user = await user_manager.get_or_create_user_by_qq_id(
        request.qq_user_id, nickname=request.nickname, avatar=request.avatar
    )
    # 如果已存在，可更新昵称/头像（不强制）
    if request.nickname is not None or request.avatar is not None:
        await user_manager.update_user(user.id, nickname=request.nickname, avatar=request.avatar)
        user = await user_manager.get_user_by_id(user.id) or user

    return AdminUserSummary(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        qq_user_id=user.qq_user_id,
        linyu_user_id=user.linyu_user_id,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at.isoformat() if getattr(user, "created_at", None) else "",
    )


@router.get("/users/{user_key}/config", response_model=AdminUserConfigResponse, dependencies=[Depends(require_admin)])
async def get_user_config(user_key: str, merged: bool = True):
    user = await _resolve_user(user_key)
    overrides = await user_manager.get_user_config_dict(user.id)

    merged_cfg: Optional[Dict[str, Any]] = None
    if merged:
        merged_cfg = config_merger.get_user_config(_build_global_config(), overrides, skip_empty=True)

    return AdminUserConfigResponse(
        user_id=user.id,
        qq_user_id=user.qq_user_id,
        linyu_user_id=user.linyu_user_id,
        overrides=overrides,
        merged=merged_cfg,
    )


@router.put("/users/{user_key}/config", response_model=AdminUserConfigResponse, dependencies=[Depends(require_admin)])
async def update_user_config(user_key: str, request: AdminUpdateUserConfigRequest):
    user = await _resolve_user(user_key)

    # 构建存储字段
    config_data: Dict[str, Any] = {}
    if request.system_prompt is not None:
        config_data["system_prompt"] = request.system_prompt
    if request.llm is not None:
        config_data["llm_config"] = request.llm
    if request.tts is not None:
        config_data["tts_config"] = request.tts
    if request.image_generation is not None:
        config_data["image_gen_config"] = request.image_generation
    if request.video_generation is not None:
        config_data["video_gen_config"] = request.video_generation
    if request.vision is not None:
        config_data["vision_config"] = request.vision
    if request.prompt_enhancer is not None:
        config_data["prompt_enhancer_config"] = request.prompt_enhancer
    if request.emotes is not None:
        config_data["emote_config"] = request.emotes
    if request.adapters is not None:
        config_data["adapters"] = request.adapters
    if request.preferences is not None:
        config_data["preferences"] = request.preferences

    success = await user_manager.update_user_config(user.id, config_data)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="配置更新失败")

    overrides = await user_manager.get_user_config_dict(user.id)
    merged_cfg = config_merger.get_user_config(_build_global_config(), overrides, skip_empty=True)

    return AdminUserConfigResponse(
        user_id=user.id,
        qq_user_id=user.qq_user_id,
        linyu_user_id=user.linyu_user_id,
        overrides=overrides,
        merged=merged_cfg,
    )


@router.delete("/users/{user_key}", dependencies=[Depends(require_admin)])
async def delete_user(user_key: str):
    """删除用户"""
    user = await _resolve_user(user_key)
    
    # 同时删除用户数据文件（按 username 命名的目录）
    from backend.user import user_data_manager
    user_data_manager.delete_user_data(user.username)
    
    success = await user_manager.delete_user(user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="删除用户失败")
    
    return {"message": f"用户 {user.username} 已删除", "user_id": user.id}


class AdminSetUserAdminRequest(BaseModel):
    is_admin: int = Field(..., description="是否为管理员：1=是，0=否")


@router.post("/users/{user_key}/admin", dependencies=[Depends(require_admin)])
async def set_user_admin(user_key: str, request: AdminSetUserAdminRequest):
    """设置用户的管理员状态"""
    user = await _resolve_user(user_key)
    
    # 更新用户的管理员状态
    from sqlalchemy import update
    from backend.user.models import User
    
    async with user_manager.get_session() as session:
        stmt = update(User).where(User.id == user.id).values(is_admin=request.is_admin)
        await session.execute(stmt)
        await session.commit()
    
    return {
        "message": f"用户 {user.username} 的管理员状态已更新",
        "user_id": user.id,
        "is_admin": request.is_admin
    }


class AdminSetUserActiveRequest(BaseModel):
    is_active: int = Field(..., description="是否启用：1=启用，0=禁用")


@router.post("/users/{user_key}/active", dependencies=[Depends(require_admin)])
async def set_user_active(user_key: str, request: AdminSetUserActiveRequest):
    """设置用户的启用状态"""
    user = await _resolve_user(user_key)
    
    success = await user_manager.update_user(user.id, is_active=request.is_active)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="更新用户状态失败")
    
    return {
        "message": f"用户 {user.username} 的状态已更新",
        "user_id": user.id,
        "is_active": request.is_active
    }


@router.get("/users/{user_key}/storage", dependencies=[Depends(require_admin)])
async def get_user_storage_stats(user_key: str):
    """获取用户存储统计信息"""
    user = await _resolve_user(user_key)
    
    from backend.user import user_data_manager
    stats = user_data_manager.get_user_storage_stats(user.username)
    
    return {
        "user_id": user.id,
        "username": user.username,
        "storage": stats
    }
