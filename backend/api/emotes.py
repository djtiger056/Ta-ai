from fastapi import APIRouter, HTTPException
from typing import Any, Dict, List, Optional
from pathlib import Path
from pydantic import BaseModel

from ..config import config
from ..emote import EmoteConfig, EmoteCategory, EmoteManager
from .bot_provider import get_bot, reset_bot

router = APIRouter(prefix="/api/emotes", tags=["emotes"])


class ScanFolderRequest(BaseModel):
    path: str
    file_extensions: Optional[List[str]] = None

_fallback_manager: Optional[EmoteManager] = None


def _get_manager() -> EmoteManager:
    """优先复用Bot上的管理器，避免配置不一致"""
    global _fallback_manager
    try:
        bot = get_bot()
        if bot and getattr(bot, "emote_manager", None):
            return bot.emote_manager
    except Exception:
        pass

    if _fallback_manager is None:
        emote_cfg = config.emote_config if hasattr(config, "emote_config") else EmoteConfig()
        _fallback_manager = EmoteManager(emote_cfg)
    return _fallback_manager


@router.get("/config")
async def get_emote_config():
    try:
        manager = _get_manager()
        return {
            "config": manager.config.dict(),
            "categories": manager.list_categories_info(),
            "base_path": str(manager.base_path),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取表情包配置失败: {str(e)}")


@router.post("/config")
async def update_emote_config(payload: Dict[str, Any]):
    """更新表情包配置并持久化"""
    try:
        new_config = EmoteConfig(**payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"配置格式错误: {str(e)}")

    try:
        manager = _get_manager()
        manager.update_config(new_config)
        config.update_config("emotes", new_config.dict())
        # 触发Bot实例刷新
        reset_bot()
        return {
            "success": True,
            "config": manager.config.dict(),
            "categories": manager.list_categories_info(),
            "base_path": str(manager.base_path),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存表情包配置失败: {str(e)}")


@router.post("/reload")
async def reload_emote_files():
    """重新扫描表情包目录"""
    try:
        manager = _get_manager()
        manager.refresh_files()
        return {
            "success": True,
            "categories": manager.list_categories_info(),
            "base_path": str(manager.base_path),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重载失败: {str(e)}")


@router.post("/scan-folder")
async def scan_emote_folder(request: ScanFolderRequest):
    """扫描指定文件夹，自动发现所有子文件夹作为表情包分类"""
    folder_path = Path(request.path)

    # 支持相对路径（相对于项目根目录）
    if not folder_path.is_absolute():
        project_root = Path(__file__).resolve().parent.parent
        folder_path = (project_root / folder_path).resolve()

    if not folder_path.exists():
        raise HTTPException(status_code=400, detail=f"路径不存在: {folder_path}")
    if not folder_path.is_dir():
        raise HTTPException(status_code=400, detail=f"路径不是文件夹: {folder_path}")

    extensions = request.file_extensions or ["png", "jpg", "jpeg", "gif", "webp"]
    discovered_categories = []

    try:
        for sub_dir in sorted(folder_path.iterdir()):
            if not sub_dir.is_dir():
                continue
            # 跳过隐藏文件夹
            if sub_dir.name.startswith("."):
                continue

            # 统计该子文件夹中的图片文件数
            file_count = 0
            sample_files = []
            for ext in extensions:
                for f in sub_dir.glob(f"*.{ext}"):
                    file_count += 1
                    if len(sample_files) < 5:
                        sample_files.append(f.name)
                for f in sub_dir.glob(f"*.{ext.upper()}"):
                    file_count += 1
                    if len(sample_files) < 5:
                        sample_files.append(f.name)

            discovered_categories.append({
                "name": sub_dir.name,
                "path": str(sub_dir),
                "file_count": file_count,
                "sample_files": sample_files,
                "keywords": [],
                "weight": 1.0,
                "enabled": True,
            })
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=f"无权限访问: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"扫描失败: {str(e)}")

    return {
        "success": True,
        "base_path": str(folder_path),
        "categories": discovered_categories,
        "total_categories": len(discovered_categories),
        "total_files": sum(c["file_count"] for c in discovered_categories),
    }
