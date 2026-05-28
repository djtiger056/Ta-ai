import aiohttp
from aiohttp import ClientTimeout
import asyncio
import json
from typing import Dict, Any, AsyncGenerator
from .base import BaseLLMProvider
from ..config import config
from ..utils.llm_payload_logger import record_payload


class OpenAIProvider(BaseLLMProvider):
    """OpenAI兼容的LLM提供商"""
    
    def __init__(self, provider_name: str = 'openai', llm_config: Dict[str, Any] | None = None):
        self.provider_name = provider_name
        self.config = llm_config if llm_config is not None else config.llm_config
        
        # 优先使用提供商特定的配置
        provider_config = self.config.get(provider_name, {})

        # 依据不同提供商设置默认的Base URL
        default_api_bases = {
            'openai': 'https://api.openai.com/v1',
            'siliconflow': 'https://api.siliconflow.cn/v1',
            'deepseek': 'https://api.deepseek.com/v1',
            'yunwu': 'https://yunwu.ai/v1',
            'qwen': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        }

        raw_api_base = (
            self.config.get('api_base')
            or provider_config.get('api_base')
            or default_api_bases.get(provider_name, 'https://api.openai.com/v1')
        )
        self.api_base = self._normalize_api_base(raw_api_base)
        self.api_key = self.config.get('api_key') or provider_config.get('api_key') or ''
        self.model = self.config.get('model') or provider_config.get('model') or 'gpt-3.5-turbo'
        self.temperature = self.config.get('temperature', provider_config.get('temperature', 0.7))
        self.max_tokens = self.config.get('max_tokens', provider_config.get('max_tokens', 2000))
        self.presence_penalty = self.config.get('presence_penalty', provider_config.get('presence_penalty', 0))
        self.frequency_penalty = self.config.get('frequency_penalty', provider_config.get('frequency_penalty', 0))
        
        # 超时配置
        timeout_config = self.config.get('timeout', {})
        self.timeout_connect = timeout_config.get('connect', 15)
        self.timeout_sock_connect = timeout_config.get('sock_connect', 15)
        self.timeout_sock_read = timeout_config.get('sock_read', 60)
        self.timeout_total = timeout_config.get('total', 90)
        
        # 重试配置
        retry_config = self.config.get('retry', {})
        self.max_retries = retry_config.get('max_attempts', 3)
        self.retry_delay = retry_config.get('delay', 2)
        self.backoff_multiplier = retry_config.get('backoff_multiplier', 1.5)
        
        if not self.api_key:
            raise ValueError("API密钥未配置")

    def _normalize_api_base(self, api_base: str) -> str:
        """确保Base URL没有重复的/chat/completions后缀"""
        normalized = api_base.strip()
        suffix = '/chat/completions'
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]
        return normalized.rstrip('/')
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    async def chat(self, messages: list, **kwargs) -> str:
        """发送聊天消息并获取回复（带重试机制）"""
        url = f"{self.api_base}/chat/completions"

        data = {
            "model": kwargs.get('model', self.model),
            "messages": messages,
            "temperature": kwargs.get('temperature', self.temperature),
            "max_tokens": kwargs.get('max_tokens', self.max_tokens),
            "presence_penalty": kwargs.get('presence_penalty', self.presence_penalty),
            "frequency_penalty": kwargs.get('frequency_penalty', self.frequency_penalty),
            "stream": False
        }
        record_payload(self.provider_name, data["model"], messages, {"stream": False})

        # 使用配置的超时设置
        timeout = ClientTimeout(
            connect=self.timeout_connect,
            sock_connect=self.timeout_sock_connect,
            sock_read=self.timeout_sock_read,
            total=self.timeout_total
        )

        max_retries = self.max_retries
        base_retry_delay = self.retry_delay

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, headers=self._get_headers(), json=data) as response:
                        if response.status == 200:
                            result = await response.json()
                            return result['choices'][0]['message']['content']
                        else:
                            error_text = await response.text()
                            if attempt < max_retries - 1:
                                print(f"API请求失败，正在重试 ({attempt + 1}/{max_retries}): {response.status}")
                                await asyncio.sleep(base_retry_delay * (self.backoff_multiplier ** attempt))  # 指数退避
                                continue
                            raise Exception(f"API请求失败: {response.status} - {error_text}")
            except aiohttp.ClientError as e:
                if attempt < max_retries - 1:
                    print(f"网络错误，正在重试 ({attempt + 1}/{max_retries}): {str(e)}")
                    await asyncio.sleep(base_retry_delay * (self.backoff_multiplier ** attempt))
                    continue
                raise Exception(f"请求异常: {str(e)}")
            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    print(f"请求超时，正在重试 ({attempt + 1}/{max_retries})")
                    await asyncio.sleep(base_retry_delay * (self.backoff_multiplier ** attempt))
                    continue
                raise Exception("请求超时")
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"未知错误，正在重试 ({attempt + 1}/{max_retries}): {str(e)}")
                    await asyncio.sleep(base_retry_delay * (self.backoff_multiplier ** attempt))
                    continue
                raise Exception(f"请求异常: {str(e)}")
    
    async def chat_stream(self, messages: list, **kwargs) -> AsyncGenerator[str, None]:
        """流式聊天回复（带重试机制）"""
        url = f"{self.api_base}/chat/completions"

        data = {
            "model": kwargs.get('model', self.model),
            "messages": messages,
            "temperature": kwargs.get('temperature', self.temperature),
            "max_tokens": kwargs.get('max_tokens', self.max_tokens),
            "presence_penalty": kwargs.get('presence_penalty', self.presence_penalty),
            "frequency_penalty": kwargs.get('frequency_penalty', self.frequency_penalty),
            "stream": True
        }
        record_payload(self.provider_name, data["model"], messages, {"stream": True})

        # 使用配置的超时设置
        timeout = ClientTimeout(
            connect=self.timeout_connect,
            sock_connect=self.timeout_sock_connect,
            sock_read=self.timeout_sock_read,
            total=self.timeout_total
        )

        max_retries = self.max_retries
        base_retry_delay = self.retry_delay

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, headers=self._get_headers(), json=data) as response:
                        if response.status == 200:
                            async for line in response.content:
                                line = line.decode('utf-8').strip()
                                if line.startswith('data: '):
                                    data_str = line[6:]
                                    if data_str == '[DONE]':
                                        break
                                    try:
                                        data_obj = json.loads(data_str)
                                        if 'choices' in data_obj and len(data_obj['choices']) > 0:
                                            delta = data_obj['choices'][0].get('delta', {})
                                            content = delta.get('content')
                                            if content is not None:
                                                yield str(content)
                                    except json.JSONDecodeError:
                                        continue
                            return  # 成功完成，退出重试循环
                        else:
                            error_text = await response.text()
                            if attempt < max_retries - 1:
                                print(f"API请求失败，正在重试 ({attempt + 1}/{max_retries}): {response.status}")
                                await asyncio.sleep(base_retry_delay * (self.backoff_multiplier ** attempt))
                                continue
                            raise Exception(f"API请求失败: {response.status} - {error_text}")
            except aiohttp.ClientError as e:
                if attempt < max_retries - 1:
                    print(f"网络错误，正在重试 ({attempt + 1}/{max_retries}): {str(e)}")
                    await asyncio.sleep(base_retry_delay * (self.backoff_multiplier ** attempt))
                    continue
                raise Exception(f"请求异常: {str(e)}")
            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    print(f"请求超时，正在重试 ({attempt + 1}/{max_retries})")
                    await asyncio.sleep(base_retry_delay * (self.backoff_multiplier ** attempt))
                    continue
                raise Exception("请求超时")
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"未知错误，正在重试 ({attempt + 1}/{max_retries}): {str(e)}")
                    await asyncio.sleep(base_retry_delay * (self.backoff_multiplier ** attempt))
                    continue
                raise Exception(f"请求异常: {str(e)}")
    
    async def test_connection(self) -> bool:
        """测试API连接"""
        try:
            test_messages = [
                {"role": "user", "content": "测试连接"}
            ]
            await self.chat(test_messages, max_tokens=10)
            return True
        except Exception:
            return False
