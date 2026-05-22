from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

import aiohttp
from aiohttp import ClientTimeout

from .config import VideoGenerationConfig


logger = logging.getLogger(__name__)


class VideoGenerationManager:
    """视频生成管理器。"""

    def __init__(self, config: VideoGenerationConfig):
        self.config = config

    def update_config(self, config: VideoGenerationConfig) -> None:
        self.config = config

    def should_trigger_video_generation(self, message: str) -> Optional[str]:
        """检查用户消息是否主动表达视频生成意愿，并尽量提取需求文本。"""
        if not self.config.enabled:
            return None

        text = str(message or "").strip()
        if not text:
            return None

        for keyword in self.config.trigger_keywords:
            keyword = str(keyword or "").strip()
            if not keyword:
                continue
            if keyword in text:
                prompt = self._extract_prompt(text, keyword)
                return prompt or text
        return None

    def build_prompt_instruction(self, user_intent: str) -> str:
        instruction = str(self.config.prompt_instruction or "").strip()
        intent = str(user_intent or "").strip()
        if intent:
            return f"{instruction}\n\n用户的视频需求：{intent}"
        return instruction

    def _extract_prompt(self, message: str, keyword: str) -> Optional[str]:
        patterns = [
            rf"{re.escape(keyword)}[:：]\s*(.+)",
            rf"{re.escape(keyword)}[，,]\s*(?:主题是|内容是|画面是)?\s*(.+)",
            rf"帮我{re.escape(keyword)}(.+)",
            rf"请{re.escape(keyword)}(.+)",
            rf"{re.escape(keyword)}(.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                prompt = re.sub(r"[。，！？,.!?]+$", "", match.group(1).strip())
                if prompt:
                    return prompt
        return None

    async def generate_video(self, prompt: str, images: Optional[List[str]] = None) -> Optional[str]:
        """生成视频，成功返回视频 URL。"""
        if not self.config.enabled:
            return None
        if self.config.provider != "video_api":
            raise ValueError(f"不支持的视频生成提供商: {self.config.provider}")

        cfg = self.config.video_api
        if cfg.use_async:
            return await self._generate_video_async(prompt, images=images)
        return await self._generate_video_sync(prompt, images=images)

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        api_key = str(self.config.video_api.api_key or "").strip()
        if api_key:
            headers["x-api-key"] = api_key
        return headers

    def _endpoint_path(self) -> str:
        cfg = self.config.video_api
        provider = str(cfg.provider or "").lower()
        if provider == "doubao" or str(cfg.model).startswith("doubao-"):
            return "/v1/doubao/videos/generations"
        if provider == "qwen" or str(cfg.model).startswith(("wan", "qwen-")):
            return "/v1/qwen/videos/generations"
        return "/v1/videos/generations"

    def _build_payload(self, prompt: str, images: Optional[List[str]] = None) -> Dict[str, Any]:
        cfg = self.config.video_api
        payload: Dict[str, Any] = {
            "model": cfg.model,
            "prompt": prompt,
            "response_format": "url",
        }
        clean_images = [str(image).strip() for image in (images or []) if str(image or "").strip()]
        if clean_images:
            payload["images"] = clean_images
        if cfg.duration:
            payload["duration"] = cfg.duration
        if cfg.resolution:
            payload["resolution"] = cfg.resolution
        if cfg.ratio and not clean_images:
            payload["ratio"] = cfg.ratio
        return payload

    def _normalize_video_url(self, data: Any) -> Optional[str]:
        if not isinstance(data, dict) or data.get("error"):
            return None
        candidates = [
            (data.get("data") or [{}])[0].get("url") if isinstance(data.get("data"), list) and data.get("data") else None,
            data.get("videoUrl"),
            data.get("result_url"),
        ]
        if isinstance(data.get("videoUrls"), list):
            candidates.extend(data.get("videoUrls"))
        for candidate in candidates:
            if candidate:
                return str(candidate)
        return None

    async def _post_json(self, session: aiohttp.ClientSession, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        async with session.post(url, headers=self._headers(), json=payload) as response:
            text = await response.text()
            try:
                data = await response.json(content_type=None)
            except Exception:
                data = {"message": text}
            if response.status < 200 or response.status >= 300:
                message = data.get("error", {}).get("message") if isinstance(data.get("error"), dict) else None
                raise RuntimeError(message or data.get("message") or f"HTTP {response.status}")
            return data

    async def _generate_video_sync(self, prompt: str, images: Optional[List[str]] = None) -> Optional[str]:
        cfg = self.config.video_api
        base = str(cfg.api_base or "").rstrip("/")
        url = f"{base}{self._endpoint_path()}"
        timeout = ClientTimeout(connect=15, sock_connect=15, sock_read=cfg.timeout, total=cfg.timeout + 30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            data = await self._post_json(session, url, self._build_payload(prompt, images=images))
            video_url = self._normalize_video_url(data)
            if not video_url:
                raise RuntimeError("接口未返回视频地址")
            return video_url

    async def _generate_video_async(self, prompt: str, images: Optional[List[str]] = None) -> Optional[str]:
        cfg = self.config.video_api
        base = str(cfg.api_base or "").rstrip("/")
        timeout = ClientTimeout(connect=15, sock_connect=15, sock_read=60, total=cfg.timeout + 60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            submit = await self._post_json(
                session,
                f"{base}/v1/videos/generations/async",
                self._build_payload(prompt, images=images),
            )
            task_id = submit.get("taskId") or submit.get("task_id") or (submit.get("data") or {}).get("task_id")
            if not task_id:
                video_url = self._normalize_video_url(submit)
                if video_url:
                    return video_url
                raise RuntimeError("异步接口未返回 taskId")

            elapsed = 0.0
            poll_interval = max(1.0, float(cfg.poll_interval or 4.0))
            while elapsed < cfg.timeout:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                async with session.get(
                    f"{base}/v1/videos/generations/async/{task_id}",
                    headers=self._headers(),
                ) as response:
                    data = await response.json(content_type=None)
                    if response.status < 200 or response.status >= 300:
                        raise RuntimeError(data.get("message") or f"HTTP {response.status}")
                status = str(data.get("status") or data.get("task_status") or "").lower()
                video_url = self._normalize_video_url(data)
                if video_url:
                    return video_url
                if status in {"failed", "error", "cancelled"} or data.get("error"):
                    message = data.get("error", {}).get("message") if isinstance(data.get("error"), dict) else None
                    raise RuntimeError(message or data.get("message") or "异步视频任务失败")
            raise TimeoutError("视频生成超时")

    async def test_connection(self) -> bool:
        cfg = self.config.video_api
        base = str(cfg.api_base or "").rstrip("/")
        if not base:
            return False
        timeout = ClientTimeout(connect=5, sock_connect=5, sock_read=10, total=15)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{base}/ping") as response:
                    return response.status == 200
        except Exception as e:
            logger.warning("视频生成服务连接测试失败: %s", e)
            return False
