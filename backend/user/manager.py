"""用户管理器"""
import json
import secrets
from typing import Optional, Dict, Any
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from backend.user.models import User, UserConfig, Base
from backend.user.auth import auth_manager
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
            
            # 初始化用户数据目录
            from backend.user.data_manager import user_data_manager
            user_data_manager.init_user_data(user.id)
            
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

            # 初始化用户数据目录
            from backend.user.data_manager import user_data_manager
            user_data_manager.init_user_data(user.id)

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
        """更新用户配置"""
        async with self.get_session() as session:
            stmt = select(UserConfig).where(UserConfig.user_id == user_id)
            result = await session.execute(stmt)
            user_config = result.scalar_one_or_none()
            
            if not user_config:
                return False
            
            # 更新配置字段
            if 'system_prompt' in config_data:
                user_config.system_prompt = config_data['system_prompt']
            if 'llm_config' in config_data:
                user_config.llm_config = json.dumps(config_data['llm_config'])
            if 'tts_config' in config_data:
                user_config.tts_config = json.dumps(config_data['tts_config'])
            if 'image_gen_config' in config_data:
                user_config.image_gen_config = json.dumps(config_data['image_gen_config'])
            if 'vision_config' in config_data:
                user_config.vision_config = json.dumps(config_data['vision_config'])
            if 'prompt_enhancer_config' in config_data:
                user_config.prompt_enhancer_config = json.dumps(config_data['prompt_enhancer_config'])
            if 'emote_config' in config_data:
                user_config.emote_config = json.dumps(config_data['emote_config'])
            if 'proactive_chat_config' in config_data:
                user_config.proactive_chat_config = json.dumps(config_data['proactive_chat_config'])
            if 'preferences' in config_data:
                user_config.preferences = json.dumps(config_data['preferences'])
            
            await session.commit()
            return True
    
    async def get_user_config_dict(self, user_id: int) -> Dict[str, Any]:
        """获取用户配置字典"""
        user_config = await self.get_user_config(user_id)
        if not user_config:
            return {}
        
        config_dict = {}
        
        # 解析JSON配置
        if user_config.system_prompt:
            config_dict['system_prompt'] = user_config.system_prompt
        if user_config.llm_config:
            config_dict['llm'] = json.loads(user_config.llm_config)
        if user_config.tts_config:
            config_dict['tts'] = json.loads(user_config.tts_config)
        if user_config.image_gen_config:
            config_dict['image_generation'] = json.loads(user_config.image_gen_config)
        if user_config.vision_config:
            config_dict['vision'] = json.loads(user_config.vision_config)
        if user_config.prompt_enhancer_config:
            config_dict['prompt_enhancer'] = json.loads(user_config.prompt_enhancer_config)
        if user_config.emote_config:
            config_dict['emotes'] = json.loads(user_config.emote_config)
        if user_config.proactive_chat_config:
            config_dict['proactive_chat'] = json.loads(user_config.proactive_chat_config)
        if user_config.preferences:
            config_dict['preferences'] = json.loads(user_config.preferences)
        
        return config_dict
    
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
