#!/usr/bin/env python3
"""
treasure_pool_resolver.py — 宝藏池递归展平 + 反向索引

递归展平 Starbound/FU 的 treasure pool 嵌套结构，
计算每个物品的最终掉落概率，建立反向索引。

用法:
    python3 treasure_pool_resolver.py --assets resolved_assets -o treasure_db
    python3 treasure_pool_resolver.py --assets resolved_assets --query capricoatTreasure
    python3 treasure_pool_resolver.py --assets resolved_assets --item leather
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# 概率精度（小数位数）
PRECISION = 4
# 截断阈值：低于此概率的物品丢弃
MIN_PROBABILITY = 0.0001  # 0.01%
# 递归深度保护
MAX_DEPTH = 20


# ─────────────────────────────────────────────
# Pool 注册表：加载所有 pool 定义
# ─────────────────────────────────────────────

def load_all_pools(assets_dir: Path) -> dict[str, list]:
    """从 treasurepools/ 目录加载所有 pool 定义。"""
    pools = {}
    tp_dir = assets_dir / "treasurepools"
    if not tp_dir.exists():
        return pools

    for fn in os.listdir(tp_dir):
        if not fn.endswith(".json"):
            continue
        try:
            with open(tp_dir / fn) as f:
                d = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        if not isinstance(d, dict):
            continue

        for pool_name, pool_def in d.items():
            if pool_name == "_meta":
                continue
            pools[pool_name] = pool_def

    return pools


# ─────────────────────────────────────────────
# 递归展平引擎
# ─────────────────────────────────────────────

class TreasurePoolResolver:
    """递归展平宝藏池。"""

    def __init__(self, pools: dict[str, list]):
        self.pools = pools
        # 展平缓存
        self._cache: dict[str, list[dict]] = {}
        # 统计
        self.stats = {"resolved": 0, "cycles": 0, "missing": 0}

    def flatten(self, pool_name: str, level: int = 1) -> list[dict]:
        """
        展平一个 pool，返回掉落物品列表。

        每个条目: {item, probability, count}
        probability 为该物品在一次掉落事件中的期望概率。

        Args:
            pool_name: pool 名称
            level: 怪物等级（用于选择 pool 定义的层级）
        """
        cache_key = f"{pool_name}@{level}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = self._flatten_inner(pool_name, level, parent_prob=1.0, visited=set())
        # 合并同物品
        merged = self._merge_items(result)
        # 截断
        merged = [e for e in merged if e["probability"] >= MIN_PROBABILITY]
        # 排序
        merged.sort(key=lambda x: -x["probability"])

        self._cache[cache_key] = merged
        self.stats["resolved"] += 1
        return merged

    def _flatten_inner(
        self,
        pool_name: str,
        level: int,
        parent_prob: float,
        visited: set[str],
    ) -> list[dict]:
        """递归展平内部实现。"""
        if pool_name in visited:
            self.stats["cycles"] += 1
            return []
        if len(visited) >= MAX_DEPTH:
            return []

        pool_def = self.pools.get(pool_name)
        if pool_def is None:
            self.stats["missing"] += 1
            return []

        if not isinstance(pool_def, list) or len(pool_def) == 0:
            return []

        # 选择匹配 level 的定义
        definition = self._select_level(pool_def, level)
        if definition is None:
            return []

        visited = visited | {pool_name}
        return self._resolve_definition(definition, level, parent_prob, visited)

    def _select_level(self, pool_def: list, level: int) -> dict | None:
        """
        根据 level 选择 pool 定义。

        pool_def 是 [[level_threshold, definition], ...] 的列表，
        选择 level_threshold <= level 的最高项。
        """
        best = None
        best_threshold = -1

        for entry in pool_def:
            if not isinstance(entry, list) or len(entry) < 2:
                continue
            threshold = entry[0]
            definition = entry[1]
            if isinstance(threshold, (int, float)) and threshold <= level:
                if threshold > best_threshold:
                    best_threshold = threshold
                    best = definition

        return best

    def _resolve_definition(
        self,
        definition: dict,
        level: int,
        parent_prob: float,
        visited: set[str],
    ) -> list[dict]:
        """解析单个 pool definition。"""
        if not isinstance(definition, dict):
            return []

        results = []

        # 1. 处理 fill（固定掉落，不受 poolRounds 影响）
        for entry in definition.get("fill", []):
            results.extend(
                self._resolve_entry(entry, level, parent_prob, visited)
            )

        # 2. 处理 pool（加权随机池）
        pool_entries = definition.get("pool", [])
        if pool_entries:
            # 计算期望轮数
            expected_rounds = self._calc_expected_rounds(
                definition.get("poolRounds")
            )

            # 计算权重总和
            total_weight = sum(
                e.get("weight", 1.0) for e in pool_entries if isinstance(e, dict)
            )
            if total_weight <= 0:
                total_weight = 1.0

            # 每个条目的概率 = parent_prob × 期望轮数 × (weight / total_weight)
            for entry in pool_entries:
                if not isinstance(entry, dict):
                    continue
                weight = entry.get("weight", 1.0)
                entry_prob = parent_prob * expected_rounds * (weight / total_weight)

                if entry_prob < MIN_PROBABILITY * 0.1:
                    continue  # 提前剪枝

                results.extend(
                    self._resolve_entry(entry, level, entry_prob, visited)
                )

        return results

    def _resolve_entry(
        self,
        entry: dict,
        level: int,
        prob: float,
        visited: set[str],
    ) -> list[dict]:
        """解析单个 pool/fill 条目。"""
        if not isinstance(entry, dict):
            return []

        # 嵌套 pool 引用
        if "pool" in entry and isinstance(entry["pool"], str):
            return self._flatten_inner(entry["pool"], level, prob, visited)

        # 直接物品
        if "item" in entry:
            item_data = entry["item"]
            if isinstance(item_data, str):
                return [{"item": item_data, "probability": round(prob, PRECISION), "count": 1}]
            elif isinstance(item_data, list) and len(item_data) >= 1:
                item_name = item_data[0]
                count = item_data[1] if len(item_data) >= 2 else 1
                return [{"item": item_name, "probability": round(prob, PRECISION), "count": count}]

        return []

    def _calc_expected_rounds(self, pool_rounds) -> float:
        """
        计算期望轮数。

        poolRounds: [[probability, rounds], ...]
        E = Σ(prob × rounds)
        """
        if not pool_rounds or not isinstance(pool_rounds, list):
            return 1.0  # 默认 1 轮

        expected = 0.0
        for entry in pool_rounds:
            if isinstance(entry, list) and len(entry) >= 2:
                prob = entry[0]
                rounds = entry[1]
                expected += prob * rounds

        return expected if expected > 0 else 1.0

    def _merge_items(self, items: list[dict]) -> list[dict]:
        """合并同一物品的多个条目（概率相加，count 取加权平均）。"""
        merged = {}
        for item in items:
            key = item["item"]
            if key in merged:
                old = merged[key]
                total_prob = old["probability"] + item["probability"]
                # 加权平均 count
                if total_prob > 0:
                    avg_count = (
                        old["probability"] * old["count"]
                        + item["probability"] * item["count"]
                    ) / total_prob
                else:
                    avg_count = item["count"]
                old["probability"] = round(total_prob, PRECISION)
                old["count"] = round(avg_count, 1)
            else:
                merged[key] = {
                    "item": key,
                    "probability": item["probability"],
                    "count": item["count"],
                }
        return list(merged.values())


# ─────────────────────────────────────────────
# 反向索引：item → pool sources
# ─────────────────────────────────────────────

def build_reverse_index(
    resolver: TreasurePoolResolver,
) -> dict[str, list[dict]]:
    """
    建立物品 → pool 来源的反向索引。

    返回: {item_id: [{pool_name, probability, count}]}
    """
    reverse = defaultdict(list)

    for pool_name in resolver.pools:
        items = resolver.flatten(pool_name)
        for entry in items:
            reverse[entry["item"]].append({
                "pool": pool_name,
                "probability": entry["probability"],
                "count": entry["count"],
            })

    # 按概率排序
    for item_id in reverse:
        reverse[item_id].sort(key=lambda x: -x["probability"])

    return dict(reverse)


# ─────────────────────────────────────────────
# 怪物 → pool 映射
# ─────────────────────────────────────────────

def build_monster_pool_map(assets_dir: Path) -> dict[str, list[str]]:
    """
    从 monster 文件中提取 怪物 → treasure pool 的映射。

    返回: {pool_name: [monster_id, ...]}
    """
    pool_to_monsters = defaultdict(set)

    monster_dir = assets_dir / "monster"
    if not monster_dir.exists():
        return {}

    for fn in os.listdir(monster_dir):
        if not fn.endswith(".json"):
            continue
        try:
            with open(monster_dir / fn) as f:
                d = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        if not isinstance(d, dict):
            continue

        monster_id = d.get("type", fn.replace(".json", ""))

        # dropPools 是一个列表，每项是 {kill_type: pool_name}
        drop_pools = d.get("dropPools", [])
        if isinstance(drop_pools, list):
            for dp in drop_pools:
                if isinstance(dp, dict):
                    for kill_type, pool_name in dp.items():
                        if isinstance(pool_name, str):
                            pool_to_monsters[pool_name].add(monster_id)
                elif isinstance(dp, str):
                    pool_to_monsters[dp].add(monster_id)

        # baseParameters.dropPools
        bp = d.get("baseParameters", {})
        if isinstance(bp, dict):
            for dp in bp.get("dropPools", []):
                if isinstance(dp, dict):
                    for kill_type, pool_name in dp.items():
                        if isinstance(pool_name, str):
                            pool_to_monsters[pool_name].add(monster_id)

        # treasurePool (单个字段)
        tp = d.get("treasurePool", "")
        if tp:
            pool_to_monsters[tp].add(monster_id)

    return {k: sorted(v) for k, v in pool_to_monsters.items()}


# ─────────────────────────────────────────────
# 输出
# ─────────────────────────────────────────────

def save_treasure_db(
    resolver: TreasurePoolResolver,
    reverse_index: dict,
    monster_pool_map: dict,
    output_dir: Path,
):
    """保存宝藏池数据库。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 展平后的 pool → items
    pool_items = {}
    for pool_name in resolver.pools:
        items = resolver.flatten(pool_name)
        if items:
            pool_items[pool_name] = items
    with open(output_dir / "pool_drops.json", "w", encoding="utf-8") as f:
        json.dump(pool_items, f, ensure_ascii=False, indent=2)

    # 2. 反向索引 item → pools
    with open(output_dir / "item_drop_sources.json", "w", encoding="utf-8") as f:
        json.dump(reverse_index, f, ensure_ascii=False, indent=2)

    # 3. 怪物 → pool 映射
    with open(output_dir / "monster_pools.json", "w", encoding="utf-8") as f:
        json.dump(monster_pool_map, f, ensure_ascii=False, indent=2)

    # 4. 元数据
    meta = {
        "total_pools": len(resolver.pools),
        "resolved_pools": len(pool_items),
        "unique_items_dropped": len(reverse_index),
        "pools_with_monsters": len(monster_pool_map),
        "stats": resolver.stats,
    }
    with open(output_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n💾 输出目录: {output_dir.resolve()}")
    print(f"   pool 定义总数: {len(resolver.pools)}")
    print(f"   已展平 pool 数: {len(pool_items)}")
    print(f"   可掉落物品种类: {len(reverse_index)}")
    print(f"   怪物关联 pool 数: {len(monster_pool_map)}")
    print(f"   循环引用: {resolver.stats['cycles']}")
    print(f"   缺失引用: {resolver.stats['missing']}")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="宝藏池递归展平 + 反向索引")
    parser.add_argument("--assets", type=Path, default=Path("resolved_assets"),
                        help="resolved_assets 目录路径")
    parser.add_argument("-o", "--output", type=Path, default=Path("treasure_db"),
                        help="输出目录")
    parser.add_argument("--query", type=str, default=None,
                        help="展平指定 pool（测试模式）")
    parser.add_argument("--item", type=str, default=None,
                        help="查询物品掉落来源（测试模式）")
    parser.add_argument("--level", type=int, default=1,
                        help="怪物等级（默认 1）")

    args = parser.parse_args()

    if not args.assets.exists():
        print(f"❌ 目录不存在: {args.assets}", file=sys.stderr)
        sys.exit(1)

    print("📦 加载 treasure pool 定义...")
    pools = load_all_pools(args.assets)
    print(f"   {len(pools)} 个 pool")

    resolver = TreasurePoolResolver(pools)

    if args.query:
        # 展平单个 pool
        items = resolver.flatten(args.query, level=args.level)
        print(f"\n{'═' * 60}")
        print(f"  展平: {args.query} (level={args.level})")
        print(f"{'═' * 60}")
        if items:
            for e in items:
                pct = e["probability"] * 100
                print(f"  {e['item']:40s}  {pct:>7.2f}%  x{e['count']}")
        else:
            print("  (空或未找到)")

        # 也显示关联怪物
        monster_map = build_monster_pool_map(args.assets)
        monsters = monster_map.get(args.query, [])
        if monsters:
            print(f"\n  🐾 关联怪物 ({len(monsters)}):")
            for m in monsters[:10]:
                print(f"    - {m}")

        print(f"\n{'═' * 60}")

    elif args.item:
        # 查询物品掉落来源
        reverse = build_reverse_index(resolver)
        monster_map = build_monster_pool_map(args.assets)

        sources = reverse.get(args.item, [])
        print(f"\n{'═' * 60}")
        print(f"  物品掉落来源: {args.item}")
        print(f"{'═' * 60}")
        if sources:
            for s in sources[:20]:
                pct = s["probability"] * 100
                monsters = monster_map.get(s["pool"], [])
                monster_str = f"  ← {', '.join(monsters[:3])}" if monsters else ""
                print(f"  {s['pool']:40s}  {pct:>7.2f}%  x{s['count']}{monster_str}")
        else:
            print("  (未找到掉落来源)")
        print(f"\n{'═' * 60}")

    else:
        # 完整构建
        print("\n🔧 展平所有 pool...")
        reverse = build_reverse_index(resolver)
        print(f"   {len(reverse)} 种物品有掉落来源")

        print("🐾 构建怪物 → pool 映射...")
        monster_map = build_monster_pool_map(args.assets)

        save_treasure_db(resolver, reverse, monster_map, args.output)


if __name__ == "__main__":
    main()
