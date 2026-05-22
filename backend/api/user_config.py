"""用户配置管理 API 接口"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from backend.user import user_manager, auth_manager
from backend.api.deps import get_access_token
from backend.api.bot_provider import get_bot
from backend.adapters.linyu_manager import get_linyu_session_manager


router = APIRouter(prefix="/api", tags=["user_config"])


class UserConfigResponse(BaseModel):
    """用户配置响应模型"""
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


class UpdateUserConfigRequest(BaseModel):
    """更新用户配置请求模型"""
    system_prompt: Optional[str] = Field(default=None, description="系统提示词")
    llm: Optional[Dict[str, Any]] = Field(default=None, description="LLM配置")
    tts: Optional[Dict[str, Any]] = Field(default=None, description="TTS配置")
    image_generation: Optional[Dict[str, Any]] = Field(default=None, description="图像生成配置")
    video_generation: Optional[Dict[str, Any]] = Field(default=None, description="视频生成配置")
    vision: Optional[Dict[str, Any]] = Field(default=None, description="视觉识别配置")
    prompt_enhancer: Optional[Dict[str, Any]] = Field(default=None, description="提示词增强配置")
    emotes: Optional[Dict[str, Any]] = Field(default=None, description="表情包配置")
    adapters: Optional[Dict[str, Any]] = Field(default=None, description="适配器配置")
    preferences: Optional[Dict[str, Any]] = Field(default=None, description="其他偏好设置")


@router.get("/user/config", response_model=UserConfigResponse)
async def get_user_config(token: str = Depends(get_access_token)):
    """获取用户配置"""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少令牌")
    user_info = auth_manager.get_user_from_token(token)
    
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌"
        )
    
    config_dict = await user_manager.get_user_config_dict(user_info['user_id'])
    
    return UserConfigResponse(**config_dict)


@router.put("/user/config", response_model=UserConfigResponse)
async def update_user_config(request: UpdateUserConfigRequest, token: str = Depends(get_access_token)):
    """更新用户配置"""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少令牌")
    user_info = auth_manager.get_user_from_token(token)
    
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌"
        )
    
    # 构建配置数据
    config_data = {}
    if request.system_prompt is not None:
        config_data['system_prompt'] = request.system_prompt
    if request.llm is not None:
        config_data['llm_config'] = request.llm
    if request.tts is not None:
        config_data['tts_config'] = request.tts
    if request.image_generation is not None:
        config_data['image_gen_config'] = request.image_generation
    if request.video_generation is not None:
        config_data['video_gen_config'] = request.video_generation
    if request.vision is not None:
        config_data['vision_config'] = request.vision
    if request.prompt_enhancer is not None:
        config_data['prompt_enhancer_config'] = request.prompt_enhancer
    if request.emotes is not None:
        config_data['emote_config'] = request.emotes
    if request.adapters is not None:
        config_data['adapters'] = request.adapters
    if request.preferences is not None:
        config_data['preferences'] = request.preferences
    
    # 更新配置
    success = await user_manager.update_user_config(user_info['user_id'], config_data)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="配置更新失败"
        )
    
    # 返回更新后的配置
    get_bot().invalidate_user_cache(str(user_info['user_id']))
    config_dict = await user_manager.get_user_config_dict(user_info['user_id'])
    try:
        get_bot().invalidate_user_cache(str(user_info['user_id']))
    except Exception:
        pass
    manager = get_linyu_session_manager()
    if manager:
        manager.request_refresh_user(str(user_info['user_id']))
    
    return UserConfigResponse(**config_dict)


@router.delete("/user/config")
async def reset_user_config(token: str = Depends(get_access_token), config_type: Optional[str] = None):
    """重置用户配置
    
    Args:
        token: 访问令牌
        config_type: 配置类型，可选值: system_prompt, llm, tts, image_generation, vision, 
                     prompt_enhancer, emotes, preferences
                     如果不指定，则重置所有配置
    """
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少令牌")
    user_info = auth_manager.get_user_from_token(token)
    
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌"
        )
    
    # 构建重置数据
    config_data = {}
    
    if config_type:
        # 重置指定类型的配置
        valid_types = [
            'system_prompt', 'llm', 'tts', 'image_generation', 'video_generation',
            'vision', 'prompt_enhancer', 'emotes', 'adapters', 'preferences'
        ]
        
        if config_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的配置类型。有效类型: {', '.join(valid_types)}"
            )
        
        if config_type == 'system_prompt':
            config_data['system_prompt'] = None
        elif config_type == 'llm':
            config_data['llm_config'] = None
        elif config_type == 'tts':
            config_data['tts_config'] = None
        elif config_type == 'image_generation':
            config_data['image_gen_config'] = None
        elif config_type == 'video_generation':
            config_data['video_gen_config'] = None
        elif config_type == 'vision':
            config_data['vision_config'] = None
        elif config_type == 'prompt_enhancer':
            config_data['prompt_enhancer_config'] = None
        elif config_type == 'emotes':
            config_data['emote_config'] = None
        elif config_type == 'adapters':
            config_data['adapters'] = None
        elif config_type == 'preferences':
            config_data['preferences'] = None
    else:
        # 重置所有配置
        config_data = {
            'system_prompt': None,
            'llm_config': None,
            'tts_config': None,
            'image_gen_config': None,
            'video_gen_config': None,
            'vision_config': None,
            'prompt_enhancer_config': None,
            'emote_config': None,
            'adapters': None,
            'preferences': None
        }
    
    # 更新配置
    success = await user_manager.update_user_config(user_info['user_id'], config_data)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="配置重置失败"
        )

    try:
        get_bot().invalidate_user_cache(str(user_info['user_id']))
    except Exception:
        pass

    manager = get_linyu_session_manager()
    if manager:
        manager.request_refresh_user(str(user_info['user_id']))
    
    return {"message": "配置重置成功"}


@router.get("/user/profile", response_model=Dict[str, Any])
async def get_user_profile(token: str = Depends(get_access_token)):
    """获取用户完整信息（包括配置）"""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少令牌")
    user_info = auth_manager.get_user_from_token(token)
    
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌"
        )
    
    user = await user_manager.get_user_by_id(user_info['user_id'])
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    config_dict = await user_manager.get_user_config_dict(user_info['user_id'])
    
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "qq_user_id": user.qq_user_id,
        "avatar": user.avatar,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat(),
        "config": config_dict
    }
