"""
记忆系统数据模型
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Float, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from backend.utils.datetime_utils import get_now


def get_current_time():
    """获取当前时间供SQLAlchemy使用"""
    return get_now()

Base = declarative_base()


class MemoryConfig(BaseModel):
    """记忆系统配置模型"""
    # 总开关：是否启用“短期窗口→待处理→摘要→长期事实”流水线
    pipeline_enabled: bool = Field(default=True, description="是否启用新的记忆流水线（短期窗口/待处理/摘要/长期）")

    short_term_enabled: bool = Field(default=True, description="是否启用短期记忆")
    mid_term_enabled: bool = Field(default=True, description="是否启用中期记忆")
    long_term_enabled: bool = Field(default=True, description="是否启用长期记忆")
    long_term_strategy: str = Field(default="local", description="长期记忆策略（local/external）")
    external_memory_provider: str = Field(default="memobase", description="外部记忆提供商")
    external_memory_base_url: Optional[str] = Field(default=None, description="外部记忆服务地址")
    external_memory_api_key: Optional[str] = Field(default=None, description="外部记忆API Key")
    external_memory_timeout: int = Field(default=30, description="外部记忆接口超时（秒）")
    external_memory_prefer_topics: Optional[List[str]] = Field(default=None, description="外部记忆上下文优先主题")
    embedding_provider: str = Field(default="local", description="嵌入向量提供商（local/openai_compatible/aliyun）")
    embedding_model: str = Field(default="all-MiniLM-L6-v2", description="嵌入模型名称")
    embedding_api_base: Optional[str] = Field(default=None, description="外部嵌入API Base")
    embedding_api_key: Optional[str] = Field(default=None, description="外部嵌入API Key")
    embedding_timeout: int = Field(default=30, description="外部嵌入API超时（秒）")
    embedding_dimensions: Optional[int] = Field(default=None, description="嵌入向量维度（外部模型/降级时使用）")
    rag_top_k: int = Field(default=3, description="RAG检索返回的top-k数量")
    rag_score_threshold: float = Field(default=0.5, description="RAG检索分数阈值")
    mid_term_context_count: int = Field(default=5, description="注入LLM上下文的中期摘要条数")

    # 兼容字段：历史上用于“短期记忆最大轮次”，Bot侧会用 *2 换算为 message 数量
    short_term_max_rounds: int = Field(default=50, description="短期记忆最大轮次（兼容字段，1轮≈user+assistant）")
    # 新字段：更明确的命名（为空时回退到 short_term_max_rounds）
    short_term_keep_rounds: Optional[int] = Field(default=None, description="短期窗口保留轮次（为空则使用short_term_max_rounds）")

    # 待处理区与摘要
    pending_enabled: bool = Field(default=True, description="是否启用待处理区（超过短期窗口的原文进入待处理）")
    pending_chunk_rounds: int = Field(default=20, description="待处理区每满多少轮触发一次摘要（1轮≈user+assistant）")
    pending_delete_after_summary: bool = Field(default=True, description="摘要完成后是否删除该chunk的原文（否则转为archived）")
    pending_overlap_messages: int = Field(default=4, description="摘要输入时附加的重叠消息数（用于跨chunk衔接）")

    # LLM 摘要与事实抽取
    summarizer_enabled: bool = Field(default=True, description="是否启用专用摘要LLM（启用后可抽取长期事实）")
    summarizer_llm: Dict[str, Any] = Field(default_factory=dict, description="摘要LLM配置（与llm节结构兼容）")
    summarizer_max_facts: int = Field(default=20, description="单次摘要最多抽取的长期事实条数")
    summarizer_fact_min_importance: Optional[float] = Field(default=None, description="事实入长期记忆的最低重要度（为空则使用importance_threshold）")
    legacy_auto_extract_enabled: bool = Field(default=False, description="是否保留旧的启发式长期记忆抽取（不推荐与summarizer同时开）")

    # 旧字段：规则摘要间隔（仅在pipeline_enabled=false时使用）
    summary_interval: int = Field(default=10, description="（旧）摘要生成间隔（对话轮次，仅pipeline_enabled=false时使用）")
    summary_max_length: int = Field(default=500, description="摘要最大长度")
    max_summaries: int = Field(default=10, description="最大摘要数量")
    max_long_term_memories: int = Field(default=1000, description="长期记忆最大数量")
    importance_threshold: float = Field(default=0.75, description="重要性阈值（0-1），超过此值才存入长期记忆")
    same_question_reset_minutes: int = Field(default=45, description="同类问题间隔超过该分钟数时按新一轮问题处理")
    frequency_penalty: float = Field(default=0.5, description="重复惩罚参数（用于LLM生成）")

    # 记忆过期和衰减配置

    class Config:
        json_schema_extra = {
            "example": {
                "pipeline_enabled": True,
                "short_term_enabled": True,
                "mid_term_enabled": True,
                "long_term_enabled": True,
                "long_term_strategy": "local",
                "external_memory_provider": "memobase",
                "external_memory_base_url": "http://localhost:8019",
                "external_memory_api_key": "secret",
                "external_memory_timeout": 30,
                "external_memory_prefer_topics": ["基本信息", "兴趣爱好"],
                "embedding_provider": "local",
                "embedding_model": "all-MiniLM-L6-v2",
                "embedding_api_base": None,
                "embedding_api_key": "",
                "embedding_timeout": 30,
                "embedding_dimensions": 384,
                "rag_top_k": 3,
                "rag_score_threshold": 0.75,
                "short_term_max_rounds": 20,
                "short_term_keep_rounds": 20,
                "pending_enabled": True,
                "pending_chunk_rounds": 20,
                "pending_delete_after_summary": True,
                "pending_overlap_messages": 4,
                "summarizer_enabled": True,
                "summarizer_llm": {
                    "provider": "openai",
                    "api_key": "sk-xxx",
                    "model": "gpt-4o-mini",
                    "temperature": 0.2,
                    "max_tokens": 1200
                },
                "summarizer_max_facts": 20,
                "summarizer_fact_min_importance": 0.75,
                "legacy_auto_extract_enabled": False,
                "summary_interval": 10,
                "summary_max_length": 500,
                "max_summaries": 10,
                "max_long_term_memories": 1000,
                "importance_threshold": 0.75,
                "same_question_reset_minutes": 45,
                "frequency_penalty": 0.5,
            }
        }


class MemoryItemDB(Base):
    """记忆项数据库模型"""
    __tablename__ = "memory_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    session_id = Column(String(255), nullable=False, index=True)
    content = Column(Text, nullable=False)
    memory_type = Column(String(50), nullable=False, index=True)  # short_term, mid_term, long_term
    importance = Column(Float, default=0.5)  # 重要性评分，0-1
    meta_data = Column(JSON, default=dict)  # 额外元数据（避免metadata保留字）
    created_at = Column(DateTime, default=get_current_time)
    updated_at = Column(DateTime, default=get_current_time, onupdate=get_current_time)

    # 复合索引优化查询性能
    __table_args__ = (
        Index('idx_user_session_type', 'user_id', 'session_id', 'memory_type'),
        Index('idx_user_type', 'user_id', 'memory_type'),
        Index('idx_session_created', 'session_id', 'created_at'),
        Index('idx_importance_created', 'importance', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "content": self.content,
            "memory_type": self.memory_type,
            "importance": self.importance,
            "metadata": self.meta_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class MemorySummaryDB(Base):
    """记忆摘要数据库模型"""
    __tablename__ = "memory_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    session_id = Column(String(255), nullable=False, index=True)
    summary = Column(Text, nullable=False)
    conversation_range = Column(String(100), nullable=False)  # 例如 "1-10", "11-20"
    meta_data = Column(JSON, default=dict)  # 额外元数据（避免metadata保留字）
    created_at = Column(DateTime, default=get_current_time)

    # 复合索引优化查询性能
    __table_args__ = (
        Index('idx_user_session_summary', 'user_id', 'session_id'),
        Index('idx_user_created_summary', 'user_id', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "summary": self.summary,
            "conversation_range": self.conversation_range,
            "metadata": self.meta_data,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class MemorySessionStateDB(Base):
    """会话状态（持久化游标，用于重启后不乱序/不重复摘要）"""
    __tablename__ = "memory_session_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    session_id = Column(String(255), nullable=False, index=True)
    message_count = Column(Integer, default=0)  # 已写入的消息数量（message粒度）
    round_count = Column(Integer, default=0)  # 已发生的轮次数（以user消息为轮起点）
    created_at = Column(DateTime, default=get_current_time)
    updated_at = Column(DateTime, default=get_current_time, onupdate=get_current_time)

    __table_args__ = (
        Index('idx_user_session_state', 'user_id', 'session_id', unique=True),
    )


class MemoryItem(BaseModel):
    """记忆项Pydantic模型"""
    id: Optional[int] = None
    user_id: str
    session_id: str
    content: str
    memory_type: str  # short_term, mid_term, long_term
    importance: float = 0.5
    metadata: Dict[str, Any] = {}
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MemorySummary(BaseModel):
    """记忆摘要Pydantic模型"""
    id: Optional[int] = None
    user_id: str
    session_id: str
    summary: str
    conversation_range: str
    metadata: Dict[str, Any] = {}
    created_at: Optional[str] = None


class ConversationMessage(BaseModel):
    """对话消息模型"""
    role: str  # user, assistant, system
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


class ReminderItemDB(Base):
    """待办事项数据库模型"""
    __tablename__ = "reminder_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    session_id = Column(String(255), nullable=False, index=True)
    content = Column(Text, nullable=False)  # 待办事项内容
    trigger_time = Column(DateTime, nullable=False, index=True)  # 触发时间
    status = Column(String(50), default="pending", index=True)  # pending, completed, cancelled
    original_message = Column(Text, nullable=True)  # 原始用户消息
    time_expression = Column(String(100), nullable=True)  # 时间表达式（如"今晚"、"明早"）
    reminder_message = Column(Text, nullable=True)  # 提醒消息模板
    meta_data = Column(JSON, default=dict)  # 额外元数据
    created_at = Column(DateTime, default=get_current_time)
    completed_at = Column(DateTime, nullable=True)  # 完成时间

    # 复合索引优化查询性能
    __table_args__ = (
        Index('idx_status_trigger_time', 'status', 'trigger_time'),
        Index('idx_user_status', 'user_id', 'status'),
        Index('idx_user_session_status', 'user_id', 'session_id', 'status'),
        Index('idx_user_trigger_time', 'user_id', 'trigger_time'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "content": self.content,
            "trigger_time": self.trigger_time.isoformat() if self.trigger_time else None,
            "status": self.status,
            "original_message": self.original_message,
            "time_expression": self.time_expression,
            "reminder_message": self.reminder_message,
            "metadata": self.meta_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class ReminderItem(BaseModel):
    """待办事项Pydantic模型"""
    id: Optional[int] = None
    user_id: str
    session_id: str
    content: str
    trigger_time: str  # ISO格式的时间字符串
    status: str = "pending"  # pending, completed, cancelled
    original_message: Optional[str] = None
    time_expression: Optional[str] = None
    reminder_message: Optional[str] = None
    metadata: Dict[str, Any] = {}
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
