"""
TTS API 路由
"""

import asyncio
import base64
import re
import uuid
from fastapi import APIRouter, HTTPException, Response, UploadFile, File, Form, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import yaml
from pathlib import Path
import logging
from ..tts.manager import TTSManager
from ..config import config as app_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["tts"])

# 全局TTS管理器实例
_tts_manager: Optional[TTSManager] = None


class TTSConfigRequest(BaseModel):
    """TTS配置请求"""
    enabled: Optional[bool] = Field(None, description="是否启用TTS")
    probability: Optional[float] = Field(None, description="TTS触发概率")
    proactive_enabled: Optional[bool] = Field(None, description="是否允许AI主动触发TTS")
    provider: Optional[str] = Field(None, description="TTS提供商")
    voice_only_when_tts: Optional[bool] = Field(None, description="启用后有语音时隐藏对应文本，仅发送语音")
    qihang: Optional[Dict[str, Any]] = Field(None, description="启航AI配置")
    qwen: Optional[Dict[str, Any]] = Field(None, description="千问（声音复刻）配置")
    segment_config: Optional[Dict[str, Any]] = Field(None, description="分段配置")
    randomization: Optional[Dict[str, Any]] = Field(None, description="随机播报配置")
    text_cleaning: Optional[Dict[str, Any]] = Field(None, description="文本清洗配置")


class TTSSynthesisRequest(BaseModel):
    """TTS合成请求"""
    text: str = Field(..., description="要合成的文本")
    voice: Optional[str] = Field(None, description="语音角色")


