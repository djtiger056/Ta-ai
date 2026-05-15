import asyncio
import json
import websockets
import base64
import tempfile
import os
import time
import uuid
import random
import re
from typing import Optional, Dict, Any
from ..core.bot import Bot
from ..config import config
from ..api import proactive as proactive_api
from ..utils.text_splitter import smart_split_text
from .debouncer import MessageDebouncer


class QQAdapter:
    """QQ适配器，通过WebSocket连接NapCat"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.qq_config = config.adapters_config.get('qq', {})
        self.ws_host = self.qq_config.get('ws_host', '127.0.0.1')
        self.ws_port = self.qq_config.get('ws_port', 3001)
        self.access_token = self.qq_config.get('access_token', '')
        self.need_at = self.qq_config.get('need_at', True)
        
        # 访问控制配置
        self.access_control_config = self.qq_config.get('access_control', {})
        self.access_control_enabled = self.access_control_config.get('enabled', False)
        self.access_control_mode = self.access_control_config.get('mode', 'disabled')
        self.access_whitelist = set(str(uid) for uid in self.access_control_config.get('whitelist', []))
        self.access_blacklist = set(str(uid) for uid in self.access_control_config.get('blacklist', []))
        self.access_deny_message = self.access_control_config.get('deny_message', '抱歉，你没有权限使用此机器人。')
        
        # 分段发送配置
        self.segment_config = self.qq_config.get('segment_config', {})
        self.segment_enabled = self.segment_config.get('enabled', True)  # 默认启用
        self.max_segment_length = self.segment_config.get('max_segment_length', 100)
        self.min_segment_length = self.segment_config.get('min_segment_length', 5)
        self.delay_range = self.segment_config.get('delay_range', [0.5, 2.0])  # 延迟范围（秒）
        self.split_strategy = self.segment_config.get('strategy', 'sentence')  # 分割策略
        self.min_sentences_to_split = self.segment_config.get('min_sentences_to_split', 2)  # 最小句子数阈值        
        
        # 重连配置
        self.reconnect_config = self.qq_config.get('reconnect_config', {})
        self.max_reconnect_attempts = self.reconnect_config.get('max_attempts', 10)  # 最大重连次数
        self.reconnect_interval = self.reconnect_config.get('interval', 5.0)  # 重连间隔（秒）
        self.connect_timeout = self.reconnect_config.get('connect_timeout', 10.0)  # 连接超时（秒）
        self.heartbeat_timeout = self.reconnect_config.get('heartbeat_timeout', 30.0)  # 心跳超时（秒）
        
        # 重连状态
        self.reconnect_attempts = 0
        self.last_reconnect_time = 0
        
        # 消息防抖配置
        self.debounce_config = self.qq_config.get('debounce', {})
        self.debounce_enabled = self.debounce_config.get('enabled', False)
        self.debounce_delay = self.debounce_config.get('delay', 3.0)
        self.debounce_max_wait = self.debounce_config.get('max_wait', 15.0)
        self.debounce_separator = self.debounce_config.get('separator', '\n')
        self.debouncer = MessageDebouncer(
            delay=self.debounce_delay,
            max_wait=self.debounce_max_wait,
            separator=self.debounce_separator,
        )
        
        self.websocket = None
        self.running = False
        self.user_id = None
        self.follow_up_waiters: Dict[str, asyncio.Future] = {}
        # 防重复发送同一张表情包
        self._emote_send_cache: Dict[str, Dict[str, float]] = {}
        
    async def start(self):
        """启动QQ适配器，带自动重连功能"""
        self.running = True
        self.reconnect_attempts = 0
        
        while self.running:
            try:
                # 构建WebSocket URL
                ws_url = f"ws://{self.ws_host}:{self.ws_port}"
                if self.access_token:
                    ws_url += f"?access_token={self.access_token}"
                
                print(f"🔗 正在连接NapCat WebSocket ({self.reconnect_attempts + 1}/{self.max_reconnect_attempts}): {ws_url}")
                
                # 带超时的连接
                try:
                    # 使用connect_timeout作为连接超时
                    async with asyncio.timeout(self.connect_timeout):
                        websocket = await websockets.connect(ws_url)
                except asyncio.TimeoutError:
                    print(f"⏱️ 连接超时 ({self.connect_timeout}秒)")
                    raise ConnectionError(f"连接超时 ({self.connect_timeout}秒)")
                
                self.websocket = websocket
                print("✅ NapCat连接成功！")
                self.reconnect_attempts = 0  # 连接成功，重置重连计数
                
                # 监听消息
                await self._handle_messages()
                
                # 如果_handle_messages返回，说明连接已断开，进行重连
                print("🔌 连接断开，准备重连...")
                if self.websocket:
                    try:
                        await self.websocket.close()
                    except:
                        pass
                    self.websocket = None
                
            except (websockets.exceptions.ConnectionClosed, ConnectionError, 
                    OSError, asyncio.TimeoutError) as e:
                # 连接失败，准备重连
                self.reconnect_attempts += 1
                error_type = type(e).__name__
                print(f"❌ NapCat连接失败 ({error_type}): {str(e)}")
                
                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    print(f"⚠️ 已达到最大重连次数 ({self.max_reconnect_attempts})，停止重连")
                    self.running = False
                    break
                
                # 等待重连间隔
                wait_time = self.reconnect_interval
                print(f"⏳ 等待 {wait_time:.1f} 秒后重连...")
                await asyncio.sleep(wait_time)
                
            except Exception as e:
                # 其他异常，也尝试重连
                self.reconnect_attempts += 1
                print(f"❌ NapCat连接异常: {str(e)}")
                
                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    print(f"⚠️ 已达到最大重连次数 ({self.max_reconnect_attempts})，停止重连")
                    self.running = False
                    break
                
                wait_time = self.reconnect_interval
                print(f"⏳ 等待 {wait_time:.1f} 秒后重连...")
                await asyncio.sleep(wait_time)
    
    async def _handle_messages(self):
        """处理接收到的消息，带超时和错误处理"""
        print("🎯 开始监听QQ消息...")
        
        while self.running and self.websocket:
            try:
                # 接收消息，带超时设置
                try:
                    message = await asyncio.wait_for(
                        self.websocket.recv(), 
                        timeout=self.heartbeat_timeout
                    )
                except asyncio.TimeoutError:
                    print(f"⏱️ 接收消息超时 ({self.heartbeat_timeout}秒)，可能连接已失效")
                    # 超时视为连接失效，跳出循环进行重连
                    break
                
                # 解析消息
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    print(f"❌ JSON解析失败，消息内容: {message[:100]}...")
                    continue
                
                # 处理消息
                await self._process_message(data)
                
            except websockets.exceptions.ConnectionClosed as e:
                print(f"🔌 NapCat连接已断开: {e.code if e.code else '未知'} - {e.reason if e.reason else '未知原因'}")
                break
            except (OSError, ConnectionError, websockets.exceptions.WebSocketException) as e:
                print(f"🔌 网络连接错误: {type(e).__name__}: {str(e)}")
                break
            except Exception as e:
                print(f"❌ 消息处理错误: {type(e).__name__}: {str(e)}")
                # 其他异常不中断连接，继续处理
                continue
        
        print("🔄 消息处理循环结束，准备重连...")
    
    async def _process_message(self, data: Dict[str, Any]):
        """处理单条消息"""
        post_type = data.get('post_type')
        
        if post_type == 'message':
            await self._handle_chat_message(data)
        elif post_type == 'notice':
            await self._handle_notice(data)
        elif post_type == 'request':
            await self._handle_request(data)
        elif post_type == 'meta_event':
            # 忽略心跳等元事件
            pass
    
    async def _handle_chat_message(self, data: Dict[str, Any]):
        """处理聊天消息"""
        message_type = data.get('message_type')
        
        if message_type == 'private':
            await self._handle_private_message(data)
        elif message_type == 'group':
            await self._handle_group_message(data)
    
    async def _handle_private_message(self, data: Dict[str, Any]):
        """处理私聊消息"""
        user_id = str(data.get('user_id', ''))
        self_id = str(data.get('self_id', ''))
        raw_message = data.get('raw_message', '')
        message = data.get('message', '')
        
        if not raw_message or not user_id:
            return

        # 忽略自己发送的消息（NapCat/OneBot 可能回传自身消息导致重复触发）
        if self_id and user_id == self_id:
            return
        
        # 检查用户访问权限
        has_access, deny_message = self._check_user_access(user_id)
        if not has_access:
            print(f"🚫 私聊消息被拒绝 {user_id}: {deny_message}")
            await self.send_private_message(user_id, deny_message)
            return
        
        # 解析消息内容
        text_content = self._parse_message_content(message)
        if not text_content:
            text_content = raw_message
        
        if not text_content:
            return

        conversation_key = self._get_conversation_key(user_id, is_group=False)
        if self._deliver_follow_up_message(conversation_key, text_content):
            return
        
        print(f"📨 私聊消息 {user_id}: {text_content}")
        
        # 任务变量初始化
        image_task = None
        
        # 检查是否需要生成图像
        image_prompt = self.bot.should_generate_image(text_content, user_id=user_id)
        if image_prompt:
            print(f"🎨 检测到图像生成请求: {image_prompt}")
            # 异步启动图像生成任务，不等待
            image_task = asyncio.create_task(
                self._handle_image_generation(user_id, image_prompt, is_group=False)
            )
            return
        
        # 检查是否需要识别图片
        vision_task = None
        image_segments = self._extract_image_segments(message)
        if image_segments and self.bot.should_recognize_image(image_segments):
            print(f"🔍 检测到图片识别请求，共 {len(image_segments)} 张图片")
            vision_task = asyncio.create_task(
                self._handle_vision_recognition(user_id, image_segments, text_content, is_group=False)
            )
            # 如果有视觉识别任务，则不再进行普通聊天回复
            return

        # 检查是否需要识别语音
        voice_segments = self._extract_voice_segments(message)
        if voice_segments:
            print(f"🎤 检测到语音消息，共 {len(voice_segments)} 段语音")
            asr_task = asyncio.create_task(
                self._handle_asr_recognition(user_id, voice_segments, text_content, is_group=False)
            )
            # 如果有语音识别任务，则不再进行普通聊天回复
            return

        # 生成回复
        if self.debounce_enabled:
            # 使用防抖器：等待用户发完所有消息后再统一回复
            debounce_key = f"private_{user_id}"
            await self.debouncer.add_message(
                debounce_key,
                text_content,
                callback=lambda merged_text: self._do_private_reply(user_id, merged_text),
            )
        else:
            await self._do_private_reply(user_id, text_content)

    async def _do_private_reply(self, user_id: str, text_content: str):
        """执行私聊回复（可能由防抖器合并后调用）"""
        try:
            proactive_api.record_user_activity("qq_private", user_id, user_id, text_content)
            response = await self.bot.chat(text_content, user_id=user_id)
            proactive_api.record_assistant_activity("qq_private", user_id, user_id, response)

            # 检查是否有主动生成的图片
            last_image = self.bot.get_last_generated_image()
            if last_image and last_image.get("image_data"):
                image_data = last_image["image_data"]
                print(f"[QQ Adapter] 检测到Bot主动生成图片，大小: {len(image_data)} bytes")

            voice_only = self.bot.is_voice_only_mode(user_id)

            if voice_only:
                audio_data = await self._resolve_tts_audio(response, user_id)

                text_to_send = self.bot.strip_tts_text(response, user_id=user_id)

                if text_to_send:
                    await self.send_private_message(user_id, text_to_send)

                if audio_data:
                    print(f"🎵 语音合成成功，大小: {len(audio_data)} bytes")
                    await self.send_voice_message(user_id, audio_data)

                if last_image and last_image.get("image_data"):
                    asyncio.create_task(self._send_image_with_delay(user_id, last_image["image_data"], is_group=False))
            else:
                audio_data = await self._resolve_tts_audio(response, user_id)

                text_to_send = self.bot.strip_tts_text(response, user_id=user_id)
                if text_to_send:
                    await self.send_private_message(user_id, text_to_send)

                if audio_data:
                    print(f"🎵 发送语音消息")
                    await self.send_voice_message(user_id, audio_data)

                if last_image and last_image.get("image_data"):
                    asyncio.create_task(self._send_image_with_delay(user_id, last_image["image_data"], is_group=False))

            try:
                await self._maybe_send_emote(text_content, response, user_id, is_group=False)
            except Exception as e:
                print(f"[Emote] emote send failed: {str(e)}")

        except Exception as e:
            print(f"❌ 私聊回复失败: {str(e)}")
            await self.send_private_message(user_id, "抱歉，回复失败了...")
    
    async def _handle_group_message(self, data: Dict[str, Any]):
        """处理群消息"""
        group_id = str(data.get('group_id', ''))
        user_id = str(data.get('user_id', ''))
        self_id = str(data.get('self_id', ''))
        raw_message = data.get('raw_message', '')
        message = data.get('message', '')
        
        if not raw_message or not group_id or not user_id:
            return

        # 忽略自己发送的消息，避免重复响应
        if self_id and user_id == self_id:
            return
        
        # 解析消息内容
        text_content = self._parse_message_content(message)
        if not text_content:
            text_content = raw_message
        
        if not text_content:
            return

        conversation_key = self._get_conversation_key(group_id, is_group=True, user_id=user_id)
        if self._deliver_follow_up_message(conversation_key, text_content):
            return
        
        # 检查是否需要@机器人
        if self.need_at:
            if not self._is_at_bot(message):
                return
        
        # 检查用户访问权限
        has_access, deny_message = self._check_user_access(user_id)
        if not has_access:
            print(f"🚫 群消息被拒绝 {group_id}/{user_id}: {deny_message}")
            await self.send_group_message(group_id, deny_message)
            return
        
        print(f"📨 群消息 {group_id}/{user_id}: {text_content}")
        
        # 任务变量初始化
        image_task = None
        
        # 检查是否需要生成图像
        effective_user_id = user_id or f"group_{group_id}"
        image_prompt = self.bot.should_generate_image(text_content, user_id=effective_user_id)
        if image_prompt:
            print(f"🎨 检测到图像生成请求: {image_prompt}")
            # 异步启动图像生成任务，不等待
            image_task = asyncio.create_task(
                self._handle_image_generation(group_id, image_prompt, is_group=True, group_id=group_id, user_id=user_id)
            )
            return
        
        # 检查是否需要识别图片
        vision_task = None
        image_segments = self._extract_image_segments(message)
        if image_segments and self.bot.should_recognize_image(image_segments):
            print(f"🔍 检测到图片识别请求，共 {len(image_segments)} 张图片")
            vision_task = asyncio.create_task(
                self._handle_vision_recognition(group_id, image_segments, text_content, is_group=True, group_id=group_id, user_id=user_id)
            )
            # 如果有视觉识别任务，则不再进行普通聊天回复
            return

        # 检查是否需要识别语音
        voice_segments = self._extract_voice_segments(message)
        if voice_segments:
            print(f"🎤 检测到语音消息，共 {len(voice_segments)} 段语音")
            asr_task = asyncio.create_task(
                self._handle_asr_recognition(group_id, voice_segments, text_content, is_group=True, group_id=group_id, user_id=user_id)
            )
            # 如果有语音识别任务，则不再进行普通聊天回复
            return

        # 生成回复
        if self.debounce_enabled:
            # 使用防抖器：等待用户发完所有消息后再统一回复
            debounce_key = f"group_{group_id}_{user_id}"
            await self.debouncer.add_message(
                debounce_key,
                text_content,
                callback=lambda merged_text: self._do_group_reply(group_id, user_id, merged_text),
            )
        else:
            await self._do_group_reply(group_id, user_id, text_content)

    async def _do_group_reply(self, group_id: str, user_id: str, text_content: str):
        """执行群聊回复（可能由防抖器合并后调用）"""
        try:
            session_id = f"group_{group_id}_{user_id}"
            proactive_api.record_user_activity("qq_group", group_id, session_id, text_content)
            response = await self.bot.chat(text_content, user_id=user_id, session_id=session_id)
            proactive_api.record_assistant_activity("qq_group", group_id, session_id, response)

            # 检查是否有主动生成的图片
            last_image = self.bot.get_last_generated_image()
            if last_image and last_image.get("image_data"):
                image_data = last_image["image_data"]
                print(f"[QQ Adapter] 检测到Bot主动生成图片（群聊），大小: {len(image_data)} bytes")

            voice_only = self.bot.is_voice_only_mode(user_id)

            if voice_only:
                try:
                    audio_data = await self._resolve_tts_audio(response, user_id)
                except Exception as e:
                    print(f"❌ TTS合成失败: {str(e)}")
                    audio_data = None

                text_to_send = self.bot.strip_tts_text(response, user_id=user_id)
                if text_to_send:
                    await self.send_group_message(group_id, text_to_send)

                if audio_data:
                    print(f"🎵 语音合成成功，大小: {len(audio_data)} bytes")
                    await self.send_voice_message(group_id, audio_data, is_group=True, group_id=group_id)

                if last_image and last_image.get("image_data"):
                    asyncio.create_task(self._send_image_with_delay(group_id, last_image["image_data"], is_group=True, group_id=group_id))
            else:
                audio_data = await self._resolve_tts_audio(response, user_id)

                text_to_send = self.bot.strip_tts_text(response, user_id=user_id)
                if text_to_send:
                    await self.send_group_message(group_id, text_to_send)

                if audio_data:
                    print(f"🎵 发送语音消息")
                    await self.send_voice_message(group_id, audio_data, is_group=True, group_id=group_id)

                if last_image and last_image.get("image_data"):
                    asyncio.create_task(self._send_image_with_delay(group_id, last_image["image_data"], is_group=True, group_id=group_id))

            try:
                await self._maybe_send_emote(text_content, response, group_id, is_group=True, group_id=group_id)
            except Exception as e:
                print(f"[Emote] emote send failed: {str(e)}")

        except Exception as e:
            print(f"❌ 群回复失败: {str(e)}")
            await self.send_group_message(group_id, "抱歉，回复失败了...")
    
    def _get_conversation_key(self, target_id: str, is_group: bool, user_id: Optional[str] = None) -> str:
        """构造用于跟踪会话的键"""
        if is_group and user_id:
            return f"group_{target_id}_{user_id}"
        return str(target_id)

    def _deliver_follow_up_message(self, conversation_key: str, message_text: Optional[str]) -> bool:
        """
        如果存在等待的图片识别补充消息，则投递该消息并终止常规处理。
        """
        if not message_text or not message_text.strip():
            return False
        future = self.follow_up_waiters.get(conversation_key)
        if future and not future.done():
            future.set_result(message_text.strip())
            return True
        return False

    def _strip_cq_codes(self, text: str) -> str:
        """去掉CQ码、首尾空白并压缩多余空行，避免把原始富文本塞进记忆/LLM。"""
        try:
            import re
            cleaned = re.sub(r"\[CQ:[^\]]+\]", "", text or "")
            cleaned = cleaned.replace("\r", "")
            cleaned = re.sub(r"\n{2,}", "\n", cleaned)
            return cleaned.strip()
        except Exception:
            return (text or "").strip()

    def _parse_message_content(self, message) -> str:
        """解析消息内容，提取纯文本"""
        if isinstance(message, str):
            return self._strip_cq_codes(message)
        
        if isinstance(message, list):
            text_parts = []
            for segment in message:
                if segment.get('type') == 'text':
                    text_parts.append(segment.get('data', {}).get('text', ''))
            return self._strip_cq_codes(''.join(text_parts))
        
        return str(message).strip()
    
    def _extract_image_segments(self, message) -> list:
        """提取消息中的图片段
        
        Args:
            message: 消息内容，可以是字符串或列表
            
        Returns:
            图片段列表，每个元素是包含type和data的字典
        """
        print(f"[DEBUG] _extract_image_segments: message type={type(message)}, is_list={isinstance(message, list)}")
        if not isinstance(message, list):
            print(f"[DEBUG] message is not a list, returning empty list. message preview: {str(message)[:100]}")
            return []
        
        image_segments = []
        for segment in message:
            if isinstance(segment, dict) and segment.get('type') == 'image':
                image_segments.append(segment)
        print(f"[DEBUG] Found {len(image_segments)} image segments")
        if image_segments:
            print(f"[DEBUG] First image segment keys: {list(image_segments[0].keys()) if image_segments else []}")
        return image_segments
    
    def _extract_image_data(self, image_segment: dict) -> Optional[bytes]:
        """从图片段中提取图片数据

        Args:
            image_segment: 图片段字典

        Returns:
            图片二进制数据，如果无法提取则返回None
        """
        try:
            data = image_segment.get('data', {})
            file_info = data.get('file', '')
            url = data.get('url', '')

            # 检查是否是base64格式
            if file_info.startswith('base64://'):
                import base64
                base64_data = file_info[9:]  # 移除'base64://'
                return base64.b64decode(base64_data)

            # 如果有URL，尝试下载图片
            if url:
                try:
                    import httpx
                    print(f"[DEBUG] 正在从URL下载图片: {url[:100]}...")
                    response = httpx.get(url, timeout=30.0)
                    if response.status_code == 200:
                        print(f"[DEBUG] 图片下载成功，大小: {len(response.content)} bytes")
                        return response.content
                    else:
                        print(f"[DEBUG] 图片下载失败，状态码: {response.status_code}")
                except Exception as e:
                    print(f"[DEBUG] URL下载图片失败: {str(e)}")

            return None
        except Exception as e:
            print(f"提取图片数据失败: {str(e)}")
            return None

    def _extract_voice_segments(self, message) -> list:
        """提取消息中的语音段

        Args:
            message: 消息内容，可以是字符串或列表

        Returns:
            语音段列表，每个元素是包含type和data的字典
        """
        print(f"[DEBUG] _extract_voice_segments: message type={type(message)}, is_list={isinstance(message, list)}")
        if not isinstance(message, list):
            print(f"[DEBUG] message is not a list, returning empty list.")
            return []

        voice_segments = []
        for segment in message:
            if isinstance(segment, dict) and segment.get('type') == 'record':
                voice_segments.append(segment)
        print(f"[DEBUG] Found {len(voice_segments)} voice segments")
        if voice_segments:
            print(f"[DEBUG] First voice segment keys: {list(voice_segments[0].keys()) if voice_segments else []}")
        return voice_segments

    def _extract_voice_data(self, voice_segment: dict) -> Optional[bytes]:
        """从语音段中提取语音数据

        Args:
            voice_segment: 语音段字典

        Returns:
            语音二进制数据，如果无法提取则返回None
        """
        try:
            data = voice_segment.get('data', {})
            file_info = data.get('file', '')
            url = data.get('url', '')

            # 检查是否是base64格式
            if file_info.startswith('base64://'):
                import base64
                base64_data = file_info[9:]  # 移除'base64://'
                print(f"[DEBUG] 提取base64语音数据，原始长度: {len(base64_data)}")
                return base64.b64decode(base64_data)

            # 如果有URL，尝试下载语音
            if url:
                try:
                    import httpx
                    print(f"[DEBUG] 正在从URL下载语音: {url[:100]}...")
                    response = httpx.get(url, timeout=30.0)
                    if response.status_code == 200:
                        print(f"[DEBUG] 语音下载成功，大小: {len(response.content)} bytes")
                        return response.content
                    else:
                        print(f"[DEBUG] 语音下载失败，状态码: {response.status_code}")
                except Exception as e:
                    print(f"[DEBUG] URL下载语音失败: {str(e)}")

            return None
        except Exception as e:
            print(f"提取语音数据失败: {str(e)}")
            return None

    def _is_at_bot(self, message) -> bool:
        """检查消息是否@了机器人"""
        if isinstance(message, list):
            for segment in message:
                if segment.get('type') == 'at' and segment.get('data', {}).get('qq') == 'all':
                    return True
        return False
    
    def _check_user_access(self, user_id: str) -> tuple[bool, Optional[str]]:
        """检查用户是否有访问权限
        
        Args:
            user_id: 用户ID
            
        Returns:
            (是否允许访问, 拒绝消息(None表示允许))
        """
        # 每次都从 config 读取最新的访问控制配置，确保更新后立即生效
        access_control_config = config.qq_access_control_config
        access_control_enabled = access_control_config.get('enabled', False)
        access_control_mode = access_control_config.get('mode', 'disabled')
        access_whitelist = set(str(uid) for uid in access_control_config.get('whitelist', []))
        access_blacklist = set(str(uid) for uid in access_control_config.get('blacklist', []))
        access_deny_message = access_control_config.get('deny_message', '抱歉，你没有权限使用此机器人。')
        
        # 如果访问控制未启用，允许所有用户
        if not access_control_enabled:
            return True, None
        
        user_id_str = str(user_id)
        
        # 黑名单模式：黑名单中的用户被拒绝
        if access_control_mode == 'blacklist':
            if user_id_str in access_blacklist:
                return False, access_deny_message
            return True, None
        
        # 白名单模式：只有白名单中的用户被允许
        elif access_control_mode == 'whitelist':
            if user_id_str in access_whitelist:
                return True, None
            return False, access_deny_message
        
        # 其他模式（disabled）：允许所有用户
        return True, None
    
    def _count_sentences(self, text: str) -> int:
        """
        统计文本中的句子数量
        
        Args:
            text: 要统计的文本
            
        Returns:
            句子数量
        """
        if not text or not text.strip():
            return 0
        
        # 按中文和英文标点分割
        sentences = re.split(r'[。！？.!?]+', text.strip())
        # 过滤空字符串
        sentences = [s for s in sentences if s.strip()]
        return len(sentences)
    
    async def _send_segmented(self, target_id: str, message: str, is_group: bool = False, group_id: Optional[str] = None):
        """
        分段发送消息
        
        Args:
            target_id: 目标ID（用户ID或群ID）
            message: 要发送的消息
            is_group: 是否为群消息
            group_id: 如果是群消息，提供群ID（与target_id相同）
        """
        if not self.websocket:
            return
        
        # 如果不启用分段发送，直接发送
        if not self.segment_enabled:
            if is_group:
                await self._send_raw_group_message(target_id, message)
            else:
                await self._send_raw_private_message(target_id, message)
            return
        
        # 判断是否需要分段发送
        # 如果消息长度超过最大段长度，或者句子数量达到最小分割阈值，则进行分段
        sentence_count = self._count_sentences(message)
        should_segment = (
            len(message) > self.max_segment_length or 
            sentence_count >= self.min_sentences_to_split
        )
        
        if not should_segment:
            if is_group:
                await self._send_raw_group_message(target_id, message)
            else:
                await self._send_raw_private_message(target_id, message)
            return
        
        # 分割文本
        segments = []
        if self.split_strategy == 'sentence':
            # 分句发送模式：直接按句子分割
            sentences = re.split(r'[。！？.!?]+', message.strip())
            sentences = [s.strip() for s in sentences if s.strip()]
            
            # 合并过短的句子（如果下一个句子也很短，就合并）
            merged_sentences = []
            i = 0
            while i < len(sentences):
                current = sentences[i]
                # 如果当前句子太短，且不是最后一个句子，尝试与下一个句子合并
                if len(current) < self.min_segment_length and i < len(sentences) - 1:
                    next_sentence = sentences[i + 1]
                    combined = current + '，' + next_sentence
                    if len(combined) <= self.max_segment_length:
                        merged_sentences.append(combined)
                        i += 2
                    else:
                        # 合并失败，尝试将短句合并到前一个句子
                        if merged_sentences and len(merged_sentences[-1]) + len(current) + 1 <= self.max_segment_length:
                            merged_sentences[-1] = merged_sentences[-1] + '，' + current
                        else:
                            # 无法合并，也要保留短句（不过滤）
                            merged_sentences.append(current)
                        i += 1
                else:
                    merged_sentences.append(current)
                    i += 1
            
            # 不再过滤过短的句子，避免消息不完整
            segments = merged_sentences
            
            # 如果分割后只剩一段，检查是否需要合并（原消息本身就很短）
            if len(segments) == 1 and len(message) <= self.max_segment_length:
                # 只有一段短消息，直接发送
                if is_group:
                    await self._send_raw_group_message(target_id, message)
                else:
                    await self._send_raw_private_message(target_id, message)
                return
        else:
            # 使用原有的smart_split_text进行分割
            segments = smart_split_text(
                text=message,
                max_length=self.max_segment_length,
                min_length=self.min_segment_length,
                strategy=self.split_strategy
            )
        
        if not segments:
            return
        
        print(f"📝 消息分割为 {len(segments)} 段，将分段发送")
        
        # 逐段发送
        for i, segment in enumerate(segments, 1):
            # 发送当前段
            if is_group:
                await self._send_raw_group_message(target_id, segment)
            else:
                await self._send_raw_private_message(target_id, segment)
            
            # 如果不是最后一段，添加延迟
            if i < len(segments):
                delay = random.uniform(self.delay_range[0], self.delay_range[1])
                print(f"⏳ 段 {i}/{len(segments)} 发送完成，等待 {delay:.2f} 秒...")
                await asyncio.sleep(delay)
        
        print(f"✅ 分段发送完成，共发送 {len(segments)} 段")
    
    async def _send_raw_private_message(self, user_id: str, message: str):
        """底层私聊消息发送（不进行分段处理）"""
        if not self.websocket:
            return
        
        data = {
            "action": "send_private_msg",
            "params": {
                "user_id": int(user_id),
                "message": message
            }
        }
        
        await self.websocket.send(json.dumps(data))
        print(f"📤 发送私聊消息 {user_id}: {message}")
    
    async def _send_raw_group_message(self, group_id: str, message: str):
        """底层群消息发送（不进行分段处理）"""
        if not self.websocket:
            return
        
        data = {
            "action": "send_group_msg",
            "params": {
                "group_id": int(group_id),
                "message": message
            }
        }
        
        await self.websocket.send(json.dumps(data))
        print(f"📤 发送群消息 {group_id}: {message}")
    
    async def send_private_message(self, user_id: str, message: str):
        """
        发送私聊消息（自动分段）
        
        根据segment_config配置决定是否分段发送消息
        """
        await self._send_segmented(user_id, message, is_group=False)
    
    async def send_group_message(self, group_id: str, message: str):
        """
        发送群消息（自动分段）
        
        根据segment_config配置决定是否分段发送消息
        """
        await self._send_segmented(group_id, message, is_group=True, group_id=group_id)
    
    async def _handle_notice(self, data: Dict[str, Any]):
        """处理通知消息"""
        # 可以在这里处理好友添加、群邀请等通知
        pass
    
    async def _handle_request(self, data: Dict[str, Any]):
        """处理请求消息"""
        # 可以在这里处理好友请求、群邀请等
        pass
    
    async def send_voice_message(self, user_id: str, audio_data: bytes, is_group: bool = False, group_id: Optional[str] = None):
        """发送语音消息（base64编码）"""
        if not self.websocket:
            return
        
        if not audio_data:
            print("❌ 语音数据为空")
            return
        
        print(f"🎵 准备发送语音消息，数据大小: {len(audio_data)} bytes")
        
        # 尝试多种base64编码格式
        base64_data = base64.b64encode(audio_data).decode('utf-8')
        print(f"🎵 生成base64语音消息，长度: {len(base64_data)} chars")
        
        # 定义不同格式的消息
        formats = [
            # 格式1: base64://协议（常见CQ码格式）
            {"name": "CQ码base64", "message": f"[CQ:record,file=base64://{base64_data}]"},
            
            # 格式2: 纯base64字符串（某些NapCat版本可能支持）
            {"name": "纯base64", "message": base64_data},
            
            # 格式3: 消息段数组格式（JSON）
            {"name": "消息段JSON", "message": json.dumps([{
                "type": "record",
                "data": {
                    "file": f"base64://{base64_data}"
                }
            }])},
            
            # 格式4: 带魔数的CQ码
            {"name": "CQ码带魔数", "message": f"[CQ:record,file=base64://{base64_data},magic=1]"},
        ]
        
        # 尝试所有格式，直到成功或全部失败
        success = False
        last_error = None
        
        for format_info in formats:
            message = format_info["message"]
            format_name = format_info["name"]
            
            if is_group and group_id:
                data = {
                    "action": "send_group_msg",
                    "params": {
                        "group_id": int(group_id),
                        "message": message
                    }
                }
            else:
                data = {
                    "action": "send_private_msg",
                    "params": {
                        "user_id": int(user_id),
                        "message": message
                    }
                }
            
            try:
                json_data = json.dumps(data)
                print(f"📤 尝试发送语音消息 [{format_name}] (前100字符): {json_data[:100]}...")
                await self.websocket.send(json_data)
                print(f"✅ 语音消息发送成功 [{format_name}] {'群组' if is_group else '私聊'} {user_id}")
                success = True
                break  # 成功则跳出循环
                
            except Exception as e:
                last_error = e
                print(f"❌ 格式 [{format_name}] 发送失败: {str(e)}")
                # 继续尝试下一种格式
        
        if not success:
            print(f"❌ 所有语音消息格式都发送失败，最后错误: {last_error}")
    
    async def _send_image_with_delay(self, target_id: str, image_data: bytes, is_group: bool = False, group_id: Optional[str] = None, delay_seconds: float = 5.0):
        """延迟发送图片消息
        
        Args:
            target_id: 目标ID（用户ID或群ID）
            image_data: 图片数据
            is_group: 是否为群消息
            group_id: 群ID（如果是群消息）
            delay_seconds: 延迟秒数，默认5秒
        """
        try:
            # 延迟指定秒数
            await asyncio.sleep(delay_seconds)
            # 发送图片
            await self.send_image_message(target_id, image_data, is_group=is_group, group_id=group_id)
            print(f"[QQ Adapter] 图片已延迟 {delay_seconds} 秒后发送成功")
        except Exception as e:
            print(f"[QQ Adapter] 延迟发送图片失败: {str(e)}")
    
    async def _handle_image_generation(self, target_id: str, prompt: str, is_group: bool = False, group_id: Optional[str] = None, user_id: Optional[str] = None):
        """处理图像生成请求（仅生成图片，失败时发送错误消息）"""
        try:
            # 配置按“用户”生效；上下文/记忆按“会话”隔离（群聊会话独立）
            effective_user_id = user_id or target_id
            session_id = target_id
            if is_group and group_id and user_id:
                session_id = f"group_{group_id}_{user_id}"

            # 生成图像
            image_data = await self.bot.generate_image(prompt, user_id=effective_user_id, session_id=session_id)
            
            if image_data:
                # 发送图片
                await self.send_image_message(target_id, image_data, is_group=is_group, group_id=group_id)
            else:
                # 发送失败消息
                image_gen_config = self.bot.get_image_gen_config()
                error_msg = image_gen_config.get('error_message', '😢 图片生成失败：{error}').format(error="未知错误")
                if is_group:
                    await self.send_group_message(target_id, error_msg)
                else:
                    await self.send_private_message(target_id, error_msg)
                    
        except Exception as e:
            print(f"❌ 图像生成处理失败: {str(e)}")
            image_gen_config = self.bot.get_image_gen_config()
            error_msg = image_gen_config.get('error_message', '😢 图片生成失败：{error}').format(error=str(e))
            if is_group:
                await self.send_group_message(target_id, error_msg)
            else:
                await self.send_private_message(target_id, error_msg)
    
    async def _handle_vision_recognition(self, target_id: str, image_segments: list, text_content: str, 
                                        is_group: bool = False, group_id: Optional[str] = None, 
                                        user_id: Optional[str] = None):
        """处理视觉识别请求
        
        Args:
            target_id: 目标ID（用户ID或群ID）
            image_segments: 图片段列表
            text_content: 文本内容（如果有）
            is_group: 是否为群消息
            group_id: 群ID（如果是群消息）
            user_id: 用户ID（如果是群消息）
        """
        try:
            vision_config = self.bot.get_vision_config()
            print(f"[DEBUG] 获取的vision_config键: {list(vision_config.keys())}")
            print(f"[DEBUG] vision_config中是否有follow_up_timeout: {'follow_up_timeout' in vision_config}")
            if 'follow_up_timeout' in vision_config:
                print(f"[DEBUG] vision_config['follow_up_timeout'] = {vision_config['follow_up_timeout']}")
            if not vision_config.get('enabled', False):
                print("视觉识别功能未启用")
                return
            

            
            # 创建等待补充消息的future
            conversation_key = self._get_conversation_key(target_id, is_group, user_id)
            existing_future = self.follow_up_waiters.get(conversation_key)
            if existing_future and not existing_future.done():
                existing_future.cancel()
            loop = asyncio.get_running_loop()
            follow_up_future = loop.create_future()
            self.follow_up_waiters[conversation_key] = follow_up_future
            
            # 处理每张图片
            recognition_results = []
            for segment in image_segments:
                # 提取图片数据
                image_data = self._extract_image_data(segment)
                if not image_data:
                    print("❌ 无法提取图片数据")
                    continue
                
                # 识别图片
                recognition_text = await self.bot.recognize_image(image_data=image_data, prompt="描述这幅图")
                if recognition_text:
                    recognition_results.append(recognition_text)
            
            if not recognition_results:
                error_msg = vision_config.get('error_message', '😢 图片识别失败：{error}').format(error="无法识别")
                if is_group:
                    await self.send_group_message(target_id, error_msg)
                else:
                    await self.send_private_message(target_id, error_msg)
                # 清理future
                conversation_key = self._get_conversation_key(target_id, is_group, user_id)
                self.follow_up_waiters.pop(conversation_key, None)
                return
            
            # 合并识别结果
            combined_recognition = "\n".join(recognition_results)
            conversation_key = self._get_conversation_key(target_id, is_group, user_id)
            # 获取配置中的等待超时时间
            follow_up_timeout = vision_config.get('follow_up_timeout', 5.0)
            print(f"[DEBUG] 视觉识别配置中的follow_up_timeout: {follow_up_timeout}")
            follow_up_message = await self._wait_for_follow_up_message(conversation_key, timeout=follow_up_timeout)

            # 构建最终用户消息：指令文本 + 识别结果
            instruction_text = vision_config.get('instruction_text', '这是一张图片的描述，请根据描述生成一段合适的话语：')
            user_message_parts = []
            if text_content and text_content.strip():
                user_message_parts.append(text_content.strip())
            if follow_up_message:
                user_message_parts.append(follow_up_message)
            user_message_parts.append(f"{instruction_text}\n\n{combined_recognition}")
            user_message = "\n\n".join(user_message_parts)
            
            # 调用LLM生成回复
            user_identifier = target_id
            if is_group and user_id:
                user_identifier = f"group_{group_id}_{user_id}"
            
            effective_user_id = user_id or target_id
            proactive_api.record_user_activity(
                "qq_group" if is_group else "qq_private",
                target_id,
                user_identifier,
                user_message,
            )
            llm_response = await self.bot.chat(user_message, user_id=effective_user_id, session_id=user_identifier)
            proactive_api.record_assistant_activity(
                "qq_group" if is_group else "qq_private",
                target_id,
                user_identifier,
                llm_response,
            )
             
            # 语音合成（如果有）
            audio_data = await self._resolve_tts_audio(llm_response, effective_user_id)

            # 移除已用于TTS的文本，避免重复发送
            text_to_send = self.bot.strip_tts_text(llm_response, user_id=effective_user_id)

            # 发送文本（如果有剩余文本）
            if text_to_send:
                if is_group:
                    await self.send_group_message(target_id, text_to_send)
                else:
                    await self.send_private_message(target_id, text_to_send)

            # 发送语音（如果有）
            if audio_data:
                await self.send_voice_message(target_id, audio_data, is_group=is_group, group_id=group_id)
            
        except Exception as e:
            print(f"❌ 视觉识别处理失败: {str(e)}")
            vision_config = self.bot.get_vision_config()
            error_msg = vision_config.get('error_message', '😢 图片识别失败：{error}').format(error=str(e))
            if is_group:
                await self.send_group_message(target_id, error_msg)
            else:
                await self.send_private_message(target_id, error_msg)

    async def _handle_asr_recognition(self, target_id: str, voice_segments: list, text_content: str,
                                      is_group: bool = False, group_id: Optional[str] = None,
                                      user_id: Optional[str] = None):
        """处理语音识别请求

        Args:
            target_id: 目标ID（用户ID或群ID）
            voice_segments: 语音段列表
            text_content: 文本内容（如果有）
            is_group: 是否为群消息
            group_id: 群ID（如果是群消息）
            user_id: 用户ID（如果是群消息）
        """
        try:
            # 获取ASR配置
            asr_config = config.asr_config if hasattr(config, 'asr_config') else None
            if not asr_config or not asr_config.enabled:
                print("ASR功能未启用")
                return

            # 发送处理中消息（可选）
            processing_msg = asr_config.processing_message
            if processing_msg:
                if is_group:
                    await self.send_group_message(target_id, processing_msg)
                else:
                    await self.send_private_message(target_id, processing_msg)

            # 处理每段语音
            transcription_results = []
            for segment in voice_segments:
                # 提取语音数据
                voice_data = self._extract_voice_data(segment)
                if not voice_data:
                    print("❌ 无法提取语音数据")
                    continue

                # 语音转文本
                transcription_text = await self.bot.transcribe_voice(voice_data, filename="voice.mp3")
                if transcription_text:
                    transcription_results.append(transcription_text)

            if not transcription_results:
                error_msg = asr_config.error_message
                if is_group:
                    await self.send_group_message(target_id, error_msg)
                else:
                    await self.send_private_message(target_id, error_msg)
                return

            # 合并识别结果
            combined_transcription = "\n".join(transcription_results)
            print(f"🎤 语音识别结果: {combined_transcription}")

            # 构建最终用户消息
            user_message_parts = []
            cleaned_text = (text_content or "").strip()
            if cleaned_text:
                user_message_parts.append(cleaned_text)
            user_message_parts.append(combined_transcription)
            user_message = "\n".join(user_message_parts)

            # 调用LLM生成回复
            user_identifier = target_id
            if is_group and user_id:
                user_identifier = f"group_{group_id}_{user_id}"

            effective_user_id = user_id or target_id
            proactive_api.record_user_activity(
                "qq_group" if is_group else "qq_private",
                target_id,
                user_identifier,
                user_message,
            )
            llm_response = await self.bot.chat(user_message, user_id=effective_user_id, session_id=user_identifier)
            proactive_api.record_assistant_activity(
                "qq_group" if is_group else "qq_private",
                target_id,
                user_identifier,
                llm_response,
            )

            # 语音合成（如果有）
            audio_data = await self._resolve_tts_audio(llm_response, effective_user_id)

            # 移除已用于TTS的文本，避免重复发送
            text_to_send = self.bot.strip_tts_text(llm_response, user_id=effective_user_id)

            # 发送文本（如果有剩余文本）
            if text_to_send:
                if is_group:
                    await self.send_group_message(target_id, text_to_send)
                else:
                    await self.send_private_message(target_id, text_to_send)

            # 发送语音（如果有）
            if audio_data:
                await self.send_voice_message(target_id, audio_data, is_group=is_group, group_id=group_id)

        except Exception as e:
            print(f"❌ 语音识别处理失败: {str(e)}")
            asr_config = config.asr_config if hasattr(config, 'asr_config') else None
            error_msg = asr_config.error_message if asr_config else "语音识别失败了呢"
            if is_group:
                await self.send_group_message(target_id, error_msg)
            else:
                await self.send_private_message(target_id, error_msg)
    async def _maybe_send_emote(self, user_text: str, bot_reply: str, target_id: str,
                                is_group: bool = False, group_id: Optional[str] = None):
        """Send a sticker based on context and probability, with short-term dedup"""
        if not getattr(self.bot, 'emote_manager', None):
            return
        try:
            selection = self.bot.emote_manager.select_emote(user_text, bot_reply)
        except Exception as e:
            print(f'[Emote] failed to select emote: {str(e)}')
            return

        if not selection:
            return

        # 短时间内同一会话重复的同一文件不再发送，避免 NapCat/OneBot 端重复推送
        try:
            import time
            conversation_key = self._get_conversation_key(target_id, is_group, group_id if is_group else None)
            cache = self._emote_send_cache.setdefault(conversation_key, {})
            now = time.time()
            last_ts = cache.get(selection.file_path, 0)
            if now - last_ts < 2.0:
                print(f"[Emote] skip duplicate emote within 2s: {selection.file_path}")
                return
            cache[selection.file_path] = now
        except Exception as e:
            print(f"[Emote] dedup check failed: {str(e)}")

        try:
            await self.send_image_message(
                target_id,
                selection.as_bytes(),
                is_group=is_group,
                group_id=group_id
            )
            print(f'[Emote] sent emote {selection.category}/{selection.file_name}')
        except Exception as e:
            print(f'[Emote] send emote failed: {str(e)}')


    async def _wait_for_follow_up_message(self, conversation_key: str, timeout: float = 5.0) -> Optional[str]:
        """等待用户在识别完成后的短暂时间内发送的补充消息"""
        follow_up_future: Optional[asyncio.Future] = None
        try:
            existing_future = self.follow_up_waiters.get(conversation_key)
            if existing_future is not None:
                # 使用已存在的future
                follow_up_future = existing_future
            else:
                # 创建新的future
                loop = asyncio.get_running_loop()
                follow_up_future = loop.create_future()
                self.follow_up_waiters[conversation_key] = follow_up_future
            
            message = await asyncio.wait_for(follow_up_future, timeout=timeout)
            return message.strip() if isinstance(message, str) else None
        except asyncio.TimeoutError:
            return None
        finally:
            # 清理：移除当前future，如果它仍然在字典中
            stored = self.follow_up_waiters.get(conversation_key)
            if follow_up_future and stored is follow_up_future:
                self.follow_up_waiters.pop(conversation_key, None)

    async def send_image_message(self, target_id: str, image_data: bytes, is_group: bool = False, group_id: Optional[str] = None):
        """发送图片消息"""
        if not self.websocket:
            return
        
        if not image_data:
            print("❌ 图片数据为空")
            return
        
        print(f"🖼️ 准备发送图片消息，数据大小: {len(image_data)} bytes")
        
        # 将图片转换为base64
        import base64
        base64_data = base64.b64encode(image_data).decode('utf-8')
        print(f"🖼️ 生成base64图片消息，长度: {len(base64_data)} chars")
        
        # 构建CQ码格式的图片消息
        image_message = f"[CQ:image,file=base64://{base64_data}]"
        
        # 发送消息
        if is_group and group_id:
            data = {
                "action": "send_group_msg",
                "params": {
                    "group_id": int(group_id),
                    "message": image_message
                }
            }
        else:
            data = {
                "action": "send_private_msg",
                "params": {
                    "user_id": int(target_id),
                    "message": image_message
                }
            }
        
        try:
            await self.websocket.send(json.dumps(data))
            print(f"✅ 图片消息发送成功 {'群组' if is_group else '私聊'} {target_id}")
        except Exception as e:
            print(f"❌ 图片消息发送失败: {str(e)}")
    
    async def _resolve_tts_audio(self, response: str, user_id: str) -> Optional[bytes]:
        """统一 TTS 合成入口：优先 AI 主动触发，否则走概率触发。

        Args:
            response: Bot 返回的原始回复文本
            user_id: 用户 ID

        Returns:
            音频数据，无语音时返回 None
        """
        forced = self.bot.get_last_tts_forced()
        if forced and forced.get("text"):
            try:
                audio = await self.bot.synthesize_speech_forced(forced["text"], user_id=user_id)
                if audio:
                    print(f"🎵 语音合成成功（AI主动触发），大小: {len(audio)} bytes")
                return audio
            except Exception as e:
                print(f"❌ TTS强制合成失败: {str(e)}")
                return None
        else:
            try:
                audio = await self.bot.synthesize_speech(response, user_id=user_id)
                if audio:
                    print(f"🎵 语音合成成功（概率触发），大小: {len(audio)} bytes")
                return audio
            except Exception as e:
                print(f"❌ TTS合成失败: {str(e)}")
                return None

    async def stop(self):
        """停止适配器"""
        self.running = False
        if self.websocket:
            await self.websocket.close()
        print("🔌 QQ适配器已停止")
