#!/usr/bin/env python3
"""
audit_missed_assets.py — 对照 GAME_FILE_TYPES，统计漏扫的文件和物品

遍历 unpacked_data 内容 mod（与 asset_resolver 相同范围），找出：
1. 扫描器根本不认的扩展名
2. 其中带 itemName 的真正漏掉物品
3. 配方 / 科研树引用了、但知识库没有的 ID

用法:
    python3 audit_missed_assets.py
    python3 audit_missed_assets.py --data unpacked_data --kb knowledge_base
    python3 audit_missed_assets.py -o missed_assets_report.json
    python3 audit_missed_assets.py --sample 100 --seed 42
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import random
from collections import Counter, defaultdict
from pathlib import Path

from asset_resolver import (
    CONTENT_MODS,
    GAME_FILE_TYPES,
    SKIP_DIRS,
    parse_json_lenient,
)

# 明确不是实体定义的资源（不必尝试 JSON 解析）
NON_DATA_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".tga", ".dds", ".bmp", ".ico",
    ".ogg", ".wav", ".flac", ".mp3",
    ".ttf", ".otf", ".woff", ".woff2",
    ".lua", ".txt", ".md", ".html", ".css", ".js", ".xml", ".csv",
    ".zip", ".pak", ".7z", ".db", ".bin", ".dat", ".bak", ".log",
    ".psd", ".xcf", ".ase", ".blend", ".fbx", ".obj", ".mtl",
}

# Starbound 常见视觉/关卡资源，一般不是物品词条
VISUAL_OR_WORLD_EXTS = {
    ".frames", ".animation", ".particle", ".projectile",
    ".dungeon", ".structure", ".tileset", ".chunk",
    ".behavior", ".nodes", ".monsterpart", ".monsterskill",
    ".cinematic", ".namesource", ".radiomessages",
    ".metadata", ".versioning", ".disabled",
}

MAX_PARSE_BYTES = 2 * 1024 * 1024
EXAMPLE_LIMIT = 8


def game_suffix(filename: str) -> tuple[str, bool]:
    """(扩展名, 是否 patch)。空扩展名返回 ''。"""
    if filename.endswith(".patch"):
        base = filename[:-6]
        return Path(base).suffix.lower(), True
    return Path(filename).suffix.lower(), False


def should_skip_dir(rel_parts: tuple[str, ...]) -> bool:
    return any(p.startswith(("a_", ".")) for p in rel_parts)


def load_kb_index(kb_dir: Path) -> dict[str, set[str]]:
    """entity_id → {entity_type, ...}"""
    ids: dict[str, set[str]] = defaultdict(set)
    index = kb_dir / "index.jsonl"
    if not index.exists():
        return ids
    with open(index, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            eid = row.get("entity_id") or ""
            et = row.get("entity_type") or ""
            if eid:
                ids[eid].add(et)
    return ids


def kb_has_item(eid: str, kb: dict[str, set[str]]) -> bool:
    return bool(kb.get(eid, set()) & {"item", "object"})


def kb_has_any(eid: str, kb: dict[str, set[str]]) -> bool:
    return eid in kb and bool(kb[eid])


def load_recipe_ids(recipe_db: Path) -> set[str]:
    ids: set[str] = set()
    for name in ("output_index.json", "input_index.json"):
        path = recipe_db / name
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            ids.update(data.keys())
    return ids


def load_research_unlocks(kb_dir: Path) -> set[str]:
    ids: set[str] = set()
    path = kb_dir / "research_trees.json"
    if not path.exists():
        return ids
    with open(path, encoding="utf-8") as f:
        trees = json.load(f)
    if not isinstance(trees, dict):
        return ids
    for tree in trees.values():
        nodes = (tree or {}).get("nodes") or {}
        if not isinstance(nodes, dict):
            continue
        for node in nodes.values():
            for uid in (node or {}).get("unlocks") or []:
                if uid:
                    ids.add(uid)
    return ids


def extract_ids(data) -> dict:
    """从 JSON 里抽出可能的实体 ID / 显示名。"""
    if not isinstance(data, dict):
        return {}
    out = {}
    for key in (
        "itemName", "objectName", "name", "id", "type", "kind",
        "shortdescription", "shortDescription", "title",
    ):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            out[key] = val.strip()
    return out


def classify_ext(ext: str) -> str:
    if not ext:
        return "no_ext"
    if ext in GAME_FILE_TYPES:
        return "scanned"
    if ext in (".config", ".configfunctions"):
        return "scanned_config"
    if ext in NON_DATA_EXTS:
        return "media_or_code"
    if ext in VISUAL_OR_WORLD_EXTS:
        return "visual_or_world"
    if ext in {".material", ".matmod"}:
        return "tile_data"
    if ext == ".vehicle":
        return "vehicle"
    if ext == ".stagehand":
        return "stagehand"
    return "unknown_data"


def walk_mods(data_dir: Path, mods: list[str]) -> dict:
    ext_files = defaultdict(lambda: {
        "base": 0,
        "patch": 0,
        "bucket": "",
        "item_ids": [],
        "other_ids": [],
        "examples": [],
        "parse_fail": 0,
        "under_items": 0,
    })
    missed_items: dict[str, dict] = {}  # itemName → info
    unscanned: list[dict] = []
    stats = {
        "files_total": 0,
        "files_base": 0,
        "files_patch": 0,
        "mods_missing": [],
    }

    for mod_name in mods:
        mod_dir = data_dir / mod_name
        if not mod_dir.exists():
            stats["mods_missing"].append(mod_name)
            continue
        for root, dirs, files in os.walk(mod_dir):
            root_path = Path(root)
            rel = root_path.relative_to(mod_dir)
            if rel.parts and (rel.parts[0] in SKIP_DIRS or should_skip_dir(rel.parts)):
                dirs.clear()
                continue
            dirs[:] = [d for d in dirs if not d.startswith(("a_", ".")) and d not in SKIP_DIRS]

            for filename in files:
                stats["files_total"] += 1
                ext, is_patch = game_suffix(filename)
                bucket = classify_ext(ext)
                rec = ext_files[ext or "(none)"]
                rec["bucket"] = bucket
                if is_patch:
                    rec["patch"] += 1
                    stats["files_patch"] += 1
                    continue
                rec["base"] += 1
                stats["files_base"] += 1

                rel_file = str((rel / filename)).replace("\\", "/")
                under_items = rel_file.startswith("items/") or "/items/" in f"/{rel_file}"
                if under_items:
                    rec["under_items"] += 1
                if bucket not in ("scanned", "scanned_config"):
                    unscanned.append({
                        "mod": mod_name,
                        "rel": rel_file,
                        "abs": str(root_path / filename),
                        "ext": ext or "(none)",
                        "bucket": bucket,
                    })

                if bucket in (
                    "scanned", "scanned_config", "media_or_code",
                    "visual_or_world", "tile_data",
                ):
                    continue

                filepath = root_path / filename
                try:
                    if filepath.stat().st_size > MAX_PARSE_BYTES:
                        rec["parse_fail"] += 1
                        continue
                except OSError:
                    rec["parse_fail"] += 1
                    continue

                data = parse_json_lenient(filepath)
                if data is None:
                    rec["parse_fail"] += 1
                    continue

                fields = extract_ids(data)
                item_name = fields.get("itemName")
                example = {
                    "mod": mod_name,
                    "path": rel_file,
                    "itemName": item_name,
                    "objectName": fields.get("objectName"),
                    "shortdescription": fields.get("shortdescription")
                    or fields.get("shortDescription")
                    or fields.get("title"),
                }
                if len(rec["examples"]) < EXAMPLE_LIMIT:
                    rec["examples"].append(example)

                if item_name:
                    rec["item_ids"].append(item_name)
                    prev = missed_items.get(item_name)
                    if prev is None or (prev.get("source_mod") == "Starbound" and mod_name != "Starbound"):
                        missed_items[item_name] = {
                            "itemName": item_name,
                            "ext": ext,
                            "source_mod": mod_name,
                            "path": rel_file,
                            "shortdescription": example["shortdescription"] or "",
                            "category": data.get("category") if isinstance(data, dict) else "",
                            "rarity": data.get("rarity") if isinstance(data, dict) else "",
                        }
                elif fields.get("objectName") or fields.get("name") or fields.get("id"):
                    rec["other_ids"].append(
                        fields.get("objectName") or fields.get("name") or fields.get("id")
                    )

    return {
        "ext_files": ext_files,
        "missed_items": missed_items,
        "unscanned": unscanned,
        "stats": stats,
    }


def inspect_file(entry: dict) -> dict:
    """抽查单个未扫描文件，判断像不像该进知识库的词条。"""
    ext = entry["ext"]
    bucket = entry["bucket"]
    path = Path(entry["abs"])
    result = {
        **entry,
        "verdict": "other",
        "note": "",
        "itemName": "",
        "objectName": "",
        "keys": [],
    }

    if bucket == "media_or_code":
        result["verdict"] = "media_or_code"
        result["note"] = ext
        return result

    data = None
    try:
        size = path.stat().st_size
    except OSError as e:
        result["verdict"] = "unreadable"
        result["note"] = str(e)
        return result
    if size <= MAX_PARSE_BYTES and ext not in NON_DATA_EXTS:
        data = parse_json_lenient(path)

    if data is None:
        result["verdict"] = "unparsed"
        result["note"] = f"{ext} {bucket}"
        return result

    fields = extract_ids(data)
    result["itemName"] = fields.get("itemName") or ""
    result["objectName"] = fields.get("objectName") or ""
    if isinstance(data, dict):
        result["keys"] = list(data.keys())[:8]
    elif isinstance(data, list):
        result["keys"] = [f"list[{len(data)}]"]

    if result["itemName"]:
        result["verdict"] = "HAS_itemName"
        result["note"] = result["itemName"]
        if fields.get("shortdescription"):
            result["note"] += f" | {fields['shortdescription']}"
        return result
    if result["objectName"]:
        result["verdict"] = "HAS_objectName"
        result["note"] = result["objectName"]
        return result

    if bucket == "tile_data":
        drop = ""
        if isinstance(data, dict):
            drop = str(data.get("itemDrop") or data.get("modName") or data.get("materialId") or "")
        result["verdict"] = "tile_data"
        result["note"] = drop
        return result
    if bucket in ("vehicle", "stagehand"):
        result["verdict"] = f"possible_{bucket}"
        result["note"] = fields.get("name") or fields.get("type") or fields.get("id") or ""
        return result
    if bucket == "visual_or_world":
        result["verdict"] = "visual_or_world"
        result["note"] = ",".join(result["keys"][:5])
        return result

    extra = fields.get("name") or fields.get("id") or fields.get("type") or ""
    result["verdict"] = "support_json"
    result["note"] = extra or ",".join(result["keys"][:5])
    return result


def run_sample(unscanned: list[dict], n: int, seed: int, pool: str) -> list[dict]:
    if pool == "data":
        pool_files = [
            e for e in unscanned
            if e["bucket"] not in ("media_or_code", "visual_or_world")
        ]
        label = "非媒体/非动画"
    else:
        pool_files = unscanned
        label = "全部未扫描基础文件"
    rng = random.Random(seed)
    k = min(n, len(pool_files))
    picked = rng.sample(pool_files, k) if k else []
    inspected = [inspect_file(e) for e in picked]
    counts = Counter(r["verdict"] for r in inspected)

    print()
    print("=" * 72)
    print(f"抽查 {k} / {len(pool_files)}  ({label}, seed={seed})")
    print("=" * 72)
    print("  判定分布:")
    for verdict, c in counts.most_common():
        print(f"    {c:4}  {verdict}")

    suspicious = {"HAS_itemName", "HAS_objectName", "possible_vehicle", "possible_stagehand"}
    hits = [r for r in inspected if r["verdict"] in suspicious]
    print(f"  像词条的: {len(hits)}")
    if hits:
        for r in hits:
            print(f"    [{r['verdict']}] {r['ext']:16} {r['mod']}/{r['rel']}  {r['note']}")

    print()
    print("  全部样本:")
    for i, r in enumerate(inspected, 1):
        print(f"    {i:3}. {r['verdict']:<20} {r['ext']:<16} {r['rel'][:70]}  {r['note'][:50]}")
    return inspected


def print_table(rows: list[tuple], headers: list[str], min_widths: list[int] | None = None):
    widths = list(min_widths or [len(h) for h in headers])
    for i, h in enumerate(headers):
        widths[i] = max(widths[i], len(h))
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    print("  ".join(h.rjust(w) if i < len(headers) - 1 else h.ljust(w)
                    for i, (h, w) in enumerate(zip(headers, widths))))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        parts = []
        for i, (cell, w) in enumerate(zip(row, widths)):
            s = str(cell)
            parts.append(s.rjust(w) if i < len(row) - 1 else s.ljust(w))
        print("  ".join(parts))


def main():
    parser = argparse.ArgumentParser(description="统计 GAME_FILE_TYPES 漏扫的文件和物品")
    parser.add_argument("--data", type=Path, default=Path("unpacked_data"))
    parser.add_argument("--kb", type=Path, default=Path("knowledge_base"))
    parser.add_argument("--recipes", type=Path, default=Path("recipe_db"))
    parser.add_argument("-o", "--output", type=Path, help="写出 JSON 报告")
    parser.add_argument("--top", type=int, default=30, help="每种列表最多展示条数")
    parser.add_argument("--sample", type=int, default=0, help="从未扫描文件中随机抽查 N 个")
    parser.add_argument("--seed", type=int, default=42, help="抽查随机种子")
    args = parser.parse_args()

    if not args.data.exists():
        print(f"找不到 {args.data}", file=sys.stderr)
        sys.exit(1)

    print("📂 扫描 unpacked_data 内容 mod...")
    walked = walk_mods(args.data, CONTENT_MODS)
    ext_files = walked["ext_files"]
    missed_items = walked["missed_items"]
    stats = walked["stats"]
    unscanned = walked["unscanned"]

    print("📖 对照知识库 / 配方 / 科研树...")
    kb = load_kb_index(args.kb)
    kb_ids = set(kb)
    recipe_ids = load_recipe_ids(args.recipes)
    research_ids = load_research_unlocks(args.kb)

    scanned_base = 0
    unscanned_base = 0
    itemlike_files = 0
    for rec in ext_files.values():
        if rec["bucket"] in ("scanned", "scanned_config"):
            scanned_base += rec["base"]
        else:
            unscanned_base += rec["base"]
        itemlike_files += len(rec["item_ids"])

    missed_not_in_kb = [m for m in missed_items.values() if not kb_has_item(m["itemName"], kb)]
    missed_already_item = [m for m in missed_items.values() if kb_has_item(m["itemName"], kb)]
    missed_id_collision = [
        m for m in missed_not_in_kb
        if kb_has_any(m["itemName"], kb)
    ]

    recipe_missing = sorted(i for i in recipe_ids if not kb_has_any(i, kb))
    research_missing = sorted(i for i in research_ids if not kb_has_any(i, kb))
    missed_id_set = {m["itemName"] for m in missed_items.values()}
    recipe_missing_by_ext = [i for i in recipe_missing if i in missed_id_set]
    recipe_missing_other = [i for i in recipe_missing if i not in missed_id_set]
    research_missing_by_ext = [i for i in research_missing if i in missed_id_set]
    recipe_missing_codex = [i for i in recipe_missing_other if i.endswith("-codex")]
    recipe_missing_rest = [i for i in recipe_missing_other if not i.endswith("-codex")]

    by_ext = defaultdict(list)
    for m in missed_not_in_kb:
        if m["ext"] == ".unused":
            continue
        by_ext[m["ext"]].append(m)

    print()
    print("=" * 72)
    print("总览")
    print("=" * 72)
    print(f"  内容 mod 文件总计     {stats['files_total']:>8}")
    print(f"  其中基础文件          {stats['files_base']:>8}")
    print(f"  其中 patch            {stats['files_patch']:>8}")
    print(f"  白名单已扫描基础文件  {scanned_base:>8}  (含 .config)")
    print(f"  白名单未扫描基础文件  {unscanned_base:>8}  (含图片/音频/lua 等)")
    print(f"  漏扫且带 itemName     {len(missed_items):>8}  种物品")
    print(f"    无 item/object 词条 {len(missed_not_in_kb):>8}")
    print(f"      其中只撞上任务等  {len(missed_id_collision):>8}")
    print(f"    已有 item/object    {len(missed_already_item):>8}")
    print(f"  知识库实体 ID         {len(kb_ids):>8}")
    print(f"  配方引用 ID           {len(recipe_ids):>8}")
    print(f"  配方有、知识库无      {len(recipe_missing):>8}")
    print(f"    能归因于漏扫扩展    {len(recipe_missing_by_ext):>8}")
    print(f"    百科书 -codex 后缀  {len(recipe_missing_codex):>8}")
    print(f"    其他原因            {len(recipe_missing_rest):>8}")
    print(f"  科研树解锁有、库无    {len(research_missing):>8}")
    print(f"    能归因于漏扫扩展    {len(research_missing_by_ext):>8}")
    if stats["mods_missing"]:
        print(f"  配置了但不存在的 mod: {', '.join(stats['mods_missing'])}")

    # 漏扫扩展：有 itemName 的优先
    print()
    print("=" * 72)
    print("漏扫扩展名（按带 itemName 的基础文件数）")
    print("=" * 72)
    item_ext_rows = []
    for ext, rec in sorted(
        ext_files.items(),
        key=lambda kv: (-len(kv[1]["item_ids"]), -kv[1]["base"], kv[0]),
    ):
        n_items = len(set(rec["item_ids"]))
        if rec["bucket"] in ("scanned", "scanned_config") or rec["base"] == 0:
            continue
        if n_items == 0 and rec["bucket"] in ("media_or_code", "visual_or_world"):
            continue
        examples = ", ".join(
            e.get("itemName") or Path(e["path"]).stem
            for e in rec["examples"][:4]
            if e.get("itemName") or e.get("shortdescription")
        )
        item_ext_rows.append((
            rec["base"], rec["patch"], n_items, rec["under_items"],
            rec["bucket"], ext, examples,
        ))
    print_table(
        item_ext_rows,
        ["base", "patch", "itemName", "in items/", "bucket", "ext", "examples"],
        [5, 5, 8, 9, 16, 16, 20],
    )

    print()
    print("=" * 72)
    print("建议补进 GAME_FILE_TYPES 的物品扩展（有 itemName 且知识库缺失）")
    print("=" * 72)
    if not by_ext:
        print("  无")
    else:
        for ext, items in sorted(by_ext.items(), key=lambda kv: -len(kv[1])):
            print(f"\n  {ext}  →  item  ({len(items)} 种缺失)")
            for m in sorted(items, key=lambda x: x["itemName"])[: args.top]:
                name = m["shortdescription"] or ""
                extra = f"  {name}" if name else ""
                print(f"    {m['itemName']:<28} {m['source_mod']:<22}{extra}")
            if len(items) > args.top:
                print(f"    ... 还有 {len(items) - args.top} 种")

    print()
    print("=" * 72)
    print("配方引用了但知识库没有、且不是漏扫扩展造成的 ID")
    print("=" * 72)
    print(f"  -codex 后缀（百科书实体 ID 一般不带这个后缀）: {len(recipe_missing_codex)}")
    if not recipe_missing_rest:
        print("  其余: 无")
    else:
        print(f"  其余 {len(recipe_missing_rest)} 个:")
        for eid in recipe_missing_rest[: args.top]:
            print(f"    {eid}")
        if len(recipe_missing_rest) > args.top:
            print(f"    ... 还有 {len(recipe_missing_rest) - args.top} 个")
    if missed_id_collision:
        print()
        print("  ID 撞名（有任务/其他类型，但没有物品词条）:")
        for m in missed_id_collision:
            types = ",".join(sorted(kb.get(m["itemName"], [])))
            print(f"    {m['itemName']:<28} kb={types}  ext={m['ext']}")

    report = {
        "stats": {
            **stats,
            "scanned_base": scanned_base,
            "unscanned_base": unscanned_base,
            "kb_ids": len(kb_ids),
            "recipe_ids": len(recipe_ids),
            "missed_item_files": itemlike_files,
            "missed_item_unique": len(missed_items),
            "missed_item_not_in_kb": len(missed_not_in_kb),
            "missed_already_item": len(missed_already_item),
            "missed_id_collision": len(missed_id_collision),
            "recipe_missing": len(recipe_missing),
            "recipe_missing_by_ext": len(recipe_missing_by_ext),
            "recipe_missing_other": len(recipe_missing_other),
            "recipe_missing_codex": len(recipe_missing_codex),
            "recipe_missing_rest": len(recipe_missing_rest),
            "research_missing": len(research_missing),
            "research_missing_by_ext": len(research_missing_by_ext),
        },
        "by_ext": {
            ext: {
                "base": rec["base"],
                "patch": rec["patch"],
                "bucket": rec["bucket"],
                "itemName_unique": sorted(set(rec["item_ids"])),
                "under_items": rec["under_items"],
                "parse_fail": rec["parse_fail"],
                "examples": rec["examples"],
            }
            for ext, rec in sorted(ext_files.items())
        },
        "missed_items_not_in_kb": sorted(missed_not_in_kb, key=lambda x: (x["ext"], x["itemName"])),
        "suggested_game_file_types": {
            ext: "item" for ext in sorted(by_ext)
        },
        "recipe_missing_by_ext": recipe_missing_by_ext,
        "recipe_missing_codex": recipe_missing_codex,
        "recipe_missing_rest": recipe_missing_rest,
        "research_missing_by_ext": research_missing_by_ext,
        "research_missing_other": [i for i in research_missing if i not in missed_id_set],
    }

    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n📝 报告已写到 {args.output}")

    if args.sample:
        run_sample(unscanned, args.sample, args.seed, "all")
        run_sample(unscanned, args.sample, args.seed, "data")


if __name__ == "__main__":
    main()
