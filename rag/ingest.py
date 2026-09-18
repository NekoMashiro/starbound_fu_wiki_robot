#!/usr/bin/env python3
"""
ingest.py — 将知识库导入 ChromaDB 向量数据库（支持增量更新）

读取 knowledge_base/ 下的实体 JSON 和 Wiki Markdown，
调用智谱 embedding-3 向量化，存入 ChromaDB。

增量模式（默认）：基于内容哈希，只处理新增/修改/删除的文档。
全量模式（--reset）：清空后重新导入全部。

用法:
    cd rag
    python ingest.py                    # 增量更新（推荐）
    python ingest.py --reset            # 清空后重新导入
    python ingest.py --limit 100        # 仅导入前 100 条（测试用）
    python ingest.py --dry-run          # 只计算差异，不实际执行
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import chromadb

from config import (
    KNOWLEDGE_BASE_DIR, CHROMA_DB_DIR, SKIP_ENTRY_COMPLETENESS,
    BM25_CACHE_PATH, SEARCH_CORPUS_PATH, INDEX_JSONL,
)
from embedding import get_embeddings

_WIKI_HEADING_RE = re.compile(r'^(#{2,3})\s+(.+)$', re.M)
_SLUG_RE = re.compile(r'[^\w\u4e00-\u9fff]+', re.UNICODE)

COLLECTION_NAME = 'fu_knowledge_base'
BATCH_SIZE = 32
HASH_INDEX_PATH = Path(__file__).parent / 'doc_hashes.json'


def _content_hash(embed_text: str, content_snippet: str) -> str:
    """计算文档的复合哈希：embed_text 决定向量，content 决定存储内容。"""
    # 两部分拼接：embed hash + content hash
    eh = hashlib.md5(embed_text.encode('utf-8')).hexdigest()[:16]
    ch = hashlib.md5(content_snippet.encode('utf-8')).hexdigest()[:16]
    return f"{eh}:{ch}"


def _split_hash(h: str) -> tuple[str, str]:
    """拆分复合哈希为 (embed_hash, content_hash)。"""
    parts = h.split(':', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return h, h  # 兼容旧格式


def _resolve_id(entity_id: str, names: dict[str, tuple[str, str]]) -> str:
    if entity_id in names:
        return entity_id
    for alt in (
        f'{entity_id}ore',
        entity_id.replace('_mod_', '_ore_'),
        entity_id.replace('_mod_', '_'),
    ):
        if alt in names:
            return alt
    return entity_id


def _label(entity_id: str, names: dict[str, tuple[str, str]]) -> str:
    eid = _resolve_id(entity_id, names)
    zh, en = names.get(eid, ('', ''))
    if zh and en:
        return f'{zh}({en})'
    return zh or en or entity_id


def load_name_index(kb_dir: Path) -> dict[str, tuple[str, str]]:
    """entity_id → (name_zh, name_en)，含 D 级，供 embed 反查。"""
    names: dict[str, tuple[str, str]] = {}
    path = kb_dir / 'index.jsonl'
    if not path.exists() and INDEX_JSONL.exists():
        path = INDEX_JSONL
    if not path.exists():
        return names
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            eid = row.get('entity_id') or ''
            if eid:
                names[eid] = (row.get('name_zh') or '', row.get('name_en') or '')
    return names


def build_relation_index(entities: list[dict]) -> dict[str, list[str]]:
    """pool 名 / 怪物 id → 会掉落的物品 id（来自已入库实体的 drop_sources）。"""
    pool_to_items: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, set[str]] = defaultdict(set)
    for entity in entities:
        item_id = entity.get('entity_id') or ''
        if not item_id:
            continue
        drops = entity.get('drop_sources') or {}
        for key, data in drops.items():
            if key == 'total_pools' or not isinstance(data, dict):
                continue
            for src in data.get('top') or []:
                pool = src.get('pool') or ''
                if pool and item_id not in seen[pool]:
                    seen[pool].add(item_id)
                    pool_to_items[pool].append(item_id)
                for mid in src.get('monsters') or []:
                    if mid and item_id not in seen[mid]:
                        seen[mid].add(item_id)
                        pool_to_items[mid].append(item_id)
    return pool_to_items


def _wiki_slug(heading: str) -> str:
    slug = _SLUG_RE.sub('-', heading.strip()).strip('-')
    return (slug or 'section')[:48]


def split_wiki_sections(content: str) -> list[tuple[str, str]]:
    """按 ## / ### 切成 (标题, 正文)。无标题的开头归为引言。"""
    matches = list(_WIKI_HEADING_RE.finditer(content))
    if not matches:
        return []
    sections: list[tuple[str, str]] = []
    intro = content[:matches[0].start()].strip()
    if intro:
        sections.append(('引言', intro))
    for i, m in enumerate(matches):
        heading = m.group(2).strip()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[m.end():end].strip()
        if heading:
            sections.append((heading, body))
    return sections


