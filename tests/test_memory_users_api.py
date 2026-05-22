import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api.memory import get_memory_users


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

    assert result["user_ids"] == [
        "123456",
        "550e8400-e29b-41d4-a716-446655440000",
    ]
    assert result["user_info"] == [
        {
            "user_id": "123456",
            "display_name": "project_user | QQ:123456",
            "selector_key": "project_user | QQ:123456",
            "channel": "qq",
        },
        {
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "display_name": "project_user | Linyu:linyu_alice",
            "selector_key": "project_user | Linyu:linyu_alice",
            "channel": "linyu",
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

    assert result["user_ids"] == ["550e8400-e29b-41d4-a716-446655440000"]
    assert result["user_info"][0]["display_name"] == "project_user | Linyu:已绑定账号"


@pytest.mark.asyncio
async def test_get_memory_users_requires_valid_token(monkeypatch):
    monkeypatch.setattr(
        "backend.api.memory._get_authenticated_user",
        AsyncMock(side_effect=HTTPException(status_code=401, detail="无效的令牌")),
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_memory_users(token="bad-token")

    assert exc_info.value.status_code == 401
