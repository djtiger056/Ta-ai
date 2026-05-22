from typing import Any, Dict, List

from pydantic import BaseModel


class VideoApiConfig(BaseModel):
    """Images API 视频生成服务配置。"""

    api_base: str = "http://127.0.0.1:18080"
    api_key: str = ""
    provider: str = "qwen"
    model: str = "wan2.7-t2v"
    timeout: int = 600
    ratio: str = "16:9"
    resolution: str = "1080P"
    duration: int = 5
    use_async: bool = False
    poll_interval: float = 4.0


class VideoGenerationConfig(BaseModel):
    """视频生成配置。"""

    enabled: bool = False
    provider: str = "video_api"
    video_api: VideoApiConfig = VideoApiConfig()
    trigger_keywords: List[str] = [
        "生成视频",
        "做个视频",
        "做一段视频",
        "视频生成",
        "文生视频",
    ]
    prompt_instruction: str = (
        "用户刚刚明确提出了视频生成需求。你可以把用户需求整理成一段适合视频生成模型的中文提示词。"
        "如果确实要生成视频，只输出自然回复，并在末尾附加一段 [GEN_VIDEO: 提示词]。"
        "提示词应包含主体、动作、场景、镜头、风格、光线和时长感。"
        "不要在用户没有主动要求生成视频时使用 [GEN_VIDEO:]。"
    )
    generating_message: str = "🎬 正在为你生成视频，请稍候..."
    error_message: str = "😢 视频生成失败：{error}"
    success_message: str = "✨ 视频已生成完成！"

    class Config:
        extra = "allow"
