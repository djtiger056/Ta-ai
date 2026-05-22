from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any
import json
import time

from . import proactive as proactive_api
from .bot_provider import get_bot, reset_bot  # noqa: F401 — 保持向后兼容

router = APIRouter(prefix="/api", tags=["chat"])

class ChatRequest(BaseModel):
    message: str
    user_id: str = "web_user"
    session_id: str | None = None

def _detect_audio_mime(audio_data: bytes) -> str:
    if not audio_data:
        return "audio/mpeg"
    if audio_data[:4] == b"RIFF" and audio_data[8:12] == b"WAVE":
        return "audio/wav"
    if audio_data[:4] == b"OggS":
        return "audio/ogg"
    return "audio/mpeg"

@router.post("/chat")
async def chat(request: ChatRequest):
    """普通聊天接口"""
    try:
        bot = get_bot()
        session_id = request.session_id or request.user_id
        proactive_api.record_user_activity("web", request.user_id, session_id, request.message)
        response = await bot.chat(request.message, request.user_id, session_id=session_id)
        proactive_api.record_assistant_activity("web", request.user_id, session_id, response)

        if bot.pop_last_mode_command(request.user_id, session_id) or await bot.is_roleplay_mode(request.user_id):
            return {
                "response": response,
                "audio": None,
                "audio_mime": None,
                "voice_only": False,
                "emote": None,
                "image": None,
            }

        # 获取生成的图片（如果有）
        last_image = bot.get_last_generated_image()
        image_base64 = None
        if last_image and last_image.get("image_data"):
            import base64
            image_base64 = base64.b64encode(last_image["image_data"]).decode('utf-8')
            print(f"[Chat API] 返回生成的图片，大小: {len(last_image['image_data'])} bytes")

        last_video = bot.get_last_generated_video()
        video_url = None
        if last_video and last_video.get("video_url"):
            video_url = last_video["video_url"]
            print(f"[Chat API] 返回生成的视频: {video_url}")

        # 尝试合成语音（优先 AI 主动触发，否则走概率）
        try:
            forced_tts = bot.get_last_tts_forced()
            audio_data = None
            audio_base64 = None
            audio_mime = None
            voice_only = bot.is_voice_only_mode(request.user_id)
            text_to_send = response

            if forced_tts and forced_tts.get("text"):
                # AI 主动触发 TTS
                audio_data = await bot.synthesize_speech_forced(
                    forced_tts["text"], user_id=request.user_id
                )
                if audio_data:
                    import base64
                    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                    audio_mime = _detect_audio_mime(audio_data)
                    print(f"TTS音频生成成功（AI主动触发），大小: {len(audio_data)} bytes")
                    if voice_only:
                        text_to_send = bot.strip_tts_text(response, request.user_id)
            else:
                # 概率触发 TTS
                audio_data = await bot.synthesize_speech(response, user_id=request.user_id)
                if audio_data:
                    import base64
                    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                    audio_mime = _detect_audio_mime(audio_data)
                    print(f"TTS音频生成成功，大小: {len(audio_data)} bytes")
                    if voice_only:
                        text_to_send = bot.strip_tts_text(response, request.user_id)
                else:
                    print("TTS未生成音频（可能被概率或配置阻止）")
                    text_to_send = response
        except Exception as e:
            print(f"TTS生成失败: {str(e)}")
            audio_base64 = None
            audio_mime = None
            voice_only = False
            text_to_send = response

        emote_payload = None
        try:
            emote_payload = bot.maybe_get_emote_payload(request.message, response)
        except Exception as e:
            print(f"选择表情包失败: {str(e)}")

        return {
            "response": text_to_send,
            "audio": audio_base64,
            "audio_mime": audio_mime,
            "voice_only": bool(audio_base64 and voice_only),
            "emote": emote_payload,
            "image": image_base64,
            "video": video_url,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"聊天失败: {str(e)}")

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式聊天接口"""
    async def generate():
        request_start = time.perf_counter()
        session_id = request.session_id or request.user_id

        def elapsed_ms() -> float:
            return round((time.perf_counter() - request_start) * 1000, 2)

        def meta_event(stage: str, extra: Dict[str, Any] | None = None) -> str:
            payload: Dict[str, Any] = {
                "meta": {
                    "stage": stage,
                    "elapsed_ms": elapsed_ms(),
                    "server_ts": time.time(),
                }
            }
            if extra:
                payload["meta"].update(extra)
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        try:
            yield meta_event("server_request_received")
            bot = get_bot()
            proactive_api.record_user_activity("web", request.user_id, session_id, request.message)
            yield meta_event("bot_ready")
            full_response = ""
            first_chunk_seen = False

            # 流式输出文本
            async for chunk in bot.chat_stream(request.message, request.user_id, session_id=session_id):
                if chunk is None:
                    continue
                if not first_chunk_seen:
                    yield meta_event("first_model_chunk")
                    first_chunk_seen = True
                chunk_text = str(chunk)
                full_response += chunk_text
                yield f"data: {json.dumps({'content': chunk_text})}\n\n"

            yield meta_event("llm_stream_done", {"response_chars": len(full_response)})
            proactive_api.record_assistant_activity("web", request.user_id, session_id, full_response)

            if bot.pop_last_mode_command(request.user_id, session_id) or await bot.is_roleplay_mode(request.user_id):
                yield meta_event("stream_done")
                yield "data: [DONE]\n\n"
                return

            # 获取生成的图片（如果有）
            last_image = bot.get_last_generated_image()
            if last_image and last_image.get("image_data"):
                import base64
                image_base64 = base64.b64encode(last_image["image_data"]).decode('utf-8')
                print(f"[Chat Stream API] 返回生成的图片，大小: {len(last_image['image_data'])} bytes")
                yield f"data: {json.dumps({'image': image_base64})}\n\n"

            last_video = bot.get_last_generated_video()
            if last_video and last_video.get("video_url"):
                video_url = last_video["video_url"]
                print(f"[Chat Stream API] 返回生成的视频: {video_url}")
                yield f"data: {json.dumps({'video': video_url}, ensure_ascii=False)}\n\n"

            # 完成文本输出后，尝试合成语音（优先 AI 主动触发）
            try:
                forced_tts = bot.get_last_tts_forced()
                if forced_tts and forced_tts.get("text"):
                    audio_data = await bot.synthesize_speech_forced(
                        forced_tts["text"], user_id=request.user_id
                    )
                    if audio_data:
                        import base64
                        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                        print(f"流式TTS音频生成成功（AI主动触发），大小: {len(audio_data)} bytes")
                        yield f"data: {json.dumps({'audio': audio_base64, 'audio_mime': _detect_audio_mime(audio_data), 'voice_only': bot.is_voice_only_mode(request.user_id)})}\n\n"
                else:
                    audio_data = await bot.synthesize_speech(full_response, user_id=request.user_id)
                    if audio_data:
                        import base64
                        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                        print(f"流式TTS音频生成成功，大小: {len(audio_data)} bytes")
                        yield f"data: {json.dumps({'audio': audio_base64, 'audio_mime': _detect_audio_mime(audio_data), 'voice_only': bot.is_voice_only_mode(request.user_id)})}\n\n"
                    else:
                        print("流式TTS未生成音频")
            except Exception as e:
                print(f"流式TTS生成失败: {str(e)}")

            try:
                emote_payload = bot.maybe_get_emote_payload(request.message, full_response)
                if emote_payload:
                    yield f"data: {json.dumps({'emote': emote_payload})}\n\n"
            except Exception as e:
                print(f"选择表情包失败: {str(e)}")

            yield meta_event("stream_done")
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield meta_event("stream_error", {"error": str(e)})
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
