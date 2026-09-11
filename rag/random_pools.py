"""人话 → 随机池。

只做别名对表，不判 ask / chat / random。
匹配规则：具体池优先于 any；同一档里更长的别名先中，中了就停。
滤池字段留给以后抽签用，现在还不读知识库。
"""

from __future__ import annotations

from dataclasses import dataclass


# 武器 category。大类 weapon 用这些，不用脏 tag（tag=weapon 会混进裤子、面罩）。
WEAPON_CATEGORIES = (
    'assaultRifle',
    'pistol',
    'sniperRifle',
    'shotgun',
    'machinePistol',
    'rocketLauncher',
    'bow',
    'broadsword',
    'shortsword',
    'dagger',
    'katana',
    'spear',
    'axe',
    'hammer',
    'mace',
    'staff',
    'wand',
    'whip',
    'uniqueWeapon',
)


@dataclass(frozen=True)
class Pool:
    id: str
    label_zh: str
    aliases: tuple[str, ...]
    entity_type: str | None = None
    categories: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    rotate: tuple[str, ...] = ()


# 具体池。别名写成玩家可能打的词，不要用单字（枪 / 剑 / 刀 太容易误伤）。
# 「枪」单独留给 weapon 大类。
POOLS: tuple[Pool, ...] = (
    Pool(
        'food',
        '食物',
        ('做好的食物', 'preparedFood', '料理', '吃的', '食物'),
        entity_type='item',
        categories=('preparedFood', 'food'),
    ),
    Pool(
        'drink',
        '饮料',
        ('饮料', '喝的', '来杯酒', 'drink'),
        entity_type='item',
        categories=('drink',),
    ),
    Pool(
        'medicine',
        '药品',
        ('药品', '药物', '治疗包', '医药', 'medicine'),
        entity_type='item',
        categories=('medicine',),
    ),
    Pool(
        'monster',
        '怪物',
        ('怪物', '魔物', '来个怪', 'monster'),
        entity_type='monster',
    ),
    Pool(
        'biome',
        '生态',
        ('生态', '星球', '今天去哪', '去哪玩', 'biome'),
        entity_type='biome',
    ),
    Pool(
        'tech',
        '科技',
        ('主动技', '来个科技', '随机科技', 'tech'),
        entity_type='tech',
    ),
    Pool(
        'assault_rifle',
        '突击步枪',
        ('突击步枪', 'assaultRifle', '步枪'),
        entity_type='item',
        categories=('assaultRifle',),
    ),
    Pool(
        'sniper',
        '狙击步枪',
        ('狙击步枪', '狙击枪', 'sniperRifle', '狙击'),
        entity_type='item',
        categories=('sniperRifle',),
    ),
    Pool(
        'shotgun',
        '霰弹枪',
        ('霰弹枪', '散弹枪', 'shotgun'),
        entity_type='item',
        categories=('shotgun',),
    ),
    Pool(
        'machine_pistol',
        '冲锋枪',
        ('冲锋枪', 'machinePistol', 'smg'),
        entity_type='item',
        categories=('machinePistol',),
    ),
    Pool(
        'pistol',
        '手枪',
        ('手枪', '手炮', 'pistol'),
        entity_type='item',
        categories=('pistol',),
    ),
    Pool(
        'rocket',
        '火箭筒',
        ('火箭发射器', '火箭筒', 'rocketLauncher'),
        entity_type='item',
        categories=('rocketLauncher',),
    ),
    Pool(
        'bow',
        '弓',
        ('弓箭', '来把弓', 'bow'),
        entity_type='item',
        categories=('bow',),
    ),
    Pool(
        'broadsword',
        '宽剑',
        ('宽剑', '大剑', 'broadsword'),
        entity_type='item',
        categories=('broadsword',),
    ),
    Pool(
        'shortsword',
        '短剑',
        ('短剑', 'shortsword'),
        entity_type='item',
        categories=('shortsword',),
    ),
    Pool(
        'katana',
        '武士刀',
        ('武士刀', '太刀', 'katana'),
        entity_type='item',
        categories=('katana',),
    ),
    Pool(
        'dagger',
        '匕首',
        ('匕首', '短刀', 'dagger'),
        entity_type='item',
        categories=('dagger',),
    ),
    Pool(
        'spear',
        '矛',
        ('长矛', '战矛', 'spear'),
        entity_type='item',
        categories=('spear',),
    ),
    Pool(
        'axe',
        '斧',
        ('战斧', '巨斧', '斧头', 'axe'),
        entity_type='item',
        categories=('axe',),
    ),
    Pool(
        'hammer',
        '锤',
        ('战锤', '锤子', 'hammer'),
        entity_type='item',
        categories=('hammer',),
    ),
    Pool(
        'mace',
        '钉头锤',
        ('钉头锤', '狼牙棒', 'mace'),
        entity_type='item',
        categories=('mace',),
    ),
    Pool(
        'staff',
        '法杖',
        ('法杖', 'staff'),
        entity_type='item',
        categories=('staff',),
    ),
    Pool(
        'wand',
        '魔杖',
        ('魔杖', 'wand'),
        entity_type='item',
        categories=('wand',),
    ),
    Pool(
        'whip',
        '鞭',
        ('长鞭', '鞭子', 'whip'),
        entity_type='item',
        categories=('whip',),
    ),
    Pool(
        'shield',
        '盾',
        ('盾牌', '来个盾', 'shield'),
        entity_type='item',
        categories=('shield',),
    ),
    Pool(
        'weapon',
        '武器',
        ('武器', '来把枪', '来把刀', 'weapon'),
        entity_type='item',
        categories=WEAPON_CATEGORIES,
    ),
    Pool(
        'bee',
        '蜜蜂',
        ('蜜蜂', '蜂后', '工蜂'),
        entity_type='item',
        tags=('bee', 'bees'),
    ),
    Pool(
        'fossil',
        '化石',
        ('化石', 'fossil'),
        entity_type='item',
        tags=('fossil',),
    ),
    Pool(
        'seed',
        '种子',
        ('种子', '作物', 'seed'),
        entity_type='object',
        categories=('seed',),
    ),
    Pool(
        'light',
        '灯',
        ('灯具', '来个灯', '照明'),
        entity_type='object',
        categories=('light',),
    ),
    Pool(
        'door',
        '门',
        ('来个门', '房门'),
        entity_type='object',
        categories=('door',),
    ),
    Pool(
        'bed',
        '床',
        ('来张床', '来个床'),
        entity_type='object',
        tags=('bed',),
    ),
    Pool(
        'storage',
        '箱子',
        ('储物', '箱子', '柜子'),
        entity_type='object',
        categories=('storage',),
    ),
    # any 必须放最后一档匹配，避免「来一个吃的」被「来一个」抢走。
    Pool(
        'any',
        '随便',
        ('今日推荐', '随便来一个', '随机一个', '随便', '随机'),
        rotate=('food', 'drink', 'monster', 'biome'),
    ),
)

