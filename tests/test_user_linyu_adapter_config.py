import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.user.data_manager import UserDataManager
from backend.user.manager import UserManager


@pytest.mark.asyncio
async def test_user_config_can_persist_adapters_section(tmp_path):
    db_path = tmp_path / "users.db"
    user_data_path = tmp_path / "user_data"
    admin_config_path = tmp_path / "config.yaml"
    admin_config_path.write_text(
        yaml.safe_dump(
            {
                "llm": {"provider": "openai", "model": "default-model"},
                "adapters": {"linyu": {"enabled": False, "server": "http://localhost"}},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    manager = UserManager(db_url=f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await manager.init_db()

    from backend.user import manager as user_manager_module

    original_data_manager = user_manager_module.user_data_manager
    user_manager_module.user_data_manager = UserDataManager(
        base_path=str(user_data_path),
        admin_config_path=str(admin_config_path),
    )
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


@pytest.mark.asyncio
async def test_new_user_config_starts_as_full_admin_config_copy(tmp_path):
    db_path = tmp_path / "users.db"
    user_data_path = tmp_path / "user_data"
    admin_config_path = tmp_path / "config.yaml"
    admin_config = {
        "system_prompt": "默认人设",
        "llm": {"provider": "openai", "model": "admin-model"},
        "tts": {"enabled": True, "provider": "qihang"},
        "adapters": {"qq": {"enabled": True}},
    }
    admin_config_path.write_text(
        yaml.safe_dump(admin_config, allow_unicode=True),
        encoding="utf-8",
    )

    manager = UserManager(db_url=f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await manager.init_db()

    from backend.user import manager as user_manager_module

    original_data_manager = user_manager_module.user_data_manager
    user_manager_module.user_data_manager = UserDataManager(
        base_path=str(user_data_path),
        admin_config_path=str(admin_config_path),
    )
    try:
        user = await manager.create_user(username="copy_tester", password="secret123")
        assert user is not None

        user_config_path = user_data_path / "copy_tester" / "config.yaml"
        copied_config = yaml.safe_load(user_config_path.read_text(encoding="utf-8"))
        assert copied_config == admin_config

        cfg = await manager.get_user_config_dict(user.id)
        assert cfg["system_prompt"] == "默认人设"
        assert cfg["llm"]["model"] == "admin-model"
        assert cfg["tts"]["enabled"] is True
        assert cfg["adapters"]["qq"]["enabled"] is True
    finally:
        user_manager_module.user_data_manager = original_data_manager


@pytest.mark.asyncio
async def test_reset_user_config_restores_admin_defaults(tmp_path):
    db_path = tmp_path / "users.db"
    user_data_path = tmp_path / "user_data"
    admin_config_path = tmp_path / "config.yaml"
    admin_config = {
        "llm": {"provider": "openai", "model": "admin-model"},
        "tts": {"enabled": True, "provider": "admin-tts"},
    }
    admin_config_path.write_text(
        yaml.safe_dump(admin_config, allow_unicode=True),
        encoding="utf-8",
    )

    manager = UserManager(db_url=f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await manager.init_db()

    from backend.user import manager as user_manager_module

    original_data_manager = user_manager_module.user_data_manager
    user_manager_module.user_data_manager = UserDataManager(
        base_path=str(user_data_path),
        admin_config_path=str(admin_config_path),
    )
    try:
        user = await manager.create_user(username="reset_tester", password="secret123")
        assert user is not None

        ok = await manager.update_user_config(user.id, {"llm_config": {"model": "user-model"}})
        assert ok is True
        cfg = await manager.get_user_config_dict(user.id)
        assert cfg["llm"]["model"] == "user-model"

        ok = await manager.update_user_config(user.id, {"llm_config": None})
        assert ok is True
        cfg = await manager.get_user_config_dict(user.id)
        assert cfg["llm"]["model"] == "admin-model"
        assert cfg["tts"]["provider"] == "admin-tts"

        ok = await manager.update_user_config(
            user.id,
            {
                "llm_config": None,
                "tts_config": None,
                "adapters": None,
                "system_prompt": None,
                "preferences": None,
            },
        )
        assert ok is True
        copied_config = yaml.safe_load(
            (user_data_path / "reset_tester" / "config.yaml").read_text(encoding="utf-8")
        )
        assert copied_config == admin_config
    finally:
        user_manager_module.user_data_manager = original_data_manager
