import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api import user_auth as user_auth_api
from backend.adapters.linyu import LinyuAdapter


@pytest.mark.asyncio
async def test_bind_linyu_rejects_unknown_account(monkeypatch):
    monkeypatch.setattr(
        user_auth_api.auth_manager,
        "get_user_from_token",
        lambda token: {"user_id": 1},
    )
    monkeypatch.setattr(
        user_auth_api.user_manager,
        "get_user_by_id",
        AsyncMock(return_value=SimpleNamespace(id=1)),
    )
    monkeypatch.setattr(
        user_auth_api,
        "_resolve_linyu_user_id",
        AsyncMock(return_value=None),
    )

    with pytest.raises(HTTPException) as exc_info:
        await user_auth_api.bind_linyu_account(token="token", linyu_user_id="ghost-account")

    assert exc_info.value.status_code == 400
    assert "未能解析" in exc_info.value.detail


@pytest.mark.asyncio
async def test_bind_linyu_resolves_account_before_update(monkeypatch):
    update_user = AsyncMock(return_value=True)

    monkeypatch.setattr(
        user_auth_api.auth_manager,
        "get_user_from_token",
        lambda token: {"user_id": 7},
    )
    monkeypatch.setattr(
        user_auth_api.user_manager,
        "get_user_by_id",
        AsyncMock(return_value=SimpleNamespace(id=7)),
    )
    monkeypatch.setattr(
        user_auth_api,
        "_resolve_linyu_user_id",
        AsyncMock(return_value="11111111-2222-3333-4444-555555555555"),
    )
    monkeypatch.setattr(
        user_auth_api.user_manager,
        "get_user_by_linyu_id",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        user_auth_api.user_manager,
        "update_user",
        update_user,
    )

    result = await user_auth_api.bind_linyu_account(token="token", linyu_user_id="alice")

    assert result["linyu_user_id"] == "11111111-2222-3333-4444-555555555555"
    assert result["linyu_account"] == "alice"
    update_user.assert_awaited_once_with(
        user_id=7,
        linyu_user_id="11111111-2222-3333-4444-555555555555",
        linyu_account="alice",
    )


@pytest.mark.asyncio
async def test_bound_user_can_bypass_auto_bound_target_lock(monkeypatch):
    adapter = LinyuAdapter.__new__(LinyuAdapter)
    adapter.user_id = None
    adapter.target_user_id = "old-target"
    adapter.target_user_account = ""
    adapter.auto_bind_first_user = True
    adapter._has_explicit_target = False
    adapter.access_control_enabled = True
    adapter.access_control_mode = "whitelist"
    adapter.access_whitelist = set()
    adapter.access_deny_message = "denied"

    adapter._try_resolve_linyu_binding = AsyncMock()
    adapter._get_bound_linyu_user = AsyncMock(return_value=SimpleNamespace(id=99))
    adapter._is_message_processed = lambda msg_id: False
    adapter._deliver_follow_up_message = lambda conversation_key, message_text: False
    adapter._get_conversation_key = lambda target_id, is_group=False, user_id=None: f"linyu_user_{target_id}"
    adapter._handle_text_message = AsyncMock()
    adapter.send_private_message = AsyncMock()
    adapter._mark_read = AsyncMock()

    def fake_create_task(coro):
        coro.close()
        return None

    monkeypatch.setattr("backend.adapters.linyu.asyncio.create_task", fake_create_task)

    await adapter._handle_private_message(
        {
            "fromId": "new-user",
            "id": "msg-1",
            "msgContent": {
                "type": "text",
                "content": "hello",
            },
        }
    )

    assert "new-user" in adapter.access_whitelist
    adapter._handle_text_message.assert_awaited_once_with("new-user", "hello")


