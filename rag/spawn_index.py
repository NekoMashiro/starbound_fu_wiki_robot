"""Wiki 星球生成表。

Frackin' Universe Wiki 把「某物在哪种星球、生成率多少」放在 Cargo 里，
不在物品词条正文：

- recipe 表：station 为 Biome objects / monsters / fish 等，
  inputs 是 biome:<生态 ID>，wikitext 里带生成率百分比
- layer / region / planet 表：生态挂到星球的哪一层

矿脉不在这张百分比表里。矿石分布在 relationship_db/biome_ores.json，
这里只把生态 ID 换成星球名，权重保持原样，不当成百分比。

重建索引（需要同目录上一级的 wiki XML）::

    cd rag && python spawn_index.py
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from config import KNOWLEDGE_BASE_DIR, PROJECT_ROOT

SPAWN_INDEX_PATH = PROJECT_ROOT / 'relationship_db' / 'spawn_index.json'
BIOME_ORES_PATH = PROJECT_ROOT / 'relationship_db' / 'biome_ores.json'
DEFAULT_XML = PROJECT_ROOT / 'frackinuniversewiki-20260903.xml'

MW_NS = '{http://www.mediawiki.org/xml/export-0.11/}'

SPAWN_STATIONS = {
    'Biome objects': 'object',
    'Biome monsters': 'monster',
    'Biome fish': 'fish',
    'Biome trees': 'tree',
    'Biome chests': 'chest',
    'Biome blocks': 'block',
    'Drops from breakable objects': 'breakable',
}

LAYER_ZH = {
    'surface': '地表',
    'subsurface': '地表下层',
    'underground1': '地下浅层',
    'underground2': '地下中层',
    'underground3': '地下深层',
    'core': '核心层',
    'atmosphere': '大气层',
    'space': '太空层',
}
LAYER_RANK = {name: i for i, name in enumerate(LAYER_ZH)}

WHERE_ZH = {
    'underground': '地下',
    'surface': '地表',
    'monsters': '怪物刷新',
    'fish': '钓鱼',
    'ground': '地面',
    'trees': '树木',
    'chests': '宝箱',
}

KIND_ZH = {
    'object': '场景物体',
    'monster': '怪物',
    'fish': '鱼类',
    'tree': '树木',
    'chest': '宝箱',
    'block': '地面方块',
    'breakable': '可破坏物掉落',
    'ore': '矿脉',
}

_LOCATION_RE = re.compile(
    r'星球|生成率|生成|在哪|哪里|哪儿|生态|分布|出没|刷新|刷在|出现|能找到|哪颗|哪种|什么星|矿脉|挖到'
)
_BIOME_LABEL_RE = re.compile(
    r'\[\[(?:[^|\]]*\|)?Biome: ([^\]]+)\]\]\s*(?:\'\'\(([^)]*)\)\'\')?'
)
_PCT_RE = re.compile(r"'''([\d.]+)%'''")
_NOTE_RE = re.compile(r"''\(([^)]*)\)''")
_LINK_RE = re.compile(r'\[\[(?:([^|\]]+)\|)?([^\]]+)\]\]')
_SURFACE_LAYERS = {'surface', 'subsurface'}
_DEEP_LAYERS = {'underground1', 'underground2', 'underground3', 'core'}
_STORE_MARK = '{{#cargo_store:_table = '


def wants_location_query(question: str) -> bool:
    """问的是出没地点或生成率，而不是配方。"""
    return bool(_LOCATION_RE.search(question or ''))


def load_spawn_index(path: Path | None = None) -> dict:
    path = path or SPAWN_INDEX_PATH
    if not path.exists():
        return _empty_index()
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    data.setdefault('planets', {})
    data.setdefault('biomes', {})
    data.setdefault('spawns', {})
    data.setdefault('ores', {})
    data.setdefault('biome_plants', {})
    return data


def index_has(index: dict, entity_id: str) -> bool:
    if not entity_id or not index:
        return False
    return entity_id in index.get('spawns', {}) or entity_id in index.get('ores', {})


def iter_cargo_stores(text: str):
    """逐条抽出 Cargo store。recipe 的 wikitext 里会再嵌一层 }}。"""
    pos = 0
    while True:
        i = text.find(_STORE_MARK, pos)
        if i < 0:
            return
        j = i + len(_STORE_MARK)
        nl = text.find('\n', j)
        if nl < 0:
            return
        table = text[j:nl].strip()
        if table == 'recipe':
            wiki_at = text.find('|wikitext=', nl)
            if wiki_at < 0:
                pos = nl + 1
                continue
            fields = _parse_fields(text[nl + 1:wiki_at])
            wiki_start = wiki_at + len('|wikitext=')
            end = text.find('\n}}', wiki_start)
            if end < 0:
                return
            fields['wikitext'] = text[wiki_start:end]
            yield table, fields
            pos = end + 3
        else:
            end = text.find('}}', nl)
            if end < 0:
                return
            yield table, _parse_fields(text[nl + 1:end])
            pos = end + 2


def parse_output_rates(wikitext: str) -> list[dict]:
    """按输出子弹的顺序取出生成率。组内百分比和组被抽中的概率分开记。"""
    text = wikitext
    if '|outputs=' in text:
        text = text.split('|outputs=', 1)[1]
    results = []
    in_group = False
    group_buf: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if 'recipe-group' in line and line.startswith('<div'):
            in_group = True
            group_buf = []
        if not line.startswith('*'):
            if in_group and '</div>' in line:
                _close_group(group_buf, line)
                in_group = False
                group_buf = []
            continue
        rate_m = _PCT_RE.search(line)
        note_m = _NOTE_RE.search(line)
        target, label = _bullet_identity(line)
        entry = {
            'rate': float(rate_m.group(1)) if rate_m else None,
            'group_rate': None,
            'note': note_m.group(1) if note_m else '',
            'target': target,
            'label': label,
        }
        results.append(entry)
        if in_group:
            group_buf.append(entry)
        if '</div>' in line:
            _close_group(group_buf, line)
            in_group = False
            group_buf = []
    return results


def parse_biome_label(wikitext: str) -> tuple[str, str]:
    match = _BIOME_LABEL_RE.search(wikitext or '')
    if not match:
        return '', ''
    return match.group(1).strip(), (match.group(2) or '').strip()


def build_spawn_index(
    xml_path: Path,
    biome_dir: Path | None = None,
    biome_ores_path: Path | None = None,
    item_dir: Path | None = None,
) -> dict:
    index = _empty_index()
    stats = {
        'recipes': 0,
        'rate_mismatch': 0,
        'spawns': 0,
    }
    for title, text in _iter_latest_cargo_texts(xml_path):
        if not title.startswith('Template:Cargo/'):
            continue
        for table, fields in iter_cargo_stores(text):
            if table == 'planet':
                _add_planet(index, fields)
            elif table == 'region':
                _add_region(index, fields)
            elif table == 'layer':
                _add_layer(index, fields)
            elif table == 'biome':
                _add_biome_name(index, fields)
            elif table == 'recipe':
                stats['recipes'] += 1
                mismatch = _add_recipe(index, fields)
                if mismatch:
                    stats['rate_mismatch'] += 1
    _attach_biome_places(index)
    _overlay_biome_zh(index, biome_dir or (KNOWLEDGE_BASE_DIR / 'entities' / 'biome'))
    _overlay_planet_zh(index)
    _add_ore_veins(
        index,
        biome_ores_path or BIOME_ORES_PATH,
        item_dir or (KNOWLEDGE_BASE_DIR / 'entities' / 'item'),
    )
    _sort_records(index)
    index.pop('_pending', None)
    index['_stats'] = {
        'planets': len(index['planets']),
        'biomes': len(index['biomes']),
        'spawn_ids': len(index['spawns']),
        'spawn_rows': sum(len(v) for v in index['spawns'].values()),
        'ore_ids': len(index['ores']),
        'recipes_seen': stats['recipes'],
        'rate_mismatch': stats['rate_mismatch'],
    }
    return index


def format_location_brief(index: dict, entities: list[dict], limit_each: int = 18) -> str:
    """给 LLM 的生成位置。没有记录就返回空字符串。"""
    if not index or not entities:
        return ''
    blocks = []
    for ent in entities:
        eid = ent.get('entity_id') or ''
        spawns = index.get('spawns', {}).get(eid) or []
        ores = index.get('ores', {}).get(eid) or []
        if not spawns and not ores:
            continue
        title = _entity_title(ent)
        lines = [title]
        if spawns:
            shown, hidden = _trim(spawns, limit_each)
            for row in shown:
                lines.append(_format_spawn(index, row))
            if hidden:
                lines.append(f'- 另有 {hidden} 条生成记录未列出')
        if ores:
            lines.append(
                '矿脉（数字是分布权重，不是生成率百分比。'
                '游戏还会按星球威胁等级再筛一遍，低威胁星球不一定刷得出来）'
            )
            planet_rows, loose, core_only = _ore_planets(index, ores)
            shown, hidden = _trim(planet_rows, 30)
            for row in shown:
                lines.append(_format_ore_planet(index, row))
            if loose:
                names = '、'.join(loose[:8])
                extra = f' 等 {len(loose)} 个生态' if len(loose) > 8 else ''
                lines.append(f'- 未挂到星球图层的生态: {names}{extra}')
            if core_only:
                lines.append(f'- 另有 {core_only} 种星球只在核心层或太空层的矿表里出现')
            if hidden:
                lines.append(f'- 另有 {hidden} 种星球也有矿脉，地表或地下权重更低')
        blocks.append('\n'.join(lines))
    if not blocks:
        return ''
    return (
        '【生成位置】下面是 Wiki 星球图层和生成表的查询结果，回答「在哪种星球、生成率多少」时只根据这一段。\n'
        '带百分号的才是生成率。矿脉权重不要换算成概率，也不要改用参考资料里截断过的 biomes 字段。\n\n'
        + '\n\n'.join(blocks)
    )


def build_found_on(index: dict, entity_id: str) -> dict | None:
    """收成能放进词条的一小段。星球按权重档合并，避免几十条图层把上下文撑满。"""
    if not index or not entity_id:
        return None
    spawns = index.get('spawns', {}).get(entity_id) or []
    ores = index.get('ores', {}).get(entity_id) or []
    if not spawns and not ores:
        return None
    found: dict = {}
    if spawns:
        places = []
        for row in spawns[:6]:
            biome = index.get('biomes', {}).get(row.get('biome') or '') or {}
            place = {
                'kind': KIND_ZH.get(row.get('kind') or '', row.get('kind') or ''),
                'biome': _biome_label(biome, row.get('biome') or ''),
            }
            where = WHERE_ZH.get(row.get('where') or '', row.get('where') or '')
            if where:
                place['where'] = where
            if row.get('rate') is not None:
                place['rate'] = f"{_num(row['rate'])}%"
            if row.get('group_rate') is not None:
                place['group_rate'] = f"{_num(row['group_rate'])}%"
            if row.get('note'):
                place['note'] = row['note']
            planets = _short_planets(index, biome.get('planets') or [], row.get('biome') or '', limit=3)
            if planets:
                place['planets'] = planets
            places.append(place)
        found['places'] = places
        hidden = len(spawns) - len(places)
        if hidden > 0:
            found['more_places'] = hidden
    if ores:
        planet_rows, loose, core_only = _ore_planets(index, ores)
        bands = _ore_bands(index, planet_rows)
        if bands:
            found['ore_weight_note'] = '分布权重不是生成率百分比；低威胁星球不一定刷得出'
            found['ore_planets'] = bands
        hidden_bands = _ore_band_count(planet_rows) - len(bands)
        if hidden_bands > 0:
            found['more_ore_bands'] = hidden_bands
        if loose:
            found['unmapped_biomes'] = len(loose)
        if core_only:
            found['core_or_space_only_planets'] = core_only
    return found or None


def collect_biome_plants(index: dict, plant_meta: dict) -> dict:
    """每个生态上的树、地表植物，以及这个生态会出现在哪些星球。"""
    grouped: dict[str, dict] = {}
    for eid, rows in (index.get('spawns') or {}).items():
        for row in rows:
            biome_id = row.get('biome') or ''
            if not biome_id:
                continue
            slot = grouped.setdefault(biome_id, {'trees': [], 'ground': []})
            if row.get('kind') == 'tree':
                name = row.get('label') or eid.split(':', 1)[-1]
                if name and _usable_tree_name(name) and name not in slot['trees']:
                    slot['trees'].append(name)
            elif row.get('kind') == 'object' and _is_ground_plant(eid, plant_meta.get(eid)):
                slot['ground'].append({
                    'id': eid,
                    'name': (plant_meta.get(eid) or {}).get('name') or eid,
                    'rate': row.get('rate'),
                })
    result = {}
    for biome_id, slot in grouped.items():
        if not slot['trees'] and not slot['ground']:
            continue
        biome = (index.get('biomes') or {}).get(biome_id) or {}
        plants: dict = {}
        trees = slot['trees'][:16]
        if trees:
            plants['trees'] = trees
        hidden_trees = len(slot['trees']) - len(trees)
        if hidden_trees > 0:
            plants['more_trees'] = hidden_trees
        ground = _compact_ground(slot['ground'])
        if ground:
            plants['ground'] = ground
        hidden_ground = len({row['id'] for row in slot['ground']}) - len(ground)
        if hidden_ground > 0:
            plants['more_ground'] = hidden_ground
        planets = _short_planets(index, biome.get('planets') or [], biome_id, limit=6)
        if planets:
            plants['planets'] = planets
        result[biome_id] = plants
    return result


def apply_biome_plants(index: dict, kb_dir: Path | None = None) -> dict:
    """把植物清单写进生态词条，并放进索引供检索补全。"""
    kb_dir = kb_dir or KNOWLEDGE_BASE_DIR
    plant_meta = _load_plant_meta(index, kb_dir)
    plants_by_biome = collect_biome_plants(index, plant_meta)
    index['biome_plants'] = plants_by_biome
    biome_dir = kb_dir / 'entities' / 'biome'
    written = 0
    unchanged = 0
    if biome_dir.exists():
        for path in biome_dir.glob('*.json'):
            plants = plants_by_biome.get(path.stem)
            if not plants:
                continue
            try:
                doc = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            if doc.get('plants') == plants:
                unchanged += 1
                continue
            doc['plants'] = plants
            path.write_text(
                json.dumps(doc, ensure_ascii=False, indent=2) + '\n',
                encoding='utf-8',
            )
            written += 1
    return {
        'biomes': len(plants_by_biome),
        'written': written,
        'unchanged': unchanged,
    }


def biome_appearances(index: dict) -> dict[str, list[dict]]:
    """每个生态出现在哪些星球、哪一层、主生态还是次级生态。"""
    result = {}
    for biome_id, biome in (index.get('biomes') or {}).items():
        rows = []
        for planet_id, layer, role in biome.get('planets') or []:
            if 'unknown' in planet_id:
                continue
            rows.append({
                'planet': _short_planet(index, planet_id),
                'where': LAYER_ZH.get(layer, layer),
                'role': '主生态' if role == 'primary' else '次级生态',
                '_layer': LAYER_RANK.get(layer, 99),
                '_role': 0 if role == 'primary' else 1,
                '_pid': planet_id,
            })
        rows.sort(key=lambda row: (row['_role'], row['_layer'], row['_pid']))
        clean = [
            {'planet': row['planet'], 'where': row['where'], 'role': row['role']}
            for row in rows
        ]
        if clean:
            result[biome_id] = clean
    return result


def planet_biome_tables(index: dict) -> dict[str, list[dict]]:
    """每颗星球按图层列出主生态和次级生态。"""
    grouped: dict[str, dict] = {}
    for biome_id, biome in (index.get('biomes') or {}).items():
        label = _biome_label(biome, biome_id)
        for planet_id, layer, role in biome.get('planets') or []:
            if 'unknown' in planet_id:
                continue
            slot = grouped.setdefault(planet_id, {}).setdefault(
                layer, {'primary': [], 'secondary': []},
            )
            names = slot['primary' if role == 'primary' else 'secondary']
            if label not in names:
                names.append(label)
    tables = {}
    for planet_id, layers in grouped.items():
        rows = []
        for layer in sorted(layers, key=lambda name: LAYER_RANK.get(name, 99)):
            slot = layers[layer]
            row = {'where': LAYER_ZH.get(layer, layer)}
            if slot['primary']:
                row['主生态'] = sorted(slot['primary'])
            if slot['secondary']:
                row['次级生态'] = sorted(slot['secondary'])
            rows.append(row)
        if rows:
            tables[planet_id] = rows
    return tables


def apply_world_map(index: dict, kb_dir: Path | None = None) -> dict:
    """把生态和星球的对应写进两边的词条，并登记星球索引。"""
    kb_dir = kb_dir or KNOWLEDGE_BASE_DIR
    appearances = biome_appearances(index)
    tables = planet_biome_tables(index)
    biome_dir = kb_dir / 'entities' / 'biome'
    biome_written = 0
    biome_unchanged = 0
    if biome_dir.exists():
        for path in biome_dir.glob('*.json'):
            rows = appearances.get(path.stem)
            if not rows:
                continue
            try:
                doc = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict) or doc.get('appears_on') == rows:
                if isinstance(doc, dict) and doc.get('appears_on') == rows:
                    biome_unchanged += 1
                continue
            doc['appears_on'] = rows
            path.write_text(
                json.dumps(doc, ensure_ascii=False, indent=2) + '\n',
                encoding='utf-8',
            )
            biome_written += 1

    planet_dir = kb_dir / 'entities' / 'planet'
    planet_dir.mkdir(parents=True, exist_ok=True)
    planet_docs = []
    planet_written = 0
    planet_unchanged = 0
    for planet_id, layers in tables.items():
        meta = (index.get('planets') or {}).get(planet_id) or {}
        source = 'FrackinUniverse'
        biome_path = biome_dir / f'{planet_id}.json'
        if biome_path.exists():
            try:
                biome_doc = json.loads(biome_path.read_text(encoding='utf-8'))
                source = biome_doc.get('source_mod') or source
            except (OSError, json.JSONDecodeError):
                pass
        doc = {
            'entity_id': planet_id,
            'entity_type': 'planet',
            'source_mod': source,
            'name_en': meta.get('name') or planet_id,
            'name_zh': meta.get('zh') or '',
            'entry_completeness': 'C',
            'biomes': layers,
        }
        if meta.get('min_tier'):
            doc['min_tier'] = str(meta['min_tier'])
        if meta.get('max_tier'):
            doc['max_tier'] = str(meta['max_tier'])
        planet_docs.append(doc)
        path = planet_dir / f'{planet_id}.json'
        try:
            old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
        except (OSError, json.JSONDecodeError):
            old = None
        if old == doc:
            planet_unchanged += 1
            continue
        path.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        planet_written += 1
    _sync_planet_index(kb_dir, planet_docs)
    return {
        'biomes': len(appearances),
        'biome_written': biome_written,
        'biome_unchanged': biome_unchanged,
        'planets': len(planet_docs),
        'planet_written': planet_written,
        'planet_unchanged': planet_unchanged,
    }


def _sync_planet_index(kb_dir: Path, planets: list[dict]) -> None:
    """星球词条写进 index.jsonl，点名时才能对上中文名。"""
    index_path = kb_dir / 'index.jsonl'
    if not index_path.exists():
        return
    kept = []
    with open(index_path, encoding='utf-8') as f:
        for line in f:
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError:
                kept.append(text + '\n')
                continue
            if row.get('entity_type') == 'planet':
                continue
            kept.append(text + '\n')
    for doc in sorted(planets, key=lambda item: item['entity_id']):
        kept.append(json.dumps({
            'entity_id': doc['entity_id'],
            'entity_type': 'planet',
            'name_en': doc.get('name_en') or '',
            'name_zh': doc.get('name_zh') or '',
            'source_mod': doc.get('source_mod') or '',
            'entry_completeness': doc.get('entry_completeness') or 'C',
            'file': f"entities/planet/{doc['entity_id']}.json",
        }, ensure_ascii=False) + '\n')
    index_path.write_text(''.join(kept), encoding='utf-8')


def apply_found_on(index: dict, kb_dir: Path | None = None) -> dict:
    """把 found_on 写进已有词条。同一个 ID 的物品和物体都会写。"""
    kb_dir = kb_dir or KNOWLEDGE_BASE_DIR
    entities_dir = kb_dir / 'entities'
    wanted = set(index.get('spawns') or {}) | set(index.get('ores') or {})
    written = 0
    unchanged = 0
    found_ids = set()
    if entities_dir.exists():
        for type_dir in entities_dir.iterdir():
            if not type_dir.is_dir():
                continue
            for path in type_dir.glob('*.json'):
                if path.stem not in wanted:
                    continue
                try:
                    doc = json.loads(path.read_text(encoding='utf-8'))
                except (OSError, json.JSONDecodeError):
                    continue
                if not isinstance(doc, dict):
                    continue
                eid = doc.get('entity_id') or path.stem
                found = build_found_on(index, eid)
                if not found:
                    continue
                found_ids.add(eid)
                if doc.get('found_on') == found:
                    unchanged += 1
                    continue
                doc['found_on'] = found
                path.write_text(
                    json.dumps(doc, ensure_ascii=False, indent=2) + '\n',
                    encoding='utf-8',
                )
                written += 1
    return {
        'written': written,
        'unchanged': unchanged,
        'entity_ids': len(found_ids),
        'missing_ids': len(wanted - found_ids),
    }


def save_spawn_index(index: dict, path: Path | None = None) -> None:
    path = path or SPAWN_INDEX_PATH
    payload = {k: v for k, v in index.items() if not k.startswith('_')}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')


def _empty_index() -> dict:
    return {
        'planets': {},
        'biomes': {},
        'spawns': {},
        'ores': {},
        '_pending': {
            'regions': {},
            'layers': [],
        },
    }


def _parse_fields(header: str) -> dict:
    fields = {}
    for line in header.splitlines():
        line = line.strip()
        if not line.startswith('|') or '=' not in line:
            continue
        key, value = line[1:].split('=', 1)
        fields[key.strip()] = value.strip()
    return fields


def _close_group(group_buf: list[dict], line: str) -> None:
    match = _PCT_RE.search(line)
    if not match:
        return
    rate = float(match.group(1))
    for entry in group_buf:
        entry['group_rate'] = rate


def _iter_latest_cargo_texts(xml_path: Path):
    """XML dump 带历史修订，只取每个页面的最后一版。"""
    for _event, elem in ET.iterparse(xml_path, events=('end',)):
        if elem.tag != f'{MW_NS}page':
            continue
        title = elem.findtext(f'{MW_NS}title') or ''
        if title.startswith('Template:Cargo/'):
            texts = elem.findall(f'{MW_NS}revision/{MW_NS}text')
            text = texts[-1].text if texts else ''
            yield title, text or ''
        elem.clear()


def _add_planet(index: dict, fields: dict) -> None:
    pid = fields.get('id') or ''
    if not pid:
        return
    index['planets'][pid] = {
        'name': fields.get('name') or pid,
        'zh': '',
        'min_tier': fields.get('minTier') or '',
        'max_tier': fields.get('maxTier') or '',
    }


def _add_region(index: dict, fields: dict) -> None:
    rid = fields.get('id') or ''
    biome = fields.get('biome') or ''
    if rid and biome:
        index['_pending']['regions'][rid] = biome


def _add_layer(index: dict, fields: dict) -> None:
    planet = fields.get('planet') or ''
    layer = fields.get('layer') or ''
    if not planet or not layer:
        return
    index['_pending']['layers'].append({
        'planet': planet,
        'layer': layer,
        'primary': _split_ids(fields.get('primaryRegion') or ''),
        'secondary': _split_ids(fields.get('secondaryRegions') or ''),
    })


def _add_biome_name(index: dict, fields: dict) -> None:
    bid = fields.get('id') or ''
    if not bid:
        return
    biome = index['biomes'].setdefault(bid, {'name': bid, 'zh': '', 'planets': []})
    if fields.get('name'):
        biome['name'] = fields['name']


def _add_recipe(index: dict, fields: dict) -> bool:
    kind = SPAWN_STATIONS.get(fields.get('station') or '')
    if not kind:
        return False
    biome_ids = [
        part.split(':', 1)[1]
        for part in (fields.get('inputs') or '').split(',')
        if part.strip().startswith('biome:') and part.strip().split(':', 1)[1]
    ]
    if not biome_ids:
        return False
    output_ids = []
    for part in (fields.get('outputs') or '').split(','):
        part = part.strip()
        if not part or part.startswith('pool:'):
            continue
        if part.startswith('monster:'):
            part = part.split(':', 1)[1]
        output_ids.append(part)
    if not output_ids:
        return False
    wikitext = fields.get('wikitext') or ''
    label, where = parse_biome_label(wikitext)
    rates = parse_output_rates(wikitext)
    rates = [row for row in rates if not (row.get('target') or '').startswith('TreasurePool')]
    rates = _collapse_same_label(rates, len(output_ids))
    mismatch = len(rates) != len(output_ids)
    for biome_id in biome_ids:
        biome = index['biomes'].setdefault(
            biome_id, {'name': label or biome_id, 'zh': '', 'planets': []},
        )
        if label and biome['name'] in (biome_id, ''):
            biome['name'] = label
        for i, item_id in enumerate(output_ids):
            rate = rates[i] if i < len(rates) else {'rate': None, 'group_rate': None, 'note': ''}
            row = {
                'kind': kind,
                'biome': biome_id,
                'where': where,
                'rate': rate.get('rate'),
                'group_rate': rate.get('group_rate'),
                'note': rate.get('note') or '',
            }
            if kind == 'tree':
                tree_name = _tree_display_name(rate.get('label') or '')
                if tree_name:
                    row['label'] = tree_name
            row = {k: v for k, v in row.items() if v not in (None, '')}
            bucket = index['spawns'].setdefault(item_id, [])
            sig = _spawn_sig(row)
            if any(_spawn_sig(old) == sig for old in bucket):
                continue
            bucket.append(row)
    return mismatch


def _usable_tree_name(name: str) -> bool:
    key = re.sub(r'\s+', '', (name or '').lower())
    if key in {'nothing', 'blank', 'none', 'nofoliage'}:
        return False
    return not (key.endswith('blank') or 'nofoliage' in key)


def _tree_display_name(label: str) -> str:
    """Stem: weeping (Weeping) → Weeping。"""
    label = (label or '').strip()
    match = re.search(r'\(([^)]+)\)\s*$', label)
    if match:
        return match.group(1).strip()
    if ':' in label:
        return label.split(':', 1)[1].strip()
    return label


def _is_ground_plant(entity_id: str, meta: dict | None) -> bool:
    category = ((meta or {}).get('category') or '').lower()
    if category in ('seed', 'sapling', 'farmable'):
        return True
    lowered = (entity_id or '').lower()
    return lowered.endswith(('seed', 'sapling', 'plant', 'flower', 'shroom', 'mushroom', 'bush', 'fern', 'kelp'))


def _compact_ground(rows: list[dict], limit: int = 12) -> list[dict]:
    best: dict[str, dict] = {}
    for row in rows:
        eid = row['id']
        current = best.get(eid)
        rate = row.get('rate')
        if current is None or (rate or -1) > (current.get('_rate') or -1):
            item = {'id': eid, 'name': row.get('name') or eid}
            if rate is not None:
                item['rate'] = f'{_num(rate)}%'
                item['_rate'] = rate
            best[eid] = item
    ordered = sorted(
        best.values(),
        key=lambda item: (-(item.get('_rate') or -1), item['id']),
    )
    cleaned = []
    for item in ordered[:limit]:
        item.pop('_rate', None)
        cleaned.append(item)
    return cleaned


def _load_plant_meta(index: dict, kb_dir: Path) -> dict:
    object_ids = {
        eid for eid, rows in (index.get('spawns') or {}).items()
        if any(row.get('kind') == 'object' for row in rows)
    }
    meta = {}
    for folder in ('item', 'object'):
        type_dir = kb_dir / 'entities' / folder
        if not type_dir.exists():
            continue
        for path in type_dir.glob('*.json'):
            if path.stem not in object_ids:
                continue
            try:
                doc = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            eid = doc.get('entity_id') or path.stem
            zh = (doc.get('name_zh') or '').strip()
            en = (doc.get('name_en') or '').strip()
            if zh and en:
                name = f'{zh}({en})'
            else:
                name = zh or en or eid
            meta[eid] = {'name': name, 'category': doc.get('category') or ''}
    return meta


def _bullet_identity(line: str) -> tuple[str, str]:
    match = _LINK_RE.search(line)
    if match:
        target = (match.group(1) or match.group(2) or '').strip()
        label = (match.group(2) or target).strip()
        return target, label
    plain = _PCT_RE.sub('', line)
    plain = re.sub(r"''[^']*''", '', plain)
    plain = plain.lstrip('*').strip()
    return '', plain


def _collapse_same_label(rates: list[dict], count: int) -> list[dict]:
    """同一物品连写两行时合成一条，避免和输出 ID 错位。"""
    rates = list(rates)
    while len(rates) > count:
        merged = False
        for i in range(len(rates) - 1):
            label = rates[i].get('label') or ''
            if not label or label != rates[i + 1].get('label'):
                continue
            if (rates[i + 1].get('rate') or -1) > (rates[i].get('rate') or -1):
                kept = dict(rates[i + 1])
                kept['group_rate'] = rates[i].get('group_rate') or rates[i + 1].get('group_rate')
                rates[i] = kept
            del rates[i + 1]
            merged = True
            break
        if not merged:
            break
    return rates


def _spawn_sig(row: dict) -> tuple:
    return (
        row.get('kind'), row.get('biome'), row.get('where'),
        row.get('rate'), row.get('group_rate'), row.get('note'),
    )


def _attach_biome_places(index: dict) -> None:
    regions = index['_pending']['regions']
    seen: dict[str, set] = {}
    for layer in index['_pending']['layers']:
        for role, region_ids in (
            ('primary', layer['primary']),
            ('secondary', layer['secondary']),
        ):
            for region_id in region_ids:
                biome_id = regions.get(region_id)
                if not biome_id:
                    continue
                place = (layer['planet'], layer['layer'], role)
                bag = seen.setdefault(biome_id, set())
                if place in bag:
                    continue
                bag.add(place)
                biome = index['biomes'].setdefault(
                    biome_id, {'name': biome_id, 'zh': '', 'planets': []},
                )
                biome['planets'].append(list(place))
    for biome in index['biomes'].values():
        biome['planets'].sort(key=lambda p: (
            0 if p[2] == 'primary' else 1,
            LAYER_RANK.get(p[1], 99),
            p[0],
        ))


def _overlay_biome_zh(index: dict, biome_dir: Path) -> None:
    if not biome_dir.exists():
        return
    for path in biome_dir.glob('*.json'):
        biome = index['biomes'].get(path.stem)
        if not biome:
            continue
        try:
            doc = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        zh = (doc.get('friendly_name_zh') or doc.get('name_zh') or '').strip()
        if zh:
            biome['zh'] = zh
        en = (doc.get('friendly_name') or doc.get('name_en') or '').strip()
        if en and biome.get('name') in (path.stem, ''):
            biome['name'] = en


def _overlay_planet_zh(index: dict) -> None:
    for pid, planet in index['planets'].items():
        biome = index['biomes'].get(pid) or {}
        zh = biome.get('zh') or ''
        if zh:
            planet['zh'] = zh


def _add_ore_veins(index: dict, biome_ores_path: Path, item_dir: Path) -> None:
    if not biome_ores_path.exists() or not item_dir.exists():
        return
    item_ids = {path.stem for path in item_dir.glob('*.json')}
    try:
        ore_map = json.loads(biome_ores_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return
    best: dict[str, dict[str, float]] = {}
    for biome_id, rows in ore_map.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            ore_name = (row.get('ore') or '').strip()
            if not ore_name:
                continue
            item_id = _resolve_ore_item(ore_name, item_ids)
            if not item_id:
                continue
            try:
                weight = float(row.get('weight') or 0)
            except (TypeError, ValueError):
                continue
            if weight <= 0:
                continue
            slot = best.setdefault(item_id, {})
            if weight > slot.get(biome_id, 0):
                slot[biome_id] = weight
    for item_id, biomes in best.items():
        index['ores'][item_id] = [
            {'biome': biome_id, 'weight': weight}
            for biome_id, weight in biomes.items()
        ]


def _resolve_ore_item(ore_name: str, item_ids: set[str]) -> str | None:
    candidates = []
    if ore_name.startswith('arcana_mod_'):
        candidates.append('arcana_ore_' + ore_name[len('arcana_mod_'):])
    if ore_name.endswith('ore'):
        candidates.append(ore_name)
    else:
        candidates.append(ore_name + 'ore')
        candidates.append(ore_name)
    for cand in candidates:
        if cand in item_ids:
            return cand
    return None


def _sort_records(index: dict) -> None:
    for rows in index['spawns'].values():
        rows.sort(key=lambda row: (
            -_sort_rate(row),
            row.get('biome') or '',
            row.get('kind') or '',
        ))
    for rows in index['ores'].values():
        rows.sort(key=lambda row: (-row['weight'], row['biome']))


def _sort_rate(row: dict) -> float:
    rate = row.get('rate')
    if rate is None:
        return -1.0
    return float(rate)


def _split_ids(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(',') if part.strip()]


def _entity_title(ent: dict) -> str:
    zh = (ent.get('name_zh') or '').strip()
    en = (ent.get('name_en') or '').strip()
    eid = ent.get('entity_id') or ''
    if zh and en:
        name = f'{zh}({en})'
    else:
        name = zh or en or eid
    return f'{name}'


def _format_spawn(index: dict, row: dict) -> str:
    biome = index['biomes'].get(row['biome']) or {}
    kind = KIND_ZH.get(row['kind'], row['kind'])
    where = WHERE_ZH.get(row['where'], row['where'])
    bits = [kind, _biome_label(biome, row['biome'])]
    if where:
        bits.append(where)
    rate = _format_rate(row.get('rate'), row.get('group_rate'))
    if rate:
        bits.append(rate)
    if row.get('note'):
        bits.append(row['note'])
    planets = _format_planet_list(
        index, biome.get('planets') or [], row.get('biome') or '', limit=8,
    )
    if planets:
        bits.append('这个生态会出现在: ' + planets)
    else:
        bits.append('这张星球图层表里没有对应星球')
    return '- ' + ' · '.join(bits)


def _format_rate(rate, group_rate) -> str:
    if rate is None and group_rate is None:
        return ''
    if rate is None:
        return f'生成率 {_num(group_rate)}%'
    text = f'生成率 {_num(rate)}%'
    if group_rate is not None and group_rate != rate:
        text += f'（该组被抽中的概率 {_num(group_rate)}%）'
    return text


def _ore_planets(index: dict, ores: list[dict]) -> tuple[list[dict], list[str], int]:
    """只统计星球主生态。地表和地下分开记，避免一个深层小生态把整颗星标成高权重。"""
    grouped: dict[str, dict] = {}
    loose = []
    for row in ores:
        biome = index['biomes'].get(row['biome']) or {}
        places = [p for p in (biome.get('planets') or []) if p[2] == 'primary']
        if not places:
            if not biome.get('planets'):
                loose.append(_biome_label(biome, row['biome']))
            continue
        for planet_id, layer, _role in places:
            slot = grouped.setdefault(planet_id, {
                'planet': planet_id,
                'surface': 0.0,
                'deep': 0.0,
                'deep_layer': '',
                'core': 0.0,
                'other': 0.0,
                'other_layer': '',
            })
            weight = row['weight']
            if layer in _SURFACE_LAYERS:
                slot['surface'] = max(slot['surface'], weight)
            elif layer in _DEEP_LAYERS and layer != 'core':
                if weight > slot['deep']:
                    slot['deep'] = weight
                    slot['deep_layer'] = layer
            elif layer == 'core':
                slot['core'] = max(slot.get('core', 0.0), weight)
            elif weight > slot['other']:
                slot['other'] = weight
                slot['other_layer'] = layer
    rows = []
    core_only = 0
    for slot in grouped.values():
        # 核心层和太空层是很多星球共用的矿表，不拿来给整颗星排名。
        slot['score'] = max(slot['surface'], slot['deep'])
        if slot['score'] <= 0:
            if slot.get('core') or slot['other']:
                core_only += 1
            continue
        rows.append(slot)
    rows.sort(key=lambda slot: (
        1 if 'unknown' in slot['planet'] else 0,
        0 if slot['surface'] else 1,
        -slot['surface'],
        -slot['deep'],
        slot['planet'],
    ))
    return rows, loose, core_only


def _format_ore_planet(index: dict, row: dict) -> str:
    planet = index['planets'].get(row['planet']) or {}
    bits = [_planet_label(planet, row['planet'])]
    if row['surface']:
        bits.append(f"地表权重 {_num(row['surface'])}")
    if row['deep']:
        layer = LAYER_ZH.get(row['deep_layer'], row['deep_layer'])
        bits.append(f'{layer}权重 {_num(row["deep"])}')
    elif row['other'] and not row['surface']:
        layer = LAYER_ZH.get(row['other_layer'], row['other_layer'])
        bits.append(f'{layer}权重 {_num(row["other"])}')
    return '- ' + ' · '.join(bits)


def _format_planet_list(index: dict, places: list, biome_id: str, limit: int) -> str:
    order = []
    seen = set()
    for planet_id, _layer, _role in places:
        if planet_id in seen:
            continue
        seen.add(planet_id)
        order.append(planet_id)
    order.sort(key=lambda pid: (
        1 if 'unknown' in pid else 0,
        0 if pid == biome_id else 1,
        0 if any(p[0] == pid and p[2] == 'primary' for p in places) else 1,
        pid,
    ))
    if not order:
        return ''
    shown = order[:limit]
    labels = []
    for pid in shown:
        planet = index['planets'].get(pid) or {}
        mine = [p for p in places if p[0] == pid]
        layer_bits = '、'.join(
            f"{LAYER_ZH.get(layer, layer)}{'主生态' if role == 'primary' else '次级生态'}"
            for _pid, layer, role in mine[:4]
        )
        labels.append(f"{_planet_label(planet, pid)}（{layer_bits}）")
    text = '；'.join(labels)
    if len(order) > limit:
        text += f'；等共 {len(order)} 种星球'
    return text


def _short_planets(index: dict, places: list, biome_id: str, limit: int) -> list[str]:
    order = []
    seen = set()
    for planet_id, _layer, _role in places:
        if planet_id in seen:
            continue
        seen.add(planet_id)
        order.append(planet_id)
    order.sort(key=lambda pid: (
        1 if 'unknown' in pid else 0,
        0 if pid == biome_id else 1,
        0 if any(p[0] == pid and p[2] == 'primary' for p in places) else 1,
        pid,
    ))
    labels = []
    for pid in order:
        if 'unknown' in pid:
            continue
        label = _short_planet(index, pid)
        if label not in labels:
            labels.append(label)
        if len(labels) >= limit:
            break
    return labels


def _short_planet(index: dict, planet_id: str) -> str:
    planet = index.get('planets', {}).get(planet_id) or {}
    name = planet.get('name') or planet_id
    zh = planet.get('zh') or ''
    if zh and zh != name:
        return f'{zh}({name})'
    return name


def _ore_bands(index: dict, rows: list[dict], band_limit: int = 6, name_limit: int = 10) -> list[dict]:
    grouped: dict[float, list[str]] = {}
    for row in rows:
        if not row.get('surface'):
            continue
        if 'unknown' in row['planet']:
            continue
        weight = round(float(row['surface']), 2)
        names = grouped.setdefault(weight, [])
        label = _short_planet(index, row['planet'])
        if label not in names:
            names.append(label)
    bands = []
    for weight in sorted(grouped, reverse=True)[:band_limit]:
        names = grouped[weight]
        band = {'surface_weight': weight, 'planets': names[:name_limit]}
        if len(names) > name_limit:
            band['more'] = len(names) - name_limit
        bands.append(band)
    return bands


def _ore_band_count(rows: list[dict]) -> int:
    return len({
        round(float(row['surface']), 2)
        for row in rows
        if row.get('surface')
    })


def _biome_label(biome: dict, biome_id: str) -> str:
    name = biome.get('name') or biome_id
    zh = biome.get('zh') or ''
    if zh and zh != name:
        return f'{zh}({name})'
    return name


def _planet_label(planet: dict, planet_id: str) -> str:
    name = planet.get('name') or planet_id
    zh = planet.get('zh') or ''
    if zh and zh != name:
        label = f'{zh}({name})'
    else:
        label = name
    tier = _tier_text(planet)
    if tier:
        label += f'，威胁 {tier}'
    return label


def _tier_text(planet: dict) -> str:
    lo = str(planet.get('min_tier') or '')
    hi = str(planet.get('max_tier') or '')
    if lo and hi and lo != hi:
        return f'{lo}-{hi}'
    return lo or hi


def _trim(rows: list, limit: int) -> tuple[list, int]:
    if len(rows) <= limit:
        return rows, 0
    return rows[:limit], len(rows) - limit


def _num(value) -> str:
    text = f'{float(value):.4f}'.rstrip('0').rstrip('.')
    return text


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parent))
    xml = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XML
    if not xml.exists():
        raise SystemExit(f'找不到 wiki XML: {xml}')
    print(f'解析 {xml.name} ...')
    index = build_spawn_index(xml)
    stats = index.get('_stats') or {}
    save_spawn_index(index)
    print(f'写入 {SPAWN_INDEX_PATH}')
    for key, value in stats.items():
        print(f'  {key}: {value}')
    applied = apply_found_on(index)
    print(
        f"词条 found_on: 写入 {applied['written']}，"
        f"未变化 {applied['unchanged']}，"
        f"对上 {applied['entity_ids']} 个 ID，"
        f"知识库里没有的 {applied['missing_ids']}"
    )
    planted = apply_biome_plants(index)
    save_spawn_index(index)
    print(
        f"生态植物: {planted['biomes']} 个生态，"
        f"写入 {planted['written']}，未变化 {planted['unchanged']}"
    )
    mapped = apply_world_map(index)
    print(
        f"生态星球对应: 生态写入 {mapped['biome_written']}，"
        f"未变化 {mapped['biome_unchanged']}；"
        f"星球写入 {mapped['planet_written']}，"
        f"未变化 {mapped['planet_unchanged']}"
    )
