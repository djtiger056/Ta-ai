import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.adapters.linyu import LinyuAdapter


@pytest.mark.asyncio
async def test_linyu_stream_filters_tts_tags_and_preserves_content():
    adapter = LinyuAdapter.__new__(LinyuAdapter)
    sent_messages = []

    class FakeBot:
        def register_session_channel(self, session_id, channel):
            return None

        async def chat_stream(self, prompt, user_id="default", session_id=None):
            for chunk in ("[TTS]你好", "呀[/TTS]。", "普通文本。"):
                yield chunk

    adapter.bot = FakeBot()
    adapter.segment_enabled = False
    adapter.delay_range = [0.0, 0.0]
    adapter._send_text_once = AsyncMock(
        side_effect=lambda target_id, message, is_group=False: sent_messages.append(message)
    )

    response = await adapter._stream_reply_by_sentence("user-1", "hello", session_id="session-1")

    assert response == "你好呀。普通文本。"
    assert sent_messages == ["你好呀。", "普通文本。"]


@pytest.mark.asyncio
async def test_linyu_resolve_tts_audio_prefers_forced_tts():
    adapter = LinyuAdapter.__new__(LinyuAdapter)
    adapter.bot = type(
        "FakeBot",
        (),
        {
            "get_last_tts_forced": lambda self: {"text": "请用语音读这句"},
            "synthesize_speech_forced": AsyncMock(return_value=b"forced-audio"),
            "synthesize_speech": AsyncMock(return_value=b"normal-audio"),
        },
    )()

    audio = await adapter._resolve_tts_audio("原始回复", "user-1")

    assert audio == b"forced-audio"
    adapter.bot.synthesize_speech_forced.assert_awaited_once_with("请用语音读这句", user_id="user-1")
    adapter.bot.synthesize_speech.assert_not_awaited()


@pytest.mark.asyncio
async def test_linyu_voice_only_mode_sends_voice_without_duplicate_text():
    adapter = LinyuAdapter.__new__(LinyuAdapter)
    adapter.bot = type(
        "FakeBot",
        (),
        {
            "strip_tts_text": lambda self, text, user_id="default": "",
            "get_last_tts_text": lambda self, user_id="default": "要播报的文本",
        },
    )()
    adapter._resolve_tts_audio = AsyncMock(return_value=b"voice-audio")
    adapter.send_voice_message = AsyncMock()
    adapter.send_private_message = AsyncMock()

    await adapter._deliver_tts_and_text_response("user-1", "这是一段回复", voice_only=True)

    adapter.send_voice_message.assert_awaited_once_with("user-1", b"voice-audio", speech_text="要播报的文本")
    adapter.send_private_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_linyu_voice_only_mode_falls_back_to_text_when_tts_missing():
    adapter = LinyuAdapter.__new__(LinyuAdapter)
    adapter.bot = type(
        "FakeBot",
        (),
        {
            "strip_tts_text": lambda self, text, user_id="default": "",
            "get_last_tts_text": lambda self, user_id="default": None,
        },
    )()
    adapter._resolve_tts_audio = AsyncMock(return_value=None)
    adapter.send_voice_message = AsyncMock()
    adapter.send_private_message = AsyncMock()

    await adapter._deliver_tts_and_text_response("user-1", "这是一段回复", voice_only=True)

    adapter.send_voice_message.assert_not_awaited()
    adapter.send_private_message.assert_awaited_once_with("user-1", "这是一段回复")


@pytest.mark.asyncio
async def test_linyu_text_reply_uses_owner_user_config_for_voice_only():
    adapter = LinyuAdapter.__new__(LinyuAdapter)
    adapter.owner_user_id = "owner-42"
    adapter.bot = type(
        "FakeBot",
        (),
        {
            "is_voice_only_mode": lambda self, user_id="default": user_id == "owner-42",
            "get_last_generated_image": lambda self: None,
        },
    )()
    adapter._stream_reply_by_sentence = AsyncMock(return_value="回复文本")
    adapter._deliver_tts_and_text_response = AsyncMock()
    adapter._maybe_send_emote = AsyncMock()

    await adapter._do_text_reply("linyu-peer-9", "你好")

    adapter._stream_reply_by_sentence.assert_awaited_once_with(
        user_id="linyu-peer-9",
        prompt="你好",
        bot_user_id="owner-42",
        session_id="linyu_private:linyu-peer-9",
        emit_text=False,
    )
    adapter._deliver_tts_and_text_response.assert_awaited_once_with(
        user_id="linyu-peer-9",
        response="回复文本",
        voice_only=True,
        bot_user_id="owner-42",
    )
