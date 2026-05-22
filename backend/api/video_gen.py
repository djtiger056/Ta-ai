from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Any, Dict, Optional

from ..core.bot import Bot
from backend.api.deps import get_access_token
from backend.api.bot_provider import get_bot
from backend.user import auth_manager, user_manager


router = APIRouter(prefix="/api/video-gen", tags=["视频生成"])


class VideoGenConfigRequest(BaseModel):
    enabled: bool = True
    provider: str = "video_api"
    video_api: Dict[str, Any] = {}
    trigger_keywords: list = []
    prompt_instruction: str = ""
    generating_message: str = "🎬 正在为你生成视频，请稍候..."
    error_message: str = "😢 视频生成失败：{error}"
    success_message: str = "✨ 视频已生成完成！"


class VideoGenRequest(BaseModel):
    prompt: str
    user_id: Optional[str] = None


class VideoGenResponse(BaseModel):
    success: bool
    message: str
    video_url: Optional[str] = None


@router.get("/config")
async def get_video_gen_config(bot: Bot = Depends(get_bot)):
    try:
        config = bot.get_video_gen_config()
        return {"success": True, "data": config}
    except Exception as e:
        return {"success": False, "message": str(e), "data": {}}


@router.post("/config")
async def update_video_gen_config(
    request: VideoGenConfigRequest,
    bot: Bot = Depends(get_bot),
):
    try:
        bot.update_video_gen_config(request.dict())
        return {"success": True, "message": "配置更新成功"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/generate")
async def generate_video(
    request: VideoGenRequest,
    bot: Bot = Depends(get_bot),
    token: str = Depends(get_access_token),
):
    try:
        effective_user_id = request.user_id or "web_video_user"
        if token:
            user_info = auth_manager.get_user_from_token(token)
            if user_info:
                effective_user_id = str(user_info.get("user_id") or user_info.get("id") or effective_user_id)

        video_url = await bot.generate_video(request.prompt, user_id=effective_user_id)
        if video_url:
            return VideoGenResponse(success=True, message="视频生成成功", video_url=video_url)
        return VideoGenResponse(success=False, message="视频生成失败")
    except Exception as e:
        return VideoGenResponse(success=False, message=f"视频生成失败：{str(e)}")


@router.post("/test-connection")
async def test_connection(
    bot: Bot = Depends(get_bot),
    token: str = Depends(get_access_token),
):
    try:
        user_id = None
        if token:
            user_info = auth_manager.get_user_from_token(token)
            if user_info:
                current_user_id = user_info.get("user_id") or user_info.get("id")
                if current_user_id:
                    user = await user_manager.get_user_by_id(int(current_user_id))
                    if not user or not getattr(user, "is_admin", 0):
                        user_id = str(current_user_id)

        success = await bot.test_video_gen_connection(user_id=user_id or None)
        return {"success": success, "message": "连接成功" if success else "连接失败"}
    except Exception as e:
        return {"success": False, "message": f"连接测试失败：{str(e)}"}
