"""
记忆系统API端点
"""

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json

from ..config import config
from ..memory import MemoryManager, MemoryConfig, MemoryItem, MemorySummary

router = APIRouter(prefix="/api", tags=["memory"])

# 共享MemoryManager实例
_memory_manager = None


def _build_memory_user_display(user: Any, fallback_user_id: str) -> str:
    """构造记忆系统用户展示串：项目用户名 + QQ号 + Linyu账号。"""
    username = str(getattr(user, "nickname", None) or getattr(user, "username", None) or fallback_user_id).strip()
    qq_id = str(getattr(user, "qq_user_id", None) or "").strip() or "-"
    linyu_account = str(getattr(user, "linyu_account", None) or getattr(user, "linyu_user_id", None) or "").strip() or "-"
    return f"{username} | QQ:{qq_id} | Linyu:{linyu_account}"


def _split_roleplay_memory_user_id(user_id: str) -> tuple[str, bool]:
    suffix = "::roleplay"
    raw = str(user_id or "")
    if raw.endswith(suffix):
        return raw[:-len(suffix)], True
    return raw, False

def get_memory_manager():
    """获取共享记忆管理器实例"""
    global _memory_manager
    if _memory_manager is None:
        # 从配置创建MemoryConfig
        memory_config_dict = config.get('memory', {})
        memory_config = MemoryConfig(**memory_config_dict)
        
        _memory_manager = MemoryManager(memory_config)
        
        # 异步初始化（这里简化处理，实际应该在应用启动时初始化）
        # 注意：FastAPI不支持在同步函数中直接运行async函数
        # 我们将在第一次请求时初始化，或者更好的方式是在应用启动事件中初始化
    return _memory_manager


async def ensure_memory_manager_initialized():
    """确保记忆管理器已初始化"""
    manager = get_memory_manager()
    # 检查是否已初始化
    if hasattr(manager, 'engine') and manager.engine is None:
        try:
            await manager.initialize()
            print("记忆管理器已初始化")
        except Exception as e:
            print(f"记忆管理器初始化失败: {e}")
            raise HTTPException(status_code=500, detail=f"记忆系统初始化失败: {str(e)}")
    return manager


# 请求/响应模型
class UpdateMemoryConfigRequest(BaseModel):
    """更新记忆配置请求"""
    config: Dict[str, Any]

class AddLongTermMemoryRequest(BaseModel):
    """添加长期记忆请求"""
    user_id: str
    content: str
    importance: float = 0.5
    metadata: Dict[str, Any] = {}

class SearchMemoriesRequest(BaseModel):
    """搜索记忆请求"""
    user_id: str
    query: str
    top_k: int = 3
    score_threshold: float = 0.5

class ClearMemoriesRequest(BaseModel):
    """清除记忆请求"""
    user_id: str
    session_id: Optional[str] = None

class UpdateLongTermMemoryRequest(BaseModel):
    """更新长期记忆请求"""
    content: Optional[str] = None
    importance: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

class BatchAddLongTermMemoriesRequest(BaseModel):
    """批量添加长期记忆请求"""
    user_id: str
    memories: List[Dict[str, Any]]  # 每个元素包含 content, importance, metadata

class BatchDeleteShortTermMemoriesRequest(BaseModel):
    """批量删除短期记忆请求"""
    user_id: str
    session_id: Optional[str] = None
    before_date: Optional[str] = None  # ISO格式日期字符串

class ExternalContextRequest(BaseModel):
    """外部记忆上下文请求"""
    user_id: str
    max_token_size: int = 500
    prefer_topics: Optional[List[str]] = None
    customize_context_prompt: Optional[str] = None


@router.get("/memory/config")
async def get_memory_config():
    """获取记忆系统配置"""
    try:
        memory_config_dict = config.get('memory', {})
        return {"config": memory_config_dict}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.post("/memory/config")
