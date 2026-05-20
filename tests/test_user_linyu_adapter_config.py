import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.user.data_manager import UserDataManager
from backend.user.manager import UserManager


@pytest.mark.asyncio
async def test_user_config_can_persist_adapters_section(tmp_path):
    db_path = tmp_path / "users.db"
    user_data_path = tmp_path / "user_data"

    manager = UserManager(db_url=f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await manager.init_db()

    from backend.user import manager as user_manager_module

    original_data_manager = user_manager_module.user_data_manager
    user_manager_module.user_data_manager = UserDataManager(base_path=str(user_data_path))
    try:
        user = await manager.create_user(username="tester01", password="secret123", nickname="tester")
        assert user is not None

        ok = await manager.update_user_config(
            user.id,
            {
                "adapters": {
                    "linyu": {
                        "enabled": True,
                        "account": "ai_tester01",
                        "password": "pwd001",
                        "target_user_account": "user_tester01",
                    }
                }
            },
        )
        assert ok is True

        cfg = await manager.get_user_config_dict(user.id)
        assert cfg["adapters"]["linyu"]["enabled"] is True
        assert cfg["adapters"]["linyu"]["account"] == "ai_tester01"
        assert cfg["adapters"]["linyu"]["target_user_account"] == "user_tester01"
    finally:
        user_manager_module.user_data_manager = original_data_manager