POOL_BY_ID = {p.id: p for p in POOLS}

# ---------------------------------------------------------------------------
# 以后再说（有池，但人话不稳定或 tag 脏，先不要对表）
#
# 近战/远程大类：ranged / melee —— 用 weapon 兜，别名太容易和具体枪型抢。
# 脏武器 tag：upgradeableWeapon / balanced / energy / hyper / bioweapon /
#   defensive / offensive / explorer（例子里会混进裤子、面罩）。
# 材料：zerchesium / telebrium / lunari / xithricite / penumbrite /
#   irradium / isogen / ice / slime / shadow / bone / cosmic / atropus /
#   aether / elder / ancient / precursor。玩家更常问「怎么挖」，是 ask。
# 种族家具：floran / hylotl / apex / avian / human / glitch / novakid /
#   avali / nightar / peglaci / elduukhar / mantizi / skath / orion /
#   titancorp / exousia / horizon / luye / gilten / aurea。
# 殖民地套装：glitchcastle / floranvillage / humanprison / avalicamp /
#   hylotloceancity / novakidvillage / … 几乎没人会喊内部房间 id。
# 形容词/内部：pretty / misc / fu / valuable / hideous / cute / odd / evil /
#   combat / commerce / science / knowledge / wired / electronic。
# 家具细类：furniture / decorative / cooking / fridgeStorage / trophy。
# 其它：uniqueWeapon / species / liquid / christmas / musical / urban /
#   industrial / hive / bug / teaIngredient / protectorate。
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PoolMatch:
    pool: Pool
    alias: str

    @property
    def pool_id(self) -> str:
        return self.pool.id


def _alias_key(alias: str) -> tuple[int, str]:
    return (-len(alias), alias.lower())


def _build_alias_index(pools: tuple[Pool, ...]) -> tuple[tuple[str, Pool], ...]:
    pairs = [(alias, pool) for pool in pools for alias in pool.aliases]
    return tuple(sorted(pairs, key=lambda item: _alias_key(item[0])))


_CONCRETE_INDEX = _build_alias_index(tuple(p for p in POOLS if p.id != 'any'))
_ANY_INDEX = _build_alias_index(tuple(p for p in POOLS if p.id == 'any'))


def _match_index(text: str, index: tuple[tuple[str, Pool], ...]) -> PoolMatch | None:
    lowered = text.lower()
    for alias, pool in index:
        needle = alias.lower() if alias.isascii() else alias
        haystack = lowered if alias.isascii() else text
        if needle and needle in haystack:
            return PoolMatch(pool, alias)
    return None


def resolve_pool(text: str) -> PoolMatch | None:
    """从用户这句话里对出一个池。对不上返回 None（不是 any）。"""
    text = (text or '').strip()
    if not text:
        return None
    return _match_index(text, _CONCRETE_INDEX) or _match_index(text, _ANY_INDEX)


def format_match(match: PoolMatch | None) -> str:
    if match is None:
        return 'None'
    pool = match.pool
    filt = []
    if pool.entity_type:
        filt.append(f'type={pool.entity_type}')
    if pool.categories:
        filt.append('category=' + ','.join(pool.categories[:4])
                    + ('…' if len(pool.categories) > 4 else ''))
    if pool.tags:
        filt.append('tag=' + ','.join(pool.tags))
    if pool.rotate:
        filt.append('rotate=' + ','.join(pool.rotate))
    extra = ' '.join(filt)
    return f'{pool.id}  via {match.alias!r}  ({pool.label_zh})  {extra}'.rstrip()


if __name__ == '__main__':
    import sys

    samples = sys.argv[1:] or [
        '推荐个吃的',
        '来把突击步枪',
        '来把步枪',
        '来把枪',
        '来一个吃的',
        '随便来一个',
        '今天去哪',
        '来个蜜蜂',
        '来把武士刀',
        '钨矿怎么熔炼',
    ]
    for text in samples:
        print(f'{text}  →  {format_match(resolve_pool(text))}')