async def update_memory_config(request: UpdateMemoryConfigRequest):
    """更新记忆系统配置"""
    try:
        # 更新配置文件
        config.update_config('memory', request.config)
        
        # 重新初始化MemoryManager（下次请求时会使用新配置）
        global _memory_manager
        _memory_manager = None
        
        return {"message": "配置更新成功", "config": request.config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")


@router.get("/memory/users")
async def get_memory_users():
    """获取所有有记忆的用户ID列表，附带用户名/昵称信息"""
    try:
        manager = await ensure_memory_manager_initialized()
        user_ids = await manager.get_all_user_ids()

        # 尝试从用户管理器获取用户名映射
        user_info_list = []
        try:
            from backend.user import user_manager
            for uid in user_ids:
                base_uid, is_roleplay = _split_roleplay_memory_user_id(uid)
                info = {"user_id": uid, "display_name": uid, "selector_key": uid}
                # 尝试按 qq_user_id 查找
                user = await user_manager.get_user_by_qq_id(base_uid)
                if not user and base_uid.isdigit():
                    user = await user_manager.get_user_by_id(int(base_uid))
                if not user:
                    # 尝试按 username 查找
                    user = await user_manager.get_user_by_username(base_uid)
                if user:
                    display_name = _build_memory_user_display(user, uid)
                    if is_roleplay:
                        display_name = f"{display_name}（情景演绎）"
                    info["display_name"] = display_name
                    info["selector_key"] = display_name
                elif is_roleplay:
                    info["display_name"] = f"{base_uid}（情景演绎）"
                    info["selector_key"] = info["display_name"]
                user_info_list.append(info)
        except Exception:
            # 如果用户管理器不可用，回退到纯 ID 列表
            user_info_list = [{"user_id": uid, "display_name": uid, "selector_key": uid} for uid in user_ids]

        return {"user_ids": user_ids, "user_info": user_info_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取用户ID列表失败: {str(e)}")


@router.get("/memory/stats")
async def get_memory_stats():
    """获取记忆系统统计信息"""
    try:
        manager = await ensure_memory_manager_initialized()
        stats = await manager.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.get("/memory/short-term")
async def get_short_term_memories(
    user_id: str = Query(..., description="用户ID"),
    session_id: str = Query(..., description="会话ID"),
    limit: int = Query(50, description="最大返回数量")
):
    """获取短期记忆（对话历史）"""
    try:
        manager = await ensure_memory_manager_initialized()
        memories = await manager.get_short_term_memories(user_id, session_id, limit)
        return {"memories": memories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取短期记忆失败: {str(e)}")


@router.get("/memory/pending")
async def get_pending_memories(
    user_id: str = Query(..., description="用户ID"),
    session_id: str = Query(..., description="会话ID"),
    limit: int = Query(100, description="最大返回数量")
):
    """获取待处理区原文（超过短期窗口的对话原文）"""
    try:
        manager = await ensure_memory_manager_initialized()
        if not hasattr(manager, "get_pending_memories"):
            raise HTTPException(status_code=500, detail="当前记忆管理器不支持待处理区")
        memories = await manager.get_pending_memories(user_id=user_id, session_id=session_id, limit=limit)
        return {"memories": memories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取待处理区失败: {str(e)}")


@router.post("/memory/pending/summarize")
async def summarize_pending_memories(
    user_id: str = Query(..., description="用户ID"),
    session_id: str = Query(..., description="会话ID")
):
    """手动触发：摘要待处理区（若不足一个chunk则无操作）"""
    try:
        manager = await ensure_memory_manager_initialized()
        if not hasattr(manager, "summarize_pending_now"):
            raise HTTPException(status_code=500, detail="当前记忆管理器不支持待处理区摘要")
        result = await manager.summarize_pending_now(user_id=user_id, session_id=session_id, force=True)
        if isinstance(result, dict):
            return result
        return {"ok": bool(result), "processed": bool(result), "force": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"触发待处理区摘要失败: {str(e)}")


@router.get("/memory/mid-term")
async def get_mid_term_memories(
    user_id: str = Query(..., description="用户ID"),
    session_id: Optional[str] = Query(None, description="会话ID（可选）"),
    limit: int = Query(10, description="最大返回数量")
):
    """获取中期记忆（对话摘要）"""
    try:
        manager = await ensure_memory_manager_initialized()
        summaries = await manager.get_mid_term_summaries(user_id, session_id, limit)
        return {"summaries": summaries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取中期记忆失败: {str(e)}")


@router.get("/memory/long-term")
async def get_long_term_memories(
    user_id: str = Query(..., description="用户ID"),
    limit: int = Query(100, description="最大返回数量")
):
    """获取长期记忆"""
    try:
        manager = await ensure_memory_manager_initialized()
        memories = await manager.get_long_term_memories(user_id, limit)
        return {"memories": memories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取长期记忆失败: {str(e)}")


@router.post("/memory/long-term/search")
async def search_long_term_memories(request: SearchMemoriesRequest):
    """搜索长期记忆"""
    try:
        manager = await ensure_memory_manager_initialized()
        memories = await manager.search_long_term_memories(
            user_id=request.user_id,
            query=request.query,
            top_k=request.top_k,
            score_threshold=request.score_threshold
        )
        return {"memories": memories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索长期记忆失败: {str(e)}")


@router.post("/memory/long-term")
async def add_long_term_memory(request: AddLongTermMemoryRequest):
    """手动添加长期记忆"""
    try:
        manager = await ensure_memory_manager_initialized()
        success = await manager.add_long_term_memory(
            user_id=request.user_id,
            content=request.content,
            importance=request.importance,
            metadata=request.metadata
        )
        
        if success:
            return {"message": "长期记忆添加成功"}
        else:
            raise HTTPException(status_code=500, detail="长期记忆添加失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加长期记忆失败: {str(e)}")


@router.delete("/memory/long-term/{memory_id}")
async def delete_long_term_memory(memory_id: str):
    """删除长期记忆（简化实现，实际需要用户验证）"""
    try:
        manager = await ensure_memory_manager_initialized()
        if getattr(manager.config, "long_term_strategy", "local").lower() == "external":
            raise HTTPException(status_code=501, detail="外部记忆暂不支持删除操作")

        # 兼容不同类型的记忆管理器
        if hasattr(manager, 'vector_store') and manager.vector_store:
            # 原始MemoryManager使用vector_store
            success = await manager.vector_store.delete_memory(memory_id)
        elif hasattr(manager, '_delete_long_term_memory_by_id'):
            success = await manager._delete_long_term_memory_by_id(memory_id)
        else:
            raise HTTPException(status_code=500, detail="当前记忆管理器不支持删除操作")

        if success:
            return {"message": "记忆删除成功"}
        else:
            raise HTTPException(status_code=404, detail="记忆未找到")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除记忆失败: {str(e)}")


@router.put("/memory/long-term/{memory_id}")
async def update_long_term_memory(memory_id: str, request: UpdateLongTermMemoryRequest):
    """更新长期记忆（编辑内容和重要性）"""
    try:
        manager = await ensure_memory_manager_initialized()
        if getattr(manager.config, "long_term_strategy", "local").lower() == "external":
            raise HTTPException(status_code=501, detail="外部记忆暂不支持更新操作")

        # 兼容不同类型的记忆管理器
        if hasattr(manager, '_update_long_term_memory_by_id'):
            success = await manager._update_long_term_memory_by_id(
                memory_id=memory_id,
                content=request.content,
                importance=request.importance,
                metadata=request.metadata
            )
        else:
            raise HTTPException(status_code=500, detail="当前记忆管理器不支持更新操作")

        if success:
            return {"message": "记忆更新成功"}
        else:
            raise HTTPException(status_code=404, detail="记忆未找到")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新记忆失败: {str(e)}")


@router.post("/memory/batch/add-short-term")
async def batch_add_short_term_memories(
    user_id: str = Query(..., description="用户ID"),
    session_id: str = Query(..., description="会话ID"),
    messages: List[Dict[str, Any]] = Body(..., description="消息列表")
):
    """批量添加短期记忆"""
    try:
        from ..memory.models import ConversationMessage
        from datetime import datetime

        manager = await ensure_memory_manager_initialized()

        # 转换消息格式
        conversation_messages = []
        for msg in messages:
            conversation_messages.append(ConversationMessage(
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
                timestamp=datetime.fromisoformat(msg.get("timestamp", datetime.now().isoformat()))
            ))

        count = await manager.batch_add_short_term_memories(
            user_id=user_id,
            session_id=session_id,
            messages=conversation_messages
        )

        return {"message": f"已批量添加 {count} 条短期记忆", "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量添加短期记忆失败: {str(e)}")


@router.post("/memory/batch/add-long-term")
async def batch_add_long_term_memories(request: BatchAddLongTermMemoriesRequest):
    """批量添加长期记忆"""
    try:
        manager = await ensure_memory_manager_initialized()

        # 兼容不同类型的记忆管理器
        if hasattr(manager, 'add_long_term_memories_batch'):
            count = await manager.add_long_term_memories_batch(
                user_id=request.user_id,
                memories=request.memories
            )
            return {"message": f"已批量添加 {count} 条长期记忆", "count": count}
        else:
            raise HTTPException(status_code=500, detail="当前记忆管理器不支持批量添加操作")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量添加长期记忆失败: {str(e)}")


@router.post("/memory/batch/delete-short-term")
async def batch_delete_short_term_memories(request: BatchDeleteShortTermMemoriesRequest):
    """批量删除短期记忆"""
    try:
        manager = await ensure_memory_manager_initialized()

        from datetime import datetime
        before_date = None
        if request.before_date:
            before_date = datetime.fromisoformat(request.before_date)

        count = await manager.delete_short_term_memories_batch(
            user_id=request.user_id,
            session_id=request.session_id,
            before_date=before_date
        )

        return {"message": f"已批量删除 {count} 条短期记忆", "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量删除短期记忆失败: {str(e)}")


@router.post("/memory/clear")
async def clear_memories(request: ClearMemoriesRequest):
    """清除记忆"""
    try:
        manager = await ensure_memory_manager_initialized()
        success = await manager.clear_all_memories(
            user_id=request.user_id,
            session_id=request.session_id
        )
        
        if success:
            return {"message": "记忆清除成功"}
        else:
            raise HTTPException(status_code=500, detail="记忆清除失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除记忆失败: {str(e)}")


@router.get("/memory/test")
async def test_memory_system():
    """测试记忆系统连接"""
    try:
        manager = await ensure_memory_manager_initialized()
        stats = await manager.get_stats()
        return {
            "status": "正常",
            "stats": stats,
            "message": "记忆系统运行正常"
        }
    except Exception as e:
        return {
            "status": "异常",
            "error": str(e),
            "message": "记忆系统测试失败"
        }


@router.get("/memory/external/ping")
async def external_memory_ping():
    """测试外部记忆系统连接"""
    try:
        manager = await ensure_memory_manager_initialized()
        result = await manager.ping_external_memory()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"外部记忆连接失败: {str(e)}")


@router.get("/memory/external/profiles")
async def get_external_profiles(
    user_id: str = Query(..., description="用户ID")
):
    """获取外部记忆画像"""
    try:
        manager = await ensure_memory_manager_initialized()
        profiles = await manager.get_external_profiles(user_id=user_id)
        return {"profiles": profiles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取外部画像失败: {str(e)}")


@router.get("/memory/external/events")
async def get_external_events(
    user_id: str = Query(..., description="用户ID"),
    limit: int = Query(10, description="最大返回数量"),
    query: Optional[str] = Query(None, description="检索关键词（可选）")
):
    """获取外部记忆事件"""
    try:
        manager = await ensure_memory_manager_initialized()
        events = await manager.get_external_events(user_id=user_id, limit=limit, query=query)
        return {"events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取外部事件失败: {str(e)}")


@router.post("/memory/external/context")
async def get_external_context(request: ExternalContextRequest):
    """获取外部记忆上下文"""
    try:
        manager = await ensure_memory_manager_initialized()
        prefer_topics = request.prefer_topics
        if prefer_topics is None:
            prefer_topics = getattr(manager.config, "external_memory_prefer_topics", None)
        context = await manager.get_external_context(
            user_id=request.user_id,
            max_token_size=request.max_token_size,
            prefer_topics=prefer_topics,
            customize_context_prompt=request.customize_context_prompt
        )
        return {"context": context}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取外部上下文失败: {str(e)}")
