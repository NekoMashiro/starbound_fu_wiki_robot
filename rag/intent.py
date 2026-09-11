"""提问 / 闲聊 / 随机。失败或不确定时默认 ask，避免真问题被当成玩梗或抽签。"""

import re

import httpx

from config import (
    LLM_MODEL,
    LLM_PROVIDER,
    OPENROUTER_API_BASE,
    OPENROUTER_API_KEY,
    ZHIPU_API_BASE,
    ZHIPU_API_KEY,
    openrouter_provider_prefs,
)
INTENTS = ('ask', 'chat', 'random')
DEFAULT_INTENT = 'ask'

_THINK_RE = re.compile(r'<think>.*?</think>', re.DOTALL)
_TOKEN_RE = re.compile(r'\b(ask|chat|random)\b', re.IGNORECASE)

# 像在查资料：即使带「来个」也交给模型或回落到 ask。
_ASK_HINT_RE = re.compile(
    r'怎么|如何|配方|熔炼|掉落|在哪|哪里|为什么|能不能|是谁|是什么|多少|任务|boss',
    re.IGNORECASE,
)
# 像在抽签。故意不写单字「抽」，避免「抽出物」这类问句。
_RANDOM_HINT_RE = re.compile(
    r'推荐个|推荐一|推荐点|随便来|随便抽|随便一个|来个|来只|来把|来张|来杯'
    r'|今日推荐|今天去哪|去哪玩|随机一个|随机来|抽一个|抽个',
)


CLASSIFY_SYSTEM = """你在给 Starbound / Frackin' Universe QQ 机器人做意图分类。
只输出一个词：ask、chat 或 random。不要解释。

ask：玩家在查游戏事实——配方、熔炼、掉落、任务、boss、机制、在哪挖、怎么做、能不能、为什么没有。
即使带语气词、哭腔、玩梗用词，只要有要查的点，就是 ask。
「推荐一下某某怎么做 / 掉落率」也是 ask，不是 random。

random：想让机器人从某一类里抽一条，还没有指定具体词条。
例如推荐个吃的、来把枪、来个怪、今天去哪、随便来一个。
不要输出具体 category / tag 名，只要 random。

chat：闲聊、打招呼、复读玩梗、角色扮演（假装 S.A.I.L 点具体菜、殖民地段子）、吐槽群友。
点了明确的已有物品名称、不是「抽一个未知的」——算 chat，不算 random。

不确定就输出 ask。

对照：
- 钨矿怎么熔炼啊呜呜呜 → ask
- 武士刀的掉落率是多少？ → ask
- 取得鲛人神器任务，boss是谁？ → ask
- 可以限定我的殖民地只有哪些种族吗？ → ask
- 推荐个吃的 → random
- 来把步枪 → random
- 来个蜜蜂 → random
- 今天去哪 → random
- 随便来一个 → random
- 疯狂星期四 v我50日耀矿 → chat
- 给我转50像素快点 → chat
- 嘿 S.A.I.L 帮我去餐厅点烤肋排 → chat
- 怎么骗殖民地 npc 替我种棉花 → chat
"""


def looks_like_random(text: str) -> bool:
    """口令像抽签、又不像在查资料。不对池子，避免「武士刀」问句误入 random。"""
    text = (text or '').strip()
    if not text or _ASK_HINT_RE.search(text):
        return False
    return bool(_RANDOM_HINT_RE.search(text))


def classify_intent(text: str) -> str:
    """返回 ask / chat / random。任何失败都回落到 ask。"""
    text = (text or '').strip()
    if not text:
        return DEFAULT_INTENT
    if looks_like_random(text):
        return 'random'
    try:
        raw = _complete(text)
    except Exception:
        return DEFAULT_INTENT
    return parse_intent(raw)


def parse_intent(raw: str) -> str:
    """从模型输出里抽出 ask/chat/random；解析不到则 ask。"""
    cleaned = _THINK_RE.sub('', raw or '').strip()
    if not cleaned:
        return DEFAULT_INTENT
    match = _TOKEN_RE.search(cleaned)
    if match:
        return match.group(1).lower()
    lowered = cleaned.lower()
    for intent in ('random', 'chat', 'ask'):
        if lowered.startswith(intent):
            return intent
    return DEFAULT_INTENT


def _complete(text: str) -> str:
    if LLM_PROVIDER == 'zhipu':
        api_base = ZHIPU_API_BASE
        api_key = ZHIPU_API_KEY
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }
    else:
        api_base = OPENROUTER_API_BASE
        api_key = OPENROUTER_API_KEY
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://github.com/fu-wiki-robot',
            'X-Title': 'FU Wiki Robot',
        }

    body = {
        'model': LLM_MODEL,
        'messages': [
            {'role': 'system', 'content': CLASSIFY_SYSTEM},
            {'role': 'user', 'content': text},
        ],
        'temperature': 0,
        'max_tokens': 16,
    }
    if LLM_PROVIDER == 'openrouter':
        body['reasoning'] = {'effort': 'none'}
        body['provider'] = openrouter_provider_prefs()

    response = httpx.post(
        f'{api_base}/chat/completions',
        headers=headers,
        json=body,
        timeout=10.0,
    )
    response.raise_for_status()
    choice = response.json()['choices'][0]
    return choice.get('message', {}).get('content') or ''
