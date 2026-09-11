"""提问 vs 闲聊。失败或不确定时默认 ask，避免真问题被当成玩梗。"""

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

INTENTS = ('ask', 'chat')
DEFAULT_INTENT = 'ask'

_THINK_RE = re.compile(r'<think>.*?</think>', re.DOTALL)
_TOKEN_RE = re.compile(r'\b(ask|chat)\b', re.IGNORECASE)

CLASSIFY_SYSTEM = """你在给 Starbound / Frackin' Universe QQ 机器人做意图分类。
只输出一个词：ask 或 chat。不要解释。

ask：玩家在查游戏事实——配方、熔炼、掉落、任务、boss、机制、在哪挖、怎么做、能不能、为什么没有。
即使带语气词、哭腔、玩梗用词，只要有要查的点，就是 ask。

chat：闲聊、打招呼、复读玩梗、角色扮演（假装 S.A.I.L 点菜、殖民地段子）、吐槽群友、没有明确要查的资料点。
角色扮演里点了具体物品名称也算 chat（后面仍会检索，这里只判口吻）。

不确定就输出 ask。

对照：
- 钨矿怎么熔炼啊呜呜呜 → ask
- 武士刀的掉落率是多少？ → ask
- 取得鲛人神器任务，boss是谁？ → ask
- 可以限定我的殖民地只有哪些种族吗？ → ask
- 疯狂星期四 v我50日耀矿 → chat
- 给我转50像素快点 → chat
- 嘿 S.A.I.L 帮我去餐厅点烤肋排 → chat
- 怎么骗殖民地 npc 替我种棉花 → chat
"""


def classify_intent(text: str) -> str:
    """返回 ask 或 chat。任何失败都回落到 ask。"""
    text = (text or '').strip()
    if not text:
        return DEFAULT_INTENT
    try:
        raw = _complete(text)
    except Exception:
        return DEFAULT_INTENT
    return parse_intent(raw)


def parse_intent(raw: str) -> str:
    """从模型输出里抽出 ask/chat；解析不到则 ask。"""
    cleaned = _THINK_RE.sub('', raw or '').strip()
    if not cleaned:
        return DEFAULT_INTENT
    match = _TOKEN_RE.search(cleaned)
    if match:
        return match.group(1).lower()
    lowered = cleaned.lower()
    if lowered.startswith('chat'):
        return 'chat'
    if lowered.startswith('ask'):
        return 'ask'
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
