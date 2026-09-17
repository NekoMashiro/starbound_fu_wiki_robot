#!/usr/bin/env python3
"""
build_knowledge_base.py — 构建 Frackin' Universe 知识库

将 wiki XML dump + FU mod 游戏数据 JSON 合并为统一的知识库。

输出:
  wiki_knowledge_base/
  ├── documents/          # 独立 .md 文档（人类可读）
  │   ├── wiki/           # wiki 文章
  │   ├── items/          # 物品
  │   ├── objects/        # 可放置物体
  │   ├── monsters/       # 怪物
  │   ├── biomes/         # 生态群系
  │   ├── codex/          # 游戏内百科
  │   ├── tech/           # 科技
  │   └── species/        # 种族
  ├── index.jsonl         # 主索引（每行一条，含全文）
  ├── metadata.json       # 全局统计
  └── redirects.json      # wiki 重定向别名

用法:
  python3 build_knowledge_base.py \\
    --wiki-output wiki_output \\
    --game-data FrackinUniverse \\
    --chinese FU_Chinese \\
    -o wiki_knowledge_base
"""

import argparse
import json
import os
import re
import sys
import time
import yaml
from pathlib import Path
from collections import defaultdict

WIKI_BASE_URL = "https://frackinuniverse.miraheze.org/wiki/"


# ─────────────────────────────────────────────
# 1. 游戏数据解析器
# ─────────────────────────────────────────────

# 游戏数据文件后缀 → 知识库类型映射
GAME_FILE_TYPES = {
    # items
    '.item': 'item',
    '.activeitem': 'item',
    '.consumable': 'item',
    '.augment': 'item',
    '.head': 'item',
    '.chest': 'item',
    '.legs': 'item',
    '.back': 'item',
    '.liqitem': 'item',
    '.matitem': 'item',
    '.coinitem': 'item',
    '.currency': 'item',
    '.instrument': 'item',
    '.thrownitem': 'item',
    '.flashlight': 'item',
    '.miningtool': 'item',
    '.beamaxe': 'item',
    '.tillingtool': 'item',
    '.harvestingtool': 'item',
    '.inspectiontool': 'item',
    '.painttool': 'item',
    '.wiretool': 'item',
    '.unlock': 'item',
    # others
    '.object': 'object',
    '.monstertype': 'monster',
    '.biome': 'biome',
    '.codex': 'codex',
    '.tech': 'tech',
    '.species': 'species',
    '.statuseffect': 'statuseffect',
}

# 装备子类型映射
ARMOR_SUBTYPES = {
    '.head': 'head_armor',
    '.chest': 'chest_armor',
    '.legs': 'leg_armor',
    '.back': 'back_armor',
}


def parse_json_lenient(filepath: Path) -> dict | None:
    """宽松 JSON 解析：处理注释和尾逗号。"""
    try:
        text = filepath.read_text(encoding='utf-8', errors='replace')
        # 移除 // 行注释
        text = re.sub(r'//.*?$', '', text, flags=re.MULTILINE)
        # 移除 /* */ 块注释
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        # 移除尾逗号 (},] 或 },})
        text = re.sub(r',\s*([}\]])', r'\1', text)
        return json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def scan_game_data(game_dir: Path) -> list[dict]:
    """扫描 FU mod 目录，提取所有游戏数据。"""
    entries = []
    for ext, entry_type in GAME_FILE_TYPES.items():
        for filepath in game_dir.rglob(f'*{ext}'):
            # 跳过 patch 文件（不完整数据）、测试文件、未启用内容
            if '.patch' in filepath.suffixes:
                continue
            rel = filepath.relative_to(game_dir)
            if any(part.startswith(('a_', '.')) for part in rel.parts):
                continue

            data = parse_json_lenient(filepath)
            if data is None:
                continue

            entry = extract_entry(data, entry_type, ext, filepath, game_dir)
            if entry:
                entries.append(entry)

    return entries


def extract_entry(data: dict, entry_type: str, ext: str, filepath: Path, game_dir: Path) -> dict | None:
    """从 JSON 数据中提取知识库条目。"""
    # 各类型的 ID 字段不同
    id_keys = {
        'item': ['itemName'],
        'object': ['objectName'],
        'monster': ['type'],
        'biome': ['name'],
        'codex': ['id'],
        'tech': ['name'],
        'species': ['kind'],
        'statuseffect': ['name'],
    }

    item_id = None
    for key in id_keys.get(entry_type, []):
        item_id = data.get(key)
        if item_id:
            break
    if not item_id:
        return None

    entry = {
        'id': item_id,
        'type': entry_type,
        'source': 'game_data',
        'source_file': str(filepath.relative_to(game_dir)),
    }

    # 通用字段
    for field in ['shortdescription', 'description', 'category', 'rarity',
                  'price', 'level', 'maxStack', 'twoHanded', 'itemTags',
                  'race', 'friendlyName']:
        if field in data:
            entry[field] = data[field]

    # 标题：优先 shortdescription > friendlyName > id
    entry['title'] = (data.get('shortdescription')
                       or data.get('friendlyName')
                       or item_id)

    # 类型特定字段
    if entry_type == 'item':
        _extract_item_specifics(data, entry, ext)
    elif entry_type == 'object':
        _extract_object_specifics(data, entry)
    elif entry_type == 'monster':
        _extract_monster_specifics(data, entry)
    elif entry_type == 'biome':
        _extract_biome_specifics(data, entry)
    elif entry_type == 'codex':
        _extract_codex_specifics(data, entry)
    elif entry_type == 'tech':
        _extract_tech_specifics(data, entry)
    elif entry_type == 'species':
        _extract_species_specifics(data, entry)
    elif entry_type == 'statuseffect':
        _extract_statuseffect_specifics(data, entry)

    return entry


