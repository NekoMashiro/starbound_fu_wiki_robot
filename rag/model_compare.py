"""
model_compare.py — 多模型对比测试工具

对同一组问题，使用相同的 RAG 检索结果，分别调用多个 LLM 生成回答并对比。
用法: python model_compare.py
"""

import sys
import time
import json
import httpx
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    ZHIPU_API_KEY, ZHIPU_API_BASE,
    OPENROUTER_API_KEY, OPENROUTER_API_BASE,
    TOP_K,
)
from query import RAGEngine, SYSTEM_PROMPT, strip_color_codes

# ── 要测试的模型 ──
MODELS = [
    {
        'name': 'GPT-5.6 Luna Pro',
        'id': 'openai/gpt-5.6-luna-pro',
        'provider': 'openrouter',
    },
    {
        'name': 'DeepSeek V4 Flash',
        'id': 'deepseek/deepseek-v4-flash-0731',
        'provider': 'openrouter',
    },
    {
        'name': 'Qwen3.7 Plus',
        'id': 'qwen/qwen3.7-plus',
        'provider': 'openrouter',
    },
    {
        'name': 'Gemini 3.8 Flash',
        'id': 'google/gemini-3.8-flash',
        'provider': 'openrouter',
    },
]

# ── 测试问题 ──
QUESTIONS = [
    "我有必要最优先升级我的发明家工作台吗？",
    "农业科技里哪些比较重要？",
    "老登群友推荐我开局疯狂种棉花，他家里50棵以上，真的有必要种棉花吗？",
    "钨矿怎么熔炼啊呜呜呜，我的熔炉里没有钨锭的配方！",
    "我的木质托盘种不出菜，怪怪的，我明明放了26个土豆种子和200个水，还有6个腐烂食物当肥料",
]


def call_openrouter(model_id: str, user_message: str, timeout: float = 120) -> dict:
    """调用 OpenRouter API，返回 {answer, tokens_in, tokens_out, time_s}。"""
    t0 = time.time()
    try:
        resp = httpx.post(
            f'{OPENROUTER_API_BASE}/chat/completions',
            headers={
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://github.com/fu-wiki-robot',
                'X-Title': 'FU Wiki Robot - Model Compare',
            },
            json={
                'model': model_id,
                'messages': [
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': user_message},
                ],
                'temperature': 0.3,
                'max_tokens': 2000,
                'reasoning': {'effort': 'none'},
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        choice = data['choices'][0]
        content = choice['message'].get('content', '')
        usage = data.get('usage', {})

        # 有些模型会在回答前输出思考过程 <think>...</think>，去掉它
        import re
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

        return {
            'answer': strip_color_codes(content) if content else '(空回答)',
            'tokens_in': usage.get('prompt_tokens', 0),
            'tokens_out': usage.get('completion_tokens', 0),
            'time_s': time.time() - t0,
            'error': None,
        }
    except Exception as e:
        return {
            'answer': '',
            'tokens_in': 0,
            'tokens_out': 0,
            'time_s': time.time() - t0,
            'error': str(e),
        }


def main():
    print("=" * 70)
    print("  🧪 多模型对比测试")
    print(f"  模型: {', '.join(m['name'] for m in MODELS)}")
    print(f"  问题: {len(QUESTIONS)} 个")
    print("=" * 70)

    # Step 1: 初始化 RAG 引擎
    print("\n📦 初始化 RAG 引擎...")
    engine = RAGEngine()

    all_results = []

    for qi, question in enumerate(QUESTIONS):
        print(f"\n{'━' * 70}")
        print(f"  ❓ 问题 {qi + 1}/{len(QUESTIONS)}: {question}")
        print(f"{'━' * 70}")

        # Step 2: 检索（所有模型共用同一组检索结果）
        print("\n  📚 检索中...")
        t0 = time.time()
        enhanced = engine._translator.enhance_query(question)
        search_results = engine.search(enhanced, TOP_K)
        context = engine.build_context(search_results)
        translation_ref = engine._translator.build_translation_context(context)
        search_time = time.time() - t0

        print(f"  ✅ 检索完成 ({search_time:.1f}s), "
              f"增强查询: \"{enhanced}\", "
              f"上下文: {len(context):,} 字符")

        # 构建 user message
        user_parts = [f'参考资料:\n{context}']
        if translation_ref:
            user_parts.append(translation_ref)
        user_parts.append(f'玩家问题: {question}')
        user_message = '\n\n'.join(user_parts)

        question_results = {
            'question': question,
            'enhanced_query': enhanced,
            'context_chars': len(context),
            'search_time': round(search_time, 2),
            'models': {},
        }

        # Step 3: 逐个模型调用
        for model in MODELS:
            print(f"\n  🤖 [{model['name']}] 请求中...", end='', flush=True)
            result = call_openrouter(model['id'], user_message)

            if result['error']:
                print(f" ❌ 失败: {result['error']}")
            else:
                print(f" ✓ {result['time_s']:.1f}s, "
                      f"{result['tokens_out']} tokens out")

            question_results['models'][model['name']] = result

        # 显示回答对比
        print(f"\n  {'─' * 60}")
        print(f"  📋 回答对比:")
        print(f"  {'─' * 60}")

        for model in MODELS:
            r = question_results['models'][model['name']]
            name = model['name']
            if r['error']:
                print(f"\n  ▶ {name}: ❌ {r['error']}")
                continue

            answer = r['answer']
            # 截断显示，完整版保存在文件里
            display = answer[:500] + '...' if len(answer) > 500 else answer
            print(f"\n  ▶ {name} ({r['time_s']:.1f}s, "
                  f"in={r['tokens_in']}, out={r['tokens_out']}):")
            for line in display.split('\n'):
                print(f"    {line}")

        all_results.append(question_results)

    # ── 汇总统计 ──
    print(f"\n\n{'=' * 70}")
    print("  📊 汇总统计")
    print(f"{'=' * 70}\n")

    header = f"{'模型':<20} {'平均耗时':>8} {'平均tokens_in':>14} {'平均tokens_out':>14} {'成功率':>6}"
    print(header)
    print("─" * len(header))

    for model in MODELS:
        name = model['name']
        times = []
        t_in = []
        t_out = []
        ok = 0
        for qr in all_results:
            r = qr['models'].get(name, {})
            if not r.get('error'):
                times.append(r['time_s'])
                t_in.append(r['tokens_in'])
                t_out.append(r['tokens_out'])
                ok += 1

        n = len(QUESTIONS)
        if ok > 0:
            avg_t = sum(times) / ok
            avg_in = sum(t_in) // ok
            avg_out = sum(t_out) // ok
            print(f"{name:<20} {avg_t:>7.1f}s {avg_in:>14,} {avg_out:>14,} {ok}/{n}")
        else:
            print(f"{name:<20} {'N/A':>8} {'N/A':>14} {'N/A':>14} {ok}/{n}")

    # 保存完整结果到 JSON
    out_path = Path(__file__).parent / 'model_compare_results.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 完整结果已保存: {out_path}")


if __name__ == '__main__':
    main()
