"""提问 / 闲聊 / 随机。是否抽签只由模型判断，失败或不确定时默认 ask。"""

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


CLASSIFY_SYSTEM = """你在给 Starbound / Frackin' Universe QQ 机器人做意图分类。
只输出一个词：ask、chat 或 random。不要解释，不要输出 category / tag 名。

看这句话在让机器人做什么。吃的、好喝、枪、随机这些词不决定类别。按顺序判断，命中就停。

1. ask：有一个被提问的对象，要查它的事实。对象是材料、物品、任务或机制。事实包括配方、用途、能做成什么、熔炼、掉落、在哪、能不能、有哪些。
   只有向这个对象提问才算。顺口提到的背景（已经造好了、在庆祝、在飞船上）不是提问对象。
   宾语写成「好吃的」「吃的」也不改类别：仍是在问这个对象能变成什么。
   「随便」「随机」若修饰制作条件（可以随便做、不限材料），是 ask。
   语气词、哭腔不改 ask。玩梗里若夹着真实资料点（熔炼、掉落、配方），仍是 ask。

2. random：没有被提问的对象，而是要交出某一类里还没点名的一条。
   类名还没落到某一条具体词条：喝的、枪、衣服、去处、蜜蜂、怪物。
   「随机」修饰的是就要的那一条本身。
   庆祝、角色扮演、叫摘希去拿，只是外壳。外壳两边都可以有，不靠它区分 random 和 chat。

3. chat：闲聊、打招呼、玩梗、吐槽，或点名了具体物品让摘希去拿。点了名就不是在抽未知的一条。
   怎么骗、怎么整人这种段子不是在查资料。

不确定就输出 ask。

对照每对句式相同，只差有没有点名，或只差是在提问还是在要一条：
- 钨矿可以用来做什么 → ask
- 吃什么好 → random
- 已经藻豆荚自由了！现在有哪些东西是可以随便做的 → ask
- 庆祝一下，来杯喝的 → random
- 庆祝一下，来杯礁荚可乐 → chat
- 去柜子里拿一件衣服 → random
- 去柜子里拿那件船长的披风 → chat
- 今天去哪 → random
- 来个烤肋排 → chat
- 疯狂星期四 v我50日耀矿 → chat
"""


def decide_intent(text: str) -> str | None:
    """空话直接 ask。其余一律交给模型，不用关键词抢判 random。"""
    if not (text or '').strip():
        return DEFAULT_INTENT
    return None


def classify_intent(text: str) -> str:
    """返回 ask / chat / random。任何失败都回落到 ask。"""
    text = (text or '').strip()
    decided = decide_intent(text)
    if decided:
        return decided
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
