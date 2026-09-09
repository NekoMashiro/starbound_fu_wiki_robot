"""
query.py — RAG 查询核心

混合检索（BM25 关键词 + 向量语义）+ LLM 生成回答。
完整文档上下文模式：检索到的文档完整传递给 LLM。
"""

import json
import os
import pickle
import re
import sys
import time
from pathlib import Path

import chromadb
import httpx
import jieba
from rank_bm25 import BM25Okapi

from config import (
    CHROMA_DB_DIR, KNOWLEDGE_BASE_DIR, BM25_CACHE_PATH,
    OPENROUTER_API_KEY, OPENROUTER_API_BASE, LLM_MODEL,
    TOP_K, BM25_WEIGHT, VECTOR_WEIGHT, MAX_CONTEXT_LENGTH,
)
from embedding import get_embedding
from translator import Translator

COLLECTION_NAME = 'fu_knowledge_base'

_COLOR_CODE_RE = re.compile(r'\^[a-zA-Z#0-9]+;')

def strip_color_codes(text: str) -> str:
    """去除 Starbound 游戏内的颜色标记。"""
    return _COLOR_CODE_RE.sub('', text) if text else text


def _step(msg: str, end: str = ''):
    """输出步骤提示（不换行，等后续补充耗时）。"""
    sys.stdout.write(f'  {msg}')
    sys.stdout.flush()


def _done(t0: float, extra: str = ''):
    """输出步骤完成耗时。"""
    elapsed = time.time() - t0
    suffix = f' {extra}' if extra else ''
    print(f' ✓ {elapsed:.2f}s{suffix}')


SYSTEM_PROMPT = """你是 Starbound 游戏知识助手，精通 Frackin' Universe (FU)、Arcana、Voyage 等主流 mod。

你的职责：
1. 根据提供的参考资料，用**中文**回答玩家的问题
2. 物品名称格式为 "中文名(English Name)"
3. 配方材料请参照【物品翻译参考表】翻译为中文
4. 回答要准确、简洁、实用
5. 如果参考资料不足以回答问题，坦诚说明
6. 参考资料中的 JSON 是游戏数据的结构化表示，请正确解读其中的字段含义

参考资料中的常见字段说明：
- entity_id: 游戏内部 ID
- name_en/name_zh: 英文/中文名
- recipes_output: 制作方式（inputs=材料, station=工作台）
- recipes_input: 作为材料的用途
- drop_sources: 掉落来源（按渠道分类）
- biomes: 出现的生态环境
- machine_processing: 机器加工方式
- requires_research: true 表示配方需先在研究系统解锁才能看到

回答格式：
- 物品查询：名称、描述、关键属性、制作方式、获取途径
- 攻略问题：步骤和建议"""


