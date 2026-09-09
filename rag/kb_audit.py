"""Knowledge-base quality audit: coverage gaps and dirty fields."""

import json
from collections import Counter, defaultdict
from pathlib import Path

KB = Path(__file__).resolve().parent.parent / "knowledge_base"
ENT = KB / "entities"


def load_entities():
    docs = []
    for p in ENT.rglob("*.json"):
        try:
            docs.append(json.loads(p.read_text()))
        except Exception:
            pass
    return docs


def main():
    docs = load_entities()
    print(f"实体文档: {len(docs)}")

    # 1) recipe input names: ID only vs zh
    recipe_items = 0
    recipe_with_zh = 0
    station_filename = 0
    station_total = 0
    also_at_filename = 0
    weapons = 0
    weapons_with_dps = 0
    monsters = 0
    monsters_with_items = 0
    items_with_drops = 0
    items_with_recipes = 0
    empty_zh = 0
    empty_desc = 0
    no_wiki = 0

    dirty_stations = []
    monster_pool_only = 0

    for d in docs:
        et = d.get("entity_type")
        if not d.get("name_zh"):
            empty_zh += 1
        if not d.get("description_zh") and not d.get("description_en"):
            empty_desc += 1
        if not d.get("wiki_ref"):
            no_wiki += 1

        if et == "item":
            if d.get("recipes_output"):
                items_with_recipes += 1
            if d.get("drop_sources"):
                items_with_drops += 1
            if d.get("baseDps") or d.get("category") in (
                "katana", "broadsword", "shortsword", "dagger", "spear",
                "hammer", "axe", "bow", "sniperRifle", "assaultRifle",
                "shotgun", "pistol", "staff", "wand",
            ) or "weapon" in (d.get("tags") or []):
                weapons += 1
                if d.get("baseDps"):
                    weapons_with_dps += 1

            for r in d.get("recipes_output") or []:
                station_total += 1
                st = r.get("station") or ""
                if st.endswith(".json") or st in (".", "...", "…"):
                    station_filename += 1
                    if len(dirty_stations) < 8:
                        dirty_stations.append((d["entity_id"], st))
                for a in r.get("also_at") or []:
                    if (a.get("name") or "").endswith(".json"):
                        also_at_filename += 1
                for inp in r.get("inputs") or []:
                    recipe_items += 1
                    if inp.get("name_zh") or inp.get("name_en"):
                        recipe_with_zh += 1

        if et == "monster":
            monsters += 1
            if d.get("drops") or d.get("drop_items"):
                monsters_with_items += 1
            if d.get("drop_pool_default") and not d.get("drops"):
                monster_pool_only += 1

    print("\n── 覆盖 ──")
    print(f"  无中文名: {empty_zh} ({empty_zh/len(docs):.1%})")
    print(f"  无描述: {empty_desc} ({empty_desc/len(docs):.1%})")
    print(f"  未关联 Wiki: {no_wiki} ({no_wiki/len(docs):.1%})")
    print(f"  有制作配方的物品: {items_with_recipes}")
    print(f"  有掉落来源的物品: {items_with_drops}")
    print(f"  武器(含tags/category): {weapons}, 其中有 DPS: {weapons_with_dps}")
    print(f"  怪物: {monsters}, 仅有 pool 名: {monster_pool_only}, 已展开掉落物: {monsters_with_items}")

    print("\n── 配方质量 ──")
    print(f"  配方材料字段带中英文名: {recipe_with_zh}/{recipe_items}")
    print(f"  工作台名为文件名/省略号: {station_filename}/{station_total}")
    print(f"  also_at 为文件名: {also_at_filename}")
    if dirty_stations:
        print("  脏工作台示例:")
        for eid, st in dirty_stations:
            print(f"    {eid}: {st!r}")

    # 2) research tree ingested?
    rt = KB / "research_trees.json"
    print(f"\n── 研究树文件 ──")
    print(f"  存在: {rt.exists()}, 大小: {rt.stat().st_size if rt.exists() else 0}")

    # 3) sample tungsten / cotton / hydrotray
    for eid in ["tungstenore", "tungstenbar", "cotton", "cottonwool", "hydrotray", "fu_woodenwateringtray"]:
        hits = list(ENT.rglob(f"{eid}.json"))
        print(f"  {eid}: {hits[0].relative_to(KB) if hits else 'MISSING'}")

    # 4) quality of tungstenore recipes_output (is it smelting or reverse?)
    p = ENT / "item" / "tungstenore.json"
    if p.exists():
        d = json.loads(p.read_text())
        print("\n── tungstenore.recipes_output 首条 ──")
        print(json.dumps((d.get("recipes_output") or [None])[0], ensure_ascii=False, indent=2)[:600])
        print("  recipes_input examples:", (d.get("recipes_input") or {}).get("by_category"))


if __name__ == "__main__":
    main()