def _extract_item_specifics(data: dict, entry: dict, ext: str):
    """提取物品特定字段。"""
    if ext in ARMOR_SUBTYPES:
        entry['armor_type'] = ARMOR_SUBTYPES[ext]

    # 食物属性
    if 'foodValue' in data:
        entry['foodValue'] = data['foodValue']
    if 'effects' in data:
        effects = []
        for group in data['effects']:
            if isinstance(group, list):
                for eff in group:
                    if isinstance(eff, dict) and 'effect' in eff:
                        effects.append(eff)
        if effects:
            entry['effects'] = effects

    # 武器属性
    for field in ['elementalType', 'critChance', 'critBonus',
                  'baseShieldHealth', 'perfectBlockTime']:
        if field in data:
            entry[field] = data[field]

    # 主要能力
    pa = data.get('primaryAbility', {})
    if isinstance(pa, dict):
        ability_info = {}
        for k in ['energyPerShot', 'fireTime', 'baseDps', 'projectileType',
                   'drawTime', 'powerProjectileTime']:
            if k in pa:
                ability_info[k] = pa[k]
        if ability_info:
            entry['primaryAbility'] = ability_info

    # 副能力
    aa = data.get('altAbility', {})
    if isinstance(aa, dict) and 'name' in aa:
        entry['altAbilityName'] = aa['name']

    # 盾牌属性
    for field in ['shieldHealthRegen', 'shieldEnergyRegen', 'shieldBash',
                  'shieldProtection', 'shieldStamina']:
        if field in data and data[field] != 0:
            entry[field] = data[field]

    # 防护属性（非零值）
    protections = {}
    for k, v in data.items():
        if k.startswith('protection') and isinstance(v, (int, float)) and v != 0:
            protections[k] = v
    if protections:
        entry['protections'] = protections


def _extract_object_specifics(data: dict, entry: dict):
    """提取物体特定字段。"""
    for field in ['colonyTags', 'lightColor', 'particleEmitter',
                  'interactAction', 'health']:
        if field in data:
            entry[field] = data[field]

    # 提取 power 信息
    if 'inputNodes' in data or 'outputNodes' in data:
        entry['has_wiring'] = True


def _extract_monster_specifics(data: dict, entry: dict):
    """提取怪物特定字段。"""
    bp = data.get('baseParameters', {})
    if isinstance(bp, dict):
        for field in ['touchDamage', 'level', 'aggressive']:
            if field in bp:
                entry[f'monster_{field}'] = bp[field]
        # 掉落池
        if 'dropPools' in data:
            entry['dropPools'] = data['dropPools']

    if 'categories' in data:
        entry['monster_categories'] = data['categories']


def _extract_biome_specifics(data: dict, entry: dict):
    """提取生态群系特定字段。"""
    for field in ['mainBlock', 'subBlocks', 'weather', 'statusEffects']:
        if field in data:
            entry[field] = data[field]


def _extract_codex_specifics(data: dict, entry: dict):
    """提取百科特定字段。"""
    entry['title'] = data.get('title', entry.get('title', ''))
    if 'contentPages' in data:
        pages = data['contentPages']
        if isinstance(pages, list):
            entry['codex_content'] = '\n\n'.join(
                p if isinstance(p, str) else str(p) for p in pages
            )
    if 'species' in data:
        entry['codex_species'] = data['species']
    if 'tags' in data:
        entry['codex_tags'] = data['tags']


def _extract_tech_specifics(data: dict, entry: dict):
    """提取科技特定字段。"""
    entry['title'] = data.get('shortdescription', data.get('name', ''))
    for field in ['type', 'rarity', 'energyCost']:
        if field in data:
            entry[f'tech_{field}'] = data[field]


def _extract_species_specifics(data: dict, entry: dict):
    """提取种族特定字段。"""
    entry['title'] = data.get('charCreationTooltip', {}).get('title',
                     data.get('kind', ''))
    tooltip = data.get('charCreationTooltip', {})
    if 'description' in tooltip:
        entry['species_description'] = tooltip['description']


def _extract_statuseffect_specifics(data: dict, entry: dict):
    """提取状态效果特定字段。"""
    entry['title'] = data.get('label', data.get('name', ''))
    for field in ['label', 'icon', 'blockingStat', 'defaultDuration']:
        if field in data:
            entry[f'effect_{field}'] = data[field]
    if 'effectConfig' in data:
        ec = data['effectConfig']
        if isinstance(ec, dict):
            for k in ['healAmount', 'damagePerSecond', 'energyRegenPercentageRate']:
                if k in ec:
                    entry[f'effect_{k}'] = ec[k]


