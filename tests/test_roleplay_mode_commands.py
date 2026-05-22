from types import SimpleNamespace

import pytest

from backend.core.bot import Bot


class DummyProvider:
    def __init__(self):
        self.calls = []

    async def chat(self, messages):
        self.calls.append(messages)
        return "本次情景里，用户和 AI 完成了一段重要互动。"


class DummyMemoryManager:
    def __init__(self, messages=None, summaries=None, message_count=0):
        self.config = SimpleNamespace(short_term_max_rounds=50, mid_term_context_count=3)
        self.async_session = None
        self.messages = messages or []
        self.summaries = summaries or []
        self.message_count = message_count
        self.force_summarized = False
        self.written = []

    async def _get_session_state(self, session_id, user_id):
        return {"message_count": self.message_count, "round_count": 0}

    async def summarize_pending_now(self, user_id, session_id, force=True):
        self.force_summarized = force
        return {"ok": True, "processed": False}

    async def get_mid_term_summaries(self, user_id, session_id=None, limit=100):
        return self.summaries

    async def add_short_term_memory(self, user_id, session_id, message):
        self.written.append((user_id, session_id, message))
        return True


def make_bot(preferences=None):
    bot = object.__new__(Bot)
    bot._last_mode_command = None
    bot._last_tts_forced_text = None
    bot._last_generated_image = None
    bot._roleplay_memory_managers = {}
    bot._roleplay_memory_signatures = {}
    bot.session_histories = {}
    bot._preferences = preferences if preferences is not None else {"chat_mode": "companion"}
    bot._provider = DummyProvider()
    bot._roleplay_manager = DummyMemoryManager(message_count=4)
    bot.memory_manager = DummyMemoryManager()
    bot.logger = SimpleNamespace(warning=lambda *args, **kwargs: None)

    async def get_prefs(user_id):
        return dict(bot._preferences)

    async def update_prefs(user_id, prefs):
        bot._preferences = dict(prefs)
        return True

    async def get_roleplay_manager(user_id):
        return bot._roleplay_manager

    async def ensure_memory():
        return True

    bot._get_user_preferences_for_update = get_prefs
    bot._update_user_preferences = update_prefs
    bot._get_roleplay_memory_manager = get_roleplay_manager
    bot._get_user_llm_provider = lambda user_id: bot._provider
    bot._ensure_memory_manager_initialized = ensure_memory
    bot._get_session_history = lambda session_id, user_id="default": bot.session_histories.setdefault(session_id, [])
    bot._trim_conversation_history = lambda session_id, user_id="default": None
    bot.invalidate_user_cache = lambda user_id: None
    return bot


@pytest.mark.asyncio
async def test_slash_roleplay_updates_mode_without_llm_call():
    bot = make_bot()

    response = await bot._handle_mode_switch_command("  /情景  ", "u1", "s1")

    assert response == "已切换到情景演绎模式。"
    assert bot._preferences["chat_mode"] == "roleplay"
    assert bot._preferences["roleplay_active_episodes"]["s1"]["start_message_index"] == 4
    assert bot._provider.calls == []
    assert bot.pop_last_mode_command("u1", "s1")["mode"] == "roleplay"


@pytest.mark.asyncio
async def test_slash_companion_summarizes_episode_into_companion_short_term():
    bot = make_bot(
        {
            "chat_mode": "roleplay",
            "roleplay_active_episodes": {"s1": {"started_at": "now", "start_message_index": 1}},
        }
    )
    bot._roleplay_manager.messages = [
        {
            "message": {"role": "user", "content": "我们在雨夜重逢。"},
            "metadata": {"message_index": 2},
        },
        {
            "message": {"role": "assistant", "content": "我递给你一把伞。"},
            "metadata": {"message_index": 3},
        },
    ]

    async def raw_since(memory_manager, user_id, session_id, start_index, limit=500):
        return [m for m in memory_manager.messages if m["metadata"]["message_index"] > start_index]

    bot._get_roleplay_raw_memories_since = raw_since

    response = await bot._handle_mode_switch_command("/伴侣", "u1", "s1")

    assert response == "已切换到 AI 伴侣模式，并整理了本次情景演绎记忆。"
    assert bot._preferences["chat_mode"] == "companion"
    assert "s1" not in bot._preferences["roleplay_active_episodes"]
    assert bot._roleplay_manager.force_summarized is True
    assert bot.memory_manager.written
    written_message = bot.memory_manager.written[0][2]
    assert written_message.role == "assistant"
    assert written_message.content.startswith("【情景演绎结束摘要】")


@pytest.mark.asyncio
async def test_slash_companion_without_content_switches_without_empty_memory():
    bot = make_bot({"chat_mode": "roleplay", "roleplay_active_episodes": {}})

    response = await bot._handle_mode_switch_command("/伴侣", "u1", "s1")

    assert response == "已切换到 AI 伴侣模式。"
    assert bot._preferences["chat_mode"] == "companion"
    assert bot.memory_manager.written == []


@pytest.mark.asyncio
async def test_non_exact_command_is_ignored():
    bot = make_bot()

    response = await bot._handle_mode_switch_command("/情景 开始", "u1", "s1")

    assert response is None
    assert bot._preferences["chat_mode"] == "companion"


@pytest.mark.asyncio
async def test_chat_stream_mode_command_yields_confirmation_only():
    bot = make_bot()

    async def get_user_config(user_id):
        return {}

    bot._get_user_config = get_user_config
    bot._refresh_provider = lambda *args, **kwargs: None
    bot._user_cache = SimpleNamespace(get_chat_mode=lambda user_id: "companion")

    chunks = []
    async for chunk in Bot.chat_stream(bot, " /情景 ", user_id="u1", session_id="s1"):
        chunks.append(chunk)

    assert chunks == ["已切换到情景演绎模式。"]
    assert bot._preferences["chat_mode"] == "roleplay"
    assert bot._provider.calls == []
