"""Retrieval-only eval: check whether expected entities land in top-k."""

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


def main():
    engine = RAGEngine()
    print("\n" + "=" * 64)
    print("  检索评测")
    print("=" * 64)

    passed = 0
    for i, case in enumerate(CASES, 1):
        mode = case.get("match", "id")
        results = engine.search(engine._translator.enhance_query(case["q"]))
        hits = []
        for r in results:
            meta = r["metadata"]
            hits.append(
                f"{meta.get('entity_type','?')}:{meta.get('entity_id') or meta.get('name_en','?')} "
                f"({meta.get('name_zh') or meta.get('name_en') or '?'})"
            )

        ok = True
        missing = []
        if "expect_all" in case:
            for token in case["expect_all"]:
                if not any(hit_ok(r, token, mode) for r in results):
                    ok = False
                    missing.append(token)
        if "expect_any" in case:
            if not any(
                hit_ok(r, token, mode)
                for token in case["expect_any"]
                for r in results
            ):
                ok = False
                missing = case["expect_any"]

        passed += int(ok)
        mark = "✅" if ok else "❌"
        print(f"\n{mark} [{i}] {case['q']}")
        print(f"    期望: {case.get('expect_all') or case['expect_any']}  ({case['note']})")
        if missing and not ok:
            print(f"    未命中: {missing}")
        print(f"    top: {hits[:5]}")

    print(f"\n{'=' * 64}")
    print(f"  检索通过 {passed}/{len(CASES)}")
    print("=" * 64)


if __name__ == "__main__":
    main()
