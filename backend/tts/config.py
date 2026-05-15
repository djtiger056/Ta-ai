"""
TTS 配置模型
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class TTSRandomizationConfig(BaseModel):
    """TTS 随机播报配置"""
    enabled: bool = Field(True, description="是否启用随机播报")
    full_probability: float = Field(1.0, description="完整播报概率")
    partial_probability: float = Field(0.0, description="部分句子播报概率")
    none_probability: float = Field(0.0, description="不播报概率")
    min_partial_sentences: int = Field(1, description="部分播报时最少句子数")
    max_partial_sentences: int = Field(2, description="部分播报时最多句子数")


class TTSConfig(BaseModel):
    """TTS 配置"""
    enabled: bool = Field(True, description="是否启用TTS")
    probability: float = Field(1.0, description="TTS触发概率，0-1之间")
    proactive_enabled: bool = Field(True, description="是否允许AI主动触发TTS（通过[TTS]标签）")
    provider: str = Field("qihang", description="TTS提供商(qihang/qwen)")
    voice_only_when_tts: bool = Field(False, description="启用后有语音时隐藏对应文本，仅发送语音")
    qihang: Dict[str, Any] = Field(default_factory=lambda: {
        "api_base": "https://api.qhaigc.net/v1",
        "api_key": "",
        "model": "qhai-tts",
        "voice": "柔情萝莉"
    }, description="启航AI配置")
    qwen: Dict[str, Any] = Field(default_factory=lambda: {
        "api_key": "",
        "model": "qwen3-tts-vc-realtime-2025-11-27",
        "voice_id": "",
        "preferred_name": "lfbot",
        "customization_url": "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization",
        "realtime_ws_url": "wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
        "voice_sample_file": "",
        "audio_format": "mp3_44100",
        "synthesis_type": 0,
        "volume": 50,
        "speech_rate": 1.0,
        "pitch_rate": 1.0,
        "seed": 0,
        "instruction": "",
        "language_hints": [],
        "timeout_millis": 60000
    }, description="千问（DashScope CosyVoice）声音复刻配置")
    segment_config: Dict[str, Any] = Field(default_factory=lambda: {
        "enabled": True,
        "strategy": "last",
        "max_segments": 1,
        "send_timing": "async",
        "delay_range": [0.5, 2.0],
        "min_segment_length": 5,
        "max_segment_length": 100,
        "interval_step": 2
    }, description="分段配置")
    randomization: TTSRandomizationConfig = Field(
        default_factory=TTSRandomizationConfig,
        description="随机播报策略配置"
    )
    text_cleaning: Dict[str, Any] = Field(default_factory=lambda: {
        "enabled": False,
        "remove_emoji": True,
        "remove_kaomoji": True,
        "remove_action_text": True,
        "remove_brackets_content": True,
        "remove_markdown": True,
        "max_length": 500
    }, description="文本清洗配置")


class TTSSegmentConfig(BaseModel):
    """TTS 分段配置"""
    enabled: bool = Field(True, description="是否启用分段处理")
    strategy: str = Field("last", description="分段策略: first, last, middle")
    max_segments: int = Field(1, description="最大分段数")
    send_timing: str = Field("async", description="发送时机: sync, async")
    delay_range: List[float] = Field([0.5, 2.0], description="延迟范围(秒)")
    min_segment_length: int = Field(5, description="最小分段长度")
    max_segment_length: int = Field(100, description="最大分段长度")
    interval_step: int = Field(2, description="间隔步长")


class TTSTextCleaningConfig(BaseModel):
    """TTS 文本清洗配置"""
    enabled: bool = Field(False, description="是否启用文本清洗")
    remove_emoji: bool = Field(True, description="移除emoji")
    remove_kaomoji: bool = Field(True, description="移除颜文字")
    remove_action_text: bool = Field(True, description="移除动作描述")
    remove_brackets_content: bool = Field(True, description="移除括号内容")
    remove_markdown: bool = Field(True, description="移除Markdown标记")
    max_length: int = Field(500, description="最大文本长度")
