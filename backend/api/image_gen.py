from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from typing import Dict, Any, Optional
import base64

from ..core.bot import Bot
from backend.api.deps import get_access_token
from backend.api.bot_provider import get_bot
from backend.user.auth import auth_manager
from backend.user.data_manager import user_data_manager
from backend.image_gen.base_image_service import BaseImageService
from backend.config import config as app_config


router = APIRouter(prefix="/api/image-gen", tags=["图像生成"])

# 底图管理服务实例
_fallback_path = app_config.get("image_generation", {}).get(
    "default_base_image_path", "backend/data/default_base_image.jpg"
)
base_image_service = BaseImageService(user_data_manager, _fallback_path)


class ImageGenConfigRequest(BaseModel):
    """图像生成配置请求"""
    enabled: bool = True
    provider: str = "modelscope"
    fallback_provider: str = "yunwu"
    enable_fallback: bool = True
    modelscope: Dict[str, Any] = {}
    yunwu: Dict[str, Any] = {}
    kling_api: Dict[str, Any] = {}
    image_api: Dict[str, Any] = {}
    gpt_image: Dict[str, Any] = {}
    trigger_keywords: list = []
    generating_message: str = "🎨 正在为你生成图片，请稍候..."
    error_message: str = "😢 图片生成失败：{error}"
    success_message: str = "✨ 图片已生成完成！"


class BaseImageUploadResponse(BaseModel):
    """底图上传响应"""
    success: bool
    message: str
    filename: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None


class BaseImageGetResponse(BaseModel):
    """底图查看响应"""
    success: bool
    message: str
    image_data: Optional[str] = None  # Base64 encoded
    filename: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    last_modified: Optional[str] = None  # ISO timestamp


class ImageGenRequest(BaseModel):
    """图像生成请求"""
    prompt: str
    user_id: Optional[str] = None


class ImageGenResponse(BaseModel):
    """图像生成响应"""
    success: bool
    message: str
    image_data: Optional[str] = None


@router.get("/config")
async def get_image_gen_config(bot: Bot = Depends(get_bot)):
    """获取图像生成配置"""
    try:
        config = bot.get_image_gen_config()
        return {"success": True, "data": config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config")
async def update_image_gen_config(
    request: ImageGenConfigRequest,
    bot: Bot = Depends(get_bot)
):
    """更新图像生成配置"""
    try:
        config_dict = request.dict()
        bot.update_image_gen_config(config_dict)
        return {"success": True, "message": "配置更新成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_image(
    request: ImageGenRequest,
    bot: Bot = Depends(get_bot),
    token: str = Depends(get_access_token),
):
    """生成图像"""
    try:
        effective_user_id = request.user_id or "web_image_user"
        if token:
            user_info = auth_manager.get_user_from_token(token)
            if user_info:
                # 优先使用 username（底图按 username 存储）
                effective_user_id = user_info.get("username") or str(user_info.get("qq_user_id") or user_info.get("user_id") or effective_user_id)

        image_data = await bot.generate_image(request.prompt, user_id=effective_user_id)
        if image_data:
            base64_data = base64.b64encode(image_data).decode('utf-8')
            return ImageGenResponse(success=True, message="图片生成成功", image_data=base64_data)
        return ImageGenResponse(success=False, message="图片生成失败")
    except Exception as e:
        return ImageGenResponse(success=False, message=f"图片生成失败：{str(e)}")


@router.post("/test-connection")
async def test_connection(
    bot: Bot = Depends(get_bot),
    token: str = Depends(get_access_token),
):
    """测试图像生成连接"""
    try:
        # 非管理员使用用户级配置测试；管理员用全局配置
        user_id = None
        if token:
            user_info = auth_manager.get_user_from_token(token)
            if user_info:
                current_user_id = user_info.get("user_id") or user_info.get("id")
                if current_user_id:
                    from backend.user import user_manager
                    user = await user_manager.get_user_by_id(int(current_user_id))
                    if not user or not getattr(user, "is_admin", 0):
                        user_id = str(current_user_id)

        success = await bot.test_image_gen_connection(user_id=user_id or None)
        return {"success": success, "message": "连接成功" if success else "连接失败"}
    except Exception as e:
        return {"success": False, "message": f"连接测试失败：{str(e)}"}


# ============ 底图管理端点 ============


def _get_authenticated_username(token: str) -> str:
    """从 token 中获取已认证的用户名，未认证则抛出 401。"""
    if not token:
        raise HTTPException(status_code=401, detail="未授权")
    user_info = auth_manager.get_user_from_token(token)
    if not user_info:
        raise HTTPException(status_code=401, detail="未授权")
    username = user_info.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="未授权")
    return username


@router.post("/base-image/upload", response_model=BaseImageUploadResponse)
async def upload_base_image(
    file: UploadFile = File(...),
    token: str = Depends(get_access_token),
):
    """上传用户底图（multipart 文件上传）。

    - 支持格式：JPEG/PNG/WebP
    - 大小限制：≤5MB
    - 每用户最多一张，新上传会替换旧底图
    """
    username = _get_authenticated_username(token)

    # 读取文件内容
    file_data = await file.read()

    # 验证文件格式（通过文件名扩展名）
    filename = file.filename or "upload"
    from pathlib import Path as _Path
    ext = _Path(filename).suffix.lower()
    if ext not in BaseImageService.ALLOWED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail="不支持的格式，仅支持 JPEG/PNG/WebP",
        )

    # 验证文件大小
    if len(file_data) > BaseImageService.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="文件大小不能超过 5MB",
        )

    # 调用服务上传
    try:
        result = await base_image_service.upload_base_image(username, file_data, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return BaseImageUploadResponse(
        success=True,
        message="底图上传成功",
        filename=result.get("filename"),
        file_size=result.get("file_size"),
        mime_type=result.get("mime_type"),
    )


@router.get("/base-image", response_model=BaseImageGetResponse)
async def get_base_image(
    token: str = Depends(get_access_token),
):
    """获取当前用户底图（Base64 编码）及元数据。"""
    username = _get_authenticated_username(token)

    result = await base_image_service.get_base_image(username)
    if result is None:
        raise HTTPException(status_code=404, detail="未上传底图")

    return BaseImageGetResponse(
        success=True,
        message="获取底图成功",
        image_data=result.get("image_data"),
        filename=result.get("filename"),
        file_size=result.get("file_size"),
        mime_type=result.get("mime_type"),
        last_modified=result.get("last_modified"),
    )


@router.delete("/base-image")
async def delete_base_image(
    token: str = Depends(get_access_token),
):
    """删除当前用户底图。"""
    username = _get_authenticated_username(token)

    deleted = await base_image_service.delete_base_image(username)
    if not deleted:
        raise HTTPException(status_code=404, detail="未上传底图")

    return {"success": True, "message": "底图已删除"}
