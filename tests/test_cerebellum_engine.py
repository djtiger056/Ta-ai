import asyncio
import os
import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.core.cerebellum.engine import CerebellumEngine
from backend.core.cerebellum.models import ExternalStimulus


@pytest.mark.asyncio
async def test_positive_stimulus_increases_joy_and_pleasure():
    engine = CerebellumEngine()
    engine.config.enabled = True
    target_key = engine._compose_target_key("web", "u1", "u1")
    state = engine._ensure_state(target_key, engine._now())
    before_joy = state.intensities["joy"]
    before_pleasure = state.intensities["pleasure"]

    await engine.submit_stimulus(ExternalStimulus(
        stimulus_type="user_message",
        intensity=0.9,
        valence="positive",
        source="user",
        channel="web",
        user_id="u1",
        session_id="u1",
        message="今天很开心",
    ))
    await engine.tick()

    state = engine.states[target_key]
    assert state.intensities["joy"] > before_joy
    assert state.intensities["pleasure"] > before_pleasure
    assert state.dominant_emotion in state.intensities


def test_tie_break_prefers_last_triggered_emotion():
    engine = CerebellumEngine()
    state = engine._initial_state(engine._now(), {emotion: 0.1 for emotion in ("joy", "anger", "sadness", "pleasure", "surprise", "fatigue")})
    state.intensities["joy"] = 0.8
    state.intensities["sadness"] = 0.8
    state.intensities["pleasure"] = 0.2
    state.last_triggered_emotion = "sadness"

    assert engine._dominant_emotion(state) == "sadness"


@pytest.mark.asyncio
async def test_persistence_round_trip(tmp_path: Path):
    engine = CerebellumEngine()
    engine.config.enabled = True
    engine.config.state_file = str(tmp_path / "cerebellum_state.json")
    target_key = engine._compose_target_key("web", "u1", "u1")
    state = engine._ensure_state(target_key, engine._now())
    state.intensities["surprise"] = 0.77
    engine._last_active_target_key = target_key
    await engine.persist_state()

    restored = CerebellumEngine()
    restored.config.state_file = str(tmp_path / "cerebellum_state.json")
    restored.state = restored._load_or_initialize_state()

    assert restored.states[target_key].intensities["surprise"] > 0.0
    assert Path(restored.config.state_file).exists()


@pytest.mark.asyncio
async def test_high_intensity_generates_motivation_signal():
    engine = CerebellumEngine()
    engine.config.enabled = True
    target_key = engine._compose_target_key("web", "u1", "u1")
    state = engine._ensure_state(target_key, engine._now())
    engine._last_user_message_at[target_key] = engine._now() - timedelta(minutes=15)
    state.intensities["joy"] = 0.91
    state.intensities["pleasure"] = 0.83
    state.dominant_emotion = "joy"
    signals = engine._evaluate_motivations(target_key, state, engine._now())

    assert signals
    assert signals[0].motivation_type == "share"


@pytest.mark.asyncio
async def test_emotion_state_is_isolated_per_user():
    engine = CerebellumEngine()
    engine.config.enabled = True
    engine.config.circadian["active"]["micro_wave_probability"] = 0.0
    engine.config.autonomous_drift["enabled"] = False
    engine.config.inactivity_stimulus["enabled"] = False
    engine.states = {}
    engine.history = {}
    engine.active_motivations = {}
    engine._last_user_message_at = {}
    engine._last_motivation_dispatched_at = {}
    engine._cooldown_blocked_until_user_message = set()
    engine.state = engine._select_snapshot_state()

    await engine.submit_stimulus(ExternalStimulus(
        stimulus_type="user_message",
        intensity=1.0,
        valence="positive",
        source="user",
        channel="web",
        user_id="u1",
        session_id="u1",
        message="好开心",
    ))
    await engine.submit_stimulus(ExternalStimulus(
        stimulus_type="user_message",
        intensity=1.0,
        valence="negative",
        source="user",
        channel="web",
        user_id="u2",
        session_id="u2",
        message="好难过",
    ))
    await engine.tick()

    key1 = engine._compose_target_key("web", "u1", "u1")
    key2 = engine._compose_target_key("web", "u2", "u2")
    state1 = engine.states[key1]
    state2 = engine.states[key2]

    assert state1.intensities["joy"] > state1.baselines["joy"]
    assert state2.intensities["sadness"] > state2.baselines["sadness"]
    assert state1.intensities["sadness"] <= state1.baselines["sadness"] + 1e-6
    assert state2.intensities["joy"] <= state2.baselines["joy"] + 1e-6


@pytest.mark.asyncio
async def test_dispatch_requires_user_reengagement_to_avoid_hour_long_retrigger():
    dispatched: list[tuple[str | None, str]] = []

    async def dispatcher(signal):
        dispatched.append((signal.target_key, signal.motivation_type))
        return True

    engine = CerebellumEngine(proactive_dispatcher=dispatcher)
    engine.config.enabled = True
    engine.config.action_threshold = 0.52
    engine.config.motivation_cooldown_seconds = 60
    engine.config.require_user_reengagement_after_dispatch = True
    engine.config.circadian["active"]["micro_wave_probability"] = 0.0
    engine.config.autonomous_drift["enabled"] = False
    engine.config.inactivity_stimulus["enabled"] = False
    engine.states = {}
    engine.history = {}
    engine.active_motivations = {}
    engine._last_user_message_at = {}
    engine._last_motivation_dispatched_at = {}
    engine._cooldown_blocked_until_user_message = set()
    engine.state = engine._select_snapshot_state()

    target_key = engine._compose_target_key("web", "u1", "u1")
    state = engine._ensure_state(target_key, engine._now())
    state.intensities["joy"] = 0.95
    state.intensities["pleasure"] = 0.9
    state.dominant_emotion = "joy"
    engine._last_user_message_at[target_key] = engine._now() - timedelta(hours=4)

    for _ in range(3):
        await engine.tick()
        state.last_updated_at = state.last_updated_at - timedelta(minutes=31)

    assert len(dispatched) == 1

    await engine.submit_message_stimulus("我回来了", "web", "u1", "u1")
    state.intensities["joy"] = 0.95
    state.intensities["pleasure"] = 0.9
    engine._last_user_message_at[target_key] = engine._now() - timedelta(hours=4)
    engine._last_motivation_dispatched_at[target_key] = engine._now() - timedelta(minutes=31)
    await engine.tick()
    state.last_updated_at = state.last_updated_at - timedelta(minutes=31)
    await engine.tick()

    assert len(dispatched) >= 2