def write_search_corpus(docs: list[dict]):
    """把每篇的 embed_text 写成 BM25 语料，不依赖 Chroma 是否已更新。"""
    with open(SEARCH_CORPUS_PATH, 'w', encoding='utf-8') as f:
        for d in docs:
            f.write(json.dumps({
                'id': d['id'],
                'search_text': d['embed_text'][:2000],
                'metadata': d['metadata'],
            }, ensure_ascii=False) + '\n')


def load_documents(kb_dir: Path, limit: int | None = None) -> list[dict]:
    """
    从 knowledge_base/ 加载所有文档。

    实体文档: 读取 JSON，生成结构化 embedding 文本
    Wiki 文档: 短页保持整页；长页按标题切块并保留父文档
    """
    names = load_name_index(kb_dir)
    entities: list[dict] = []

    entities_dir = kb_dir / 'entities'
    if entities_dir.exists():
        for type_dir in sorted(entities_dir.iterdir()):
            if not type_dir.is_dir():
                continue
            for fn in sorted(os.listdir(type_dir)):
                if not fn.endswith('.json'):
                    continue
                try:
                    with open(type_dir / fn, encoding='utf-8') as f:
                        entity = json.load(f)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if not isinstance(entity, dict):
                    continue
                if entity.get('entry_completeness', 'D') in SKIP_ENTRY_COMPLETENESS:
                    continue
                entities.append(entity)

    relations = build_relation_index(entities)
    docs = []

    for entity in entities:
        doc_id = f"{entity.get('entity_type', 'unknown')}:{entity.get('entity_id', '')}"
        embed_text = build_entity_embed_text(entity, names, relations)
        full_content = json.dumps(entity, ensure_ascii=False, indent=2)
        docs.append({
            'id': doc_id,
            'embed_text': embed_text,
            'content': full_content,
            'hash': _content_hash(embed_text, full_content),
            'metadata': {
                'entity_id': entity.get('entity_id', ''),
                'entity_type': entity.get('entity_type', ''),
                'name_en': entity.get('name_en', ''),
                'name_zh': entity.get('name_zh', ''),
                'source_mod': entity.get('source_mod', ''),
                'entry_completeness': entity.get('entry_completeness', ''),
                'doc_kind': 'entity',
            },
        })
        if limit and len(docs) >= limit:
            return docs

    wiki_dir = kb_dir / 'wiki'
    if wiki_dir.exists():
        for mod_dir in sorted(wiki_dir.iterdir()):
            if not mod_dir.is_dir():
                continue
            for md_file in sorted(mod_dir.glob('*.md')):
                try:
                    content = md_file.read_text(encoding='utf-8')
                except UnicodeDecodeError:
                    continue

                title = md_file.stem.replace('_', ' ')
                parent_id = f"wiki:{mod_dir.name}:{md_file.stem}"
                sections = split_wiki_sections(content)
                long_wiki = len(content) > 1500 and len(sections) >= 2
                name_zh = title if re.search(r'[\u4e00-\u9fff]', title) else ''
                name_en = '' if name_zh else title

                if long_wiki:
                    toc = '；'.join(h for h, _ in sections[:20])
                    parent_embed = f"{title}\n章节: {toc}\n{content[:1500]}"
                else:
                    parent_embed = f"{title}\n{content[:3000]}"

                docs.append({
                    'id': parent_id,
                    'embed_text': parent_embed,
                    'content': content,
                    'hash': _content_hash(parent_embed, content[:5000]),
                    'metadata': {
                        'entity_id': md_file.stem,
                        'entity_type': 'wiki',
                        'name_en': name_en,
                        'name_zh': name_zh,
                        'source_mod': mod_dir.name,
                        'entry_completeness': 'S',
                        'doc_kind': 'wiki',
                    },
                })
                if limit and len(docs) >= limit:
                    return docs

                if long_wiki:
                    for heading, body in sections:
                        if len(body) < 40:
                            continue
                        chunk_id = f"{parent_id}#{_wiki_slug(heading)}"
                        embed_text = f"{title} {heading}\n{body[:2000]}"
                        chunk_content = f"# {title}\n\n## {heading}\n\n{body}"
                        docs.append({
                            'id': chunk_id,
                            'embed_text': embed_text,
                            'content': chunk_content,
                            'hash': _content_hash(embed_text, chunk_content[:5000]),
                            'metadata': {
                                'entity_id': md_file.stem,
                                'entity_type': 'wiki',
                                'name_en': '' if name_zh else f'{title} / {heading}',
                                'name_zh': f'{title} / {heading}' if name_zh else '',
                                'source_mod': mod_dir.name,
                                'entry_completeness': 'S',
                                'doc_kind': 'wiki_chunk',
                                'parent_id': parent_id,
                            },
                        })
                        if limit and len(docs) >= limit:
                            return docs

    return docs


