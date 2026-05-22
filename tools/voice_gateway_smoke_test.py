#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""语音网关最小联调脚本。

用法示例：
python tools/voice_gateway_smoke_test.py \
  --base-url http://127.0.0.1:8003 \
  --user-id u_demo \
  --chat-id c_demo \
  --wav-in ./sample_16k_mono_pcm16.wav \
  --save-pcm-out ./ai_reply.pcm

注意：
1) 输入 WAV 必须是 16kHz / mono / PCM16。
2) 当前后端上行要求 20ms 帧，脚本会自动按 640 字节切帧发送。
3) 如果需要快速排错，建议先把 config.yaml 的 voice_gateway.tts.enabled 设为 false，先验证文本链路。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import wave
from pathlib import Path
from typing import Optional

import requests
import websockets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Voice Gateway 最小联调脚本")
    parser.add_argument("--base-url", default="http://127.0.0.1:8003", help="后端地址")
    parser.add_argument("--user-id", required=True, help="用户ID")
    parser.add_argument("--chat-id", required=True, help="会话ID")
    parser.add_argument("--device-id", default="smoke-device", help="设备ID")
    parser.add_argument("--platform", default="cli", help="平台标识")
    parser.add_argument("--wav-in", required=True, help="输入 WAV 文件（16k mono pcm16）")
    parser.add_argument("--save-pcm-out", default="", help="保存AI返回的PCM裸流")
    parser.add_argument("--frame-ms", type=int, default=20, help="发送帧长毫秒")
    parser.add_argument("--recv-seconds", type=int, default=8, help="发送完后继续接收秒数")
    return parser.parse_args()


def load_wav_pcm16_mono_16k(path: Path) -> bytes:
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        rate = wf.getframerate()
        width = wf.getsampwidth()
        if channels != 1 or rate != 16000 or width != 2:
            raise ValueError(
                f"WAV格式不匹配：channels={channels}, rate={rate}, width={width}；"
                "需要 mono/16000/16bit(2字节)"
            )
        return wf.readframes(wf.getnframes())


def request_token(
    base_url: str,
    user_id: str,
    chat_id: str,
    device_id: str,
    platform: str,
) -> dict:
    url = f"{base_url.rstrip('/')}/api/voice-session/token"
    payload = {
        "chat_id": chat_id,
        "user_id": user_id,
        "device_id": device_id,
        "platform": platform,
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


async def run_ws(
    ws_url: str,
    pcm_data: bytes,
    frame_ms: int,
    recv_seconds: int,
    save_pcm_out: Optional[Path],
) -> None:
    # 16kHz * 1ch * 16bit => 每毫秒 32 字节
    frame_bytes = int(16000 * frame_ms / 1000) * 2

    print(f"[INFO] 连接WS: {ws_url}")
    ai_audio = bytearray()

    async with websockets.connect(ws_url, max_size=None) as ws:
        await ws.send(json.dumps({"event": "session.start", "payload": {}}))
        print("[SEND] session.start")

        stop_recv = False

        async def recv_loop():
            nonlocal stop_recv
            while not stop_recv:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    break

                if isinstance(msg, bytes):
                    ai_audio.extend(msg)
                    print(f"[RECV][audio] {len(msg)} bytes")
                else:
                    try:
                        data = json.loads(msg)
                    except Exception:
                        print(f"[RECV][text-raw] {msg}")
                        continue

                    event = data.get("event")
                    payload = data.get("payload", {})
                    if event == "error":
                        print(f"[RECV][error] {payload}")
                    elif event == "transcript.user":
                        print(f"[RECV][user] {payload.get('text', '')}")
                    elif event == "transcript.ai.delta":
                        print(payload.get("delta", ""), end="", flush=True)
                    elif event == "transcript.ai.done":
                        print("\n[RECV][ai.done]")
                    else:
                        print(f"[RECV][{event}] {payload}")

        recv_task = asyncio.create_task(recv_loop())

        # 按20ms帧发送音频
        for i in range(0, len(pcm_data), frame_bytes):
            await ws.send(pcm_data[i:i + frame_bytes])
            await asyncio.sleep(frame_ms / 1000)

        print("[SEND] 音频发送完毕，等待AI响应...")
        await asyncio.sleep(max(1, recv_seconds))

        await ws.send(json.dumps({"event": "session.end", "payload": {"reason": "smoke_test"}}))
        print("[SEND] session.end")

        await asyncio.sleep(1.0)
        stop_recv = True
        await asyncio.gather(recv_task, return_exceptions=True)

    if save_pcm_out:
        save_pcm_out.write_bytes(bytes(ai_audio))
        print(f"[INFO] 已保存AI音频PCM: {save_pcm_out} ({len(ai_audio)} bytes)")


def main() -> None:
    args = parse_args()
    wav_path = Path(args.wav_in).resolve()
    if not wav_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {wav_path}")

    pcm_data = load_wav_pcm16_mono_16k(wav_path)
    print(f"[INFO] 读取输入音频: {wav_path} ({len(pcm_data)} bytes)")

    token_data = request_token(
        base_url=args.base_url,
        user_id=args.user_id,
        chat_id=args.chat_id,
        device_id=args.device_id,
        platform=args.platform,
    )

    token = token_data["token"]
    ws_path = token_data.get("ws_url", f"/ws/voice-session?token={token}")
    if ws_path.startswith("ws://") or ws_path.startswith("wss://"):
        ws_url = ws_path
    else:
        base = args.base_url.rstrip("/")
        if base.startswith("https://"):
            ws_base = "wss://" + base[len("https://") :]
        elif base.startswith("http://"):
            ws_base = "ws://" + base[len("http://") :]
        else:
            ws_base = "ws://" + base
        ws_url = ws_base + ws_path

    print(f"[INFO] session_id={token_data.get('session_id')} expires_in={token_data.get('expires_in')}s")
    save_path = Path(args.save_pcm_out).resolve() if args.save_pcm_out else None
    started = time.time()
    asyncio.run(
        run_ws(
            ws_url=ws_url,
            pcm_data=pcm_data,
            frame_ms=args.frame_ms,
            recv_seconds=args.recv_seconds,
            save_pcm_out=save_path,
        )
    )
    print(f"[INFO] 完成，耗时 {time.time() - started:.2f}s")


if __name__ == "__main__":
    main()
