from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


EMOTIONS = ("joy", "anger", "sadness", "pleasure", "surprise", "fatigue")

EMOTION_LABELS = {
    "joy": "喜悦",
    "anger": "愤怒",
    "sadness": "悲伤",
    "pleasure": "愉悦",
    "surprise": "惊讶",
    "fatigue": "疲倦",
}

MOTIVATION_LABELS = {
    "share": "想分享",
    "confide": "想倾诉",
    "rest": "想休息",
    "express": "想表达",
    "express_boundary": "想表达边界",
}

DEFAULT_BASELINES: Dict[str, float] = {
    "joy": 0.35,
    "anger": 0.08,
    "sadness": 0.15,
    "pleasure": 0.32,
    "surprise": 0.12,
    "fatigue": 0.20,
}

DEFAULT_CIRCADIAN: Dict[str, Any] = {
    "timezone": "Asia/Shanghai",
    "night": {
        "start": "23:00",
        "end": "06:00",
        "fatigue_baseline": 0.55,
        "baseline_adjustments": {
            "joy": -0.04,
            "pleasure": -0.05,
        },
    },
    "active": {
        "start": "08:00",
        "end": "22:00",
        "micro_wave_probability": 0.40,
        "micro_wave_amplitude": 0.06,
        "positive_bias": 0.55,
    },
}

DEFAULT_PROACTIVE_CHAT: Dict[str, Any] = {
    "enabled": False,
    "timezone": "Asia/Shanghai",
    "check_interval_seconds": 60,
    "default_prompt": "",
    "behavior_rules": {
        "enabled": True,
        "global_cooldown_seconds": 1800,
        "inactive_greeting": {
            "enabled": True,
            "after_seconds": 21600,
            "min_user_messages": 1,
            "instruction": "",
        },
        "conversation_follow_up": {
            "enabled": True,
            "after_seconds": 900,
            "min_user_messages": 1,
            "instruction": "",
        },
    },
    "message_templates": [],
    "image_generation": {
        "enabled": False,
        "max_per_day": 3,
    },
    "targets": [],
}


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


@dataclass
class ExternalStimulus:
    stimulus_type: str
    intensity: float
    valence: str = "neutral"
    source: str = "system"
    channel: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    message: str = ""
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.created_at:
            data["created_at"] = self.created_at.isoformat()
        return data


@dataclass
class MotivationSignal:
    motivation_type: str
    intensity: float
    description: str
    suggested_action: str
    dominant_emotion: str
    dominant_emotion_intensity: float
    status: str = "active"
    created_at: Optional[datetime] = None
    target_key: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "motivation_type": self.motivation_type,
            "motivation_label": MOTIVATION_LABELS.get(self.motivation_type, self.motivation_type),
            "intensity": round(clamp(self.intensity), 4),
            "description": self.description,
            "suggested_action": self.suggested_action,
            "dominant_emotion": self.dominant_emotion,
            "dominant_emotion_label": EMOTION_LABELS.get(self.dominant_emotion, self.dominant_emotion),
            "dominant_emotion_intensity": round(clamp(self.dominant_emotion_intensity), 4),
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "target_key": self.target_key,
        }


@dataclass
class EmotionState:
    intensities: Dict[str, float]
    baselines: Dict[str, float]
    dominant_emotion: str
    last_updated_at: datetime
    last_tick_duration_ms: float = 0.0
    last_triggered_emotion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intensities": {key: round(clamp(value), 4) for key, value in self.intensities.items()},
            "baselines": {key: round(clamp(value), 4) for key, value in self.baselines.items()},
            "dominant_emotion": self.dominant_emotion,
            "dominant_emotion_label": EMOTION_LABELS.get(self.dominant_emotion, self.dominant_emotion),
            "last_updated_at": self.last_updated_at.isoformat(),
            "last_tick_duration_ms": round(max(0.0, self.last_tick_duration_ms), 4),
            "last_triggered_emotion": self.last_triggered_emotion,
            "last_triggered_emotion_label": EMOTION_LABELS.get(self.last_triggered_emotion or "", self.last_triggered_emotion),
        }


@dataclass
class CerebellumConfigData:
    enabled: bool = False
    tick_interval: int = 30
    decay_rate: float = 0.008
    action_threshold: float = 0.52
    persistence_interval: int = 300
    state_file: str = "data/cerebellum_state.json"
    max_stimulus_step: float = 0.28
    history_limit: int = 2880
    replace_time_windows: bool = True
    motivation_cooldown_seconds: int = 1800
    proactive_chat: Dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_PROACTIVE_CHAT))
    baseline_values: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_BASELINES))
    circadian: Dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_CIRCADIAN))
    inactivity_stimulus: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "after_seconds": 10800,
        "intensity": 0.35,
        "repeat_interval_seconds": 7200,
        "escalation_factor": 1.15,
        "max_intensity": 0.65,
    })
    autonomous_drift: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "drift_probability": 0.25,
        "drift_step": 0.03,
        "preferred_emotions": ["joy", "pleasure", "sadness"],
        "sadness_weight_when_inactive": 0.6,
    })

    def resolved_state_file(self, project_root: Path) -> Path:
        path = Path(self.state_file)
        if path.is_absolute():
            return path
        return project_root / path

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "tick_interval": self.tick_interval,
            "decay_rate": round(max(0.0, self.decay_rate), 6),
            "action_threshold": round(clamp(self.action_threshold), 4),
            "persistence_interval": self.persistence_interval,
            "state_file": self.state_file,
            "max_stimulus_step": round(clamp(self.max_stimulus_step), 4),
            "history_limit": self.history_limit,
            "replace_time_windows": self.replace_time_windows,
            "motivation_cooldown_seconds": self.motivation_cooldown_seconds,
            "proactive_chat": self.proactive_chat,
            "baseline_values": {key: round(clamp(value), 4) for key, value in self.baseline_values.items()},
            "circadian": self.circadian,
            "inactivity_stimulus": self.inactivity_stimulus,
            "autonomous_drift": self.autonomous_drift,
        }
