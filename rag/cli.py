#!/usr/bin/env python3
"""
cli.py — FU Wiki Robot 命令行交互式问答

用法:
    cd rag
    python cli.py
"""

import sys
from query import RAGEngine, strip_color_codes


WELCOME = """
╔══════════════════════════════════════════════════╗
║   🎮 Starbound + FU + Arcana Wiki Robot          ║
║   输入问题即可查询，支持中英文                   ║
║   输入 quit / exit / q 退出                      ║
╚══════════════════════════════════════════════════╝
"""


def main():
    print(WELCOME)

    try:
        engine = RAGEngine()
    except Exception as e:
        print(f'❌ 初始化失败: {e}')
        print('   请确保已运行 python ingest.py --reset 导入知识库')
        sys.exit(1)

    print()

    while True:
        try:
            question = input('🎯 你的问题: ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\n👋 再见！')
            break

        if not question:
            continue
        if question.lower() in ('quit', 'exit', 'q', '退出'):
            print('👋 再见！')
            break

        print('🔍 检索中...')
        result = engine.ask(question)

        # 显示查询增强
        enhanced = result.get('enhanced_query', '')
        if enhanced and enhanced != question:
            print(f'🔄 查询增强: {enhanced}')

        # 显示回答
        print(f'\n💬 回答:\n')
        print(result['answer'])

        # 显示参考来源
        if result['sources']:
            print(f'\n📚 参考来源 ({len(result["sources"])} 篇):')
            for s in result['sources']:
                name_en = strip_color_codes(s.get('name_en', ''))
                name_zh = strip_color_codes(s.get('name_zh', ''))
                etype = s.get('entity_type', '')
                mod = s.get('source_mod', '')
                score = s.get('score', 0)

                label = f'{name_en}'
                if name_zh:
                    label += f' ({name_zh})'
                if etype:
                    label = f'[{etype}] {label}'
                if mod:
                    label += f' [{mod}]'

                print(f'   • {label}  (score: {score})')

        print(f'\n⚙️  模型: {result["model"]}')
        print('─' * 50)


if __name__ == '__main__':
    main()
