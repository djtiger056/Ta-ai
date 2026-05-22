"""
向量存储模块，用于长期记忆的向量检索
"""

import asyncio
import os
import json
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging
import chromadb
from chromadb.config import Settings
import aiohttp
from datetime import datetime
from backend.utils.datetime_utils import get_now, to_isoformat


logger = logging.getLogger(__name__)


def _load_sentence_transformer(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


class VectorStore:
    """向量存储类，封装ChromaDB操作"""
    
    def __init__(self, persist_directory: str = "./data/chroma",
                 embedding_provider: str = "local",
                 embedding_model_name: str = "all-MiniLM-L6-v2",
                 embedding_api_base: Optional[str] = None,
                 embedding_api_key: Optional[str] = None,
                 embedding_timeout: int = 30,
                 embedding_dimensions: Optional[int] = None):
        """
        初始化向量存储
        
        Args:
            persist_directory: 向量数据库持久化目录
            embedding_provider: 嵌入向量提供商（local/openai_compatible/aliyun）
            embedding_model_name: 嵌入模型名称
            embedding_api_base: 外部嵌入API Base
            embedding_api_key: 外部嵌入API Key
            embedding_timeout: 外部嵌入API超时（秒）
            embedding_dimensions: 嵌入向量维度（外部模型/降级时使用）
        """
        self.persist_directory = Path(persist_directory)
        self.embedding_provider = (embedding_provider or "local").lower()
        self.embedding_model_name = embedding_model_name
        self.embedding_api_base = embedding_api_base
        self.embedding_api_key = embedding_api_key
        self.embedding_timeout = embedding_timeout
        self.embedding_dimensions = embedding_dimensions
        self.embedding_model = None
        self.chroma_client = None
        self.collection = None
        self._default_embedding_dimensions = 384
        
        # 创建目录
        self.persist_directory.mkdir(parents=True, exist_ok=True)

    def _normalize_metadata_value(self, value: Any) -> Any:
        """将metadata值规范化为Chroma可接受的标量类型"""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, datetime):
            return to_isoformat(value)
        if isinstance(value, (list, tuple, set, dict)):
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return str(value)
        return str(value)

    def _normalize_metadata(self, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """清洗metadata，避免向量库因复杂类型报错"""
        if not metadata:
            return {}
        normalized: Dict[str, Any] = {}
        for key, value in metadata.items():
            normalized[str(key)] = self._normalize_metadata_value(value)
        return normalized
        
    async def initialize(self):
        """异步初始化向量存储"""
        # 初始化嵌入模型或外部嵌入配置
        if self.embedding_provider == "local":
            try:
                print(f"正在加载嵌入模型: {self.embedding_model_name} (超时: 60秒)")
                # 在单独线程中加载模型，避免阻塞事件循环
                self.embedding_model = await asyncio.wait_for(
                    asyncio.to_thread(_load_sentence_transformer, self.embedding_model_name),
                    timeout=60.0
                )
                try:
                    self.embedding_dimensions = int(self.embedding_model.get_sentence_embedding_dimension())
                except Exception:
                    self.embedding_dimensions = self.embedding_dimensions or self._default_embedding_dimensions
                print(f"嵌入模型加载成功: {self.embedding_model_name}")
            except asyncio.TimeoutError:
                print(f"加载嵌入模型超时: {self.embedding_model_name} (超过60秒)")
                self.embedding_model = None
            except Exception as e:
                print(f"加载嵌入模型失败 {self.embedding_model_name}: {e}")
                self.embedding_model = None

            # 如果主模型加载失败，尝试备用模型
            if self.embedding_model is None:
                try:
                    print("尝试加载更小的模型: all-MiniLM-L6-v2 (超时: 30秒)")
                    self.embedding_model = await asyncio.wait_for(
                        asyncio.to_thread(_load_sentence_transformer, "all-MiniLM-L6-v2"),
                        timeout=30.0
                    )
                    try:
                        self.embedding_dimensions = int(self.embedding_model.get_sentence_embedding_dimension())
                    except Exception:
                        self.embedding_dimensions = self.embedding_dimensions or self._default_embedding_dimensions
                    print("备用模型加载成功: all-MiniLM-L6-v2")
                except asyncio.TimeoutError:
                    print("加载备用嵌入模型超时: all-MiniLM-L6-v2 (超过30秒)")
                    print("警告: 嵌入模型加载失败，向量存储功能将不可用")
                    self.embedding_model = None
                except Exception as e2:
                    print(f"加载备用嵌入模型失败: {e2}")
                    print("警告: 嵌入模型加载失败，向量存储功能将不可用")
                    self.embedding_model = None
        else:
            # 外部嵌入模式：不加载本地模型
            if self.embedding_provider in ("aliyun", "dashscope"):
                logger.info(f"使用外部嵌入模型（阿里云/DashScope）: {self.embedding_model_name}")
            elif self.embedding_provider in ("openai_compatible", "openai"):
                logger.info(f"使用外部嵌入模型（OpenAI兼容）: {self.embedding_model_name}")
            else:
                print(f"未知 embedding_provider={self.embedding_provider}，回退到本地模型")
                self.embedding_provider = "local"
                return await self.initialize()
        
        # 初始化ChromaDB客户端
        try:
            self.chroma_client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=Settings(allow_reset=True)
            )
        except Exception as e:
            print(f"初始化ChromaDB客户端失败: {e}")
            raise
        
        # 创建或获取集合
        try:
            self.collection = self.chroma_client.get_or_create_collection(
                name="long_term_memories",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            print(f"创建/获取集合失败: {e}")
            raise
    
    def _fallback_embedding(self) -> List[float]:
        dim = self.embedding_dimensions or self._default_embedding_dimensions
        return [0.0] * int(dim)

    def _generate_embedding_local(self, text: str) -> List[float]:
        """使用本地模型生成文本嵌入向量"""
        if self.embedding_model is None:
            print("警告: 嵌入模型不可用，无法生成向量")
            return self._fallback_embedding()
        embedding = self.embedding_model.encode(text).tolist()
        if self.embedding_dimensions is None:
            self.embedding_dimensions = len(embedding)
        return embedding

    async def _generate_embedding_openai_compatible(self, text: str) -> List[float]:
        """使用 OpenAI 兼容接口生成文本嵌入向量"""
        if not self.embedding_api_base:
            print("警告: embedding_api_base 未配置，无法调用外部嵌入模型")
            return self._fallback_embedding()
        if not self.embedding_api_key:
            print("警告: embedding_api_key 未配置，无法调用外部嵌入模型")
            return self._fallback_embedding()

        base = self.embedding_api_base.rstrip("/")
        if base.endswith("/embeddings"):
            url = base
        else:
            url = f"{base}/embeddings"

        headers = {
            "Authorization": f"Bearer {self.embedding_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.embedding_model_name,
            "input": text
        }

        try:
            timeout = aiohttp.ClientTimeout(total=self.embedding_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        detail = await resp.text()
                        print(f"外部嵌入接口返回错误: HTTP {resp.status} - {detail}")
                        return self._fallback_embedding()
                    data = await resp.json()
            embedding = None
            if isinstance(data, dict):
                items = data.get("data") or data.get("embeddings")
                if isinstance(items, list) and items:
                    first = items[0]
                    if isinstance(first, dict):
                        embedding = first.get("embedding")
                    elif isinstance(first, list):
                        embedding = first
            if not embedding:
                print("外部嵌入接口返回格式异常，无法解析向量")
                return self._fallback_embedding()
            if self.embedding_dimensions is None:
                self.embedding_dimensions = len(embedding)
            return embedding
        except Exception as e:
            print(f"外部嵌入接口调用失败: {e}")
            return self._fallback_embedding()

    async def _generate_embedding_dashscope(self, text: str) -> List[float]:
        """使用 DashScope(阿里云) 嵌入模型生成向量"""
        try:
            import dashscope
            from dashscope import TextEmbedding
        except Exception as e:
            print(f"DashScope SDK不可用: {e}")
            return self._fallback_embedding()

        if self.embedding_api_key:
            dashscope.api_key = self.embedding_api_key
        if not getattr(dashscope, "api_key", None):
            print("警告: embedding_api_key 未配置，无法调用 DashScope 嵌入模型")
            return self._fallback_embedding()

        try:
            response = await asyncio.to_thread(
                TextEmbedding.call,
                model=self.embedding_model_name,
                input=text
            )
            output = None
            if isinstance(response, dict):
                output = response.get("output") or response.get("data") or response
            else:
                output = getattr(response, "output", None) or getattr(response, "data", None) or {}

            embeddings = None
            if isinstance(output, dict):
                embeddings = output.get("embeddings") or output.get("embedding") or output.get("data")

            embedding = None
            if isinstance(embeddings, list) and embeddings:
                first = embeddings[0]
                if isinstance(first, dict):
                    embedding = first.get("embedding")
                elif isinstance(first, list):
                    embedding = first

            if not embedding:
                print("DashScope返回格式异常，无法解析向量")
                return self._fallback_embedding()
            if self.embedding_dimensions is None:
                self.embedding_dimensions = len(embedding)
            return embedding
        except Exception as e:
            print(f"DashScope嵌入调用失败: {e}")
            return self._fallback_embedding()

    async def _generate_embedding(self, text: str) -> List[float]:
        """生成文本嵌入向量"""
        if self.embedding_provider == "local":
            return self._generate_embedding_local(text)
        if self.embedding_provider in ("aliyun", "dashscope"):
            return await self._generate_embedding_dashscope(text)
        return await self._generate_embedding_openai_compatible(text)
    
    async def add_memory(self, memory_id: str, user_id: str, content: str, 
                        metadata: Dict[str, Any] = None) -> bool:
        """
        添加记忆到向量存储
        
        Args:
            memory_id: 记忆ID
            user_id: 用户ID
            content: 记忆内容
            metadata: 元数据
            
        Returns:
            是否成功
        """
        if self.collection is None:
            raise RuntimeError("向量存储未初始化")
        
        try:
            embedding = await self._generate_embedding(content)
            
            # 准备元数据
            now = get_now()
            memory_metadata = {
                "user_id": user_id,
                "content": content,
                "timestamp": to_isoformat(now)  # 使用北京时间
            }
            if metadata:
                memory_metadata.update(metadata)
            memory_metadata = self._normalize_metadata(memory_metadata)
            
            # 添加到集合
            self.collection.add(
                ids=[memory_id],
                embeddings=[embedding],
                metadatas=[memory_metadata],
                documents=[content]
            )
            return True
        except Exception as e:
            print(f"添加记忆到向量存储失败: {e}")
            return False
    
    async def search_memories(self, query: str, user_id: str = None, 
                            top_k: int = 3, score_threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        搜索相关记忆
        
        Args:
            query: 查询文本
            user_id: 用户ID（可选，用于过滤）
            top_k: 返回结果数量
            score_threshold: 分数阈值
            
        Returns:
            相关记忆列表，包含内容和相似度分数
        """
        if self.collection is None:
            raise RuntimeError("向量存储未初始化")
        
        try:
            query_embedding = await self._generate_embedding(query)
            
            # 构建过滤条件
            where = None
            if user_id:
                where = {"user_id": user_id}
            
            # 执行查询
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"]
            )
            
            # 处理结果
            memories = []
            if results["ids"] and len(results["ids"][0]) > 0:
                for i in range(len(results["ids"][0])):
                    distance = results["distances"][0][i]
                    similarity = 1.0 - distance  # ChromaDB使用余弦距离，转换为相似度
                    
                    if similarity >= score_threshold:
                        metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                        memories.append({
                            "id": results["ids"][0][i],
                            "content": results["documents"][0][i],
                            "metadata": metadata,
                            "importance": (metadata or {}).get("importance"),
                            "created_at": (metadata or {}).get("timestamp") or (metadata or {}).get("created_at"),
                            "similarity": similarity
                        })
            
            return memories
        except Exception as e:
            print(f"搜索记忆失败: {e}")
            return []
    
    async def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        if self.collection is None:
            raise RuntimeError("向量存储未初始化")
        
        try:
            self.collection.delete(ids=[memory_id])
            return True
        except Exception as e:
            print(f"删除记忆失败: {e}")
            return False
    
    async def update_memory(self, memory_id: str, content: str = None, 
                          metadata: Dict[str, Any] = None) -> bool:
        """更新记忆"""
        if self.collection is None:
            raise RuntimeError("向量存储未初始化")
        
        try:
            # 获取现有记忆
            existing = self.collection.get(ids=[memory_id])
            if not existing["ids"]:
                return False
            
            # 更新内容或元数据
            current_metadata = existing["metadatas"][0] if existing["metadatas"] else {}
            current_content = existing["documents"][0] if existing["documents"] else ""
            
            new_content = content if content is not None else current_content
            new_metadata = self._normalize_metadata({**current_metadata, **(metadata or {})})
            
            # 重新生成嵌入
            new_embedding = await self._generate_embedding(new_content)
            
            # 更新
            self.collection.update(
                ids=[memory_id],
                embeddings=[new_embedding],
                metadatas=[new_metadata],
                documents=[new_content]
            )
            return True
        except Exception as e:
            print(f"更新记忆失败: {e}")
            return False
    
    async def get_user_memories(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取用户的所有记忆"""
        if self.collection is None:
            raise RuntimeError("向量存储未初始化")
        
        try:
            results = self.collection.get(
                where={"user_id": user_id},
                limit=limit,
                include=["documents", "metadatas"]
            )
            
            memories = []
            for i in range(len(results["ids"])):
                metadata = results["metadatas"][i] if results["metadatas"] else {}
                memories.append({
                    "id": results["ids"][i],
                    "content": results["documents"][i],
                    "metadata": metadata,
                    "importance": (metadata or {}).get("importance"),
                    "created_at": (metadata or {}).get("timestamp") or (metadata or {}).get("created_at")
                })
            
            return memories
        except Exception as e:
            print(f"获取用户记忆失败: {e}")
            return []
    
    async def clear_user_memories(self, user_id: str) -> bool:
        """清除用户的所有记忆"""
        if self.collection is None:
            raise RuntimeError("向量存储未初始化")
        
        try:
            self.collection.delete(where={"user_id": user_id})
            return True
        except Exception as e:
            print(f"清除用户记忆失败: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取向量存储统计信息"""
        if self.collection is None:
            return {"count": 0, "status": "未初始化"}
        
        try:
            count = self.collection.count()
            return {
                "count": count,
                "status": "运行中",
                "embedding_model": self.embedding_model_name,
                "embedding_provider": self.embedding_provider,
                "embedding_dimensions": self.embedding_dimensions
            }
        except Exception as e:
            return {"count": 0, "status": f"错误: {str(e)}"}
