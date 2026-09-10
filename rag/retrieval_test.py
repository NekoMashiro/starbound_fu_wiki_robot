"""Retrieval-only eval: RRF vs old weighted fusion, with rank / MRR."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from query import RAGEngine

CASES = [
    {
        "q": "钨矿怎么熔炼啊，我的熔炉里没有钨锭的配方",
        "expect_any": ["tungstenbar", "tungstenore"],
        "note": "熔炼配方应命中钨锭/钨矿",
    },
    {
        "q": "超致密武士刀怎么做",
        "expect_any": ["densiniumkatana"],
        "note": "新补的 activeitem",
    },
    {
        "q": "超致密武士刀和日耀武士刀哪个更强",
        "expect_all": ["densiniumkatana", "solariumkatana"],
        "note": "对比问法应同时召回两把刀",
    },
    {
        "q": "绒山羊掉什么",
        "expect_any": ["capricoat"],
        "note": "怪物掉落",
    },
    {
        "q": "武士刀的掉落率是多少？我打了三次鲛人主线了还没掉",
        "expect_any": ["hylotl", "katana", "mission"],
        "match": "id_or_name",
        "note": "模糊品类+任务掉落",
    },
    {
        "q": "我有必要最优先升级发明家工作台吗",
        "expect_any": ["inventor", "crafting", "research", "工"],
        "match": "id_or_name",
        "note": "攻略/工作台升级",
    },
    {
        "q": "木质托盘种不出菜，放了土豆种子和水还有腐烂食物",
        "expect_any": ["tray", "hydro", "growing", "wooden", "托盘", "种植"],
        "match": "id_or_name",
        "note": "农业种植",
    },
    {
        "q": "开局有必要疯狂种棉花吗",
        "expect_any": ["cotton", "棉花"],
        "match": "id_or_name",
        "note": "棉花用途",
    },
    {
        "q": "Anima Shard 在哪些生态能挖到",
        "expect_any": ["arcana_ore_animaOre", "animaOre"],
        "note": "矿石-生态关联",
    },
    {
        "q": "农业科技里哪些比较重要",
        "expect_any": ["research", "农业", "farming", "agriculture"],
        "match": "id_or_name",
        "note": "研究树/科技",
    },
]


def hit_ok(r: dict, token: str, mode: str) -> bool:
    meta = r["metadata"]
    eid = (meta.get("entity_id") or r.get("id") or "").lower()
    name = f"{meta.get('name_en','')} {meta.get('name_zh','')} {eid}".lower()
    t = token.lower()
    if mode == "id":
        return t in eid
    return t in name or t in eid


def first_rank(results: list[dict], tokens: list[str], mode: str) -> int | None:
    """1-based rank of the first result matching any token."""
    for i, r in enumerate(results, 1):
        if any(hit_ok(r, token, mode) for token in tokens):
            return i
    return None


def all_ranks(results: list[dict], tokens: list[str], mode: str) -> list[int | None]:
    ranks = []
    for token in tokens:
        rank = None
        for i, r in enumerate(results, 1):
            if hit_ok(r, token, mode):
                rank = i
                break
        ranks.append(rank)
    return ranks


def score_case(results: list[dict], case: dict) -> dict:
    mode = case.get("match", "id")
    if "expect_all" in case:
        tokens = case["expect_all"]
        ranks = all_ranks(results, tokens, mode)
        ok = all(r is not None for r in ranks)
        mrr = sum((1 / r if r else 0) for r in ranks) / len(ranks)
        best = min((r for r in ranks if r is not None), default=None)
        return {"ok": ok, "mrr": mrr, "best_rank": best, "ranks": ranks, "missing": [
            t for t, r in zip(tokens, ranks) if r is None
        ]}

    tokens = case["expect_any"]
    rank = first_rank(results, tokens, mode)
    ok = rank is not None
    return {
        "ok": ok,
        "mrr": (1 / rank) if rank else 0.0,
        "best_rank": rank,
        "ranks": [rank],
        "missing": [] if ok else tokens,
    }


def fmt_rank(rank: int | None) -> str:
    return str(rank) if rank is not None else "-"


def top_preview(results: list[dict], n: int = 5) -> str:
    parts = []
    for r in results[:n]:
        meta = r["metadata"]
        parts.append(
            f"{meta.get('entity_type', '?')}:"
            f"{meta.get('entity_id') or meta.get('name_en', '?')}"
            f"({meta.get('name_zh') or meta.get('name_en') or '?'})"
        )
    return " | ".join(parts)


def main():
    engine = RAGEngine()
    print("\n" + "=" * 72)
    print("  检索评测  ·  weighted(旧) vs RRF(新)  ·  同一候选池")
    print("=" * 72)

    rows = []
    for i, case in enumerate(CASES, 1):
        compared = engine.search_compare(case["q"])
        old = score_case(compared["weighted"], case)
        new = score_case(compared["rrf"], case)
        rows.append((case, old, new, compared))

        old_mark = "OK" if old["ok"] else "MISS"
        new_mark = "OK" if new["ok"] else "MISS"
        delta = ""
        if old["best_rank"] and new["best_rank"]:
            diff = old["best_rank"] - new["best_rank"]
            if diff > 0:
                delta = f"  rank +{diff}"
            elif diff < 0:
                delta = f"  rank {diff}"
        elif new["ok"] and not old["ok"]:
            delta = "  新命中"
        elif old["ok"] and not new["ok"]:
            delta = "  新丢失"

        print(f"\n[{i}] {case['q']}")
        print(f"    期望: {case.get('expect_all') or case['expect_any']}  ({case['note']})")
        print(
            f"    旧 {old_mark} rank={fmt_rank(old['best_rank'])} mrr={old['mrr']:.3f}  |  "
            f"新 {new_mark} rank={fmt_rank(new['best_rank'])} mrr={new['mrr']:.3f}"
            f"{delta}"
        )
        if "expect_all" in case:
            tokens = case["expect_all"]
            print(
                f"    分条: 旧 {list(zip(tokens, [fmt_rank(r) for r in old['ranks']]))}  "
                f"新 {list(zip(tokens, [fmt_rank(r) for r in new['ranks']]))}"
            )
        if new["missing"]:
            print(f"    新未命中: {new['missing']}")
        print(f"    旧 top: {top_preview(compared['weighted'])}")
        print(f"    新 top: {top_preview(compared['rrf'])}")

    old_hit = sum(1 for _, old, _, _ in rows if old["ok"])
    new_hit = sum(1 for _, _, new, _ in rows if new["ok"])
    old_mrr = sum(old["mrr"] for _, old, _, _ in rows) / len(rows)
    new_mrr = sum(new["mrr"] for _, _, new, _ in rows) / len(rows)
    improved = sum(
        1 for _, old, new, _ in rows
        if (new["mrr"] - old["mrr"]) > 1e-9
    )
    worsened = sum(
        1 for _, old, new, _ in rows
        if (old["mrr"] - new["mrr"]) > 1e-9
    )

    print(f"\n{'=' * 72}")
    print(
        f"  Hit@10   旧 {old_hit}/{len(CASES)}   →  新 {new_hit}/{len(CASES)}"
    )
    print(f"  MRR      旧 {old_mrr:.3f}   →  新 {new_mrr:.3f}")
    print(f"  变好 {improved} 条 / 变差 {worsened} 条 / 持平 {len(CASES) - improved - worsened} 条")
    print("=" * 72)


if __name__ == "__main__":
    main()
