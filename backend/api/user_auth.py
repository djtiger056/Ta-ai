"""用户认证 API 接口"""
import re
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from backend.user import user_manager, auth_manager, User
from backend.api.deps import get_access_token


router = APIRouter(prefix="/api", tags=["auth"])

# 用户名只允许英文字母和数字
_USERNAME_RE = re.compile(r'^[A-Za-z0-9]+$')


class RegisterRequest(BaseModel):
    """注册请求模型"""
    username: str = Field(description="用户名（只允许英文字母和数字）", min_length=3, max_length=50)
    password: str = Field(description="密码", min_length=6, max_length=100)
    nickname: Optional[str] = Field(default=None, description="昵称")
    qq_user_id: Optional[str] = Field(default=None, description="QQ用户ID")
    avatar: Optional[str] = Field(default=None, description="头像URL")

    @field_validator('username')
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not _USERNAME_RE.match(v):
            raise ValueError('用户名只允许英文字母和数字')
        return v


class LoginRequest(BaseModel):
    """登录请求模型"""
    username: str = Field(description="用户名")
    password: str = Field(description="密码")


class UserResponse(BaseModel):
    """用户响应模型"""
    id: int
    username: str
    nickname: Optional[str]
    qq_user_id: Optional[str]
    linyu_user_id: Optional[str]
    linyu_account: Optional[str]
    avatar: Optional[str]
    is_active: int
    is_admin: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """令牌响应模型"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest):
    """用户注册"""
    # 检查用户名是否已存在
    existing_user = await user_manager.get_user_by_username(request.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    
    # 检查QQ用户ID是否已存在
    if request.qq_user_id:
        existing_qq_user = await user_manager.get_user_by_qq_id(request.qq_user_id)
        if existing_qq_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该QQ账号已注册"
            )
    
    # 创建用户
    user = await user_manager.create_user(
        username=request.username,
        password=request.password,
        nickname=request.nickname,
        qq_user_id=request.qq_user_id,
        avatar=request.avatar
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="用户创建失败"
        )
    
    return UserResponse.model_validate(user)


@router.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """用户登录"""
    # 认证用户
    user = await user_manager.authenticate(request.username, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用"
        )
    
    # 创建访问令牌
    token = auth_manager.create_token(
        user_id=user.id,
        username=user.username,
        qq_user_id=user.qq_user_id
    )
    
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user)
    )


@router.get("/auth/me", response_model=UserResponse)
async def get_current_user(token: str = Depends(get_access_token)):
    """获取当前用户信息"""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少令牌")
    user_info = auth_manager.get_user_from_token(token)
    
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌"
        )
    
    user = await user_manager.get_user_by_id(user_info['user_id'])
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return UserResponse.model_validate(user)


@router.post("/auth/qq-bind")
async def bind_qq_account(token: str = Depends(get_access_token), qq_user_id: str = ""):
    """绑定QQ账号"""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少令牌")
    if not qq_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少 qq_user_id")
    user_info = auth_manager.get_user_from_token(token)
    
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌"
        )
    
    # 检查QQ用户ID是否已被绑定
    existing_user = await user_manager.get_user_by_qq_id(qq_user_id)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该QQ账号已被绑定"
        )
    
    # 获取用户
    user = await user_manager.get_user_by_id(user_info['user_id'])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 更新用户QQ ID
    success = await user_manager.update_user(
        user_id=user.id,
        qq_user_id=qq_user_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="绑定失败"
        )
    
    return {"message": "QQ账号绑定成功"}


@router.post("/auth/linyu-bind")
async def bind_linyu_account(token: str = Depends(get_access_token), linyu_user_id: str = ""):
    """绑定Linyu账号
    
    接受 Linyu 用户 ID（UUID格式）或 Linyu 账号名。
    如果传入的是账号名，会自动解析为用户 ID。
    解析失败时直接报错，避免绑定到不存在的账号。
    """
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少令牌")
    if not linyu_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少 linyu_user_id")
    user_info = auth_manager.get_user_from_token(token)
    
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌"
        )

    # 获取当前用户
    user = await user_manager.get_user_by_id(user_info['user_id'])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    input_value = linyu_user_id.strip()
    resolved_id = input_value
    display_account = input_value  # 用于前端显示的账号名

    if _looks_like_uuid(input_value):
        # 用户直接输入了 UUID，尝试反查账号名
        display_account = input_value[:8] + "..."
    else:
        # 用户输入的是账号名，尝试解析为 userId
        display_account = input_value
        resolved = await _resolve_linyu_user_id(input_value)
        if not resolved:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="未能解析该 Linyu 账号，请确认账号存在且后端 Linyu 连接正常"
            )
        resolved_id = resolved

    # 检查Linyu用户ID是否已被绑定
    existing_user = await user_manager.get_user_by_linyu_id(resolved_id)
    if existing_user and existing_user.id != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该Linyu账号已被绑定"
        )
    
    # 更新用户Linyu ID和账号名
    success = await user_manager.update_user(
        user_id=user.id,
        linyu_user_id=resolved_id,
        linyu_account=display_account
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="绑定失败"
        )
    
    return {"message": "Linyu账号绑定成功", "linyu_user_id": resolved_id, "linyu_account": display_account}


def _looks_like_uuid(value: str) -> bool:
    """判断是否为 UUID 格式"""
    return len(value) == 36 and value.count("-") == 4


async def _resolve_linyu_user_id(account: str) -> Optional[str]:
    """通过 Linyu API 将账号解析为用户 ID"""
    import aiohttp
    from backend.config import config as app_config
    from backend.user import user_manager

    linyu_config = app_config.adapters_config.get("linyu", {})
    http_host = linyu_config.get("http_host", "127.0.0.1")
    http_port = linyu_config.get("http_port", 9200)
    
    # 构建 base URL
    if http_host.startswith("http://") or http_host.startswith("https://"):
        base_url = http_host.rstrip("/")
    else:
        base_url = f"http://{http_host}"
    if ":" not in base_url.split("://", 1)[1]:
        base_url = f"{base_url}:{http_port}"

    credential_candidates: list[tuple[str, str]] = []

    # 优先尝试全局机器人账号
    bot_account = str(linyu_config.get("account", "") or "").strip()
    bot_password = str(linyu_config.get("password", "") or "").strip()
    if bot_account and bot_password:
        credential_candidates.append((bot_account, bot_password))

    # 再尝试所有用户级 Linyu AI 账号
    try:
        users = await user_manager.list_users(limit=1000)
        for user in users:
            user_cfg = await user_manager.get_user_config_dict(user.id)
            user_linyu = ((user_cfg or {}).get("adapters", {}) or {}).get("linyu", {}) or {}
            account_value = str(user_linyu.get("account", "") or "").strip()
            password_value = str(user_linyu.get("password", "") or "").strip()
            if account_value and password_value and (account_value, password_value) not in credential_candidates:
                credential_candidates.append((account_value, password_value))
    except Exception:
        pass

    if not credential_candidates:
        return None

    try:
        async with aiohttp.ClientSession() as session:
            for login_account, login_password in credential_candidates:
                # 获取公钥
                async with session.get(f"{base_url}/v1/api/login/public-key") as resp:
                    pk_result = await resp.json()
                public_key_pem = pk_result.get("data", "") if isinstance(pk_result, dict) else str(pk_result)

                # 加密密码
                from cryptography.hazmat.primitives.asymmetric import padding
                from cryptography.hazmat.primitives.serialization import load_pem_public_key
                import base64

                password_str = str(login_password) if login_password else ""
                public_key = load_pem_public_key(str(public_key_pem).encode("utf-8"))
                encrypted = public_key.encrypt(password_str.encode("utf-8"), padding.PKCS1v15())
                encrypted_password = base64.b64encode(encrypted).decode("utf-8")

                # 登录获取 token
                login_payload = {"account": login_account, "password": encrypted_password, "onlineEquipment": "bot"}
                async with session.post(f"{base_url}/v1/api/login", json=login_payload) as resp:
                    login_result = await resp.json()
                login_data = login_result.get("data") if isinstance(login_result, dict) else None
                if not login_data or "token" not in login_data:
                    continue
                bot_token = login_data["token"]

                # 搜索用户
                headers = {"x-token": bot_token}
                search_payload = {"userInfo": account}
                async with session.post(f"{base_url}/v1/api/user/search", json=search_payload, headers=headers) as resp:
                    search_result = await resp.json()
                data = search_result.get("data") if isinstance(search_result, dict) else None
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and str(item.get("account", "")) == account:
                            return str(item.get("id") or item.get("userId") or "")
                    if len(data) == 1 and isinstance(data[0], dict):
                        return str(data[0].get("id") or data[0].get("userId") or "")
                elif isinstance(data, dict):
                    return str(data.get("id") or data.get("userId") or "")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Linyu 账号解析失败: {e}")
    return None


class ChangePasswordRequest(BaseModel):
    """修改密码请求模型"""
    old_password: str = Field(description="旧密码")
    new_password: str = Field(description="新密码", min_length=6, max_length=100)


@router.post("/auth/change-password")
async def change_password(request: ChangePasswordRequest, token: str = Depends(get_access_token)):
    """修改密码"""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少令牌")
    
    user_info = auth_manager.get_user_from_token(token)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌"
        )
    
    # 获取用户
    user = await user_manager.get_user_by_id(user_info['user_id'])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 验证旧密码
    if not auth_manager.verify_password(request.old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误"
        )
    
    # 更新密码
    from sqlalchemy import update
    from backend.user.models import User as UserModel
    
    async with user_manager.get_session() as session:
        new_hash = auth_manager.hash_password(request.new_password)
        stmt = update(UserModel).where(UserModel.id == user.id).values(password_hash=new_hash)
        await session.execute(stmt)
        await session.commit()
    
    return {"message": "密码修改成功"}


class UpdateProfileRequest(BaseModel):
    """更新个人信息请求模型"""
    nickname: Optional[str] = Field(default=None, description="昵称")
    avatar: Optional[str] = Field(default=None, description="头像URL")


@router.put("/auth/profile", response_model=UserResponse)
async def update_profile(request: UpdateProfileRequest, token: str = Depends(get_access_token)):
    """更新个人信息"""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少令牌")
    
    user_info = auth_manager.get_user_from_token(token)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌"
        )
    
    # 更新用户信息
    success = await user_manager.update_user(
        user_id=user_info['user_id'],
        nickname=request.nickname,
        avatar=request.avatar
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新失败"
        )
    
    # 返回更新后的用户信息
    user = await user_manager.get_user_by_id(user_info['user_id'])
    return UserResponse.model_validate(user)