# ─────────────────────────────────────────────
# 2. 配方索引构建
# ─────────────────────────────────────────────

def build_recipe_index(game_dir: Path) -> dict[str, list[dict]]:
    """构建物品ID → 配方列表的索引。"""
    recipes_by_output = defaultdict(list)
    recipes_by_input = defaultdict(list)

    for filepath in game_dir.rglob('*.recipe'):
        rel = filepath.relative_to(game_dir)
        if any(part.startswith(('a_', '.')) for part in rel.parts):
            continue

        data = parse_json_lenient(filepath)
        if data is None:
            continue

        recipe = extract_recipe(data, filepath, game_dir)
        if recipe:
            output_id = recipe['output_id']
            recipes_by_output[output_id].append(recipe)
            for inp in recipe.get('inputs', []):
                recipes_by_input[inp['item']].append({
                    'produces': output_id,
                    'produces_name': recipe.get('output_name', output_id),
                    'groups': recipe.get('groups', []),
                })

    # 也处理 .recipe.patch 文件（补丁配方）
    for filepath in game_dir.rglob('*.recipe.patch'):
        rel = filepath.relative_to(game_dir)
        if any(part.startswith(('a_', '.')) for part in rel.parts):
            continue
        data = parse_json_lenient(filepath)
        if data is None or not isinstance(data, list):
            continue
        # 从路径推断物品名
        item_name = filepath.stem.replace('.recipe', '')
        for op in data:
            if isinstance(op, dict) and op.get('path', '').startswith('/groups'):
                val = op.get('value')
                if val and isinstance(val, str):
                    recipes_by_output[item_name].append({
                        'output_id': item_name,
                        'groups': [val],
                        'is_patch': True,
                    })

    return dict(recipes_by_output), dict(recipes_by_input)


def extract_recipe(data: dict, filepath: Path, game_dir: Path) -> dict | None:
    """从配方 JSON 提取结构化配方。"""
    output = data.get('output')
    if not output:
        return None

    output_item = output.get('item', '') if isinstance(output, dict) else str(output)
    output_count = output.get('count', 1) if isinstance(output, dict) else 1

    inputs = []
    for inp in data.get('input', []):
        if isinstance(inp, dict):
            inputs.append({
                'item': inp.get('item', ''),
                'count': inp.get('count', 1),
            })

    groups = data.get('groups', [])

    # 推断工作台名称
    crafting_station = _infer_station(groups, filepath, game_dir)

    return {
        'output_id': output_item,
        'output_count': output_count,
        'output_name': output.get('parameters', {}).get('shortdescription', '') if isinstance(output, dict) else '',
        'inputs': inputs,
        'groups': groups,
        'crafting_station': crafting_station,
        'source_file': str(filepath.relative_to(game_dir)),
    }


# 工作台组名 → 可读名称
STATION_NAMES = {
    'plain': 'Crafting',
    'woodworking': 'Wooden Workbench',
    'craftingfurniture': 'Wooden Workbench',
    'mortar': 'Mortar and Pestle',
    'anvil': 'Iron Anvil',
    'anvil2': 'Metalwork Station',
    'anvil3': 'Replicator / Armory',
    'armory3': 'Armory',
    'farmingmerchant': 'Terramart',
    'apiary': 'Apiary Crafting Station',
    'atomicfurnace': 'Atomic Furnace',
    'arcfurnace': 'Arc Smelter',
    'blastfurnace': 'Blast Furnace',
    'electricfurnace': 'Electric Furnace',
    'centrifuge': 'Centrifuge',
    'centrifuge2': 'Gas Centrifuge',
    'extractionlab': 'Extraction Lab',
    'extractionlabmadness': 'Extraction Lab (Madness)',
    'fissionreactor': 'Fission Reactor',
    'xenolab': 'Xeno Research Lab',
    'xenolab2': 'Advanced Xenolab',
    'roboticcraftingtable': 'Robotic Crafting Table',
    'machiningcraftingtable': 'Machining Table',
    'powerstation': 'Power Station',
    'separatortable': 'Separator Table',
    'medicalresearch': 'Medical Research Station',
    'pesticidestation': 'Pesticide Station',
    'craftingwheel': 'Spinning Wheel',
    'craftingfurnace': 'Furnace',
    'craftingfurnace2': 'Alloy Furnace',
    'craftingfurnace3': 'Atomic Furnace',
    'assemblyline': 'Assembly Line',
    'pickupwindow': 'Pickup',
}


def _infer_station(groups: list, filepath: Path, game_dir: Path) -> str:
    """从配方组名和文件路径推断工作台名称。"""
    for g in groups:
        if g in STATION_NAMES:
            return STATION_NAMES[g]
    # 从路径推断
    rel = str(filepath.relative_to(game_dir))
    for station_key, station_name in STATION_NAMES.items():
        if station_key in rel.lower():
            return station_name
    if groups:
        return groups[0]
    return 'Unknown'


