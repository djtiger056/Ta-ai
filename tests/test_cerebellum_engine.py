import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.core.cerebellum.engine import CerebellumEngine
from backend.core.cerebellum.models import ExternalStimulus


@pytest.mark.asyncio
async def test_positive_stimulus_increases_joy_and_pleasure():
    engine = CerebellumEngine()
    engine.config.enabled = True
    before_joy = engine.state.intensities["joy"]
    before_pleasure = engine.state.intensities["pleasure"]

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

    assert engine.state.intensities["joy"] > before_joy
    assert engine.state.intensities["pleasure"] > before_pleasure
    assert engine.state.dominant_emotion in engine.state.intensities


def test_tie_break_prefers_last_triggered_emotion():
    engine = CerebellumEngine()
    engine.state.intensities["joy"] = 0.8
    engine.state.intensities["sadness"] = 0.8
    engine.state.last_triggered_emotion = "sadness"

    assert engine._dominant_emotion() == "sadness"


@pytest.mark.asyncio
async def test_persistence_round_trip(tmp_path: Path):
    engine = CerebellumEngine()
    engine.config.enabled = True
    engine.config.state_file = str(tmp_path / "cerebellum_state.json")
    engine.state.intensities["surprise"] = 0.77
    await engine.persist_state()

    restored = CerebellumEngine()
    restored.config.state_file = str(tmp_path / "cerebellum_state.json")
    restored.state = restored._load_or_initialize_state()

    assert restored.state.intensities["surprise"] > 0.0
    assert Path(restored.config.state_file).exists()


@pytest.mark.asyncio
async def test_high_intensity_generates_motivation_signal():
    engine = CerebellumEngine()
    engine.config.enabled = True
    engine.state.intensities["joy"] = 0.91
    engine.state.intensities["pleasure"] = 0.83
    signals = engine._evaluate_motivations(engine._now())

    assert signals
    assert signals[0].motivation_type == "share"
