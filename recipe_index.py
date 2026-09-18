#!/usr/bin/env python3
"""
recipe_index.py — 配方索引引擎

解析 resolved_assets/ 中的配方和机器加工数据，建立：
1. 正向索引：output_item → [recipe]  （怎么做这个物品）
2. 反向索引：input_item → [recipe]   （这个物品能做什么）
3. 工作站索引：station → [recipe]     （这个工作站能做什么）
4. 机器加工索引：machine → [(input, output, bonus)]
5. 萃取索引：extractionlab_recipes（研磨机 / 物质萃取器 / 量子萃取器）
6. 离心/筛粉/碎岩：centrifuge_recipes（按 centrifugeType 分表）
7. 空气冷凝器：按星球类型出货

用法:
    python3 recipe_index.py --assets resolved_assets -o recipe_db
    python3 recipe_index.py --assets resolved_assets --query ironore
    python3 recipe_index.py --processing-only --query liquidoil
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path


# ─────────────────────────────────────────────
# Recipe group → 工作站名称的映射
# ─────────────────────────────────────────────

def build_station_map(assets_dir: Path) -> dict[str, list[dict]]:
    """
    从 object 和 config 文件中建立 recipe_group → station 的映射。

    返回: {group_name: [{station_id, station_name, station_name_zh}]}
    """
    group_to_stations = defaultdict(list)

    def _clean_color(text: str) -> str:
        return re.sub(r'\^[^;]*;', '', text)

    def _register_filters(filters: list, station_info: dict):
        for g in filters:
            if g:
                group_to_stations[g].append(station_info)

    # 1. 从 object 文件扫描
    object_dir = assets_dir / "object"
    if object_dir.exists():
        for fn in os.listdir(object_dir):
            if not fn.endswith(".json"):
                continue
            try:
                with open(object_dir / fn) as f:
                    d = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            if not isinstance(d, dict):
                continue

            obj_name = d.get("objectName", "")
            raw_name = _clean_color(d.get("shortdescription", "")).strip()
            meta = d.get("_meta", {})
            zh = meta.get("zh", {})
            name_zh = _clean_color(zh.get("shortdescription_zh", "")).strip()
            # 中文 patch 可能已覆盖 shortdescription，此时 raw_name 就是中文
            # 优先用 _meta.zh 作为中文名，raw_name 可能是英文也可能是中文
            station_name_zh = name_zh or raw_name

            station_info = {
                "station_id": obj_name,
                "station_name": raw_name,
                "station_name_zh": station_name_zh,
            }

            # interactData.filter (顶层)
            interact = d.get("interactData", {})
            if isinstance(interact, dict):
                _register_filters(interact.get("filter", []), station_info)

            # upgradeStages[].interactData.filter (可升级工作站)
            for stage in d.get("upgradeStages", []):
                if not isinstance(stage, dict):
                    continue
                stage_interact = stage.get("interactData", {})
                if isinstance(stage_interact, dict):
                    stage_filters = stage_interact.get("filter", [])
                    if stage_filters:
                        stage_params = stage.get("itemSpawnParameters", {})
                        # stage 的 shortdescription 已被中文 patch 覆盖，就是该阶段的正确名称
                        stage_raw = _clean_color(stage_params.get("shortdescription", "")).strip()
                        stage_info = {
                            "station_id": obj_name,
                            "station_name": stage_raw or raw_name,
                            "station_name_zh": stage_raw or station_name_zh,
                        }
                        _register_filters(stage_filters, stage_info)

            # recipeGroup (centrifuge 等机器)
            rg = d.get("recipeGroup", "")
            if rg:
                group_to_stations[rg].append(station_info)

    # 2. 从 config 文件扫描（UI 配置也定义 filter）
    config_dir = assets_dir / "config"
    if config_dir.exists():
        for fn in os.listdir(config_dir):
            if not fn.endswith(".json"):
                continue
            try:
                with open(config_dir / fn) as f:
                    d = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            if not isinstance(d, dict):
                continue

            filt = d.get("filter", [])
            title = d.get("title", "")
            if filt and isinstance(filt, list):
                for g in filt:
                    if g and not any(s["station_id"] == fn for s in group_to_stations.get(g, [])):
                        group_to_stations[g].append({
                            "station_id": f"config:{fn}",
                            "station_name": title or fn,
                            "station_name_zh": "",
                        })

    # 去重
    for g in group_to_stations:
        seen = set()
        deduped = []
        for s in group_to_stations[g]:
            key = s["station_id"]
            if key not in seen:
                seen.add(key)
                deduped.append(s)
        group_to_stations[g] = deduped

    return dict(group_to_stations)


# ─────────────────────────────────────────────
# 配方解析
# ─────────────────────────────────────────────

def parse_recipes(assets_dir: Path, station_map: dict) -> list[dict]:
    """
    解析所有 .recipe 文件。

    返回 recipe 列表，每个包含:
    - recipe_id, output_item, output_count
    - inputs: [{item, count}]
    - groups: [str]
    - stations: [{station_id, station_name, station_name_zh}]
    - source_mod
    """
    recipe_dir = assets_dir / "recipe"
    if not recipe_dir.exists():
        return []

    recipes = []
    for fn in sorted(os.listdir(recipe_dir)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(recipe_dir / fn) as f:
                d = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        if not isinstance(d, dict):
            continue

        output = d.get("output", {})
        output_item = output.get("item", "") if isinstance(output, dict) else ""
        output_count = output.get("count", 1) if isinstance(output, dict) else 1

        inputs = []
        for inp in d.get("input", []):
            if isinstance(inp, dict):
                inputs.append({
                    "item": inp.get("item", ""),
                    "count": inp.get("count", 1),
                })

        groups = d.get("groups", [])
        meta = d.get("_meta", {})

        # 映射到工作站
        stations = []
        seen_stations = set()
        for g in groups:
            for s in station_map.get(g, []):
                if s["station_id"] not in seen_stations:
                    seen_stations.add(s["station_id"])
                    stations.append(s)

        recipe = {
            "recipe_id": meta.get("entity_id", fn.replace(".json", "")),
            "output_item": output_item,
            "output_count": output_count,
            "inputs": inputs,
            "groups": groups,
            "stations": stations,
            "source_mod": meta.get("source_mod", ""),
            "duration": d.get("duration"),
        }
        recipes.append(recipe)

    return recipes


# ─────────────────────────────────────────────
# 机器加工解析 (inputsToOutputs)
# ─────────────────────────────────────────────

def parse_machine_processing(assets_dir: Path) -> list[dict]:
    """
    从 object 文件中提取 inputsToOutputs 和 bonusOutputs 数据。

    这些是 electric furnace / blast furnace 等不使用 .recipe 文件的机器。
    """
    object_dir = assets_dir / "object"
    if not object_dir.exists():
        return []

    processing = []

    for fn in sorted(os.listdir(object_dir)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(object_dir / fn) as f:
                d = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        if not isinstance(d, dict):
            continue

        i2o = d.get("inputsToOutputs", {})
        bonus = d.get("bonusOutputs", {})

        if not i2o:
            continue

        machine_id = d.get("objectName", fn.replace(".json", ""))
        machine_name = re.sub(r'\^[^;]*;', '', d.get("shortdescription", ""))
        meta = d.get("_meta", {})
        zh = meta.get("zh", {})
        machine_name_zh = re.sub(r'\^[^;]*;', '', zh.get("shortdescription_zh", ""))

        for inp_item, out_item in i2o.items():
            entry = {
                "type": "machine_processing",
                "machine_id": machine_id,
                "machine_name": machine_name,
                "machine_name_zh": machine_name_zh,
                "input_item": inp_item,
                "output_item": out_item,
                "source_mod": meta.get("source_mod", ""),
            }
            # 副产物
            if inp_item in bonus:
                entry["bonus_outputs"] = bonus[inp_item]
            processing.append(entry)

    return processing


# 萃取实验室族：Hand Mill / Extraction Lab 用 basic，MKII 用 advanced，量子用 quantum
EXTRACTION_STATIONS = [
    {"id": "handmill", "name": "Hand Mill", "name_zh": "研磨机", "tier": "basic"},
    {"id": "extractionlab", "name": "Extraction Lab", "name_zh": "物质萃取器", "tier": "basic"},
    {"id": "extractionlabadv", "name": "Extraction Lab MKII", "name_zh": "物质萃取器 MKII", "tier": "advanced"},
    {"id": "quantumextractor", "name": "Quantum Extractor", "name_zh": "量子萃取器", "tier": "quantum"},
]
EXTRACTION_STATION_LABEL = "研磨机 / 物质萃取器 / 物质萃取器 MKII / 量子萃取器"


def find_extraction_config(assets_dir: Path) -> Path | None:
    """优先用合并后的 extractionlab_recipes，跳过单 mod 副本。"""
    config_dir = assets_dir / "config"
    if not config_dir.exists():
        return None
    merged, mods = [], []
    for fn in os.listdir(config_dir):
        if "extractionlab_recipes" not in fn or not fn.endswith(".json"):
            continue
        path = config_dir / fn
        if re.search(r"\.config__[A-Za-z]", fn):
            mods.append(path)
        else:
            merged.append(path)
    if merged:
        return sorted(merged)[0]
    if mods:
        return sorted(mods)[0]
    return None


def _normalize_extract_count(raw) -> dict:
    """产量可能是数字或 [basic, advanced, quantum]。"""
    if isinstance(raw, (int, float)):
        n = int(raw)
        return {"basic": n, "advanced": n, "quantum": n}
    if isinstance(raw, list) and raw:
        vals = [int(x) for x in raw[:3]]
        while len(vals) < 3:
            vals.append(vals[-1])
        return {"basic": vals[0], "advanced": vals[1], "quantum": vals[2]}
    return {"basic": 1, "advanced": 1, "quantum": 1}


def parse_extraction_recipes(assets_dir: Path) -> list[dict]:
    """从 extractionlab_recipes.config 抽出萃取规则（一行一个产出）。"""
    chosen = find_extraction_config(assets_dir)
    if chosen is None:
        return []

    try:
        with open(chosen, encoding="utf-8") as f:
            doc = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return []

    rows = doc.get("_raw") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        return []

    source_mod = ""
    if isinstance(doc, dict):
        source_mod = (doc.get("_meta") or {}).get("source_mod", "") or "Frackin' Universe"

    recipes = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        inputs_raw = row.get("inputs") or {}
        outputs_raw = row.get("outputs") or {}
        if not isinstance(inputs_raw, dict) or not isinstance(outputs_raw, dict):
            continue
        inputs = [
            {"item": str(k), "count": int(v) if isinstance(v, (int, float)) else 1}
            for k, v in inputs_raw.items() if k
        ]
        if not inputs:
            continue
        for out_item, out_raw in outputs_raw.items():
            if not out_item:
                continue
            recipes.append({
                "type": "extraction",
                "inputs": inputs,
                "output_item": str(out_item),
                "output_count": _normalize_extract_count(out_raw),
                "source_mod": source_mod,
            })
    return recipes


def find_resolved_file(directory: Path, needle: str) -> Path | None:
    """优先用合并资源，跳过 __FrackinUniverse 这类单 mod 副本。"""
    if not directory.exists():
        return None
    merged, mods = [], []
    for fn in os.listdir(directory):
        if needle not in fn or not fn.endswith(".json"):
            continue
        path = directory / fn
        if re.search(r"__[A-Za-z][A-Za-z0-9]+\.json$", fn):
            mods.append(path)
        else:
            merged.append(path)
    if merged:
        return sorted(merged)[0]
    if mods:
        return sorted(mods)[0]
    return None


# 离心机 / 筛粉机 / 碎岩机：同一张 centrifuge_recipes，按 map 选机器
CENTRIFUGE_MAP_FAMILY = {
    "itemMapFarm": "centrifuge",
    "itemMapBees": "centrifuge",
    "itemMapLiquids": "centrifuge",
    "itemMapIsotopes": "centrifuge",
    "itemMapPowder": "sifter",
    "itemMapRocks": "crusher",
}

CENTRIFUGE_STATIONS_BY_MAP = {
    "itemMapFarm": [
        {"id": "woodencentrifuge", "name_zh": "木制离心机"},
        {"id": "ironcentrifuge", "name_zh": "铁制离心机"},
        {"id": "industrialcentrifuge", "name_zh": "工业用离心机"},
        {"id": "centrifuge", "name_zh": "实验室离心机"},
        {"id": "centrifuge2", "name_zh": "气体离心机"},
    ],
    "itemMapBees": [
        {"id": "woodencentrifuge", "name_zh": "木制离心机"},
        {"id": "ironcentrifuge", "name_zh": "铁制离心机"},
        {"id": "industrialcentrifuge", "name_zh": "工业用离心机"},
        {"id": "centrifuge", "name_zh": "实验室离心机"},
        {"id": "centrifuge2", "name_zh": "气体离心机"},
    ],
    "itemMapLiquids": [
        {"id": "ironcentrifuge", "name_zh": "铁制离心机"},
        {"id": "industrialcentrifuge", "name_zh": "工业用离心机"},
        {"id": "centrifuge", "name_zh": "实验室离心机"},
        {"id": "centrifuge2", "name_zh": "气体离心机"},
    ],
    "itemMapIsotopes": [
        {"id": "centrifuge2", "name_zh": "气体离心机"},
    ],
    "itemMapPowder": [
        {"id": "fu_woodensifter", "name_zh": "木制筛粉机"},
        {"id": "isn_powdersifter", "name_zh": "高级筛粉机"},
        {"id": "precursorsmelter", "name_zh": "先驱熔炉"},
    ],
    "itemMapRocks": [
        {"id": "fu_rockcrusher", "name_zh": "碎岩机"},
        {"id": "fu_rockbreaker", "name_zh": "破岩机"},
        {"id": "precursorsmelter", "name_zh": "先驱熔炉"},
    ],
}


def _station_label(stations: list[dict]) -> str:
    return " / ".join(s.get("name_zh") or s.get("id", "") for s in stations if s)


def parse_centrifuge_recipes(assets_dir: Path) -> list[dict]:
    """离心/筛粉/碎岩：output 带稀有度，不是固定数量。"""
    chosen = find_resolved_file(assets_dir / "config", "centrifuge_recipes")
    if chosen is None:
        return []
    try:
        with open(chosen, encoding="utf-8") as f:
            doc = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return []
    if not isinstance(doc, dict):
        return []
    source_mod = (doc.get("_meta") or {}).get("source_mod", "") or "Frackin' Universe"
    recipes = []
    for map_name, family in CENTRIFUGE_MAP_FAMILY.items():
        mapping = doc.get(map_name)
        if not isinstance(mapping, dict):
            continue
        stations = CENTRIFUGE_STATIONS_BY_MAP.get(map_name) or []
        label = _station_label(stations)
        for inp, outputs in mapping.items():
            if not inp or not isinstance(outputs, dict):
                continue
            for out_item, pair in outputs.items():
                if not out_item:
                    continue
                rarity, weight = "common", 1
                if isinstance(pair, list) and pair:
                    rarity = str(pair[0])
                    if len(pair) > 1 and isinstance(pair[1], (int, float)):
                        weight = int(pair[1])
                elif isinstance(pair, str):
                    rarity = pair
                recipes.append({
                    "type": "centrifuge",
                    "family": family,
                    "map": map_name,
                    "input_item": str(inp),
                    "output_item": str(out_item),
                    "rarity": rarity,
                    "weight": weight,
                    "stations": label,
                    "source_mod": source_mod,
                })
    return recipes


def parse_atmos_outputs(assets_dir: Path) -> list[dict]:
    """空气冷凝器：按 world.type() 出货，无消耗原料。"""
    chosen = find_resolved_file(assets_dir / "object", "isn_atmoscondenser.json")
    if chosen is None:
        chosen = find_resolved_file(assets_dir / "object", "isn_atmoscondenser")
    if chosen is None:
        return []
    try:
        with open(chosen, encoding="utf-8") as f:
            doc = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return []
    outputs = doc.get("outputs") if isinstance(doc, dict) else None
    if not isinstance(outputs, dict):
        return []
    source_mod = ((doc.get("_meta") or {}).get("source_mod") if isinstance(doc, dict) else "") or "Frackin' Universe"
    rows = []
    for biome, table in outputs.items():
        if not biome:
            continue
        alias_of = table if isinstance(table, str) else None
        resolved = table
        seen = set()
        while isinstance(resolved, str) and resolved not in seen:
            seen.add(resolved)
            resolved = outputs.get(resolved)
        if not isinstance(resolved, list):
            continue
        for bucket in resolved:
            if not isinstance(bucket, dict):
                continue
            rarity = str(bucket.get("weight") or "common")
            for item in bucket.get("items") or []:
                if not item:
                    continue
                rows.append({
                    "type": "atmos",
                    "biome": str(biome),
                    "alias_of": alias_of,
                    "output_item": str(item),
                    "rarity": rarity,
                    "station": "空气冷凝器",
                    "station_id": "isn_atmoscondenser",
                    "source_mod": source_mod,
                })
    return rows


# ─────────────────────────────────────────────
# 索引构建
# ─────────────────────────────────────────────

class RecipeIndex:
    """配方索引数据库。"""

    def __init__(self):
        self.recipes: list[dict] = []
        self.machine_processing: list[dict] = []
        self.extractions: list[dict] = []
        self.centrifuges: list[dict] = []
        self.atmos: list[dict] = []

        # 正向索引：output_item → [recipe_idx]
        self.output_index: dict[str, list[int]] = defaultdict(list)
        # 反向索引：input_item → [recipe_idx]
        self.input_index: dict[str, list[int]] = defaultdict(list)
        # 工作站索引：station_id → [recipe_idx]
        self.station_index: dict[str, list[int]] = defaultdict(list)

        # 机器加工索引
        self.machine_output_index: dict[str, list[int]] = defaultdict(list)
        self.machine_input_index: dict[str, list[int]] = defaultdict(list)
        self.extraction_output_index: dict[str, list[int]] = defaultdict(list)
        self.extraction_input_index: dict[str, list[int]] = defaultdict(list)
        self.centrifuge_output_index: dict[str, list[int]] = defaultdict(list)
        self.centrifuge_input_index: dict[str, list[int]] = defaultdict(list)
        self.atmos_output_index: dict[str, list[int]] = defaultdict(list)
        self.atmos_biome_index: dict[str, list[int]] = defaultdict(list)

        self.station_map: dict = {}

    def build(self, assets_dir: Path):
        """构建所有索引。"""
        print("🔧 构建工作站映射...")
        self.station_map = build_station_map(assets_dir)
        print(f"   {len(self.station_map)} 个 recipe group 映射到工作站")

        print("📋 解析配方...")
        self.recipes = parse_recipes(assets_dir, self.station_map)
        print(f"   {len(self.recipes)} 个配方")

        print("⚙️  解析机器加工...")
        self.machine_processing = parse_machine_processing(assets_dir)
        print(f"   {len(self.machine_processing)} 条机器加工规则")

        print("🧪 解析萃取配方...")
        self._index_extractions(parse_extraction_recipes(assets_dir))
        print(f"   {len(self.extractions)} 条萃取产出")

        print("🌀 解析离心/筛粉/碎岩...")
        self._index_centrifuges(parse_centrifuge_recipes(assets_dir))
        print(f"   {len(self.centrifuges)} 条概率产出")

        print("🌬️  解析空气冷凝器...")
        self._index_atmos(parse_atmos_outputs(assets_dir))
        print(f"   {len(self.atmos)} 条冷凝产出")

        print("📇 构建索引...")
        for i, r in enumerate(self.recipes):
            if r["output_item"]:
                self.output_index[r["output_item"]].append(i)
            for inp in r["inputs"]:
                if inp["item"]:
                    self.input_index[inp["item"]].append(i)
            for s in r.get("stations", []):
                self.station_index[s["station_id"]].append(i)

        for i, mp in enumerate(self.machine_processing):
            self.machine_output_index[mp["output_item"]].append(i)
            self.machine_input_index[mp["input_item"]].append(i)

        print(f"   output 索引: {len(self.output_index)} 个物品")
        print(f"   input 索引: {len(self.input_index)} 个材料")
        print(f"   station 索引: {len(self.station_index)} 个工作站")
        print(f"   machine output 索引: {len(self.machine_output_index)} 个产出")
        print(f"   machine input 索引: {len(self.machine_input_index)} 个输入")
        print(f"   extraction output 索引: {len(self.extraction_output_index)} 个产出")
        print(f"   extraction input 索引: {len(self.extraction_input_index)} 个输入")
        print(f"   centrifuge output 索引: {len(self.centrifuge_output_index)} 个产出")
        print(f"   centrifuge input 索引: {len(self.centrifuge_input_index)} 个输入")
        print(f"   atmos output 索引: {len(self.atmos_output_index)} 个产出")

    def _index_extractions(self, recipes: list[dict]):
        self.extractions = recipes
        self.extraction_output_index = defaultdict(list)
        self.extraction_input_index = defaultdict(list)
        for i, ex in enumerate(self.extractions):
            if ex.get("output_item"):
                self.extraction_output_index[ex["output_item"]].append(i)
            for inp in ex.get("inputs") or []:
                if inp.get("item"):
                    self.extraction_input_index[inp["item"]].append(i)

    def _index_centrifuges(self, recipes: list[dict]):
        self.centrifuges = recipes
        self.centrifuge_output_index = defaultdict(list)
        self.centrifuge_input_index = defaultdict(list)
        for i, row in enumerate(self.centrifuges):
            if row.get("output_item"):
                self.centrifuge_output_index[row["output_item"]].append(i)
            if row.get("input_item"):
                self.centrifuge_input_index[row["input_item"]].append(i)

    def _index_atmos(self, recipes: list[dict]):
        self.atmos = recipes
        self.atmos_output_index = defaultdict(list)
        self.atmos_biome_index = defaultdict(list)
        for i, row in enumerate(self.atmos):
            if row.get("output_item"):
                self.atmos_output_index[row["output_item"]].append(i)
            if row.get("biome"):
                self.atmos_biome_index[row["biome"]].append(i)

    def build_extraction_only(self, assets_dir: Path):
        """只解析萃取配置，不重扫全部 .recipe。"""
        print("🧪 解析萃取配方...")
        self._index_extractions(parse_extraction_recipes(assets_dir))
        print(f"   {len(self.extractions)} 条萃取产出")
        print(f"   extraction output 索引: {len(self.extraction_output_index)} 个产出")
        print(f"   extraction input 索引: {len(self.extraction_input_index)} 个输入")

    def build_processing_only(self, assets_dir: Path):
        """只解析离心/筛粉/碎岩和空气冷凝器。"""
        print("🌀 解析离心/筛粉/碎岩...")
        self._index_centrifuges(parse_centrifuge_recipes(assets_dir))
        print(f"   {len(self.centrifuges)} 条概率产出")
        print("🌬️  解析空气冷凝器...")
        self._index_atmos(parse_atmos_outputs(assets_dir))
        print(f"   {len(self.atmos)} 条冷凝产出")

    def query_item(self, item_id: str) -> dict:
        """
        查询一个物品的所有配方信息。

        返回:
        - produced_by: 怎么做这个物品（配方列表）
        - used_in: 这个物品能用来做什么（配方列表）
        - machine_produced_by: 哪些机器能产出这个物品
        - machine_used_in: 这个物品能被哪些机器加工
        """
        result = {
            "item_id": item_id,
            "produced_by": [],
            "used_in": [],
            "machine_produced_by": [],
            "machine_used_in": [],
            "extracted_from": [],
            "extracts_into": [],
            "centrifuged_from": [],
            "centrifuges_into": [],
            "condensed_on": [],
        }

        # 配方产出
        for idx in self.output_index.get(item_id, []):
            r = self.recipes[idx]
            result["produced_by"].append({
                "recipe_id": r["recipe_id"],
                "inputs": r["inputs"],
                "output_count": r["output_count"],
                "stations": r["stations"],
                "source_mod": r["source_mod"],
            })

        # 配方使用
        for idx in self.input_index.get(item_id, []):
            r = self.recipes[idx]
            result["used_in"].append({
                "recipe_id": r["recipe_id"],
                "output_item": r["output_item"],
                "output_count": r["output_count"],
                "all_inputs": r["inputs"],
                "stations": r["stations"],
                "source_mod": r["source_mod"],
            })

        # 机器产出
        for idx in self.machine_output_index.get(item_id, []):
            result["machine_produced_by"].append(self.machine_processing[idx])

        # 机器使用
        for idx in self.machine_input_index.get(item_id, []):
            result["machine_used_in"].append(self.machine_processing[idx])

        for idx in self.extraction_output_index.get(item_id, []):
            result["extracted_from"].append(self.extractions[idx])
        for idx in self.extraction_input_index.get(item_id, []):
            result["extracts_into"].append(self.extractions[idx])
        for idx in self.centrifuge_output_index.get(item_id, []):
            result["centrifuged_from"].append(self.centrifuges[idx])
        for idx in self.centrifuge_input_index.get(item_id, []):
            result["centrifuges_into"].append(self.centrifuges[idx])
        for idx in self.atmos_output_index.get(item_id, []):
            result["condensed_on"].append(self.atmos[idx])

        return result

    def save(self, output_dir: Path):
        """保存索引到文件。"""
        output_dir.mkdir(parents=True, exist_ok=True)

        # 保存完整配方列表
        with open(output_dir / "recipes.jsonl", "w", encoding="utf-8") as f:
            for r in self.recipes:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        # 保存机器加工列表
        with open(output_dir / "machine_processing.jsonl", "w", encoding="utf-8") as f:
            for mp in self.machine_processing:
                f.write(json.dumps(mp, ensure_ascii=False) + "\n")

        self.save_extraction(output_dir, update_meta=False)
        self.save_processing(output_dir, update_meta=False)

        # 保存工作站映射
        with open(output_dir / "station_map.json", "w", encoding="utf-8") as f:
            json.dump(self.station_map, f, ensure_ascii=False, indent=2)

        # 保存正向/反向索引（item → [行号]，用行号避免 recipe_id 重复导致覆盖）
        output_idx = {k: v for k, v in self.output_index.items()}
        with open(output_dir / "output_index.json", "w", encoding="utf-8") as f:
            json.dump(output_idx, f, ensure_ascii=False, indent=2)

        input_idx = {k: v for k, v in self.input_index.items()}
        with open(output_dir / "input_index.json", "w", encoding="utf-8") as f:
            json.dump(input_idx, f, ensure_ascii=False, indent=2)

        # 保存元数据
        meta = {
            "total_recipes": len(self.recipes),
            "total_machine_rules": len(self.machine_processing),
            "total_extractions": len(self.extractions),
            "unique_extraction_outputs": len(self.extraction_output_index),
            "unique_extraction_inputs": len(self.extraction_input_index),
            "total_centrifuge_pairs": len(self.centrifuges),
            "unique_centrifuge_outputs": len(self.centrifuge_output_index),
            "unique_centrifuge_inputs": len(self.centrifuge_input_index),
            "total_atmos_rows": len(self.atmos),
            "unique_atmos_outputs": len(self.atmos_output_index),
            "unique_atmos_biomes": len(self.atmos_biome_index),
            "unique_outputs": len(self.output_index),
            "unique_inputs": len(self.input_index),
            "unique_stations": len(self.station_index),
        }
        with open(output_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        print(f"\n💾 输出目录: {output_dir.resolve()}")
        print(f"   recipes.jsonl: {len(self.recipes)} 条配方")
        print(f"   machine_processing.jsonl: {len(self.machine_processing)} 条机器规则")
        print(f"   extraction.jsonl: {len(self.extractions)} 条萃取产出")
        print(f"   centrifuge.jsonl: {len(self.centrifuges)} 条概率产出")
        print(f"   atmos.jsonl: {len(self.atmos)} 条冷凝产出")
        print(f"   station_map.json: {len(self.station_map)} 个 group→station 映射")
        print(f"   output_index.json: {len(self.output_index)} 个物品产出索引")
        print(f"   input_index.json: {len(self.input_index)} 个材料使用索引")

    def save_extraction(self, output_dir: Path, update_meta: bool = True):
        """只写萃取索引，不覆盖配方文件。"""
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / "extraction.jsonl", "w", encoding="utf-8") as f:
            for ex in self.extractions:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        with open(output_dir / "extraction_output_index.json", "w", encoding="utf-8") as f:
            json.dump(dict(self.extraction_output_index), f, ensure_ascii=False, indent=2)
        with open(output_dir / "extraction_input_index.json", "w", encoding="utf-8") as f:
            json.dump(dict(self.extraction_input_index), f, ensure_ascii=False, indent=2)
        if update_meta:
            meta_path = output_dir / "metadata.json"
            meta = {}
            if meta_path.exists():
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
            meta["total_extractions"] = len(self.extractions)
            meta["unique_extraction_outputs"] = len(self.extraction_output_index)
            meta["unique_extraction_inputs"] = len(self.extraction_input_index)
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        print(f"   extraction.jsonl: {len(self.extractions)} 条萃取产出")
        print(f"   extraction outputs: {len(self.extraction_output_index)} / inputs: {len(self.extraction_input_index)}")

    def save_processing(self, output_dir: Path, update_meta: bool = True):
        """只写离心/筛粉/碎岩和空气冷凝器索引。"""
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / "centrifuge.jsonl", "w", encoding="utf-8") as f:
            for row in self.centrifuges:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        with open(output_dir / "centrifuge_output_index.json", "w", encoding="utf-8") as f:
            json.dump(dict(self.centrifuge_output_index), f, ensure_ascii=False, indent=2)
        with open(output_dir / "centrifuge_input_index.json", "w", encoding="utf-8") as f:
            json.dump(dict(self.centrifuge_input_index), f, ensure_ascii=False, indent=2)
        with open(output_dir / "atmos.jsonl", "w", encoding="utf-8") as f:
            for row in self.atmos:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        with open(output_dir / "atmos_output_index.json", "w", encoding="utf-8") as f:
            json.dump(dict(self.atmos_output_index), f, ensure_ascii=False, indent=2)
        with open(output_dir / "atmos_biome_index.json", "w", encoding="utf-8") as f:
            json.dump(dict(self.atmos_biome_index), f, ensure_ascii=False, indent=2)
        if update_meta:
            meta_path = output_dir / "metadata.json"
            meta = {}
            if meta_path.exists():
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
            meta["total_centrifuge_pairs"] = len(self.centrifuges)
            meta["unique_centrifuge_outputs"] = len(self.centrifuge_output_index)
            meta["unique_centrifuge_inputs"] = len(self.centrifuge_input_index)
            meta["total_atmos_rows"] = len(self.atmos)
            meta["unique_atmos_outputs"] = len(self.atmos_output_index)
            meta["unique_atmos_biomes"] = len(self.atmos_biome_index)
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        print(f"   centrifuge.jsonl: {len(self.centrifuges)} 条概率产出")
        print(f"   atmos.jsonl: {len(self.atmos)} 条冷凝产出")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="配方索引引擎")
    parser.add_argument("--assets", type=Path, default=Path("resolved_assets"),
                        help="resolved_assets 目录路径")
    parser.add_argument("-o", "--output", type=Path, default=Path("recipe_db"),
                        help="输出目录")
    parser.add_argument("--query", type=str, default=None,
                        help="查询物品 ID（测试模式）")
    parser.add_argument("--extraction-only", action="store_true",
                        help="只解析并写出萃取索引")
    parser.add_argument("--processing-only", action="store_true",
                        help="只解析并写出离心/筛粉/碎岩和空气冷凝器")

    args = parser.parse_args()

    if not args.assets.exists():
        print(f"❌ 目录不存在: {args.assets}", file=sys.stderr)
        sys.exit(1)

    idx = RecipeIndex()
    if args.extraction_only:
        idx.build_extraction_only(args.assets)
        if args.query:
            result = idx.query_item(args.query)
            print(f"\n🧪 萃取产出 {args.query}: {len(result['extracted_from'])}")
            for ex in result["extracted_from"][:15]:
                inputs_str = " + ".join(f"{i['item']}x{i['count']}" for i in ex["inputs"])
                oc = ex["output_count"]
                print(f"    {inputs_str} → {oc['basic']}/{oc['advanced']}/{oc['quantum']}")
            print(f"🧪 {args.query} 可萃取成: {len(result['extracts_into'])}")
            for ex in result["extracts_into"][:15]:
                oc = ex["output_count"]
                print(f"    → {ex['output_item']} {oc['basic']}/{oc['advanced']}/{oc['quantum']}")
            return
        idx.save_extraction(args.output)
        return

    if args.processing_only:
        idx.build_processing_only(args.assets)
        if args.query:
            result = idx.query_item(args.query)
            print(f"\n🌀 离心/筛粉/碎岩产出 {args.query}: {len(result['centrifuged_from'])}")
            for row in result["centrifuged_from"][:15]:
                print(f"    {row['input_item']} [{row['family']}/{row['rarity']}] @ {row['stations']}")
            print(f"🌀 {args.query} 可加工成: {len(result['centrifuges_into'])}")
            for row in result["centrifuges_into"][:15]:
                print(f"    → {row['output_item']} [{row['family']}/{row['rarity']}]")
            print(f"🌬️  空气冷凝器: {len(result['condensed_on'])}")
            for row in result["condensed_on"][:15]:
                print(f"    {row['biome']} [{row['rarity']}]")
            return
        idx.save_processing(args.output)
        return

    idx.build(args.assets)

    if args.query:
        # 测试模式
        result = idx.query_item(args.query)
        print(f"\n{'═' * 60}")
        print(f"  查询: {args.query}")
        print(f"{'═' * 60}")

        print(f"\n  📦 怎么做 {args.query}? ({len(result['produced_by'])} 个配方)")
        for r in result["produced_by"][:10]:
            inputs_str = " + ".join(f"{i['item']}x{i['count']}" for i in r["inputs"])
            stations_str = ", ".join(s["station_name"] or s["station_id"] for s in r["stations"][:3])
            print(f"    {inputs_str} → x{r['output_count']}")
            if stations_str:
                print(f"      工作站: {stations_str}")

        print(f"\n  🔨 {args.query} 能做什么? ({len(result['used_in'])} 个配方)")
        for r in result["used_in"][:10]:
            print(f"    → {r['output_item']}x{r['output_count']}  [{r['source_mod']}]")

        print(f"\n  ⚙️  机器产出 {args.query}? ({len(result['machine_produced_by'])} 条)")
        for mp in result["machine_produced_by"][:10]:
            bonus = mp.get("bonus_outputs", {})
            bonus_str = f" (副产物: {', '.join(bonus.keys())})" if bonus else ""
            print(f"    {mp['machine_name']} ({mp['machine_name_zh']}): {mp['input_item']} → {args.query}{bonus_str}")

        print(f"\n  ⚙️  机器加工 {args.query}? ({len(result['machine_used_in'])} 条)")
        for mp in result["machine_used_in"][:10]:
            bonus = mp.get("bonus_outputs", {})
            bonus_str = f" (副产物: {', '.join(bonus.keys())})" if bonus else ""
            print(f"    {mp['machine_name']} ({mp['machine_name_zh']}): {args.query} → {mp['output_item']}{bonus_str}")

        print(f"\n  🧪 萃取出 {args.query}? ({len(result['extracted_from'])} 条)")
        for ex in result["extracted_from"][:10]:
            inputs_str = " + ".join(f"{i['item']}x{i['count']}" for i in ex["inputs"])
            oc = ex["output_count"]
            print(f"    {inputs_str} → {oc['basic']}/{oc['advanced']}/{oc['quantum']}")

        print(f"\n{'═' * 60}")
    else:
        idx.save(args.output)


if __name__ == "__main__":
    main()