# ─────────────────────────────────────────────
# 3. 中文翻译加载
# ─────────────────────────────────────────────

def load_chinese_translations(chinese_dir: Path) -> dict[str, dict[str, str]]:
    """
    加载汉化 mod 的翻译数据。

    返回: { "items/active/shields/penumbriteshield.activeitem": {
                "/shortdescription": "半影盾",
                "/description": "^green;+12%能量回复^reset;"
            }, ... }
    """
    translations = {}  # source_file_path → { json_path → chinese_text }

    texts_dir = chinese_dir / 'translations' / 'texts'
    if not texts_dir.exists():
        return translations

    for json_file in texts_dir.rglob('*.json'):
        data = parse_json_lenient(json_file)
        if not data or not isinstance(data, list):
            continue

        for entry in data:
            if not isinstance(entry, dict):
                continue
            texts = entry.get('Texts', {})
            chs = texts.get('Chs', '')
            if not chs:
                continue

            files = entry.get('Files', {})
            for source_file, json_paths in files.items():
                if source_file not in translations:
                    translations[source_file] = {}
                if isinstance(json_paths, list):
                    for jp in json_paths:
                        translations[source_file][jp] = chs

    return translations


def get_chinese_for_entry(entry: dict, zh_translations: dict) -> dict[str, str]:
    """
    查找某个游戏条目的中文翻译。

    返回: { 'title_zh': '半影盾', 'description_zh': '+12%能量回复', ... }
    """
    result = {}
    source_file = entry.get('source_file', '')
    if not source_file or source_file not in zh_translations:
        return result

    zh = zh_translations[source_file]

    # 标题（shortdescription）
    for key in ['/shortdescription', '/title']:
        if key in zh:
            clean = re.sub(r'\^[^;]*;', '', zh[key]).strip()
            result['title_zh'] = clean
            break

    # 描述
    if '/description' in zh:
        clean = re.sub(r'\^[^;]*;', '', zh['/description']).strip()
        result['description_zh'] = clean

    # friendlyName（用于 biome 等）
    if '/friendlyName' in zh:
        result['title_zh'] = zh['/friendlyName']

    # label（用于 statuseffect）
    if '/label' in zh:
        result['title_zh'] = zh['/label']

    return result


# ─────────────────────────────────────────────
# 4. Wiki 文章加载
# ─────────────────────────────────────────────

def load_wiki_articles(wiki_dir: Path) -> list[dict]:
    """加载已解析的 wiki 文章。"""
    articles = []
    articles_dir = wiki_dir / 'articles'
    if not articles_dir.exists():
        return articles

    for txt_file in sorted(articles_dir.iterdir()):
        if txt_file.suffix != '.txt':
            continue

        content = txt_file.read_text(encoding='utf-8')

        # 解析元信息头部
        title = ''
        page_id = ''
        timestamp = ''
        body = content

        title_m = re.search(r'^标题:\s*(.+)$', content, re.MULTILINE)
        if title_m:
            title = title_m.group(1).strip()
        pid_m = re.search(r'^页面ID:\s*(.+)$', content, re.MULTILINE)
        if pid_m:
            page_id = pid_m.group(1).strip()
        ts_m = re.search(r'^最后更新:\s*(.+)$', content, re.MULTILINE)
        if ts_m:
            timestamp = ts_m.group(1).strip()

        # 提取正文（头部之后的内容）
        sep_pos = content.find('══')
        if sep_pos >= 0:
            nl_pos = content.find('\n', sep_pos)
            body = content[nl_pos + 1:].strip() if nl_pos >= 0 else ''

        if not body or len(body) < 10:
            continue

        wiki_url = WIKI_BASE_URL + title.replace(' ', '_')

        articles.append({
            'id': f'wiki_{safe_id(title)}',
            'type': 'wiki_article',
            'source': 'wiki',
            'title': title,
            'page_id': page_id,
            'timestamp': timestamp,
            'wiki_url': wiki_url,
            'body': body,
        })

    # 也加载 categories
    cats_dir = wiki_dir / 'categories'
    if cats_dir.exists():
        for txt_file in sorted(cats_dir.iterdir()):
            if txt_file.suffix != '.txt':
                continue
            content = txt_file.read_text(encoding='utf-8')
            title_m = re.search(r'^标题:\s*(.+)$', content, re.MULTILINE)
            title = title_m.group(1).strip() if title_m else txt_file.stem
            sep_pos = content.find('══')
            body = content[content.find('\n', sep_pos) + 1:].strip() if sep_pos >= 0 else ''
            if body and len(body) >= 10:
                articles.append({
                    'id': f'wiki_{safe_id(title)}',
                    'type': 'wiki_category',
                    'source': 'wiki',
                    'title': title,
                    'wiki_url': WIKI_BASE_URL + title.replace(' ', '_'),
                    'body': body,
                })

    return articles


