#!/usr/bin/env python3
"""
build_game_data.py — 知识库组装引擎

将 resolved_assets + recipe_db + treasure_db + relationship_db + wiki_articles
组装成最终的知识库文档（精简 JSON + Wiki Markdown）。

用法:
    python3 build_game_data.py -o knowledge_base
    python3 build_game_data.py -o knowledge_base --sample 20
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

# ─────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────

ASSETS_DIR = Path("resolved_assets")
RECIPE_DB = Path("recipe_db")
TREASURE_DB = Path("treasure_db")
RELATIONSHIP_DB = Path("relationship_db")
WIKI_DIR = Path("wiki_articles")
UNPACKED_DIR = Path("unpacked_data")

# 要生成文档的实体类型
ENTITY_TYPES = [
    "item", "object", "monster", "codex", "biome", "tech",
    "statuseffect", "species", "liquid", "quest", "tenant", "collection",
]
# 跳过的类型（数据已嵌入其他实体 or 信息密度太低）
SKIP_TYPES = ["recipe", "config", "treasurepools", "raceeffect", "weather", "npc"]

# 截断上限
MAX_RECIPES_INPUT_PER_CATEGORY = 5
MAX_RECIPES_INPUT_CATEGORIES = 8
MAX_RECIPES_OUTPUT = 15
MAX_DROP_TOP_PER_CATEGORY = 5
MAX_BIOMES = 10
RARITY_RANK = {"common": 0, "normal": 1, "uncommon": 2, "rare": 3, "rarest": 4}

# drop pool 分类关键词
POOL_CATEGORY_RULES = [
    ("mining", lambda n, p: "rock" in n.lower() or (p > 5.0 and "ore" in n.lower())),
    ("hunting_harvest", lambda n, p: "hunting" in n.lower() or "harvest" in n.lower()),
    ("boss_mission", lambda n, p: "boss" in n.lower() or "mission" in n.lower()),
    ("quest_rewards", lambda n, p: "questreward" in n.lower() or "questloot" in n.lower()
     or "dailyjob" in n.lower()),
    ("chest_loot", lambda n, p: "chest" in n.lower() or "dungeon" in n.lower()
     or "lootbox" in n.lower()),
    ("monster_drops", lambda n, p: "treasure" in n.lower() or "vault" in n.lower()),
]


def clean_color(text: str) -> str:
    return re.sub(r'\^[^;]*;', '', text) if text else ""


# ─────────────────────────────────────────────
# 数据加载器
# ─────────────────────────────────────────────

class DataLoader:
    """加载所有中间数据。"""

    def __init__(self):
        self.recipe_output_idx: dict = {}   # item → [line_index]
        self.recipe_input_idx: dict = {}    # item → [line_index]
        self.recipes: list = []             # [recipe] 按行号索引
        self.machine_input: dict = defaultdict(list)   # item → [mp]
        self.machine_output: dict = defaultdict(list)   # item → [mp]
        self.extraction_input: dict = defaultdict(list)  # item → [ex]
        self.extraction_output: dict = defaultdict(list)  # item → [ex]
        self.centrifuge_input: dict = defaultdict(list)
        self.centrifuge_output: dict = defaultdict(list)
        self.atmos_output: dict = defaultdict(list)
        self.atmos_biome: dict = defaultdict(list)
        self.biome_names: dict = {}
        self.drop_sources: dict = {}        # item → [{pool, probability, count}]
        self.monster_pools: dict = {}       # pool → [monster_id]
        self.blueprints: dict = {}          # item → [blueprint]
        self.biome_ores: dict = {}          # biome → [{ore, weight}]
        self.biome_monsters: dict = {}      # biome → [monster]
        self.race_effects: dict = {}
        self.research_trees: dict = {}
        self.item_tags: dict = {}           # tag → [item_id]
        self.status_effects: dict = {}
        self.collections: dict = {}
        self.codex_info: dict = {}
        self.upgrade_paths: dict = {}
        self.liquids: dict = {}
        self.quest_rewards: dict = {}
        self.tenant_reqs: list = []
        # 全局物品元数据缓存 (entity_id → {rarity, category, name_en, ...})
        self.item_meta: dict = {}
        # matmod 映射: modName → itemDrop, 以及反向 itemDrop → [modName]
        self.matmod_to_item: dict = {}
        self.item_to_matmod: dict = defaultdict(list)

    def load_all(self):
        t0 = time.time()
        print("📂 加载中间数据...")

        # recipes
        self._load_recipes()
        # treasure
        self._load_treasure()
        # relationships
        self._load_relationships()
        # matmod → itemDrop mapping
        self._load_matmod_mapping()
        # item metadata cache
        self._load_item_meta()

        print(f"   完成! {time.time()-t0:.1f}s")

    def _load_recipes(self):
        # 按行号加载配方列表（避免 recipe_id 重复导致覆盖）
        recipes_path = RECIPE_DB / "recipes.jsonl"
        if recipes_path.exists():
            with open(recipes_path) as f:
                for line in f:
                    self.recipes.append(json.loads(line))

        # 索引文件存的是行号（整数列表）
        idx_path = RECIPE_DB / "output_index.json"
        if idx_path.exists():
            with open(idx_path) as f:
                self.recipe_output_idx = json.load(f)

        idx_path = RECIPE_DB / "input_index.json"
        if idx_path.exists():
            with open(idx_path) as f:
                self.recipe_input_idx = json.load(f)

        # machine processing
        mp_path = RECIPE_DB / "machine_processing.jsonl"
        if mp_path.exists():
            with open(mp_path) as f:
                for line in f:
                    mp = json.loads(line)
                    self.machine_input[mp["input_item"]].append(mp)
                    self.machine_output[mp["output_item"]].append(mp)

        ex_path = RECIPE_DB / "extraction.jsonl"
        if ex_path.exists():
            with open(ex_path) as f:
                for line in f:
                    ex = json.loads(line)
                    out_item = ex.get("output_item")
                    if out_item:
                        self.extraction_output[out_item].append(ex)
                    for inp in ex.get("inputs") or []:
                        item = inp.get("item")
                        if item:
                            self.extraction_input[item].append(ex)

        cf_path = RECIPE_DB / "centrifuge.jsonl"
        if cf_path.exists():
            with open(cf_path) as f:
                for line in f:
                    row = json.loads(line)
                    if row.get("output_item"):
                        self.centrifuge_output[row["output_item"]].append(row)
                    if row.get("input_item"):
                        self.centrifuge_input[row["input_item"]].append(row)

        at_path = RECIPE_DB / "atmos.jsonl"
        if at_path.exists():
            with open(at_path) as f:
                for line in f:
                    row = json.loads(line)
                    if row.get("output_item"):
                        self.atmos_output[row["output_item"]].append(row)
                    if row.get("biome"):
                        self.atmos_biome[row["biome"]].append(row)

        biome_dir = Path("knowledge_base/entities/biome")
        if biome_dir.exists():
            for p in biome_dir.glob("*.json"):
                try:
                    with open(p, encoding="utf-8") as f:
                        bdoc = json.load(f)
                except (json.JSONDecodeError, OSError):
                    continue
                bid = bdoc.get("entity_id") or p.stem
                self.biome_names[bid] = {
                    "name_en": bdoc.get("name_en") or bdoc.get("friendly_name") or bid,
                    "name_zh": bdoc.get("name_zh") or bdoc.get("friendly_name_zh") or "",
                }

        print(
            f"   配方: {len(self.recipes)}, 机器: {sum(len(v) for v in self.machine_input.values())}, "
            f"萃取: {sum(len(v) for v in self.extraction_output.values())}, "
            f"离心族: {sum(len(v) for v in self.centrifuge_output.values())}, "
            f"冷凝: {sum(len(v) for v in self.atmos_output.values())}"
        )

    def _load_treasure(self):
        dp_path = TREASURE_DB / "item_drop_sources.json"
        if dp_path.exists():
            with open(dp_path) as f:
                self.drop_sources = json.load(f)

        mp_path = TREASURE_DB / "monster_pools.json"
        if mp_path.exists():
            with open(mp_path) as f:
                self.monster_pools = json.load(f)

        print(f"   掉落: {len(self.drop_sources)} 种物品, 怪物pool: {len(self.monster_pools)}")

    def _load_relationships(self):
        def _load_json(name):
            p = RELATIONSHIP_DB / f"{name}.json"
            if p.exists():
                with open(p) as f:
                    return json.load(f)
            return {} if not name.endswith("s") else []

        self.blueprints = _load_json("blueprints")
        self.biome_ores = _load_json("biome_ores")
        self.biome_monsters = _load_json("biome_monsters")
        self.race_effects = _load_json("race_effects")
        self.research_trees = _load_json("research_trees")
        self.item_tags = _load_json("item_tags")
        self.status_effects = _load_json("status_effects")
        self.collections = _load_json("collections")
        self.codex_info = _load_json("codex_sources")
        self.upgrade_paths = _load_json("upgrade_paths")
        self.liquids = _load_json("liquids")
        self.quest_rewards = _load_json("quest_rewards")
        self.tenant_reqs = _load_json("tenant_requirements")
        if isinstance(self.tenant_reqs, dict):
            self.tenant_reqs = list(self.tenant_reqs.values()) if self.tenant_reqs else []

        print(f"   关系数据: {sum(1 for v in [self.blueprints, self.biome_ores, self.race_effects, self.research_trees, self.item_tags, self.status_effects, self.collections, self.codex_info, self.upgrade_paths, self.liquids, self.quest_rewards] if v)} 类已加载")

    def _load_matmod_mapping(self):
        """扫描 .matmod 文件，建立矿石方块名 → 掉落物品名的映射。"""
        count = 0
        for root, dirs, files in os.walk(UNPACKED_DIR):
            for fn in files:
                if not fn.endswith(".matmod"):
                    continue
                fp = os.path.join(root, fn)
                try:
                    with open(fp, encoding="utf-8", errors="replace") as f:
                        d = json.load(f)
                except:
                    continue
                mod_name = d.get("modName", "")
                item_drop = d.get("itemDrop", "")
                if mod_name and item_drop:
                    self.matmod_to_item[mod_name] = item_drop
                    self.item_to_matmod[item_drop].append(mod_name)
                    count += 1
        print(f"   matmod映射: {count}")

    def _load_item_meta(self):
        """缓存所有 item/object 的 rarity/category/name 用于排序。"""
        for entity_type in ["item", "object"]:
            type_dir = ASSETS_DIR / entity_type
            if not type_dir.exists():
                continue
            for fn in os.listdir(type_dir):
                if not fn.endswith(".json"):
                    continue
                try:
                    with open(type_dir / fn) as f:
                        d = json.load(f)
                except:
                    continue
                if not isinstance(d, dict):
                    continue
                eid = d.get("itemName") or d.get("objectName") or ""
                if eid:
                    self.item_meta[eid] = {
                        "rarity": d.get("rarity", "Common"),
                        "category": d.get("category", ""),
                        "name_en": clean_color(d.get("shortdescription", "")),
                    }


# ─────────────────────────────────────────────
# 掉落来源归纳
# ─────────────────────────────────────────────

def summarize_drop_sources(
    item_id: str, loader: DataLoader
) -> dict | None:
    """将物品的掉落来源归纳为分类摘要。"""
    sources = loader.drop_sources.get(item_id, [])
    if not sources:
        return None

    # 分类
    categories = defaultdict(list)
    for src in sources:
        pool_name = src["pool"]
        prob = src["probability"]
        categorized = False
        for cat_name, rule_fn in POOL_CATEGORY_RULES:
            if rule_fn(pool_name, prob):
                categories[cat_name].append(src)
                categorized = True
                break
        if not categorized:
            categories["other"].append(src)

    result = {"total_pools": len(sources)}

    for cat_name, cat_sources in categories.items():
        # 按概率降序排
        cat_sources.sort(key=lambda x: -x["probability"])
        top = cat_sources[:MAX_DROP_TOP_PER_CATEGORY]

        # 关联怪物
        top_with_monsters = []
        for s in top:
            entry = {
                "pool": s["pool"],
                "probability": s["probability"],
                "count": s.get("count", 1),
            }
            monsters = loader.monster_pools.get(s["pool"], [])
            if monsters:
                entry["monsters"] = monsters[:5]
            top_with_monsters.append(entry)

        cat_data = {
            "count": len(cat_sources),
            "top": top_with_monsters,
        }

        # 概率范围
        probs = [s["probability"] for s in cat_sources]
        if len(probs) > 1:
            cat_data["prob_range"] = [
                round(min(probs), 4), round(max(probs), 4)
            ]

        result[cat_name] = cat_data

    return result


# ─────────────────────────────────────────────
# 配方归纳
# ─────────────────────────────────────────────

def summarize_recipes_input(item_id: str, loader: DataLoader) -> dict | None:
    """归纳物品作为材料的配方用途（按 output category 分组）。"""
    recipe_indices = loader.recipe_input_idx.get(item_id, [])
    if not recipe_indices:
        return None

    # 按 output 物品的 category 分组
    by_category = defaultdict(list)
    for idx in recipe_indices:
        if idx >= len(loader.recipes):
            continue
        r = loader.recipes[idx]
        output_item = r.get("output_item", "")
        meta = loader.item_meta.get(output_item, {})
        cat = meta.get("category", "") or "other"
        by_category[cat].append({
            "output": output_item,
            "output_name": meta.get("name_en", ""),
            "output_count": r.get("output_count", 1),
            "stations": [s.get("station_name", "") for s in r.get("stations", [])[:2]],
        })

    # 每个分类取 top N（按物品名排序保持稳定）
    result = {"by_category": {}, "total": len(recipe_indices)}
    cat_count = 0
    for cat in sorted(by_category.keys(), key=lambda c: -len(by_category[c])):
        if cat_count >= MAX_RECIPES_INPUT_CATEGORIES:
            break
        items = by_category[cat]
        items.sort(key=lambda x: x["output"])
        examples = [it["output"] for it in items[:MAX_RECIPES_INPUT_PER_CATEGORY]]
        result["by_category"][cat] = {
            "count": len(items),
            "examples": examples,
        }
        cat_count += 1

    return result


def summarize_recipes_output(item_id: str, loader: DataLoader) -> list | None:
    """归纳物品的制作方式（按材料数量升序）。"""
    recipe_indices = loader.recipe_output_idx.get(item_id, [])
    if not recipe_indices:
        return None

    recipes = []
    for idx in recipe_indices:
        if idx >= len(loader.recipes):
            continue
        r = loader.recipes[idx]
        inputs = r.get("inputs", [])
        stations = r.get("stations", [])
        entry = {
            "inputs": [{"item": i["item"], "count": i["count"]} for i in inputs],
            "output_count": r.get("output_count", 1),
            "station": stations[0]["station_name"] if stations else "",
            "station_zh": stations[0].get("station_name_zh", "") if stations else "",
            "source_mod": r.get("source_mod", ""),
        }
        # 标记需要研究解锁的配方（FU 的 nouncrafting 机制）
        groups = r.get("groups", [])
        if "nouncrafting" in groups:
            entry["requires_research"] = True
        # 如果有多个可用工作站，列出前几个
        if len(stations) > 1:
            entry["also_at"] = [
                {"name": s["station_name"], "name_zh": s.get("station_name_zh", "")}
                for s in stations[1:8]
            ]
        recipes.append(entry)

    # 按材料总数升序（最简单的在前）
    recipes.sort(key=lambda r: sum(i["count"] for i in r["inputs"]))
    return recipes[:MAX_RECIPES_OUTPUT]


def summarize_machine_processing(item_id: str, loader: DataLoader) -> list | None:
    """获取物品的机器加工信息（作为输入）。"""
    mps = loader.machine_input.get(item_id, [])
    if not mps:
        return None
    return [{
        "machine": clean_color(mp.get("machine_name", "")),
        "machine_zh": clean_color(mp.get("machine_name_zh", "")),
        "output": mp["output_item"],
        "bonus": list(mp.get("bonus_outputs", {}).keys()),
    } for mp in mps]


def _extraction_yield(ex: dict) -> float:
    oc = ex.get("output_count") or {}
    out_n = max(int(oc.get("basic", 0) or 0), int(oc.get("advanced", 0) or 0),
                int(oc.get("quantum", 0) or 0), 0)
    in_n = sum(int(i.get("count", 1) or 1) for i in (ex.get("inputs") or [])) or 1
    return out_n / in_n


def summarize_extracted_from(item_id: str, loader: DataLoader) -> list | None:
    """可萃取获得该物品的原料 ID，按转化率排序，全部保留。"""
    rows = loader.extraction_output.get(item_id, [])
    if not rows:
        return None
    ranked = sorted(rows, key=_extraction_yield, reverse=True)
    out, seen = [], set()
    for ex in ranked:
        for inp in ex.get("inputs") or []:
            item = inp.get("item")
            if item and item not in seen:
                seen.add(item)
                out.append(item)
    return out or None


def summarize_extracts_into(item_id: str, loader: DataLoader) -> list | None:
    """该物品可萃取成的产物 ID，按转化率排序，全部保留。"""
    rows = loader.extraction_input.get(item_id, [])
    if not rows:
        return None
    ranked = sorted(rows, key=_extraction_yield, reverse=True)
    out, seen = [], set()
    for ex in ranked:
        output_item = ex.get("output_item")
        if output_item and output_item not in seen:
            seen.add(output_item)
            out.append(output_item)
    return out or None


def _rarity_key(row: dict) -> tuple:
    return (RARITY_RANK.get(str(row.get("rarity", "")).lower(), 9), -int(row.get("weight") or 0))


def _biome_label(biome_id: str, loader: DataLoader) -> str:
    if biome_id == "default":
        return "普通星球(default)"
    info = loader.biome_names.get(biome_id) or {}
    zh = info.get("name_zh") or ""
    en = info.get("name_en") or ""
    if zh and en and zh != en:
        return f"{zh}({en})"
    return zh or en or biome_id


def summarize_process_from(item_id: str, loader: DataLoader, family: str) -> list | None:
    rows = [r for r in loader.centrifuge_output.get(item_id, []) if r.get("family") == family]
    if not rows:
        return None
    ranked = sorted(rows, key=_rarity_key)
    out, seen = [], set()
    for row in ranked:
        item = row.get("input_item")
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out or None


def summarize_process_into(item_id: str, loader: DataLoader, family: str) -> list | None:
    rows = [r for r in loader.centrifuge_input.get(item_id, []) if r.get("family") == family]
    if not rows:
        return None
    ranked = sorted(rows, key=_rarity_key)
    out, seen = [], set()
    for row in ranked:
        item = row.get("output_item")
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out or None


def summarize_condensed_on(item_id: str, loader: DataLoader) -> list | None:
    rows = loader.atmos_output.get(item_id, [])
    if not rows:
        return None
    best = {}
    for row in rows:
        biome = row.get("alias_of") or row.get("biome")
        if not biome:
            continue
        rarity = row.get("rarity") or "common"
        if biome not in best or _rarity_key({"rarity": rarity}) < _rarity_key({"rarity": best[biome]}):
            best[biome] = rarity
    ranked = sorted(best, key=lambda b: (RARITY_RANK.get(str(best[b]).lower(), 9), b))
    return ranked or None


def summarize_condenser_outputs(biome_id: str, loader: DataLoader) -> dict | None:
    rows = loader.atmos_biome.get(biome_id, [])
    if not rows:
        # 别名星球：尝试找指向自己的表
        return None
    buckets = defaultdict(list)
    for row in rows:
        if row.get("alias_of"):
            continue
        rarity = row.get("rarity") or "common"
        item = row.get("output_item")
        if item and item not in buckets[rarity]:
            buckets[rarity].append(item)
    if not buckets:
        return None
    return {
        "common": buckets.get("common", []),
        "uncommon": buckets.get("uncommon", []),
        "rare": buckets.get("rare", []),
    }


def summarize_atmosphere_machine(loader: DataLoader) -> dict | None:
    if not loader.atmos_biome:
        return None
    examples = []
    prefer = ["default", "desert", "infernus", "tarball", "ocean", "moon", "atropus", "toxic"]
    seen = set()
    for biome in prefer + sorted(loader.atmos_biome):
        if biome in seen:
            continue
        rows = loader.atmos_biome.get(biome) or []
        if not rows or any(r.get("alias_of") for r in rows):
            continue
        seen.add(biome)
        common = []
        for row in rows:
            if row.get("rarity") == "common" and row.get("output_item") not in common:
                common.append(row["output_item"])
        examples.append({
            "biome": biome,
            "biome_zh": _biome_label(biome, loader),
            "common": common[:6],
        })
        if len(examples) >= 8:
            break
    return {
        "note": "产出取决于星球类型；飞船环绕该星球时用同一张表。附近气井会减速。",
        "biome_count": len({b for b, rows in loader.atmos_biome.items() if not any(r.get('alias_of') for r in rows)}),
        "examples": examples,
    }


# ─────────────────────────────────────────────
# 生态关联
# ─────────────────────────────────────────────

def find_biomes_for_ore(item_id: str, loader: DataLoader) -> list | None:
    """查找矿石出现的生态。同时检查 item_id 和对应的 matmod 名。"""
    # 需要匹配的 ID 集合：物品 ID 本身 + 对应的 matmod 方块名
    match_ids = {item_id}
    for matmod_name in loader.item_to_matmod.get(item_id, []):
        match_ids.add(matmod_name)

    biomes = []
    for biome_name, ores in loader.biome_ores.items():
        for ore in ores:
            if ore.get("ore", "") in match_ids:
                biomes.append({"biome": biome_name, "weight": ore.get("weight", 0)})
                break
    if not biomes:
        return None
    biomes.sort(key=lambda b: -b["weight"])
    return biomes[:MAX_BIOMES]


def find_biomes_for_monster(monster_id: str, loader: DataLoader) -> list | None:
    """查找怪物出现的生态。"""
    biomes = []
    for biome_name, monsters in loader.biome_monsters.items():
        if monster_id in monsters:
            biomes.append(biome_name)
    return biomes if biomes else None


# ─────────────────────────────────────────────
# 词条完善度（知识库信息密度，不是物品等级）
# ─────────────────────────────────────────────

def compute_entry_completeness(doc: dict) -> str:
    """根据词条信息密度计算完善度：S 最全，D 最薄。"""
    score = 0

    # 有中文名
    if doc.get("name_zh"):
        score += 2
    # 有描述
    if doc.get("description_en"):
        score += 1
    if doc.get("description_zh"):
        score += 1
    # 有配方
    if doc.get("recipes_output"):
        score += 1
    if doc.get("recipes_input"):
        score += 1
    # 有掉落
    if doc.get("drop_sources"):
        score += 1
    # 有生态
    if doc.get("biomes"):
        score += 1
    # 有关系数据
    for k in ["blueprints_unlocked", "machine_processing", "race_effects",
              "research_node", "collection_in", "extracted_from", "extracts_into",
              "centrifuged_from", "sifted_from", "crushed_from", "condensed_on",
              "condenser_outputs"]:
        if doc.get(k):
            score += 0.5

    if score >= 6:
        return "S"
    elif score >= 4:
        return "A"
    elif score >= 2.5:
        return "B"
    elif score >= 1:
        return "C"
    return "D"


# ─────────────────────────────────────────────
# Wiki 匹配
# ─────────────────────────────────────────────

def load_wiki_index(wiki_dir: Path) -> dict[str, Path]:
    """加载 wiki 文章索引，返回 {normalized_title: filepath}。"""
    index = {}
    if not wiki_dir.exists():
        return index
    for md_file in wiki_dir.rglob("*.md"):
        title = md_file.stem.replace("_", " ").lower()
        index[title] = md_file
    return index


def match_wiki(name_en: str, wiki_index: dict) -> str | None:
    """尝试匹配 wiki 文章。"""
    if not name_en:
        return None
    normalized = name_en.lower().strip()
    if normalized in wiki_index:
        return str(wiki_index[normalized].name)
    # 去掉 "FU " 等前缀
    for prefix in ["fu ", "frackin' "]:
        if normalized.startswith(prefix):
            stripped = normalized[len(prefix):]
            if stripped in wiki_index:
                return str(wiki_index[stripped].name)
    return None


# ─────────────────────────────────────────────
# 实体文档构建
# ─────────────────────────────────────────────

def build_entity_doc(
    entity: dict,
    entity_type: str,
    loader: DataLoader,
    wiki_index: dict,
) -> dict | None:
    """构建单个实体的知识库文档。"""
    if not isinstance(entity, dict):
        return None

    meta = entity.get("_meta", {})
    zh = meta.get("zh", {})

    # 基础 ID
    entity_id = meta.get("entity_id", "")
    if not entity_id:
        return None

    # 基础字段
    name_en = clean_color(
        entity.get("shortdescription")
        or entity.get("shortDescription")
        or entity.get("title")
        or entity.get("label")
        or entity.get("friendlyName")
        or entity.get("name")
        or ""
    )
    name_zh = clean_color(
        zh.get("shortdescription_zh")
        or zh.get("shortDescription_zh")
        or zh.get("title_zh")
        or zh.get("label_zh")
        or zh.get("friendlyName_zh")
        or ""
    )
    desc_en = clean_color(entity.get("description", ""))
    desc_zh = clean_color(zh.get("description_zh", ""))

    doc = {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "source_mod": meta.get("source_mod", ""),
        "name_en": name_en,
        "name_zh": name_zh,
        "description_en": desc_en,
        "description_zh": desc_zh,
    }

    # ── 类型特定字段 ──

    if entity_type in ("item", "object"):
        doc["rarity"] = entity.get("rarity", "")
        doc["category"] = entity.get("category", "")
        doc["price"] = entity.get("price", 0)
        tags = entity.get("itemTags", entity.get("colonyTags", []))
        if isinstance(tags, list):
            doc["tags"] = tags

        # 武器特有字段（.activeitem）
        if entity.get("elementalType"):
            doc["elementalType"] = entity["elementalType"]
        if entity.get("level"):
            doc["level"] = entity["level"]
        if entity.get("twoHanded") is not None:
            doc["twoHanded"] = entity["twoHanded"]
        primary = entity.get("primaryAbility", {})
        if isinstance(primary, dict) and primary.get("baseDps"):
            doc["baseDps"] = primary["baseDps"]
        if entity.get("critChance"):
            doc["critChance"] = entity["critChance"]
        if entity.get("critBonus"):
            doc["critBonus"] = entity["critBonus"]
        if entity.get("primaryAbilityType"):
            doc["primaryAbilityType"] = entity["primaryAbilityType"]
        alt = entity.get("altAbilityType") or entity.get("altAbility", {}).get("name")
        if alt:
            doc["altAbilityType"] = alt

        # 配方
        ro = summarize_recipes_output(entity_id, loader)
        if ro:
            doc["recipes_output"] = ro
        ri = summarize_recipes_input(entity_id, loader)
        if ri:
            doc["recipes_input"] = ri
        mp = summarize_machine_processing(entity_id, loader)
        if mp:
            doc["machine_processing"] = mp
        # 也检查机器产出
        mp_out = loader.machine_output.get(entity_id, [])
        if mp_out:
            doc["machine_produced_by"] = [{
                "machine": clean_color(m.get("machine_name", "")),
                "machine_zh": clean_color(m.get("machine_name_zh", "")),
                "input": m["input_item"],
            } for m in mp_out]
        extracted_from = summarize_extracted_from(entity_id, loader)
        if extracted_from:
            doc["extracted_from"] = extracted_from
        extracts_into = summarize_extracts_into(entity_id, loader)
        if extracts_into:
            doc["extracts_into"] = extracts_into
        for family, from_key, into_key in (
            ("centrifuge", "centrifuged_from", "centrifuges_into"),
            ("sifter", "sifted_from", "sifts_into"),
            ("crusher", "crushed_from", "crushes_into"),
        ):
            from_rows = summarize_process_from(entity_id, loader, family)
            if from_rows:
                doc[from_key] = from_rows
            into_rows = summarize_process_into(entity_id, loader, family)
            if into_rows:
                doc[into_key] = into_rows
        condensed = summarize_condensed_on(entity_id, loader)
        if condensed:
            doc["condensed_on"] = condensed
        if entity_id == "isn_atmoscondenser":
            atmos_machine = summarize_atmosphere_machine(loader)
            if atmos_machine:
                doc["atmosphere_outputs"] = atmos_machine

        # 掉落
        ds = summarize_drop_sources(entity_id, loader)
        if ds:
            doc["drop_sources"] = ds

        # 生态（矿石）
        biomes = find_biomes_for_ore(entity_id, loader)
        if biomes:
            doc["biomes"] = biomes

        # 蓝图
        bps = loader.blueprints.get(entity_id, [])
        if bps:
            doc["blueprints_unlocked"] = bps

        # 升级路径
        up = loader.upgrade_paths.get(entity_id)
        if up:
            doc["upgrade_path"] = up

    elif entity_type == "monster":
        # 怪物特定
        doc["level"] = entity.get("baseParameters", {}).get("level", 1) if isinstance(entity.get("baseParameters"), dict) else ""

        # 掉落池
        drop_pools = entity.get("dropPools", [])
        if isinstance(drop_pools, list):
            default_pool = ""
            hunting_pool = ""
            for dp in drop_pools:
                if isinstance(dp, dict):
                    default_pool = dp.get("default", default_pool)
                    hunting_pool = dp.get("bow", hunting_pool)
            if default_pool:
                doc["drop_pool_default"] = default_pool
            if hunting_pool and hunting_pool != default_pool:
                doc["drop_pool_hunting"] = hunting_pool

        # 出现生态
        biomes = find_biomes_for_monster(entity_id, loader)
        if biomes:
            doc["biomes"] = biomes

    elif entity_type == "biome":
        # 生态特定
        doc["friendly_name"] = clean_color(entity.get("friendlyName", ""))
        doc["friendly_name_zh"] = clean_color(zh.get("friendlyName_zh", ""))
        # 矿石（去重：同名矿石保留最高 weight）
        raw_ores = loader.biome_ores.get(entity_id, [])
        if raw_ores:
            best_ores = {}
            for ore in raw_ores:
                name = ore.get("ore", "")
                if name not in best_ores or ore.get("weight", 0) > best_ores[name].get("weight", 0):
                    best_ores[name] = ore
            deduped = sorted(best_ores.values(), key=lambda x: -x.get("weight", 0))
            doc["ores"] = deduped[:20]
        # 怪物
        monsters = loader.biome_monsters.get(entity_id, [])
        if monsters:
            doc["monsters"] = monsters
        # 天气
        weather = entity.get("weather", [])
        if weather:
            doc["weather"] = weather[:10] if isinstance(weather, list) else [weather]
        # 状态效果
        se = entity.get("statusEffects", [])
        if se:
            doc["status_effects"] = se
        condenser = summarize_condenser_outputs(entity_id, loader)
        if condenser:
            doc["condenser_outputs"] = condenser

    elif entity_type == "codex":
        info = loader.codex_info.get(entity_id, {})
        if info:
            doc["species"] = info.get("species", "")
            doc["content_pages"] = info.get("content_pages", [])

    elif entity_type == "tech":
        doc["type"] = entity.get("type", "")

    elif entity_type == "statuseffect":
        info = loader.status_effects.get(entity_id, {})
        if info:
            doc["icon"] = info.get("icon", "")
            doc["stats"] = info.get("stats", {})

    elif entity_type == "species":
        # 种族效果
        re_data = loader.race_effects.get(entity_id, {})
        if re_data:
            doc["race_effects"] = re_data

    elif entity_type == "liquid":
        info = loader.liquids.get(entity_id, {})
        if info:
            doc["status_effects"] = info.get("statusEffects", [])
            doc["interactions"] = info.get("interactions", {})

    elif entity_type == "quest":
        info = loader.quest_rewards.get(entity_id, {})
        if info:
            doc["rewards"] = info.get("rewards", [])
            doc["money_range"] = info.get("moneyRange", [])
            doc["prerequisites"] = info.get("prerequisites", [])
            doc["text_en"] = info.get("text_en", "")
            doc["text_zh"] = info.get("text_zh", "")

    elif entity_type == "tenant":
        doc["required_tags"] = entity.get("colonyTagCriteria", {})

    elif entity_type == "collection":
        info = loader.collections.get(entity_id, {})
        if info:
            doc["items"] = info.get("items", [])

    # ── 通用：Wiki 匹配 ──
    wiki_ref = match_wiki(name_en, wiki_index)
    if wiki_ref:
        doc["wiki_ref"] = wiki_ref

    # ── 词条完善度 ──
    doc["entry_completeness"] = compute_entry_completeness(doc)

    return doc


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────

def build_knowledge_base(output_dir: Path, sample_count: int = 0):
    """构建完整知识库。"""
    start = time.time()

    # 1. 加载数据
    loader = DataLoader()
    loader.load_all()

    # 2. 加载 Wiki 索引
    print("\n📖 加载 Wiki 文章...")
    wiki_index = load_wiki_index(WIKI_DIR)
    print(f"   {len(wiki_index)} 篇 Wiki 文章")

    # 3. 构建实体文档
    print("\n🔧 构建实体文档...")
    output_dir.mkdir(parents=True, exist_ok=True)
    entities_dir = output_dir / "entities"
    # 清理旧数据，避免残留文件干扰
    if entities_dir.exists():
        shutil.rmtree(entities_dir)
    entities_dir.mkdir(exist_ok=True)

    total = 0
    by_type = defaultdict(int)
    by_tier = defaultdict(int)
    wiki_matched = 0
    index_entries = []
    sample_docs = []

    seen_entity_ids = set()  # 去重：同一 entity_type+entity_id 只保留第一个

    for entity_type in ENTITY_TYPES:
        type_dir = ASSETS_DIR / entity_type
        if not type_dir.exists():
            continue

        out_type_dir = entities_dir / entity_type
        out_type_dir.mkdir(exist_ok=True)

        files = sorted(os.listdir(type_dir))
        for fn in files:
            if not fn.endswith(".json"):
                continue
            try:
                with open(type_dir / fn) as f:
                    entity = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            doc = build_entity_doc(entity, entity_type, loader, wiki_index)
            if doc is None:
                continue

            # 去重：resolved_assets 可能对同一 entity_id 产生多个文件
            eid = doc["entity_id"]
            dedup_key = f"{entity_type}:{eid}"
            if dedup_key in seen_entity_ids:
                continue
            seen_entity_ids.add(dedup_key)

            # 保存
            safe_name = re.sub(r'[<>:"|?*\\/]', '_', eid)[:200]
            out_path = out_type_dir / f"{safe_name}.json"

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)

            total += 1
            by_type[entity_type] += 1
            by_tier[doc["entry_completeness"]] += 1
            if doc.get("wiki_ref"):
                wiki_matched += 1

            # 索引
            index_entries.append({
                "entity_id": eid,
                "entity_type": entity_type,
                "name_en": doc.get("name_en", ""),
                "name_zh": doc.get("name_zh", ""),
                "source_mod": doc.get("source_mod", ""),
                "entry_completeness": doc["entry_completeness"],
                "file": str(out_path.relative_to(output_dir)),
            })

            # 采样
            if sample_count > 0 and len(sample_docs) < sample_count:
                if total % max(1, len(files) // 3) == 0:
                    sample_docs.append(doc)

        print(f"   {entity_type:15s}: {by_type[entity_type]:>6}")

    # 4. 复制 Wiki 文章
    print(f"\n📖 复制 Wiki 文章...")
    wiki_out = output_dir / "wiki"
    wiki_count = 0
    if WIKI_DIR.exists():
        for subdir in WIKI_DIR.iterdir():
            if subdir.is_dir():
                out_sub = wiki_out / subdir.name
                out_sub.mkdir(parents=True, exist_ok=True)
                for md in subdir.glob("*.md"):
                    shutil.copy2(md, out_sub / md.name)
                    wiki_count += 1
                    # 添加到索引
                    index_entries.append({
                        "entity_id": md.stem,
                        "entity_type": "wiki",
                        "name_en": md.stem.replace("_", " "),
                        "name_zh": "",
                        "source_mod": subdir.name,
                        "entry_completeness": "S",
                        "file": f"wiki/{subdir.name}/{md.name}",
                    })
    print(f"   {wiki_count} 篇")

    # 5. 研究树单独保存（它是全局数据，不属于单个实体）
    if loader.research_trees:
        rt_path = output_dir / "research_trees.json"
        with open(rt_path, "w", encoding="utf-8") as f:
            json.dump(loader.research_trees, f, ensure_ascii=False, indent=2)
        print(f"\n🌳 研究树: {len(loader.research_trees)} 棵")

    # 6. 写索引
    index_path = output_dir / "index.jsonl"
    with open(index_path, "w", encoding="utf-8") as f:
        for entry in sorted(index_entries, key=lambda x: (x["entity_type"], x.get("entity_id", ""))):
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # 7. 元数据
    meta = {
        "total_entities": total,
        "wiki_articles": wiki_count,
        "total_documents": total + wiki_count,
        "by_type": dict(sorted(by_type.items())),
        "by_entry_completeness": dict(sorted(by_tier.items())),
        "wiki_matched": wiki_matched,
        "build_time_seconds": round(time.time() - start, 1),
    }
    with open(output_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 8. 打印统计
    elapsed = time.time() - start
    print(f"\n{'═' * 60}")
    print(f"  💾 知识库构建完成!")
    print(f"{'═' * 60}")
    print(f"  输出目录: {output_dir.resolve()}")
    print(f"  实体文档: {total}")
    print(f"  Wiki 文章: {wiki_count}")
    print(f"  总文档数: {total + wiki_count}")
    print(f"  Wiki 匹配: {wiki_matched} 个实体关联了 Wiki")
    print(f"  词条完善度:")
    for tier in ["S", "A", "B", "C", "D"]:
        count = by_tier.get(tier, 0)
        pct = count / total * 100 if total else 0
        bar = "█" * int(pct / 2)
        print(f"    {tier}: {count:>6} ({pct:.1f}%) {bar}")
    print(f"  耗时: {elapsed:.1f}s")
    print(f"{'═' * 60}")

    # 采样展示
    if sample_docs:
        print(f"\n📋 随机采样 {len(sample_docs)} 个文档:")
        for doc in sample_docs:
            print(f"\n  --- {doc['entity_id']} ({doc['entity_type']}) [{doc['entry_completeness']}] ---")
            print(f"  EN: {doc.get('name_en', '')}")
            print(f"  ZH: {doc.get('name_zh', '')}")
            if doc.get("recipes_output"):
                print(f"  配方产出: {len(doc['recipes_output'])} 种做法")
            if doc.get("recipes_input"):
                print(f"  配方用途: {doc['recipes_input']['total']} 个配方")
            if doc.get("drop_sources"):
                print(f"  掉落来源: {doc['drop_sources']['total_pools']} 个 pool")
            if doc.get("wiki_ref"):
                print(f"  Wiki: {doc['wiki_ref']}")


def _set_or_clear(doc: dict, key: str, value) -> bool:
    if value:
        if doc.get(key) != value:
            doc[key] = value
            return True
        return False
    if key in doc:
        del doc[key]
        return True
    return False


def patch_extraction_fields(output_dir: Path) -> int:
    """给已有知识库文档补 extracted_from / extracts_into，避免全量重建。"""
    return patch_machine_fields(output_dir, extraction=True, processing=False)


def patch_machine_fields(output_dir: Path, extraction: bool = True, processing: bool = True) -> int:
    """给已有知识库文档补萃取 / 离心 / 筛粉 / 碎岩 / 冷凝字段。"""
    loader = DataLoader()
    loader.load_all()
    patched = 0
    stats = defaultdict(int)
    types = ("item", "object", "liquid", "biome") if processing else ("item", "object", "liquid")
    for entity_type in types:
        type_dir = output_dir / "entities" / entity_type
        if not type_dir.exists():
            continue
        for path in type_dir.glob("*.json"):
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
            eid = doc.get("entity_id") or path.stem
            changed = False
            updates = {}
            if extraction and entity_type != "biome":
                updates["extracted_from"] = summarize_extracted_from(eid, loader)
                updates["extracts_into"] = summarize_extracts_into(eid, loader)
            if processing and entity_type != "biome":
                for family, from_key, into_key in (
                    ("centrifuge", "centrifuged_from", "centrifuges_into"),
                    ("sifter", "sifted_from", "sifts_into"),
                    ("crusher", "crushed_from", "crushes_into"),
                ):
                    updates[from_key] = summarize_process_from(eid, loader, family)
                    updates[into_key] = summarize_process_into(eid, loader, family)
                updates["condensed_on"] = summarize_condensed_on(eid, loader)
                if eid == "isn_atmoscondenser":
                    updates["atmosphere_outputs"] = summarize_atmosphere_machine(loader)
            if processing and entity_type == "biome":
                updates["condenser_outputs"] = summarize_condenser_outputs(eid, loader)
            for key, value in updates.items():
                if _set_or_clear(doc, key, value):
                    changed = True
                if value:
                    stats[key] += 1
            if not changed:
                continue
            doc["entry_completeness"] = compute_entry_completeness(doc)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
                f.write("\n")
            patched += 1
    print(f"机器字段已写入 {patched} 个文档 {dict(stats)}")
    return patched


def main():
    parser = argparse.ArgumentParser(description="知识库组装引擎")
    parser.add_argument("-o", "--output", type=Path, default=Path("knowledge_base"),
                        help="输出目录")
    parser.add_argument("--sample", type=int, default=0,
                        help="随机采样 N 个文档展示")
    parser.add_argument("--patch-extraction", action="store_true",
                        help="只给现有文档补萃取字段")
    parser.add_argument("--patch-processing", action="store_true",
                        help="只给现有文档补离心/筛粉/碎岩/冷凝字段")

    args = parser.parse_args()
    if args.patch_extraction or args.patch_processing:
        patch_machine_fields(
            args.output,
            extraction=args.patch_extraction,
            processing=args.patch_processing or not args.patch_extraction,
        )
        return
    build_knowledge_base(args.output, args.sample)


if __name__ == "__main__":
    main()
