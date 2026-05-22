import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.memory.reminder_detector import ReminderDetector


class DummyProvider:
    def __init__(self, response='{"is_reminder": true, "content": "误判", "time_expression": "今晚"}'):
        self.response = response
        self.calls = 0

    async def chat(self, messages, **kwargs):
        self.calls += 1
        return self.response


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    [
        "今晚吃什么好呢",
        "我记得你之前说过这个",
        "你还记得上次我们聊的论文吗",
        "等会我可能要出去一下",
        "明天下午我们继续聊这个方向",
        "记得吗，我之前说过这个实验",
    ],
)
async def test_normal_chat_does_not_create_reminder_or_call_llm(message):
    provider = DummyProvider()
    detector = ReminderDetector(provider, enable_llm_fallback=True)

    result = await detector.detect_reminder_intent(message)

    assert result is None
    assert provider.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "content"),
    [
        ("10分钟后提醒我喝水", "喝水"),
        ("明天中午提醒我去取快递", "去取快递"),
        ("提醒我起床", "起床"),
        ("晚上8点提醒我开会", "开会"),
        ("别忘了明天下午提交报告", "提交报告"),
    ],
)
async def test_explicit_reminders_are_detected(message, content):
    provider = DummyProvider()
    detector = ReminderDetector(provider, enable_llm_fallback=False)

    result = await detector.detect_reminder_intent(message)

    assert result is not None
    assert result["is_reminder"] is True
    assert result["content"] == content
    assert result["trigger_time"] is not None
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_llm_fallback_is_disabled_by_default():
    provider = DummyProvider()
    detector = ReminderDetector(provider)

    result = await detector.detect_reminder_intent("提醒一下")

    assert result is None
    assert provider.calls == 0