@pytest.mark.asyncio
async def test_global_linyu_session_maps_bound_sender_to_project_user(monkeypatch):
    adapter = LinyuAdapter.__new__(LinyuAdapter)
    adapter.owner_user_id = None
    adapter.user_id = "ai-user"
    adapter.target_user_id = ""
    adapter.target_user_account = ""
    adapter.auto_bind_first_user = False
    adapter._has_explicit_target = False
    adapter.access_control_enabled = True
    adapter.access_control_mode = "whitelist"
    adapter.access_whitelist = set()
    adapter.access_deny_message = "denied"
    adapter._bound_bot_user_ids = {}

    adapter._try_resolve_linyu_binding = AsyncMock()
    adapter._get_bound_linyu_user = AsyncMock(return_value=SimpleNamespace(id=18))
    adapter._is_message_processed = lambda msg_id: False
    adapter._deliver_follow_up_message = lambda conversation_key, message_text: False
    adapter._get_conversation_key = lambda target_id, is_group=False, user_id=None: f"linyu_user_{target_id}"
    adapter._handle_text_message = AsyncMock()
    adapter.send_private_message = AsyncMock()
    adapter._mark_read = AsyncMock()

    def fake_create_task(coro):
        coro.close()
        return None

    monkeypatch.setattr("backend.adapters.linyu.asyncio.create_task", fake_create_task)

    await adapter._handle_private_message(
        {
            "fromId": "d8ba2701-5c71-43c1-809c-d1bbfc57b3f3",
            "id": "msg-2",
            "msgContent": {
                "type": "text",
                "content": "hello",
            },
        }
    )

    assert adapter._get_bot_user_id("d8ba2701-5c71-43c1-809c-d1bbfc57b3f3") == "18"
    assert "d8ba2701-5c71-43c1-809c-d1bbfc57b3f3" in adapter.access_whitelist
    adapter._handle_text_message.assert_awaited_once_with(
        "d8ba2701-5c71-43c1-809c-d1bbfc57b3f3",
        "hello",
    )


@pytest.mark.asyncio
async def test_global_owner_id_does_not_hide_bound_project_user(monkeypatch):
    adapter = LinyuAdapter.__new__(LinyuAdapter)
    adapter.owner_user_id = "global"
    adapter.user_id = "ai-user"
    adapter.target_user_id = ""
    adapter.target_user_account = ""
    adapter.auto_bind_first_user = False
    adapter._has_explicit_target = False
    adapter.access_control_enabled = True
    adapter.access_control_mode = "whitelist"
    adapter.access_whitelist = set()
    adapter.access_deny_message = "denied"
    adapter._bound_bot_user_ids = {}

    adapter._try_resolve_linyu_binding = AsyncMock()
    adapter._get_bound_linyu_user = AsyncMock(return_value=SimpleNamespace(id=18))
    adapter._is_message_processed = lambda msg_id: False
    adapter._deliver_follow_up_message = lambda conversation_key, message_text: False
    adapter._get_conversation_key = lambda target_id, is_group=False, user_id=None: f"linyu_user_{target_id}"
    adapter._handle_text_message = AsyncMock()
    adapter.send_private_message = AsyncMock()
    adapter._mark_read = AsyncMock()

    def fake_create_task(coro):
        coro.close()
        return None

    monkeypatch.setattr("backend.adapters.linyu.asyncio.create_task", fake_create_task)

    await adapter._handle_private_message(
        {
            "fromId": "d8ba2701-5c71-43c1-809c-d1bbfc57b3f3",
            "id": "msg-3",
            "msgContent": {
                "type": "text",
                "content": "hello",
            },
        }
    )

    assert adapter._get_bot_user_id("d8ba2701-5c71-43c1-809c-d1bbfc57b3f3") == "18"
    assert "d8ba2701-5c71-43c1-809c-d1bbfc57b3f3" in adapter.access_whitelist
    adapter._handle_text_message.assert_awaited_once_with(
        "d8ba2701-5c71-43c1-809c-d1bbfc57b3f3",
        "hello",
    )
