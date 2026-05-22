"""用户管理器"""
import json
import secrets
from typing import Optional, Dict, Any
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from backend.user.models import User, UserConfig, Base
from backend.user.auth import auth_manager
from backend.user.data_manager import user_data_manager
from backend.config import config


class UserManager:
    """用户管理器"""
    
    def __init__(self, db_url: str = "sqlite+aiosqlite:///data/users.db"):
        if db_url.startswith("sqlite+aiosqlite:///") and not db_url.startswith("sqlite+aiosqlite:////"):
            from pathlib import Path
            project_root = Path(__file__).resolve().parents[2]
            relative_path = db_url.replace("sqlite+aiosqlite:///", "", 1)
            db_file = project_root / relative_path
            db_file.parent.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
        self.engine = create_async_engine(db_url, echo=False)
        self.async_session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def init_db(self):
        """初始化数据库表"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # 自动迁移：为已有数据库添加新列
            await conn.run_sync(self._migrate_columns)

    @staticmethod
    def _migrate_columns(connection):
        """检查并添加缺失的列（兼容已有数据库）"""
        from sqlalchemy import inspect, text
        inspector = inspect(connection)
        columns = [col['name'] for col in inspector.get_columns('users')]
        if 'linyu_user_id' not in columns:
            # SQLite 不支持 ALTER TABLE ADD COLUMN ... UNIQUE，需分步操作
            connection.execute(text(
                "ALTER TABLE users ADD COLUMN linyu_user_id VARCHAR(100)"
            ))
            connection.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_linyu_user_id ON users (linyu_user_id)"
            ))
        if 'linyu_account' not in columns:
            connection.execute(text(
                "ALTER TABLE users ADD COLUMN linyu_account VARCHAR(100)"
            ))
    
    def get_session(self) -> AsyncSession:
        """获取数据库会话"""
        return self.async_session_factory()
    
    async def create_user(
        self,
        username: str,
        password: str,
        nickname: Optional[str] = None,
        qq_user_id: Optional[str] = None,
        avatar: Optional[str] = None
    ) -> Optional[User]:
        """创建用户"""
        async with self.get_session() as session:
            # 检查用户名是否已存在
            stmt = select(User).where(User.username == username)
            result = await session.execute(stmt)
            if result.scalar_one_or_none():
                return None
            
            # 检查QQ用户ID是否已存在
            if qq_user_id:
                stmt = select(User).where(User.qq_user_id == qq_user_id)
                result = await session.execute(stmt)
                if result.scalar_one_or_none():
                    return None
            
            # 创建用户
            user = User(
                username=username,
                password_hash=auth_manager.hash_password(password),
                nickname=nickname or username,
                qq_user_id=qq_user_id,
                avatar=avatar
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            
            # 创建用户配置
            user_config = UserConfig(user_id=user.id)
            session.add(user_config)
            await session.commit()
            
            # 初始化用户数据目录（按 username 命名）
            user_data_manager.init_user_data(user.username)
            
            return user
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """根据ID获取用户"""
        async with self.get_session() as session:
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        async with self.get_session() as session:
            stmt = select(User).where(User.username == username)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
    
    async def get_user_by_qq_id(self, qq_user_id: str) -> Optional[User]:
        """根据QQ用户ID获取用户"""
        async with self.get_session() as session:
            stmt = select(User).where(User.qq_user_id == qq_user_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_user_by_linyu_id(self, linyu_user_id: str) -> Optional[User]:
        """根据Linyu用户ID或账号名获取用户"""
        async with self.get_session() as session:
            stmt = select(User).where(User.linyu_user_id == linyu_user_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def has_any_linyu_binding(self) -> bool:
        """是否存在任意已绑定的 Linyu 账号。"""
        async with self.get_session() as session:
            stmt = select(User.id).where(User.linyu_user_id.is_not(None)).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def get_or_create_user_by_linyu_id(
        self,
        linyu_user_id: str,
        *,
        nickname: Optional[str] = None,
        avatar: Optional[str] = None,
    ) -> User:
        """按 Linyu 用户ID 获取或自动创建用户（免注册）。

        用途：机器人面向 Linyu 多用户使用时，首次接触自动建档，默认继承全局配置。
        """
        existing = await self.get_user_by_linyu_id(linyu_user_id)
        if existing:
            return existing

        base_username = f"linyu_{linyu_user_id}"
        username = base_username

        random_password = secrets.token_urlsafe(32)
        password_hash = auth_manager.hash_password(random_password)

        async with self.get_session() as session:
            suffix = 0
            while True:
                stmt = select(User).where(User.username == username)
                res = await session.execute(stmt)
                if res.scalar_one_or_none() is None:
                    break
                suffix += 1
                username = f"{base_username}_{suffix}"

            user = User(
                username=username,
                password_hash=password_hash,
                nickname=nickname or username,
                linyu_user_id=linyu_user_id,
                avatar=avatar,
                is_active=1,
                is_admin=0,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            user_config = UserConfig(user_id=user.id)
            session.add(user_config)
            await session.commit()

            user_data_manager.init_user_data(user.username)

            return user

    async def get_or_create_user_by_qq_id(
        self,
        qq_user_id: str,
        *,
        nickname: Optional[str] = None,
        avatar: Optional[str] = None,
    ) -> User:
        """按 QQ 用户ID 获取或自动创建用户（免注册）。

        用途：机器人面向 QQ 多用户使用时，首次接触自动建档，默认继承全局配置；
        后续可由管理员为该 qq_user_id 下发独立配置覆盖。
        """
        existing = await self.get_user_by_qq_id(qq_user_id)
        if existing:
            return existing

        base_username = f"qq_{qq_user_id}"
        username = base_username

        # 生成一个随机密码，避免可登录（没有人知道密码）；如需登录体系可后续绑定/重置
        random_password = secrets.token_urlsafe(32)
        password_hash = auth_manager.hash_password(random_password)

        async with self.get_session() as session:
            # 避免用户名冲突
            suffix = 0
            while True:
                stmt = select(User).where(User.username == username)
                res = await session.execute(stmt)
                if res.scalar_one_or_none() is None:
                    break
                suffix += 1
                username = f"{base_username}_{suffix}"

            user = User(
                username=username,
                password_hash=password_hash,
                nickname=nickname or username,
                qq_user_id=qq_user_id,
                avatar=avatar,
                is_active=1,
                is_admin=0,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            user_config = UserConfig(user_id=user.id)
            session.add(user_config)
            await session.commit()

            # 初始化用户数据目录（按 username 命名）
            user_data_manager.init_user_data(user.username)

            return user
    
    async def authenticate(self, username: str, password: str) -> Optional[User]:
        """用户认证"""
        user = await self.get_user_by_username(username)
        if user and user.is_active and auth_manager.verify_password(password, user.password_hash):
            return user
        return None
    
    async def get_user_config(self, user_id: int) -> Optional[UserConfig]:
        """获取用户配置"""
        async with self.get_session() as session:
            stmt = select(UserConfig).where(UserConfig.user_id == user_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
    
    async def update_user_config(
        self,
        user_id: int,
        config_data: Dict[str, Any]
    ) -> bool:
        """更新用户配置（写入用户数据目录的 config.yaml）"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        # 将 API 字段名映射为 config.yaml 顶层键
        _KEY_MAP = {
            'llm_config': 'llm',
            'tts_config': 'tts',
            'image_gen_config': 'image_generation',
            'vision_config': 'vision',
            'prompt_enhancer_config': 'prompt_enhancer',
            'emote_config': 'emotes',
            'proactive_chat_config': 'proactive_chat',
            'adapters': 'adapters',
        }

        file_data: Dict[str, Any] = {}
        for raw_key, value in config_data.items():
            yaml_key = _KEY_MAP.get(raw_key, raw_key)
            if value is None:
                # None 表示重置该键，用空 dict 占位（reset_user_config 会删除）
                continue
            # 如果 value 是 JSON 字符串（旧路径兼容），先解析
            if isinstance(value, str):
                try:
                    import json as _json
                    value = _json.loads(value)
                except Exception:
                    pass
            file_data[yaml_key] = value

        # 处理 None 值（重置）
        reset_keys = [_KEY_MAP.get(k, k) for k, v in config_data.items() if v is None]
        is_full_reset_request = (
            config_data
            and len(reset_keys) == len(config_data)
            and {
                _KEY_MAP.get(k, k)
                for k in config_data.keys()
            } >= {
                'system_prompt',
                'llm',
                'tts',
                'image_generation',
                'vision',
                'prompt_enhancer',
                'emotes',
                'proactive_chat',
                'adapters',
                'preferences',
            }
        )
        if is_full_reset_request:
            return user_data_manager.reset_user_config(user.username)

        if file_data:
            ok = user_data_manager.save_user_config(user.username, file_data)
            if not ok:
                return False

        if reset_keys:
            user_data_manager.reset_user_config(user.username, reset_keys)

        return True

    async def get_user_config_dict(self, user_id: int) -> Dict[str, Any]:
        """从用户数据目录的 config.yaml 读取用户配置"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return {}

        data = user_data_manager.load_user_config(user.username)
        if not data:
            return {}

        # 统一字段名（与 UserConfigResponse 对齐）
        result: Dict[str, Any] = {}
        _YAML_TO_API = {
            'llm': 'llm',
            'tts': 'tts',
            'image_generation': 'image_generation',
            'vision': 'vision',
            'prompt_enhancer': 'prompt_enhancer',
            'emotes': 'emotes',
            'proactive_chat': 'proactive_chat',
            'adapters': 'adapters',
            'system_prompt': 'system_prompt',
            'preferences': 'preferences',
        }
        for yaml_key, api_key in _YAML_TO_API.items():
            if yaml_key in data:
                result[api_key] = data[yaml_key]

        return result
    
    async def list_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """列出用户"""
        async with self.get_session() as session:
            stmt = select(User).offset(skip).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())
    
    async def update_user(
        self,
        user_id: int,
        nickname: Optional[str] = None,
        avatar: Optional[str] = None,
        is_active: Optional[int] = None,
        qq_user_id: Optional[str] = None,
        linyu_user_id: Optional[str] = None,
        linyu_account: Optional[str] = None,
    ) -> bool:
        """更新用户信息"""
        async with self.get_session() as session:
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                return False
            
            if nickname is not None:
                user.nickname = nickname
            if avatar is not None:
                user.avatar = avatar
            if is_active is not None:
                user.is_active = is_active
            if qq_user_id is not None:
                user.qq_user_id = qq_user_id
            if linyu_user_id is not None:
                user.linyu_user_id = linyu_user_id
            if linyu_account is not None:
                user.linyu_account = linyu_account
            
            await session.commit()
            return True
    
    async def delete_user(self, user_id: int) -> bool:
        """删除用户"""
        async with self.get_session() as session:
            stmt = delete(User).where(User.id == user_id)
            await session.execute(stmt)
            await session.commit()
            return True


# 全局用户管理器实例
user_manager = UserManager()
