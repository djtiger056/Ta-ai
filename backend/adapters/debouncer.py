"""消息防抖器：将短时间内同一用户的多条消息合并为一条再处理。

避免用户分多次发送消息时，AI 对每条消息分别回复的尴尬场景。
"""

import asyncio
from typing import Dict, List, Callable, Awaitable, Optional


class MessageDebouncer:
    """消息防抖器

    收到用户消息后启动倒计时，如果在倒计时内又收到新消息，
    则重置计时器并追加到缓冲区。超时后将所有缓冲消息合并为一条，
    调用回调函数处理。

    Parameters
    ----------
    delay : float
        最后一条消息后等待的秒数（默认 3.0）
    max_wait : float
        从第一条消息开始的最大等待时间（默认 15.0），
        防止用户持续发消息导致永远不触发回复
    separator : str
        多条消息合并时的分隔符（默认换行）
    """

    def __init__(
        self,
        delay: float = 3.0,
        max_wait: float = 15.0,
        separator: str = "\n",
    ):
        self.delay = delay
        self.max_wait = max_wait
        self.separator = separator

        # user_key -> 消息缓冲列表
        self._buffers: Dict[str, List[str]] = {}
        # user_key -> 防抖定时任务
        self._timers: Dict[str, asyncio.Task] = {}
        # user_key -> 回调函数
        self._callbacks: Dict[str, Callable[[str], Awaitable[None]]] = {}
        # user_key -> 第一条消息的时间戳（用于 max_wait 判断）
        self._first_message_time: Dict[str, float] = {}

    async def add_message(
        self,
        user_key: str,
        text: str,
        callback: Callable[[str], Awaitable[None]],
    ) -> None:
        """添加一条消息到缓冲区。

        Parameters
        ----------
        user_key : str
            用户标识（可以是 user_id，也可以是 group_id:user_id）
        text : str
            消息文本
        callback : async callable
            合并后的消息将传给此回调处理
        """
        loop = asyncio.get_running_loop()
        now = loop.time()

        # 初始化缓冲区
        if user_key not in self._buffers:
            self._buffers[user_key] = []
            self._first_message_time[user_key] = now
            print(f"⏳ [防抖] 收到 {user_key} 第1条消息，开始等待 {self.delay}s...")
        else:
            count = len(self._buffers[user_key]) + 1
            print(f"⏳ [防抖] 收到 {user_key} 第{count}条消息，重置计时器")

        self._buffers[user_key].append(text)
        self._callbacks[user_key] = callback

        # 检查是否已超过 max_wait
        elapsed = now - self._first_message_time.get(user_key, now)
        if elapsed >= self.max_wait:
            # 已经等够久了，立即触发
            print(f"⚡ [防抖] {user_key} 已达最大等待时间 {self.max_wait}s，立即触发回复")
            await self._fire(user_key)
            return

        # 取消旧的定时器，启动新的
        old_timer = self._timers.get(user_key)
        if old_timer and not old_timer.done():
            old_timer.cancel()

        # 计算实际等待时间：取 delay 和剩余 max_wait 的较小值
        remaining_max = self.max_wait - elapsed
        actual_delay = min(self.delay, remaining_max)

        self._timers[user_key] = asyncio.create_task(
            self._delayed_fire(user_key, actual_delay)
        )

    async def _delayed_fire(self, user_key: str, delay: float) -> None:
        """等待指定时间后触发回调。"""
        try:
            await asyncio.sleep(delay)
            await self._fire(user_key)
        except asyncio.CancelledError:
            pass

    async def _fire(self, user_key: str) -> None:
        """合并缓冲区消息并触发回调。"""
        messages = self._buffers.pop(user_key, [])
        callback = self._callbacks.pop(user_key, None)
        self._timers.pop(user_key, None)
        self._first_message_time.pop(user_key, None)

        if messages and callback:
            merged = self.separator.join(messages)
            if len(messages) > 1:
                print(f"✅ [防抖] {user_key} 合并了 {len(messages)} 条消息为一条发送")
                for i, msg in enumerate(messages, 1):
                    preview = msg[:50] + "..." if len(msg) > 50 else msg
                    print(f"   ├─ 第{i}条: {preview}")
                merged_preview = merged[:100] + "..." if len(merged) > 100 else merged
                print(f"   └─ 合并结果: {merged_preview}")
            else:
                print(f"✅ [防抖] {user_key} 等待超时，仅1条消息，直接发送")
            try:
                await callback(merged)
            except Exception as e:
                print(f"❌ [防抖] 回调执行失败: {type(e).__name__}: {e}")

    def is_buffering(self, user_key: str) -> bool:
        """检查指定用户是否有消息正在缓冲中。"""
        return user_key in self._buffers

    def cancel(self, user_key: str) -> None:
        """取消指定用户的缓冲（丢弃未处理的消息）。"""
        self._buffers.pop(user_key, None)
        self._callbacks.pop(user_key, None)
        self._first_message_time.pop(user_key, None)
        timer = self._timers.pop(user_key, None)
        if timer and not timer.done():
            timer.cancel()

    def cancel_all(self) -> None:
        """取消所有缓冲。"""
        for key in list(self._timers.keys()):
            self.cancel(key)
