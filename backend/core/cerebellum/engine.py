from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections import deque
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable, Deque, Dict, List, Optional
from zoneinfo import ZoneInfo

from ...config import config as global_config
from .models import (
    DEFAULT_BASELINES,
    DEFAULT_CIRCADIAN,
    EMOTION_LABELS,
    EMOTIONS,
    ExternalStimulus,
    EmotionState,
    MotivationSignal,
    CerebellumConfigData,
    clamp,
)

logger = logging.getLogger(__name__)


class CerebellumEngine:
    """轻量级情绪与动机引擎。"""

    def __init__(self, proactive_dispatcher: Optional[Callable[[MotivationSignal], Awaitable[bool]]] = None):
        self.project_root = Path(__file__).resolve().parents[3]
        self.proactive_dispatcher = proactive_dispatcher
        self.config = self._load_config()
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = asyncio.Lock()
        self._stimuli: asyncio.Queue[ExternalStimulus] = asyncio.Queue()
        self._subscribers: set[tuple[asyncio.Queue[Dict[str, Any]], asyncio.AbstractEventLoop]] = set()
        self._last_persist_at: Optional[datetime] = None
        self._last_user_message_at: Dict[str, datetime] = {}
        self._inactivity_triggered_for: Dict[str, datetime] = {}
        self.active_motivations: Deque[MotivationSignal] = deque(maxlen=50)
        self.history: Deque[Dict[str, Any]] = deque(maxlen=max(1, self.config.history_limit))
        self._last_active_target_key: Optional[str] = None
        # 动机冷却：防止高情绪持续期间频繁推送主动消息
        self._last_motivation_dispatched_at: Optional[datetime] = None
        self.state = self._load_or_initialize_state()

    def _load_config(self) -> CerebellumConfigData:
        raw = global_config.get("cerebellum", {}) or {}
        if not isinstance(raw, dict):
            raw = {}
        baselines = dict(DEFAULT_BASELINES)
        configured_baselines = raw.get("baseline_values") or raw.get("baselines") or {}
        if isinstance(configured_baselines, dict):
            for emotion in EMOTIONS:
                baselines[emotion] = self._safe_float(configured_baselines.get(emotion), baselines[emotion], 0.0, 1.0)

        cfg = CerebellumConfigData(
            enabled=bool(raw.get("enabled", False)),
            tick_interval=self._safe_int(raw.get("tick_interval"), 30, 10, 86400),
            decay_rate=self._safe_float(raw.get("decay_rate"), 0.015, 0.0, 1.0),
            action_threshold=self._safe_float(raw.get("action_threshold"), 0.68, 0.0, 1.0),
            persistence_interval=self._safe_int(raw.get("persistence_interval"), 300, 30, 86400),
            state_file=str(raw.get("state_file") or "data/cerebellum_state.json"),
            max_stimulus_step=self._safe_float(raw.get("max_stimulus_step"), 0.18, 0.01, 1.0),
            history_limit=self._safe_int(raw.get("history_limit"), 2880, 10, 100000),
            replace_time_windows=bool(raw.get("replace_time_windows", True)),
            motivation_cooldown_seconds=self._safe_int(raw.get("motivation_cooldown_seconds"), 1800, 60, 86400),
            baseline_values=baselines,
            circadian=self._merge_dict(DEFAULT_CIRCADIAN, raw.get("circadian") if isinstance(raw.get("circadian"), dict) else {}),
            inactivity_stimulus=self._merge_dict({
                "enabled": True,
                "after_seconds": 21600,
                "intensity": 0.22,
            }, raw.get("inactivity_stimulus") if isinstance(raw.get("inactivity_stimulus"), dict) else {}),
        )
        return cfg

    def reload_config(self, updates: Optional[Dict[str, Any]] = None) -> CerebellumConfigData:
        if updates:
            global_config.update_config("cerebellum", updates)
        else:
            global_config.refresh_from_file()
        self.config = self._load_config()
        self.history = deque(self.history, maxlen=max(1, self.config.history_limit))
        self.state.baselines = self._current_baselines(self._now())
        return self.config

    async def start(self):
        if self.running:
            return
        self.loop = asyncio.get_running_loop()
        self.running = True
        self.task = asyncio.create_task(self._run_loop())
        print("[Cerebellum] 小脑情感引擎已启动")

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        await self.persist_state()
        print("[Cerebellum] 小脑情感引擎已停止")

    async def _run_loop(self):
        while self.running:
            try:
                if self.config.enabled:
                    await self.tick()
                else:
                    await self._broadcast()
            except Exception as exc:
                logger.exception("小脑引擎 Tick 失败: %s", exc)
            await asyncio.sleep(max(10, int(self.config.tick_interval)))

    async def tick(self) -> EmotionState:
        started = time.perf_counter()
        async with self._lock:
            now = self._now()
            elapsed = max(0.0, (now - self.state.last_updated_at).total_seconds())
            baselines = self._current_baselines(now)
            stimuli = self._drain_stimuli()
            self._apply_decay(elapsed, baselines)
            for stimulus in stimuli:
                self._apply_stimulus(stimulus)
            self._apply_micro_wave(now)
            self._apply_inactivity_stimulus(now)
            self.state.baselines = baselines
            self.state.dominant_emotion = self._dominant_emotion()
            self.state.last_updated_at = now
            self.state.last_tick_duration_ms = (time.perf_counter() - started) * 1000

            signals = self._evaluate_motivations(now)
            self.active_motivations.extend(signals)
            self._append_history(now, signals)
            await self._dispatch_motivation(signals)
            if self._should_persist(now):
                await self.persist_state()
            snapshot = self.state

        await self._broadcast()
        return snapshot

    async def submit_stimulus(self, stimulus: ExternalStimulus):
        stimulus.created_at = stimulus.created_at or self._now()
        if stimulus.source == "user" and stimulus.user_id:
            key = self._compose_target_key(stimulus.channel or "web", stimulus.user_id, stimulus.session_id)
            self._last_user_message_at[key] = stimulus.created_at
            self._inactivity_triggered_for.pop(key, None)
            self._last_active_target_key = key
        await self._stimuli.put(stimulus)

    async def submit_message_stimulus(
        self,
        message: Optional[str],
        channel: str,
        user_id: str,
        session_id: Optional[str] = None,
    ):
        text = str(message or "")
        valence, intensity = self.analyze_message(text)
        await self.submit_stimulus(ExternalStimulus(
            stimulus_type="user_message",
            intensity=intensity,
            valence=valence,
            source="user",
            channel=channel,
            user_id=user_id,
            session_id=session_id or user_id,
            message=text,
        ))

    def analyze_message(self, message: str) -> tuple[str, float]:
        text = str(message or "").lower()
        positive_words = self._get_sentiment_words("positive")
        negative_words = self._get_sentiment_words("negative")
        surprise_words = self._get_sentiment_words("surprise")
        positive = sum(1 for word in positive_words if word in text)
        negative = sum(1 for word in negative_words if word in text)
        surprise = sum(1 for word in surprise_words if word in text)
        length_bonus = min(0.12, len(text.strip()) / 500)
        if surprise and surprise >= positive and surprise >= negative:
            return "surprise", clamp(0.22 + 0.08 * surprise + length_bonus)
        if positive > negative:
            return "positive", clamp(0.2 + 0.08 * positive + length_bonus)
        if negative > positive:
            return "negative", clamp(0.22 + 0.08 * negative + length_bonus)
        return "neutral", clamp(0.08 + length_bonus)

    def _get_sentiment_words(self, category: str) -> tuple[str, ...]:
        """从外部词典文件加载情感关键词，带缓存。"""
        if not hasattr(self, "_sentiment_cache"):
            self._sentiment_cache: Dict[str, tuple[str, ...]] = {}
            try:
                import yaml
                words_file = self.project_root / "backend" / "data" / "sentiment_words.yaml"
                if words_file.exists():
                    data = yaml.safe_load(words_file.read_text(encoding="utf-8")) or {}
                    for key in ("positive", "negative", "surprise"):
                        items = data.get(key, [])
                        self._sentiment_cache[key] = tuple(str(w).lower() for w in items if w)
            except Exception as exc:
                logger.warning("加载情感词典失败，使用内置词库: %s", exc)
            # 内置兜底
            if "positive" not in self._sentiment_cache:
                self._sentiment_cache["positive"] = ("谢谢", "开心", "喜欢", "爱你", "棒", "厉害", "高兴", "舒服", "期待", "thank", "love", "great", "happy")
            if "negative" not in self._sentiment_cache:
                self._sentiment_cache["negative"] = ("难过", "讨厌", "烦", "生气", "崩溃", "累死", "失望", "孤独", "哭", "sad", "angry", "hate", "upset")
            if "surprise" not in self._sentiment_cache:
                self._sentiment_cache["surprise"] = ("惊讶", "居然", "竟然", "哇", "天啊", "wow", "surprise")
        return self._sentiment_cache.get(category, ())

    def snapshot(self) -> Dict[str, Any]:
        return {
            "enabled": self.config.enabled,
            "running": self.running,
            "state": self.state.to_dict(),
            "config": self.config.to_dict(),
            "motivation_count": len(self.active_motivations),
        }

    def motivations_snapshot(self) -> List[Dict[str, Any]]:
        return [signal.to_dict() for signal in list(self.active_motivations)[-30:]]

    def history_snapshot(self, hours: float = 24.0, limit: int = 500) -> List[Dict[str, Any]]:
        cutoff = self._now() - timedelta(hours=max(0.1, hours))
        items = []
        for item in self.history:
            ts = item.get("timestamp")
            try:
                dt = datetime.fromisoformat(ts) if isinstance(ts, str) else None
            except ValueError:
                dt = None
            if dt and dt >= cutoff:
                items.append(item)
        return items[-max(1, min(limit, 5000)):]

    async def subscribe(self) -> asyncio.Queue[Dict[str, Any]]:
        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=5)
        # 记录订阅者所在的事件循环，用于跨线程安全推送
        loop = asyncio.get_event_loop()
        self._subscribers.add((queue, loop))
        try:
            queue.put_nowait(self._stream_payload())
        except asyncio.QueueFull:
            pass
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Dict[str, Any]]):
        self._subscribers = {item for item in self._subscribers if item[0] is not queue}

    async def persist_state(self):
        path = self.config.resolved_state_file(self.project_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": self._now().isoformat(),
            "state": self.state.to_dict(),
            "history": list(self.history)[-min(len(self.history), 500):],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._last_persist_at = self._now()

    def _load_or_initialize_state(self) -> EmotionState:
        now = self._now()
        baselines = self._current_baselines(now)
        path = self.config.resolved_state_file(self.project_root)
        if not path.exists():
            return self._initial_state(now, baselines)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            raw_state = payload.get("state", {})
            intensities = {
                emotion: clamp((raw_state.get("intensities") or {}).get(emotion, baselines[emotion]))
                for emotion in EMOTIONS
            }
            saved_at_raw = payload.get("saved_at") or raw_state.get("last_updated_at")
            saved_at = datetime.fromisoformat(saved_at_raw) if saved_at_raw else now
            elapsed = max(0.0, (now - saved_at).total_seconds())
            decay_factor = min(1.0, max(0.0, self.config.decay_rate * elapsed))
            for emotion in EMOTIONS:
                intensities[emotion] = clamp(intensities[emotion] + (baselines[emotion] - intensities[emotion]) * decay_factor)
            state = EmotionState(
                intensities=intensities,
                baselines=baselines,
                dominant_emotion=raw_state.get("dominant_emotion") or "joy",
                last_updated_at=now,
                last_triggered_emotion=raw_state.get("last_triggered_emotion"),
            )
            history = payload.get("history") or []
            for item in history[-self.config.history_limit:]:
                if isinstance(item, dict):
                    self.history.append(item)
            state.dominant_emotion = self._dominant_from_intensities(state.intensities, state.last_triggered_emotion)
            return state
        except Exception as exc:
            logger.warning("小脑状态恢复失败，使用默认基线: %s", exc)
            return self._initial_state(now, baselines)

    def _initial_state(self, now: datetime, baselines: Dict[str, float]) -> EmotionState:
        return EmotionState(
            intensities=dict(baselines),
            baselines=dict(baselines),
            dominant_emotion=self._dominant_from_intensities(baselines, None),
            last_updated_at=now,
        )

    def _current_baselines(self, now: datetime) -> Dict[str, float]:
        baselines = dict(self.config.baseline_values)
        circadian = self.config.circadian if isinstance(self.config.circadian, dict) else {}
        night = circadian.get("night") if isinstance(circadian.get("night"), dict) else {}
        if self._time_in_range(now, night.get("start", "23:00"), night.get("end", "06:00")):
            baselines["fatigue"] = self._safe_float(night.get("fatigue_baseline"), 0.58, 0.0, 1.0)
            adjustments = night.get("baseline_adjustments") or {}
            if isinstance(adjustments, dict):
                for emotion, delta in adjustments.items():
                    if emotion in baselines:
                        baselines[emotion] = clamp(baselines[emotion] + self._safe_float(delta, 0.0, -1.0, 1.0))
        return {emotion: clamp(baselines.get(emotion, DEFAULT_BASELINES[emotion])) for emotion in EMOTIONS}

    def _apply_decay(self, elapsed_seconds: float, baselines: Dict[str, float]):
        # 指数衰减：按经过的等效 Tick 数计算衰减因子，避免长间隔时线性过冲
        ticks_equivalent = elapsed_seconds / max(10, self.config.tick_interval)
        factor = 1.0 - (1.0 - self.config.decay_rate) ** ticks_equivalent
        factor = clamp(factor)
        for emotion in EMOTIONS:
            current = self.state.intensities.get(emotion, baselines[emotion])
            self.state.intensities[emotion] = clamp(current + (baselines[emotion] - current) * factor)

    def _apply_stimulus(self, stimulus: ExternalStimulus):
        step = clamp(stimulus.intensity) * self.config.max_stimulus_step
        valence = str(stimulus.valence or "neutral").lower()
        mapping: Dict[str, float] = {}
        if valence == "positive":
            mapping = {"joy": step, "pleasure": step * 0.8}
        elif valence == "negative":
            mapping = {"sadness": step, "anger": step * 0.35}
        elif valence == "surprise":
            mapping = {"surprise": step}
        elif stimulus.stimulus_type == "ignored":
            mapping = {"sadness": step, "fatigue": step * 0.4}
        else:
            mapping = {"surprise": step * 0.35}
        triggered = None
        strongest_delta = 0.0
        for emotion, delta in mapping.items():
            self.state.intensities[emotion] = clamp(self.state.intensities.get(emotion, 0.0) + delta)
            if delta >= strongest_delta:
                triggered = emotion
                strongest_delta = delta
        if triggered:
            self.state.last_triggered_emotion = triggered

    def _apply_micro_wave(self, now: datetime):
        active = (self.config.circadian or {}).get("active") or {}
        if not isinstance(active, dict):
            return
        if not self._time_in_range(now, active.get("start", "08:00"), active.get("end", "22:00")):
            return
        probability = self._safe_float(active.get("micro_wave_probability"), 0.35, 0.0, 1.0)
        if random.random() > probability:
            return
        amplitude = min(self.config.max_stimulus_step, self._safe_float(active.get("micro_wave_amplitude"), 0.05, 0.0, 1.0))
        emotion = random.choice([e for e in EMOTIONS if e != "anger"])
        delta = random.uniform(-amplitude, amplitude)
        self.state.intensities[emotion] = clamp(self.state.intensities.get(emotion, 0.0) + delta)
        if delta > 0:
            self.state.last_triggered_emotion = emotion

    def _apply_inactivity_stimulus(self, now: datetime):
        cfg = self.config.inactivity_stimulus
        if not isinstance(cfg, dict) or not cfg.get("enabled", True):
            return
        after_seconds = self._safe_int(cfg.get("after_seconds"), 21600, 60, 604800)
        intensity = self._safe_float(cfg.get("intensity"), 0.22, 0.0, 1.0)
        for key, last_at in list(self._last_user_message_at.items()):
            if (now - last_at).total_seconds() < after_seconds:
                continue
            if self._inactivity_triggered_for.get(key) == last_at:
                continue
            self._apply_stimulus(ExternalStimulus(
                stimulus_type="ignored",
                intensity=intensity,
                valence="negative",
                source="system",
            ))
            self._inactivity_triggered_for[key] = last_at

    def _evaluate_motivations(self, now: datetime) -> List[MotivationSignal]:
        intensities = self.state.intensities
        candidates: List[MotivationSignal] = []
        joy_strength = max(intensities.get("joy", 0.0), intensities.get("pleasure", 0.0))
        if joy_strength >= self.config.action_threshold:
            candidates.append(MotivationSignal("share", joy_strength, "情绪明亮，想把当下的开心分享给用户。", "主动发一条轻松分享或关心近况的消息。", self.state.dominant_emotion, intensities[self.state.dominant_emotion], created_at=now, target_key=self._last_active_target_key))
        if intensities.get("sadness", 0.0) >= self.config.action_threshold:
            candidates.append(MotivationSignal("confide", intensities["sadness"], "有些低落，想温柔地表达需要陪伴。", "主动发一条不施压的倾诉式问候。", self.state.dominant_emotion, intensities[self.state.dominant_emotion], created_at=now, target_key=self._last_active_target_key))
        if intensities.get("fatigue", 0.0) >= self.config.action_threshold:
            candidates.append(MotivationSignal("rest", intensities["fatigue"], "疲倦感较高，想放慢节奏并表达休息需求。", "主动发一条短消息，语气柔和克制。", self.state.dominant_emotion, intensities[self.state.dominant_emotion], created_at=now, target_key=self._last_active_target_key))
        if intensities.get("surprise", 0.0) >= self.config.action_threshold:
            candidates.append(MotivationSignal("express", intensities["surprise"], "被某件事触动，想立刻表达。", "主动发一条带有即时感的小感叹。", self.state.dominant_emotion, intensities[self.state.dominant_emotion], created_at=now, target_key=self._last_active_target_key))
        if intensities.get("anger", 0.0) >= self.config.action_threshold:
            candidates.append(MotivationSignal("express_boundary", intensities["anger"], "边界感被触动，想谨慎表达自己的感受。", "主动发一条温和但有边界的消息。", self.state.dominant_emotion, intensities[self.state.dominant_emotion], created_at=now, target_key=self._last_active_target_key))
        candidates.sort(key=lambda item: item.intensity, reverse=True)
        return candidates

    async def _dispatch_motivation(self, signals: List[MotivationSignal]):
        if not signals or not self.proactive_dispatcher:
            return
        signal = signals[0]
        if signal.intensity < self.config.action_threshold:
            return
        # 小脑侧动机冷却检查：防止高情绪持续期间频繁推送
        now = self._now()
        if self._last_motivation_dispatched_at:
            elapsed = (now - self._last_motivation_dispatched_at).total_seconds()
            if elapsed < self.config.motivation_cooldown_seconds:
                signal.status = "cooldown"
                return
        try:
            dispatched = await self.proactive_dispatcher(signal)
            signal.status = "dispatched" if dispatched else "pending"
            if dispatched:
                self._last_motivation_dispatched_at = now
        except Exception as exc:
            signal.status = "pending"
            logger.warning("推送小脑动机到主动调度器失败: %s", exc)

    def _append_history(self, now: datetime, signals: List[MotivationSignal]):
        self.history.append({
            "timestamp": now.isoformat(),
            "intensities": {key: round(clamp(value), 4) for key, value in self.state.intensities.items()},
            "dominant_emotion": self.state.dominant_emotion,
            "motivation_types": [signal.motivation_type for signal in signals],
        })

    def _dominant_emotion(self) -> str:
        return self._dominant_from_intensities(self.state.intensities, self.state.last_triggered_emotion)

    def _dominant_from_intensities(self, intensities: Dict[str, float], last_triggered: Optional[str]) -> str:
        max_value = max(intensities.get(emotion, 0.0) for emotion in EMOTIONS)
        winners = [emotion for emotion in EMOTIONS if abs(intensities.get(emotion, 0.0) - max_value) < 1e-9]
        if last_triggered in winners:
            return str(last_triggered)
        return winners[0] if winners else "joy"

    def _drain_stimuli(self) -> List[ExternalStimulus]:
        items: List[ExternalStimulus] = []
        while True:
            try:
                items.append(self._stimuli.get_nowait())
            except asyncio.QueueEmpty:
                break
        return items

    async def _broadcast(self):
        if not self._subscribers:
            return
        payload = self._stream_payload()
        current_loop = asyncio.get_event_loop()
        for queue, target_loop in list(self._subscribers):
            # 清理满队列中的旧消息
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                if target_loop is current_loop:
                    # 同一事件循环，直接投递
                    queue.put_nowait(payload)
                else:
                    # 跨线程：通过目标循环的 call_soon_threadsafe 安全投递
                    target_loop.call_soon_threadsafe(queue.put_nowait, payload)
            except (asyncio.QueueFull, RuntimeError):
                pass

    def _stream_payload(self) -> Dict[str, Any]:
        return {
            "event": "cerebellum.state",
            "payload": {
                "state": self.state.to_dict(),
                "motivations": self.motivations_snapshot(),
                "enabled": self.config.enabled,
                "running": self.running,
            },
        }

    def _should_persist(self, now: datetime) -> bool:
        if not self._last_persist_at:
            return True
        return (now - self._last_persist_at).total_seconds() >= self.config.persistence_interval

    def _now(self) -> datetime:
        tz_name = (self.config.circadian or {}).get("timezone") or "Asia/Shanghai"
        try:
            return datetime.now(ZoneInfo(str(tz_name)))
        except Exception:
            return datetime.now()

    def _time_in_range(self, now: datetime, start: Any, end: Any) -> bool:
        try:
            start_t = dt_time.fromisoformat(str(start or "00:00"))
            end_t = dt_time.fromisoformat(str(end or "23:59"))
        except ValueError:
            return False
        current = now.time()
        if start_t <= end_t:
            return start_t <= current <= end_t
        return current >= start_t or current <= end_t

    def _compose_target_key(self, channel: str, user_id: str, session_id: Optional[str] = None) -> str:
        return f"{channel}:{user_id}:{session_id or user_id}"

    def _safe_int(self, value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            logger.warning("小脑配置整数值无效，使用默认值: %s", default)
            parsed = default
        return max(minimum, min(maximum, parsed))

    def _safe_float(self, value: Any, default: float, minimum: float, maximum: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            logger.warning("小脑配置浮点值无效，使用默认值: %s", default)
            parsed = default
        return max(minimum, min(maximum, parsed))

    def _merge_dict(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(base)
        for key, value in (override or {}).items():
            if isinstance(result.get(key), dict) and isinstance(value, dict):
                result[key] = self._merge_dict(result[key], value)
            else:
                result[key] = value
        return result
