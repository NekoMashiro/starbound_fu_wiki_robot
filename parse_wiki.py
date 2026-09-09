#!/usr/bin/env python3
"""
parse_wiki.py — Frackin' Universe Wiki XML Dump Parser

将 MediaWiki XML dump 文件解析、拆分、清洗为纯文本文件，用于知识库建设。

用法:
    python3 parse_wiki.py frackinuniversewiki-20260903.xml -o wiki_output

输出结构:
    wiki_output/
    ├── articles/          # ns=0  主要内容页面 (12000+)
    ├── categories/        # ns=14 分类页面
    ├── treasure_pools/    # ns=3000 宝藏池数据
    ├── redirects.jsonl    # 重定向映射
    └── index.json         # 所有页面索引
"""

import argparse
import json
import os
import re
import sys
import html
import time
import xml.etree.ElementTree as ET
from pathlib import Path

# MediaWiki XML namespace
MW_NS = "http://www.mediawiki.org/xml/export-0.11/"

# 要提取的 wiki 命名空间及对应输出目录
NS_CONFIG = {
    "0":    "articles",         # 主要内容
    "14":   "categories",       # 分类
    "3000": "treasure_pools",   # TreasurePool 游戏数据
}


# ─────────────────────────────────────────────
# Wikitext → 纯文本 清洗器
# ─────────────────────────────────────────────