def build_entity_embed_text(
    entity: dict,
    names: dict[str, tuple[str, str]] | None = None,
    relations: dict[str, list[str]] | None = None,
) -> str:
    """
    构建实体的 embedding 文本。

    将关键字段拼接为可检索的文本，确保中英文名称、描述、
    标签、配方材料、掉落物、生态等都能被向量检索命中。
    """
    names = names or {}
    relations = relations or {}
    parts = []

    name_en = entity.get('name_en', '')
    name_zh = entity.get('name_zh', '')
    entity_id = entity.get('entity_id', '')
    if name_en:
        parts.append(name_en)
    if name_zh:
        parts.append(name_zh)
    if entity_id:
        parts.append(entity_id)

    etype = entity.get('entity_type', '')
    mod = entity.get('source_mod', '')
    if etype:
        parts.append(f"[{etype}]")
    if mod:
        parts.append(f"mod: {mod}")

    desc_en = entity.get('description_en', '')
    desc_zh = entity.get('description_zh', '')
    if desc_en:
        parts.append(desc_en)
    if desc_zh:
        parts.append(desc_zh)

    tags = entity.get('tags', [])
    if tags:
        parts.append(f"tags: {', '.join(tags)}")
    cat = entity.get('category', '')
    rarity = entity.get('rarity', '')
    if cat:
        parts.append(f"category: {cat}")
    if rarity:
        parts.append(f"rarity: {rarity}")

    weapon_parts = []
    if entity.get('elementalType'):
        weapon_parts.append(f"element:{entity['elementalType']}")
    if entity.get('baseDps'):
        weapon_parts.append(f"DPS:{entity['baseDps']}")
    if entity.get('level'):
        weapon_parts.append(f"lv{entity['level']}")
    if entity.get('primaryAbilityType'):
        weapon_parts.append(entity['primaryAbilityType'])
    if entity.get('altAbilityType'):
        weapon_parts.append(entity['altAbilityType'])
    if weapon_parts:
        parts.append(f"weapon: {', '.join(weapon_parts)}")

    recipes = entity.get('recipes_output', [])
    if recipes:
        recipe_strs = []
        for r in recipes[:10]:
            inputs = ', '.join(
                f"{_label(i['item'], names)}x{i['count']}"
                for i in r.get('inputs', [])
            )
            station = r.get('station_zh', '') or r.get('station', '')
            recipe_strs.append(f"{inputs} @ {station}")
        parts.append("制作方式: " + '; '.join(recipe_strs))

    usage = entity.get('recipes_input', {})
    if usage:
        total = usage.get('total', 0)
        examples = []
        for info in (usage.get('by_category') or {}).values():
            if isinstance(info, dict):
                for ex in info.get('examples') or []:
                    examples.append(_label(ex, names))
        extra = f", 例如: {', '.join(examples[:8])}" if examples else ''
        cats = list((usage.get('by_category') or {}).keys())
        parts.append(f"用途: {total}个配方, 类别: {', '.join(cats[:5])}{extra}")

    drops = entity.get('drop_sources', {})
    if drops:
        bits = [f"{drops.get('total_pools', 0)}个pool"]
        for cat in ('monster_drops', 'chest_loot', 'quest_rewards', 'boss_mission', 'other'):
            block = drops.get(cat)
            if not isinstance(block, dict):
                continue
            labels = []
            for src in (block.get('top') or [])[:4]:
                for mid in src.get('monsters') or []:
                    labels.append(_label(mid, names))
                pool = src.get('pool') or ''
                if pool and not src.get('monsters'):
                    labels.append(pool)
            if labels:
                bits.append(f"{cat}: {', '.join(labels[:8])}")
        parts.append("掉落来源: " + '；'.join(bits))

    def _id_labels(raw, limit=24) -> list[str]:
        ids = []
        for row in raw or []:
            if isinstance(row, str):
                ids.append(row)
            elif isinstance(row, dict):
                ids.append(row.get('item') or row.get('input') or row.get('output') or row.get('biome') or '')
        ids = [i for i in ids if i]
        labels = [_label(i, names) for i in ids[:limit]]
        if len(ids) > limit:
            labels.append(f'等{len(ids)}种')
        return labels

    subject = name_zh or name_en or entity_id
    extracted = _id_labels(entity.get('extracted_from'))
    if extracted:
        parts.append(
            f"可通过萃取获得{subject} 萃取获得{subject}的原料 提取 萃取实验室: "
            + ', '.join(extracted)
        )

    extracts_into = _id_labels(entity.get('extracts_into'))
    if extracts_into:
        parts.append("可萃取成: " + ', '.join(extracts_into))

    for key, verb in (
        ('centrifuged_from', '离心获得 离心机'),
        ('sifted_from', '筛粉获得 筛粉机'),
        ('crushed_from', '碎岩获得 碎岩机 破岩机'),
        ('centrifuges_into', '可离心成'),
        ('sifts_into', '可筛成'),
        ('crushes_into', '可粉碎成'),
    ):
        labels = _id_labels(entity.get(key))
        if labels:
            parts.append(f"{verb}: " + ', '.join(labels))

    condensed = entity.get('condensed_on')
    if isinstance(condensed, dict):
        condensed = [b.get('biome') for b in (condensed.get('biomes') or []) if b.get('biome')]
    condensed_labels = _id_labels(condensed)
    if condensed_labels:
        parts.append("空气冷凝器 大气提取 冷凝获得: " + ', '.join(condensed_labels))

    condenser_out = entity.get('condenser_outputs') or {}
    if isinstance(condenser_out, dict) and (condenser_out.get('common') or condenser_out.get('uncommon')):
        common = ', '.join(_label(i, names) for i in (condenser_out.get('common') or [])[:8])
        parts.append(f"空气冷凝器产出: {common}")

    atmos_machine = entity.get('atmosphere_outputs') or {}
    if isinstance(atmos_machine, dict) and atmos_machine.get('examples'):
        bits = [
            f"{ex.get('biome_zh') or ex.get('biome')}"
            for ex in atmos_machine['examples'][:8]
        ]
        parts.append("空气冷凝器按星球出货: " + ', '.join(bits))

    biomes = entity.get('biomes', [])
    if biomes:
        biome_labels = []
        for b in biomes[:10]:
            bid = b['biome'] if isinstance(b, dict) else str(b)
            biome_labels.append(_label(bid, names))
        parts.append(f"生态: {', '.join(biome_labels)}")

    wiki_ref = entity.get('wiki_ref', '')
    if wiki_ref:
        parts.append(f"wiki: {wiki_ref}")

    if etype == 'monster':
        drop_ids: list[str] = []
        seen_drop = set()
        for key in (
            entity_id,
            entity.get('drop_pool_default') or '',
            entity.get('drop_pool_hunting') or '',
        ):
            for item_id in relations.get(key, []):
                if item_id not in seen_drop:
                    seen_drop.add(item_id)
                    drop_ids.append(item_id)
        if drop_ids:
            parts.append("掉落物: " + ', '.join(_label(i, names) for i in drop_ids[:12]))
        dp = entity.get('drop_pool_default', '')
        if dp:
            parts.append(f"掉落池: {dp}")

    if etype == 'biome':
        fn = entity.get('friendly_name', '')
        fn_zh = entity.get('friendly_name_zh', '')
        if fn:
            parts.append(fn)
        if fn_zh:
            parts.append(fn_zh)
        ores = entity.get('ores', [])
        if ores:
            ore_names = [_label(o['ore'], names) for o in ores[:12]]
            parts.append(f"矿石: {', '.join(ore_names)}")
        monsters = entity.get('monsters', [])
        if monsters:
            parts.append(
                "怪物: " + ', '.join(_label(m, names) for m in monsters[:10])
            )

    return '\n'.join(parts)


