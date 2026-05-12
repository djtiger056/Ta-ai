import asyncio
import os
import sys
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.core.proactive import ProactiveChatScheduler
from backend.core.cerebellum.models import MotivationSignal


class DummyBot:
    def __init__(self):
        self.instructions: list[str] = []
        self.memory_manager = None
        self.image_gen_manager = None

    async def generate_proactive_reply(self, instruction: str, user_id: str = "default") -> str:
        self.instructions.append(instruction)
        return "主动消息测试"


def build_scheduler() -> ProactiveChatScheduler:
    scheduler = ProactiveChatScheduler(DummyBot())
    scheduler._config = {
        "enabled": True,
        "check_interval_seconds": 60,
        "targets": [{
            "channel": "web",
            "user_id": "web_user",
            "session_id": "web_user",
            "display_name": "测试用户",
        }],
        "behavior_rules": {
            "enabled": True,
            "global_cooldown_seconds": 0,
            "inactive_greeting": {
                "enabled": True,
                "after_seconds": 60,
                "min_user_messages": 1,
            },
            "conversation_follow_up": {
                "enabled": True,
                "after_seconds": 30,
                "min_user_messages": 1,
            },
        },
    }
    scheduler.register_sender("web", scheduler.enqueue_web_message)
    return scheduler


def test_follow_up_reason_detects_open_question():
    scheduler = build_scheduler()
    reason = scheduler._should_schedule_conversation_follow_up(
        "我明天要去面试，有点紧张",
        "那你准备得怎么样了？记得回来和我说",
    )
    assert reason == "assistant_question"


def test_follow_up_reason_ignores_explicit_conversation_end():
    scheduler = build_scheduler()
    reason = scheduler._should_schedule_conversation_follow_up(
        "晚安，明天再聊",
        "晚安宝宝，早点睡",
    )
    assert reason is None


@pytest.mark.asyncio
async def test_inactive_greeting_triggers_after_user_silence():
    scheduler = build_scheduler()
    scheduler.record_user_activity("web", "web_user", "web_user", "今天项目改得我有点累")
    scheduler.record_assistant_activity("web", "web_user", "web_user", "辛苦啦，忙完记得歇会", allow_follow_up=False)

    state = scheduler.target_state["web:web_user:web_user"]
    activity = scheduler._ensure_activity_state(state)
    activity["last_user_message_at"] = scheduler._now() - timedelta(seconds=120)
    activity["last_assistant_message_at"] = scheduler._now() - timedelta(seconds=110)

    sent = await scheduler._check_behavior_rules(
        scheduler._config["targets"][0],
        state,
        scheduler._now(),
    )

    assert sent is True
    messages = scheduler.poll_pending_messages("web", "web_user", "web_user")
    assert len(messages) == 1
    assert messages[0]["content"] == "主动消息测试"
    assert activity["inactivity_triggered_for_user_at"] is not None


@pytest.mark.asyncio
async def test_conversation_follow_up_triggers_when_topic_is_open():
    scheduler = build_scheduler()
    scheduler.record_user_activity("web", "web_user", "web_user", "我明天要去面试，有点紧张")
    scheduler.record_assistant_activity("web", "web_user", "web_user", "那你准备得怎么样了？记得回来和我说")

    state = scheduler.target_state["web:web_user:web_user"]
    activity = scheduler._ensure_activity_state(state)
    activity["pending_follow_up_due_at"] = scheduler._now() - timedelta(seconds=5)
    activity["last_user_message_at"] = scheduler._now() - timedelta(seconds=40)
    activity["last_assistant_message_at"] = scheduler._now() - timedelta(seconds=35)

    sent = await scheduler._check_behavior_rules(
        scheduler._config["targets"][0],
        state,
        scheduler._now(),
    )

    assert sent is True
    messages = scheduler.poll_pending_messages("web", "web_user", "web_user")
    assert len(messages) == 1
    assert messages[0]["content"] == "主动消息测试"
    assert activity["pending_follow_up_due_at"] is None
    assert activity["last_follow_up_sent_at"] is not None


def test_enqueue_web_message_preserves_text_and_image():
    scheduler = build_scheduler()

    async def _run():
        await scheduler.enqueue_web_message(
            {"channel": "web", "user_id": "web_user", "session_id": "web_user"},
            {"text": "你好呀", "image": b"fake-image"},
        )

    asyncio.run(_run())

    messages = scheduler.poll_pending_messages("web", "web_user", "web_user")
    assert len(messages) == 1
    assert messages[0]["content"] == "你好呀"
    assert messages[0]["image_base64"]


@pytest.mark.asyncio
async def test_motivation_signal_triggers_proactive_message():
    scheduler = build_scheduler()
    signal = MotivationSignal(
        motivation_type="share",
        intensity=0.88,
        description="想分享开心的事",
        suggested_action="主动找用户聊天",
        dominant_emotion="joy",
        dominant_emotion_intensity=0.88,
    )

    sent = await scheduler.handle_motivation_signal(signal)

    assert sent is True
    messages = scheduler.poll_pending_messages("web", "web_user", "web_user")
    assert len(messages) == 1
    assert messages[0]["content"] == "主动消息测试"
    assert "当前小脑动机" in scheduler.bot.instructions[-1]
