"""用户数据文件管理器

管理每个用户的个人数据文件夹，目录以用户名命名（只含英文+数字，安全可读）：

    user_data/
    └── {username}/
        ├── config.yaml     ← 用户个人配置（初始化时复制根目录 config.yaml）
        ├── images/         ← 图生图等生成的图片
        ├── logs/           ← 聊天日志
        ├── uploads/        ← 用户上传的文件
        └── voice_samples/  ← TTS 克隆声音样本
"""
import shutil
import yaml
import copy
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class UserDataManager:
    """用户数据文件管理器（按 username 组织目录）"""

    IMAGES_DIR = "images"
    LOGS_DIR = "logs"
    UPLOADS_DIR = "uploads"
    VOICE_SAMPLES_DIR = "voice_samples"
    USER_CONFIG_FILE = "config.yaml"

    def __init__(self, base_path: Optional[str] = None, admin_config_path: Optional[str] = None):
        project_root = Path(__file__).resolve().parents[2]
        if base_path:
            self.base_path = Path(base_path)
        else:
            self.base_path = project_root / "user_data"
        self.admin_config_path = Path(admin_config_path) if admin_config_path else project_root / "config.yaml"
        self.example_config_path = self.admin_config_path.with_name("config.example.yaml")
        self.base_path.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 目录管理
    # ------------------------------------------------------------------

    def _get_user_dir(self, username: str) -> Path:
        """返回用户数据根目录（user_data/{username}）"""
        return self.base_path / username

    def _ensure_user_dirs(self, username: str) -> Path:
        """确保用户所有子目录存在，返回用户根目录"""
        user_dir = self._get_user_dir(username)
        for subdir in [self.IMAGES_DIR, self.LOGS_DIR, self.UPLOADS_DIR, self.VOICE_SAMPLES_DIR]:
            (user_dir / subdir).mkdir(parents=True, exist_ok=True)
        return user_dir

    def init_user_data(self, username: str) -> Path:
        """初始化用户数据目录（创建时调用）"""
        user_dir = self._ensure_user_dirs(username)
        self.ensure_user_config(username)
        logger.info(f"初始化用户数据目录: {user_dir}")
        return user_dir

    # ------------------------------------------------------------------
    # 用户配置（config.yaml）
    # ------------------------------------------------------------------

    def get_user_config_path(self, username: str) -> Path:
        """返回用户配置文件路径（user_data/{username}/config.yaml）"""
        return self._get_user_dir(username) / self.USER_CONFIG_FILE

    def _get_admin_config_source(self) -> Optional[Path]:
        """返回可复制的管理员兜底配置文件路径。"""
        if self.admin_config_path.exists():
            return self.admin_config_path
        if self.example_config_path.exists():
            return self.example_config_path
        return None

    def _load_admin_config(self) -> Dict[str, Any]:
        """加载根目录管理员兜底配置，不存在或格式异常时返回空 dict。"""
        source = self._get_admin_config_source()
        if not source:
            return {}
        try:
            with open(source, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.error(f"加载管理员兜底配置失败 path={source}: {e}")
            return {}

    def ensure_user_config(self, username: str, *, overwrite: bool = False) -> bool:
        """确保用户 config.yaml 存在。

        默认直接复制根目录 config.yaml 的完整文件内容。overwrite=True 时会用
        最新管理员兜底配置覆盖用户配置，用于“重置全部配置”。已有的旧式局部
        用户配置会自动用管理员配置补齐缺失字段，同时保留用户已修改的值。
        """
        try:
            self._ensure_user_dirs(username)
            config_path = self.get_user_config_path(username)
            if config_path.exists() and not overwrite:
                existing: Dict[str, Any] = {}
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        loaded = yaml.safe_load(f)
                    if isinstance(loaded, dict):
                        existing = loaded
                except Exception:
                    return True

                admin_config = self._load_admin_config()
                if not admin_config:
                    return True

                merged = _deep_merge(admin_config, existing)
                if merged != existing:
                    with open(config_path, 'w', encoding='utf-8') as f:
                        yaml.dump(merged, f, default_flow_style=False, allow_unicode=True)
                    logger.info(f"补齐用户配置: username={username}, path={config_path}")
                return True

            source = self._get_admin_config_source()
            if source:
                shutil.copyfile(source, config_path)
            else:
                with open(config_path, 'w', encoding='utf-8') as f:
                    yaml.dump({}, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"初始化用户配置: username={username}, path={config_path}")
            return True
        except Exception as e:
            logger.error(f"初始化用户配置失败 username={username}: {e}")
            return False

    def load_user_config(self, username: str) -> Optional[Dict[str, Any]]:
        """从 config.yaml 加载用户配置，不存在则复制管理员兜底配置后再加载"""
        config_path = self.get_user_config_path(username)
        if not self.ensure_user_config(username):
            return None
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            return data if isinstance(data, dict) else None
        except Exception as e:
            logger.error(f"加载用户配置失败 username={username}: {e}")
            return None

    def save_user_config(self, username: str, config: Dict[str, Any]) -> bool:
        """将用户配置保存到 config.yaml（深度合并已有内容）"""
        try:
            self._ensure_user_dirs(username)
            config_path = self.get_user_config_path(username)
            self.ensure_user_config(username)

            # 读取已有配置，深度合并后写回
            existing: Dict[str, Any] = {}
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        loaded = yaml.safe_load(f)
                    if isinstance(loaded, dict):
                        existing = loaded
                except Exception:
                    pass

            merged = _deep_merge(existing, config)

            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(merged, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"保存用户配置: username={username}, path={config_path}")
            return True
        except Exception as e:
            logger.error(f"保存用户配置失败 username={username}: {e}")
            return False

    def reset_user_config(self, username: str, keys: Optional[List[str]] = None) -> bool:
        """重置用户配置。

        keys 为 None 时重新复制整份管理员兜底配置。指定 keys 时，仅把对应顶层键
        恢复为管理员配置中的默认值；管理员配置不存在该键则从用户配置中移除。
        """
        config_path = self.get_user_config_path(username)
        try:
            if keys is None:
                return self.ensure_user_config(username, overwrite=True)

            if not config_path.exists():
                return self.ensure_user_config(username)

            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            admin_config = self._load_admin_config()
            for k in keys:
                if k in admin_config:
                    data[k] = copy.deepcopy(admin_config[k])
                else:
                    data.pop(k, None)

            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            return True
        except Exception as e:
            logger.error(f"重置用户配置失败 username={username}: {e}")
            return False

    # ------------------------------------------------------------------
    # 图片
    # ------------------------------------------------------------------

    def get_user_image_dir(self, username: str) -> Path:
        self._ensure_user_dirs(username)
        return self._get_user_dir(username) / self.IMAGES_DIR

    def save_user_image(self, username: str, image_data: bytes, filename: str) -> Optional[Path]:
        try:
            image_path = self.get_user_image_dir(username) / filename
            with open(image_path, 'wb') as f:
                f.write(image_data)
            return image_path
        except Exception as e:
            logger.error(f"保存用户图片失败 username={username}: {e}")
            return None

    def list_user_images(self, username: str) -> List[Dict[str, Any]]:
        try:
            image_dir = self.get_user_image_dir(username)
            images = []
            for fp in image_dir.iterdir():
                if fp.is_file() and fp.suffix.lower() in {'.jpg', '.jpeg', '.png', '.gif', '.webp'}:
                    stat = fp.stat()
                    images.append({
                        'filename': fp.name,
                        'path': str(fp),
                        'size': stat.st_size,
                        'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    })
            return sorted(images, key=lambda x: x['modified_at'], reverse=True)
        except Exception as e:
            logger.error(f"列出用户图片失败 username={username}: {e}")
            return []

    def delete_user_image(self, username: str, filename: str) -> bool:
        try:
            image_path = self.get_user_image_dir(username) / filename
            if image_path.exists():
                image_path.unlink()
            return True
        except Exception as e:
            logger.error(f"删除用户图片失败 username={username}: {e}")
            return False

    # ------------------------------------------------------------------
    # 上传文件
    # ------------------------------------------------------------------

    def get_user_upload_dir(self, username: str) -> Path:
        self._ensure_user_dirs(username)
        return self._get_user_dir(username) / self.UPLOADS_DIR

    def save_user_upload(self, username: str, file_data: bytes, filename: str) -> Optional[Path]:
        try:
            file_path = self.get_user_upload_dir(username) / filename
            with open(file_path, 'wb') as f:
                f.write(file_data)
            return file_path
        except Exception as e:
            logger.error(f"保存用户上传文件失败 username={username}: {e}")
            return None

    # ------------------------------------------------------------------
    # 语音样本
    # ------------------------------------------------------------------

    def get_user_voice_sample_dir(self, username: str) -> Path:
        self._ensure_user_dirs(username)
        return self._get_user_dir(username) / self.VOICE_SAMPLES_DIR

    def save_voice_sample(self, username: str, audio_data: bytes, filename: str) -> Optional[Path]:
        try:
            file_path = self.get_user_voice_sample_dir(username) / filename
            with open(file_path, 'wb') as f:
                f.write(audio_data)
            return file_path
        except Exception as e:
            logger.error(f"保存用户语音样本失败 username={username}: {e}")
            return None

    # ------------------------------------------------------------------
    # 日志
    # ------------------------------------------------------------------

    def get_user_log_dir(self, username: str) -> Path:
        self._ensure_user_dirs(username)
        return self._get_user_dir(username) / self.LOGS_DIR

    def append_user_log(self, username: str, log_type: str, content: str) -> bool:
        try:
            log_dir = self.get_user_log_dir(username)
            today = datetime.now().strftime("%Y-%m-%d")
            log_file = log_dir / f"{log_type}_{today}.log"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {content}\n")
            return True
        except Exception as e:
            logger.error(f"写入用户日志失败 username={username}: {e}")
            return False

    # ------------------------------------------------------------------
    # 存储统计
    # ------------------------------------------------------------------

    def get_user_storage_stats(self, username: str) -> Dict[str, Any]:
        user_dir = self._get_user_dir(username)
        if not user_dir.exists():
            return {'total_size': 0, 'file_count': 0, 'breakdown': {}}

        def _dir_stats(path: Path):
            size, count = 0, 0
            if path.exists():
                for fp in path.rglob('*'):
                    if fp.is_file():
                        size += fp.stat().st_size
                        count += 1
            return size, count

        breakdown: Dict[str, Any] = {}
        total_size, total_files = 0, 0
        for subdir in [self.IMAGES_DIR, self.LOGS_DIR, self.UPLOADS_DIR, self.VOICE_SAMPLES_DIR]:
            s, c = _dir_stats(user_dir / subdir)
            breakdown[subdir] = {'size': s, 'file_count': c}
            total_size += s
            total_files += c

        # 单独统计 config.yaml
        cfg = user_dir / self.USER_CONFIG_FILE
        if cfg.exists():
            total_size += cfg.stat().st_size
            total_files += 1

        return {'total_size': total_size, 'file_count': total_files, 'breakdown': breakdown}

    # ------------------------------------------------------------------
    # 删除用户数据
    # ------------------------------------------------------------------

    def delete_user_data(self, username: str) -> bool:
        try:
            user_dir = self._get_user_dir(username)
            if user_dir.exists():
                shutil.rmtree(user_dir)
                logger.info(f"删除用户数据目录: {user_dir}")
            return True
        except Exception as e:
            logger.error(f"删除用户数据失败 username={username}: {e}")
            return False

    # ------------------------------------------------------------------
    # 兼容旧接口（按 user_id 操作，自动查 username）
    # ------------------------------------------------------------------

    def init_user_data_by_id(self, user_id: int, username: str) -> Path:
        """兼容旧调用：用 username 初始化目录"""
        return self.init_user_data(username)


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------

def _deep_merge(target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    """深度合并，source 覆盖 target，递归处理嵌套 dict"""
    import copy
    result = copy.deepcopy(target)
    for k, v in source.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = copy.deepcopy(v)
    return result


# 全局实例
user_data_manager = UserDataManager()
