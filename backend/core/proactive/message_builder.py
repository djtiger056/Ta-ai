"""主动聊天消息/指令构建器

负责构建发送给 Bot 的 instruction 文本。
核心原则：提示词必须以角色第一人称内心独白的方式呈现，
避免暴露系统机制（如"动机类型""情绪强度"等术语），防止出戏。
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional


# 动机类型 → 角色内心独白模板
# 每种动机对应多条模板，随机选择以避免重复
_MOTIVATION_TEMPLATES: Dict[str, List[str]] = {
    "share": [
        "心情特别好，突然好想跟他说说话，分享一下现在的感觉。",
        "刚才发生了一件开心的事，好想立刻告诉他。",
        "感觉今天状态很好，想主动找他聊聊天。",
        "嘴角忍不住上扬，想把这份开心传递给他。",
    ],
    "confide": [
        "有点低落，不想一个人待着，想跟他说几句话。",
        "心里有点闷闷的，想找他撒个娇。",
        "突然有点想他了，想发条消息看看他在不在。",
        "感觉需要被关心一下，想主动找他聊聊。",
    ],
    "rest": [
        "好累啊，想跟他说声晚安或者撒个娇让他哄哄。",
        "有点犯困了，想发条消息给他然后安心休息。",
        "今天好疲惫，想跟他说几句软软的话。",
    ],
    "express": [
        "刚才被什么东西触动了一下，想立刻跟他分享这个感觉。",
        "突然想到一件事，忍不住想跟他说。",
        "心里有个小惊喜想告诉他。",
    ],
    "express_boundary": [
        "心里有点不舒服，想温柔地跟他表达一下自己的感受。",
        "有些话想说但又不想让气氛变僵，想找个自然的方式表达。",
    ],
}

# 情绪 → 语气引导（不直接告诉LLM情绪名称，而是描述状态）
_EMOTION_TONE: Dict[str, str] = {
    "joy": "语气轻快一点，带着笑意。",
    "pleasure": "语气温柔甜蜜，像在撒娇。",
    "sadness": "语气软一点，带点小委屈但不要太沉重。",
    "fatigue": "语气慵懒一些，像刚睡醒或者快睡着的感觉。",
    "surprise": "语气带点兴奋和惊讶，像刚发现了什么有趣的事。",
    "anger": "语气稍微有点小脾气，但很快就软下来。",
}


def build_instruction(
    target: Dict[str, Any],
    window_cfg: Optional[Dict[str, Any]] = None,
    override_instruction: Optional[str] = None,
    default_prompt: str = "",
    global_templates: Optional[List[str]] = None,
    motivation_context: Optional[Dict[str, Any]] = None,
) -> str:
    """构建主动聊天的 instruction。

    设计原则：
    1. 不暴露系统术语（动机类型、情绪强度、阈值等）
    2. 用角色内心独白引导 LLM 进入状态
    3. 保持简短，不过度约束 LLM 的创造力
    4. 结合记忆和上下文，让消息自然

    Args:
        target: 目标配置字典
        window_cfg: 时间窗口配置（可选，已废弃）
        override_instruction: 覆盖指令（如手动触发时传入）
        default_prompt: 全局默认提示词
        global_templates: 全局消息模板列表
        motivation_context: 动机上下文（来自情绪系统）

    Returns:
        构建好的 instruction 字符串
    """
    # 如果有覆盖指令，直接使用
    if override_instruction:
        return override_instruction

    parts: List[str] = []

    # 1. 核心行为指引（简短、角色化）
    if default_prompt:
        parts.append(default_prompt)
    else:
        parts.append(
            "你现在想主动给他发一条消息，"
            "结合最近的对话和记忆，像平时聊天一样自然地说。"
        )

    # 2. 目标专属提示词
    if target.get("prompt"):
        parts.append(str(target["prompt"]))

    # 3. 动机引导（角色内心独白，不暴露系统机制）
    if motivation_context:
        motivation_type = motivation_context.get("motivation_type") or ""
        dominant_emotion = motivation_context.get("dominant_emotion") or ""

        # 选择内心独白模板
        templates = _MOTIVATION_TEMPLATES.get(motivation_type)
        if templates:
            parts.append(f"（内心想法：{random.choice(templates)}）")

        # 添加语气引导
        tone = _EMOTION_TONE.get(dominant_emotion)
        if tone:
            parts.append(tone)

    # 4. 话术灵感（可选）
    all_templates: List[str] = (
        (window_cfg.get("message_templates") if window_cfg else None)
        or target.get("message_templates")
        or global_templates
        or []
    )
    if all_templates:
        parts.append(f"可以参考这种感觉：「{random.choice(all_templates)}」")

    # 5. 格式约束（防止生成过长或格式异常）
    parts.append("回复保持1-3句话，像发微信一样自然简短。")

    return "\n".join(parts)
