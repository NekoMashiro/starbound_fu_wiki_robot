"""
qq_format.py — 把 RAG 结果收成 QQ Markdown。

不发模型名、不发外链。群聊整条发送；单聊流式用同一套正文。
不依赖 query.py，避免 --echo 启动时加载 Chroma。
"""

import re

_COLOR_CODE_RE = re.compile(r'\^[a-zA-Z#0-9]+;')
_THINK_RE = re.compile(r'<think>.*?</think>', re.DOTALL)

EMPTY_TEXT = '请输入问题。'
BUSY_TEXT = '当前查询较多，请稍后再试。'
IN_FLIGHT_TEXT = '上一条还在生成，请稍候。'
ERROR_TEXT = '查询失败，请稍后再试。'

CHUNK_SIZE = 1800
MAX_ANSWER_CHUNKS = 5
MAX_SOURCES = 3
STREAM_MAX_CHARS = 3500


def strip_color_codes(text: str) -> str:
    return _COLOR_CODE_RE.sub('', text) if text else text


def visible_markdown(text: str) -> str:
    """去掉思考块和游戏色码，得到可下发的 Markdown。"""
    text = _THINK_RE.sub('', text or '')
    return strip_color_codes(text).strip()


def _source_label(source: dict) -> str:
    name_en = strip_color_codes(source.get('name_en', ''))
    name_zh = strip_color_codes(source.get('name_zh', ''))
    etype = source.get('entity_type', '')

    if name_zh and name_en:
        label = f'{name_zh} ({name_en})'
    else:
        label = name_zh or name_en or '?'
    if etype:
        label = f'[{etype}] {label}'
    return label


def append_sources(answer: str, sources: list) -> str:
    answer = visible_markdown(answer)
    if not answer:
        answer = ERROR_TEXT
    labels = [_source_label(s) for s in (sources or [])[:MAX_SOURCES]]
    if labels:
        lines = '\n'.join(f'- {x}' for x in labels)
        answer = f'{answer}\n\n***\n参考\n{lines}'
    return answer


def _split_chunks(text: str, size: int = CHUNK_SIZE) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    chunks = []
    rest = text
    while rest:
        if len(rest) <= size:
            chunks.append(rest)
            break
        cut = rest.rfind('\n', 0, size)
        if cut < size // 3:
            cut = rest.rfind('。', 0, size)
        if cut < size // 3:
            cut = size
        piece = rest[:cut].strip()
        if piece:
            chunks.append(piece)
        rest = rest[cut:].lstrip('\n')
    return chunks


def format_markdown_chunks(result: dict) -> list[str]:
    """群聊：完整 Markdown，超长拆成最多 5 条。"""
    text = append_sources(result.get('answer') or '', result.get('sources') or [])
    chunks = _split_chunks(text)
    if not chunks:
        return [ERROR_TEXT]
    if len(chunks) > MAX_ANSWER_CHUNKS:
        chunks = chunks[:MAX_ANSWER_CHUNKS]
        chunks[-1] = chunks[-1].rstrip() + '\n\n…(已截断)'
    return chunks
