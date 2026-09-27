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
只输出一个词：ask、chat 或 random。不要解释。

ask：玩家在查游戏事实——配方、熔炼、掉落、任务、boss、机制、在哪挖、怎么做、能不能、为什么没有、有哪些可以做。
即使带语气词、哭腔、玩梗用词，只要有要查的点，就是 ask。
「推荐一下某某怎么做 / 掉落率」也是 ask，不是 random。
「随便」「随机」如果是在问哪些东西可以随便做、随便合成、不限材料，仍是 ask。

random：想让机器人从某一类里抽一条，还没有指定具体词条。
例如推荐个吃的、来把枪、来个怪、今天去哪、随便来一个。
不要输出具体 category / tag 名，只要 random。
句子里出现「随便」「随机」本身不够，必须是在要一条未知词条。

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
- 抽签 → random
- 随机一把枪 → random
- 吃什么好 → random
- 已经藻豆荚自由了！现在有哪些东西是可以随便做的 → ask
- 来个烤肋排 → chat
- 疯狂星期四 v我50日耀矿 → chat
- 给我转50像素快点 → chat
- 嘿 S.A.I.L 帮我去餐厅点烤肋排 → chat
- 嘿帮我看看烤肋排再来个汉堡 → chat
- 怎么骗殖民地 npc 替我种棉花 → chat
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
