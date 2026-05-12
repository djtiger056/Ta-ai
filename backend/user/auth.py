"""用户认证工具类"""
import hashlib
import jwt
from datetime import timedelta
from typing import Optional, Dict, Any
from backend.config import config
from backend.utils.datetime_utils import get_now


class AuthManager:
    """认证管理器"""

    ALGORITHM = 'HS256'
    TOKEN_EXPIRE_HOURS = 24 * 7  # 7天过期

    @staticmethod
    def _get_secret_key() -> str:
        """获取 JWT 密钥（每次从配置读取，支持热更新）"""
        key = config.get('jwt_secret_key', 'your-secret-key-change-this-in-production')
        if not key or not isinstance(key, str):
            key = 'your-secret-key-change-this-in-production'
        return key

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """验证密码"""
        return AuthManager.hash_password(password) == password_hash
    
    @staticmethod
    def create_token(user_id: int, username: str, qq_user_id: Optional[str] = None) -> str:
        """创建访问令牌"""
        payload = {
            'user_id': user_id,
            'username': username,
            'qq_user_id': qq_user_id,
            'exp': get_now() + timedelta(hours=AuthManager.TOKEN_EXPIRE_HOURS),
            'iat': get_now()
        }
        return jwt.encode(payload, AuthManager._get_secret_key(), algorithm=AuthManager.ALGORITHM)
    
    @staticmethod
    def decode_token(token: str) -> Optional[Dict[str, Any]]:
        """解码访问令牌"""
        try:
            payload = jwt.decode(token, AuthManager._get_secret_key(), algorithms=[AuthManager.ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError as e:
            print(f"[DEBUG] Token decode error: {e}")
            return None
    
    @staticmethod
    def get_user_from_token(token: str) -> Optional[Dict[str, Any]]:
        """从令牌获取用户信息"""
        payload = AuthManager.decode_token(token)
        if payload:
            return {
                'user_id': payload.get('user_id'),
                'username': payload.get('username'),
                'qq_user_id': payload.get('qq_user_id')
            }
        return None


# 全局认证管理器实例
auth_manager = AuthManager()