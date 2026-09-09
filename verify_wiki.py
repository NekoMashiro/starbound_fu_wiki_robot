#!/usr/bin/env python3
"""
verify_wiki.py — 验证 wiki 解析质量

功能:
  1. 全面性分析：XML 中的页面 vs 提取的页面，缺失了什么？
  2. 物品搜索：在提取结果和原始 XML 中搜索特定词条
  3. 内容质量分析：文件大小分布、过短页面、清洗质量抽查
  4. 模板页面分析：被跳过的页面到底包含什么？

用法:
  python3 verify_wiki.py frackinuniversewiki-20260903.xml wiki_output
  python3 verify_wiki.py frackinuniversewiki-20260903.xml wiki_output --search "Aegisalt"
  python3 verify_wiki.py frackinuniversewiki-20260903.xml wiki_output --search "Penumbrite"
"""

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

MW_NS = "http://www.mediawiki.org/xml/export-0.11/"


def scan_xml(xml_path: str):
    """扫描 XML dump，收集所有 ns=0 页面的信息。"""
    pages = []
    for event, elem in ET.iterparse(xml_path, events=['end']):
        if elem.tag != f'{{{MW_NS}}}page':
            continue
        ns_elem = elem.find(f'{{{MW_NS}}}ns')
        ns_val = ns_elem.text if ns_elem is not None else '0'
        if ns_val != '0':
            elem.clear()
            continue

        title_elem = elem.find(f'{{{MW_NS}}}title')
        page_id_elem = elem.find(f'{{{MW_NS}}}id')
        title = title_elem.text if title_elem is not None else ''
        page_id = page_id_elem.text if page_id_elem is not None else '0'

        revisions = elem.findall(f'{{{MW_NS}}}revision')
        raw_text = ''
        if revisions:
            text_elem = revisions[-1].find(f'{{{MW_NS}}}text')
            raw_text = text_elem.text if text_elem is not None and text_elem.text else ''

        is_redirect = bool(re.match(r'#REDIRECT', raw_text, re.IGNORECASE))

        # 分析内容类型
        content_type = classify_content(raw_text, is_redirect)

        pages.append({
            'title': title,
            'page_id': page_id,
            'raw_len': len(raw_text),
            'is_redirect': is_redirect,
            'content_type': content_type,
            'raw_preview': raw_text[:300] if raw_text else '',
        })
        elem.clear()

    return pages


def classify_content(raw_text: str, is_redirect: bool) -> str:
    """分类页面内容类型。"""
    if is_redirect:
        return 'redirect'
    if not raw_text or len(raw_text.strip()) == 0:
        return 'empty'

    stripped = raw_text.strip()

    # 纯模板页面（仅包含 {{...}} 和 HTML 注释）
    no_comments = re.sub(r'<!--.*?-->', '', stripped, flags=re.DOTALL).strip()
    no_templates = re.sub(r'\{\{[^{}]*\}\}', '', no_comments)
    # 递归移除嵌套模板
    for _ in range(10):
        new = re.sub(r'\{\{[^{}]*\}\}', '', no_templates)
        if new == no_templates:
            break
        no_templates = new

    remaining = re.sub(r'\[\[Category:[^\]]*\]\]', '', no_templates, flags=re.IGNORECASE)
    remaining = re.sub(r'<[^>]+>', '', remaining)
    remaining = remaining.strip()

    if len(remaining) < 20:
        return 'template_only'

    if len(remaining) < 50:
        return 'stub'

    return 'content'


def load_output_index(output_dir: str) -> dict:
    """加载输出的 index.json。"""
    index_path = Path(output_dir) / 'index.json'
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'pages': []}


