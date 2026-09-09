#!/usr/bin/env python3
"""
relationship_extractors.py — 游戏实体关系提取

从 resolved_assets/ 提取 15 类交叉引用关系（配方和掉落由独立模块处理）。
每个提取器返回统一格式的关系列表。

用法:
    python3 relationship_extractors.py --assets resolved_assets -o relationship_db
    python3 relationship_extractors.py --assets resolved_assets --test
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────

def load_entities(assets_dir: Path, entity_type: str) -> list[dict]:
    """加载指定类型的所有实体。"""
    type_dir = assets_dir / entity_type
    if not type_dir.exists():
        return []
    entities = []
    for fn in os.listdir(type_dir):
        if not fn.endswith(".json"):
            continue
        try:
            with open(type_dir / fn) as f:
                entities.append(json.load(f))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    return entities


def clean_color(text: str) -> str:
    """清理 Starbound 颜色标记。"""
    return re.sub(r'\^[^;]*;', '', text) if text else ""


# ─────────────────────────────────────────────
# R1: 蓝图解锁
# ─────────────────────────────────────────────

def extract_blueprints(assets_dir: Path) -> dict[str, list[str]]:
    """
    提取 learnBlueprintsOnPickup 关系。

    返回: {item_id: [blueprint_item_id, ...]}
    即"捡起这个物品会解锁哪些蓝图"。
    """
    blueprints = {}
    for entity_type in ["item", "object"]:
        for entity in load_entities(assets_dir, entity_type):
            if not isinstance(entity, dict):
                continue
            bps = entity.get("learnBlueprintsOnPickup", [])
            if not bps:
                continue
            entity_id = (entity.get("itemName") or entity.get("objectName") or "")
            if entity_id:
                # bps 可以是 [{"item": "xxx"}, ...] 或 ["xxx", ...]
                bp_list = []
                for bp in bps:
                    if isinstance(bp, dict):
                        bp_list.append(bp.get("item", ""))
                    elif isinstance(bp, str):
                        bp_list.append(bp)
                bp_list = [b for b in bp_list if b]
                if bp_list:
                    blueprints[entity_id] = bp_list
    return blueprints


# ─────────────────────────────────────────────
# R2: 种子 ↔ 作物
# ─────────────────────────────────────────────

def extract_farmables(assets_dir: Path) -> list[dict]:
    """
    提取种子→作物关系。

    从 object 文件中找 farmable 类型，提取 stages 的产出。
    返回: [{seed_item, crop_items: [item_id, ...], object_name}]
    """
    farmables = []
    for entity in load_entities(assets_dir, "object"):
        if not isinstance(entity, dict):
            continue
        # farmable 通常有 "stages" 字段
        stages = entity.get("stages")
        if not stages or not isinstance(stages, list):
            continue
        obj_name = entity.get("objectName", "")
        if not obj_name:
            continue

        # 从最后阶段提取产出
        crop_items = set()
        for stage in stages:
            if not isinstance(stage, dict):
                continue
            harvest = stage.get("harvestPool")
            if harvest and isinstance(harvest, str):
                crop_items.add(harvest)
            # 也看 interactAction 里的 harvestPool
            interact = stage.get("interactAction")
            if interact and isinstance(interact, str) and "harvest" in interact.lower():
                pass  # harvestPool 已处理

        # 寻找种子 → 这个 farmable 的关系
        # 通常 seeds 在 item 文件里引用 objectName
        # 这里先记录 farmable 本身
        if crop_items:
            farmables.append({
                "farmable_object": obj_name,
                "harvest_pools": sorted(crop_items),
                "short_en": clean_color(entity.get("shortdescription", "")),
                "short_zh": clean_color(
                    entity.get("_meta", {}).get("zh", {}).get("shortdescription_zh", "")
                ),
            })

    # 从 item 里找种子引用
    seed_map = {}
    for entity in load_entities(assets_dir, "item"):
        if not isinstance(entity, dict):
            continue
        item_name = entity.get("itemName", "")
        # 种子通常有 objectName 字段指向 farmable
        obj_ref = entity.get("objectName", "")
        if obj_ref and item_name:
            seed_map[obj_ref] = item_name

    # 关联
    results = []
    for f in farmables:
        seed = seed_map.get(f["farmable_object"], "")
        results.append({
            "seed_item": seed,
            "farmable_object": f["farmable_object"],
            "harvest_pools": f["harvest_pools"],
            "name_en": f["short_en"],
            "name_zh": f["short_zh"],
        })

    return results


# ─────────────────────────────────────────────
# R3: 矿石 ↔ 生态
# ─────────────────────────────────────────────

def extract_biome_ores(assets_dir: Path) -> dict[str, list[dict]]:
    """
    提取生态中的矿石分布。

    biome 的 "ores" 字段引用 oredistributions.configfunctions 中定义的分布组，
    组里面是 [[概率, [[矿名, 权重], ...]], ...] 的结构。

    返回: {biome_name: [{ore, weight}, ...]}
    """
    # 1. 加载矿石分布定义
    ore_dists = {}
    config_dir = assets_dir / "config"
    for fn in os.listdir(config_dir) if config_dir.exists() else []:
        if "oredist" in fn.lower():
            try:
                with open(config_dir / fn) as f:
                    d = json.load(f)
                if isinstance(d, dict):
                    for group_name, group_def in d.items():
                        if group_name == "_meta":
                            continue
                        # 解析 [[prob, [[ore, weight], ...]], ...]
                        ores = []
                        if isinstance(group_def, list):
                            for entry in group_def:
                                if isinstance(entry, list) and len(entry) >= 2:
                                    ore_list = entry[1]
                                    if isinstance(ore_list, list):
                                        for ore_entry in ore_list:
                                            if isinstance(ore_entry, list) and len(ore_entry) >= 2:
                                                ore_name = ore_entry[0]
                                                weight = ore_entry[1]
                                                if weight > 0:
                                                    ores.append({"ore": ore_name, "weight": weight})
                        if ores:
                            ore_dists[group_name] = ores
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

    # 2. 遍历 biome，关联矿石分布
    biome_ores = {}
    for entity in load_entities(assets_dir, "biome"):
        if not isinstance(entity, dict):
            continue
        biome_name = entity.get("name", "")
        if not biome_name:
            continue

        ore_ref = entity.get("ores", "")
        if isinstance(ore_ref, str) and ore_ref in ore_dists:
            biome_ores[biome_name] = ore_dists[ore_ref]

    return biome_ores


# ─────────────────────────────────────────────
# R4: 种族效果
# ─────────────────────────────────────────────

def extract_race_effects(assets_dir: Path) -> dict[str, dict]:
    """
    提取种族效果（raceeffect 文件）。

    每个文件是一个种族，含 stats/diet/envEffects/liquidEffects/weaponEffects 等。
    返回: {race_name: {stats, diet, envEffects, ...}}
    """
    race_effects = {}
    for entity in load_entities(assets_dir, "raceeffect"):
        if not isinstance(entity, dict):
            continue
        meta = entity.get("_meta", {})
        # 文件名就是种族名
        race_name = meta.get("entity_id", "")
        if not race_name:
            continue

        info = {}

        # stats: 基础属性修正
        stats = entity.get("stats", [])
        if isinstance(stats, list):
            info["stats"] = [
                {k: v for k, v in s.items()}
                for s in stats if isinstance(s, dict)
            ]

        # diet: 饮食类型
        diet = entity.get("diet", "")
        if diet:
            info["diet"] = diet

        # envEffects: 环境效果
        env = entity.get("envEffects", {})
        if isinstance(env, dict) and env:
            info["envEffects"] = env

        # liquidEffects
        liq = entity.get("liquidEffects", {})
        if isinstance(liq, dict) and liq:
            info["liquidEffects"] = liq

        # weaponEffects
        wpn = entity.get("weaponEffects", {})
        if isinstance(wpn, dict) and wpn:
            info["weaponEffects"] = wpn

        # controlModifiers
        ctrl = entity.get("controlModifiers", {})
        if isinstance(ctrl, dict) and ctrl:
            info["controlModifiers"] = ctrl

        # tech
        tech = entity.get("tech", [])
        if tech:
            info["tech"] = tech

        if info:
            race_effects[race_name] = info

    return race_effects


# ─────────────────────────────────────────────
# R5: 科技树 (FU Research)
# ─────────────────────────────────────────────

def extract_research_trees(assets_dir: Path) -> dict[str, dict]:
    """
    提取 FU 研究树的前置/后继关系。

    结构: config 文件含 researchTree.{tree_name}.{node_id} 嵌套。
    返回: {tree_name: {node_id: {children, unlocks, price, icon, position}}}
    """
    all_trees = {}
    config_dir = assets_dir / "config"
    if not config_dir.exists():
        return all_trees

    # 研究树定义文件
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

        # 找 researchTree 字段
        rt = d.get("researchTree", {})
        if not isinstance(rt, dict) or not rt:
            continue

        # 也取 strings 里的树名翻译
        strings = d.get("strings", {})
        tree_names = {}
        if isinstance(strings, dict):
            tree_names = strings.get("trees", {})

        for tree_name, nodes in rt.items():
            if not isinstance(nodes, dict):
                continue

            tree_data = {
                "display_name": tree_names.get(tree_name, tree_name),
                "nodes": {},
            }
            for node_id, node_def in nodes.items():
                if not isinstance(node_def, dict):
                    continue
                tree_data["nodes"][node_id] = {
                    "children": node_def.get("children", []),
                    "unlocks": node_def.get("unlocks", []),
                    "price": node_def.get("price", []),
                    "icon": node_def.get("icon", ""),
                }
            if tree_data["nodes"]:
                all_trees[tree_name] = tree_data

    return all_trees


# ─────────────────────────────────────────────
# R6: 租户需求
# ─────────────────────────────────────────────

def extract_tenant_requirements(assets_dir: Path) -> list[dict]:
    """
    提取租户的 colonyTagCriteria。

    返回: [{tenant_name, name_en, name_zh, required_tags: {tag: count}}]
    """
    tenants = []
    for entity in load_entities(assets_dir, "tenant"):
        if not isinstance(entity, dict):
            continue
        meta = entity.get("_meta", {})
        name = entity.get("name", meta.get("entity_id", ""))
        tags = entity.get("colonyTagCriteria", {})
        if not tags or not isinstance(tags, dict):
            continue
        tenants.append({
            "tenant_name": name,
            "name_en": clean_color(entity.get("shortdescription", entity.get("name", ""))),
            "name_zh": clean_color(meta.get("zh", {}).get("shortdescription_zh", "")),
            "required_tags": tags,
            "priority": entity.get("priority", 0),
        })
    return tenants


# ─────────────────────────────────────────────
# R7: 状态效果关联
# ─────────────────────────────────────────────

def extract_status_effects(assets_dir: Path) -> dict[str, dict]:
    """
    提取 statuseffect 详细信息。

    返回: {effect_id: {label_en, label_zh, description, ...}}
    """
    effects = {}
    for entity in load_entities(assets_dir, "statuseffect"):
        if not isinstance(entity, dict):
            continue
        name = entity.get("name", "")
        if not name:
            continue
        meta = entity.get("_meta", {})
        zh = meta.get("zh", {})
        effects[name] = {
            "label_en": clean_color(entity.get("label", "")),
            "label_zh": clean_color(zh.get("label_zh", "")),
            "description_en": entity.get("description", ""),
            "description_zh": zh.get("description_zh", ""),
            "icon": entity.get("icon", ""),
            "source_mod": meta.get("source_mod", ""),
            # 效果数值
            "effectConfig": entity.get("effectConfig", {}),
            "stats": _extract_stat_modifiers(entity),
        }
    return effects


def _extract_stat_modifiers(entity: dict) -> dict:
    """提取 statuseffect 的数值修正。"""
    stats = {}
    for key in ["baseMultiplier", "effectiveMultiplier", "amount",
                 "healthAmount", "energyAmount", "foodAmount"]:
        if key in entity:
            stats[key] = entity[key]
    # effectConfig 里可能也有
    ec = entity.get("effectConfig", {})
    if isinstance(ec, dict):
        for key in ["healthAmount", "energyAmount", "powerMultiplier"]:
            if key in ec:
                stats[key] = ec[key]
    return stats


# ─────────────────────────────────────────────
# R8: 物品标签
# ─────────────────────────────────────────────

def extract_item_tags(assets_dir: Path) -> dict[str, list[str]]:
    """
    提取物品的 itemTags。

    返回: {tag: [item_id, ...]}（反向索引）
    """
    tag_index = defaultdict(list)
    for entity_type in ["item", "object"]:
        for entity in load_entities(assets_dir, entity_type):
            if not isinstance(entity, dict):
                continue
            item_id = entity.get("itemName") or entity.get("objectName") or ""
            tags = entity.get("itemTags", [])
            if isinstance(tags, list) and item_id:
                for tag in tags:
                    if isinstance(tag, str) and tag:
                        tag_index[tag].append(item_id)
    return dict(tag_index)


# ─────────────────────────────────────────────
# R9: Collection 收集
# ─────────────────────────────────────────────

def extract_collections(assets_dir: Path) -> dict[str, dict]:
    """
    提取 collection 内容。

    返回: {collection_name: {title, items: [item_id, ...]}}
    """
    collections = {}
    for entity in load_entities(assets_dir, "collection"):
        if not isinstance(entity, dict):
            continue
        name = entity.get("name", "")
        title = entity.get("title", name)
        items = []
        for entry in entity.get("collectables", []):
            if isinstance(entry, dict):
                items.append(entry.get("name", ""))
            elif isinstance(entry, str):
                items.append(entry)

        # collectables 也可能是 dict
        collectables = entity.get("collectables", {})
        if isinstance(collectables, dict):
            items = list(collectables.keys())

        if name:
            collections[name] = {
                "title": title,
                "items": [i for i in items if i],
            }
    return collections


# ─────────────────────────────────────────────
# R10: Codex 来源
# ─────────────────────────────────────────────

def extract_codex_sources(assets_dir: Path) -> dict[str, dict]:
    """
    提取 codex 的来源和内容摘要。

    返回: {codex_id: {title_en, title_zh, species, description, content_pages}}
    """
    codexes = {}
    for entity in load_entities(assets_dir, "codex"):
        if not isinstance(entity, dict):
            continue
        codex_id = entity.get("id", "")
        if not codex_id:
            continue
        meta = entity.get("_meta", {})
        zh = meta.get("zh", {})

        # 提取内容页
        content_pages = []
        for page in entity.get("contentPages", []):
            if isinstance(page, str):
                content_pages.append(clean_color(page)[:200])  # 截断

        codexes[codex_id] = {
            "title_en": clean_color(entity.get("title", "")),
            "title_zh": clean_color(zh.get("title_zh", "")),
            "description_en": entity.get("description", ""),
            "description_zh": zh.get("description_zh", ""),
            "species": entity.get("species", ""),
            "content_pages": content_pages,
            "source_mod": meta.get("source_mod", ""),
        }
    return codexes


# ─────────────────────────────────────────────
# R11: 物品升级路径
# ─────────────────────────────────────────────

def extract_upgrade_paths(assets_dir: Path) -> dict[str, dict]:
    """
    提取物品的 upgradeParameters。

    返回: {item_id: {upgrades_to: str, ...}}
    """
    upgrades = {}
    for entity in load_entities(assets_dir, "item"):
        if not isinstance(entity, dict):
            continue
        item_id = entity.get("itemName", "")
        up = entity.get("upgradeParameters", {})
        if not up or not isinstance(up, dict):
            continue
        upgrades[item_id] = {
            "upgrades_to": up.get("inventoryIcon", ""),  # 不一定有
            "seed": up.get("seed", ""),
            "shortdescription": up.get("shortdescription", ""),
            "scripts": up.get("scripts", []),
        }
    return upgrades


# ─────────────────────────────────────────────
# R12: 怪物 ↔ 生态
# ─────────────────────────────────────────────

def extract_biome_monsters(assets_dir: Path) -> dict[str, list[str]]:
    """
    提取生态中的怪物生成。

    返回: {biome_name: [monster_type, ...]}
    同时建反向: 在调用方处理
    """
    biome_monsters = {}
    for entity in load_entities(assets_dir, "biome"):
        if not isinstance(entity, dict):
            continue
        biome_name = entity.get("name", "")
        if not biome_name:
            continue

        monsters = set()
        # spawnProfile
        spawn = entity.get("spawnProfile", {})
        if isinstance(spawn, dict):
            for group in spawn.get("groups", []):
                if isinstance(group, dict):
                    pool = group.get("pool", [])
                    if not isinstance(pool, list):
                        continue
                    for monster in pool:
                        if isinstance(monster, list) and len(monster) >= 2:
                            monsters.add(monster[1] if isinstance(monster[1], str) else str(monster[1]))
                        elif isinstance(monster, str):
                            monsters.add(monster)

        # monsterParameters
        for mp_key in ["monsterParameters", "surfaceMonsters", "undergroundMonsters"]:
            mp = entity.get(mp_key, [])
            if isinstance(mp, list):
                for m in mp:
                    if isinstance(m, dict):
                        monsters.add(m.get("type", ""))
                    elif isinstance(m, str):
                        monsters.add(m)

        monsters.discard("")
        if monsters:
            biome_monsters[biome_name] = sorted(monsters)

    return biome_monsters


# ─────────────────────────────────────────────
# R13: 液体属性
# ─────────────────────────────────────────────

def extract_liquids(assets_dir: Path) -> dict[str, dict]:
    """
    提取液体属性。

    返回: {liquid_name: {description, statusEffects, interactions, ...}}
    """
    liquids = {}
    for entity in load_entities(assets_dir, "liquid"):
        if not isinstance(entity, dict):
            continue
        name = entity.get("name", "")
        if not name:
            continue
        meta = entity.get("_meta", {})
        zh = meta.get("zh", {})
        liquids[name] = {
            "name_en": clean_color(entity.get("shortdescription", entity.get("liquidName", name))),
            "name_zh": clean_color(zh.get("shortdescription_zh", "")),
            "description_en": entity.get("description", ""),
            "description_zh": zh.get("description_zh", ""),
            "statusEffects": entity.get("statusEffects", []),
            "interactions": entity.get("interactions", {}),
            "source_mod": meta.get("source_mod", ""),
        }
    return liquids


# ─────────────────────────────────────────────
# R14: 任务奖励
# ─────────────────────────────────────────────

def extract_quest_rewards(assets_dir: Path) -> dict[str, dict]:
    """
    提取任务的奖励信息。

    返回: {quest_id: {title_en, title_zh, rewards: [item_id, ...], prerequisites}}
    """
    quests = {}
    for entity in load_entities(assets_dir, "quest"):
        if not isinstance(entity, dict):
            continue
        quest_id = entity.get("id", entity.get("questId", ""))
        if not quest_id:
            continue
        meta = entity.get("_meta", {})
        zh = meta.get("zh", {})

        rewards = []
        for r in entity.get("rewards", []):
            if isinstance(r, dict):
                rewards.append(r.get("item", ""))
            elif isinstance(r, list) and len(r) >= 1:
                rewards.append(r[0] if isinstance(r[0], str) else "")
        # moneyRange 也算
        money = entity.get("moneyRange", [])
        rewardText = entity.get("completionText", "")

        prerequisites = entity.get("prerequisites", [])
        if isinstance(prerequisites, str):
            prerequisites = [prerequisites]

        raw_text = entity.get("text", "")[:200]
        text_zh_from_meta = zh.get("text_zh", "")[:200] if zh.get("text_zh") else ""
        # 中文 patch 会直接覆盖 text 字段，检测后正确归类
        if not text_zh_from_meta and raw_text and re.search(r'[\u4e00-\u9fff]', raw_text):
            text_en = ""
            text_zh = clean_color(raw_text)
        else:
            text_en = raw_text
            text_zh = text_zh_from_meta

        quests[quest_id] = {
            "title_en": clean_color(entity.get("title", "")),
            "title_zh": clean_color(zh.get("title_zh", "")),
            "text_en": text_en,
            "text_zh": text_zh,
            "rewards": [r for r in rewards if r],
            "moneyRange": money,
            "prerequisites": prerequisites,
            "source_mod": meta.get("source_mod", ""),
        }
    return quests


# ─────────────────────────────────────────────
# R15: NPC 商店
# ─────────────────────────────────────────────

def extract_npc_shops(assets_dir: Path) -> list[dict]:
    """
    提取 NPC 的商店售卖物品。

    从 config 文件中查找 merchant / shop 配置。
    """
    shops = []
    config_dir = assets_dir / "config"
    if not config_dir.exists():
        return shops

    for fn in os.listdir(config_dir):
        if not fn.endswith(".json"):
            continue
        if not any(kw in fn.lower() for kw in ["shop", "merchant", "store", "vendor"]):
            continue
        try:
            with open(config_dir / fn) as f:
                d = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        if not isinstance(d, dict):
            continue

        # 寻找 buyItems / sellItems / items 等字段
        items = []
        for key in ["buyItems", "sellItems", "items", "stock"]:
            val = d.get(key, [])
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        items.append(item.get("item", item.get("name", "")))
                    elif isinstance(item, str):
                        items.append(item)
        items = [i for i in items if i]
        if items:
            shops.append({
                "config_file": fn,
                "items": items,
            })

    return shops


# ─────────────────────────────────────────────
# 主逻辑：运行所有提取器
# ─────────────────────────────────────────────

ALL_EXTRACTORS = {
    "blueprints": ("R1: 蓝图解锁", extract_blueprints),
    "farmables": ("R2: 种子↔作物", extract_farmables),
    "biome_ores": ("R3: 矿石↔生态", extract_biome_ores),
    "race_effects": ("R4: 种族效果", extract_race_effects),
    "research_trees": ("R5: 科技树", extract_research_trees),
    "tenant_requirements": ("R6: 租户需求", extract_tenant_requirements),
    "status_effects": ("R7: 状态效果", extract_status_effects),
    "item_tags": ("R8: 物品标签", extract_item_tags),
    "collections": ("R9: 收集", extract_collections),
    "codex_sources": ("R10: Codex", extract_codex_sources),
    "upgrade_paths": ("R11: 升级路径", extract_upgrade_paths),
    "biome_monsters": ("R12: 怪物↔生态", extract_biome_monsters),
    "liquids": ("R13: 液体", extract_liquids),
    "quest_rewards": ("R14: 任务奖励", extract_quest_rewards),
    "npc_shops": ("R15: NPC 商店", extract_npc_shops),
}


def run_all(assets_dir: Path) -> dict[str, any]:
    """运行所有提取器，返回 {key: data}。"""
    results = {}
    for key, (desc, func) in ALL_EXTRACTORS.items():
        print(f"  {desc}...", end=" ", flush=True)
        data = func(assets_dir)
        size = len(data) if isinstance(data, (dict, list)) else 0
        print(f"✅ {size} 条")
        results[key] = data
    return results


def save_results(results: dict, output_dir: Path):
    """保存所有关系数据。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    meta = {}
    for key, data in results.items():
        out_path = output_dir / f"{key}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        meta[key] = len(data) if isinstance(data, (dict, list)) else 0

    with open(output_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n💾 输出目录: {output_dir.resolve()}")
    for key, count in meta.items():
        desc = ALL_EXTRACTORS[key][0]
        print(f"   {desc:25s}: {count:>6}")


# ─────────────────────────────────────────────
# 测试模式
# ─────────────────────────────────────────────

def run_test(assets_dir: Path, extractor_key: str | None = None):
    """测试模式：运行并展示样例数据。"""
    if extractor_key and extractor_key in ALL_EXTRACTORS:
        desc, func = ALL_EXTRACTORS[extractor_key]
        print(f"\n{'═' * 60}")
        print(f"  测试: {desc}")
        print(f"{'═' * 60}")
        data = func(assets_dir)
        _show_sample(extractor_key, data)
    else:
        results = run_all(assets_dir)
        for key, data in results.items():
            desc = ALL_EXTRACTORS[key][0]
            print(f"\n{'═' * 60}")
            print(f"  {desc}")
            print(f"{'═' * 60}")
            _show_sample(key, data)


def _show_sample(key: str, data):
    """显示每个提取器的样例数据。"""
    if isinstance(data, dict):
        items = list(data.items())[:5]
        for k, v in items:
            s = json.dumps(v, ensure_ascii=False)
            print(f"  {k}: {s[:150]}")
    elif isinstance(data, list):
        for entry in data[:5]:
            s = json.dumps(entry, ensure_ascii=False)
            print(f"  {s[:200]}")
    print(f"  ... 共 {len(data)} 条")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="游戏实体关系提取")
    parser.add_argument("--assets", type=Path, default=Path("resolved_assets"))
    parser.add_argument("-o", "--output", type=Path, default=Path("relationship_db"))
    parser.add_argument("--test", nargs="?", const="all", default=None,
                        help="测试模式（可指定提取器名，如 --test blueprints）")

    args = parser.parse_args()

    if not args.assets.exists():
        print(f"❌ 目录不存在: {args.assets}", file=sys.stderr)
        sys.exit(1)

    if args.test:
        if args.test == "all":
            run_test(args.assets)
        else:
            run_test(args.assets, args.test)
    else:
        print("🔗 提取游戏实体关系...")
        results = run_all(args.assets)
        save_results(results, args.output)


if __name__ == "__main__":
    main()
