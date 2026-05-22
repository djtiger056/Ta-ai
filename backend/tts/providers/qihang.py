"""
启航AI TTS 提供商
"""

import aiohttp
import asyncio
from typing import Dict, Any, Optional, List
from ..base import BaseTTSProvider
import logging
import re

logger = logging.getLogger(__name__)


class QihangTTSProvider(BaseTTSProvider):
    """启航AI TTS 提供商"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_base = config.get('api_base') or config.get('base_url') or 'https://api.qhaigc.net/v1'
        self.api_key = config.get('api_key', '')
        self.model = config.get('model', 'qhai-tts')
        self.default_voice = config.get('voice', '柔情萝莉')

    def _auth_values(self) -> List[str]:
        api_key = (self.api_key or '').strip()
        if api_key.lower().startswith('bearer '):
            return [api_key, api_key.split(None, 1)[1].strip()]
        return [api_key, f'Bearer {api_key}']

    def _get_headers(self, auth_value: Optional[str] = None, *, json: bool = False) -> Dict[str, str]:
        """官方示例使用原始 Key，OpenAPI 声明为 Bearer；调用处会兼容重试。"""
        auth_value = auth_value or self._auth_values()[0]
        headers = {'Authorization': auth_value}
        if json:
            headers['Content-Type'] = 'application/json'
        return headers
    
    async def synthesize(self, text: str, voice: Optional[str] = None) -> bytes:
        """
        合成语音
        
        Args:
            text: 要合成的文本
            voice: 语音角色，可选
            
        Returns:
            bytes: 音频数据
            
        Raises:
            Exception: 合成失败时抛出异常
        """
        if not self.api_key:
            raise ValueError("启航AI API密钥未配置")
        
        voice = voice or self.default_voice
        
        data = {
            'model': self.model,
            'input': text,
            'voice': voice
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                last_error = ""
                for index, auth_value in enumerate(self._auth_values()):
                    async with session.post(
                        f"{self.api_base.rstrip('/')}/audio/speech",
                        headers=self._get_headers(auth_value, json=True),
                        json=data
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            last_error = f"{response.status} - {error_text}"
                            if response.status in (401, 403) and index == 0:
                                continue
                            logger.error(f"启航AI TTS 请求失败: {last_error}")
                            raise Exception(f"启航AI TTS 请求失败: {response.status}")

                        audio_data = await response.read()
                        logger.info(f"启航AI TTS 合成成功，文本长度: {len(text)}，音频大小: {len(audio_data)}")
                        return audio_data
                raise Exception(f"启航AI TTS 请求失败: {last_error}")
                    
        except aiohttp.ClientError as e:
            logger.error(f"启航AI TTS 网络请求失败: {str(e)}")
            raise Exception(f"启航AI TTS 网络请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"启航AI TTS 合成失败: {str(e)}")
            raise Exception(f"启航AI TTS 合成失败: {str(e)}")

    def _extract_voices_from_response(self, result: Any) -> List[Dict[str, str]]:
        """尽可能兼容不同返回格式，提取语音列表"""
        voices: List[Dict[str, str]] = []
        candidates = []

        if isinstance(result, dict):
            if isinstance(result.get('voice_characters'), list):
                candidates = result.get('voice_characters', [])
            elif isinstance(result.get('data'), list):
                candidates = result.get('data', [])
            elif isinstance(result.get('voices'), list):
                candidates = result.get('voices', [])
        elif isinstance(result, list):
            candidates = result

        for item in candidates:
            if isinstance(item, dict):
                name = item.get('name') or item.get('id') or item.get('voice') or ''
                description = item.get('description') or item.get('desc') or ''
                if name:
                    voices.append({'name': name, 'description': description})
            elif isinstance(item, str):
                voices.append({'name': item, 'description': ''})

        return voices
    
    async def get_voices(self, allow_fallback: bool = True) -> List[Dict[str, str]]:
        """
        获取可用语音角色列表

        Returns:
            List[Dict[str, str]]: 语音角色列表，包含 name 和 description
        """
        if not self.api_key:
            raise ValueError("启航AI API密钥未配置")

        # 默认兜底列表，保证界面可用
        fallback_voices = [{
            'name': self.default_voice,
            'description': '默认音色'
        }]

        # 逐个尝试可能的接口路径，兼容不同版本
        base_url = self.api_base.rstrip('/')
        candidate_endpoints = [
            f"{base_url}/voice/models/list",  # 调用指南中的正式路径
            f"{base_url}/models",  # OpenAI 兼容模型列表，部分部署会在这里返回 qhai-tts:角色
            f"{base_url}/voice.models/list",
            f"{base_url}/voices",
            f"{base_url}/voice_models",
        ]

        try:
            async with aiohttp.ClientSession() as session:
                last_error = ""
                for auth_value in self._auth_values():
                    auth_failed = False
                    for endpoint in candidate_endpoints:
                        try:
                            async with session.get(endpoint, headers=self._get_headers(auth_value)) as response:
                                if response.status == 404:
                                    logger.warning(f"语音列表接口不存在: {endpoint}")
                                    continue
                                if response.status != 200:
                                    error_text = await response.text()
                                    last_error = f"{response.status} - {error_text}"
                                    logger.error(f"获取启航AI语音列表失败[{endpoint}]: {last_error}")
                                    if response.status in (401, 403):
                                        auth_failed = True
                                        break
                                    continue

                                result = await response.json()

                                # 尝试从 /v1/models API中提取TTS语音角色
                                # 返回格式: {"data": [{"id": "qhai-tts:角色名", "description": "..."}, ...]}
                                if endpoint.endswith('/models') and isinstance(result, dict):
                                    models = result.get('data', [])
                                    voices = []
                                    for model in models:
                                        model_id = model.get('id', '')
                                        # 解析 qhai-tts:角色名 格式
                                        if model_id.startswith('qhai-tts:'):
                                            # 直接从模型ID中提取角色名
                                            voice_name = model_id.split(':', 1)[1] if ':' in model_id else model_id
                                            description = model.get('description', '')
                                            # 清理描述，只保留简短描述
                                            if description:
                                                # 提取"角色"后面的内容作为简短描述
                                                match = re.search(r'角色["\s]*[:：]["\s]*([^"]+?)[，,。]', description)
                                                if match:
                                                    description = match.group(1).strip()
                                            voices.append({
                                                'name': voice_name,
                                                'description': description
                                            })

                                    if voices:
                                        logger.info(f"获取启航AI语音列表成功（{endpoint}），共 {len(voices)} 个语音角色")
                                        return voices
                                    logger.warning(f"启航AI语音列表返回为空（{endpoint}），使用兜底列表")
                                else:
                                    # 尝试其他格式
                                    voices = self._extract_voices_from_response(result)
                                    if voices:
                                        logger.info(f"获取启航AI语音列表成功（{endpoint}），共 {len(voices)} 个语音角色")
                                        return voices
                                    logger.warning(f"启航AI语音列表返回为空（{endpoint}），使用兜底列表")
                        except aiohttp.ClientError as e:
                            logger.error(f"获取启航AI语音列表网络异常[{endpoint}]: {str(e)}")
                            continue
                        except Exception as e:
                            logger.error(f"处理启航AI语音列表响应失败[{endpoint}]: {str(e)}")
                            continue

                    if auth_failed:
                        continue
                    break

            if allow_fallback:
                logger.warning("所有语音列表接口均不可用，返回默认音色列表")
                return fallback_voices
            raise Exception(f"启航AI语音列表接口不可用{f': {last_error}' if last_error else ''}")

        except aiohttp.ClientError as e:
            logger.error(f"获取启航AI语音列表网络请求失败: {str(e)}")
            if allow_fallback:
                return fallback_voices
            raise Exception(f"启航AI语音列表网络请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"获取启航AI语音列表失败: {str(e)}")
            if allow_fallback:
                return fallback_voices
            raise
    
    async def test_connection(self) -> bool:
        """
        测试连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            # 尝试获取语音列表来测试连接
            voices = await self.get_voices(allow_fallback=False)
            return bool(voices)
        except Exception as e:
            logger.error(f"启航AI TTS 连接测试失败: {str(e)}")
            return False
