"""
文本分割工具
"""

import re
from typing import List


SENTENCE_ENDINGS = "。！？.!?"


def _split_sentence_chunks(text: str) -> List[str]:
    """按句末标点切分，并保留标点。"""
    parts = re.split(r'([。！？.!?]+)', text)
    chunks: List[str] = []

    for i in range(0, len(parts), 2):
        content = parts[i]
        ending = parts[i + 1] if i + 1 < len(parts) else ""
        chunk = f"{content}{ending}".strip()
        if chunk:
            chunks.append(chunk)

    if not chunks and text.strip():
        return [text.strip()]
    return chunks


def _split_chunk_by_spaces(chunk: str, max_length: int) -> List[str]:
    """当单句过长时，优先按空格继续分段，再回退到硬切分。"""
    chunk = chunk.strip()
    if not chunk:
        return []

    parts = [part for part in re.split(r'(\s+)', chunk) if part]
    segments: List[str] = []
    current = ""

    for part in parts:
        if part.isspace():
            if current and not current.endswith(" "):
                current += " "
            continue

        candidate = f"{current}{part}" if current else part
        if len(candidate.strip()) <= max_length:
            current = candidate
            continue

        if current.strip():
            segments.append(current.strip())
            current = ""

        if len(part) <= max_length:
            current = part
            continue

        remaining = part
        while len(remaining) > max_length:
            segments.append(remaining[:max_length])
            remaining = remaining[max_length:]
        current = remaining

    if current.strip():
        segments.append(current.strip())

    return segments


def _merge_short_segments(segments: List[str], max_length: int, min_length: int) -> List[str]:
    """合并过短分段，避免发出太碎的消息。"""
    merged: List[str] = []
    i = 0

    while i < len(segments):
        current = segments[i].strip()
        if not current:
            i += 1
            continue

        if len(current) < min_length and i < len(segments) - 1:
            next_segment = segments[i + 1].strip()
            separator = "" if current[-1] in SENTENCE_ENDINGS else " "
            combined = f"{current}{separator}{next_segment}".strip()
            if len(combined) <= max_length:
                merged.append(combined)
                i += 2
                continue

        if len(current) < min_length and merged:
            separator = "" if merged[-1][-1] in SENTENCE_ENDINGS else " "
            combined = f"{merged[-1]}{separator}{current}".strip()
            if len(combined) <= max_length:
                merged[-1] = combined
                i += 1
                continue

        merged.append(current)
        i += 1

    return merged


def split_text_by_sentences(text: str, max_length: int = 100, min_length: int = 5) -> List[str]:
    """
    按句子分割文本，确保每段不超过最大长度
    
    Args:
        text: 原始文本
        max_length: 每段最大长度
        min_length: 每段最小长度（低于此长度的段将被忽略）
        
    Returns:
        分割后的文本列表
    """
    text = text.strip()
    if not text:
        return []

    sentence_chunks = _split_sentence_chunks(text)
    segments: List[str] = []

    for chunk in sentence_chunks:
        if len(chunk) <= max_length:
            segments.append(chunk)
        else:
            segments.extend(_split_chunk_by_spaces(chunk, max_length))

    if not segments:
        segments = _split_chunk_by_spaces(text, max_length)

    return _merge_short_segments(segments, max_length, min_length)


def split_text_by_length(text: str, max_length: int = 100) -> List[str]:
    """
    按固定长度分割文本
    
    Args:
        text: 原始文本
        max_length: 每段最大长度
        
    Returns:
        分割后的文本列表
    """
    if len(text) <= max_length:
        return [text]
    
    segments = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = start + max_length
        if end >= text_length:
            segments.append(text[start:])
            break
        
        # 尝试在标点符号处分割
        last_punctuation = max(
            text.rfind('。', start, end),
            text.rfind('！', start, end),
            text.rfind('？', start, end),
            text.rfind('.', start, end),
            text.rfind('!', start, end),
            text.rfind('?', start, end),
            text.rfind('，', start, end),
            text.rfind(',', start, end),
            text.rfind(';', start, end),
            text.rfind('；', start, end),
            text.rfind(' ', start, end),
            text.rfind('\n', start, end)
        )
        
        if last_punctuation > start and last_punctuation - start > max_length * 0.5:
            end = last_punctuation + 1
        
        segments.append(text[start:end].strip())
        start = end
    
    return segments


def smart_split_text(text: str, max_length: int = 100, min_length: int = 5, strategy: str = 'sentence') -> List[str]:
    """
    智能文本分割
    
    Args:
        text: 原始文本
        max_length: 每段最大长度
        min_length: 每段最小长度
        strategy: 分割策略，'sentence' 或 'length'
        
    Returns:
        分割后的文本列表
    """
    # 保护图片URL不被分割
    text = protect_image_urls(text)
    
    if strategy == 'sentence':
        return split_text_by_sentences(text, max_length, min_length)
    elif strategy == 'length':
        return split_text_by_length(text, max_length)
    else:
        raise ValueError(f"不支持的策略: {strategy}")


def protect_image_urls(text: str) -> str:
    """
    保护文本中的图片URL，用占位符替换，避免被分割算法破坏
    
    Args:
        text: 包含图片URL的文本
        
    Returns:
        替换后的文本
    """
    import re
    
    # 匹配Markdown格式的图片: ![alt](url) 或 [image](url)
    image_pattern = r'(\[([^\]]*)\]\((https?://[^\s)]+)\))'
    
    # 找到所有图片URL并替换为占位符
    protected_urls = []
    placeholder_counter = 0
    
    def replace_with_placeholder(match):
        nonlocal placeholder_counter
        placeholder = f"__IMAGE_PLACEHOLDER_{placeholder_counter}__"
        placeholder_counter += 1
        protected_urls.append((placeholder, match.group(0)))
        return placeholder
    
    # 替换图片URL
    protected_text = re.sub(image_pattern, replace_with_placeholder, text)
    
    # 恢复图片URL（确保完整URL不被分割）
    for placeholder, original_url in protected_urls:
        # 检查占位符是否被分割
        if placeholder in protected_text:
            protected_text = protected_text.replace(placeholder, original_url)
    
    return protected_text
