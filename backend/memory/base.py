"""
记忆管理器基类
提取 MemoryManager 的公共代码
"""

import asyncio
import json
import re
import uuid
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from abc import ABC, abstractmethod
from functools import lru_cache
from hashlib import md5
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from sqlalchemy import func
from backend.utils.datetime_utils import get_now, to_isoformat, ensure_timezone

from .models import (
    MemoryConfig, MemoryItemDB, MemorySummaryDB,
    MemoryItem, MemorySummary, ConversationMessage, ReminderItemDB, MemorySessionStateDB, Base
)
from .summarizer import LLMSummarizer


logger = logging.getLogger(__name__)


class BaseMemoryManager(ABC):
    """记忆管理器基类"""

    def __init__(self, config: MemoryConfig, db_url: str = None):
        """
        初始化记忆管理器

        Args:
            config: 记忆配置
            db_url: 数据库URL，默认使用SQLite
        """
        self.config = config
        if db_url:
            self.db_url = db_url
        else:
            # 固定到项目根目录的数据文件，避免因启动目录不同导致读取到空库
            from pathlib import Path
            project_root = Path(__file__).resolve().parents[2]
            db_path = (project_root / "data" / "lfbot.db").as_posix()
            self.db_url = f"sqlite+aiosqlite:///{db_path}"
        self.engine = None
        self.async_session = None

        # 会话状态跟踪
        self.session_states: Dict[str, Dict[str, Any]] = {}  # session_id -> state

        # LRU缓存（用于缓存查询结果）
        self._cache: Dict[str, Tuple[Any, float]] = {}  # key -> (value, timestamp)
        self._cache_max_size = 100  # 最大缓存条目数
        self._cache_ttl = 300  # 缓存过期时间（秒）

        # 会话级锁与后台摘要任务
        self._session_locks: Dict[str, asyncio.Lock] = {}
        self._pending_summary_tasks: Dict[str, asyncio.Task] = {}

    @abstractmethod
    async def initialize(self):
        """异步初始化记忆管理器"""
        pass

    @abstractmethod
    async def add_long_term_memory(self, user_id: str, content: str,
                                 importance: float = None,
                                 metadata: Dict[str, Any] = None) -> bool:
        """添加长期记忆（子类实现）"""
        pass

    @abstractmethod
    async def search_long_term_memories(self, user_id: str, query: str,
                                      top_k: int = None,
                                      score_threshold: float = None) -> List[Dict[str, Any]]:
        """搜索长期记忆（子类实现）"""
        pass

    @abstractmethod
    async def get_long_term_memories(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取用户的长期记忆（子类实现）"""
        pass

    # ========== 兼容层（对齐 API/测试命名）==========

    async def batch_add_short_term_memories(self, user_id: str, session_id: str,
                                           messages: List[ConversationMessage]) -> int:
        """兼容别名：批量添加短期记忆"""
        return await self.add_short_term_memories_batch(user_id=user_id, session_id=session_id, messages=messages)

    async def batch_add_long_term_memories(self, user_id: str, memories: List[Dict[str, Any]]) -> int:
        """兼容别名：批量添加长期记忆（优先走批量接口，否则逐条写入）"""
        if hasattr(self, "add_long_term_memories_batch"):
            return await self.add_long_term_memories_batch(user_id=user_id, memories=memories)
        count = 0
        for mem in memories:
            ok = await self.add_long_term_memory(
                user_id=user_id,
                content=mem.get("content", ""),
                importance=mem.get("importance"),
                metadata=mem.get("metadata") or mem.get("meta_data")
            )
            if ok:
                count += 1
        return count


    async def delete_long_term_memory(self, memory_id: str) -> bool:
        """兼容别名：删除长期记忆"""
        if hasattr(self, "_delete_long_term_memory_by_id"):
            return await self._delete_long_term_memory_by_id(memory_id)
        return False

    async def update_long_term_memory(self, memory_id: str, content: Optional[str] = None,
                                      importance: Optional[float] = None,
                                      metadata: Optional[Dict[str, Any]] = None) -> bool:
        """兼容别名：更新长期记忆"""
        if hasattr(self, "_update_long_term_memory_by_id"):
            return await self._update_long_term_memory_by_id(
                memory_id=memory_id,
                content=content,
                importance=importance,
                metadata=metadata
            )
        return False

    # ========== 缓存管理（公共方法）==========

    def _make_cache_key(self, *args) -> str:
        """生成缓存键"""
        key_str = "|".join(str(arg) for arg in args)
        return md5(key_str.encode()).hexdigest()

    def _get_cache(self, key: str) -> Optional[Any]:
        """获取缓存"""
        import time
        if key in self._cache:
            value, timestamp = self._cache[key]
            # 检查缓存是否过期
            if time.time() - timestamp < self._cache_ttl:
                return value
            else:
                # 缓存过期，删除
                del self._cache[key]
        return None

    def _set_cache(self, key: str, value: Any):
        """设置缓存"""
        import time
        # 如果缓存已满，删除最旧的条目
        if len(self._cache) >= self._cache_max_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

        self._cache[key] = (value, time.time())

    def _clear_cache(self, pattern: str = None):
        """清除缓存（可选按模式匹配）"""
        if pattern is None:
            # 清除所有缓存
            self._cache.clear()
        else:
            # 清除匹配模式的缓存
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]

    # ========== 数据库初始化（公共方法）==========

    async def _init_database(self):
        """初始化数据库"""
        try:
            from pathlib import Path
            db_path = Path(self.db_url.replace('sqlite+aiosqlite:///', ''))
            if db_path.parent:
                db_path.parent.mkdir(parents=True, exist_ok=True)

            self.engine = create_async_engine(
                self.db_url,
                echo=False,
                future=True,
                pool_pre_ping=True
            )

            # 创建表
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            self.async_session = sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            logger.info("记忆数据库初始化成功")
        except Exception as e:
            print(f"记忆数据库初始化失败: {e}")
            raise

    # ========== 短期记忆相关方法（公共方法） ==========

    async def add_short_term_memory(self, user_id: str, session_id: str,
                                  message: ConversationMessage) -> bool:
        """
        添加短期记忆（对话消息）

        Args:
            user_id: 用户ID
            session_id: 会话ID
            message: 对话消息

        Returns:
            是否成功
        """
        if not self.config.short_term_enabled:
            return False

        if self.async_session is None:
            return False

        try:
            async with self.async_session() as session:
                # 递增并持久化会话游标（避免重启后轮次/摘要错乱）
                message_index, round_index = await self._bump_session_counters(
                    session=session,
                    user_id=user_id,
                    session_id=session_id,
                    role=message.role
                )

                # 创建短期记忆项（原文）
                memory_item = MemoryItemDB(
                    user_id=user_id,
                    session_id=session_id,
                    content=json.dumps({
                        "role": message.role,
                        "content": message.content,
                        "timestamp": message.timestamp.isoformat()
                    }, ensure_ascii=False),
                    memory_type="short_term",
                    meta_data={
                        "message_index": message_index,
                        "round_index": round_index,
                        "auto_clean": True
                    }
                )
                session.add(memory_item)
                await session.commit()

            # 清除相关缓存
            self._clear_cache(f"short_term:{user_id}:{session_id}")

            # 新流水线：短期窗口裁剪→进入待处理→后台摘要→抽取长期事实
            if getattr(self.config, "pipeline_enabled", False):
                await self._pipeline_after_message_added(user_id=user_id, session_id=session_id, role=message.role)
            else:
                # 旧逻辑：规则摘要 + 启发式长期抽取
                await self._check_and_generate_summary(session_id, user_id)
                if getattr(self.config, "legacy_auto_extract_enabled", True):
                    await self._extract_important_memories(session_id, user_id)

            return True
        except Exception as e:
            print(f"添加短期记忆失败: {e}")
            return False

    async def _bump_session_counters(self, session: AsyncSession, user_id: str, session_id: str,
                                    role: str) -> Tuple[int, int]:
        """
        递增并持久化会话计数器。

        - message_count: 每条消息+1
        - round_count: 以 user 消息为“新一轮”起点

        Returns:
            (message_index, round_index)
        """
        stmt = select(MemorySessionStateDB).where(
            MemorySessionStateDB.user_id == user_id,
            MemorySessionStateDB.session_id == session_id
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()

        if row is None:
            row = MemorySessionStateDB(
                user_id=user_id,
                session_id=session_id,
                message_count=0,
                round_count=0
            )
            session.add(row)
            await session.flush()

        row.message_count = int(row.message_count or 0) + 1
        if role == "user":
            row.round_count = int(row.round_count or 0) + 1

        row.updated_at = get_now()
        await session.flush()
        return int(row.message_count), int(row.round_count or 0)

    def _effective_keep_rounds(self) -> int:
        keep = getattr(self.config, "short_term_keep_rounds", None)
        if keep is None:
            keep = getattr(self.config, "short_term_max_rounds", 20)
        try:
            keep = int(keep)
        except Exception:
            keep = 20
        return max(1, keep)

    def _pending_chunk_messages(self) -> int:
        rounds = getattr(self.config, "pending_chunk_rounds", 20)
        try:
            rounds = int(rounds)
        except Exception:
            rounds = 20
        rounds = max(1, rounds)
        return rounds * 2

    def _get_session_lock(self, user_id: str, session_id: str) -> asyncio.Lock:
        key = f"{user_id}_{session_id}"
        lock = self._session_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._session_locks[key] = lock
        return lock

    async def _pipeline_after_message_added(self, user_id: str, session_id: str, role: str):
        if not getattr(self.config, "pending_enabled", True):
            return

        # 1) 把超出短期窗口的原文滚入待处理区
        await self._roll_short_term_to_pending(user_id=user_id, session_id=session_id)

        # 2) 仅在“一轮完成后”（assistant 输出后）尝试触发摘要，避免半轮入摘要
        if role != "assistant":
            return

        if not getattr(self.config, "summarizer_enabled", False):
            return

        key = f"{user_id}_{session_id}"
        task = self._pending_summary_tasks.get(key)
        if task and not task.done():
            return

        self._pending_summary_tasks[key] = asyncio.create_task(
            self._summarize_pending_loop(user_id=user_id, session_id=session_id, force=False)
        )

    async def _roll_short_term_to_pending(self, user_id: str, session_id: str):
        """将超出短期窗口的短期原文迁移到待处理区（不丢失原文）"""
        if self.async_session is None or not self.config.short_term_enabled:
            return

        keep_messages = self._effective_keep_rounds() * 2

        async with self.async_session() as session:
            # 当前短期消息总数
            count_stmt = select(func.count(MemoryItemDB.id)).where(
                MemoryItemDB.user_id == user_id,
                MemoryItemDB.session_id == session_id,
                MemoryItemDB.memory_type == "short_term"
            )
            count_result = await session.execute(count_stmt)
            total = int(count_result.scalar() or 0)
            extra = total - keep_messages
            if extra <= 0:
                return

            # 找到最旧的 extra 条短期原文，迁移到 pending
            ids_stmt = select(MemoryItemDB.id).where(
                MemoryItemDB.user_id == user_id,
                MemoryItemDB.session_id == session_id,
                MemoryItemDB.memory_type == "short_term"
            ).order_by(MemoryItemDB.id.asc()).limit(extra)
            ids_result = await session.execute(ids_stmt)
            ids = [row[0] for row in ids_result.all()]
            if not ids:
                return

            mem_stmt = select(MemoryItemDB).where(MemoryItemDB.id.in_(ids))
            mem_result = await session.execute(mem_stmt)
            items = mem_result.scalars().all()
            for item in items:
                item.memory_type = "pending"
            await session.commit()

        # 清缓存（短期/待处理相关）
        self._clear_cache(f"short_term:{user_id}:{session_id}")
        self._clear_cache(f"pending:{user_id}:{session_id}")

    async def get_pending_memories(self, user_id: str, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取待处理区原文（用于调试/可视化）"""
        if self.async_session is None:
            return []
        cache_key = self._make_cache_key("pending", user_id, session_id, limit)
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        try:
            async with self.async_session() as session:
                stmt = select(MemoryItemDB).where(
                    MemoryItemDB.user_id == user_id,
                    MemoryItemDB.session_id == session_id,
                    MemoryItemDB.memory_type == "pending"
                ).order_by(MemoryItemDB.id.asc()).limit(limit)
                result = await session.execute(stmt)
                memories = result.scalars().all()
                items: List[Dict[str, Any]] = []
                for mem in memories:
                    mem_dict = mem.to_dict()
                    try:
                        mem_dict["message"] = json.loads(mem_dict["content"])
                    except Exception:
                        mem_dict["message"] = {"role": "unknown", "content": mem_dict["content"]}
                    items.append(mem_dict)
                self._set_cache(cache_key, items)
                return items
        except Exception as e:
            print(f"获取待处理区失败: {e}")
            return []

    async def summarize_pending_now(self, user_id: str, session_id: str, force: bool = True) -> Dict[str, Any]:
        """手动触发：摘要待处理区（默认强制处理不足一个chunk的剩余内容）"""
        if not getattr(self.config, "pipeline_enabled", False):
            return {
                "ok": False,
                "processed": False,
                "reason": "pipeline_disabled",
                "force": bool(force),
            }
        if not getattr(self.config, "summarizer_enabled", False):
            return {
                "ok": False,
                "processed": False,
                "reason": "summarizer_disabled",
                "force": bool(force),
            }

        loop_result = await self._summarize_pending_loop(user_id=user_id, session_id=session_id, force=force)
        processed_batches = int((loop_result or {}).get("processed_batches", 0) or 0)
        recovered_count = int((loop_result or {}).get("recovered_pending_processing", 0) or 0)
        return {
            "ok": True,
            "processed": processed_batches > 0,
            "processed_batches": processed_batches,
            "recovered_pending_processing": recovered_count,
            "force": bool(force),
        }

    async def _recover_pending_processing(self, user_id: str, session_id: str) -> int:
        """恢复异常残留的 pending_processing 为 pending（用于手动修复）"""
        if self.async_session is None:
            return 0

        recovered = 0
        async with self.async_session() as session:
            stmt = select(MemoryItemDB).where(
                MemoryItemDB.user_id == user_id,
                MemoryItemDB.session_id == session_id,
                MemoryItemDB.memory_type == "pending_processing"
            )
            result = await session.execute(stmt)
            items = result.scalars().all()
            for it in items:
                it.memory_type = "pending"
                meta = dict(it.meta_data or {})
                meta.pop("batch_id", None)
                it.meta_data = meta
                recovered += 1

            if recovered > 0:
                await session.commit()

        if recovered > 0:
            self._clear_cache(f"pending:{user_id}:{session_id}")
        return recovered

    async def _summarize_pending_loop(self, user_id: str, session_id: str, force: bool = False):
        """后台摘要：按chunk消费pending，生成摘要并（可选）删除原文，抽取长期事实"""
        result_info = {
            "processed_batches": 0,
            "recovered_pending_processing": 0,
        }
        if self.async_session is None:
            return result_info

        lock = self._get_session_lock(user_id, session_id)
        async with lock:
            if force:
                result_info["recovered_pending_processing"] = await self._recover_pending_processing(
                    user_id=user_id,
                    session_id=session_id,
                )

            chunk_size = self._pending_chunk_messages()

            while True:
                # 取最旧的一批 pending
                async with self.async_session() as session:
                    count_stmt = select(func.count(MemoryItemDB.id)).where(
                        MemoryItemDB.user_id == user_id,
                        MemoryItemDB.session_id == session_id,
                        MemoryItemDB.memory_type == "pending"
                    )
                    count_result = await session.execute(count_stmt)
                    pending_total = int(count_result.scalar() or 0)
                    min_required = 1 if force else chunk_size
                    if pending_total < min_required:
                        return result_info

                    fetch_size = min(chunk_size, pending_total) if force else chunk_size

                    stmt = select(MemoryItemDB).where(
                        MemoryItemDB.user_id == user_id,
                        MemoryItemDB.session_id == session_id,
                        MemoryItemDB.memory_type == "pending"
                    ).order_by(MemoryItemDB.id.asc()).limit(fetch_size)
                    result = await session.execute(stmt)
                    batch_items = result.scalars().all()
                    if len(batch_items) < fetch_size:
                        return result_info

                    batch_id = uuid.uuid4().hex
                    batch_item_ids = [it.id for it in batch_items]
                    for item in batch_items:
                        item.memory_type = "pending_processing"
                        meta = dict(item.meta_data or {})
                        meta["batch_id"] = batch_id
                        item.meta_data = meta
                    await session.commit()

                # 调用摘要器（LLM）
                conversations: List[Dict[str, str]] = []
                for item in batch_items:
                    try:
                        payload = json.loads(item.content)
                        role = payload.get("role", "unknown")
                        content = payload.get("content", "")
                        # 过滤空 content，避免脏数据污染摘要输入
                        if not content or not content.strip():
                            continue
                        conversations.append({"role": role, "content": content})
                    except Exception:
                        continue

                overlap_tail: List[Dict[str, str]] = []
                overlap_n = int(getattr(self.config, "pending_overlap_messages", 0) or 0)
                if overlap_n > 0:
                    try:
                        async with self.async_session() as session:
                            tail_stmt = select(MemoryItemDB).where(
                                MemoryItemDB.user_id == user_id,
                                MemoryItemDB.session_id == session_id,
                                MemoryItemDB.memory_type == "archived"
                            ).order_by(MemoryItemDB.id.desc()).limit(overlap_n)
                            tail_result = await session.execute(tail_stmt)
                            tail_items = list(reversed(tail_result.scalars().all()))
                            for t in tail_items:
                                try:
                                    payload = json.loads(t.content)
                                    overlap_tail.append({"role": payload.get("role", "unknown"), "content": payload.get("content", "")})
                                except Exception:
                                    continue
                    except Exception:
                        overlap_tail = []

                summary_text = None
                extracted_facts = []
                summarizer_meta: Dict[str, Any] = {}
                try:
                    summarizer_cfg = getattr(self.config, "summarizer_llm", None)
                    if summarizer_cfg is None:
                        summarizer_cfg = {}

                    # 允许“完全不配置专用摘要LLM”时回退到全局 llm（开箱即用）
                    # 但如果用户已经显式填写了 provider/model/api_base/api_key 的任意一项，则视为想独立配置：
                    # 缺关键字段时直接报错，避免默默回退造成“以为用了摘要LLM但实际没用”的错觉。
                    explicit = any(
                        (summarizer_cfg or {}).get(k) not in (None, "", {})
                        for k in ("provider", "model", "api_base", "api_key")
                    )
                    if not explicit:
                        try:
                            from ..config import config as app_config
                            summarizer_cfg = app_config.llm_config
                        except Exception:
                            summarizer_cfg = summarizer_cfg or {}
                    else:
                        if not (summarizer_cfg.get("provider") and summarizer_cfg.get("model") and summarizer_cfg.get("api_key")):
                            raise ValueError("摘要LLM配置不完整：需要 provider/model/api_key（或清空 summarizer_llm 以回退全局 llm）")
                    summarizer = LLMSummarizer(summarizer_cfg)
                    summary_text, extracted_facts, summarizer_meta = await summarizer.summarize_and_extract(
                        conversations=conversations,
                        overlap_tail=overlap_tail,
                        max_facts=int(getattr(self.config, "summarizer_max_facts", 20) or 20)
                    )
                except Exception as e:
                    print(f"摘要LLM调用失败（batch={batch_id}）: {e}")
                    # 失败回退：把 processing 恢复为 pending
                    async with self.async_session() as session:
                        stmt = select(MemoryItemDB).where(
                            MemoryItemDB.id.in_(batch_item_ids),
                            MemoryItemDB.memory_type == "pending_processing"
                        )
                        result = await session.execute(stmt)
                        items = result.scalars().all()
                        for it in items:
                            it.memory_type = "pending"
                            meta = dict(it.meta_data or {})
                            meta.pop("batch_id", None)
                            it.meta_data = meta
                        await session.commit()
                    return result_info

                # 写入中期摘要 + 抽取长期事实 + 清理原文
                async with self.async_session() as session:
                    # 重新加载该 batch 的 items（避免跨会话对象状态）
                    stmt = select(MemoryItemDB).where(
                        MemoryItemDB.id.in_(batch_item_ids),
                        MemoryItemDB.memory_type == "pending_processing"
                    )
                    result = await session.execute(stmt)
                    processing_items = result.scalars().all()
                    if not processing_items:
                        return result_info
                    processing_items.sort(key=lambda it: it.id or 0)

                    # 计算范围（优先用 message_index；否则用 id）
                    first = processing_items[0]
                    last = processing_items[-1]
                    start_idx = (first.meta_data or {}).get("message_index") or first.id
                    end_idx = (last.meta_data or {}).get("message_index") or last.id
                    conversation_range = f"{start_idx}-{end_idx}"

                    final_summary = (summary_text or "").strip()
                    if self.config.summary_max_length and len(final_summary) > int(self.config.summary_max_length):
                        final_summary = final_summary[: int(self.config.summary_max_length)]

                    summary_row = MemorySummaryDB(
                        user_id=user_id,
                        session_id=session_id,
                        summary=final_summary,
                        conversation_range=conversation_range,
                        meta_data={
                            "batch_id": batch_id,
                            "source_count": len(processing_items),
                            "source_ids": [it.id for it in processing_items],
                            "summarizer_meta": summarizer_meta,
                            "facts_count": len(extracted_facts),
                        }
                    )
                    session.add(summary_row)
                    await session.commit()

                    # 清理旧摘要
                    await self._cleanup_old_summaries(user_id, session_id)

                    delete_after = bool(getattr(self.config, "pending_delete_after_summary", True))
                    for it in processing_items:
                        if delete_after:
                            await session.delete(it)
                        else:
                            it.memory_type = "archived"
                            meta = dict(it.meta_data or {})
                            meta.pop("batch_id", None)
                            it.meta_data = meta
                    await session.commit()

                # 抽取的长期事实入库（在 DB 提交之后做，避免影响摘要/清理的原子性）
                await self._ingest_extracted_facts(
                    user_id=user_id,
                    session_id=session_id,
                    conversation_range=conversation_range,
                    facts=extracted_facts
                )

                self._clear_cache(f"pending:{user_id}:{session_id}")
                result_info["processed_batches"] = int(result_info["processed_batches"] or 0) + 1

    async def _ingest_extracted_facts(self, user_id: str, session_id: str, conversation_range: str, facts: List[Any]):
        if not self.config.long_term_enabled:
            return

        threshold = getattr(self.config, "summarizer_fact_min_importance", None)
        if threshold is None:
            threshold = getattr(self.config, "importance_threshold", 0.75)
        try:
            threshold = float(threshold)
        except Exception:
            threshold = 0.75

        to_add: List[Dict[str, Any]] = []
        for f in facts or []:
            try:
                importance = float(getattr(f, "importance", 0.0))
            except Exception:
                continue
            if importance < threshold:
                continue
            content = str(getattr(f, "text", "") or "").strip()
            if not content:
                continue
            metadata = {
                "source": "summarizer",
                "session_id": session_id,
                "conversation_range": conversation_range,
                "importance": importance,
                "tags": list(getattr(f, "tags", []) or []),
                "compression": getattr(f, "compression", "compress"),
                "evidence": list(getattr(f, "evidence", []) or []),
            }
            to_add.append({"content": content, "importance": importance, "metadata": metadata})

        if not to_add:
            return

        # 兼容不同实现：优先批量写入
        if hasattr(self, "add_long_term_memories_batch"):
            try:
                await self.add_long_term_memories_batch(user_id=user_id, memories=to_add)
                return
            except Exception:
                pass

        for item in to_add:
            try:
                await self.add_long_term_memory(
                    user_id=user_id,
                    content=item["content"],
                    importance=item["importance"],
                    metadata=item["metadata"]
                )
            except Exception as e:
                print(f"写入长期事实失败: {e}")

    async def get_short_term_memories(self, user_id: str, session_id: str,
                                    limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取短期记忆（最近的对话）

        Args:
            user_id: 用户ID
            session_id: 会话ID
            limit: 最大返回数量

        Returns:
            短期记忆列表
        """
        if not self.config.short_term_enabled:
            return []

        if self.async_session is None:
            return []

        # 尝试从缓存获取
        cache_key = self._make_cache_key("short_term", user_id, session_id, limit)
        cached_result = self._get_cache(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            async with self.async_session() as session:
                stmt = select(MemoryItemDB).where(
                    MemoryItemDB.user_id == user_id,
                    MemoryItemDB.session_id == session_id,
                    MemoryItemDB.memory_type == "short_term"
                ).order_by(MemoryItemDB.id.desc()).limit(limit)

                result = await session.execute(stmt)
                memories = result.scalars().all()

                # 转换为字典并解析内容
                memory_list = []
                for mem in memories:
                    mem_dict = mem.to_dict()
                    try:
                        content_data = json.loads(mem_dict["content"])
                        mem_dict["message"] = content_data
                    except:
                        mem_dict["message"] = {"role": "unknown", "content": mem_dict["content"]}
                    memory_list.append(mem_dict)

                # 按插入顺序排序（最早的在前），避免 created_at 精度导致乱序
                memory_list.sort(key=lambda x: x.get("id", 0) or 0)

                # 缓存结果
                self._set_cache(cache_key, memory_list)

                return memory_list
        except Exception as e:
            print(f"获取短期记忆失败: {e}")
            return []

    async def clear_short_term_memories(self, user_id: str, session_id: Optional[str] = None) -> bool:
        """清除短期/待处理/归档原文（session_id为空时清除该用户全部会话原文）"""
        if self.async_session is None:
            return False

        try:
            async with self.async_session() as session:
                stmt = select(MemoryItemDB).where(MemoryItemDB.user_id == user_id).where(
                    MemoryItemDB.memory_type.in_(["short_term", "pending", "pending_processing", "archived"])
                )
                if session_id:
                    stmt = stmt.where(MemoryItemDB.session_id == session_id)
                result = await session.execute(stmt)
                memories = result.scalars().all()

                for mem in memories:
                    await session.delete(mem)

                # 清理会话游标（避免下次从旧计数继续）
                state_stmt = select(MemorySessionStateDB).where(MemorySessionStateDB.user_id == user_id)
                if session_id:
                    state_stmt = state_stmt.where(MemorySessionStateDB.session_id == session_id)
                state_result = await session.execute(state_stmt)
                states = state_result.scalars().all()
                for st in states:
                    await session.delete(st)

                await session.commit()

                # 清缓存
                if session_id:
                    self._clear_cache(f"short_term:{user_id}:{session_id}")
                    self._clear_cache(f"pending:{user_id}:{session_id}")
                else:
                    self._clear_cache(f"short_term:{user_id}")
                    self._clear_cache(f"pending:{user_id}")
                return True
        except Exception as e:
            print(f"清除短期记忆失败: {e}")
            return False

    # ========== 中期记忆相关方法（公共方法） ==========

    async def _check_and_generate_summary(self, session_id: str, user_id: str):
        """检查并生成对话摘要"""
        # 新流水线下，中期摘要由“待处理区批量摘要”产生，这里直接跳过旧逻辑
        if getattr(self.config, "pipeline_enabled", False):
            return

        if not self.config.mid_term_enabled:
            return

        try:
            # 获取当前轮次
            current_round = await self._get_session_round(session_id, user_id)

            # 检查是否达到摘要生成间隔
            interval = int(getattr(self.config, "summary_interval", 0) or 0)
            if interval > 0 and current_round % interval == 0:
                await self._generate_conversation_summary(session_id, user_id, current_round)
        except Exception as e:
            print(f"检查摘要生成失败: {e}")

    async def _generate_conversation_summary(self, session_id: str, user_id: str, current_round: int):
        """生成对话摘要（优化版 - 智能提取关键信息）"""
        if self.async_session is None:
            return

        try:
            # 获取需要摘要的对话范围
            start_round = max(1, current_round - self.config.summary_interval + 1)
            end_round = current_round

            # 获取该范围内的对话
            async with self.async_session() as session:
                stmt = select(MemoryItemDB).where(
                    MemoryItemDB.user_id == user_id,
                    MemoryItemDB.session_id == session_id,
                    MemoryItemDB.memory_type == "short_term"
                ).order_by(MemoryItemDB.created_at)

                result = await session.execute(stmt)
                all_memories = result.scalars().all()

                # 过滤指定轮次范围
                if len(all_memories) > 0:
                    # 取最近N条消息
                    recent_memories = all_memories[-self.config.summary_interval * 2:]

                    # 提取对话文本
                    conversations = []
                    for mem in recent_memories:
                        try:
                            content_data = json.loads(mem.content)
                            conversations.append({
                                "role": content_data['role'],
                                "content": content_data['content']
                            })
                        except:
                            pass

                    if not conversations:
                        return

                    # 生成智能摘要
                    summary_text, summary_type = await self._generate_smart_summary(conversations)

                    # 保存摘要
                    summary = MemorySummaryDB(
                        user_id=user_id,
                        session_id=session_id,
                        summary=summary_text,
                        conversation_range=f"{start_round}-{end_round}",
                        meta_data={
                            "round_start": start_round,
                            "round_end": end_round,
                            "total_messages": len(recent_memories),
                            "summary_type": summary_type,  # "topic", "event", "emotion", "general"
                            "key_points": await self._extract_key_points(conversations)
                        }
                    )
                    session.add(summary)
                    await session.commit()

                    # 清理旧摘要
                    await self._cleanup_old_summaries(user_id, session_id)

                    print(f"已生成对话摘要 [{summary_type}]: {session_id} 轮次 {start_round}-{end_round}")
        except Exception as e:
            print(f"生成对话摘要失败: {e}")

    async def _generate_smart_summary(self, conversations: List[Dict]) -> Tuple[str, str]:
        """
        生成智能摘要（使用规则和启发式方法）

        Returns:
            (summary_text, summary_type)
            summary_type: topic（话题）、event（事件）、emotion（情感）、general（通用）
        """
        # 提取所有用户消息
        user_messages = [conv["content"] for conv in conversations if conv["role"] == "user"]

        if not user_messages:
            return "无有效对话内容", "general"

        # 合并用户消息
        combined_text = " ".join(user_messages)

        # 检测摘要类型
        summary_type = self._detect_summary_type(combined_text)

        # 根据类型生成摘要
        if summary_type == "topic":
            summary = self._generate_topic_summary(user_messages)
        elif summary_type == "event":
            summary = self._generate_event_summary(user_messages)
        elif summary_type == "emotion":
            summary = self._generate_emotion_summary(user_messages)
        else:
            summary = self._generate_general_summary(user_messages)

        # 限制长度
        if len(summary) > self.config.summary_max_length:
            summary = summary[:self.config.summary_max_length] + "..."

        return summary, summary_type

    def _detect_summary_type(self, text: str) -> str:
        """检测摘要类型"""
        # 检测事件关键词
        event_keywords = ["去了", "吃了", "买了", "做了", "发生了", "遇到", "看到", "听到"]
        if any(kw in text for kw in event_keywords):
            return "event"

        # 检测情感关键词
        emotion_keywords = ["开心", "难过", "生气", "喜欢", "讨厌", "害怕", "担心", "高兴", "悲伤", "愤怒"]
        if any(kw in text for kw in emotion_keywords):
            return "emotion"

        # 检测话题关键词
        topic_keywords = ["聊聊", "说说", "讨论", "关于", "想了解", "想知道"]
        if any(kw in text for kw in topic_keywords):
            return "topic"

        return "general"

    def _generate_topic_summary(self, messages: List[str]) -> str:
        """生成话题摘要"""
        # 提取关键话题词
        topics = []
        for msg in messages:
            # 简单的关键词提取
            if "游戏" in msg:
                topics.append("游戏")
            elif "学习" in msg or "复习" in msg:
                topics.append("学习")
            elif "吃饭" in msg or "吃" in msg:
                topics.append("吃饭")
            elif "电影" in msg or "剧" in msg:
                topics.append("娱乐")
            elif "工作" in msg:
                topics.append("工作")

        if topics:
            unique_topics = list(set(topics))
            return f"聊了{len(unique_topics)}个话题：{', '.join(unique_topics)}"

        return "日常聊天"

    def _generate_event_summary(self, messages: List[str]) -> str:
        """生成事件摘要"""
        events = []
        for msg in messages:
            # 提取事件
            if "吃了" in msg:
                events.append("吃饭")
            elif "去了" in msg:
                events.append("外出")
            elif "买了" in msg:
                events.append("购物")
            elif "做了" in msg:
                events.append("完成某事")

        if events:
            return "发生了这些事：" + "、".join(events)

        return "日常活动"

    def _generate_emotion_summary(self, messages: List[str]) -> str:
        """生成情感摘要"""
        emotions = []
        for msg in messages:
            if "开心" in msg or "高兴" in msg:
                emotions.append("开心")
            elif "难过" in msg or "伤心" in msg:
                emotions.append("难过")
            elif "生气" in msg or "愤怒" in msg:
                emotions.append("生气")

        if emotions:
            # 统计主要情感
            emotion_count = {}
            for e in emotions:
                emotion_count[e] = emotion_count.get(e, 0) + 1
            main_emotion = max(emotion_count.items(), key=lambda x: x[1])[0]
            return f"情绪：{main_emotion}"

        return "日常交流"

    def _generate_general_summary(self, messages: List[str]) -> str:
        """生成通用摘要"""
        # 取最后一条消息作为主要参考
        last_msg = messages[-1] if messages else ""
        if len(last_msg) > 50:
            return last_msg[:50] + "..."
        return last_msg or "日常对话"

    async def _extract_key_points(self, conversations: List[Dict]) -> List[str]:
        """提取关键点（简化实现）"""
        key_points = []

        for conv in conversations:
            if conv["role"] == "user":
                content = conv["content"]

                # 提取关键信息
                if re.search(r'(记得|记住|别忘了)', content):
                    key_points.append(f"提醒：{content}")
                elif re.search(r'(喜欢|爱看|偏好)', content):
                    key_points.append(f"偏好：{content}")
                elif re.search(r'(明天|晚上|中午|下午)', content):
                    key_points.append(f"计划：{content}")

        # 限制关键点数量
        return key_points[:3]

    async def get_mid_term_summaries(self, user_id: str, session_id: str = None,
                                   limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取中期记忆（对话摘要）

        Args:
            user_id: 用户ID
            session_id: 会话ID（可选）
            limit: 最大返回数量

        Returns:
            摘要列表
        """
        if not self.config.mid_term_enabled:
            return []

        if self.async_session is None:
            return []

        try:
            async with self.async_session() as session:
                stmt = select(MemorySummaryDB).where(
                    MemorySummaryDB.user_id == user_id
                )
                if session_id:
                    stmt = stmt.where(MemorySummaryDB.session_id == session_id)

                stmt = stmt.order_by(MemorySummaryDB.created_at.desc()).limit(limit)
                result = await session.execute(stmt)
                summaries = result.scalars().all()

                return [summary.to_dict() for summary in summaries]
        except Exception as e:
            print(f"获取中期记忆失败: {e}")
            return []

    async def _cleanup_old_summaries(self, user_id: str, session_id: str):
        """清理旧摘要"""
        if self.async_session is None:
            return

        try:
            async with self.async_session() as session:
                # 获取所有摘要
                stmt = select(MemorySummaryDB).where(
                    MemorySummaryDB.user_id == user_id,
                    MemorySummaryDB.session_id == session_id
                ).order_by(MemorySummaryDB.created_at.desc())

                result = await session.execute(stmt)
                all_summaries = result.scalars().all()

                # 如果超过最大数量，删除最旧的
                if len(all_summaries) > self.config.max_summaries:
                    summaries_to_delete = all_summaries[self.config.max_summaries:]
                    for summary in summaries_to_delete:
                        await session.delete(summary)

                    await session.commit()
                    print(f"已清理 {len(summaries_to_delete)} 个旧摘要")
        except Exception as e:
            print(f"清理旧摘要失败: {e}")

    # ========== 会话状态管理（公共方法） ==========

    async def _get_session_state(self, session_id: str, user_id: str) -> Dict[str, Any]:
        """获取会话状态"""
        key = f"{user_id}_{session_id}"
        if key not in self.session_states:
            state = {
                "message_count": 0,
                "round_count": 0,
                "created_at": get_now().isoformat()
            }

            # 尝试从持久化状态恢复（避免重启丢失计数）
            if self.async_session is not None:
                try:
                    async with self.async_session() as session:
                        stmt = select(MemorySessionStateDB).where(
                            MemorySessionStateDB.user_id == user_id,
                            MemorySessionStateDB.session_id == session_id
                        )
                        result = await session.execute(stmt)
                        row = result.scalar_one_or_none()
                        if row is not None:
                            state["message_count"] = int(row.message_count or 0)
                            state["round_count"] = int(row.round_count or 0)
                except Exception:
                    pass

            self.session_states[key] = state
        return self.session_states[key]

    async def _update_session_state(self, session_id: str, user_id: str, event: str):
        """更新会话状态（兼容旧逻辑：优先使用 _bump_session_counters）"""
        state = await self._get_session_state(session_id, user_id)

        if event == "message_added":
            state["message_count"] = int(state.get("message_count", 0) or 0) + 1

        state["updated_at"] = get_now().isoformat()

    async def _get_session_round(self, session_id: str, user_id: str) -> int:
        """获取当前会话轮次"""
        state = await self._get_session_state(session_id, user_id)
        return state.get("round_count", 0)

    # ========== 配置管理（公共方法） ==========

    async def update_config(self, new_config: MemoryConfig):
        """更新记忆配置"""
        self.config = new_config

    async def get_stats(self) -> Dict[str, Any]:
        """获取记忆系统统计信息（基础实现，子类可扩展）"""
        stats = {
            "short_term_enabled": self.config.short_term_enabled,
            "mid_term_enabled": self.config.mid_term_enabled,
            "long_term_enabled": self.config.long_term_enabled,
            "pipeline_enabled": getattr(self.config, "pipeline_enabled", False),
        }

        if self.async_session is None:
            stats["short_term_count"] = 0
            stats["pending_count"] = 0
            stats["pending_processing_count"] = 0
            stats["archived_count"] = 0
            stats["summary_count"] = 0
            return stats

        try:
            async with self.async_session() as session:
                # 短期记忆数量
                stmt = select(func.count(MemoryItemDB.id)).where(MemoryItemDB.memory_type == "short_term")
                result = await session.execute(stmt)
                short_term_count = int(result.scalar() or 0)

                # 待处理数量
                stmt = select(func.count(MemoryItemDB.id)).where(MemoryItemDB.memory_type == "pending")
                result = await session.execute(stmt)
                pending_count = int(result.scalar() or 0)

                # 待处理（处理中）数量
                stmt = select(func.count(MemoryItemDB.id)).where(MemoryItemDB.memory_type == "pending_processing")
                result = await session.execute(stmt)
                pending_processing_count = int(result.scalar() or 0)

                # 已归档原文数量
                stmt = select(func.count(MemoryItemDB.id)).where(MemoryItemDB.memory_type == "archived")
                result = await session.execute(stmt)
                archived_count = int(result.scalar() or 0)

                # 摘要数量
                stmt = select(func.count(MemorySummaryDB.id))
                result = await session.execute(stmt)
                summary_count = int(result.scalar() or 0)

                stats["short_term_count"] = short_term_count
                stats["pending_count"] = pending_count
                stats["pending_processing_count"] = pending_processing_count
                stats["archived_count"] = archived_count
                stats["summary_count"] = summary_count
        except Exception as e:
            stats["short_term_count"] = 0
            stats["pending_count"] = 0
            stats["pending_processing_count"] = 0
            stats["archived_count"] = 0
            stats["summary_count"] = 0
            stats["error"] = str(e)

        return stats

    async def get_all_user_ids(self) -> List[str]:
        """获取所有有记忆的用户ID列表"""
        if self.async_session is None:
            return []
        try:
            async with self.async_session() as session:
                stmt = select(MemoryItemDB.user_id).distinct()
                result = await session.execute(stmt)
                user_ids = result.scalars().all()
                return list(user_ids)
        except Exception as e:
            print(f"获取用户ID列表失败: {e}")
            return []

    async def get_last_interaction_time(self, user_id: str, session_id: Optional[str] = None) -> Optional[datetime]:
        """获取某个用户最近一条记忆的时间，用于判断上次互动时间"""
        if self.async_session is None:
            return None
        try:
            async with self.async_session() as session:
                stmt = select(MemoryItemDB.created_at).where(MemoryItemDB.user_id == user_id)
                if session_id:
                    stmt = stmt.where(MemoryItemDB.session_id == session_id)
                stmt = stmt.order_by(MemoryItemDB.created_at.desc()).limit(1)
                result = await session.execute(stmt)
                last_created = result.scalar_one_or_none()
                return last_created
        except Exception as e:
            print(f"获取上次互动时间失败: {e}")
            return None

    # ========== 待办事项相关方法（公共方法） ==========

    async def add_reminder(
        self,
        user_id: str,
        session_id: str,
        content: str,
        trigger_time: datetime,
        original_message: str = None,
        time_expression: str = None,
        reminder_message: str = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        添加待办事项

        Args:
            user_id: 用户ID
            session_id: 会话ID
            content: 待办事项内容
            trigger_time: 触发时间
            original_message: 原始用户消息
            time_expression: 时间表达式（如"今晚"、"明早"）
            reminder_message: 提醒消息模板
            metadata: 额外元数据

        Returns:
            是否成功
        """
        if self.async_session is None:
            return False

        try:
            async with self.async_session() as session:
                reminder = ReminderItemDB(
                    user_id=user_id,
                    session_id=session_id,
                    content=content,
                    trigger_time=trigger_time,
                    status="pending",
                    original_message=original_message,
                    time_expression=time_expression,
                    reminder_message=reminder_message,
                    meta_data=metadata or {}
                )
                session.add(reminder)
                await session.commit()
                print(f"已添加待办事项: {content} (触发时间: {trigger_time})")
                return True
        except Exception as e:
            print(f"添加待办事项失败: {e}")
            return False

    async def get_pending_reminders(self, current_time: datetime = None) -> List[Dict[str, Any]]:
        """
        获取所有待处理的待办事项（触发时间已到且状态为pending）

        Args:
            current_time: 当前时间，默认使用系统时间

        Returns:
            待办事项列表
        """
        if self.async_session is None:
            return []

        if current_time is None:
            current_time = get_now()

        try:
            async with self.async_session() as session:
                stmt = select(ReminderItemDB).where(
                    ReminderItemDB.status == "pending",
                    ReminderItemDB.trigger_time <= current_time
                ).order_by(ReminderItemDB.trigger_time.asc())

                result = await session.execute(stmt)
                reminders = result.scalars().all()

                return [reminder.to_dict() for reminder in reminders]
        except Exception as e:
            print(f"获取待处理待办事项失败: {e}")
            return []

    async def complete_reminder(self, reminder_id: int) -> bool:
        """
        完成待办事项

        Args:
            reminder_id: 待办事项ID

        Returns:
            是否成功
        """
        if self.async_session is None:
            return False

        try:
            async with self.async_session() as session:
                stmt = select(ReminderItemDB).where(ReminderItemDB.id == reminder_id)
                result = await session.execute(stmt)
                reminder = result.scalar_one_or_none()

                if reminder:
                    reminder.status = "completed"
                    reminder.completed_at = get_now()
                    await session.commit()
                    print(f"已完成待办事项: {reminder.content}")
                    return True
                return False
        except Exception as e:
            print(f"完成待办事项失败: {e}")
            return False

    async def get_all_reminders(self, user_id: str = None, session_id: str = None,
                               status: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取待办事项列表

        Args:
            user_id: 用户ID（可选）
            session_id: 会话ID（可选）
            status: 状态筛选（可选）
            limit: 最大返回数量

        Returns:
            待办事项列表
        """
        if self.async_session is None:
            return []

        try:
            async with self.async_session() as session:
                stmt = select(ReminderItemDB)

                if user_id:
                    stmt = stmt.where(ReminderItemDB.user_id == user_id)
                if session_id:
                    stmt = stmt.where(ReminderItemDB.session_id == session_id)
                if status:
                    stmt = stmt.where(ReminderItemDB.status == status)

                stmt = stmt.order_by(ReminderItemDB.created_at.desc()).limit(limit)

                result = await session.execute(stmt)
                reminders = result.scalars().all()

                return [reminder.to_dict() for reminder in reminders]
        except Exception as e:
            print(f"获取待办事项列表失败: {e}")
            return []

    async def cancel_reminder(self, reminder_id: int) -> bool:
        """
        取消待办事项

        Args:
            reminder_id: 待办事项ID

        Returns:
            是否成功
        """
        if self.async_session is None:
            return False

        try:
            async with self.async_session() as session:
                stmt = select(ReminderItemDB).where(ReminderItemDB.id == reminder_id)
                result = await session.execute(stmt)
                reminder = result.scalar_one_or_none()

                if reminder:
                    reminder.status = "cancelled"
                    await session.commit()
                    print(f"已取消待办事项: {reminder.content}")
                    return True
                return False
        except Exception as e:
            print(f"取消待办事项失败: {e}")
            return False

    # ========== 抽象方法：子类必须实现 ==========

    @abstractmethod
    async def _extract_important_memories(self, session_id: str, user_id: str):
        """提取重要信息到长期记忆（子类实现）"""
        pass

    @abstractmethod
    async def _cleanup_old_long_term_memories(self, user_id: str):
        """清理旧的长期记忆（子类实现）"""
        pass

    @abstractmethod
    async def clear_all_memories(self, user_id: str, session_id: str = None):
        """清除所有记忆（子类实现）"""
        pass

    # ========== 批量操作方法（批量插入/删除）==========

    async def add_short_term_memories_batch(self, user_id: str, session_id: str,
                                           messages: List[ConversationMessage]) -> int:
        """
        批量添加短期记忆

        Args:
            user_id: 用户ID
            session_id: 会话ID
            messages: 对话消息列表

        Returns:
            成功添加的数量
        """
        if not self.config.short_term_enabled:
            return 0

        if self.async_session is None:
            return 0

        try:
            async with self.async_session() as session:
                # 批量创建记忆项
                memory_items = []
                for i, message in enumerate(messages):
                    message_index, round_index = await self._bump_session_counters(
                        session=session,
                        user_id=user_id,
                        session_id=session_id,
                        role=message.role
                    )
                    memory_item = MemoryItemDB(
                        user_id=user_id,
                        session_id=session_id,
                        content=json.dumps({
                            "role": message.role,
                            "content": message.content,
                            "timestamp": message.timestamp.isoformat()
                        }, ensure_ascii=False),
                        memory_type="short_term",
                        meta_data={
                            "message_index": message_index,
                            "round_index": round_index,
                            "auto_clean": True
                        }
                    )
                    memory_items.append(memory_item)

                # 批量添加
                session.add_all(memory_items)
                await session.commit()

                # 清除相关缓存
                self._clear_cache(f"short_term:{user_id}:{session_id}")

            # 后处理：流水线或旧逻辑
            last_role = messages[-1].role if messages else "assistant"
            if getattr(self.config, "pipeline_enabled", False):
                await self._pipeline_after_message_added(user_id=user_id, session_id=session_id, role=last_role)
            else:
                await self._check_and_generate_summary(session_id, user_id)
                if getattr(self.config, "legacy_auto_extract_enabled", True):
                    await self._extract_important_memories(session_id, user_id)

            return len(memory_items)
        except Exception as e:
            print(f"批量添加短期记忆失败: {e}")
            return 0

    async def delete_short_term_memories_batch(self, user_id: str, session_id: str = None,
                                              before_date: datetime = None) -> int:
        """
        批量删除短期记忆

        Args:
            user_id: 用户ID
            session_id: 会话ID（可选，不指定则删除用户的所有短期记忆）
            before_date: 删除此日期之前的记忆（可选）

        Returns:
            删除的数量
        """
        if self.async_session is None:
            return 0

        try:
            async with self.async_session() as session:
                stmt = select(MemoryItemDB).where(
                    MemoryItemDB.user_id == user_id,
                    MemoryItemDB.memory_type == "short_term"
                )
                if session_id:
                    stmt = stmt.where(MemoryItemDB.session_id == session_id)
                if before_date:
                    stmt = stmt.where(MemoryItemDB.created_at < before_date)

                result = await session.execute(stmt)
                memories = result.scalars().all()

                count = 0
                for mem in memories:
                    await session.delete(mem)
                    count += 1

                await session.commit()

                # 清除相关缓存
                if session_id:
                    self._clear_cache(f"short_term:{user_id}:{session_id}")
                else:
                    self._clear_cache(f"short_term:{user_id}")

                return count
        except Exception as e:
            print(f"批量删除短期记忆失败: {e}")
            return 0
