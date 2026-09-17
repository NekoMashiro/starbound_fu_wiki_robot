#!/usr/bin/env python3
"""
asset_resolver.py — Mod 扫描 + JSON Patch 合并引擎

扫描 unpacked_data/ 所有 mod，按加载顺序合并 patch 文件，
输出双语（EN+ZH）JSON 数据。

用法:
    python3 asset_resolver.py --data unpacked_data -o resolved_assets
    python3 asset_resolver.py --data unpacked_data --test  # 仅测试几个已知物品
"""

import argparse
import copy
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path


# ─────────────────────────────────────────────
# Mod 加载顺序配置
# ─────────────────────────────────────────────

# 内容 mod（后加载覆盖前）
CONTENT_MODS = [
    "Starbound",
    "Stardust Core Lite",
    "Frackin' Universe",
    # Frackin' Music — 跳过，纯音频
    "Arcana",
    "[Arcana]Titancorp Expansion",
    "[3.4 UPDATE]Voyage An Arcana Addon",
    "Multipass Arcana Addon",
    "bk3k's Inventory",
    "Efficient Watering",
    "Food Rot Info",
    "FU MushroomGun Compatibility Fix",
    "Frackin Universe More Planet Info Official Patch",
    "More Planet Info (work with 1.4.X not guaranteed)",
    "Voyage Fix",
    "disabled_drop_for_survival_mode",
]

# 中文翻译 mod（最后加载，只含 .patch）
CHINESE_MODS = [
    "zh_cn",
    "Fu sChinese Mod",
    "ArcanaSchinese",
    "[Arcana]Titancorp Expansion CN",
    "Simplified Chinese Translation Patch for Voyage",
    "Stardust Core Lite SChinese",
]

# 跳过的目录
SKIP_DIRS = {
    "zh_cn_font",
    "Frackin' Music",
}

# 要扫描的游戏数据文件扩展名 → 类型
GAME_FILE_TYPES = {
    # items
    ".item": "item",
    ".activeitem": "item",
    ".consumable": "item",
    ".augment": "item",
    ".head": "item",
    ".chest": "item",
    ".legs": "item",
    ".back": "item",
    ".liqitem": "item",
    ".matitem": "item",
    ".coinitem": "item",
    ".currency": "item",
    ".instrument": "item",
    ".thrownitem": "item",
    ".flashlight": "item",
    ".miningtool": "item",
    ".beamaxe": "item",
    ".tillingtool": "item",
    ".harvestingtool": "item",
    ".inspectiontool": "item",
    ".painttool": "item",
    ".wiretool": "item",
    ".unlock": "item",
    # others
    ".object": "object",
    ".recipe": "recipe",
    ".codex": "codex",
    ".monstertype": "monster",
    ".biome": "biome",
    ".statuseffect": "statuseffect",
    ".tech": "tech",
    ".species": "species",
    ".liquid": "liquid",
    ".weather": "weather",
    ".treasurepools": "treasurepools",
    ".tenant": "tenant",
    ".questtemplate": "quest",
    ".npctype": "npc",
    ".raceeffect": "raceeffect",
    ".collection": "collection",
}

# 需要提取中英双语的文本字段路径
BILINGUAL_FIELDS = [
    "/shortdescription",
    "/shortDescription",  # .tech 用大写 D
    "/description",
    "/title",
    "/label",             # statuseffect
    "/friendlyName",      # biome
    "/charCreationTooltip/description",  # species
    "/charCreationTooltip/title",
]

# 各类型的 ID 字段
ID_FIELDS = {
    "item": "itemName",
    "object": "objectName",
    "monster": "type",
    "biome": "name",
    "codex": "id",
    "tech": "name",
    "species": "kind",
    "statuseffect": "name",
    "liquid": "name",
    "npc": "type",
    "raceeffect": None,     # 用文件名
    "weather": None,        # 用文件名
    "tenant": None,         # 用文件名
    "quest": "id",
    "collection": None,     # 用文件名
    "recipe": None,         # 用 output.item
    "treasurepools": None,  # 多个 pool name 在一个文件里
}


# ─────────────────────────────────────────────
# JSON 宽松解析
# ─────────────────────────────────────────────

