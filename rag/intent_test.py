"""意图分类烟雾测试：解析不进网，对照句走一次 LLM。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from intent import classify_intent, looks_like_random, parse_intent

PARSE_CASES = [
    ('ask', 'ask'),
    ('chat', 'chat'),
    ('random', 'random'),
    ('ASK', 'ask'),
    ('  chat\n', 'chat'),
    ('<think>hmm</think>ask', 'ask'),
    ('<think>x</think>random', 'random'),
    ('I think this is chat', 'chat'),
    ('I think this is random', 'random'),
    ('', 'ask'),
    ('hello', 'ask'),
]

HINT_CASES = [
    ('推荐个吃的', True),
    ('来把步枪', True),
    ('来个蜜蜂', True),
    ('今天去哪', True),
    ('随便来一个', True),
    ('武士刀的掉落率是多少？', False),
    ('钨矿怎么熔炼啊呜呜呜', False),
    ('嘿 S.A.I.L 帮我去餐厅点烤肋排', False),
    ('疯狂星期四 v我50日耀矿', False),
    ('怎么做烤肋排', False),
]

CASES = [
    ('钨矿怎么熔炼啊呜呜呜，我的熔炉里没有钨锭的配方！', 'ask'),
    ('武士刀的掉落率是多少？', 'ask'),
    ('取得鲛人神器任务，boss是谁？', 'ask'),
    ('我不希望我的殖民地里有各种各样的外星人，可以限定我的殖民地只有哪些种族吗？', 'ask'),
    ('推荐个吃的', 'random'),
    ('来把步枪', 'random'),
    ('来个蜜蜂', 'random'),
    ('今天去哪', 'random'),
    ('随便来一个', 'random'),
    ('疯狂星期四 v我50日耀矿', 'chat'),
    (
        '嘿，S.A.I.L助手，帮我导航到前哨站的2站传送商店前的餐厅，'
        '我要一些烤肋排和橙光挞，一些多汁的汉堡包，加上全群配额的网格炸土豆和炸鱼条，'
        '再浇上足量的土豆泥，另外再来一大杯冷藏的礁荚可乐，从下矿的群友身上扣除50%像素',
        'chat',
    ),
    ('我想让我的殖民地npc当黑奴帮我种棉花，怎么骗他们替我干活？', 'chat'),
]


def test_parse_intent() -> int:
    failed = 0
    for raw, expect in PARSE_CASES:
        got = parse_intent(raw)
        ok = got == expect
        print(f'  [{"OK" if ok else "FAIL"}] parse {raw!r} -> {got} (expect {expect})')
        if not ok:
            failed += 1
    return failed


def test_looks_like_random() -> int:
    failed = 0
    for text, expect in HINT_CASES:
        got = looks_like_random(text)
        ok = got is expect
        print(f'  [{"OK" if ok else "FAIL"}] looks_like_random {text!r} -> {got} (expect {expect})')
        if not ok:
            failed += 1
    return failed


def test_classify() -> int:
    failed = 0
    for text, expect in CASES:
        got = classify_intent(text)
        ok = got == expect
        preview = text if len(text) <= 36 else text[:36] + '…'
        print(f'  [{"OK" if ok else "FAIL"}] {got:4}  expect={expect:4}  {preview}')
        if not ok:
            failed += 1
    return failed


def main():
    print('parse_intent')
    parse_fail = test_parse_intent()
    print('\nlooks_like_random')
    hint_fail = test_looks_like_random()
    print('\nclassify_intent (hint or live LLM)')
    live_fail = test_classify()
    total = parse_fail + hint_fail + live_fail
    print(f'\nfailed {total} / {len(PARSE_CASES) + len(HINT_CASES) + len(CASES)}')
    sys.exit(1 if total else 0)


if __name__ == '__main__':
    main()
