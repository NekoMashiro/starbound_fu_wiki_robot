"""按池子抽一条实体。种子默认是当前时间的毫秒。"""

from __future__ import annotations

import json
import pickle
import random
import time
from dataclasses import dataclass
from pathlib import Path

from config import INDEX_JSONL, KNOWLEDGE_BASE_DIR, RANDOM_CATALOG_PATH, SKIP_QUALITY_TIERS
from random_pools import POOL_BY_ID, POOLS, Pool

CACHE_VERSION = 1


@dataclass(frozen=True)
class Candidate:
    entity_id: str
    entity_type: str
    file: str
    name_en: str
    name_zh: str


@dataclass(frozen=True)
class DrawResult:
    pool: Pool
    asked_pool: Pool
    candidate: Candidate
    seed: int


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def is_drawable(entity: dict) -> bool:
    if (entity.get('quality_tier') or '') in SKIP_QUALITY_TIERS:
        return False
    name = (entity.get('name_zh') or entity.get('name_en') or '').strip()
    return bool(name)


def matches_pool(entity: dict, pool: Pool) -> bool:
    if pool.rotate or not pool.entity_type:
        return False
    if (entity.get('entity_type') or '') != pool.entity_type:
        return False
    if pool.categories:
        cat = (entity.get('category') or '').strip()
        if cat not in pool.categories:
            return False
    if pool.tags:
        raw = entity.get('tags') or []
        if not isinstance(raw, list):
            raw = [raw]
        have = {str(t).strip() for t in raw if str(t).strip()}
        if not have.intersection(pool.tags):
            return False
    return True


def _candidate_from_row(row: dict) -> Candidate:
    return Candidate(
        entity_id=row.get('entity_id') or '',
        entity_type=row.get('entity_type') or '',
        file=row.get('file') or '',
        name_en=(row.get('name_en') or '').strip(),
        name_zh=(row.get('name_zh') or '').strip(),
    )


def _needed_types() -> set[str]:
    return {p.entity_type for p in POOLS if p.entity_type}


def _type_only_types() -> set[str]:
    return {
        p.entity_type
        for p in POOLS
        if p.entity_type and not p.categories and not p.tags
    }


class RandomCatalog:
    def __init__(self, members: dict[str, tuple[Candidate, ...]]):
        self._members = members

    def members(self, pool_id: str) -> tuple[Candidate, ...]:
        return self._members.get(pool_id) or ()

    def sizes(self) -> dict[str, int]:
        return {pid: len(items) for pid, items in self._members.items()}

    def draw(self, pool: Pool, seed: int | None = None) -> DrawResult | None:
        seed = now_ms() if seed is None else int(seed)
        rng = random.Random(seed)
        asked = pool
        if pool.rotate:
            choices = [POOL_BY_ID[pid] for pid in pool.rotate if pid in POOL_BY_ID]
            if not choices:
                return None
            pool = rng.choice(choices)
        items = self.members(pool.id)
        if not items:
            return None
        return DrawResult(
            pool=pool,
            asked_pool=asked,
            candidate=rng.choice(items),
            seed=seed,
        )


def _cache_signature(index_path: Path) -> tuple:
    mtime = index_path.stat().st_mtime if index_path.exists() else 0
    spec = tuple(
        (p.id, p.entity_type, p.categories, p.tags, p.rotate)
        for p in POOLS
    )
    return (CACHE_VERSION, round(mtime, 3), spec)


def _load_cache(path: Path, signature: tuple) -> RandomCatalog | None:
    if not path.exists():
        return None
    try:
        with open(path, 'rb') as f:
            cached = pickle.load(f)
        if cached.get('signature') != signature:
            return None
        return RandomCatalog(cached['members'])
    except Exception:
        return None


def _save_cache(path: Path, signature: tuple, catalog: RandomCatalog):
    try:
        with open(path, 'wb') as f:
            pickle.dump(
                {'signature': signature, 'members': catalog._members},
                f,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
    except Exception:
        pass


def build_catalog(
    kb_dir: Path | None = None,
    index_path: Path | None = None,
    cache_path: Path | None = None,
) -> RandomCatalog:
    kb_dir = kb_dir or KNOWLEDGE_BASE_DIR
    index_path = index_path or INDEX_JSONL
    cache_path = cache_path or RANDOM_CATALOG_PATH
    signature = _cache_signature(index_path)
    cached = _load_cache(cache_path, signature)
    if cached:
        return cached

    buckets: dict[str, list[Candidate]] = {p.id: [] for p in POOLS if not p.rotate}
    needed = _needed_types()
    type_only = _type_only_types()
    concrete = tuple(p for p in POOLS if not p.rotate)

    with open(index_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not is_drawable(row):
                continue
            et = row.get('entity_type') or ''
            if et not in needed:
                continue
            if et in type_only:
                cand = _candidate_from_row(row)
                for pool in concrete:
                    if matches_pool(row, pool):
                        buckets[pool.id].append(cand)
                continue
            rel = row.get('file') or ''
            path = kb_dir / rel
            try:
                entity = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                continue
            if not is_drawable(entity):
                continue
            cand = Candidate(
                entity_id=entity.get('entity_id') or row.get('entity_id') or '',
                entity_type=entity.get('entity_type') or et,
                file=rel,
                name_en=(entity.get('name_en') or row.get('name_en') or '').strip(),
                name_zh=(entity.get('name_zh') or row.get('name_zh') or '').strip(),
            )
            for pool in concrete:
                if matches_pool(entity, pool):
                    buckets[pool.id].append(cand)

    catalog = RandomCatalog({pid: tuple(items) for pid, items in buckets.items()})
    _save_cache(cache_path, signature, catalog)
    return catalog


def load_entity(candidate: Candidate, kb_dir: Path | None = None) -> dict | None:
    kb_dir = kb_dir or KNOWLEDGE_BASE_DIR
    path = kb_dir / candidate.file
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None


if __name__ == '__main__':
    import sys

    catalog = build_catalog()
    print('pool sizes:')
    for pid, n in catalog.sizes().items():
        print(f'  {n:5}  {pid}')
    text = ' '.join(sys.argv[1:]) or '随便来一个'
    from random_pools import resolve_pool
    match = resolve_pool(text)
    pool = match.pool if match else POOL_BY_ID['any']
    draw = catalog.draw(pool)
    if not draw:
        print(f'{text} → empty ({pool.id})')
    else:
        c = draw.candidate
        label = c.name_zh or c.name_en
        print(
            f'{text} → {draw.pool.id}  {label} ({c.name_en})  '
            f'id={c.entity_id}  seed={draw.seed}'
        )