def load_redirects(output_dir: str) -> list:
    """加载重定向映射。"""
    redir_path = Path(output_dir) / 'redirects.jsonl'
    redirects = []
    if redir_path.exists():
        with open(redir_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    redirects.append(json.loads(line))
    return redirects


def analyze_completeness(xml_pages: list, output_dir: str):
    """分析数据全面性。"""
    index = load_output_index(output_dir)
    redirects = load_redirects(output_dir)

    extracted_titles = {p['title'] for p in index['pages']}
    redirect_titles = {r['from'] for r in redirects}

    # 分类统计
    type_counts = Counter(p['content_type'] for p in xml_pages)

    print('=' * 60)
    print('  📊 数据全面性分析')
    print('=' * 60)
    print()
    print(f'  XML 中 ns=0 总页面:  {len(xml_pages)}')
    print(f'  已提取为 txt:        {len(extracted_titles)}')
    print(f'  已记录重定向:        {len(redirect_titles)}')
    print()
    print('  ── XML 页面内容分类 ──')
    for ctype, count in type_counts.most_common():
        labels = {
            'content': '✅ 有实质内容',
            'template_only': '⚠️  纯模板（无静态文本）',
            'redirect': '↪️  重定向',
            'stub': '📝 极短内容（stub）',
            'empty': '❌ 空页面',
        }
        label = labels.get(ctype, ctype)
        print(f'    {label:30s}: {count:>6}')

    # 找出有内容但未被提取的页面
    content_pages = [p for p in xml_pages if p['content_type'] == 'content']
    missing_content = [p for p in content_pages if p['title'] not in extracted_titles]

    stub_pages = [p for p in xml_pages if p['content_type'] == 'stub']
    missing_stubs = [p for p in stub_pages if p['title'] not in extracted_titles]

    template_pages = [p for p in xml_pages if p['content_type'] == 'template_only']

    print()
    print('  ── 提取覆盖率 ──')
    if content_pages:
        rate = len([p for p in content_pages if p['title'] in extracted_titles]) / len(content_pages) * 100
        print(f'    有实质内容页面提取率: {rate:.1f}% ({len(content_pages) - len(missing_content)}/{len(content_pages)})')
    if missing_content:
        print(f'    ⚠️  有内容但未提取: {len(missing_content)} 页')
        print('    示例:')
        for p in missing_content[:10]:
            print(f'      - {p["title"]} ({p["raw_len"]} chars)')
            preview = p['raw_preview'][:120].replace('\n', ' ')
            print(f'        预览: {preview}...')

    print()
    print(f'  ── 纯模板页面分析（{len(template_pages)} 个）──')
    print('    这些页面在 wiki 上由模板动态生成内容，XML dump 中只有模板调用。')
    print('    常见模式:')
    template_patterns = Counter()
    for p in template_pages:
        # 提取模板名
        templates = re.findall(r'\{\{([^|{}]+)', p['raw_preview'])
        for t in templates:
            t = t.strip()
            if t and not t.startswith('!') and t not in ('DEFAULTSORT', 'DISPLAYTITLE'):
                template_patterns[t] += 1
    for pattern, count in template_patterns.most_common(15):
        print(f'      {{{{{pattern}}}}}  → {count} 页')

    print()
    print(f'  ── Stub 页面（{len(stub_pages)} 个）──')
    if stub_pages:
        print('    示例:')
        for p in stub_pages[:8]:
            remaining = re.sub(r'\{\{[^{}]*\}\}', '', p['raw_preview'])
            remaining = re.sub(r'<!--.*?-->', '', remaining, flags=re.DOTALL)
            remaining = re.sub(r'\[\[Category:[^\]]*\]\]', '', remaining, flags=re.IGNORECASE)
            remaining = re.sub(r'<[^>]+>', '', remaining).strip()
            print(f'      - {p["title"]}: "{remaining[:80]}"')

    return template_pages, missing_content


def search_item(xml_pages: list, output_dir: str, query: str):
    """在提取结果和 XML 源中搜索特定词条。"""
    index = load_output_index(output_dir)
    redirects = load_redirects(output_dir)
    output_path = Path(output_dir)

    query_lower = query.lower()

    print()
    print('=' * 60)
    print(f'  🔍 搜索: "{query}"')
    print('=' * 60)

    # 1. 在已提取的文件标题中搜索
    title_matches = [p for p in index['pages'] if query_lower in p['title'].lower()]
    print(f'\n  📁 已提取文件中匹配标题 ({len(title_matches)}):')
    for p in title_matches[:20]:
        filepath = output_path / p['file']
        print(f'    ✅ {p["title"]}  ({p["size"]} chars)  → {p["file"]}')

    # 2. 在重定向中搜索
    redir_matches = [r for r in redirects if query_lower in r['from'].lower() or query_lower in r['to'].lower()]
    if redir_matches:
        print(f'\n  ↪️  重定向中匹配 ({len(redir_matches)}):')
        for r in redir_matches[:15]:
            print(f'    {r["from"]}  →  {r["to"]}')

    # 3. 在 XML 页面标题中搜索（找到但未提取的）
    extracted_titles = {p['title'] for p in index['pages']}
    redirect_froms = {r['from'] for r in redirects}
    xml_matches = [p for p in xml_pages
                   if query_lower in p['title'].lower()
                   and p['title'] not in extracted_titles
                   and p['title'] not in redirect_froms]
    if xml_matches:
        print(f'\n  ⚠️  XML 中存在但未提取 ({len(xml_matches)}):')
        for p in xml_matches[:15]:
            preview = p['raw_preview'][:150].replace('\n', ' ')
            print(f'    - {p["title"]} [{p["content_type"]}] ({p["raw_len"]} chars)')
            print(f'      原始内容: {preview}')

    # 4. 在已提取文件的正文中搜索
    print(f'\n  📄 在已提取文件正文中搜索...')
    body_matches = []
    articles_dir = output_path / 'articles'
    if articles_dir.exists():
        for txt_file in articles_dir.iterdir():
            if txt_file.suffix == '.txt':
                content = txt_file.read_text(encoding='utf-8')
                if query_lower in content.lower():
                    # 找到匹配的上下文
                    idx = content.lower().index(query_lower)
                    start = max(0, idx - 40)
                    end = min(len(content), idx + len(query) + 40)
                    context = content[start:end].replace('\n', ' ')
                    body_matches.append((txt_file.stem, context))

    print(f'  在 {len(body_matches)} 个文件正文中提到了 "{query}":')
    for name, ctx in body_matches[:20]:
        print(f'    📖 {name}')
        print(f'       ...{ctx}...')

    if not title_matches and not redir_matches and not xml_matches and not body_matches:
        print(f'\n  ❌ 未找到任何与 "{query}" 相关的内容')


def analyze_quality(output_dir: str):
    """分析提取文件的内容质量。"""
    output_path = Path(output_dir)
    articles_dir = output_path / 'articles'

    print()
    print('=' * 60)
    print('  📈 内容质量分析')
    print('=' * 60)

    if not articles_dir.exists():
        print('  ❌ articles 目录不存在')
        return

    sizes = []
    short_pages = []
    for txt_file in sorted(articles_dir.iterdir()):
        if txt_file.suffix != '.txt':
            continue
        content = txt_file.read_text(encoding='utf-8')
        # 减去元信息头部的大小
        body_start = content.find('══')
        body = content[body_start:] if body_start >= 0 else content
        body_len = len(body.strip())
        sizes.append((txt_file.stem, body_len))
        if body_len < 100:
            short_pages.append((txt_file.stem, body_len, body.strip()[:200]))

    sizes.sort(key=lambda x: x[1])

    print(f'\n  总文件数: {len(sizes)}')
    print(f'\n  ── 文件大小分布 ──')
    brackets = [
        (0, 100, '极短 (< 100 字符)'),
        (100, 500, '短 (100-500)'),
        (500, 2000, '中等 (500-2K)'),
        (2000, 5000, '较长 (2K-5K)'),
        (5000, 10000, '长 (5K-10K)'),
        (10000, float('inf'), '非常长 (> 10K)'),
    ]
    for lo, hi, label in brackets:
        count = sum(1 for _, s in sizes if lo <= s < hi)
        bar = '█' * (count // 5) if count > 0 else ''
        print(f'    {label:25s}: {count:>5}  {bar}')

    print(f'\n  ── 最短的 15 个页面 ──')
    for name, size, preview in sorted(short_pages, key=lambda x: x[1])[:15]:
        clean_preview = preview.replace('\n', ' ').replace('══', '').strip()[:80]
        print(f'    {name:40s} ({size:>4} chars): {clean_preview}')

    print(f'\n  ── 最长的 10 个页面 ──')
    for name, size in sizes[-10:]:
        print(f'    {name:40s}: {size:>6} chars')


def main():
    parser = argparse.ArgumentParser(description='验证 wiki 解析质量')
    parser.add_argument('xml_file', help='原始 XML dump 文件')
    parser.add_argument('output_dir', help='parse_wiki.py 的输出目录')
    parser.add_argument('--search', '-s', help='搜索特定物品/词条')
    parser.add_argument('--skip-xml-scan', action='store_true',
                        help='跳过 XML 扫描（更快，但无法做全面性分析）')

    args = parser.parse_args()

    xml_pages = []
    if not args.skip_xml_scan:
        print('⏳ 正在扫描 XML dump...')
        xml_pages = scan_xml(args.xml_file)
        print(f'✅ 扫描完成，共 {len(xml_pages)} 个 ns=0 页面\n')

    if args.search:
        search_item(xml_pages, args.output_dir, args.search)
    else:
        if xml_pages:
            analyze_completeness(xml_pages, args.output_dir)
        analyze_quality(args.output_dir)


if __name__ == '__main__':
    main()
