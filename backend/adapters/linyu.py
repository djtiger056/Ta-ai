import asyncio
import base64
import copy
import io
import json
import math
import random
import re
import time
import traceback
import wave
from datetime import datetime
from typing import Optional, Dict, Any, List

import aiohttp
import websockets
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from ..core.bot import Bot
from ..config import config
from ..api import proactive as proactive_api
from ..agent_delegate.parser import extract_delegate_tag
from ..core.gen_img_parser import extract_gen_img_prompt
from ..core.tts_tag_parser import extract_tts_tag
from ..utils.text_splitter import smart_split_text
from ..voice_call import VoiceCallManager, VoiceCallConfig
from .debouncer import MessageDebouncer


class LinyuAdapter:
    """Linyu IM 适配器，通过 WebSocket + HTTP API 直连"""

    _sentence_delimiters = {"。", "！", "？", "!", "?"}

    def __init__(self, bot: Bot, linyu_config: Optional[Dict[str, Any]] = None, *, owner_user_id: Optional[str] = None):
        self.bot = bot
        self.owner_user_id = str(owner_user_id) if owner_user_id is not None else None
        self.linyu_config = copy.deepcopy(linyu_config if linyu_config is not None else config.adapters_config.get("linyu", {}))

        # 连接配置
        self.http_host = self.linyu_config.get("http_host", "127.0.0.1")
        self.http_port = self.linyu_config.get("http_port", 9200)
        self.ws_host = self.linyu_config.get("ws_host", "127.0.0.1")
        self.ws_port = self.linyu_config.get("ws_port", 9100)

        # 账号配置
        self.account = self.linyu_config.get("account", "")
        self.password = self.linyu_config.get("password", "")
        self.target_user_id = str(self.linyu_config.get("target_user_id", "")).strip()
        self.target_user_account = str(self.linyu_config.get("target_user_account", "")).strip()
        self.auto_bind_first_user = bool(self.linyu_config.get("auto_bind_first_user", False))
        self._has_explicit_target = bool(self.target_user_id or self.target_user_account)

        # 访问控制配置
        self.access_control_config = self.linyu_config.get("access_control", {})
        self.access_control_enabled = self.access_control_config.get("enabled", False)
        self.access_control_mode = self.access_control_config.get("mode", "disabled")
        self.access_whitelist = set(str(uid) for uid in self.access_control_config.get("whitelist", []))
        self.access_blacklist = set(str(uid) for uid in self.access_control_config.get("blacklist", []))
        self.access_deny_message = self.access_control_config.get("deny_message", "抱歉，你没有权限使用此机器人。")

        # 分段发送配置
        self.segment_config = self.linyu_config.get("segment_config", {})
        self.segment_enabled = self.segment_config.get("enabled", True)
        self.max_segment_length = self.segment_config.get("max_segment_length", 100)
        self.min_segment_length = self.segment_config.get("min_segment_length", 5)
        self.delay_range = self.segment_config.get("delay_range", [0.5, 2.0])
        self.split_strategy = self.segment_config.get("strategy", "sentence")
        self.min_sentences_to_split = self.segment_config.get("min_sentences_to_split", 2)

        # 媒体下载配置（独立于分段配置；兼容旧字段）
        self.media_config = self.linyu_config.get("media_config", {})
        self.media_fetch_retry_count = int(
            self.media_config.get(
                "fetch_retry_count",
                self.segment_config.get("media_fetch_retry_count", 4)
            )
        )
        self.media_fetch_retry_delay = float(
            self.media_config.get(
                "fetch_retry_delay",
                self.segment_config.get("media_fetch_retry_delay", 0.8)
            )
        )
        self.media_debug_logs = bool(self.media_config.get("debug_logs", False))

        # 重连配置
        self.reconnect_config = self.linyu_config.get("reconnect_config", {})
        self.max_reconnect_attempts = self.reconnect_config.get("max_attempts", 10)
        self.reconnect_interval = self.reconnect_config.get("interval", 5.0)
        self.connect_timeout = self.reconnect_config.get("connect_timeout", 10.0)
        self.heartbeat_interval = self.reconnect_config.get("heartbeat_interval", 25.0)
        self.heartbeat_timeout = self.reconnect_config.get("heartbeat_timeout", 60.0)
        self.http_timeout = self.reconnect_config.get("http_timeout", 15.0)

        self.websocket = None
        self.running = False
        self.reconnect_attempts = 0
        self.token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.last_started_at: Optional[float] = None
        self.last_connected_at: Optional[float] = None
        self.last_error: Optional[str] = None

        # 消息防抖配置
        self.debounce_config = self.linyu_config.get('debounce', {})
        self.debounce_enabled = self.debounce_config.get('enabled', False)
        self.debounce_delay = self.debounce_config.get('delay', 3.0)
        self.debounce_max_wait = self.debounce_config.get('max_wait', 15.0)
        self.debounce_separator = self.debounce_config.get('separator', '\n')
        self.debouncer = MessageDebouncer(
            delay=self.debounce_delay,
            max_wait=self.debounce_max_wait,
            separator=self.debounce_separator,
        )

        self.follow_up_waiters: Dict[str, asyncio.Future] = {}
        self._emote_send_cache: Dict[str, Dict[str, float]] = {}
        # 消息去重缓存
        self._processed_messages: Dict[str, float] = {}
        self._message_dedup_ttl = 60.0

        self._http_base_url = self._build_http_base()
        self._ws_base_url = self._build_ws_base()

        # 实时通话管理器（用户拨打AI）
        self.voice_call_config = VoiceCallConfig.from_linyu_adapter_config(config.adapters_config)
        self.voice_call_manager = VoiceCallManager(self, self.voice_call_config)

    def _build_http_base(self) -> str:
        host = str(self.http_host).strip().rstrip("/")
        if host.startswith("http://") or host.startswith("https://"):
            base = host
        else:
            base = f"http://{host}"
        if not self._has_port(base):
            base = f"{base}:{self.http_port}"
        return base

    def _build_ws_base(self) -> str:
        host = str(self.ws_host).strip().rstrip("/")
        if host.startswith("ws://") or host.startswith("wss://"):
            base = host
        elif host.startswith("http://") or host.startswith("https://"):
            base = host.replace("http://", "ws://").replace("https://", "wss://")
        else:
            base = f"ws://{host}"
        if not self._has_port(base):
            base = f"{base}:{self.ws_port}"
        return base

    @staticmethod
    def _has_port(url: str) -> bool:
        if "://" in url:
            netloc = url.split("://", 1)[1]
        else:
            netloc = url
        return ":" in netloc

    async def start(self):
        """启动 Linyu 适配器，带自动重连功能"""
        if not self.account or not self.password:
            print("⚠️ Linyu 账号/密码未配置，适配器未启动")
            return

        self.running = True
        self.last_started_at = time.time()
        self.reconnect_attempts = 0

        while self.running:
            try:
                await self._ensure_http_session()
                await self._authenticate()
                await self._connect_websocket()
                await self._handle_messages()

                print("🔌 Linyu 连接断开，准备重连...")
                await self._close_websocket()
            except (websockets.exceptions.ConnectionClosed, ConnectionError, OSError, asyncio.TimeoutError) as e:
                self.reconnect_attempts += 1
                error_type = type(e).__name__
                self.last_error = f"{error_type}: {str(e)}"
                print(f"❌ Linyu 连接失败 ({error_type}): {str(e)}")
                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    print(f"⚠️ 已达到最大重连次数 ({self.max_reconnect_attempts})，停止重连")
                    self.running = False
                    break
                wait_time = self.reconnect_interval
                print(f"⏳ 等待 {wait_time:.1f} 秒后重连...")
                await asyncio.sleep(wait_time)
            except Exception as e:
                self.reconnect_attempts += 1
                self.last_error = f"{type(e).__name__}: {str(e)}"
                print(f"❌ Linyu 连接异常: {str(e)}")
                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    print(f"⚠️ 已达到最大重连次数 ({self.max_reconnect_attempts})，停止重连")
                    self.running = False
                    break
                wait_time = self.reconnect_interval
                print(f"⏳ 等待 {wait_time:.1f} 秒后重连...")
                await asyncio.sleep(wait_time)

    async def stop(self):
        """停止适配器"""
        self.running = False
        try:
            await self.voice_call_manager.shutdown()
        except Exception:
            pass
        await self._close_websocket()
        await self._close_http_session()
        print("🔌 Linyu 适配器已停止")

    async def _ensure_http_session(self):
        if self.http_session and not self.http_session.closed:
            return
        timeout = aiohttp.ClientTimeout(total=self.http_timeout)
        self.http_session = aiohttp.ClientSession(timeout=timeout)

    async def _close_http_session(self):
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
        self.http_session = None

    async def _close_websocket(self):
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
        self.websocket = None

    async def _authenticate(self):
        """HTTP 登录获取 Token"""
        public_key = await self._get_public_key()
        encrypted_password = self._encrypt_password(self.password, public_key)
        payload = {
            "account": self.account,
            "password": encrypted_password,
            "onlineEquipment": "bot"
        }
        result = await self._request_json("POST", "/v1/api/login", json_data=payload, with_token=False)
        data = result.get("data") if isinstance(result, dict) else None
        if not data or "token" not in data:
            raise RuntimeError(f"登录失败: {result}")
        self.token = data.get("token")
        self.user_id = str(data.get("userId")) if data.get("userId") else None
        print("✅ Linyu 登录成功")
        await self._resolve_target_user_id()

    async def _get_public_key(self) -> str:
        result = await self._request_json("GET", "/v1/api/login/public-key", with_token=False)
        if isinstance(result, dict) and "data" in result:
            return result["data"]
        if isinstance(result, str):
            return result
        raise RuntimeError(f"获取公钥失败: {result}")

    @staticmethod
    def _encrypt_password(password: str, public_key_pem: str) -> str:
        # 兼容 YAML 将纯数字解析为 int 的情况
        password_str = "" if password is None else str(password)
        public_key_str = "" if public_key_pem is None else str(public_key_pem)
        public_key = load_pem_public_key(public_key_str.encode("utf-8"))
        encrypted = public_key.encrypt(
            password_str.encode("utf-8"),
            padding.PKCS1v15()
        )
        return base64.b64encode(encrypted).decode("utf-8")

    async def _connect_websocket(self):
        if not self.token:
            await self._authenticate()
        ws_url = f"{self._ws_base_url}/ws?x-token={self.token}"
        print(f"🔗 正在连接 Linyu WebSocket: {self._mask_ws_url(ws_url)}")
        try:
            async with asyncio.timeout(self.connect_timeout):
                self.websocket = await websockets.connect(
                    ws_url,
                    ping_interval=self.heartbeat_interval,
                    ping_timeout=self.heartbeat_timeout
                )
        except asyncio.TimeoutError:
            raise ConnectionError(f"连接超时 ({self.connect_timeout}秒)")
        print("✅ Linyu WebSocket 连接成功")
        self.last_connected_at = time.time()
        self.last_error = None
        self.reconnect_attempts = 0

    async def _handle_messages(self):
        """处理接收到的消息"""
        print("🎯 开始监听 Linyu 消息...")
        while self.running and self.websocket:
            try:
                # 直接接收消息，依赖 WebSocket 库的 ping/pong 机制检测连接状态
                message = await self.websocket.recv()

                data = self._safe_json_loads(message)
                if not data:
                    continue

                await self._process_ws_message(data)

            except websockets.exceptions.ConnectionClosed as e:
                print(f"🔌 Linyu 连接已断开: {e.code if e.code else '未知'} - {e.reason if e.reason else '未知原因'}")
                break
            except (OSError, ConnectionError, websockets.exceptions.WebSocketException) as e:
                print(f"🔌 网络连接错误: {type(e).__name__}: {str(e)}")
                break
            except Exception as e:
                print(f"❌ 消息处理错误: {type(e).__name__}: {str(e)}")
                continue
        print("🔄 消息处理循环结束，准备重连...")

    async def _process_ws_message(self, data: Dict[str, Any]):
        msg_type = data.get("type")
        if msg_type == "video":
            content = data.get("content")
            if isinstance(content, dict):
                try:
                    await self.voice_call_manager.handle_video_signal(content)
                except Exception as e:
                    print(f"❌ 处理 video 信令失败: {type(e).__name__}: {str(e)}")
            return

        if msg_type != "msg":
            return
        content = data.get("content")
        if not isinstance(content, dict):
            return

        source = content.get("source")
        if source == "group":
            await self._handle_group_message(content)
        else:
            await self._handle_private_message(content)

    async def _handle_private_message(self, message: Dict[str, Any]):
        user_id = str(message.get("fromId") or message.get("from_id") or "")
        if not user_id:
            return

        # 忽略自己发送的消息
        if self.user_id and user_id == str(self.user_id):
            return

        # 尝试将 Linyu userId 与已绑定账号名的用户关联
        await self._try_resolve_linyu_binding(user_id)
        bound_user = await self._get_bound_linyu_user(user_id)
        self._grant_bound_user_whitelist_access(user_id, bound_user)

        # 获取消息ID用于去重
        msg_id = str(message.get("id") or message.get("msgId") or message.get("msg_id") or "")
        if msg_id and self._is_message_processed(msg_id):
            print(f"⚠️ 跳过重复消息: {msg_id}")
            return

        # 单用户模式目标限制
        if not self.target_user_id and self.auto_bind_first_user:
            has_explicit_binding = await self._has_any_explicit_linyu_binding()
            if not has_explicit_binding:
                self.target_user_id = user_id
                if self.access_control_enabled and self.access_control_mode == "whitelist":
                    self.access_whitelist.add(user_id)
                print(f"✅ 自动绑定首个用户为目标: {user_id}")

        allow_bound_user_override = self._should_allow_bound_user_target_override(bound_user)
        if self.target_user_id and user_id != self.target_user_id and not allow_bound_user_override:
            print(f"ℹ️ 忽略非目标用户消息: {user_id} (target={self.target_user_id})")
            return

        # 访问控制
        has_access, deny_message = self._check_user_access(user_id)
        if not has_access:
            print(f"🚫 私聊消息被拒绝 {user_id}: {deny_message}")
            await self.send_private_message(user_id, deny_message)
            return

        msg_content = message.get("msgContent") or message.get("msg_content") or {}
        if isinstance(msg_content, str):
            parsed = self._safe_json_loads(msg_content)
            if isinstance(parsed, dict):
                msg_content = parsed
        content_type = str(msg_content.get("type") or "")
        content_raw = msg_content.get("content")
        msg_id = str(message.get("id") or message.get("msgId") or message.get("msg_id") or "")

        if content_type == "text":
            text_content = str(content_raw or "").strip()
            if not text_content:
                return

            conversation_key = self._get_conversation_key(user_id, is_group=False)
            if self._deliver_follow_up_message(conversation_key, text_content):
                return

            print(f"📨 Linyu 私聊消息 {user_id}: {text_content}")
            await self._handle_text_message(user_id, text_content)
            asyncio.create_task(self._mark_read(user_id))
        elif content_type == "img":
            print(f"🖼️ Linyu 收到图片消息 {user_id}")
            await self._handle_image_message(user_id, msg_id, msg_content)
            asyncio.create_task(self._mark_read(user_id))
        elif content_type == "voice":
            print(f"🎤 Linyu 收到语音消息 {user_id}")
            await self._handle_voice_message(user_id, msg_id, msg_content)
            asyncio.create_task(self._mark_read(user_id))
        elif content_type in {"call", "video"}:
            signal_payload = self._build_call_signal_payload(
                message=message,
                msg_content=msg_content,
            )
            if signal_payload:
                print(
                    f"📞 Linyu 收到通话信令: type={signal_payload.get('type')} "
                    f"callId={signal_payload.get('callId', '')}"
                )
                await self.voice_call_manager.handle_video_signal(signal_payload)
                asyncio.create_task(self._mark_read(user_id))
            else:
                raw_preview = str(content_raw)[:200] if content_raw is not None else ""
                print(f"ℹ️ Linyu 未能解析 call 消息负载: {raw_preview}")
        else:
            if content_type:
                print(f"ℹ️ Linyu 未处理的消息类型: {content_type}")

    def _build_call_signal_payload(self, message: Dict[str, Any], msg_content: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        payload: Dict[str, Any] = {}
        content_raw = msg_content.get("content")
        nested = self._safe_json_loads(content_raw)
        if isinstance(nested, dict):
            payload.update(nested)

        for key, value in msg_content.items():
            if key == "content":
                continue
            if key not in payload:
                payload[key] = value

        signal_type = (
            payload.get("type")
            or payload.get("callType")
            or payload.get("signalType")
            or payload.get("event")
            or payload.get("action")
        )

        if isinstance(signal_type, str) and signal_type.lower() in {"call", "video"}:
            nested2 = self._safe_json_loads(payload.get("content"))
            if isinstance(nested2, dict):
                for key, value in nested2.items():
                    if key not in payload:
                        payload[key] = value
                signal_type = (
                    nested2.get("type")
                    or nested2.get("callType")
                    or nested2.get("signalType")
                    or nested2.get("event")
                    or nested2.get("action")
                    or signal_type
                )

        if not signal_type:
            return None

        payload["type"] = str(signal_type).strip().lower().replace("-", "_")
        if not payload["type"]:
            return None

        from_id = str(message.get("fromId") or message.get("from_id") or "")
        if from_id and not payload.get("fromId"):
            payload["fromId"] = from_id

        if self.user_id and not payload.get("toId"):
            payload["toId"] = str(self.user_id)

        if not payload.get("callId"):
            for key in ("call_id", "roomId", "room_id", "sessionId", "session_id"):
                value = payload.get(key)
                if value:
                    payload["callId"] = value
                    break

        if not payload.get("callId"):
            fallback_id = str(message.get("id") or message.get("msgId") or message.get("msg_id") or "")
            if fallback_id:
                payload["callId"] = fallback_id

        return payload

    async def _handle_group_message(self, message: Dict[str, Any]):
        # 目前单用户模式默认忽略群消息
        return

    async def _handle_text_message(self, user_id: str, text_content: str):
        image_task = None
        bot_user_id = self._get_bot_user_id(user_id)

        image_prompt = self.bot.should_generate_image(text_content, user_id=bot_user_id)
        if image_prompt:
            print(f"🎨 检测到图像生成请求: {image_prompt}")
            image_task = asyncio.create_task(
                self._handle_image_generation(user_id, image_prompt)
            )
            return

        if self.debounce_enabled:
            # 使用防抖器：等待用户发完所有消息后再统一回复
            debounce_key = f"linyu_{user_id}"
            await self.debouncer.add_message(
                debounce_key,
                text_content,
                callback=lambda merged_text: self._do_text_reply(user_id, merged_text),
            )
        else:
            await self._do_text_reply(user_id, text_content)

    async def _do_text_reply(self, user_id: str, text_content: str):
        """执行文本回复（可能由防抖器合并后调用）"""
        try:
            bot_user_id = self._get_bot_user_id(user_id)
            session_id = self._get_bot_session_id(user_id)
            proactive_api.record_user_activity("linyu_private", user_id, user_id, text_content)
            voice_only = self.bot.is_voice_only_mode(bot_user_id)
            response = await self._stream_reply_by_sentence(
                user_id=user_id,
                prompt=text_content,
                bot_user_id=bot_user_id,
                session_id=session_id,
                emit_text=not voice_only,
            )
            proactive_api.record_assistant_activity("linyu_private", user_id, user_id, response)
            log_response = response[:200] + "..." if len(response) > 200 else response
            print(f"🤖 Linyu AI回复 -> {user_id}: {log_response}")
            last_image = self.bot.get_last_generated_image()

            await self._deliver_tts_and_text_response(
                user_id=user_id,
                response=response,
                voice_only=voice_only,
                bot_user_id=bot_user_id,
            )

            if last_image and last_image.get("image_data"):
                asyncio.create_task(self._send_image_with_delay(user_id, last_image["image_data"]))

            try:
                await self._maybe_send_emote(text_content, response, user_id)
            except Exception as e:
                print(f"[Emote] emote send failed: {str(e)}")

        except Exception as e:
            print(f"❌ 私聊回复失败: {type(e).__name__}: {str(e)}")
            traceback.print_exc()
            await self.send_private_message(user_id, "抱歉，回复失败了...")

    async def _handle_image_message(self, user_id: str, msg_id: str, msg_content: Dict[str, Any]):
        image_segments = [{"type": "image"}]
        if not self.bot.should_recognize_image(image_segments):
            return

        await self._handle_vision_recognition(user_id, msg_id, msg_content)

    async def _handle_voice_message(self, user_id: str, msg_id: str, msg_content: Dict[str, Any]):
        await self._handle_asr_recognition(user_id, msg_id, msg_content)

    async def _handle_image_generation(self, user_id: str, prompt: str):
        try:
            bot_user_id = self._get_bot_user_id(user_id)
            session_id = self._get_bot_session_id(user_id)
            image_data = await self.bot.generate_image(prompt, user_id=bot_user_id, session_id=session_id)
            if image_data:
                await self.send_image_message(user_id, image_data)
            else:
                image_gen_config = self.bot.get_image_gen_config()
                error_msg = image_gen_config.get("error_message", "😢 图片生成失败：{error}").format(error="未知错误")
                await self.send_private_message(user_id, error_msg)
        except Exception as e:
            print(f"❌ 图像生成处理失败: {str(e)}")
            image_gen_config = self.bot.get_image_gen_config()
            error_msg = image_gen_config.get("error_message", "😢 图片生成失败：{error}").format(error=str(e))
            await self.send_private_message(user_id, error_msg)

    async def _handle_vision_recognition(self, user_id: str, msg_id: str, msg_content: Dict[str, Any]):
        try:
            vision_config = self.bot.get_vision_config()
            if not vision_config.get("enabled", False):
                return

            # 等待补充消息
            conversation_key = self._get_conversation_key(user_id, is_group=False)
            existing_future = self.follow_up_waiters.get(conversation_key)
            if existing_future and not existing_future.done():
                existing_future.cancel()
            loop = asyncio.get_running_loop()
            follow_up_future = loop.create_future()
            self.follow_up_waiters[conversation_key] = follow_up_future

            # 获取图片数据（消息入库与文件上传可能存在时序差，增加重试）
            image_data = await self._resolve_incoming_media_bytes_with_retry(msg_id, msg_content, expect="image")
            image_url = None
            if not image_data:
                image_url = await self._resolve_incoming_media_url(msg_id, msg_content, expect="image")

            if not image_data and not image_url:
                await self.send_private_message(user_id, "😢 图片识别失败：无法获取图片")
                return

            if image_data:
                recognition_text = await self.bot.recognize_image(image_data=image_data, prompt="描述这幅图")
            else:
                recognition_text = await self.bot.recognize_image(image_url=image_url, prompt="描述这幅图")
            if not recognition_text:
                await self.send_private_message(user_id, "😢 图片识别失败：无法识别")
                return

            follow_up_timeout = vision_config.get("follow_up_timeout", 5.0)
            follow_up_message = await self._wait_for_follow_up_message(conversation_key, timeout=follow_up_timeout)

            instruction_text = vision_config.get("instruction_text", "这是一张图片的描述，请根据描述生成一段合适的话语：")
            user_message_parts = []
            if follow_up_message:
                user_message_parts.append(follow_up_message)
            user_message_parts.append(f"{instruction_text}\n\n{recognition_text}")
            user_message = "\n\n".join(user_message_parts)

            bot_user_id = self._get_bot_user_id(user_id)
            session_id = self._get_bot_session_id(user_id)
            proactive_api.record_user_activity("linyu_private", user_id, user_id, user_message)
            voice_only = self.bot.is_voice_only_mode(bot_user_id)
            llm_response = await self._stream_reply_by_sentence(
                user_id=user_id,
                prompt=user_message,
                bot_user_id=bot_user_id,
                session_id=session_id,
                emit_text=not voice_only,
            )
            proactive_api.record_assistant_activity("linyu_private", user_id, user_id, llm_response)

            await self._deliver_tts_and_text_response(
                user_id=user_id,
                response=llm_response,
                voice_only=voice_only,
                bot_user_id=bot_user_id,
            )

        except Exception as e:
            print(f"❌ 视觉识别处理失败: {str(e)}")
            vision_config = self.bot.get_vision_config()
            error_msg = vision_config.get("error_message", "😢 图片识别失败：{error}").format(error=str(e))
            await self.send_private_message(user_id, error_msg)

    async def _handle_asr_recognition(self, user_id: str, msg_id: str, msg_content: Dict[str, Any]):
        try:
            asr_config = config.asr_config if hasattr(config, "asr_config") else None
            if not asr_config or not asr_config.enabled:
                return

            processing_msg = asr_config.processing_message
            if processing_msg:
                await self.send_private_message(user_id, processing_msg)

            audio_data = await self._resolve_incoming_media_bytes_with_retry(msg_id, msg_content, expect="audio")
            if not audio_data:
                await self.send_private_message(user_id, asr_config.error_message)
                return

            filename = "voice.mp3"
            content_raw = msg_content.get("content")
            content_json = self._safe_json_loads(content_raw)
            if isinstance(content_json, dict):
                name = content_json.get("name")
                if isinstance(name, str) and "." in name:
                    filename = name
                cached_text = content_json.get("text")
                if isinstance(cached_text, str) and cached_text.strip():
                    transcription_text = cached_text.strip()
                else:
                    transcription_text = ""
            else:
                transcription_text = ""

            if not transcription_text:
                transcription_text = await self.bot.transcribe_voice(audio_data, filename=filename)
            if not transcription_text:
                await self.send_private_message(user_id, asr_config.error_message)
                return

            bot_user_id = self._get_bot_user_id(user_id)
            session_id = self._get_bot_session_id(user_id)
            proactive_api.record_user_activity("linyu_private", user_id, user_id, transcription_text)
            voice_only = self.bot.is_voice_only_mode(bot_user_id)
            llm_response = await self._stream_reply_by_sentence(
                user_id=user_id,
                prompt=transcription_text,
                bot_user_id=bot_user_id,
                session_id=session_id,
                emit_text=not voice_only,
            )
            proactive_api.record_assistant_activity("linyu_private", user_id, user_id, llm_response)

            await self._deliver_tts_and_text_response(
                user_id=user_id,
                response=llm_response,
                voice_only=voice_only,
                bot_user_id=bot_user_id,
            )

        except Exception as e:
            print(f"❌ 语音识别处理失败: {str(e)}")
            asr_config = config.asr_config if hasattr(config, "asr_config") else None
            error_msg = asr_config.error_message if asr_config else "语音识别失败了呢"
            await self.send_private_message(user_id, error_msg)

    async def send_private_message(self, user_id: str, message: str):
        await self._send_text_segments(user_id, message, is_group=False)

    async def send_group_message(self, group_id: str, message: str):
        await self._send_text_segments(group_id, message, is_group=True, group_id=group_id)

    def _split_ready_sentences(self, buffer: str) -> tuple[list[str], str]:
        """从流式缓冲区中提取完整句子，保留未完成尾部。"""
        if not buffer:
            return [], ""

        ready: list[str] = []
        start = 0
        index = 0
        length = len(buffer)

        while index < length:
            char = buffer[index]
            if char in self._sentence_delimiters:
                end = index + 1
                while end < length and buffer[end] in self._sentence_delimiters:
                    end += 1

                sentence = buffer[start:end].strip()
                if sentence:
                    ready.append(sentence)
                start = end
                index = end
                continue
            index += 1

        remaining = buffer[start:]
        return ready, remaining

    def _split_incomplete_gen_img_prefix(self, text: str) -> tuple[str, str]:
        """将可能是 [GEN_IMG: 前缀的尾巴拆分出来，等待后续 chunk 补全。"""
        if not text:
            return "", ""

        token = "[gen_img:"
        last_bracket = text.rfind("[")
        if last_bracket < 0:
            return text, ""

        suffix = text[last_bracket:].lower()
        if token.startswith(suffix):
            return text[:last_bracket], text[last_bracket:]
        return text, ""

    def _split_incomplete_tag_prefix(self, text: str, tokens: list[str]) -> tuple[str, str]:
        """将可能是任意过滤标签前缀的尾巴拆分出来，等待后续 chunk 补全。"""
        if not text:
            return "", ""

        last_bracket = text.rfind("[")
        if last_bracket < 0:
            return text, ""

        suffix = text[last_bracket:].lower()
        for token in tokens:
            if token.startswith(suffix):
                return text[:last_bracket], text[last_bracket:]
        return text, ""

    def _extract_safe_stream_text(self, pending: str) -> tuple[str, str]:
        """从待处理文本中剥离完整/半截 [GEN_IMG: ...] 和 [DELEGATE: ...] 标签，返回(可显示文本, 余留缓冲)。"""
        if not pending:
            return "", ""

        lower = pending.lower()
        # 需要过滤的标签前缀列表
        filter_tokens = ["[gen_img:", "[delegate:", "[tts]", "[/tts]"]
        cursor = 0
        visible_parts: list[str] = []

        while True:
            # 找到最近的一个标签起始位置
            earliest_start = -1
            for token in filter_tokens:
                start = lower.find(token, cursor)
                if start >= 0 and (earliest_start < 0 or start < earliest_start):
                    earliest_start = start

            if earliest_start < 0:
                tail = pending[cursor:]
                visible_tail, remainder = self._split_incomplete_tag_prefix(tail, filter_tokens)
                visible_parts.append(visible_tail)
                return "".join(visible_parts), remainder

            visible_parts.append(pending[cursor:earliest_start])
            end = pending.find("]", earliest_start)
            if end < 0:
                return "".join(visible_parts), pending[earliest_start:]

            cursor = end + 1

    async def _stream_reply_by_sentence(
        self,
        user_id: str,
        prompt: str,
        bot_user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        emit_text: bool = True,
    ) -> str:
        """按句流式发送回复，句末标点含 。！？!?。"""
        # 注册 session -> channel 映射，确保委派结果能推送回来
        effective_bot_user_id = bot_user_id or self._get_bot_user_id(user_id)
        effective_session = session_id or self._get_bot_session_id(user_id)
        self.bot.register_session_channel(effective_session, "linyu_private")

        if not emit_text:
            final_response = ""
            async for chunk in self.bot.chat_stream(prompt, user_id=effective_bot_user_id, session_id=effective_session):
                if chunk:
                    final_response += chunk

            cleaned_response, _ = extract_tts_tag(final_response)
            cleaned_response, _ = extract_gen_img_prompt(cleaned_response)
            cleaned_response, _ = extract_delegate_tag(cleaned_response)
            return cleaned_response

        final_response = ""
        sentence_buffer = ""
        stream_pending = ""
        sentence_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        sender_error: Optional[Exception] = None
        producer_error: Optional[Exception] = None
        sent_sentence_count = 0

        async def sentence_sender():
            nonlocal sender_error, sent_sentence_count
            is_first_sentence = True
            while True:
                sentence = await sentence_queue.get()
                if sentence is None:
                    break

                if not is_first_sentence and self.segment_enabled:
                    delay = random.uniform(self.delay_range[0], self.delay_range[1])
                    print(f"⏳ 流式句发送等待 {delay:.2f} 秒: {sentence[:40]}")
                    await asyncio.sleep(delay)

                try:
                    await self._send_text_once(user_id, sentence, is_group=False)
                    sent_sentence_count += 1
                except Exception as e:
                    sender_error = e
                    print(f"❌ 流式句发送失败: {type(e).__name__}: {str(e)}")
                    break
                is_first_sentence = False

        sender_task = asyncio.create_task(sentence_sender())
        try:
            try:
                async for chunk in self.bot.chat_stream(
                    prompt,
                    user_id=effective_bot_user_id,
                    session_id=effective_session,
                ):
                    if sender_error:
                        break
                    if not chunk:
                        continue

                    final_response += chunk
                    stream_pending += chunk

                    safe_text, stream_pending = self._extract_safe_stream_text(stream_pending)
                    if not safe_text:
                        continue

                    sentence_buffer += safe_text

                    ready_sentences, sentence_buffer = self._split_ready_sentences(sentence_buffer)
                    for sentence in ready_sentences:
                        if sender_error:
                            break
                        await sentence_queue.put(sentence)
            except Exception as e:
                producer_error = e

            if stream_pending and not sender_error:
                safe_tail, _ = self._extract_safe_stream_text(stream_pending)
                sentence_buffer += safe_tail

            tail = sentence_buffer.strip()
            if tail and not sender_error:
                await sentence_queue.put(tail)
        finally:
            await sentence_queue.put(None)
            await sender_task

        cleaned_response, _ = extract_tts_tag(final_response)
        cleaned_response, _ = extract_gen_img_prompt(cleaned_response)
        cleaned_response, _ = extract_delegate_tag(cleaned_response)

        if sender_error:
            if sent_sentence_count <= 0:
                raise sender_error
            print("⚠️ 流式文本已部分发出，后续分句发送失败，跳过失败兜底提示")

        if producer_error:
            if sent_sentence_count <= 0:
                raise producer_error
            print("⚠️ 流式生成中断，但已向用户发送部分内容，跳过失败兜底提示")

        return cleaned_response

    async def _deliver_tts_and_text_response(
        self,
        user_id: str,
        response: str,
        voice_only: bool,
        bot_user_id: Optional[str] = None,
    ) -> None:
        """根据语音回复配置，统一处理文本/语音发送与失败回退。"""
        effective_bot_user_id = bot_user_id or self._get_bot_user_id(user_id)
        audio_data = await self._resolve_tts_audio(response, effective_bot_user_id)
        text_to_send = response

        if audio_data:
            if voice_only:
                text_to_send = self.bot.strip_tts_text(response, user_id=effective_bot_user_id)
            try:
                tts_text = self.bot.get_last_tts_text(user_id=effective_bot_user_id)
                await self.send_voice_message(user_id, audio_data, speech_text=tts_text)
            except Exception as e:
                print(f"❌ 语音发送失败: {type(e).__name__}: {str(e)}")
                audio_data = None
                text_to_send = response

        if voice_only and text_to_send:
            await self.send_private_message(user_id, text_to_send)

    def _get_bot_user_id(self, linyu_user_id: str) -> str:
        """返回该 Linyu 会话应使用的系统内用户 ID。"""
        owner_user_id = str(getattr(self, "owner_user_id", "") or "").strip()
        return owner_user_id or str(linyu_user_id)

    def _get_bot_session_id(self, linyu_user_id: str) -> str:
        """为该 Linyu 对话生成稳定的 Bot 会话 ID。"""
        return f"linyu_private:{str(linyu_user_id)}"

    async def _resolve_tts_audio(self, response: str, user_id: str) -> Optional[bytes]:
        """统一 TTS 合成入口：优先 AI 主动触发，否则走概率触发。"""
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

        try:
            audio = await self.bot.synthesize_speech(response, user_id=user_id)
            if audio:
                print(f"🎵 语音合成成功（概率触发），大小: {len(audio)} bytes")
            return audio
        except Exception as e:
            print(f"❌ TTS合成失败: {str(e)}")
            return None

    def _count_sentences(self, text: str) -> int:
        """统计文本中的句子数量"""
        if not text or not text.strip():
            return 0
        sentences = re.split(r'[。！？.!?]+', text.strip())
        sentences = [s for s in sentences if s.strip()]
        return len(sentences)

    def _is_message_processed(self, msg_id: str) -> bool:
        """检查消息是否已处理过（防止重复处理）"""
        if not msg_id:
            return False
        now = time.time()
        expired_keys = [
            k for k, v in self._processed_messages.items()
            if now - v > self._message_dedup_ttl
        ]
        for k in expired_keys:
            del self._processed_messages[k]
        if msg_id in self._processed_messages:
            return True
        self._processed_messages[msg_id] = now
        return False

    async def _send_text_segments(self, target_id: str, message: str, is_group: bool = False, group_id: Optional[str] = None):
        if not message:
            return
        if not self.segment_enabled:
            await self._send_text_once(target_id, message, is_group=is_group, group_id=group_id)
            return

        sentence_count = self._count_sentences(message)
        should_segment = (
            len(message) > self.max_segment_length or
            sentence_count >= self.min_sentences_to_split
        )

        if not should_segment:
            await self._send_text_once(target_id, message, is_group=is_group, group_id=group_id)
            return

        try:
            segments = smart_split_text(
                text=message,
                max_length=self.max_segment_length,
                min_length=self.min_segment_length,
                strategy=self.split_strategy
            )
        except Exception:
            segments = [message]

        if len(segments) == 1 and segments[0] == message:
            await self._send_text_once(target_id, message, is_group=is_group, group_id=group_id)
            return

        if not segments:
            return

        print(f"📝 消息分割为 {len(segments)} 段，将分段发送")

        for i, segment in enumerate(segments, 1):
            await self._send_text_once(target_id, segment, is_group=is_group, group_id=group_id)
            if i < len(segments):
                delay = random.uniform(self.delay_range[0], self.delay_range[1])
                print(f"⏳ 段 {i}/{len(segments)} 发送完成，等待 {delay:.2f} 秒...")
                await asyncio.sleep(delay)

        print(f"✅ 分段发送完成，共发送 {len(segments)} 段")

    async def _send_text_once(self, target_id: str, message: str, is_group: bool = False, group_id: Optional[str] = None):
        payload = {
            "toUserId": str(group_id if is_group else target_id),
            "source": "group" if is_group else "user",
            "msgContent": {
                "type": "text",
                "content": message
            }
        }
        log_msg = message[:100] + "..." if len(message) > 100 else message
        print(f"📤 Linyu 发送消息 -> {target_id}: {log_msg}")
        await self._request_json("POST", "/v1/api/message/send", json_data=payload)

    async def send_image_message(self, user_id: str, image_data: bytes):
        if not image_data:
            return
        print(f"🖼️ 准备发送图片，大小: {len(image_data)} bytes -> 用户 {user_id}")
        msg_id = await self._create_media_message(user_id, image_data, content_type="img", filename="image.png")
        if msg_id:
            await self._upload_media("/v1/api/message/send/Img", msg_id, image_data)
        else:
            print("❌ 创建图片消息失败：未获取到 msgId")

    async def send_voice_message(self, user_id: str, audio_data: bytes, speech_text: Optional[str] = None):
        if not audio_data:
            return
        ext = self._detect_audio_extension(audio_data)
        filename = f"voice.{ext}"
        duration_seconds = self._estimate_audio_duration_seconds(audio_data, speech_text=speech_text)
        print(
            f"🎵 准备发送语音，大小: {len(audio_data)} bytes，格式: {ext}，"
            f"时长: {duration_seconds}s -> 用户 {user_id}"
        )
        msg_id = await self._create_media_message(
            user_id,
            audio_data,
            content_type="voice",
            filename=filename,
            extra_meta={"time": duration_seconds}
        )
        if msg_id:
            await self._upload_media("/v1/api/message/send/file", msg_id, audio_data)
        else:
            print("❌ 创建语音消息失败：未获取到 msgId")

    async def _create_media_message(
        self,
        user_id: str,
        data: bytes,
        content_type: str,
        filename: str,
        extra_meta: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        meta = {
            "name": filename,
            "size": len(data)
        }
        if extra_meta:
            meta.update(extra_meta)
        payload = {
            "toUserId": str(user_id),
            "source": "user",
            "msgContent": {
                "type": content_type,
                "content": json.dumps(meta, ensure_ascii=False)
            }
        }
        result = await self._request_json("POST", "/v1/api/message/send", json_data=payload)
        if not isinstance(result, dict):
            return None
        data_obj = result.get("data")
        if isinstance(data_obj, dict):
            return str(data_obj.get("id") or "")
        return None

    @staticmethod
    def _detect_audio_extension(data: bytes) -> str:
        if not data:
            return "mp3"
        if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WAVE":
            return "wav"
        if data.startswith(b"OggS"):
            return "ogg"
        if data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
            return "mp3"
        if len(data) >= 12 and data[4:8] == b"ftyp":
            return "m4a"
        return "mp3"

    def _estimate_audio_duration_seconds(self, audio_data: bytes, speech_text: Optional[str] = None) -> int:
        wav_duration = self._parse_wav_duration_seconds(audio_data)
        if wav_duration is not None:
            return wav_duration

        mp3_duration = self._parse_mp3_duration_seconds(audio_data)
        if mp3_duration is not None:
            return mp3_duration

        bytes_duration = self._estimate_duration_from_bytes(audio_data)
        if bytes_duration is not None:
            return bytes_duration

        text_duration = self._estimate_duration_from_text(speech_text)
        if text_duration is not None:
            return text_duration

        return 1

    @staticmethod
    def _parse_wav_duration_seconds(audio_data: bytes) -> Optional[int]:
        if not audio_data or len(audio_data) < 44:
            return None
        if not (audio_data.startswith(b"RIFF") and audio_data[8:12] == b"WAVE"):
            return None
        try:
            with wave.open(io.BytesIO(audio_data), "rb") as wav_file:
                frame_rate = wav_file.getframerate()
                frame_count = wav_file.getnframes()
            if frame_rate <= 0:
                return None
            seconds = int(round(frame_count / frame_rate))
            return max(1, min(600, seconds))
        except Exception:
            return None

    @staticmethod
    def _estimate_duration_from_text(speech_text: Optional[str]) -> Optional[int]:
        if not speech_text:
            return None
        stripped = re.sub(r"\s+", "", speech_text)
        if not stripped:
            return None
        cps = 4.8
        seconds = int(math.ceil(len(stripped) / cps))
        return max(1, min(600, seconds))

    def _estimate_duration_from_bytes(self, audio_data: bytes) -> Optional[int]:
        if not audio_data:
            return None
        ext = self._detect_audio_extension(audio_data)
        assumed_bitrate_kbps = 32 if ext == "mp3" else 48
        estimated = int(round((len(audio_data) * 8) / (assumed_bitrate_kbps * 1000)))
        return max(1, min(600, estimated))

    @staticmethod
    def _parse_mp3_duration_seconds(audio_data: bytes) -> Optional[int]:
        if not audio_data or len(audio_data) < 4:
            return None

        offset = 0
        length = len(audio_data)

        if length >= 10 and audio_data[:3] == b"ID3":
            tag_size = (
                ((audio_data[6] & 0x7F) << 21)
                | ((audio_data[7] & 0x7F) << 14)
                | ((audio_data[8] & 0x7F) << 7)
                | (audio_data[9] & 0x7F)
            )
            offset = 10 + tag_size
            if offset >= length - 4:
                return None

        bitrate_table = {
            0b0001: 32,
            0b0010: 40,
            0b0011: 48,
            0b0100: 56,
            0b0101: 64,
            0b0110: 80,
            0b0111: 96,
            0b1000: 112,
            0b1001: 128,
            0b1010: 160,
            0b1011: 192,
            0b1100: 224,
            0b1101: 256,
            0b1110: 320,
        }

        scan_limit = min(length - 4, offset + 4096)
        for idx in range(offset, max(offset, scan_limit)):
            b1 = audio_data[idx]
            b2 = audio_data[idx + 1]
            if b1 != 0xFF or (b2 & 0xE0) != 0xE0:
                continue

            bitrate_index = (audio_data[idx + 2] >> 4) & 0x0F
            bitrate_kbps = bitrate_table.get(bitrate_index)
            if not bitrate_kbps:
                continue

            seconds = int(round((length * 8) / (bitrate_kbps * 1000)))
            return max(1, min(600, seconds))

        return None

    async def _upload_media(self, path: str, msg_id: str, data: bytes):
        if not msg_id:
            return
        headers = self._auth_headers()
        headers["msgId"] = msg_id
        status, text = await self._request_raw("POST", path, data=data, headers=headers)
        if status != 200:
            print(f"❌ 媒体上传失败: status={status}, resp={text}")
        else:
            print(f"✅ 媒体上传成功: msgId={msg_id}")

    async def _download_media_bytes(self, msg_id: str) -> Optional[bytes]:
        if not msg_id:
            return None
        if not self.http_session:
            await self._ensure_http_session()
        headers = self._auth_headers()
        for path in ("/v1/api/message/get/media", "/v1/api/message/get/file"):
            request_variants = [
                {
                    "url": f"{self._http_base_url}{path}",
                    "headers": {**headers, "msgId": msg_id}
                },
                {
                    "url": f"{self._http_base_url}{path}?msgId={msg_id}",
                    "headers": headers
                },
                {
                    "url": f"{self._http_base_url}{path}/{msg_id}",
                    "headers": headers
                },
            ]

            for variant in request_variants:
                try:
                    async with self.http_session.get(variant["url"], headers=variant["headers"]) as resp:
                        if resp.status != 200:
                            text = await resp.text()
                            preview = str(text or "")[:120].replace("\n", " ")
                            self._media_debug_log(
                                f"⚠️ 下载媒体响应非200: msg_id={msg_id}, status={resp.status}, "
                                f"url={variant['url']}, body={preview}"
                            )
                            continue
                        content_type = str(resp.headers.get("Content-Type") or "").lower()
                        raw_data = await resp.read()
                        media_data = await self._extract_media_bytes_from_raw(raw_data, content_type, headers)
                        if media_data:
                            return media_data
                        preview = ""
                        if "application/json" in content_type:
                            preview = raw_data.decode("utf-8", errors="ignore")[:220].replace("\n", " ")
                        self._media_debug_log(
                            f"⚠️ 下载媒体返回不可用: msg_id={msg_id}, url={variant['url']}, "
                            f"content_type={content_type}, bytes={len(raw_data)}, preview={preview}"
                        )
                except Exception as e:
                    self._media_debug_log(
                        f"⚠️ 下载媒体失败: url={variant['url']}, err={type(e).__name__}: {str(e)}"
                    )
                    continue
        return None

    async def _resolve_incoming_media_bytes(self, msg_id: str, msg_content: Dict[str, Any], expect: str = "any") -> Optional[bytes]:
        if not self.http_session:
            await self._ensure_http_session()

        headers = self._auth_headers()
        content_raw = msg_content.get("content")
        content_payload = self._safe_json_loads(content_raw)
        content_candidate = None
        if isinstance(content_raw, str):
            content_candidate = content_raw

        candidate = self._extract_media_payload_candidate(content_payload)
        if not candidate and content_candidate:
            candidate = content_candidate
        if candidate:
            media_data = await self._resolve_media_candidate_to_bytes(candidate, headers)
            if media_data and self._media_match_expect(media_data, expect):
                return media_data

        msg_ids = self._collect_media_message_ids(msg_id, content_payload)
        for candidate_msg_id in msg_ids:
            media_data = await self._download_media_bytes(candidate_msg_id)
            if media_data and self._media_match_expect(media_data, expect):
                return media_data

        file_target_id, file_name = self._extract_user_file_reference(content_payload)
        if file_name:
            self._media_debug_log(f"ℹ️ 解析到文件引用: target_id={file_target_id}, file_name={file_name}")
        if file_target_id and file_name:
            media_data = await self._download_user_file_bytes(file_target_id, file_name)
            if media_data and self._media_match_expect(media_data, expect):
                return media_data

        print(
            f"⚠️ 媒体获取失败: expect={expect}, msg_ids={msg_ids}, "
            f"content_type={type(content_payload).__name__}"
        )
        return None

    async def _resolve_incoming_media_bytes_with_retry(self, msg_id: str, msg_content: Dict[str, Any], expect: str = "any") -> Optional[bytes]:
        max_attempts = max(1, self.media_fetch_retry_count)
        delay = max(0.1, self.media_fetch_retry_delay)

        for attempt in range(1, max_attempts + 1):
            media_data = await self._resolve_incoming_media_bytes(msg_id, msg_content, expect=expect)
            if media_data:
                if attempt > 1:
                    print(f"✅ 媒体重试成功: expect={expect}, attempt={attempt}/{max_attempts}")
                return media_data

            if attempt < max_attempts:
                print(f"⏳ 媒体未就绪，等待重试: expect={expect}, attempt={attempt}/{max_attempts}, sleep={delay:.2f}s")
                await asyncio.sleep(delay)
                delay = min(delay * 1.6, 3.0)

        return None

    async def _resolve_incoming_media_url(self, msg_id: str, msg_content: Dict[str, Any], expect: str = "image") -> Optional[str]:
        if not self.http_session:
            await self._ensure_http_session()

        headers = self._auth_headers()
        content_raw = msg_content.get("content")
        content_payload = self._safe_json_loads(content_raw)

        candidate = self._extract_media_payload_candidate(content_payload)
        if not candidate and isinstance(content_raw, str) and self._is_likely_media_locator(content_raw):
            candidate = content_raw.strip()

        normalized = self._normalize_media_url(candidate)
        if normalized:
            return normalized

        msg_ids = self._collect_media_message_ids(msg_id, content_payload)
        for candidate_msg_id in msg_ids:
            locator = await self._fetch_media_locator_by_msg_id(candidate_msg_id, headers)
            normalized_locator = self._normalize_media_url(locator)
            if normalized_locator:
                return normalized_locator

        file_target_id, file_name = self._extract_user_file_reference(content_payload)
        if file_target_id and file_name:
            locator = await self._fetch_user_media_url(file_target_id, file_name)
            normalized_locator = self._normalize_media_url(locator)
            if normalized_locator:
                return normalized_locator

        return None

    async def _fetch_media_locator_by_msg_id(self, msg_id: str, headers: Dict[str, str]) -> Optional[str]:
        if not msg_id or not self.http_session:
            return None

        request_variants = [
            {
                "url": f"{self._http_base_url}/v1/api/message/get/media?msgId={msg_id}",
                "headers": headers,
            },
            {
                "url": f"{self._http_base_url}/v1/api/message/get/media",
                "headers": {**headers, "msgId": msg_id},
            },
        ]

        for variant in request_variants:
            try:
                async with self.http_session.get(variant["url"], headers=variant["headers"]) as resp:
                    if resp.status != 200:
                        continue
                    text = await resp.text()
                    payload = self._safe_json_loads(text)
                    candidate = self._extract_media_payload_candidate(payload)
                    if candidate:
                        return candidate
            except Exception:
                continue
        return None

    def _normalize_media_url(self, candidate: Optional[str]) -> Optional[str]:
        token = str(candidate or "").strip()
        if not token:
            return None
        if token.startswith("http://") or token.startswith("https://"):
            return token
        if token.startswith("/"):
            return f"{self._http_base_url}{token}"
        return None

    def _extract_user_file_reference(self, payload: Any) -> tuple[Optional[str], Optional[str]]:
        file_token = None

        def _walk(node: Any):
            nonlocal file_token
            if file_token:
                return
            if isinstance(node, dict):
                for key in ("fileName", "filename", "name"):
                    value = node.get(key)
                    if isinstance(value, str) and value.strip():
                        file_token = value.strip()
                        return
                for value in node.values():
                    _walk(value)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)

        _walk(payload)
        if not file_token:
            return None, None

        normalized = file_token.replace("\\", "/")
        parts = [p for p in normalized.split("/") if p]
        if not parts:
            return None, None

        if len(parts) >= 2:
            return parts[0], parts[-1]
        return None, parts[-1]

    async def _download_user_file_bytes(self, target_id: str, file_name: str) -> Optional[bytes]:
        if not self.http_session:
            await self._ensure_http_session()
        headers = self._auth_headers()
        headers["targetId"] = str(target_id)
        headers["fileName"] = str(file_name)
        url = f"{self._http_base_url}/v1/api/user/get/file"
        try:
            async with self.http_session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    preview = str(text or "")[:160].replace("\n", " ")
                    self._media_debug_log(
                        f"⚠️ user/get/file失败: status={resp.status}, target_id={target_id}, "
                        f"file_name={file_name}, body={preview}"
                    )
                    return None
                data = await resp.read()
                if self._looks_like_image_bytes(data) or self._looks_like_audio_bytes(data):
                    return data
        except Exception as e:
            self._media_debug_log(f"⚠️ user/get/file异常: {type(e).__name__}: {str(e)}")
        return None

    async def _fetch_user_media_url(self, target_id: str, file_name: str) -> Optional[str]:
        try:
            result = await self._request_json(
                "GET",
                f"/v1/api/user/get/img?targetId={target_id}&fileName={file_name}"
            )
            candidate = self._extract_media_payload_candidate(result)
            if candidate:
                return candidate
        except Exception as e:
            self._media_debug_log(f"⚠️ user/get/img异常: {type(e).__name__}: {str(e)}")
        return None

    @staticmethod
    def _media_match_expect(media_data: bytes, expect: str) -> bool:
        if expect == "image":
            return LinyuAdapter._looks_like_image_bytes(media_data)
        if expect == "audio":
            return LinyuAdapter._looks_like_audio_bytes(media_data)
        return True

    def _collect_media_message_ids(self, primary_msg_id: str, payload: Any) -> List[str]:
        ids: List[str] = []
        if primary_msg_id:
            ids.append(str(primary_msg_id))

        def _walk(node: Any):
            if isinstance(node, dict):
                for key in ("id", "msgId", "msg_id", "fileId", "file_id", "mediaId", "media_id"):
                    value = node.get(key)
                    if value:
                        ids.append(str(value))
                for value in node.values():
                    _walk(value)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)

        _walk(payload)
        deduped: List[str] = []
        seen = set()
        for item in ids:
            token = str(item).strip()
            if not token or token in seen:
                continue
            seen.add(token)
            deduped.append(token)
        return deduped

    async def _extract_media_bytes_from_raw(self, raw_data: bytes, content_type: str, headers: Dict[str, str]) -> Optional[bytes]:
        if not raw_data:
            return None

        if self._looks_like_image_bytes(raw_data) or self._looks_like_audio_bytes(raw_data):
            return raw_data

        text = raw_data.decode("utf-8", errors="ignore").strip()
        if not text:
            return None

        if "application/json" in content_type or text.startswith("{") or text.startswith("["):
            payload = self._safe_json_loads(text)
            candidate = self._extract_media_payload_candidate(payload)
            if candidate:
                extracted = await self._resolve_media_candidate_to_bytes(candidate, headers)
                if extracted:
                    return extracted

        extracted = await self._resolve_media_candidate_to_bytes(text, headers)
        if extracted:
            return extracted
        return None

    @staticmethod
    def _looks_like_image_bytes(data: bytes) -> bool:
        return bool(
            data.startswith(b"\xff\xd8\xff") or
            data.startswith(b"\x89PNG\r\n\x1a\n") or
            data.startswith((b"GIF87a", b"GIF89a")) or
            (len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP") or
            data.startswith(b"BM")
        )

    @staticmethod
    def _looks_like_audio_bytes(data: bytes) -> bool:
        return bool(
            data.startswith(b"ID3") or
            data.startswith(b"\xff\xfb") or
            (len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE") or
            data.startswith(b"OggS")
        )

    def _extract_media_payload_candidate(self, payload: Any) -> Optional[str]:
        if isinstance(payload, str):
            text = payload.strip()
            if self._is_likely_media_locator(text):
                return text
            return None
        if isinstance(payload, dict):
            for key in ("url", "file", "content", "data", "src", "path", "downloadUrl", "download_url"):
                if key in payload:
                    candidate = self._extract_media_payload_candidate(payload.get(key))
                    if candidate:
                        return candidate
            for value in payload.values():
                candidate = self._extract_media_payload_candidate(value)
                if candidate:
                    return candidate
            return None
        if isinstance(payload, list):
            for item in payload:
                candidate = self._extract_media_payload_candidate(item)
                if candidate:
                    return candidate
        return None

    async def _resolve_media_candidate_to_bytes(self, candidate: str, headers: Dict[str, str]) -> Optional[bytes]:
        token = str(candidate or "").strip()
        if not token:
            return None
        if not self._is_likely_media_locator(token):
            return None

        if token.startswith("http://") or token.startswith("https://"):
            self._media_debug_log(f"ℹ️ 尝试通过URL获取媒体字节: {token[:160]}")

            return await self._download_media_from_url(token, headers)

        if token.startswith("/"):
            return await self._download_media_from_url(token, headers)

        decoded = self._decode_base64_media(token)
        if decoded:
            return decoded

        return None

    def _decode_base64_media(self, value: str) -> Optional[bytes]:
        payload = value.strip()
        if payload.startswith("/"):
            return None
        if payload.startswith("base64://"):
            payload = payload[9:]
        elif payload.startswith("data:"):
            comma = payload.find(",")
            if comma >= 0:
                payload = payload[comma + 1:]

        payload = payload.replace("\n", "").replace("\r", "").strip()
        if len(payload) < 32:
            return None

        try:
            decoded = base64.b64decode(payload, validate=True)
        except Exception:
            return None

        if self._looks_like_image_bytes(decoded) or self._looks_like_audio_bytes(decoded):
            return decoded
        return None

    async def _download_media_from_url(self, url: str, headers: Dict[str, str], depth: int = 0) -> Optional[bytes]:
        target_url = str(url or "").strip()
        if not target_url:
            return None
        if target_url.startswith("/"):
            target_url = f"{self._http_base_url}{target_url}"
        if depth > 2:
            return None

        try:
            for request_headers, mode in ((headers, "with-auth"), ({}, "no-auth")):
                async with self.http_session.get(target_url, headers=request_headers) as resp:
                    content_type = str(resp.headers.get("Content-Type") or "").lower()
                    raw = await resp.read()

                    if resp.status != 200:
                        preview = raw.decode("utf-8", errors="ignore")[:180].replace("\n", " ")
                        self._media_debug_log(
                            f"⚠️ URL下载非200: mode={mode}, status={resp.status}, "
                            f"content_type={content_type}, url={target_url[:180]}, body={preview}"
                        )
                        continue

                    if self._looks_like_image_bytes(raw) or self._looks_like_audio_bytes(raw):
                        return raw

                    if "application/json" in content_type:
                        text = raw.decode("utf-8", errors="ignore")
                        payload = self._safe_json_loads(text)
                        candidate = self._extract_media_payload_candidate(payload)
                        if candidate and candidate != target_url:
                            return await self._download_media_from_url(candidate, headers, depth=depth + 1)

                    first_bytes = raw[:16].hex()
                    preview = raw.decode("utf-8", errors="ignore")[:120].replace("\n", " ")
                    self._media_debug_log(
                        f"⚠️ URL下载内容不是媒体: mode={mode}, status=200, content_type={content_type}, "
                        f"len={len(raw)}, first16={first_bytes}, preview={preview}"
                    )
        except Exception as e:
            self._media_debug_log(f"⚠️ 下载媒体URL失败: {type(e).__name__}: {str(e)}")
        return None

    @staticmethod
    def _is_likely_media_locator(value: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        lower = text.lower()
        if lower.startswith(("http://", "https://", "data:", "base64://", "/")):
            return True
        if len(text) >= 96 and re.fullmatch(r"[A-Za-z0-9+/=\r\n]+", text):
            return True
        return False

    def _media_debug_log(self, message: str):
        if self.media_debug_logs:
            print(message)

    @staticmethod
    def _mask_token(token: Optional[str]) -> str:
        raw = str(token or "")
        if len(raw) <= 16:
            return "***"
        return f"{raw[:8]}...{raw[-6:]}"

    def _mask_ws_url(self, url: str) -> str:
        if "x-token=" not in url:
            return url
        prefix, token = url.split("x-token=", 1)
        return f"{prefix}x-token={self._mask_token(token)}"

    def get_runtime_status(self) -> Dict[str, Any]:
        return {
            "owner_user_id": self.owner_user_id,
            "enabled": bool(self.account and self.password),
            "running": self.running,
            "connected": self.websocket is not None,
            "login_account": self.account,
            "self_user_id": self.user_id,
            "target_user_id": self.target_user_id,
            "target_user_account": self.target_user_account,
            "auto_bind_first_user": self.auto_bind_first_user,
            "reconnect_attempts": self.reconnect_attempts,
            "last_started_at": datetime.fromtimestamp(self.last_started_at).isoformat() if self.last_started_at else None,
            "last_connected_at": datetime.fromtimestamp(self.last_connected_at).isoformat() if self.last_connected_at else None,
            "last_error": self.last_error,
            "http_host": self.http_host,
            "http_port": self.http_port,
            "ws_host": self.ws_host,
            "ws_port": self.ws_port,
        }

    async def _mark_read(self, target_id: str):
        try:
            await self._request_json("GET", f"/v1/api/chat-list/read/{target_id}")
        except Exception:
            pass

    async def _request_json(self, method: str, path: str, json_data: Optional[dict] = None, with_token: bool = True):
        if not self.http_session:
            await self._ensure_http_session()
        url = f"{self._http_base_url}{path}"
        headers = self._auth_headers() if with_token else {}
        async with self.http_session.request(method, url, json=json_data, headers=headers) as resp:
            text = await resp.text()
            if resp.status == 403:
                self.token = None
                raise ConnectionError("Token失效")
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = text
            if isinstance(data, dict) and data.get("code") in (-1, -2):
                self.token = None
                raise ConnectionError("Token失效")
            return data

    async def _request_raw(self, method: str, path: str, data: bytes, headers: Optional[dict] = None):
        if not self.http_session:
            await self._ensure_http_session()
        url = f"{self._http_base_url}{path}"
        async with self.http_session.request(method, url, data=data, headers=headers) as resp:
            if resp.status == 403:
                self.token = None
                raise ConnectionError("Token失效")
            return resp.status, await resp.text()

    def _auth_headers(self) -> Dict[str, str]:
        return {"x-token": self.token} if self.token else {}

    async def _resolve_target_user_id(self):
        # 如果配置的是账号，则通过接口解析到 userId
        account = self.target_user_account
        if not account and self.target_user_id and not self._looks_like_uuid(self.target_user_id):
            account = self.target_user_id

        if not account:
            return

        resolved = await self._resolve_user_id_by_account(account)
        if resolved:
            self.target_user_id = resolved
            if self.access_control_enabled and self.access_control_mode == "whitelist":
                self.access_whitelist.add(resolved)
            print(f"✅ 已解析账号 {account} -> userId {resolved}")
        else:
            print(f"⚠️ 未能通过账号解析 userId: {account}，请检查账号是否正确")

    async def _resolve_user_id_by_account(self, account: str) -> Optional[str]:
        try:
            payload = {"userInfo": account}
            result = await self._request_json("POST", "/v1/api/user/search", json_data=payload)
            data = result.get("data") if isinstance(result, dict) else None
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    if str(item.get("account", "")) == account:
                        return str(item.get("id") or item.get("userId") or "")
                if len(data) == 1 and isinstance(data[0], dict):
                    return str(data[0].get("id") or data[0].get("userId") or "")
            elif isinstance(data, dict):
                return str(data.get("id") or data.get("userId") or "")
        except Exception as e:
            print(f"⚠️ 账号解析失败: {str(e)}")
        return None

    @staticmethod
    def _looks_like_uuid(value: str) -> bool:
        if not value:
            return False
        return bool(len(value) == 36 and value.count("-") == 4)

    async def _try_resolve_linyu_binding(self, linyu_user_id: str):
        """如果数据库中有用户绑定了账号名（非UUID），尝试通过 Linyu API 查询该 userId 对应的 account，
        然后将数据库中按账号名绑定的记录更新为真实的 userId。
        
        这样用户绑定时输入账号名即可，首次收到消息时自动修正为 UUID。
        只在首次需要时执行，之后直接命中缓存。
        """
        from ..user import user_manager

        # 如果已经能按 userId 找到用户，无需解析
        existing = await user_manager.get_user_by_linyu_id(linyu_user_id)
        if existing:
            return

        # userId 是 UUID 格式，尝试查询对应的账号名
        if not self._looks_like_uuid(linyu_user_id):
            return

        try:
            account = await self._get_account_by_user_id(linyu_user_id)
            if not account:
                return

            # 查找是否有用户绑定了这个账号名
            user_by_account = await user_manager.get_user_by_linyu_id(account)
            if user_by_account:
                # 将账号名更新为真实的 userId，同时保留账号名用于显示
                await user_manager.update_user(
                    user_id=user_by_account.id,
                    linyu_user_id=linyu_user_id,
                    linyu_account=account
                )
                print(f"✅ 自动更新 Linyu 绑定: {account} -> {linyu_user_id}")
        except Exception as e:
            # 解析失败不影响正常消息处理
            pass

    async def _get_bound_linyu_user(self, linyu_user_id: str):
        from ..user import user_manager
        try:
            return await user_manager.get_user_by_linyu_id(linyu_user_id)
        except Exception:
            return None

    async def _has_any_explicit_linyu_binding(self) -> bool:
        from ..user import user_manager
        try:
            return await user_manager.has_any_linyu_binding()
        except Exception:
            return False

    def _should_allow_bound_user_target_override(self, bound_user: Optional[Any]) -> bool:
        return bool(
            bound_user
            and self.auto_bind_first_user
            and not self._has_explicit_target
        )

    def _grant_bound_user_whitelist_access(self, user_id: str, bound_user: Optional[Any]):
        if (
            not self._should_allow_bound_user_target_override(bound_user)
            or not self.access_control_enabled
            or self.access_control_mode != "whitelist"
        ):
            return
        self.access_whitelist.add(user_id)

    async def _get_account_by_user_id(self, target_user_id: str) -> Optional[str]:
        """通过 Linyu API 查询用户 ID 对应的账号名"""
        try:
            result = await self._request_json(
                "POST", "/v1/api/user/search",
                json_data={"userInfo": target_user_id}
            )
            data = result.get("data") if isinstance(result, dict) else None
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        uid = str(item.get("id") or item.get("userId") or "")
                        if uid == target_user_id:
                            return str(item.get("account", ""))
                if len(data) == 1 and isinstance(data[0], dict):
                    return str(data[0].get("account", ""))
            elif isinstance(data, dict):
                return str(data.get("account", ""))
        except Exception:
            pass
        return None

    def _check_user_access(self, user_id: str) -> tuple[bool, str]:
        if not self.access_control_enabled:
            return True, ""
        if self.access_control_mode == "whitelist":
            if not self.access_whitelist and self.target_user_id:
                self.access_whitelist.add(self.target_user_id)
            if user_id in self.access_whitelist:
                return True, ""
            return False, self.access_deny_message
        if self.access_control_mode == "blacklist":
            if user_id in self.access_blacklist:
                return False, self.access_deny_message
            return True, ""
        return True, ""

    def _get_conversation_key(self, target_id: str, is_group: bool, user_id: Optional[str] = None) -> str:
        if is_group:
            return f"linyu_group_{target_id}_{user_id}"
        return f"linyu_user_{target_id}"

    def _deliver_follow_up_message(self, conversation_key: str, message_text: Optional[str]) -> bool:
        future = self.follow_up_waiters.get(conversation_key)
        if future is not None and not future.done():
            future.set_result(message_text or "")
            return True
        return False

    async def _wait_for_follow_up_message(self, conversation_key: str, timeout: float = 5.0) -> Optional[str]:
        follow_up_future: Optional[asyncio.Future] = None
        try:
            existing_future = self.follow_up_waiters.get(conversation_key)
            if existing_future is not None:
                follow_up_future = existing_future
            else:
                loop = asyncio.get_running_loop()
                follow_up_future = loop.create_future()
                self.follow_up_waiters[conversation_key] = follow_up_future
            message = await asyncio.wait_for(follow_up_future, timeout=timeout)
            return message.strip() if isinstance(message, str) else None
        except asyncio.TimeoutError:
            return None
        finally:
            stored = self.follow_up_waiters.get(conversation_key)
            if follow_up_future and stored is follow_up_future:
                self.follow_up_waiters.pop(conversation_key, None)

    async def _send_image_with_delay(self, user_id: str, image_data: bytes, delay_seconds: float = 5.0):
        try:
            await asyncio.sleep(delay_seconds)
            await self.send_image_message(user_id, image_data)
        except Exception as e:
            print(f"[Linyu Adapter] 延迟发送图片失败: {str(e)}")

    async def _maybe_send_emote(self, user_text: str, bot_reply: str, target_id: str):
        if not getattr(self.bot, "emote_manager", None):
            return
        try:
            selection = self.bot.emote_manager.select_emote(user_text, bot_reply)
        except Exception as e:
            print(f"[Emote] failed to select emote: {str(e)}")
            return
        if not selection:
            return
        try:
            conversation_key = self._get_conversation_key(target_id, is_group=False)
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
            await self.send_image_message(target_id, selection.as_bytes())
            print(f"[Emote] sent emote {selection.category}/{selection.file_name}")
        except Exception as e:
            print(f"[Emote] send emote failed: {str(e)}")

    @staticmethod
    def _safe_json_loads(raw: Any) -> Optional[Dict[str, Any]]:
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None
        return None
