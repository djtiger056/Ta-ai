"""提示词系统 API 接口

提供独立的提示词管理接口，支持：
- 获取当前生效的提示词
- 更新提示词（支持来源标记）
- 查看变更历史
- 重置为全局默认
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, List

from backend.user import user_manager, auth_manager
from backend.api.deps import get_access_token
from backend.prompt_system import prompt_manager
from backend.prompt_system.models import PromptChangeRecord
from backend.config import config


router = APIRouter(prefix="/api/prompt", tags=["prompt_system"])


# ---- 请求/响应模型 ----

class GetPromptResponse(BaseModel):
    """获取提示词响应"""
    content: str = Field(description="当前生效的提示词内容")
    is_custom: bool = Field(description="是否为用户自定义提示词（非全局默认）")
    updated_at: Optional[str] = Field(default=None, description="最后更新时间")
    source: str = Field(default="system", description="最后修改来源")


class UpdatePromptRequest(BaseModel):
    """更新提示词请求"""
    content: str = Field(description="新的提示词内容")
    source: str = Field(default="user", description="变更来源: user / ai / system")
    summary: str = Field(default="", description="变更摘要（可选）")


class UpdatePromptResponse(BaseModel):
    """更新提示词响应"""
    success: bool
    content: str = Field(description="更新后的提示词内容")
    message: str = Field(default="")


class PromptHistoryResponse(BaseModel):
    """提示词变更历史响应"""
    records: List[PromptChangeRecord]


# ---- 辅助函数 ----

async def _get_username_from_token(token: str) -> str:
    """从 token 中获取用户名"""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少令牌")

    user_info = auth_manager.get_user_from_token(token)
    if not user_info:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的令牌")

    user = await user_manager.get_user_by_id(user_info["user_id"])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    return user.username


# ---- API 接口 ----

@router.get("", response_model=GetPromptResponse)
async def get_prompt(token: str = Depends(get_access_token)):
    """获取当前用户生效的提示词"""
    username = await _get_username_from_token(token)

    # 尝试自动迁移（首次访问时）
    prompt_manager.migrate_from_config(username)

    prompt_data = prompt_manager.get_prompt_data(username)
    is_custom = prompt_data.content != "" and prompt_data.source != "system"

    # 如果用户没有独立提示词，返回全局默认
    effective_content = prompt_manager.get_effective_prompt(username)

    return GetPromptResponse(
        content=effective_content,
        is_custom=prompt_data.content != "",
        updated_at=prompt_data.updated_at,
        source=prompt_data.source,
    )


@router.put("", response_model=UpdatePromptResponse)
async def update_prompt(
    request: UpdatePromptRequest,
    token: str = Depends(get_access_token),
):
    """更新当前用户的提示词"""
    username = await _get_username_from_token(token)

    if not request.content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="提示词内容不能为空",
        )

    success = prompt_manager.set_prompt(
        username=username,
        content=request.content.strip(),
        source=request.source,
        summary=request.summary,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="提示词更新失败",
        )

    return UpdatePromptResponse(
        success=True,
        content=request.content.strip(),
        message="提示词已更新",
    )


@router.delete("")
async def reset_prompt(token: str = Depends(get_access_token)):
    """重置提示词为全局默认（删除用户独立提示词）"""
    username = await _get_username_from_token(token)

    success = prompt_manager.delete_prompt(username, source="user")

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="提示词重置失败",
        )

    return {
        "success": True,
        "message": "已重置为全局默认提示词",
        "default_prompt_preview": (config.system_prompt or "")[:200],
    }


@router.get("/history", response_model=PromptHistoryResponse)
async def get_prompt_history(
    limit: int = 20,
    token: str = Depends(get_access_token),
):
    """获取提示词变更历史"""
    username = await _get_username_from_token(token)

    history = prompt_manager.get_history(username, limit=limit)

    return PromptHistoryResponse(records=history.records)


@router.get("/default")
async def get_default_prompt(token: str = Depends(get_access_token)):
    """获取全局默认提示词（只读，供参考）"""
    _ = await _get_username_from_token(token)

    return {
        "content": config.system_prompt or "",
        "source": "global_config",
    }


# ---- system_rules 接口 ----

class GetRulesResponse(BaseModel):
    """获取功能协议响应"""
    content: str = Field(description="当前生效的功能协议内容")
    is_custom: bool = Field(description="是否为用户自定义（非全局默认）")


class UpdateRulesRequest(BaseModel):
    """更新功能协议请求"""
    content: str = Field(description="新的功能协议内容")
    source: str = Field(default="user", description="变更来源")


@router.get("/rules", response_model=GetRulesResponse)
async def get_rules(token: str = Depends(get_access_token)):
    """获取当前用户生效的功能协议"""
    username = await _get_username_from_token(token)
    user_rules = prompt_manager.get_rules(username)
    effective = prompt_manager.get_effective_rules(username)
    return GetRulesResponse(
        content=effective,
        is_custom=user_rules is not None,
    )


@router.put("/rules", response_model=UpdatePromptResponse)
async def update_rules(
    request: UpdateRulesRequest,
    token: str = Depends(get_access_token),
):
    """更新当前用户的功能协议"""
    username = await _get_username_from_token(token)
    success = prompt_manager.set_rules(
        username=username,
        content=request.content,
        source=request.source,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="功能协议更新失败",
        )
    return UpdatePromptResponse(success=True, content=request.content, message="功能协议已更新")


@router.delete("/rules")
async def reset_rules(token: str = Depends(get_access_token)):
    """重置功能协议为全局默认（删除用户独立配置）"""
    username = await _get_username_from_token(token)
    prompt_manager.delete_rules(username)
    return {
        "success": True,
        "message": "已重置为全局默认功能协议",
        "default_rules_preview": (config.system_rules or "")[:200],
    }


@router.get("/rules/default")
async def get_default_rules(token: str = Depends(get_access_token)):
    """获取全局默认功能协议（只读，供参考）"""
    _ = await _get_username_from_token(token)
    return {
        "content": config.system_rules or "",
        "source": "global_config",
    }


# ---- roleplay_prompt 接口 ----

@router.get("/roleplay", response_model=GetRulesResponse)
async def get_roleplay_prompt(token: str = Depends(get_access_token)):
    """获取当前用户生效的情景演绎提示词。"""
    username = await _get_username_from_token(token)
    custom = prompt_manager.get_roleplay_prompt(username)
    effective = prompt_manager.get_effective_roleplay_prompt(username)
    return GetRulesResponse(content=effective, is_custom=custom is not None)


@router.put("/roleplay", response_model=UpdatePromptResponse)
async def update_roleplay_prompt(
    request: UpdateRulesRequest,
    token: str = Depends(get_access_token),
):
    """更新当前用户的情景演绎提示词。"""
    username = await _get_username_from_token(token)
    if not request.content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="情景演绎提示词不能为空",
        )
    success = prompt_manager.set_roleplay_prompt(username=username, content=request.content.strip())
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="情景演绎提示词更新失败",
        )
    return UpdatePromptResponse(success=True, content=request.content.strip(), message="情景演绎提示词已更新")


@router.delete("/roleplay")
async def reset_roleplay_prompt(token: str = Depends(get_access_token)):
    """重置情景演绎提示词为默认。"""
    username = await _get_username_from_token(token)
    prompt_manager.delete_roleplay_prompt(username)
    return {
        "success": True,
        "message": "已重置为默认情景演绎提示词",
        "default_prompt_preview": prompt_manager.get_effective_roleplay_prompt(username)[:200],
    }


@router.get("/roleplay/default")
async def get_default_roleplay_prompt(token: str = Depends(get_access_token)):
    """获取默认情景演绎提示词。"""
    _ = await _get_username_from_token(token)
    from backend.prompt_system import DEFAULT_ROLEPLAY_PROMPT
    return {"content": DEFAULT_ROLEPLAY_PROMPT, "source": "builtin"}


@router.get("/roleplay/exit-summary/default")
async def get_default_roleplay_exit_summary_prompt(token: str = Depends(get_access_token)):
    """获取默认情景结束摘要提示词。"""
    _ = await _get_username_from_token(token)
    from backend.core.bot import DEFAULT_ROLEPLAY_EXIT_SUMMARY_PROMPT
    return {"content": DEFAULT_ROLEPLAY_EXIT_SUMMARY_PROMPT, "source": "builtin"}
