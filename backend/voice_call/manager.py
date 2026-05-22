"""Linyu 视频信令管理器（先支持用户拨打 AI）。"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any, Dict, Optional

from .config import VoiceCallConfig
from .session import CallSession, CallState
from .webrtc_endpoint import WebRTCEndpoint


class VoiceCallManager:
    """处理 Linyu 的 video 信令。"""

    def __init__(self, adapter: Any, cfg: VoiceCallConfig):
        self.adapter = adapter
        self.cfg = cfg
        self.sessions: Dict[str, CallSession] = {}
        self.endpoints: Dict[str, WebRTCEndpoint] = {}

    def reload_config(self, cfg: VoiceCallConfig) -> None:
        self.cfg = cfg

    async def shutdown(self) -> None:
        for call_id, endpoint in list(self.endpoints.items()):
            try:
                await endpoint.close()
            except Exception:
                pass
            self.endpoints.pop(call_id, None)
        self.sessions.clear()

    async def handle_video_signal(self, content: Dict[str, Any]) -> None:
        if not self.cfg.enabled:
            return
        if not isinstance(content, dict):
            return

        content = self._normalize_signal_payload(content)
        signal_type = self._normalize_signal_type(content.get("type"))
        if not signal_type:
            return

        if signal_type == "invite":
            await self._handle_invite(content)
        elif signal_type == "offer":
            await self._handle_offer(content)
        elif signal_type == "candidate":
            await self._handle_candidate(content)
        elif signal_type == "hangup":
            await self._handle_hangup(content)
        elif signal_type == "accept":
            # 当前阶段主打“用户拨打AI”，accept主要用于后续双向拨号
            return
        elif signal_type == "answer":
            return

    def _normalize_signal_payload(self, content: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(content or {})

        desc = payload.get("desc")
        if isinstance(desc, dict):
            if not payload.get("sdp"):
                payload["sdp"] = desc.get("sdp")
            if not payload.get("sdpType"):
                payload["sdpType"] = desc.get("type") or desc.get("sdpType")

        candidate = payload.get("candidate")
        if isinstance(candidate, dict):
            payload["candidate"] = candidate.get("candidate")
            if not payload.get("sdpMid"):
                payload["sdpMid"] = candidate.get("sdpMid")
            if not payload.get("sdpMLineIndex"):
                payload["sdpMLineIndex"] = candidate.get("sdpMLineIndex")
            if not payload.get("usernameFragment"):
                payload["usernameFragment"] = candidate.get("usernameFragment")

        from_id = str(payload.get("fromId") or payload.get("from_id") or "").strip()
        if from_id and not payload.get("fromId"):
            payload["fromId"] = from_id

        if not payload.get("audioOnly"):
            if "isOnlyAudio" in payload:
                payload["audioOnly"] = payload.get("isOnlyAudio")
            elif "audio_only" in payload:
                payload["audioOnly"] = payload.get("audio_only")

        if not payload.get("callId"):
            payload["callId"] = self._derive_call_id(payload)

        return payload

    @staticmethod
    def _derive_call_id(payload: Dict[str, Any]) -> str:
        explicit_keys = ("call_id", "roomId", "room_id", "sessionId", "session_id")
        for key in explicit_keys:
            value = payload.get(key)
            if value:
                return str(value)

        signal_type = str(payload.get("type") or "").strip().lower()
        from_id = str(payload.get("fromId") or payload.get("from_id") or "").strip()
        sdp = str(payload.get("sdp") or "").strip()
        candidate = str(payload.get("candidate") or "").strip()

        if signal_type == "invite" and from_id:
            return f"invite:{from_id}"

        if signal_type in {"offer", "answer"} and from_id and sdp:
            digest = hashlib.sha1(sdp.encode("utf-8", errors="ignore")).hexdigest()[:12]
            return f"sdp:{from_id}:{digest}"

        if signal_type == "candidate" and from_id and candidate:
            digest = hashlib.sha1(candidate.encode("utf-8", errors="ignore")).hexdigest()[:12]
            return f"candidate:{from_id}:{digest}"

        if from_id:
            return f"{signal_type}:{from_id}"
        return ""

    @staticmethod
    def _normalize_signal_type(raw: Any) -> str:
        text = str(raw or "").strip().lower()
        if not text:
            return ""
        text = text.replace("-", "_")
        alias_map = {
            "callinvite": "invite",
            "call_invite": "invite",
            "rtc_invite": "invite",
            "calloffer": "offer",
            "call_offer": "offer",
            "rtc_offer": "offer",
            "callanswer": "answer",
            "call_answer": "answer",
            "rtc_answer": "answer",
            "callcandidate": "candidate",
            "call_candidate": "candidate",
            "ice_candidate": "candidate",
            "rtccandidate": "candidate",
            "rtc_candidate": "candidate",
            "callhangup": "hangup",
            "call_hangup": "hangup",
            "rtc_hangup": "hangup",
            "end": "hangup",
            "disconnect": "hangup",
        }
        if text in alias_map:
            return alias_map[text]
        for target in ("invite", "offer", "answer", "candidate", "hangup"):
            if target in text:
                return target
        return text

    async def _handle_invite(self, content: Dict[str, Any]) -> None:
        if not self.cfg.auto_answer:
            return

        call_id = str(content.get("callId") or content.get("call_id") or "")
        from_id = str(content.get("fromId") or content.get("from_id") or "")
        if not call_id or not from_id:
            return

        session = self.sessions.get(call_id)
        if session is None:
            session = CallSession(call_id=call_id, peer_user_id=from_id, is_audio_only=bool(content.get("audioOnly", True)))
            session.set_state(CallState.INCOMING_RINGING)
            self.sessions[call_id] = session

        await asyncio.sleep(max(0.0, float(self.cfg.answer_delay_seconds)))
        session.set_state(CallState.CONNECTING)

        payload = {
            "userId": from_id,
        }
        await self.adapter._request_json("POST", "/v1/api/video/accept", json_data=payload)

    async def _get_or_create_endpoint(self, call_id: str, peer_user_id: str) -> WebRTCEndpoint:
        if call_id in self.endpoints:
            return self.endpoints[call_id]

        async def _on_local_candidate(candidate_payload: dict):
            payload = {
                "userId": peer_user_id,
                "candidate": {
                    "candidate": candidate_payload.get("candidate"),
                    "sdpMid": candidate_payload.get("sdpMid"),
                    "sdpMLineIndex": candidate_payload.get("sdpMLineIndex"),
                    "usernameFragment": candidate_payload.get("usernameFragment"),
                },
            }
            await self.adapter._request_json("POST", "/v1/api/video/candidate", json_data=payload)

        endpoint = WebRTCEndpoint(on_local_candidate=_on_local_candidate)
        await endpoint.setup()
        self.endpoints[call_id] = endpoint
        return endpoint

    async def _handle_offer(self, content: Dict[str, Any]) -> None:
        call_id = str(content.get("callId") or content.get("call_id") or "")
        from_id = str(content.get("fromId") or content.get("from_id") or "")
        sdp = str(content.get("sdp") or "")
        sdp_type = str(content.get("sdpType") or content.get("sdp_type") or "offer")
        if not call_id or not from_id or not sdp:
            return

        session = self.sessions.get(call_id)
        if session is None:
            session = CallSession(call_id=call_id, peer_user_id=from_id)
            self.sessions[call_id] = session
        session.set_state(CallState.CONNECTING)

        endpoint = await self._get_or_create_endpoint(call_id=call_id, peer_user_id=from_id)
        answer = await endpoint.handle_offer(sdp=sdp, sdp_type=sdp_type)
        if not answer:
            session.set_state(CallState.FAILED)
            return

        payload = {
            "userId": from_id,
            "desc": {
                "sdp": answer.get("sdp"),
                "type": answer.get("type", "answer"),
            },
        }
        await self.adapter._request_json("POST", "/v1/api/video/answer", json_data=payload)
        session.set_state(CallState.CONNECTED)

    async def _handle_candidate(self, content: Dict[str, Any]) -> None:
        call_id = str(content.get("callId") or content.get("call_id") or "")
        if not call_id:
            return
        endpoint = self.endpoints.get(call_id)
        if not endpoint:
            return

        candidate_payload = {
            "candidate": content.get("candidate"),
            "sdpMid": content.get("sdpMid"),
            "sdpMLineIndex": content.get("sdpMLineIndex"),
            "usernameFragment": content.get("usernameFragment"),
        }
        await endpoint.add_ice_candidate(candidate_payload)

    async def _handle_hangup(self, content: Dict[str, Any]) -> None:
        call_id = str(content.get("callId") or content.get("call_id") or "")
        if not call_id:
            return

        session = self.sessions.get(call_id)
        if session:
            session.set_state(CallState.ENDED)

        endpoint = self.endpoints.pop(call_id, None)
        if endpoint:
            await endpoint.close()
        self.sessions.pop(call_id, None)