def clean_wikitext(raw: str) -> str:
    """将 MediaWiki wikitext 标记转换为干净的纯文本。"""

    text = raw

    # 0. HTML实体解码
    text = html.unescape(text)

    # 1. 移除 <ref>...</ref> 和自闭合 <ref ... />
    text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<ref[^/>]*/>', '', text, flags=re.IGNORECASE)

    # 2. 移除 <gallery>...</gallery>
    text = re.sub(r'<gallery[^>]*>.*?</gallery>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # 3. 移除 <nowiki>...</nowiki> 标签（保留内容）
    text = re.sub(r'</?nowiki>', '', text, flags=re.IGNORECASE)

    # 4. 移除 HTML 注释
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

    # 5. 移除 <div>, <span>, <big>, <small>, <br>, <hr> 等HTML标签
    text = re.sub(r'</?(?:div|span|big|small|center|blockquote|code|pre|s|u|sub|sup|em|strong|p|li|ul|ol|dl|dd|dt)[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<hr\s*/?>', '\n---\n', text, flags=re.IGNORECASE)

    # 6. 移除 __NOTOC__, __TOC__, __FORCETOC__ 等魔术词
    text = re.sub(r'__[A-Z]+__', '', text)

    # 7. 处理模板 {{...}}（嵌套处理）
    text = _remove_templates(text)

    # 8. 处理分类链接 [[Category:...]] → 提取分类信息
    categories = re.findall(r'\[\[Category:([^\]|]+)(?:\|[^\]]*)?\]\]', text, re.IGNORECASE)
    text = re.sub(r'\[\[Category:[^\]]*\]\]', '', text, flags=re.IGNORECASE)

    # 9. 处理文件/图片链接 [[File:...]] [[Image:...]] → 移除
    text = re.sub(r'\[\[(?:File|Image):[^\]]*\]\]', '', text, flags=re.IGNORECASE)

    # 10. 处理内部链接 [[Target|Display]] → Display, [[Target]] → Target
    text = re.sub(r'\[\[([^\]|]*)\|([^\]]*)\]\]', r'\2', text)
    text = re.sub(r'\[\[([^\]]*)\]\]', r'\1', text)

    # 11. 处理外部链接 [url text] → text, [url] → url
    text = re.sub(r'\[https?://\S+\s+([^\]]+)\]', r'\1', text)
    text = re.sub(r'\[https?://(\S+)\]', r'\1', text)

    # 12. 处理标题 === Title === → Title
    text = re.sub(r'^(={1,6})\s*(.+?)\s*\1\s*$', _heading_to_text, text, flags=re.MULTILINE)

    # 13. 处理粗体/斜体
    text = re.sub(r"'{5}(.+?)'{5}", r'\1', text)  # 粗斜体
    text = re.sub(r"'{3}(.+?)'{3}", r'\1', text)   # 粗体
    text = re.sub(r"'{2}(.+?)'{2}", r'\1', text)    # 斜体

    # 14. 处理wiki表格 {| ... |} → 简化为文本行
    text = _clean_tables(text)

    # 15. 处理列表项标记
    text = re.sub(r'^[*#;:]+\s*', '• ', text, flags=re.MULTILINE)

    # 16. 移除剩余 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)

    # 17. 清理多余空白
    text = re.sub(r'[ \t]+', ' ', text)            # 合并水平空白
    text = re.sub(r'\n{3,}', '\n\n', text)          # 最多两个连续换行
    text = re.sub(r'^\s+$', '', text, flags=re.MULTILINE)  # 移除只有空白的行

    # 18. 添加分类到末尾
    if categories:
        text = text.rstrip() + '\n\n分类: ' + ', '.join(categories)

    return text.strip()


def _heading_to_text(match: re.Match) -> str:
    """将 wiki 标题转为带分隔的纯文本。"""
    level = len(match.group(1))
    title = match.group(2).strip()
    if level <= 2:
        return f"\n{'─' * 40}\n{title}\n{'─' * 40}"
    else:
        return f"\n【{title}】"


def _remove_templates(text: str) -> str:
    """递归移除 {{模板}} 标记。保留部分有用模板的内容。"""
    max_iterations = 50
    for _ in range(max_iterations):
        # 找到最内层的 {{ ... }}（不包含嵌套）
        new_text = re.sub(r'\{\{([^{}]*)\}\}', _process_template, text)
        if new_text == text:
            break
        text = new_text
    return text


def _process_template(match: re.Match) -> str:
    """处理单个模板调用，提取有用信息。"""
    content = match.group(1).strip()

    # 一些有信息价值的模板，提取其参数
    lower = content.lower()

    # {{SITENAME}} → Frackin' Universe Wiki
    if lower == 'sitename':
        return "Frackin' Universe Wiki"

    # {{Quote|text|author}} → "text" — author
    if lower.startswith('quote|'):
        parts = content.split('|')
        if len(parts) >= 3:
            return f'"{parts[1].strip()}" — {parts[2].strip()}'
        elif len(parts) >= 2:
            return f'"{parts[1].strip()}"'

    # {{Color|color|text}} → text
    if lower.startswith('color|'):
        parts = content.split('|')
        if len(parts) >= 3:
            return parts[2].strip()

    # {{Item|name}} → name
    if lower.startswith('item|'):
        parts = content.split('|')
        if len(parts) >= 2:
            return parts[1].strip()

    # {{Tip|text}} / {{Note|text}} / {{Warning|text}} → text
    for prefix in ('tip|', 'note|', 'warning|', 'notice|', 'important|'):
        if lower.startswith(prefix):
            parts = content.split('|', 1)
            if len(parts) >= 2:
                return f'[{parts[0].strip()}] {parts[1].strip()}'

    # 其他模板默认移除
    return ''


def _clean_tables(text: str) -> str:
    """将 wiki 表格转换为简单文本表示。"""
    lines = text.split('\n')
    result = []
    in_table = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith('{|'):
            in_table = True
            continue
        elif stripped.startswith('|}'):
            in_table = False
            result.append('')
            continue

        if in_table:
            if stripped.startswith('|-'):
                result.append('---')
                continue
            if stripped.startswith('!'):
                # 表头
                cells = re.split(r'\s*!!\s*', stripped[1:].strip())
                result.append(' | '.join(c.strip() for c in cells if c.strip()))
            elif stripped.startswith('|'):
                # 表格单元
                cells = re.split(r'\s*\|\|\s*', stripped[1:].strip())
                result.append(' | '.join(c.strip() for c in cells if c.strip()))
        else:
            result.append(line)

    return '\n'.join(result)


# ─────────────────────────────────────────────
# 文件名安全处理
# ─────────────────────────────────────────────

def safe_filename(title: str) -> str:
    """将页面标题转换为安全的文件名。"""
    name = title.replace('/', '_')
    name = re.sub(r'[<>:"|?*\\]', '_', name)
    name = name.strip('. ')
    if not name:
        name = '_unnamed_'
    if len(name) > 200:
        name = name[:200]
    return name


# ─────────────────────────────────────────────
# XML 解析主逻辑
# ─────────────────────────────────────────────

def parse_wiki_dump(xml_path: str, output_dir: str, namespaces: dict[str, str]):
    """
    解析 MediaWiki XML dump，提取每个页面的最新版本，
    清洗 wikitext 并保存为纯文本文件。
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 创建输出子目录
    for subdir in namespaces.values():
        (output_path / subdir).mkdir(exist_ok=True)

    # 统计
    stats = {
        'total_pages': 0,
        'extracted_pages': 0,
        'skipped_redirect': 0,
        'skipped_empty': 0,
        'skipped_ns': 0,
        'by_namespace': {},
    }
    redirects = []
    index = []

    print(f"📂 输出目录: {output_path.resolve()}")
    print(f"📖 开始解析: {xml_path}")
    print(f"📝 提取命名空间: {namespaces}")
    print()

    start_time = time.time()

    # 使用 iterparse 逐个处理 <page> 元素（内存友好）
    context = ET.iterparse(xml_path, events=['end'])

    for event, elem in context:
        tag = elem.tag

        if tag != f'{{{MW_NS}}}page':
            continue

        stats['total_pages'] += 1

        # 提取页面元信息
        title_elem = elem.find(f'{{{MW_NS}}}title')
        ns_elem = elem.find(f'{{{MW_NS}}}ns')
        page_id_elem = elem.find(f'{{{MW_NS}}}id')

        title = title_elem.text if title_elem is not None else 'Untitled'
        ns_val = ns_elem.text if ns_elem is not None else '0'
        page_id = page_id_elem.text if page_id_elem is not None else '0'

        # 进度显示
        if stats['total_pages'] % 2000 == 0:
            elapsed = time.time() - start_time
            print(f"  ⏳ 已处理 {stats['total_pages']} 页 ({elapsed:.1f}s) ...")

        # 过滤命名空间
        if ns_val not in namespaces:
            stats['skipped_ns'] += 1
            elem.clear()
            continue

        # 获取最新版本的文本内容（最后一个 <revision>）
        revisions = elem.findall(f'{{{MW_NS}}}revision')
        if not revisions:
            stats['skipped_empty'] += 1
            elem.clear()
            continue

        last_rev = revisions[-1]
        text_elem = last_rev.find(f'{{{MW_NS}}}text')
        timestamp_elem = last_rev.find(f'{{{MW_NS}}}timestamp')

        raw_text = text_elem.text if text_elem is not None else ''
        timestamp = timestamp_elem.text if timestamp_elem is not None else ''

        # 检查重定向
        if not raw_text:
            stats['skipped_empty'] += 1
            elem.clear()
            continue

        redirect_match = re.match(r'#REDIRECT\s*\[\[(.+?)\]\]', raw_text, re.IGNORECASE)
        if redirect_match:
            target = redirect_match.group(1)
            redirects.append({
                'from': title,
                'to': target,
                'ns': ns_val,
                'page_id': page_id,
            })
            stats['skipped_redirect'] += 1
            elem.clear()
            continue

        # 清洗 wikitext → 纯文本
        cleaned = clean_wikitext(raw_text)

        # 跳过清洗后内容太少的页面
        if len(cleaned.strip()) < 20:
            stats['skipped_empty'] += 1
            elem.clear()
            continue

        # 构建输出文件
        subdir = namespaces[ns_val]
        filename = safe_filename(title) + '.txt'
        filepath = output_path / subdir / filename

        # 写入文件（带元信息头部）
        header = f"标题: {title}\n页面ID: {page_id}\n最后更新: {timestamp}\n{'═' * 50}\n\n"
        filepath.write_text(header + cleaned, encoding='utf-8')

        # 记录索引
        index.append({
            'title': title,
            'page_id': int(page_id),
            'ns': int(ns_val),
            'file': str(filepath.relative_to(output_path)),
            'size': len(cleaned),
            'timestamp': timestamp,
        })

        stats['extracted_pages'] += 1
        ns_name = namespaces[ns_val]
        stats['by_namespace'][ns_name] = stats['by_namespace'].get(ns_name, 0) + 1

        # 释放内存
        elem.clear()

    elapsed = time.time() - start_time

    # 保存重定向映射
    redirect_path = output_path / 'redirects.jsonl'
    with open(redirect_path, 'w', encoding='utf-8') as f:
        for r in redirects:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    # 保存索引
    index.sort(key=lambda x: x['title'])
    index_path = output_path / 'index.json'
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump({
            'wiki': "Frackin' Universe Wiki",
            'source': xml_path,
            'total_articles': len(index),
            'total_redirects': len(redirects),
            'pages': index,
        }, f, ensure_ascii=False, indent=2)

    # 打印统计摘要
    print()
    print('═' * 55)
    print('  Frackin\' Universe Wiki 解析完成!')
    print('═' * 55)
    print(f'  耗时:         {elapsed:.1f} 秒')
    print(f'  总页面数:     {stats["total_pages"]}')
    print(f'  提取页面:     {stats["extracted_pages"]}')
    print(f'  重定向:       {stats["skipped_redirect"]}')
    print(f'  空/过短页面:  {stats["skipped_empty"]}')
    print(f'  跳过(命名空间): {stats["skipped_ns"]}')
    print(f'  ─────────────────────────────────')
    for ns_name, count in sorted(stats['by_namespace'].items()):
        print(f'  {ns_name:20s}: {count:>6} 篇')
    print(f'  ─────────────────────────────────')
    print(f'  输出目录:     {output_path.resolve()}')
    print(f'  索引文件:     {index_path}')
    print(f'  重定向映射:   {redirect_path}')
    print('═' * 55)


def main():
    parser = argparse.ArgumentParser(
        description='解析 MediaWiki XML dump，拆分清洗为纯文本文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('xml_file', help='MediaWiki XML dump 文件路径')
    parser.add_argument('-o', '--output', default='wiki_output',
                        help='输出目录 (默认: wiki_output)')
    parser.add_argument('--ns', nargs='*', default=None,
                        help='要提取的命名空间编号 (默认: 0 14 3000)')

    args = parser.parse_args()

    if not os.path.isfile(args.xml_file):
        print(f'❌ 文件不存在: {args.xml_file}', file=sys.stderr)
        sys.exit(1)

    namespaces = NS_CONFIG
    if args.ns:
        namespaces = {k: NS_CONFIG.get(k, f'ns_{k}') for k in args.ns}

    parse_wiki_dump(args.xml_file, args.output, namespaces)


if __name__ == '__main__':
    main()