def load_wiki_redirects(wiki_dir: Path) -> dict:
    """加载 wiki 重定向映射。"""
    redir_path = wiki_dir / 'redirects.jsonl'
    redirects = {}
    if redir_path.exists():
        with open(redir_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    redirects[r['from']] = r['to']
    return redirects


# ─────────────────────────────────────────────
# 4. 文档生成器
# ─────────────────────────────────────────────

def safe_id(text: str) -> str:
    """生成安全的 ID 字符串。"""
    return re.sub(r'[^a-zA-Z0-9_]', '_', text.lower()).strip('_')[:100]


def safe_filename(text: str) -> str:
    """生成安全的文件名。"""
    name = re.sub(r'[<>:"|?*\\/]', '_', text)
    name = name.strip('. ')[:200]
    return name or '_unnamed_'


def title_to_wiki_url(title: str) -> str:
    """从标题生成 wiki URL。"""
    return WIKI_BASE_URL + title.replace(' ', '_')


def generate_item_document(entry: dict, recipes: list[dict],
                           used_in: list[dict],
                           wiki_body: str | None = None,
                           zh: dict | None = None) -> tuple[str, str]:
    """生成物品 .md 文档，返回 (front_matter_yaml, body_text)。"""
    zh = zh or {}

    # Front matter
    fm = {
        'id': entry['id'],
        'type': entry['type'],
        'source': entry['source'],
        'title': entry['title'],
        'wiki_url': title_to_wiki_url(entry['title']),
    }
    if zh.get('title_zh'):
        fm['title_zh'] = zh['title_zh']
    for field in ['category', 'rarity', 'level', 'price', 'itemTags',
                  'armor_type', 'elementalType']:
        if field in entry:
            fm[field] = entry[field]

    # Body — 标题行含中文
    title_line = entry['title']
    if zh.get('title_zh'):
        title_line = f"{entry['title']} ({zh['title_zh']})"
    lines = [f"# {title_line}", '']

    # 描述（中英双语）
    desc = entry.get('description', '')
    if desc:
        clean_desc = re.sub(r'\^[^;]*;', '', desc)
        lines.append(f"**描述**: {clean_desc}")
    if zh.get('description_zh'):
        lines.append(f"**中文描述**: {zh['description_zh']}")
    if desc or zh.get('description_zh'):
        lines.append('')

    # 基本属性行
    props = []
    if 'category' in entry:
        props.append(f"分类: {entry['category']}")
    if 'rarity' in entry:
        props.append(f"稀有度: {entry['rarity']}")
    if 'level' in entry:
        props.append(f"等级: {entry['level']}")
    if 'price' in entry:
        props.append(f"价格: {entry['price']}")
    if 'maxStack' in entry:
        props.append(f"堆叠上限: {entry['maxStack']}")
    if entry.get('twoHanded') is not None:
        props.append(f"双手: {'是' if entry['twoHanded'] else '否'}")
    if props:
        lines.append(' | '.join(props))
        lines.append('')

    # 标签
    tags = entry.get('itemTags', [])
    if tags:
        lines.append(f"**标签**: {', '.join(tags)}")
        lines.append('')

    # 食物属性
    if 'foodValue' in entry:
        lines.append(f"**食物值**: {entry['foodValue']}")
    if 'effects' in entry:
        lines.append('**效果**:')
        for eff in entry['effects']:
            name = eff.get('effect', '')
            dur = eff.get('duration', 0)
            dur_str = f" ({dur}s)" if dur else ''
            lines.append(f"  - {name}{dur_str}")
        lines.append('')

    # 武器/盾牌属性
    combat_props = []
    if 'elementalType' in entry:
        combat_props.append(f"元素: {entry['elementalType']}")
    if 'critChance' in entry:
        combat_props.append(f"暴击率: {entry['critChance']}%")
    if 'critBonus' in entry:
        combat_props.append(f"暴击加成: {entry['critBonus']}")
    if 'baseShieldHealth' in entry:
        combat_props.append(f"盾牌生命: {entry['baseShieldHealth']}")
    if 'perfectBlockTime' in entry:
        combat_props.append(f"完美格挡: {entry['perfectBlockTime']}s")
    if 'altAbilityName' in entry:
        combat_props.append(f"副能力: {entry['altAbilityName']}")
    if combat_props:
        lines.append('## 战斗属性')
        for p in combat_props:
            lines.append(f"- {p}")
        lines.append('')

    pa = entry.get('primaryAbility', {})
    if pa:
        lines.append('## 主能力')
        for k, v in pa.items():
            lines.append(f"- {k}: {v}")
        lines.append('')

    # 防护属性
    if 'protections' in entry:
        lines.append('## 防护属性')
        for k, v in entry['protections'].items():
            name = k.replace('protection', '')
            lines.append(f"- {name}: {v}")
        lines.append('')

    # 合成配方
    if recipes:
        lines.append('## 合成配方')
        for r in recipes:
            station = r.get('crafting_station', 'Unknown')
            lines.append(f"**工作台**: {station}")
            inputs = r.get('inputs', [])
            for inp in inputs:
                lines.append(f"  - {inp['count']}x {inp['item']}")
            out_count = r.get('output_count', 1)
            lines.append(f"  → {out_count}x {entry['title']}")
            lines.append('')

    # 用于合成（此物品作为材料）
    if used_in:
        lines.append('## 作为材料用于')
        seen = set()
        for u in used_in[:30]:
            name = u.get('produces_name') or u['produces']
            if name not in seen:
                seen.add(name)
                lines.append(f"  - {name}")
        if len(used_in) > 30:
            lines.append(f"  - ...还有 {len(used_in) - 30} 个")
        lines.append('')

    # 附加 wiki 文章内容
    if wiki_body:
        lines.append('## Wiki 文章')
        lines.append(wiki_body)
        lines.append('')

    body_text = '\n'.join(lines)
    return fm, body_text


def generate_wiki_document(article: dict) -> tuple[dict, str]:
    """生成 wiki 文章文档。"""
    fm = {
        'id': article['id'],
        'type': article['type'],
        'source': 'wiki',
        'title': article['title'],
        'wiki_url': article['wiki_url'],
    }
    if 'page_id' in article:
        fm['page_id'] = article['page_id']
    if 'timestamp' in article:
        fm['timestamp'] = article['timestamp']

    body = f"# {article['title']}\n\n{article['body']}"
    return fm, body


def generate_generic_document(entry: dict, zh: dict | None = None) -> tuple[dict, str]:
    """生成通用类型文档（monster/biome/codex/tech/species/statuseffect）。"""
    zh = zh or {}
    type_labels = {
        'monster': '怪物',
        'biome': '生态群系',
        'codex': '百科',
        'tech': '科技',
        'species': '种族',
        'statuseffect': '状态效果',
        'object': '物体',
    }

    fm = {
        'id': entry['id'],
        'type': entry['type'],
        'source': entry['source'],
        'title': entry['title'],
        'wiki_url': title_to_wiki_url(entry['title']),
    }
    if zh.get('title_zh'):
        fm['title_zh'] = zh['title_zh']
    for field in ['category', 'rarity', 'price', 'race']:
        if field in entry:
            fm[field] = entry[field]

    type_label = type_labels.get(entry['type'], entry['type'])
    title_line = entry['title']
    if zh.get('title_zh'):
        title_line = f"{entry['title']} ({zh['title_zh']})"
    lines = [f"# {title_line}", f"**类型**: {type_label}", '']

    desc = entry.get('description', '')
    if desc:
        clean_desc = re.sub(r'\^[^;]*;', '', desc)
        lines.append(f"**描述**: {clean_desc}")
    if zh.get('description_zh'):
        lines.append(f"**中文描述**: {zh['description_zh']}")
    if desc or zh.get('description_zh'):
        lines.append('')

    # 类型特定内容
    if entry['type'] == 'codex' and 'codex_content' in entry:
        lines.append('## 正文')
        lines.append(entry['codex_content'])
        lines.append('')
    elif entry['type'] == 'monster':
        if 'monster_categories' in entry:
            lines.append(f"**分类**: {', '.join(entry['monster_categories'])}")
        if 'monster_aggressive' in entry:
            lines.append(f"**攻击性**: {'是' if entry['monster_aggressive'] else '否'}")
        if 'monster_level' in entry:
            lines.append(f"**等级**: {entry['monster_level']}")
        lines.append('')
    elif entry['type'] == 'biome':
        if 'friendlyName' in entry:
            lines.append(f"**显示名称**: {entry['friendlyName']}")
        if 'mainBlock' in entry:
            lines.append(f"**主要方块**: {entry['mainBlock']}")
        if 'weather' in entry:
            weather = entry['weather']
            if isinstance(weather, list):
                lines.append(f"**天气**: {', '.join(str(w) for w in weather[:10])}")
        if 'statusEffects' in entry:
            effects = entry['statusEffects']
            if isinstance(effects, list):
                lines.append(f"**状态效果**: {', '.join(str(e) for e in effects)}")
        lines.append('')
    elif entry['type'] == 'tech':
        if 'tech_type' in entry:
            lines.append(f"**科技类型**: {entry['tech_type']}")
        if 'tech_energyCost' in entry:
            lines.append(f"**能量消耗**: {entry['tech_energyCost']}")
        lines.append('')
    elif entry['type'] == 'species':
        if 'species_description' in entry:
            lines.append(entry['species_description'])
            lines.append('')
    elif entry['type'] == 'statuseffect':
        if 'effect_label' in entry:
            lines.append(f"**显示名称**: {entry['effect_label']}")
        if 'effect_defaultDuration' in entry:
            lines.append(f"**默认持续**: {entry['effect_defaultDuration']}s")
        lines.append('')
    elif entry['type'] == 'object':
        props = []
        if 'category' in entry:
            props.append(f"分类: {entry['category']}")
        if 'rarity' in entry:
            props.append(f"稀有度: {entry['rarity']}")
        if 'price' in entry:
            props.append(f"价格: {entry['price']}")
        if 'race' in entry:
            props.append(f"种族: {entry['race']}")
        if props:
            lines.append(' | '.join(props))
        if entry.get('colonyTags'):
            lines.append(f"**殖民标签**: {', '.join(entry['colonyTags'])}")
        if entry.get('has_wiring'):
            lines.append('**支持线路连接**: 是')
        lines.append('')

    body_text = '\n'.join(lines)
    return fm, body_text


# ─────────────────────────────────────────────
# 5. 主构建逻辑
# ─────────────────────────────────────────────

def build_knowledge_base(wiki_dir: Path, game_dir: Path, output_dir: Path,
                         chinese_dir: Path | None = None):
    """构建完整的知识库。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    docs_dir = output_dir / 'documents'

    # 创建子目录
    for subdir in ['wiki', 'items', 'objects', 'monsters', 'biomes',
                   'codex', 'tech', 'species', 'statuseffects']:
        (docs_dir / subdir).mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    stats = defaultdict(int)

    # ── Step 1: 加载游戏数据 ──
    print('📦 [1/6] 扫描游戏数据...')
    game_entries = scan_game_data(game_dir)
    print(f'   找到 {len(game_entries)} 条游戏数据')
    for e in game_entries:
        stats[f'game_{e["type"]}'] += 1

    # ── Step 2: 构建配方索引 ──
    print('🔧 [2/6] 构建配方索引...')
    recipes_by_output, recipes_by_input = build_recipe_index(game_dir)
    print(f'   {len(recipes_by_output)} 个物品有合成配方')
    print(f'   {len(recipes_by_input)} 个物品被用作材料')

    # ── Step 3: 加载中文翻译 ──
    zh_translations = {}
    if chinese_dir and chinese_dir.exists():
        print('🇨🇳 [3/6] 加载中文翻译...')
        zh_translations = load_chinese_translations(chinese_dir)
        print(f'   {len(zh_translations)} 个文件有中文翻译')
    else:
        print('⏭️  [3/6] 跳过中文翻译（未提供 --chinese 参数）')

    # ── Step 4: 加载 wiki 文章 ──
    print('📖 [4/6] 加载 wiki 文章...')
    wiki_articles = load_wiki_articles(wiki_dir)
    wiki_redirects = load_wiki_redirects(wiki_dir)
    print(f'   {len(wiki_articles)} 篇文章, {len(wiki_redirects)} 条重定向')

    # 构建 wiki 标题 → 文章索引（用于匹配游戏物品）
    wiki_by_title = {}
    for art in wiki_articles:
        wiki_by_title[art['title'].lower()] = art
        # 也用简化标题索引
        simple = re.sub(r'^(Category:|Fd[_:])', '', art['title'], flags=re.IGNORECASE)
        wiki_by_title[simple.lower()] = art

    # ── Step 5: 生成文档 ──
    print('📝 [5/6] 生成知识库文档...')
    index_entries = []
    matched_wiki = set()  # 记录已与游戏数据合并的 wiki 文章
    stats['zh_matched'] = 0

    # 4a. 处理游戏数据条目
    type_to_dir = {
        'item': 'items',
        'object': 'objects',
        'monster': 'monsters',
        'biome': 'biomes',
        'codex': 'codex',
        'tech': 'tech',
        'species': 'species',
        'statuseffect': 'statuseffects',
    }

    seen_ids = set()
    for entry in game_entries:
        entry_id = entry['id']
        if entry_id in seen_ids:
            continue
        seen_ids.add(entry_id)

        entry_type = entry['type']
        subdir = type_to_dir.get(entry_type, 'items')

        # 查找匹配的 wiki 文章
        wiki_body = None
        title = entry.get('title', '')
        for lookup_title in [title, entry_id]:
            if lookup_title.lower() in wiki_by_title:
                art = wiki_by_title[lookup_title.lower()]
                wiki_body = art['body']
                matched_wiki.add(art['id'])
                entry['wiki_url'] = art['wiki_url']
                break

        # 获取中文翻译
        zh = get_chinese_for_entry(entry, zh_translations)
        if zh:
            stats['zh_matched'] += 1

        # 获取配方和用途
        recipes = recipes_by_output.get(entry_id, [])
        used_in = recipes_by_input.get(entry_id, [])

        # 生成文档
        if entry_type == 'item':
            fm, body = generate_item_document(entry, recipes, used_in, wiki_body, zh)
        elif entry_type == 'object':
            fm, body = generate_generic_document(entry, zh)
            # 物体也可能有配方
            if recipes:
                recipe_lines = ['\n## 合成配方']
                for r in recipes:
                    station = r.get('crafting_station', 'Unknown')
                    recipe_lines.append(f"**工作台**: {station}")
                    for inp in r.get('inputs', []):
                        recipe_lines.append(f"  - {inp['count']}x {inp['item']}")
                    recipe_lines.append(f"  → {r.get('output_count', 1)}x {entry['title']}")
                    recipe_lines.append('')
                body += '\n'.join(recipe_lines)
            if wiki_body:
                body += f'\n## Wiki 文章\n{wiki_body}\n'
        else:
            fm, body = generate_generic_document(entry, zh)
            if wiki_body:
                body += f'\n## Wiki 文章\n{wiki_body}\n'

        # 写入 .md 文件
        filename = safe_filename(entry_id) + '.md'
        filepath = docs_dir / subdir / filename
        md_content = '---\n' + yaml.dump(fm, allow_unicode=True, default_flow_style=False) + '---\n\n' + body
        filepath.write_text(md_content, encoding='utf-8')

        # 索引条目
        index_entry = dict(fm)
        index_entry['file'] = str(filepath.relative_to(output_dir))
        index_entry['content_length'] = len(body)
        index_entry['content'] = body
        index_entries.append(index_entry)
        stats[f'output_{subdir}'] += 1

    # 4b. 处理独立的 wiki 文章（未与游戏数据合并的）
    for article in wiki_articles:
        if article['id'] in matched_wiki:
            continue

        fm, body = generate_wiki_document(article)

        filename = safe_filename(article['title']) + '.md'
        filepath = docs_dir / 'wiki' / filename
        md_content = '---\n' + yaml.dump(fm, allow_unicode=True, default_flow_style=False) + '---\n\n' + body
        filepath.write_text(md_content, encoding='utf-8')

        index_entry = dict(fm)
        index_entry['file'] = str(filepath.relative_to(output_dir))
        index_entry['content_length'] = len(body)
        index_entry['content'] = body
        index_entries.append(index_entry)
        stats['output_wiki'] += 1

    # ── Step 6: 写入索引和元数据 ──
    print('💾 [6/6] 写入索引...')

    # index.jsonl
    index_path = output_dir / 'index.jsonl'
    with open(index_path, 'w', encoding='utf-8') as f:
        for entry in sorted(index_entries, key=lambda x: x.get('title', '')):
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    # redirects.json
    redirects_path = output_dir / 'redirects.json'
    with open(redirects_path, 'w', encoding='utf-8') as f:
        json.dump(wiki_redirects, f, ensure_ascii=False, indent=2)

    # metadata.json
    elapsed = time.time() - start_time
    metadata = {
        'name': "Frackin' Universe Knowledge Base",
        'version': '6.5.8',
        'built_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'build_time_seconds': round(elapsed, 1),
        'total_documents': len(index_entries),
        'total_redirects': len(wiki_redirects),
        'wiki_base_url': WIKI_BASE_URL,
        'stats': dict(stats),
        'schema': {
            'index.jsonl': 'One JSON object per line. Fields: id, type, source, title, wiki_url, file, content_length, content, and type-specific metadata.',
            'documents/': 'Individual .md files with YAML front-matter and body text.',
            'redirects.json': 'Map from alias title to canonical title.',
        },
    }
    meta_path = output_dir / 'metadata.json'
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # 打印摘要
    print()
    print('═' * 58)
    print("  Frackin' Universe 知识库构建完成!")
    print('═' * 58)
    print(f'  耗时: {elapsed:.1f}s')
    print(f'  总文档数: {len(index_entries)}')
    print(f'  ───────────────────────────────')
    for key in sorted(stats):
        print(f'    {key:30s}: {stats[key]:>6}')
    print(f'  ───────────────────────────────')
    print(f'  Wiki 文章合并到游戏数据: {len(matched_wiki)}')
    print(f'  独立 Wiki 文章: {stats.get("output_wiki", 0)}')
    print(f'  Wiki 重定向: {len(wiki_redirects)}')
    print(f'  🇨🇳 中文翻译匹配: {stats.get("zh_matched", 0)}')
    print(f'  ───────────────────────────────')
    print(f'  输出目录:    {output_dir.resolve()}')
    print(f'  主索引文件:  {index_path}')
    print(f'  元数据文件:  {meta_path}')
    print('═' * 58)


def main():
    parser = argparse.ArgumentParser(
        description="构建 Frackin' Universe 知识库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--wiki-output', default='wiki_output',
                        help='parse_wiki.py 的输出目录 (默认: wiki_output)')
    parser.add_argument('--game-data', default='FrackinUniverse',
                        help='FU mod 仓库目录 (默认: FrackinUniverse)')
    parser.add_argument('-o', '--output', default='wiki_knowledge_base',
                        help='知识库输出目录 (默认: wiki_knowledge_base)')
    parser.add_argument('--chinese', default=None,
                        help='中文汉化 mod 目录 (默认: 无)')

    args = parser.parse_args()

    wiki_dir = Path(args.wiki_output)
    game_dir = Path(args.game_data)
    output_dir = Path(args.output)
    chinese_dir = Path(args.chinese) if args.chinese else None

    if not wiki_dir.exists():
        print(f'❌ Wiki 输出目录不存在: {wiki_dir}', file=sys.stderr)
        sys.exit(1)
    if not game_dir.exists():
        print(f'❌ 游戏数据目录不存在: {game_dir}', file=sys.stderr)
        sys.exit(1)
    if chinese_dir and not chinese_dir.exists():
        print(f'⚠️  中文翻译目录不存在: {chinese_dir}，将跳过中文翻译', file=sys.stderr)
        chinese_dir = None

    build_knowledge_base(wiki_dir, game_dir, output_dir, chinese_dir)


if __name__ == '__main__':
    main()
