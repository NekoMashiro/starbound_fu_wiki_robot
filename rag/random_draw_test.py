"""抽签：过滤和对池不进网；同一种子应抽到同一条。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from random_draw import Candidate, RandomCatalog, is_drawable, matches_pool
from random_pools import POOL_BY_ID


def test_is_drawable() -> int:
    cases = [
        ({'name_zh': '绒山羊', 'quality_tier': 'A'}, True),
        ({'name_en': 'Capricoat', 'quality_tier': 'C'}, True),
        ({'name_zh': '废矿', 'quality_tier': 'D'}, False),
        ({'name_zh': '', 'name_en': '', 'quality_tier': 'A'}, False),
    ]
    failed = 0
    for entity, expect in cases:
        got = is_drawable(entity)
        ok = got is expect
        print(f'  [{"OK" if ok else "FAIL"}] drawable {entity} -> {got}')
        if not ok:
            failed += 1
    return failed


def test_matches_pool() -> int:
    food = POOL_BY_ID['food']
    monster = POOL_BY_ID['monster']
    bee = POOL_BY_ID['bee']
    cases = [
        ({'entity_type': 'item', 'category': 'preparedFood'}, food, True),
        ({'entity_type': 'item', 'category': 'drink'}, food, False),
        ({'entity_type': 'monster', 'name_zh': '绒山羊'}, monster, True),
        ({'entity_type': 'item', 'category': 'preparedFood'}, monster, False),
        ({'entity_type': 'item', 'tags': ['bee']}, bee, True),
        ({'entity_type': 'item', 'tags': ['weapon']}, bee, False),
    ]
    failed = 0
    for entity, pool, expect in cases:
        got = matches_pool(entity, pool)
        ok = got is expect
        print(f'  [{"OK" if ok else "FAIL"}] {pool.id} {entity} -> {got}')
        if not ok:
            failed += 1
    return failed


def test_draw_seed() -> int:
    food = POOL_BY_ID['food']
    any_pool = POOL_BY_ID['any']
    catalog = RandomCatalog({
        'food': (
            Candidate('a', 'item', 'entities/item/a.json', 'A', '甲'),
            Candidate('b', 'item', 'entities/item/b.json', 'B', '乙'),
            Candidate('c', 'item', 'entities/item/c.json', 'C', '丙'),
        ),
        'drink': (
            Candidate('d', 'item', 'entities/item/d.json', 'D', '丁'),
        ),
        'monster': (
            Candidate('m', 'monster', 'entities/monster/m.json', 'M', '怪'),
        ),
        'biome': (
            Candidate('n', 'biome', 'entities/biome/n.json', 'N', '林'),
        ),
    })
    first = catalog.draw(food, seed=42)
    again = catalog.draw(food, seed=42)
    any_draw = catalog.draw(any_pool, seed=7)
    failed = 0
    checks = [
        (first is not None and again is not None and first.candidate.entity_id == again.candidate.entity_id, 'same seed'),
        (any_draw is not None and any_draw.pool.id in ('food', 'drink', 'monster', 'biome'), 'any rotate'),
        (any_draw is not None and any_draw.asked_pool.id == 'any', 'asked any'),
    ]
    for ok, label in checks:
        print(f'  [{"OK" if ok else "FAIL"}] {label}')
        if not ok:
            failed += 1
    return failed


def main() -> int:
    failed = 0
    print('is_drawable')
    failed += test_is_drawable()
    print('matches_pool')
    failed += test_matches_pool()
    print('draw seed')
    failed += test_draw_seed()
    print(f'\nfailed {failed}')
    return failed


if __name__ == '__main__':
    sys.exit(1 if main() else 0)