# ─────────────────────────────────────────────
# 增量更新核心
# ─────────────────────────────────────────────

def load_hash_index() -> dict[str, str]:
    """加载上次的文档哈希索引。"""
    if HASH_INDEX_PATH.exists():
        with open(HASH_INDEX_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_hash_index(index: dict[str, str]):
    """保存文档哈希索引。"""
    with open(HASH_INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False)


def compute_diff(docs: list[dict], old_hashes: dict[str, str]) -> dict:
    """
    计算新旧文档的差异，区分三种更新模式：
    - re_embed: embed_text 变了，需要重新计算向量（贵）
    - content_only: embed_text 没变但内容变了，只更新文档内容（免费）
    """
    new_hashes = {d['id']: d['hash'] for d in docs}
    new_ids = set(new_hashes.keys())
    old_ids = set(old_hashes.keys())

    add_ids = new_ids - old_ids
    delete_ids = old_ids - new_ids
    common_ids = new_ids & old_ids

    re_embed_ids = set()
    content_only_ids = set()
    for did in common_ids:
        if new_hashes[did] == old_hashes[did]:
            continue
        new_eh, new_ch = _split_hash(new_hashes[did])
        old_eh, old_ch = _split_hash(old_hashes[did])
        if new_eh != old_eh:
            re_embed_ids.add(did)  # embed_text 变了，需要重新向量化
        else:
            content_only_ids.add(did)  # 只有内容变了，更新文档即可

    unchanged = len(common_ids) - len(re_embed_ids) - len(content_only_ids)
    doc_by_id = {d['id']: d for d in docs}

    return {
        'add': [doc_by_id[did] for did in add_ids],
        're_embed': [doc_by_id[did] for did in re_embed_ids],
        'content_only': [doc_by_id[did] for did in content_only_ids],
        'delete': sorted(delete_ids),
        'unchanged': unchanged,
        'new_hashes': new_hashes,
    }


def _embed_and_upsert(collection, docs: list[dict], label: str):
    """批量 embed + upsert 文档到 ChromaDB。"""
    total = len(docs)
    if total == 0:
        return

    start_time = time.time()
    for i in range(0, total, BATCH_SIZE):
        batch = docs[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        texts = [d['embed_text'] for d in batch]
        try:
            embeddings = get_embeddings(texts)
        except Exception as e:
            print(f'\n  ❌ Embedding API 失败: {e}')
            print(f'     已完成 {i}/{total}，可重新运行继续')
            sys.exit(1)

        ids = [d['id'] for d in batch]
        metadatas = [d['metadata'] for d in batch]
        documents = [d['content'][:30000] for d in batch]

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )

        elapsed = time.time() - start_time
        rate = (i + len(batch)) / elapsed if elapsed > 0 else 0
        eta = (total - i - len(batch)) / rate if rate > 0 else 0
        print(f'\r  ⏳ {label} [{batch_num}/{total_batches}] '
              f'{i + len(batch)}/{total} '
              f'({elapsed:.0f}s, ~{eta:.0f}s 剩余)', end='', flush=True)

    elapsed = time.time() - start_time
    print(f'\r  ✅ {label}: {total} 条, {elapsed:.1f}s'
          f'{" " * 30}')


def ingest(limit: int | None = None, reset: bool = False, dry_run: bool = False):
    """执行导入。"""
    if not KNOWLEDGE_BASE_DIR.exists():
        print(f'❌ 知识库目录不存在: {KNOWLEDGE_BASE_DIR}')
        print('   请先运行 python build_game_data.py 构建知识库')
        sys.exit(1)

    # 加载文档
    t0 = time.time()
    print(f'📖 加载知识库: {KNOWLEDGE_BASE_DIR}')
    docs = load_documents(KNOWLEDGE_BASE_DIR, limit)

    entity_count = sum(1 for d in docs if d['metadata']['doc_kind'] == 'entity')
    wiki_count = sum(1 for d in docs if d['metadata']['doc_kind'] == 'wiki')
    print(f'   共 {len(docs)} 条（实体 {entity_count} + Wiki {wiki_count}）'
          f'，已跳过完善度 D 的词条，加载耗时 {time.time()-t0:.1f}s')

    # 初始化 ChromaDB
    CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))

    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            print('🗑️  已清空旧数据和哈希索引')
        except Exception:
            pass
        if HASH_INDEX_PATH.exists():
            HASH_INDEX_PATH.unlink()

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={'hnsw:space': 'cosine'},
    )
    existing_count = collection.count()

    if reset:
        # ── 全量导入 ──
        print(f'\n🔄 全量导入 {len(docs)} 条文档...')

        if dry_run:
            print(f'   [dry-run] 将导入 {len(docs)} 条，跳过')
            return

        _embed_and_upsert(collection, docs, '导入')

        new_hashes = {d['id']: d['hash'] for d in docs}
        save_hash_index(new_hashes)
        write_search_corpus(docs)
    else:
        # ── 增量更新 ──
        old_hashes = load_hash_index()

        if not old_hashes:
            print(f'\n⚠️  首次运行，无历史哈希，将执行全量导入')
            print(f'   （如需全量重建，请使用 --reset）')

            if dry_run:
                print(f'   [dry-run] 将导入 {len(docs)} 条，跳过')
                return

            _embed_and_upsert(collection, docs, '首次导入')
            new_hashes = {d['id']: d['hash'] for d in docs}
            save_hash_index(new_hashes)
            write_search_corpus(docs)
        else:
            diff = compute_diff(docs, old_hashes)

            n_add = len(diff['add'])
            n_re_embed = len(diff['re_embed'])
            n_content = len(diff['content_only'])
            n_delete = len(diff['delete'])
            n_unchanged = diff['unchanged']

            print(f'\n📊 增量分析 (对比 {len(old_hashes)} → {len(docs)} 条):')
            print(f'   ✚ 新增: {n_add}')
            print(f'   ✎ 向量+内容更新: {n_re_embed} (需重新 embed)')
            print(f'   📄 仅内容更新: {n_content} (免费)')
            print(f'   ✖ 删除: {n_delete}')
            print(f'   ═ 不变: {n_unchanged}')

            need_embed = n_add + n_re_embed
            total_changes = need_embed + n_content + n_delete
            if total_changes == 0:
                print(f'\n✅ 知识库无变化，无需更新！')
                write_search_corpus(docs)
                return

            if need_embed > 0:
                est_time = need_embed / BATCH_SIZE * 0.7
                print(f'\n   需要调用 Embedding API: {need_embed} 次')
                print(f'   预计耗时: ~{est_time:.0f}s'
                      f'（全量需 ~{len(docs) / BATCH_SIZE * 0.7:.0f}s，'
                      f'节省 {(1 - need_embed / max(len(docs), 1)) * 100:.0f}%）')

            if dry_run:
                print(f'\n   [dry-run] 不执行实际操作')
                if n_add > 0:
                    print(f'   新增示例: {[d["id"] for d in diff["add"][:5]]}')
                if n_re_embed > 0:
                    print(f'   重embed示例: {[d["id"] for d in diff["re_embed"][:5]]}')
                if n_content > 0:
                    print(f'   内容更新示例: {[d["id"] for d in diff["content_only"][:5]]}')
                if n_delete > 0:
                    print(f'   删除示例: {diff["delete"][:5]}')
                return

            # 执行删除
            if n_delete > 0:
                print(f'\n🗑️  删除 {n_delete} 条过期文档...')
                for i in range(0, n_delete, 500):
                    batch_ids = diff['delete'][i:i + 500]
                    collection.delete(ids=batch_ids)
                print(f'  ✅ 已删除 {n_delete} 条')

            # 执行新增（需要 embed）
            if n_add > 0:
                print(f'\n📥 新增 {n_add} 条文档...')
                _embed_and_upsert(collection, diff['add'], '新增')

            # 执行向量更新（需要 embed）
            if n_re_embed > 0:
                print(f'\n📝 重新向量化 {n_re_embed} 条文档...')
                _embed_and_upsert(collection, diff['re_embed'], '向量更新')

            # 执行仅内容更新（不需要重新调用 Embedding API）
            if n_content > 0:
                print(f'\n📄 更新 {n_content} 条文档内容（无需重新 embed）...')
                t_content = time.time()
                for i in range(0, n_content, 500):
                    batch = diff['content_only'][i:i + 500]
                    batch_ids = [d['id'] for d in batch]
                    # 取回原有的 embeddings，避免 ChromaDB 用内置模型重新编码
                    existing = collection.get(ids=batch_ids, include=['embeddings'])
                    collection.update(
                        ids=batch_ids,
                        embeddings=existing['embeddings'],
                        metadatas=[d['metadata'] for d in batch],
                        documents=[d['content'][:30000] for d in batch],
                    )
                print(f'  ✅ 内容更新完成 ({time.time() - t_content:.1f}s)')

            # 保存新哈希
            save_hash_index(diff['new_hashes'])
            write_search_corpus(docs)

    # 知识库变了，让下次启动重建 BM25
    if BM25_CACHE_PATH.exists():
        BM25_CACHE_PATH.unlink()

    # 汇总
    final_count = collection.count()
    total_time = time.time() - t0
    print(f'\n{"═" * 50}')
    print(f'  ✅ 完成! ChromaDB: {final_count} 条, 耗时 {total_time:.1f}s')
    print(f'  数据库: {CHROMA_DB_DIR}')
    print(f'  哈希索引: {HASH_INDEX_PATH}')
    print(f'  BM25 语料: {SEARCH_CORPUS_PATH}')
    print(f'{"═" * 50}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='将知识库导入 ChromaDB（支持增量更新）')
    parser.add_argument('--limit', type=int, default=None,
                        help='仅导入前 N 条（测试用）')
    parser.add_argument('--reset', action='store_true',
                        help='清空后重新导入（全量模式）')
    parser.add_argument('--dry-run', action='store_true',
                        help='只计算差异，不实际执行')
    args = parser.parse_args()
    ingest(limit=args.limit, reset=args.reset, dry_run=args.dry_run)
