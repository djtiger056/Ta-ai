import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api.memory import get_memory_users


@pytest.mark.asyncio
async def test_get_memory_users_returns_selector_display(monkeypatch):
    fake_manager = SimpleNamespace(
        get_all_user_ids=AsyncMock(return_value=["10001"])
    )
    fake_user = SimpleNamespace(
        username="project_user",
        nickname="项目用户A",
        qq_user_id="123456",
        linyu_account="linyu_alice",
        linyu_user_id="uuid-alice",
    )

    monkeypatch.setattr("backend.api.memory.ensure_memory_manager_initialized", AsyncMock(return_value=fake_manager))
    monkeypatch.setattr("backend.user.user_manager.get_user_by_qq_id", AsyncMock(return_value=fake_user))
    monkeypatch.setattr("backend.user.user_manager.get_user_by_id", AsyncMock(return_value=None))
    monkeypatch.setattr("backend.user.user_manager.get_user_by_username", AsyncMock(return_value=None))

    result = await get_memory_users()

    assert result["user_ids"] == ["10001"]
    assert result["user_info"][0]["user_id"] == "10001"
    assert result["user_info"][0]["display_name"] == "项目用户A | QQ:123456 | Linyu:linyu_alice"
    assert result["user_info"][0]["selector_key"] == "项目用户A | QQ:123456 | Linyu:linyu_alice"
