#!/usr/bin/env python3
"""
recipe_index.py — 配方索引引擎

解析 resolved_assets/ 中的配方和机器加工数据，建立：
1. 正向索引：output_item → [recipe]  （怎么做这个物品）
2. 反向索引：input_item → [recipe]   （这个物品能做什么）
3. 工作站索引：station → [recipe]     （这个工作站能做什么）
4. 机器加工索引：machine → [(input, output, bonus)]

用法:
    python3 recipe_index.py --assets resolved_assets -o recipe_db
    python3 recipe_index.py --assets resolved_assets --query ironore
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


# ─────────────────────────────────────────────
# 索引构建
# ─────────────────────────────────────────────

class RecipeIndex:
    """配方索引数据库。"""

    def __init__(self):
        self.recipes: list[dict] = []
        self.machine_processing: list[dict] = []

        # 正向索引：output_item → [recipe_idx]
        self.output_index: dict[str, list[int]] = defaultdict(list)
        # 反向索引：input_item → [recipe_idx]
        self.input_index: dict[str, list[int]] = defaultdict(list)
        # 工作站索引：station_id → [recipe_idx]
        self.station_index: dict[str, list[int]] = defaultdict(list)

        # 机器加工索引
        self.machine_output_index: dict[str, list[int]] = defaultdict(list)
        self.machine_input_index: dict[str, list[int]] = defaultdict(list)

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
            "unique_outputs": len(self.output_index),
            "unique_inputs": len(self.input_index),
            "unique_stations": len(self.station_index),
        }
        with open(output_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        print(f"\n💾 输出目录: {output_dir.resolve()}")
        print(f"   recipes.jsonl: {len(self.recipes)} 条配方")
        print(f"   machine_processing.jsonl: {len(self.machine_processing)} 条机器规则")
        print(f"   station_map.json: {len(self.station_map)} 个 group→station 映射")
        print(f"   output_index.json: {len(self.output_index)} 个物品产出索引")
        print(f"   input_index.json: {len(self.input_index)} 个材料使用索引")


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

    args = parser.parse_args()

    if not args.assets.exists():
        print(f"❌ 目录不存在: {args.assets}", file=sys.stderr)
        sys.exit(1)

    idx = RecipeIndex()
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

        print(f"\n{'═' * 60}")
    else:
        idx.save(args.output)


if __name__ == "__main__":
    main()
