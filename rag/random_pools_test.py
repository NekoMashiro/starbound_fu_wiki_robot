"""随机池别名对表：不进网。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from random_pools import resolve_pool

CASES = [
    ('推荐个吃的', 'food', '吃的'),
    ('来把突击步枪', 'assault_rifle', '突击步枪'),
    ('来把步枪', 'assault_rifle', '步枪'),
    ('来把枪', 'weapon', '来把枪'),
    ('来一个吃的', 'food', '吃的'),
    ('随便来一个', 'any', '随便来一个'),
    ('今日推荐', 'any', '今日推荐'),
    ('今天去哪', 'biome', '今天去哪'),
    ('来个蜜蜂', 'bee', '蜜蜂'),
    ('来把武士刀', 'katana', '武士刀'),
    ('来把狙击枪', 'sniper', '狙击枪'),
    ('来把短剑', 'shortsword', '短剑'),
    ('来张床', 'bed', '来张床'),
    ('钨矿怎么熔炼', None, None),
    ('怎么做烤肋排', None, None),
    ('', None, None),
]


def main() -> int:
    failed = 0
    for text, expect_id, expect_alias in CASES:
        match = resolve_pool(text)
        got_id = match.pool_id if match else None
        got_alias = match.alias if match else None
        ok = got_id == expect_id and got_alias == expect_alias
        print(
            f'  [{"OK" if ok else "FAIL"}] {text!r} -> '
            f'{got_id}/{got_alias} (expect {expect_id}/{expect_alias})'
        )
        if not ok:
            failed += 1
    print(f'\nfailed {failed} / {len(CASES)}')
    return failed


if __name__ == '__main__':
    sys.exit(1 if main() else 0)
