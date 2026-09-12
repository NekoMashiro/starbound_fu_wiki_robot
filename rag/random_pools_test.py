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
    ('来个家具', 'furniture', '来个家具'),
    ('推荐个家具', 'furniture', '家具'),
    ('来个方块', 'block', '来个方块'),
    ('来点液体', 'liquid', '来点液体'),
    ('来套防具', 'armor', '来套防具'),
    ('来套装备', 'armor', '来套装备'),
    ('推荐个装备', 'armor', '装备'),
    ('来个头盔', 'head_armor', '头盔'),
    ('来个胸甲', 'chest_armor', '胸甲'),
    ('来个护腿', 'leg_armor', '护腿'),
    ('来套衣服', 'clothing', '来套衣服'),
    ('来个帽子', 'headwear', '帽子'),
    ('来个披风', 'cape', '披风'),
    ('来个EPP', 'epp', '来个EPP'),
    ('来个增强件', 'augment', '增强件'),
    ('来个工具', 'tool', '来个工具'),
    ('来个工作台', 'workbench', '来个工作台'),
    ('来个冰箱', 'fridge', '来个冰箱'),
    ('来个平台', 'platform', '来个平台'),
    ('来个乐器', 'instrument', '来个乐器'),
    ('来个改造器', 'terraformer', '来个改造器'),
    ('来个虫子', 'bug', '来个虫子'),
    ('来把长剑', 'longsword', '长剑'),
    ('来把弩', 'crossbow', '来把弩'),
    ('来把镰刀', 'scythe', '镰刀'),
    ('随机一把枪', 'weapon', '一把枪'),
    ('抽签', 'any', '抽签'),
    ('来一个', 'any', '来一个'),
    ('吃什么好', 'food', '吃什么'),
    ('喝什么', 'drink', '喝什么'),
    ('推荐个灯', 'light', '推荐个灯'),
    ('推荐个科技', 'tech', '科技'),
    ('去飞船柜子里随机拿一件时装打扮一下自己吧', 'clothing', '时装'),
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
