import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api.memory import get_memory_users, _ensure_session_access, _ensure_user_id_access
from backend.api.user_config import _user_runtime_ids


@pytest.mark.asyncio
async def test_get_memory_users_returns_only_current_user_memory_identities(monkeypatch):
    fake_user = SimpleNamespace(
        id=7,
        username="project_user",
        nickname="项目用户A",
        qq_user_id="123456",
        linyu_account="linyu_alice",
        linyu_user_id="550e8400-e29b-41d4-a716-446655440000",
    )

    monkeypatch.setattr(
        "backend.api.memory._get_authenticated_user",
        AsyncMock(return_value=fake_user),
    )

    result = await get_memory_users(token="valid-token")

    assert result["user_ids"] == ["7", "123456"]
    assert result["user_info"] == [
        {
            "user_id": "7",
            "display_name": "project_user | Web:7",
            "selector_key": "project_user | Web",
            "channel": "web",
            "default_session_id": "7",
            "remote_user_id": "",
            "project_user_id": "7",
        },
        {
            "user_id": "123456",
            "display_name": "project_user | QQ:123456",
            "selector_key": "project_user | QQ:123456",
            "channel": "qq",
            "default_session_id": "123456",
            "remote_user_id": "123456",
            "project_user_id": "7",
        },
        {
            "user_id": "7",
            "display_name": "project_user | Linyu:linyu_alice | 项目ID:7",
            "selector_key": "project_user | Linyu:linyu_alice",
            "channel": "linyu",
            "default_session_id": "linyu_private:550e8400-e29b-41d4-a716-446655440000",
            "remote_user_id": "550e8400-e29b-41d4-a716-446655440000",
            "project_user_id": "7",
        },
    ]


@pytest.mark.asyncio
async def test_get_memory_users_hides_linyu_uuid_when_account_is_not_displayable(monkeypatch):
    fake_user = SimpleNamespace(
        id=8,
        username="project_user",
        nickname="项目用户B",
        qq_user_id=None,
        linyu_account="550e8400-e29b-41d4-a716-446655440000",
        linyu_user_id="550e8400-e29b-41d4-a716-446655440000",
    )

    monkeypatch.setattr(
        "backend.api.memory._get_authenticated_user",
        AsyncMock(return_value=fake_user),
    )

    result = await get_memory_users(token="valid-token")

    assert result["user_ids"] == ["8"]
    assert result["user_info"][0]["display_name"] == "project_user | Web:8"
    assert result["user_info"][1]["display_name"] == "project_user | Linyu:已绑定账号 | 项目ID:8"
    assert result["user_info"][1]["default_session_id"] == "linyu_private:550e8400-e29b-41d4-a716-446655440000"
    assert result["user_info"][1]["project_user_id"] == "8"


@pytest.mark.asyncio
async def test_get_memory_users_includes_project_identity_without_external_binding(monkeypatch):
    fake_user = SimpleNamespace(
        id=9,
        username="plain_user",
        nickname="普通用户",
        qq_user_id=None,
        linyu_account=None,
        linyu_user_id=None,
    )

    monkeypatch.setattr(
        "backend.api.memory._get_authenticated_user",
        AsyncMock(return_value=fake_user),
    )

    result = await get_memory_users(token="valid-token")

    assert result["user_ids"] == ["9"]
    assert result["user_info"] == [
        {
            "user_id": "9",
            "display_name": "plain_user | Web:9",
            "selector_key": "plain_user | Web",
            "channel": "web",
            "default_session_id": "9",
            "remote_user_id": "",
            "project_user_id": "9",
        }
    ]


@pytest.mark.asyncio
async def test_get_memory_users_requires_valid_token(monkeypatch):
    monkeypatch.setattr(
        "backend.api.memory._get_authenticated_user",
        AsyncMock(side_effect=HTTPException(status_code=401, detail="无效的令牌")),
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_memory_users(token="bad-token")

    assert exc_info.value.status_code == 401


def test_memory_access_accepts_project_user_id_and_linyu_session():
    fake_user = SimpleNamespace(
        id=7,
        username="project_user",
        nickname="项目用户A",
        qq_user_id="123456",
        linyu_account="linyu_alice",
        linyu_user_id="550e8400-e29b-41d4-a716-446655440000",
    )

    assert _ensure_user_id_access(fake_user, "7") == "7"
    assert _ensure_user_id_access(fake_user, "550e8400-e29b-41d4-a716-446655440000") == "550e8400-e29b-41d4-a716-446655440000"
    assert _ensure_session_access(fake_user, "linyu_private:550e8400-e29b-41d4-a716-446655440000") == "linyu_private:550e8400-e29b-41d4-a716-446655440000"


def test_user_runtime_ids_include_project_and_bound_external_ids():
    fake_user = SimpleNamespace(
        id=7,
        qq_user_id="123456",
        linyu_user_id="550e8400-e29b-41d4-a716-446655440000",
    )

    assert _user_runtime_ids(fake_user) == {
        "7",
        "123456",
        "550e8400-e29b-41d4-a716-446655440000",
    }
