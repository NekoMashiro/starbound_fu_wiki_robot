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
    'longsword',
    'dagger',
    'katana',
    'Rapier',
    'spear',
    'shortspear',
    'axe',
    'greataxe',
    'hammer',
    'mace',
    'staff',
    'wand',
    'whip',
    'Quarterstaff',
    'quarterstaff',
    'fistWeapon',
    'crossbow',
    'scythe',
    'boomerang',
    'chakram',
    'grenadeLauncher',
    'armcannon',
    'Magnorb',
    'flamethrower',
    'liquidGun',
    'lance',
    'bioweapon',
    'uniqueWeapon',
)

# 防具只要 armour，不要 wear（那是时装）。
ARMOR_CATEGORIES = (
    'headarmour',
    'chestarmour',
    'legarmour',
)

CLOTHING_CATEGORIES = (
    'headwear',
    'chestwear',
    'legwear',
    'backwear',
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
        categories=('spear', 'shortspear'),
    ),
    Pool(
        'axe',
        '斧',
        ('战斧', '巨斧', '斧头', 'axe'),
        entity_type='item',
        categories=('axe', 'greataxe'),
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
        'longsword',
        '长剑',
        ('长剑', 'longsword'),
        entity_type='item',
        categories=('longsword',),
    ),
    Pool(
        'rapier',
        '刺剑',
        ('刺剑', '细剑', 'rapier'),
        entity_type='item',
        categories=('Rapier',),
    ),
    Pool(
        'fist',
        '拳套',
        ('拳套', '拳刃', '拳击手套'),
        entity_type='item',
        categories=('fistWeapon',),
    ),
    Pool(
        'crossbow',
        '弩',
        ('十字弩', '来把弩', 'crossbow'),
        entity_type='item',
        categories=('crossbow',),
    ),
    Pool(
        'scythe',
        '镰刀',
        ('镰刀', 'scythe'),
        entity_type='item',
        categories=('scythe',),
    ),
    Pool(
        'boomerang',
        '回旋镖',
        ('回旋镖', '飞镖', 'boomerang'),
        entity_type='item',
        categories=('boomerang',),
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
        'head_armor',
        '头盔',
        ('头盔', '头甲', 'headarmour'),
        entity_type='item',
        categories=('headarmour',),
    ),
    Pool(
        'chest_armor',
        '胸甲',
        ('胸甲', '胸铠', 'chestarmour'),
        entity_type='item',
        categories=('chestarmour',),
    ),
    Pool(
        'leg_armor',
        '护腿',
        ('护腿', '腿甲', 'legarmour'),
        entity_type='item',
        categories=('legarmour',),
    ),
    Pool(
        'armor',
        '防具',
        ('来套防具', '来套装备', '防具', '盔甲', '装备', 'armor'),
        entity_type='item',
        categories=ARMOR_CATEGORIES,
    ),
    Pool(
        'headwear',
        '帽子',
        ('帽子', '头饰', 'headwear'),
        entity_type='item',
        categories=('headwear',),
    ),
    Pool(
        'cape',
        '披风',
        ('披风', '斗篷', '背饰'),
        entity_type='item',
        categories=('backwear',),
    ),
    Pool(
        'clothing',
        '服装',
        ('来套衣服', '时装', '服装', '衣服', 'cosmetic'),
        entity_type='item',
        categories=CLOTHING_CATEGORIES,
    ),
    Pool(
        'epp',
        '环境包',
        ('环境背包', '环境包', '来个EPP', 'EPP', 'epp'),
        entity_type='item',
        categories=('enviroProtectionPack',),
    ),
    Pool(
        'augment',
        '增强件',
        ('增强件', '增强模块', 'eppAugment', 'augment'),
        entity_type='item',
        categories=('eppAugment',),
    ),
    Pool(
        'tool',
        '工具',
        ('来个工具', '采矿激光', '工具', 'tool'),
        entity_type='item',
        categories=('tool', 'Tool'),
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
    Pool(
        'fridge',
        '冰箱',
        ('来个冰箱', '冰箱', 'fridge'),
        entity_type='object',
        categories=('fridgeStorage',),
    ),
    Pool(
        'workbench',
        '工作台',
        ('来个工作台', '制作台', '工作台'),
        entity_type='object',
        categories=('crafting',),
    ),
    Pool(
        'platform',
        '平台',
        ('来个平台', '平台', 'platform'),
        entity_type='item',
        categories=('platform',),
    ),
    Pool(
        'instrument',
        '乐器',
        ('来个乐器', '乐器', 'musicalInstrument'),
        entity_type='item',
        categories=('musicalInstrument',),
    ),
    Pool(
        'terraformer',
        '改造器',
        ('地形改造', '来个改造器', '改造器', 'terraformer'),
        entity_type='object',
        categories=('terraformer',),
    ),
    Pool(
        'bug',
        '虫子',
        ('来个虫子', '昆虫', '虫子'),
        entity_type='object',
        categories=('bug',),
    ),
    Pool(
        'furniture',
        '家具',
        ('家具', '来件家具', '来个家具', '摆件', 'furniture'),
        entity_type='object',
        categories=('furniture', 'decorative'),
    ),
    Pool(
        'block',
        '方块',
        ('方块', '来个方块', '砖块', '地砖', 'block'),
        entity_type='item',
        categories=('block',),
    ),
    Pool(
        'liquid',
        '液体',
        ('液体', '来桶液体', '来点液体', 'liquid'),
        entity_type='liquid',
    ),
    # any 必须放最后一档匹配，避免「来一个吃的」被「来一个」抢走。
    Pool(
        'any',
        '全局随机',
        ('今日推荐', '随便来一个', '随机一个', '随便', '随机'),
        rotate=('food', 'drink', 'monster', 'biome'),
    ),
)

POOL_BY_ID = {p.id: p for p in POOLS}

# ---------------------------------------------------------------------------
# 不对表（人话不稳、tag 脏，或玩家根本不会喊这类词）
#
# 近战/远程：ranged / melee —— 别名和具体枪型抢，用 weapon 兜。
# 脏武器 tag：upgradeableWeapon / balanced / energy / hyper / bioweapon /
#   defensive / offensive / explorer（会混进裤子、面罩）。bioweapon 只收
#   category，不收 tag。
# 材料 / 矿石 / 基因：craftingMaterial、craftingOre、craftingGene，以及
#   zerchesium / lunari / … 材料 tag。玩家更常问「怎么挖」，是 ask。
# 种族 / 殖民地房间 id / 形容词 tag / mod 内部 category（swtjc_ewg_*、
#   species、christmas、urban、industrial、hive、teaIngredient、
#   protectorate）：不会有人喊这些抽签。
# 机甲零件 mechPart：抽到的是手臂/腿/机体，不是「来个机甲」。
# 船员合同 / 载具控制器 / 染料 / 投掷物：合同卡、控制器、手雷混荧光棒。
# 传送器 / 电路 / 陷阱：出口门、炮塔、尖刺一堆，池子看起来像坏了。
# cooking tag：冰箱已经单独开；剩下是装饰杯碟。
# EPP 的 category 叫 enviroProtectionPack，实际混了箭袋、翅膀、功能背包；
#   别名只收「EPP / 环境包」，不收「背包」（会和箱子抢）。
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
