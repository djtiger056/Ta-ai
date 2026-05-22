"""Linyu 通话配置。"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class VoiceCallConfig(BaseModel):
    enabled: bool = Field(default=False)
    auto_answer: bool = Field(default=True)
    answer_delay_seconds: float = Field(default=1.0)
    ring_timeout_seconds: int = Field(default=30)
    max_call_duration_seconds: int = Field(default=600)
    audio_only: bool = Field(default=True)

    @classmethod
    def from_linyu_adapter_config(
        cls,
        adapter_cfg: Optional[Dict[str, Any]],
        *,
        nested: bool = False,
    ) -> "VoiceCallConfig":
        linyu = (adapter_cfg or {}) if nested else ((adapter_cfg or {}).get("linyu", {}) or {})
        vc = linyu.get("voice_call", {}) or {}
        return cls.model_validate(vc)
