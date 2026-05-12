"""用户数据文件管理器

管理每个用户的个人数据文件夹，包括：
- configs/  用户配置文件
- images/   用户图片（图生图等）
- logs/     用户日志
- uploads/  用户上传的文件
"""
import os
import json
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class UserDataManager:
    """用户数据文件管理器"""
    
    def __init__(self, base_path: Optional[str] = None):
        """初始化用户数据管理器
        
        Args:
            base_path: 用户数据根目录，默认为项目根目录下的 user_data
        """
        if base_path:
            self.base_path = Path(base_path)
        else:
            # 默认使用项目根目录下的 user_data
            project_root = Path(__file__).resolve().parents[2]
            self.base_path = project_root / "user_data"
        
        # 确保根目录存在
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # 子目录名称
        self.CONFIGS_DIR = "configs"
        self.IMAGES_DIR = "images"
        self.LOGS_DIR = "logs"
        self.UPLOADS_DIR = "uploads"
        self.VOICE_SAMPLES_DIR = "voice_samples"
    
    def _get_user_dir(self, user_id: int) -> Path:
        """获取用户数据目录路径"""
        return self.base_path / str(user_id)
    
    def _ensure_user_dirs(self, user_id: int) -> Path:
        """确保用户的所有子目录都存在"""
        user_dir = self._get_user_dir(user_id)
        
        # 创建所有子目录
        subdirs = [
            self.CONFIGS_DIR,
            self.IMAGES_DIR,
            self.LOGS_DIR,
            self.UPLOADS_DIR,
            self.VOICE_SAMPLES_DIR,
        ]
        
        for subdir in subdirs:
            (user_dir / subdir).mkdir(parents=True, exist_ok=True)
        
        return user_dir
    
    def init_user_data(self, user_id: int) -> Path:
        """初始化用户数据目录
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户数据目录路径
        """
        user_dir = self._ensure_user_dirs(user_id)
        logger.info(f"初始化用户数据目录: {user_dir}")
        return user_dir
    
    def get_user_config_path(self, user_id: int, config_name: str = "config.json") -> Path:
        """获取用户配置文件路径
        
        Args:
            user_id: 用户ID
            config_name: 配置文件名
            
        Returns:
            配置文件路径
        """
        self._ensure_user_dirs(user_id)
        return self._get_user_dir(user_id) / self.CONFIGS_DIR / config_name
    
    def save_user_config(self, user_id: int, config: Dict[str, Any], config_name: str = "config.json") -> bool:
        """保存用户配置到文件
        
        Args:
            user_id: 用户ID
            config: 配置字典
            config_name: 配置文件名
            
        Returns:
            是否保存成功
        """
        try:
            config_path = self.get_user_config_path(user_id, config_name)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info(f"保存用户配置: user_id={user_id}, path={config_path}")
            return True
        except Exception as e:
            logger.error(f"保存用户配置失败: {e}")
            return False
    
    def load_user_config(self, user_id: int, config_name: str = "config.json") -> Optional[Dict[str, Any]]:
        """加载用户配置文件
        
        Args:
            user_id: 用户ID
            config_name: 配置文件名
            
        Returns:
            配置字典，如果不存在则返回None
        """
        try:
            config_path = self.get_user_config_path(user_id, config_name)
            if not config_path.exists():
                return None
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载用户配置失败: {e}")
            return None
    
    def get_user_image_dir(self, user_id: int) -> Path:
        """获取用户图片目录"""
        self._ensure_user_dirs(user_id)
        return self._get_user_dir(user_id) / self.IMAGES_DIR
    
    def save_user_image(self, user_id: int, image_data: bytes, filename: str) -> Optional[Path]:
        """保存用户图片
        
        Args:
            user_id: 用户ID
            image_data: 图片二进制数据
            filename: 文件名
            
        Returns:
            保存的文件路径，失败返回None
        """
        try:
            image_dir = self.get_user_image_dir(user_id)
            image_path = image_dir / filename
            with open(image_path, 'wb') as f:
                f.write(image_data)
            logger.info(f"保存用户图片: user_id={user_id}, path={image_path}")
            return image_path
        except Exception as e:
            logger.error(f"保存用户图片失败: {e}")
            return None
    
    def list_user_images(self, user_id: int) -> List[Dict[str, Any]]:
        """列出用户的所有图片
        
        Args:
            user_id: 用户ID
            
        Returns:
            图片信息列表
        """
        try:
            image_dir = self.get_user_image_dir(user_id)
            images = []
            for file_path in image_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    stat = file_path.stat()
                    images.append({
                        'filename': file_path.name,
                        'path': str(file_path),
                        'size': stat.st_size,
                        'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    })
            return sorted(images, key=lambda x: x['modified_at'], reverse=True)
        except Exception as e:
            logger.error(f"列出用户图片失败: {e}")
            return []
    
    def delete_user_image(self, user_id: int, filename: str) -> bool:
        """删除用户图片
        
        Args:
            user_id: 用户ID
            filename: 文件名
            
        Returns:
            是否删除成功
        """
        try:
            image_path = self.get_user_image_dir(user_id) / filename
            if image_path.exists():
                image_path.unlink()
                logger.info(f"删除用户图片: user_id={user_id}, filename={filename}")
                return True
            return False
        except Exception as e:
            logger.error(f"删除用户图片失败: {e}")
            return False
    
    def get_user_upload_dir(self, user_id: int) -> Path:
        """获取用户上传目录"""
        self._ensure_user_dirs(user_id)
        return self._get_user_dir(user_id) / self.UPLOADS_DIR
    
    def save_user_upload(self, user_id: int, file_data: bytes, filename: str) -> Optional[Path]:
        """保存用户上传的文件
        
        Args:
            user_id: 用户ID
            file_data: 文件二进制数据
            filename: 文件名
            
        Returns:
            保存的文件路径，失败返回None
        """
        try:
            upload_dir = self.get_user_upload_dir(user_id)
            file_path = upload_dir / filename
            with open(file_path, 'wb') as f:
                f.write(file_data)
            logger.info(f"保存用户上传文件: user_id={user_id}, path={file_path}")
            return file_path
        except Exception as e:
            logger.error(f"保存用户上传文件失败: {e}")
            return None
    
    def get_user_voice_sample_dir(self, user_id: int) -> Path:
        """获取用户语音样本目录"""
        self._ensure_user_dirs(user_id)
        return self._get_user_dir(user_id) / self.VOICE_SAMPLES_DIR
    
    def save_voice_sample(self, user_id: int, audio_data: bytes, filename: str) -> Optional[Path]:
        """保存用户语音样本
        
        Args:
            user_id: 用户ID
            audio_data: 音频二进制数据
            filename: 文件名
            
        Returns:
            保存的文件路径，失败返回None
        """
        try:
            voice_dir = self.get_user_voice_sample_dir(user_id)
            file_path = voice_dir / filename
            with open(file_path, 'wb') as f:
                f.write(audio_data)
            logger.info(f"保存用户语音样本: user_id={user_id}, path={file_path}")
            return file_path
        except Exception as e:
            logger.error(f"保存用户语音样本失败: {e}")
            return None
    
    def get_user_log_dir(self, user_id: int) -> Path:
        """获取用户日志目录"""
        self._ensure_user_dirs(user_id)
        return self._get_user_dir(user_id) / self.LOGS_DIR
    
    def append_user_log(self, user_id: int, log_type: str, content: str) -> bool:
        """追加用户日志
        
        Args:
            user_id: 用户ID
            log_type: 日志类型（如 chat, error, activity）
            content: 日志内容
            
        Returns:
            是否写入成功
        """
        try:
            log_dir = self.get_user_log_dir(user_id)
            today = datetime.now().strftime("%Y-%m-%d")
            log_file = log_dir / f"{log_type}_{today}.log"
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_line = f"[{timestamp}] {content}\n"
            
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_line)
            return True
        except Exception as e:
            logger.error(f"写入用户日志失败: {e}")
            return False
    
    def get_user_storage_stats(self, user_id: int) -> Dict[str, Any]:
        """获取用户存储统计信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            存储统计信息
        """
        user_dir = self._get_user_dir(user_id)
        if not user_dir.exists():
            return {
                'total_size': 0,
                'file_count': 0,
                'breakdown': {}
            }
        
        def get_dir_size(path: Path) -> tuple:
            total_size = 0
            file_count = 0
            if path.exists():
                for file_path in path.rglob('*'):
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
                        file_count += 1
            return total_size, file_count
        
        breakdown = {}
        total_size = 0
        total_files = 0
        
        for subdir in [self.CONFIGS_DIR, self.IMAGES_DIR, self.LOGS_DIR, self.UPLOADS_DIR, self.VOICE_SAMPLES_DIR]:
            size, count = get_dir_size(user_dir / subdir)
            breakdown[subdir] = {'size': size, 'file_count': count}
            total_size += size
            total_files += count
        
        return {
            'total_size': total_size,
            'file_count': total_files,
            'breakdown': breakdown
        }
    
    def delete_user_data(self, user_id: int) -> bool:
        """删除用户的所有数据
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否删除成功
        """
        try:
            user_dir = self._get_user_dir(user_id)
            if user_dir.exists():
                shutil.rmtree(user_dir)
                logger.info(f"删除用户数据目录: user_id={user_id}")
            return True
        except Exception as e:
            logger.error(f"删除用户数据失败: {e}")
            return False


# 全局用户数据管理器实例
user_data_manager = UserDataManager()
