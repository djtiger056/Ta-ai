from __future__ import annotations

import re
from typing import Optional, Tuple


_GEN_VIDEO_TAG_RE = re.compile(r"\[GEN_VIDEO:\s*(.*?)\]", re.IGNORECASE | re.DOTALL)
_PROMPT_LABEL_RE = re.compile(r"(?:提示词|prompt)\s*[:：]\s*(.+)$", re.IGNORECASE | re.DOTALL)
_BRACKET_VIDEO_GEN_RE = re.compile(r"^\s*\[[^\]]*视频生成[^\]]*\]\s*", re.IGNORECASE)


def extract_gen_video_prompt(text: str) -> Tuple[str, Optional[str]]:
    """从文本中提取 [GEN_VIDEO: ...] 视频生成指令，并返回(清理后的文本, 提示词)。"""
    if not text:
        return "", None

    matches = list(_GEN_VIDEO_TAG_RE.finditer(text))
    if not matches:
        return text, None

    last = matches[-1]
    tag_prompt = (last.group(1) or "").strip()

    suffix = text[last.end():]
    suffix_stripped = suffix.strip()

    suffix_prompt: Optional[str] = None
    label_match = _PROMPT_LABEL_RE.search(suffix_stripped)
    if label_match:
        suffix_prompt = (label_match.group(1) or "").strip()

    prompt = suffix_prompt or tag_prompt
    prefix = text[:last.start()].rstrip()

    looks_like_meta = False
    if suffix_stripped:
        if "提示词" in suffix_stripped or "prompt" in suffix_stripped.lower():
            looks_like_meta = True
        else:
            tmp = suffix_stripped
            while _BRACKET_VIDEO_GEN_RE.match(tmp):
                tmp = _BRACKET_VIDEO_GEN_RE.sub("", tmp, count=1).lstrip()
            if not tmp:
                looks_like_meta = True

    if looks_like_meta:
        cleaned = prefix
    else:
        cleaned = (prefix + suffix).strip()

    cleaned = _GEN_VIDEO_TAG_RE.sub("", cleaned).rstrip()

    if not prompt:
        return cleaned, None
    return cleaned, prompt