class RAGEngine:
    """RAG 检索增强生成引擎。"""

    def __init__(self):
        t0 = time.time()
        print('⏳ 初始化 RAG 引擎...')

        _step('📖 加载翻译词典...')
        t1 = time.time()
        self._translator = Translator()
        _done(t1)

        _step('🗄️  连接 ChromaDB...')
        t1 = time.time()
        self._chroma_client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
        self._collection = self._chroma_client.get_collection(COLLECTION_NAME)
        _done(t1, f'{self._collection.count()} 条文档')

        # 初始化 BM25 索引
        self._doc_index: list[dict] = []
        self._bm25 = None
        _step('📊 构建 BM25 索引...')
        t1 = time.time()
        self._build_bm25_index()
        _done(t1, f'{len(self._doc_index)} 条')

        elapsed = time.time() - t0
        print(f'✅ RAG 引擎就绪 (总耗时 {elapsed:.1f}s, LLM: {LLM_MODEL})\n')

    def _bm25_signature(self) -> tuple:
        """知识库变更时让 BM25 缓存失效。"""
        hash_path = Path(__file__).parent / 'doc_hashes.json'
        hash_mtime = hash_path.stat().st_mtime if hash_path.exists() else 0
        return ('v2-meta-only', self._collection.count(), round(hash_mtime, 3))

    def _load_bm25_cache(self, signature: tuple) -> bool:
        if not BM25_CACHE_PATH.exists():
            return False
        try:
            with open(BM25_CACHE_PATH, 'rb') as f:
                cached = pickle.load(f)
            if cached.get('signature') != signature:
                return False
            self._doc_index = cached['doc_index']
            self._bm25 = cached['bm25']
            return True
        except Exception:
            return False

    def _save_bm25_cache(self, signature: tuple):
        try:
            with open(BM25_CACHE_PATH, 'wb') as f:
                pickle.dump({
                    'signature': signature,
                    'doc_index': self._doc_index,
                    'bm25': self._bm25,
                }, f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:
            print(f'\n     ⚠️  BM25 缓存写入失败: {e}', end='')

    def _build_bm25_index(self):
        """用名称/ID 建 BM25；命中磁盘缓存则跳过分词。

        不再对全文 JSON 分词：23k 篇 × 2000 字会让每次启动卡住十几秒，
        而且 JSON 字段名还会污染关键词匹配。语义内容交给向量检索。
        """
        signature = self._bm25_signature()
        if self._load_bm25_cache(signature):
            print(' (缓存命中)', end='')
            return

        all_data = self._collection.get(include=['metadatas'])
        if not all_data['ids']:
            return

        tokenized_corpus = []
        for i, doc_id in enumerate(all_data['ids']):
            meta = all_data['metadatas'][i] or {}
            self._doc_index.append({
                'id': doc_id,
                'metadata': meta,
            })
            index_text = ' '.join(filter(None, [
                meta.get('name_en', ''),
                meta.get('name_zh', ''),
                meta.get('entity_id', ''),
                meta.get('entity_type', ''),
                meta.get('source_mod', ''),
            ])).lower()
            tokenized_corpus.append(list(jieba.cut(index_text)))

        if tokenized_corpus:
            self._bm25 = BM25Okapi(tokenized_corpus)
            self._save_bm25_cache(signature)

    def search(self, query: str, top_k: int = TOP_K, quiet: bool = False) -> list[dict]:
        """混合检索：BM25 + 向量检索，合并排序。"""
        results = {}
        timings = {}

        # ── BM25 关键词检索 ──
        t1 = time.time()
        bm25_hits = 0
        if self._bm25 and self._doc_index:
            query_tokens = list(jieba.cut(query.lower()))
            bm25_scores = self._bm25.get_scores(query_tokens)

            top_indices = sorted(
                range(len(bm25_scores)),
                key=lambda i: bm25_scores[i],
                reverse=True,
            )[:top_k * 2]

            max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1
            for idx in top_indices:
                if bm25_scores[idx] > 0:
                    doc = self._doc_index[idx]
                    doc_id = doc['id']
                    normalized_score = bm25_scores[idx] / max_bm25
                    results[doc_id] = {
                        'id': doc_id,
                        'metadata': doc['metadata'],
                        'content': None,
                        'bm25_score': normalized_score,
                        'vector_score': 0,
                    }
                    bm25_hits += 1
        timings['bm25'] = time.time() - t1

        # ── 向量语义检索 ──
        t1 = time.time()
        vector_hits = 0
        try:
            query_embedding = get_embedding(query)
            chroma_results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k * 2,
                include=['documents', 'metadatas', 'distances'],
            )

            if chroma_results['ids'] and chroma_results['ids'][0]:
                for i, doc_id in enumerate(chroma_results['ids'][0]):
                    distance = chroma_results['distances'][0][i]
                    similarity = 1 - distance

                    if doc_id in results:
                        results[doc_id]['vector_score'] = similarity
                        if results[doc_id]['content'] is None:
                            results[doc_id]['content'] = chroma_results['documents'][0][i]
                    else:
                        results[doc_id] = {
                            'id': doc_id,
                            'metadata': chroma_results['metadatas'][0][i],
                            'content': chroma_results['documents'][0][i],
                            'bm25_score': 0,
                            'vector_score': similarity,
                        }
                    vector_hits += 1
        except Exception as e:
            print(f'  ⚠️  向量检索失败: {e}')
        timings['vector'] = time.time() - t1

        # ── 混合排序 ──
        # 实体类型权重：游戏实体高权重，纯文本类低权重（减少 codex 噪声）
        _TYPE_WEIGHT = {
            'item': 1.0, 'object': 1.0, 'monster': 1.0,
            'biome': 1.0, 'tech': 1.0, 'liquid': 1.0,
            'wiki': 0.95,
            'statuseffect': 0.85, 'species': 0.85,
            'tenant': 0.8, 'collection': 0.8,
            'quest': 0.7, 'codex': 0.6,
        }
        for r in results.values():
            tier_bonus = {'S': 0.1, 'A': 0.05}.get(
                r['metadata'].get('quality_tier', ''), 0
            )
            etype = r['metadata'].get('entity_type', '')
            type_weight = _TYPE_WEIGHT.get(etype, 0.8)
            raw_score = (
                BM25_WEIGHT * r['bm25_score'] +
                VECTOR_WEIGHT * r['vector_score'] +
                tier_bonus
            )
            # 仅当 BM25 命中但向量未命中时（纯关键词巧合）施加惩罚
            if r['bm25_score'] > 0 and r['vector_score'] == 0:
                type_weight *= 0.7  # 额外惩罚仅靠关键词匹配的结果
            r['final_score'] = raw_score * type_weight

        sorted_results = sorted(
            results.values(),
            key=lambda x: x['final_score'],
            reverse=True,
        )[:top_k]

        # 加载未获取内容的文档
        t1 = time.time()
        fetch_count = 0
        for r in sorted_results:
            if r['content'] is None:
                try:
                    fetched = self._collection.get(
                        ids=[r['id']],
                        include=['documents'],
                    )
                    r['content'] = fetched['documents'][0] if fetched['documents'] else ''
                    fetch_count += 1
                except:
                    r['content'] = ''
        timings['fetch'] = time.time() - t1

        if not quiet:
            print(f'  🔍 BM25: {bm25_hits} hits ({timings["bm25"]:.2f}s) | '
                  f'向量: {vector_hits} hits ({timings["vector"]:.2f}s) | '
                  f'合并: {len(results)} → top {len(sorted_results)}')
            if fetch_count:
                print(f'     补充加载 {fetch_count} 篇文档 ({timings["fetch"]:.2f}s)')
            for i, r in enumerate(sorted_results[:5]):
                meta = r['metadata']
                name = meta.get('name_zh') or meta.get('name_en') or meta.get('entity_id', '?')
                etype = meta.get('entity_type', '')
                score = r['final_score']
                bm25 = r['bm25_score']
                vec = r['vector_score']
                print(f'     #{i+1} [{etype}] {name} '
                      f'(score={score:.3f}, bm25={bm25:.2f}, vec={vec:.2f})')

        return sorted_results

    def build_context(self, search_results: list[dict]) -> str:
        """将检索到的文档组装为 LLM 上下文。"""
        context_parts = []
        total_length = 0

        for i, r in enumerate(search_results):
            meta = r['metadata']
            content = strip_color_codes(r.get('content', '') or '')
            doc_kind = meta.get('doc_kind', 'entity')

            name_en = strip_color_codes(meta.get('name_en', ''))
            name_zh = strip_color_codes(meta.get('name_zh', ''))
            entity_type = meta.get('entity_type', '')
            source_mod = meta.get('source_mod', '')

            header = f"[参考资料 {i + 1}] "
            if doc_kind == 'wiki':
                header += f"Wiki: {name_en}"
                if source_mod:
                    header += f" (来源: {source_mod})"
            else:
                header += f"{entity_type}: {name_en}"
                if name_zh:
                    header += f" ({name_zh})"
                if source_mod:
                    header += f" [mod: {source_mod}]"

            doc_text = f"{header}\n{content}"
            remaining = MAX_CONTEXT_LENGTH - total_length
            if remaining <= 200:
                break
            if len(doc_text) > remaining:
                doc_text = doc_text[:remaining - 20] + '\n...(截断)'

            context_parts.append(doc_text)
            total_length += len(doc_text)

        return '\n\n---\n\n'.join(context_parts)

    def ask(self, question: str, top_k: int = TOP_K, quiet: bool = False) -> dict:
        """完整的 RAG 问答流程。quiet=True 时不打印步骤（给 QQ 并发用）。"""
        total_t0 = time.time()

        # Step 1: 查询增强
        if not quiet:
            _step('💡 查询增强...')
        t1 = time.time()
        enhanced = self._translator.enhance_query(question)
        if not quiet:
            if enhanced != question:
                _done(t1, f'→ "{enhanced}"')
            else:
                _done(t1, '(无变化)')

        # Step 2: 混合检索
        if not quiet:
            print('  📚 混合检索...')
        t1 = time.time()
        search_results = self.search(enhanced, top_k, quiet=quiet)
        search_time = time.time() - t1

        if not search_results:
            if not quiet:
                print('  ❌ 未找到相关文档')
            return {
                'answer': '抱歉，没有找到与你的问题相关的信息。请尝试换个关键词。',
                'sources': [],
                'model': LLM_MODEL,
                'enhanced_query': enhanced,
                'timings': {'total': time.time() - total_t0},
            }

        # Step 3: 组装上下文
        if not quiet:
            _step('📝 组装上下文...')
        t1 = time.time()
        context = self.build_context(search_results)
        translation_ref = self._translator.build_translation_context(context)
        ctx_chars = len(context)
        ctx_docs = min(len(search_results), context.count('[参考资料'))
        if not quiet:
            _done(t1, f'{ctx_docs} 篇, {ctx_chars:,} 字符')

        # Step 4: 调用 LLM
        user_parts = [f'参考资料:\n{context}']
        if translation_ref:
            user_parts.append(translation_ref)
        user_parts.append(f'玩家问题: {question}')
        user_message = '\n\n'.join(user_parts)

        if not quiet:
            _step(f'🤖 调用 {LLM_MODEL}...')
        t1 = time.time()
        answer = self._call_llm(user_message)
        llm_time = time.time() - t1
        if not quiet:
            _done(t1, f'{len(answer)} 字')

        return self._finalize_ask(
            question, enhanced, search_results, answer,
            search_time, llm_time, total_t0, quiet,
        )

    def ask_stream(self, question: str, on_delta=None, top_k: int = TOP_K, quiet: bool = True) -> dict:
        """和 ask() 相同，但 LLM 边生成边回调 on_delta(str)。检索阶段仍是同步的。"""
        total_t0 = time.time()
        enhanced = self._translator.enhance_query(question)
        t1 = time.time()
        search_results = self.search(enhanced, top_k, quiet=quiet)
        search_time = time.time() - t1

        if not search_results:
            answer = '抱歉，没有找到与你的问题相关的信息。请尝试换个关键词。'
            if on_delta:
                on_delta(answer)
            return {
                'answer': answer,
                'sources': [],
                'model': LLM_MODEL,
                'enhanced_query': enhanced,
                'timings': {'total': time.time() - total_t0},
            }

        context = self.build_context(search_results)
        translation_ref = self._translator.build_translation_context(context)
        user_parts = [f'参考资料:\n{context}']
        if translation_ref:
            user_parts.append(translation_ref)
        user_parts.append(f'玩家问题: {question}')
        user_message = '\n\n'.join(user_parts)

        t1 = time.time()
        parts = []
        try:
            for piece in self._iter_llm_stream(user_message):
                parts.append(piece)
                if on_delta:
                    on_delta(piece)
            answer = ''.join(parts)
            answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL).strip()
            if not answer:
                answer = '⚠️ 模型返回空内容，请重新提问。'
                if on_delta and not parts:
                    on_delta(answer)
        except Exception as e:
            answer = f'⚠️ LLM 调用失败: {e}'
            if on_delta and not parts:
                on_delta(answer)
        llm_time = time.time() - t1

        return self._finalize_ask(
            question, enhanced, search_results, answer,
            search_time, llm_time, total_t0, quiet, translate=False,
        )

    def _finalize_ask(
        self, question, enhanced, search_results, answer,
        search_time, llm_time, total_t0, quiet, translate=True,
    ) -> dict:
        if translate:
            answer = self._translator.translate_output(answer)
        answer = strip_color_codes(answer)

        total_time = time.time() - total_t0
        if not quiet:
            print(f'  ⏱️  总耗时 {total_time:.1f}s '
                  f'(检索 {search_time:.1f}s + LLM {llm_time:.1f}s)')

        return {
            'answer': answer,
            'sources': [
                {
                    'name_en': r['metadata'].get('name_en', ''),
                    'name_zh': r['metadata'].get('name_zh', ''),
                    'entity_type': r['metadata'].get('entity_type', ''),
                    'source_mod': r['metadata'].get('source_mod', ''),
                    'score': round(r['final_score'], 3),
                }
                for r in search_results
            ],
            'model': LLM_MODEL,
            'enhanced_query': enhanced,
            'timings': {
                'search': round(search_time, 2),
                'llm': round(llm_time, 2),
                'total': round(total_time, 2),
            },
        }

    def _llm_endpoint(self) -> tuple[str, dict, dict]:
        from config import LLM_PROVIDER, ZHIPU_API_KEY, ZHIPU_API_BASE

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

        request_body = {
            'model': LLM_MODEL,
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
            ],
            'temperature': 0.3,
            'max_tokens': 2000,
        }
        if LLM_PROVIDER == 'openrouter':
            request_body['reasoning'] = {'effort': 'none'}
            request_body['provider'] = {
                'sort': 'latency',
                'preferred_max_latency': {'p90': 25},
                'ignore': ['OpenInference'],
                'allow_fallbacks': True,
            }
        return api_base, headers, request_body

    def _iter_llm_stream(self, user_message: str):
        """OpenAI 兼容 SSE，产出 content delta。"""
        api_base, headers, request_body = self._llm_endpoint()
        request_body = dict(request_body)
        request_body['messages'] = list(request_body['messages']) + [
            {'role': 'user', 'content': user_message},
        ]
        request_body['stream'] = True

        with httpx.Client(timeout=60.0) as client:
            with client.stream(
                'POST',
                f'{api_base}/chat/completions',
                headers=headers,
                json=request_body,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    if line.startswith('data:'):
                        data = line[5:].strip()
                    else:
                        data = line.strip()
                    if not data or data == '[DONE]':
                        if data == '[DONE]':
                            break
                        continue
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get('choices') or []
                    if not choices:
                        continue
                    delta = (choices[0].get('delta') or {}).get('content') or ''
                    if delta:
                        yield delta

    def _call_llm(self, user_message: str) -> str:
        """调用 LLM API（支持智谱和 OpenRouter）。"""
        api_base, headers, request_body = self._llm_endpoint()
        request_body = dict(request_body)
        request_body['messages'] = list(request_body['messages']) + [
            {'role': 'user', 'content': user_message},
        ]
        try:
            response = httpx.post(
                f'{api_base}/chat/completions',
                headers=headers,
                json=request_body,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            choice = data['choices'][0]
            content = choice['message'].get('content', '')
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            finish_reason = choice.get('finish_reason', 'unknown')
            if not content or not content.strip():
                if finish_reason == 'sensitive':
                    return '⚠️ 模型触发了内容安全过滤，请换个问法试试。'
                return f'⚠️ 模型返回空内容 (finish_reason={finish_reason})，请重新提问。'
            return content
        except Exception as e:
            return f'⚠️ LLM 调用失败: {e}'
