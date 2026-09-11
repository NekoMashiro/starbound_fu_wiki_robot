#!/usr/bin/env python3
"""
cli.py — 本地命令行问答（不启动 QQ）

用法:
    cd rag
    python cli.py
    python cli.py 钨矿怎么熔炼
    python cli.py -- 嘿，S.A.I.L助手，帮我点一份烤肋排
"""

import sys
from query import RAGEngine, strip_color_codes


WELCOME = """
╔══════════════════════════════════════════════════╗
║   宇艇摘析  ·  本地问答                          ║
║   直接回车后输入，或: python cli.py 你的问题     ║
║   quit / exit / q 退出                           ║
╚══════════════════════════════════════════════════╝
"""


def _print_result(question: str, result: dict):
    intent = result.get('intent') or 'ask'
    enhanced = result.get('enhanced_query', '')
    print(f'\n🎯 intent={intent}')
    pool = result.get('pool')
    if pool:
        print(f'🎲 pool={pool}')
    pick = result.get('pick')
    if pick:
        print(f'🎯 pick={pick}')
    if enhanced and enhanced != question:
        print(f'🔄 查询增强: {enhanced}')

    print(f'\n💬 摘希:\n')
    print(result['answer'])

    sources = result.get('sources') or []
    if sources and intent not in ('chat', 'random'):
        print(f'\n📚 参考来源 ({len(sources)} 篇):')
        for s in sources[:5]:
            name_en = strip_color_codes(s.get('name_en', ''))
            name_zh = strip_color_codes(s.get('name_zh', ''))
            etype = s.get('entity_type', '')
            label = name_zh or name_en or '?'
            if name_zh and name_en:
                label = f'{name_zh} ({name_en})'
            if etype:
                label = f'[{etype}] {label}'
            print(f'   • {label}  (score: {s.get("score", 0)})')
    elif sources and intent == 'chat':
        print('\n📚 (闲聊未下发来源，检索到: '
              + ', '.join(
                  (s.get('name_zh') or s.get('name_en') or '?')
                  for s in sources[:5]
              )
              + ')')

    timings = result.get('timings') or {}
    print(f'\n⚙️  {result.get("model")}  total={timings.get("total")}s')
    print('─' * 50)


def main():
    oneshot = [a for a in sys.argv[1:] if a != '--']
    if not oneshot:
        print(WELCOME)

    try:
        engine = RAGEngine()
    except Exception as e:
        print(f'初始化失败: {e}')
        print('请确保 rag/chroma_db 已存在')
        sys.exit(1)

    def run(question: str):
        print('🔍 检索中...')
        result = engine.ask(question)
        _print_result(question, result)

    if oneshot:
        run(' '.join(oneshot))
        return

    print()
    while True:
        try:
            question = input('船长: ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\n摘希先挂起通讯啦 (´・ω・`)')
            break

        if not question:
            continue
        if question.lower() in ('quit', 'exit', 'q', '退出'):
            print('摘希先挂起通讯啦 (´・ω・`)')
            break
        run(question)


if __name__ == '__main__':
    main()