def _escape_control_chars_in_strings(text: str) -> str:
    """转义 JSON 字符串内部的非法控制字符（换行、回车、Tab）。
    
    Starbound 的 .activeitem 等文件经常在 description 字段里
    直接换行，这在标准 JSON 中是非法的。
    此函数逐字符扫描，仅在双引号内部做替换，不影响 JSON 结构。
    """
    out = []
    in_str = False
    escaped = False
    for ch in text:
        if escaped:
            out.append(ch)
            escaped = False
            continue
        if ch == '\\' and in_str:
            out.append(ch)
            escaped = True
            continue
        if ch == '"':
            in_str = not in_str
        if in_str and ch == '\n':
            out.append('\\n')
            continue
        if in_str and ch == '\r':
            out.append('\\r')
            continue
        if in_str and ch == '\t':
            out.append('\\t')
            continue
        out.append(ch)
    return ''.join(out)


def parse_json_lenient(filepath: Path) -> dict | list | None:
    """宽松 JSON 解析：处理 BOM、// 注释、/* */ 块注释、尾逗号、字符串内换行。"""
    try:
        raw = filepath.read_bytes()
        # 处理 UTF-8 BOM
        if raw.startswith(b'\xef\xbb\xbf'):
            raw = raw[3:]
        text = raw.decode("utf-8", errors="replace")
        # 移除 // 行注释（注意不要误伤 URL 里的 //）
        text = re.sub(r'(?<!:)//.*?$', '', text, flags=re.MULTILINE)
        # 移除 /* */ 块注释
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        # 移除尾逗号
        text = re.sub(r',\s*([}\]])', r'\1', text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 兜底：转义字符串内的控制字符（常见于 .activeitem 的 description）
            text = _escape_control_chars_in_strings(text)
            return json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


# ─────────────────────────────────────────────
# JSON Patch 引擎 (RFC 6902 + Starbound 扩展)
# ─────────────────────────────────────────────

def _resolve_pointer(doc, path: str):
    """解析 JSON Pointer，返回 (parent, key) 或 None。"""
    if path == "" or path == "/":
        return None, None

    parts = path.strip("/").split("/")
    current = doc
    for i, part in enumerate(parts[:-1]):
        # 数组索引
        if isinstance(current, list):
            try:
                idx = int(part)
                current = current[idx]
            except (ValueError, IndexError):
                return None, None
        elif isinstance(current, dict):
            if part not in current:
                return None, None
            current = current[part]
        else:
            return None, None

    last = parts[-1]
    if isinstance(current, list):
        if last == "-":
            return current, len(current)
        try:
            return current, int(last)
        except ValueError:
            return None, None
    elif isinstance(current, dict):
        return current, last
    return None, None


def _get_value(doc, path: str):
    """获取 JSON Pointer 指向的值。"""
    if path == "" or path == "/":
        return doc
    parts = path.strip("/").split("/")
    current = doc
    for part in parts:
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        else:
            return None
    return current


def apply_patch_op(doc: dict | list, op: dict) -> bool:
    """应用单个 JSON Patch 操作。返回是否成功。"""
    operation = op.get("op", "")
    path = op.get("path", "")
    value = op.get("value")

    if operation == "replace":
        parent, key = _resolve_pointer(doc, path)
        if parent is None:
            return False
        if isinstance(parent, list):
            if isinstance(key, int) and 0 <= key < len(parent):
                parent[key] = value
                return True
            return False
        parent[key] = value
        return True

    elif operation == "add":
        parent, key = _resolve_pointer(doc, path)
        if parent is None:
            # 尝试创建中间路径
            return _add_with_create(doc, path, value)
        if isinstance(parent, list):
            if isinstance(key, int):
                parent.insert(key, value)
            else:
                parent.append(value)
            return True
        parent[key] = value
        return True

    elif operation == "remove":
        parent, key = _resolve_pointer(doc, path)
        if parent is None:
            return False
        if isinstance(parent, list) and isinstance(key, int):
            if 0 <= key < len(parent):
                parent.pop(key)
                return True
            return False
        if isinstance(parent, dict) and key in parent:
            del parent[key]
            return True
        return False

    elif operation == "test":
        existing = _get_value(doc, path)
        inverse = op.get("inverse", False)
        if inverse:
            return existing != value
        return existing == value

    elif operation == "copy":
        source = _get_value(doc, op.get("from", ""))
        if source is None:
            return False
        parent, key = _resolve_pointer(doc, path)
        if parent is None:
            return False
        if isinstance(parent, dict):
            parent[key] = copy.deepcopy(source)
        return True

    elif operation == "move":
        source = _get_value(doc, op.get("from", ""))
        if source is None:
            return False
        # remove from source
        from_parent, from_key = _resolve_pointer(doc, op.get("from", ""))
        if from_parent is not None:
            if isinstance(from_parent, dict):
                del from_parent[from_key]
            elif isinstance(from_parent, list) and isinstance(from_key, int):
                from_parent.pop(from_key)
        # add to target
        parent, key = _resolve_pointer(doc, path)
        if parent is None:
            return False
        if isinstance(parent, dict):
            parent[key] = source
        elif isinstance(parent, list):
            parent.insert(key if isinstance(key, int) else len(parent), source)
        return True

    return False


def _add_with_create(doc, path: str, value) -> bool:
    """add 操作：如果中间路径不存在，自动创建。"""
    parts = path.strip("/").split("/")
    current = doc
    for i, part in enumerate(parts[:-1]):
        if isinstance(current, dict):
            if part not in current:
                # 判断下一级是 dict 还是 list
                next_part = parts[i + 1] if i + 1 < len(parts) else ""
                try:
                    int(next_part)
                    current[part] = []
                except ValueError:
                    current[part] = {}
            current = current[part]
        elif isinstance(current, list):
            try:
                idx = int(part)
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return False
            except ValueError:
                return False
        else:
            return False

    last = parts[-1]
    if isinstance(current, dict):
        current[last] = value
        return True
    elif isinstance(current, list):
        if last == "-":
            current.append(value)
            return True
        try:
            current.insert(int(last), value)
            return True
        except (ValueError, IndexError):
            return False
    return False


def apply_patch(doc: dict | list, patch_data: list) -> dict | list:
    """
    应用 JSON Patch 到文档。

    支持 Starbound 扩展：
    - 嵌套条件组 [[{test...}, {replace...}], [{add...}]]
    - test 操作的 inverse 字段
    """
    if not isinstance(patch_data, list):
        return doc

    for entry in patch_data:
        if isinstance(entry, list):
            # 嵌套条件组：第一个是 test，后续是操作
            # 如果 test 通过则执行后续，否则跳过整组
            all_passed = True
            ops = []
            for item in entry:
                if isinstance(item, dict):
                    if item.get("op") == "test":
                        if not apply_patch_op(doc, item):
                            all_passed = False
                            break
                    else:
                        ops.append(item)
                elif isinstance(item, list):
                    # 更深层嵌套
                    doc = apply_patch(doc, [item])
            if all_passed:
                for op in ops:
                    apply_patch_op(doc, op)
        elif isinstance(entry, dict):
            if entry.get("op") == "test":
                # 顶层 test 失败则停止整个 patch
                if not apply_patch_op(doc, entry):
                    break
            else:
                apply_patch_op(doc, entry)

    return doc


# ─────────────────────────────────────────────
# 双语字段提取
# ─────────────────────────────────────────────

def extract_bilingual_fields(en_doc: dict, zh_doc: dict) -> dict:
    """
    对比英文版和中文版文档，提取双语字段。

    返回: {"shortdescription_zh": "复合弓", ...}
    """
    zh_fields = {}
    for field_path in BILINGUAL_FIELDS:
        en_val = _get_value(en_doc, field_path)
        zh_val = _get_value(zh_doc, field_path)
        if zh_val and zh_val != en_val:
            # 将 /path/to/field 转为 field_zh 键名
            field_name = field_path.rstrip("/").split("/")[-1]
            zh_fields[f"{field_name}_zh"] = zh_val
    return zh_fields


# ─────────────────────────────────────────────
# Mod 扫描器
# ─────────────────────────────────────────────

def get_entity_id(data: dict | list, entity_type: str, filepath: Path) -> str | None:
    """提取实体 ID。"""
    if not isinstance(data, dict):
        return None
    id_field = ID_FIELDS.get(entity_type)
    if id_field:
        return data.get(id_field)
    # 无固定 ID 字段的类型，用文件名（去后缀）
    stem = filepath.stem
    # 处理双后缀如 .monstertype.patch → 去掉 .monstertype
    for ext in GAME_FILE_TYPES:
        if stem.endswith(ext.lstrip(".")):
            stem = stem[:-len(ext.lstrip("."))]
            break
    return stem or None


class AssetResolver:
    """Mod 资产扫描与 Patch 合并引擎。"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        # asset_path → {mod_name, filepath, data}
        self.assets: dict[str, dict] = {}
        # asset_path → list of (mod_name, patch_filepath)
        self.patches: dict[str, list[tuple[str, Path]]] = defaultdict(list)
        # CN patches 单独存
        self.cn_patches: dict[str, list[tuple[str, Path]]] = defaultdict(list)
        # 统计
        self.stats = defaultdict(int)

    def scan(self):
        """扫描所有 mod，注册基础文件和 patch。"""
        print("📦 扫描 mod 目录...")
        start = time.time()

        # 扫描内容 mod
        for mod_name in CONTENT_MODS:
            mod_dir = self.data_dir / mod_name
            if not mod_dir.exists():
                continue
            self._scan_mod(mod_name, mod_dir, is_chinese=False)

        # 扫描中文 mod（只注册 patch）
        for mod_name in CHINESE_MODS:
            mod_dir = self.data_dir / mod_name
            if not mod_dir.exists():
                continue
            self._scan_mod(mod_name, mod_dir, is_chinese=True)

        elapsed = time.time() - start
        print(f"   完成! 耗时 {elapsed:.1f}s")
        print(f"   基础文件: {len(self.assets)}")
        print(f"   内容 patch: {sum(len(v) for v in self.patches.values())}")
        print(f"   中文 patch: {sum(len(v) for v in self.cn_patches.values())}")

    def _scan_mod(self, mod_name: str, mod_dir: Path, is_chinese: bool):
        """扫描单个 mod 目录。"""
        count = 0
        for root, dirs, files in os.walk(mod_dir):
            # 跳过开发目录
            root_path = Path(root)
            rel_to_mod = root_path.relative_to(mod_dir)
            parts = rel_to_mod.parts
            if any(p.startswith(("a_", ".")) for p in parts):
                continue

            for filename in files:
                filepath = root_path / filename

                # 检查是否是 .patch 文件
                if filename.endswith(".patch"):
                    # 推断被 patch 的原始资产路径
                    base_filename = filename[:-6]  # 去掉 .patch
                    asset_path = str((rel_to_mod / base_filename)).replace("\\", "/")

                    # 检查是否是我们关心的文件类型
                    base_ext = Path(base_filename).suffix
                    if base_ext not in GAME_FILE_TYPES and not base_filename.endswith((".config", ".configfunctions")):
                        continue

                    if is_chinese:
                        self.cn_patches[asset_path].append((mod_name, filepath))
                    else:
                        self.patches[asset_path].append((mod_name, filepath))
                    count += 1
                    continue

                # 检查是否是基础游戏数据文件
                suffix = filepath.suffix
                if suffix not in GAME_FILE_TYPES:
                    # 也收集 .config 和 .configfunctions（配方、配置等）
                    if suffix not in (".config", ".configfunctions"):
                        continue

                asset_path = str((rel_to_mod / filename)).replace("\\", "/")

                # 后加载的 mod 覆盖先加载的
                self.assets[asset_path] = {
                    "mod_name": mod_name,
                    "filepath": filepath,
                    "entity_type": GAME_FILE_TYPES.get(suffix, "config"),
                }
                count += 1

        self.stats[f"scan_{mod_name}"] = count

    def resolve_all(self) -> dict[str, dict]:
        """
        合并所有资产：基础文件 + 内容 patch + 中文 patch。

        返回: {asset_path: {merged_data + 元信息}}
        """
        print(f"\n🔧 合并资产...")
        start = time.time()

        results = {}
        total = len(self.assets)
        processed = 0
        errors = 0

        for asset_path, info in self.assets.items():
            filepath = info["filepath"]
            mod_name = info["mod_name"]
            entity_type = info["entity_type"]

            # 1. 加载基础文件
            data = parse_json_lenient(filepath)
            if data is None:
                errors += 1
                continue

            patched_by = []

            # 2. 应用内容 patch
            if asset_path in self.patches:
                for patch_mod, patch_path in self.patches[asset_path]:
                    patch_data = parse_json_lenient(patch_path)
                    if patch_data is not None:
                        data = apply_patch(data, patch_data)
                        patched_by.append(patch_mod)

            # 3. 保存英文版快照（用于双语对比）
            en_snapshot = copy.deepcopy(data) if asset_path in self.cn_patches else None

            # 4. 应用中文 patch
            if asset_path in self.cn_patches:
                for cn_mod, cn_path in self.cn_patches[asset_path]:
                    patch_data = parse_json_lenient(cn_path)
                    if patch_data is not None:
                        data = apply_patch(data, patch_data)
                        patched_by.append(cn_mod)

            # 5. 提取双语字段
            zh_fields = {}
            if en_snapshot is not None and isinstance(data, dict) and isinstance(en_snapshot, dict):
                zh_fields = extract_bilingual_fields(en_snapshot, data)
                # 恢复英文值到主文档（保持英文为主）
                for field_path in BILINGUAL_FIELDS:
                    en_val = _get_value(en_snapshot, field_path)
                    if en_val is not None:
                        parent, key = _resolve_pointer(data, field_path)
                        if parent is not None and isinstance(parent, dict):
                            parent[key] = en_val

            # 6. 提取 ID
            entity_id = None
            if isinstance(data, dict):
                entity_id = get_entity_id(data, entity_type, filepath)

            # 7. 组装结果
            result = {
                "_asset_path": asset_path,
                "_entity_type": entity_type,
                "_source_mod": mod_name,
                "_patched_by": patched_by,
                "_entity_id": entity_id,
            }
            # 合并双语字段
            if zh_fields:
                result["_zh"] = zh_fields
            # 合并原始数据
            if isinstance(data, dict):
                result["_data"] = data
            elif isinstance(data, list):
                result["_data"] = data
            else:
                result["_data"] = data

            results[asset_path] = result

            processed += 1
            if processed % 5000 == 0:
                elapsed = time.time() - start
                print(f"   ⏳ {processed}/{total} ({elapsed:.1f}s)")

        elapsed = time.time() - start
        print(f"   ✅ 完成! {processed} 个资产合并, {errors} 个解析失败, 耗时 {elapsed:.1f}s")

        self.stats["resolved"] = processed
        self.stats["errors"] = errors

        return results


# ─────────────────────────────────────────────
# 输出
# ─────────────────────────────────────────────

def save_resolved_assets(results: dict[str, dict], output_dir: Path):
    """将合并后的资产保存为 JSON 文件。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 按 entity_type 分组保存
    type_dirs = set()
    count = 0
    index_entries = []

    for asset_path, result in results.items():
        entity_type = result["_entity_type"]
        entity_id = result.get("_entity_id")
        data = result.get("_data")

        if data is None:
            continue

        # 构建输出 JSON
        output = {}
        if isinstance(data, dict):
            output = dict(data)
        else:
            output = {"_raw": data}

        # 注入元信息
        output["_meta"] = {
            "asset_path": asset_path,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "source_mod": result["_source_mod"],
            "patched_by": result["_patched_by"],
        }
        if result.get("_zh"):
            output["_meta"]["zh"] = result["_zh"]

        # 保存文件
        type_dir = output_dir / entity_type
        type_dir.mkdir(parents=True, exist_ok=True)
        type_dirs.add(entity_type)

        # 文件名：用 entity_id，或用 asset_path 的安全版本
        if entity_id:
            safe_name = re.sub(r'[<>:"|?*\\/]', '_', entity_id)[:200]
        else:
            safe_name = re.sub(r'[<>:"|?*\\/]', '_', asset_path.replace("/", "__"))[:200]

        out_path = type_dir / f"{safe_name}.json"

        # 处理重名（不同 mod 的同名文件或截断冲突）
        if out_path.exists():
            mod_suffix = re.sub(r'[^a-zA-Z0-9]', '', result["_source_mod"])[:20]
            out_path = type_dir / f"{safe_name}__{mod_suffix}.json"
            # 如果仍然重名，加序号
            seq = 2
            base_out = out_path
            while out_path.exists():
                out_path = base_out.with_suffix(f".{seq}.json")
                seq += 1

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        # 索引条目
        idx = {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "source_mod": result["_source_mod"],
            "asset_path": asset_path,
            "file": str(out_path.relative_to(output_dir)),
        }
        if result.get("_zh"):
            idx["zh"] = result["_zh"]
        if isinstance(data, dict):
            for f_name in ("shortdescription", "shortDescription", "title", "label", "friendlyName"):
                if f_name in data:
                    idx["title_en"] = data[f_name]
                    break
        index_entries.append(idx)
        count += 1

    # 写入索引
    index_path = output_dir / "index.jsonl"
    with open(index_path, "w", encoding="utf-8") as f:
        for entry in sorted(index_entries, key=lambda x: x.get("entity_id") or ""):
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # 写入统计
    type_counts = defaultdict(int)
    for entry in index_entries:
        type_counts[entry["entity_type"]] += 1

    zh_count = sum(1 for e in index_entries if e.get("zh"))

    meta = {
        "total": count,
        "by_type": dict(sorted(type_counts.items())),
        "with_zh": zh_count,
        "types": sorted(type_dirs),
    }
    meta_path = output_dir / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n💾 输出目录: {output_dir.resolve()}")
    print(f"   总文件数: {count}")
    print(f"   有中文翻译: {zh_count}")
    print(f"   类型分布:")
    for t, c in sorted(type_counts.items()):
        print(f"     {t:20s}: {c:>6}")


# ─────────────────────────────────────────────
# 测试模式
# ─────────────────────────────────────────────

def run_test(data_dir: Path):
    """测试模式：验证几个已知物品的合并结果。"""
    resolver = AssetResolver(data_dir)
    resolver.scan()
    results = resolver.resolve_all()

    test_cases = [
        # (关键词, 期望类型, 期望的英文名, 期望有中文)
        ("compoundbow", "item", "Compound Bow", True),
        ("ironore", "item", "Iron Ore", True),
        ("exonite", "item", "Exonite Crystal", True),
        ("arcana_ore_corrodiumOre", "item", "Corrodium Ore", True),
        ("doublejump", "tech", "Pulse Jump", True),
        ("burning", None, None, True),
    ]

    print("\n" + "═" * 60)
    print("  测试模式：验证已知物品的合并结果")
    print("═" * 60)

    for keyword, expected_type, expected_en, expect_zh in test_cases:
        # 优先精确匹配 entity_id + type
        found = None
        candidates = []
        for path, result in results.items():
            eid = result.get("_entity_id", "")
            if eid and keyword.lower() in eid.lower():
                candidates.append(result)
        # 优先匹配期望类型
        if expected_type:
            for c in candidates:
                if c["_entity_type"] == expected_type:
                    found = c
                    break
        if not found and candidates:
            found = candidates[0]
        if not found:
            for path, result in results.items():
                if keyword.lower() in path.lower():
                    if expected_type is None or result["_entity_type"] == expected_type:
                        found = result
                        break

        if found:
            data = found.get("_data", {})
            zh = found.get("_zh", {})
            en_name = (data.get("shortdescription") or data.get("shortDescription")
                       or data.get("title") or data.get("label") or data.get("friendlyName") or "")
            zh_name = (zh.get("shortdescription_zh") or zh.get("shortDescription_zh")
                       or zh.get("title_zh") or zh.get("label_zh") or zh.get("friendlyName_zh") or "")

            status = "✅" if (not expected_en or en_name == expected_en) else "⚠️"
            zh_status = "✅" if (not expect_zh or zh_name) else "❌"

            print(f"\n  {keyword}:")
            print(f"    来源: {found['_source_mod']}")
            print(f"    Patch: {found['_patched_by']}")
            print(f"    EN: {en_name} {status}")
            print(f"    ZH: {zh_name} {zh_status}")
            print(f"    类型: {found['_entity_type']}")
        else:
            print(f"\n  {keyword}: ❌ 未找到!")

    print("\n" + "═" * 60)


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Mod 资产扫描与 Patch 合并引擎")
    parser.add_argument("--data", type=Path, default=Path("unpacked_data"),
                        help="unpacked_data 目录路径 (默认: unpacked_data)")
    parser.add_argument("-o", "--output", type=Path, default=Path("resolved_assets"),
                        help="输出目录 (默认: resolved_assets)")
    parser.add_argument("--test", action="store_true",
                        help="仅运行测试模式，验证几个已知物品")

    args = parser.parse_args()

    if not args.data.exists():
        print(f"❌ 数据目录不存在: {args.data}", file=sys.stderr)
        sys.exit(1)

    if args.test:
        run_test(args.data)
    else:
        resolver = AssetResolver(args.data)
        resolver.scan()
        results = resolver.resolve_all()
        save_resolved_assets(results, args.output)


if __name__ == "__main__":
    main()
