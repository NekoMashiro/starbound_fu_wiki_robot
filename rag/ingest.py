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
import sys
import time
from pathlib import Path

import chromadb

from config import KNOWLEDGE_BASE_DIR, CHROMA_DB_DIR, SKIP_QUALITY_TIERS, BM25_CACHE_PATH
from embedding import get_embeddings

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


def load_documents(kb_dir: Path, limit: int | None = None) -> list[dict]:
    """
    从 knowledge_base/ 加载所有文档。

    实体文档: 读取 JSON，生成结构化 embedding 文本
    Wiki 文档: 读取 Markdown 原文
    """
    docs = []

    # ── 实体文档 ──
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

                tier = entity.get('quality_tier', 'D')
                if tier in SKIP_QUALITY_TIERS:
                    continue

                doc_id = f"{entity.get('entity_type', 'unknown')}:{entity.get('entity_id', fn)}"
                embed_text = build_entity_embed_text(entity)
                full_content = json.dumps(entity, ensure_ascii=False, indent=2)

                docs.append({
                    'id': doc_id,
                    'embed_text': embed_text,
                    'content': full_content,
                    'hash': _content_hash(embed_text, full_content[:5000]),
                    'metadata': {
                        'entity_id': entity.get('entity_id', ''),
                        'entity_type': entity.get('entity_type', ''),
                        'name_en': entity.get('name_en', ''),
                        'name_zh': entity.get('name_zh', ''),
                        'source_mod': entity.get('source_mod', ''),
                        'quality_tier': tier,
                        'doc_kind': 'entity',
                    },
                })

                if limit and len(docs) >= limit:
                    return docs

    # ── Wiki 文档 ──
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
                doc_id = f"wiki:{mod_dir.name}:{md_file.stem}"
                embed_text = f"{title}\n{content[:3000]}"

                docs.append({
                    'id': doc_id,
                    'embed_text': embed_text,
                    'content': content,
                    'hash': _content_hash(embed_text, content[:5000]),
                    'metadata': {
                        'entity_id': md_file.stem,
                        'entity_type': 'wiki',
                        'name_en': title,
                        'name_zh': '',
                        'source_mod': mod_dir.name,
                        'quality_tier': 'S',
                        'doc_kind': 'wiki',
                    },
                })

                if limit and len(docs) >= limit:
                    return docs

    return docs


def build_entity_embed_text(entity: dict) -> str:
    """
    构建实体的 embedding 文本。

    将关键字段拼接为可检索的文本，确保中英文名称、描述、
    标签、配方材料等都能被向量检索命中。
    """
    parts = []

    # 名称（中英文，权重最高）
    name_en = entity.get('name_en', '')
    name_zh = entity.get('name_zh', '')
    entity_id = entity.get('entity_id', '')
    if name_en:
        parts.append(name_en)
    if name_zh:
        parts.append(name_zh)
    if entity_id:
        parts.append(entity_id)

    # 类型和 mod 来源
    etype = entity.get('entity_type', '')
    mod = entity.get('source_mod', '')
    if etype:
        parts.append(f"[{etype}]")
    if mod:
        parts.append(f"mod: {mod}")

    # 描述
    desc_en = entity.get('description_en', '')
    desc_zh = entity.get('description_zh', '')
    if desc_en:
        parts.append(desc_en)
    if desc_zh:
        parts.append(desc_zh)

    # 标签和分类
    tags = entity.get('tags', [])
    if tags:
        parts.append(f"tags: {', '.join(tags)}")
    cat = entity.get('category', '')
    rarity = entity.get('rarity', '')
    if cat:
        parts.append(f"category: {cat}")
    if rarity:
        parts.append(f"rarity: {rarity}")

    # 武器属性
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

    # 配方产出（怎么制作这个物品）
    recipes = entity.get('recipes_output', [])
    if recipes:
        recipe_strs = []
        for r in recipes[:5]:
            inputs = ', '.join(f"{i['item']}x{i['count']}" for i in r.get('inputs', []))
            station = r.get('station_zh', '') or r.get('station', '')
            recipe_strs.append(f"{inputs} @ {station}")
        parts.append("制作方式: " + '; '.join(recipe_strs))

    # 配方用途（这个物品能做什么）
    usage = entity.get('recipes_input', {})
    if usage:
        total = usage.get('total', 0)
        cats = list(usage.get('by_category', {}).keys())
        parts.append(f"用途: {total}个配方, 类别: {', '.join(cats[:5])}")

    # 掉落来源
    drops = entity.get('drop_sources', {})
    if drops:
        parts.append(f"掉落来源: {drops.get('total_pools', 0)}个pool")

    # 生态
    biomes = entity.get('biomes', [])
    if biomes:
        biome_names = [b['biome'] if isinstance(b, dict) else str(b) for b in biomes[:5]]
        parts.append(f"生态: {', '.join(biome_names)}")

    # Wiki 引用
    wiki_ref = entity.get('wiki_ref', '')
    if wiki_ref:
        parts.append(f"wiki: {wiki_ref}")

    # 怪物特有
    if etype == 'monster':
        dp = entity.get('drop_pool_default', '')
        if dp:
            parts.append(f"掉落池: {dp}")

    # 生态特有
    if etype == 'biome':
        fn = entity.get('friendly_name', '')
        fn_zh = entity.get('friendly_name_zh', '')
        if fn:
            parts.append(fn)
        if fn_zh:
            parts.append(fn_zh)
        ores = entity.get('ores', [])
        if ores:
            ore_names = [o['ore'] for o in ores[:10]]
            parts.append(f"矿石: {', '.join(ore_names)}")
        monsters = entity.get('monsters', [])
        if monsters:
            parts.append(f"怪物: {', '.join(monsters[:10])}")

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
          f'，已跳过 D 级，加载耗时 {time.time()-t0:.1f}s')

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