class TTSResponse(BaseModel):
    """TTS响应"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


def get_tts_manager() -> TTSManager:
    """获取TTS管理器实例"""
    global _tts_manager
    if _tts_manager is None:
        try:
            tts_config = app_config.tts_config
            _tts_manager = TTSManager(tts_config)
        except Exception as e:
            logger.error(f"加载TTS配置失败: {str(e)}")
            _tts_manager = TTSManager({})
    return _tts_manager


QWEN_VOICE_SAMPLE_DIR = Path("data/tts/qwen_voice_samples")


def _load_config_file() -> Dict[str, Any]:
    config_path = Path("config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_config_file(config: Dict[str, Any]) -> None:
    config_path = Path("config.yaml")
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


def _get_qwen_cfg(config: Dict[str, Any]) -> Dict[str, Any]:
    tts_cfg = config.setdefault("tts", {})
    return tts_cfg.setdefault("qwen", {})

def _validate_preferred_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise ValueError("preferred_name 不能为空")
    if len(name) > 16:
        raise ValueError("preferred_name 不能超过 16 个字符")
    if not re.fullmatch(r"[0-9A-Za-z_]+", name):
        raise ValueError("preferred_name 仅允许数字、大小写字母和下划线")
    return name


@router.get("/tts/config")
async def get_tts_config():
    """获取TTS配置"""
    try:
        manager = get_tts_manager()
        config = manager.get_config()
        return {"success": True, "data": config}
    except Exception as e:
        logger.error(f"获取TTS配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取TTS配置失败: {str(e)}")


@router.post("/tts/config")
async def update_tts_config(config_request: TTSConfigRequest):
    """更新TTS配置"""
    try:
        # 只更新提供的字段
        update_data = config_request.dict(exclude_unset=True)
        
        # 通过统一的 Config 类更新并持久化
        app_config.update_config('tts', {k: v for k, v in update_data.items() if v is not None})
        app_config.refresh_from_file()
        
        # 更新TTS管理器配置
        manager = get_tts_manager()
        manager.update_config(app_config.tts_config)
        
        logger.info("TTS配置更新成功")
        return {"success": True, "message": "TTS配置更新成功"}
        
    except Exception as e:
        logger.error(f"更新TTS配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新TTS配置失败: {str(e)}")


@router.get("/tts/voices")
async def get_tts_voices():
    """获取可用语音角色列表"""
    try:
        manager = get_tts_manager()
        voices = await manager.get_voices()
        return {"success": True, "data": voices}
    except Exception as e:
        logger.error(f"获取语音角色列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取语音角色列表失败: {str(e)}")


@router.post("/tts/synthesize")
async def synthesize_speech(request: TTSSynthesisRequest):
    """合成语音"""
    try:
        manager = get_tts_manager()
        
        # 检查TTS是否启用
        if not manager.config.enabled:
            raise HTTPException(status_code=400, detail="TTS功能未启用")
        
        # 合成语音
        audio_data = await manager.synthesize(request.text, request.voice)
        
        if not audio_data:
            raise HTTPException(status_code=400, detail="语音合成失败，可能文本为空或包含不支持的内容")

        # 粗略识别音频类型，避免前端/浏览器播放异常
        media_type = "audio/mpeg"
        filename = "tts_output.mp3"
        if audio_data[:4] == b"RIFF" and audio_data[8:12] == b"WAVE":
            media_type = "audio/wav"
            filename = "tts_output.wav"
        elif audio_data[:4] == b"OggS":
            media_type = "audio/ogg"
            filename = "tts_output.ogg"

        # 返回音频数据
        return Response(
            content=audio_data,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"语音合成失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"语音合成失败: {str(e)}")


@router.post("/tts/test")
async def test_tts_connection():
    """测试TTS连接"""
    try:
        manager = get_tts_manager()
        success = await manager.test_connection()

        if success:
            return {"success": True, "message": "TTS连接测试成功"}
        else:
            return {"success": False, "message": "TTS连接测试失败"}

    except Exception as e:
        logger.error(f"TTS连接测试失败: {str(e)}")
        return {"success": False, "message": f"TTS连接测试失败: {str(e)}"}


@router.get("/tts/qwen/voice-sample/{filename}")
async def get_qwen_voice_sample(filename: str):
    """提供给 DashScope 拉取的声音复刻音频样本文件（需公网可访问）"""
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=404, detail="not found")

    file_path = (QWEN_VOICE_SAMPLE_DIR / filename).resolve()
    base_dir = QWEN_VOICE_SAMPLE_DIR.resolve()
    if base_dir not in file_path.parents:
        raise HTTPException(status_code=404, detail="not found")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="not found")

    return FileResponse(path=str(file_path), filename=filename)


@router.post("/tts/qwen/voice-clone")
async def qwen_voice_clone(
    file: UploadFile = File(...),
    activate: bool = Form(True),
    api_key: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    preferred_name: Optional[str] = Form(None),
    customization_url: Optional[str] = Form(None),
    realtime_ws_url: Optional[str] = Form(None),
):
    """
    上传声音复刻音频并创建/更新千问音色（voice_id）。

    说明：根据官方文档，声音复刻接口支持直接传入 `audio.data` 的 DataURI（Base64），不需要公网 URL。
    """
    try:
        QWEN_VOICE_SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

        config = _load_config_file()
        qwen_cfg = _get_qwen_cfg(config)

        # 允许前端直接传入参数（避免“先保存配置再上传”的额外步骤）
        if api_key is not None:
            qwen_cfg["api_key"] = api_key
        if model is not None:
            qwen_cfg["model"] = model
        if preferred_name is not None:
            qwen_cfg["preferred_name"] = preferred_name
        if customization_url is not None:
            qwen_cfg["customization_url"] = customization_url
        if realtime_ws_url is not None:
            qwen_cfg["realtime_ws_url"] = realtime_ws_url

        resolved_api_key = (qwen_cfg.get("api_key") or "").strip()
        if not resolved_api_key:
            raise HTTPException(status_code=400, detail="千问TTS API Key 未配置（tts.qwen.api_key）")

        suffix = Path(file.filename or "").suffix
        if not suffix:
            suffix = ".wav"
        sample_name = f"qwen_voice_{uuid.uuid4().hex}{suffix}"
        sample_path = QWEN_VOICE_SAMPLE_DIR / sample_name

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="上传文件为空")
        sample_path.write_bytes(content)

        # 清理旧样本文件（保留最新）
        old_sample = (qwen_cfg.get("voice_sample_file") or "").strip()
        if old_sample and old_sample != sample_name:
            try:
                old_path = QWEN_VOICE_SAMPLE_DIR / old_sample
                if old_path.exists():
                    old_path.unlink()
            except Exception:
                pass

        qwen_cfg["voice_sample_file"] = sample_name

        content_type = (file.content_type or "").strip()
        if not content_type.startswith("audio/"):
            ext = suffix.lower()
            if ext == ".wav":
                content_type = "audio/wav"
            elif ext == ".mp3":
                content_type = "audio/mpeg"
            elif ext == ".m4a":
                content_type = "audio/mp4"
            elif ext == ".aac":
                content_type = "audio/aac"
            elif ext == ".ogg":
                content_type = "audio/ogg"
            else:
                content_type = "audio/mpeg"

        data_uri = f"data:{content_type};base64,{base64.b64encode(content).decode('ascii')}"

        target_model = (qwen_cfg.get("model") or "").strip() or "qwen3-tts-vc-realtime-2025-11-27"
        raw_preferred_name = (qwen_cfg.get("preferred_name") or "lfbot").strip() or "lfbot"
        try:
            resolved_preferred_name = _validate_preferred_name(raw_preferred_name)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"preferred_name 不合法：{e}（示例：lfbot_01）",
            )
        url = (qwen_cfg.get("customization_url") or "").strip() or "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization"

        headers = {
            "Authorization": f"Bearer {resolved_api_key}",
            "Content-Type": "application/json",
        }

        async def _post(payload: Dict[str, Any]) -> Dict[str, Any]:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    text = await resp.text()
                    if resp.status != 200:
                        raise HTTPException(status_code=400, detail=f"声音复刻请求失败: {resp.status}, {text}")
                    try:
                        return await resp.json()
                    except Exception:
                        raise HTTPException(status_code=400, detail=f"声音复刻响应解析失败: {text}")

        existing_voice_id = (qwen_cfg.get("voice_id") or "").strip()
        if existing_voice_id:
            await _post({
                "model": "qwen-voice-enrollment",
                "input": {
                    "action": "delete",
                    "voice": existing_voice_id,
                },
            })

        result = await _post({
            "model": "qwen-voice-enrollment",
            "input": {
                "action": "create",
                "target_model": target_model,
                "preferred_name": resolved_preferred_name,
                "audio": {"data": data_uri},
            },
        })

        voice_id = (((result or {}).get("output") or {}).get("voice") or "").strip()
        if not voice_id:
            raise HTTPException(status_code=400, detail=f"声音复刻成功但未返回 voice_id: {result}")

        qwen_cfg["voice_id"] = voice_id

        if activate:
            config.setdefault("tts", {})["provider"] = "qwen"
            config.setdefault("tts", {})["enabled"] = True

        _save_config_file(config)

        manager = get_tts_manager()
        manager.update_config(config.get("tts", {}))

        return {
            "success": True,
            "message": "声音复刻音色创建/更新成功",
            "data": {
                "voice_id": voice_id,
                "voice_sample_file": sample_name,
                "provider": config.get("tts", {}).get("provider"),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"千问声音复刻失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"千问声音复刻失败: {str(e)}")
