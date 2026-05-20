import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.adapters.linyu_manager import LinyuSessionManager


@pytest.mark.asyncio
async def test_collect_user_linyu_configs_filters_disabled_users(monkeypatch):
    manager = LinyuSessionManager(bot=object())

    users = [
        SimpleNamespace(id=1, linyu_user_id="uuid-1", linyu_account="user1"),
        SimpleNamespace(id=2, linyu_user_id="uuid-2", linyu_account="user2"),
    ]

    monkeypatch.setattr("backend.adapters.linyu_manager.user_manager.list_users", AsyncMock(return_value=users))
    monkeypatch.setattr(
        "backend.adapters.linyu_manager.user_manager.get_user_config_dict",
        AsyncMock(side_effect=[
            {
                "adapters": {
                    "linyu": {
                        "enabled": True,
                        "account": "ai_1",
                        "password": "pwd1",
                    }
                }
            },
            {
                "adapters": {
                    "linyu": {
                        "enabled": False,
                        "account": "ai_2",
                        "password": "pwd2",
                    }
                }
            },
        ]),
    )

    configs = await manager._collect_user_linyu_configs()

    assert "1" in configs
    assert "2" not in configs
    assert configs["1"]["target_user_id"] == "uuid-1"
    assert configs["1"]["target_user_account"] == "user1"


@pytest.mark.asyncio
async def test_collect_user_linyu_configs_inherits_global_server_and_prefers_bound_identity(monkeypatch):
    manager = LinyuSessionManager(bot=object())

    users = [
        SimpleNamespace(id=1, linyu_user_id="uuid-user-1", linyu_account="bound_user_1"),
    ]

    monkeypatch.setattr("backend.adapters.linyu_manager.user_manager.list_users", AsyncMock(return_value=users))
    monkeypatch.setattr(
        "backend.adapters.linyu_manager.user_manager.get_user_config_dict",
        AsyncMock(return_value={
            "adapters": {
                "linyu": {
                    "enabled": True,
                    "account": "ai_user_1",
                    "password": "pwd1",
                    "http_host": "should-not-be-used.local",
                    "target_user_id": "custom-target-id",
                    "target_user_account": "custom-target-account",
                    "auto_bind_first_user": True,
                }
            }
        }),
    )
    monkeypatch.setattr(
        "backend.adapters.linyu_manager.config._config",
        {
            "adapters": {
                "linyu": {
                    "enabled": True,
                    "http_host": "10.0.0.8",
                    "http_port": 9200,
                    "ws_host": "10.0.0.8",
                    "ws_port": 9100,
                }
            }
        },
        raising=False,
    )

    configs = await manager._collect_user_linyu_configs()

    assert configs["1"]["http_host"] == "10.0.0.8"
    assert configs["1"]["http_port"] == 9200
    assert configs["1"]["ws_host"] == "10.0.0.8"
    assert configs["1"]["ws_port"] == 9100
    assert configs["1"]["target_user_id"] == "uuid-user-1"
    assert configs["1"]["target_user_account"] == "bound_user_1"
    assert configs["1"]["auto_bind_first_user"] is True
