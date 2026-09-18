"""
translator.py — FU 游戏术语中英互译

功能:
1. 查询增强: 用户中文问题 → 自动补充英文关键词，提升检索命中率
2. 结果翻译: LLM 输出中的英文物品 ID / 名称 → 替换为中文

数据来源: knowledge_base/index.jsonl
"""

import json
import re
from pathlib import Path

from config import INDEX_JSONL

_COLOR_CODE_RE = re.compile(r'\^[a-zA-Z#0-9]+;')


def _clean(text: str) -> str:
    """去除颜色代码并 strip。"""
    return _COLOR_CODE_RE.sub('', text).strip() if text else ''


class Translator:
    """中英互译词典，基于知识库数据构建。"""

    def __init__(self, jsonl_path: Path | None = None):
        self._jsonl_path = jsonl_path or INDEX_JSONL

        # 核心词典
        self.id_to_en: dict[str, str] = {}      # densiniumbar → Densinium Bar
        self.id_to_zh: dict[str, str] = {}      # densiniumbar → 超致密锭
        self.zh_to_en: dict[str, str] = {}      # 超致密锭 → Densinium Bar
        self.zh_to_id: dict[str, str] = {}      # 超致密锭 → densiniumbar
        self.en_to_zh: dict[str, str] = {}      # densinium bar → 超致密锭 (小写key)
        self.zh_entries: dict[str, list[dict]] = {}  # 中文名 → 候选实体

        self._build()

    def _build(self):
        """从 index.jsonl 构建词典。"""
        if not self._jsonl_path.exists():
            print('⚠️  翻译词典: index.jsonl 不存在')
            return

        with open(self._jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                doc = json.loads(line)

                doc_id = doc.get('entity_id', '').strip()
                title_en = _clean(doc.get('name_en', ''))
                title_zh = _clean(doc.get('name_zh', ''))

                if not doc_id:
                    continue

                if title_en:
                    self.id_to_en[doc_id] = title_en
                if title_zh:
                    self.id_to_zh[doc_id] = title_zh

                if title_zh:
                    self.zh_entries.setdefault(title_zh, []).append({
                        'entity_id': doc_id,
                        'entity_type': doc.get('entity_type', ''),
                        'name_en': title_en,
                        'name_zh': title_zh,
                    })
                if title_zh and title_en:
                    self.zh_to_en[title_zh] = title_en
                    self.zh_to_id[title_zh] = doc_id
                    self.en_to_zh[title_en.lower()] = title_zh

        print(f'📖 翻译词典已加载: {len(self.id_to_zh)} 条中英对照')

    def _usable_zh_name(self, zh_name: str) -> bool:
        """双字以上照常匹配；单字仅当唯一指向 item/liquid（如「油」）。"""
        if len(zh_name) >= 2:
            return True
        if len(zh_name) != 1 or not ('\u4e00' <= zh_name <= '\u9fff'):
            return False
        entries = [
            e for e in (self.zh_entries.get(zh_name) or [])
            if e.get('entity_type') in ('item', 'liquid')
        ]
        return len(entries) == 1

    def mentioned_entities(self, query: str) -> list[dict]:
        """从问句里抽出已点名的实体（最长匹配，不重叠）。"""
        if not query:
            return []
        sorted_zh = sorted(
            (n for n in self.zh_entries if self._usable_zh_name(n)),
            key=len,
            reverse=True,
        )
        matched_positions = set()
        found = []
        seen_ids = set()
        for zh_name in sorted_zh:
            pos = query.find(zh_name)
            if pos == -1:
                continue
            name_range = set(range(pos, pos + len(zh_name)))
            if name_range & matched_positions:
                continue
            matched_positions |= name_range
            entries = self.zh_entries.get(zh_name) or []
            if len(zh_name) == 1:
                entries = [e for e in entries if e.get('entity_type') in ('item', 'liquid')]
            prefer = [e for e in entries if e.get('entity_type') in ('item', 'liquid')]
            chosen = (prefer or entries)[:1]
            for e in chosen:
                key = f"{e.get('entity_type')}:{e.get('entity_id')}"
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                found.append(e)
        return found

    def enhance_query(self, query: str) -> str:
        """
        查询增强: 在中文查询后附加匹配到的英文关键词。

        例: "量子萃取器怎么做" → "量子萃取器怎么做 Quantum Extractor"
        """
        appended = []

        sorted_zh = sorted(
            (n for n in self.zh_to_en if self._usable_zh_name(n)),
            key=len,
            reverse=True,
        )
        matched_positions = set()

        for zh_name in sorted_zh:
            pos = query.find(zh_name)
            if pos == -1:
                continue
            name_range = set(range(pos, pos + len(zh_name)))
            if name_range & matched_positions:
                continue
            matched_positions |= name_range
            en_name = self.zh_to_en[zh_name]
            if en_name.lower() not in query.lower():
                appended.append(en_name)

        if appended:
            return query + ' ' + ' '.join(appended)
        return query

    def translate_id(self, item_id: str) -> str | None:
        """将物品内部ID翻译为中文名。"""
        return self.id_to_zh.get(item_id)

    def translate_en(self, en_name: str) -> str | None:
        """将英文显示名翻译为中文名。"""
        return self.en_to_zh.get(en_name.lower())

    def translate_output(self, text: str) -> str:
        """后处理 LLM 输出: 将英文物品 ID/名称翻译为 "中文名(English)" 格式。"""
        lines = text.split('\n')
        result = []
        for line in lines:
            result.append(self._translate_line(line))
        return '\n'.join(result)

    def _translate_line(self, line: str) -> str:
        """翻译单行文本中的物品 ID 和英文名。"""
        recipe_match = re.match(
            r'^(\s*[-*•]\s*\d+x\s+)([a-zA-Z][a-zA-Z0-9_:]+)(.*)$', line
        )
        if recipe_match:
            prefix, item_id, suffix = recipe_match.groups()
            zh = self.id_to_zh.get(item_id)
            en = self.id_to_en.get(item_id, item_id)
            if zh:
                return f'{prefix}{zh}({en}){suffix}'
            elif en != item_id:
                return f'{prefix}{en}{suffix}'

        output_match = re.match(
            r'^(\s*→\s*\d+x\s+)(.+)$', line
        )
        if output_match:
            prefix, item_name = output_match.groups()
            clean_name = _clean(item_name)
            zh = self.en_to_zh.get(clean_name.lower())
            if zh:
                return f'{prefix}{zh}({clean_name})'

        bench_match = re.match(
            r'^(\*\*工作台\*\*:\s*)(.+)$', line
        )
        if bench_match:
            prefix, bench_name = bench_match.groups()
            clean_bench = _clean(bench_name)
            zh = self.en_to_zh.get(clean_bench.lower())
            if zh:
                return f'{prefix}{zh}({clean_bench})'

        return line

    def build_translation_context(self, text: str, max_entries: int = 30) -> str:
        """
        为 LLM 构建翻译参考表。

        扫描上下文中的物品 ID，生成 "ID → 中文名(英文名)" 速查表。
        """
        entries = []
        seen = set()

        candidates = re.findall(r'\b([a-z][a-z0-9_]{3,})\b', text.lower())
        for candidate in candidates:
            if candidate in seen:
                continue
            zh = self.id_to_zh.get(candidate)
            en = self.id_to_en.get(candidate, candidate)
            if zh:
                seen.add(candidate)
                entries.append(f'{candidate} = {zh}({en})')
                if len(entries) >= max_entries:
                    break

        if not entries:
            return ''

        return '【物品翻译参考表】\n' + '\n'.join(entries)
