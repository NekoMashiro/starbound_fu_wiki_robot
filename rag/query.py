"""
query.py — RAG 查询核心

混合检索（BM25 关键词 + 向量语义，RRF 融合）+ LLM 生成回答。
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
    openrouter_provider_prefs,
    TOP_K, CANDIDATE_K, RRF_K, FUSION, MAX_CLAUSES,
    BM25_WEIGHT, VECTOR_WEIGHT, MAX_CONTEXT_LENGTH,
    SEARCH_CORPUS_PATH,
)
from embedding import get_embeddings
from translator import Translator

COLLECTION_NAME = 'fu_knowledge_base'

_COLOR_CODE_RE = re.compile(r'\^[a-zA-Z#0-9]+;')
# 标点 + 空白（空格/全角空格/Tab/换行）；不按英文句点切，避免拆开 S.A.I.L
_CLAUSE_SPLIT_RE = re.compile(r'[，。；、！？!?\s]+')


def split_query_clauses(query: str, min_len: int = 2, max_clauses: int = MAX_CLAUSES) -> list[str]:
    """按标点和空白拆成检索子句；过短的丢掉，过多的尾部合并。"""
    parts = [p.strip() for p in _CLAUSE_SPLIT_RE.split(query) if p and p.strip()]
    clauses = [p for p in parts if len(p) >= min_len]
    if not clauses:
        stripped = query.strip()
        return [stripped] if stripped else []
    if len(clauses) > max_clauses:
        head = clauses[:max_clauses - 1]
        tail = '，'.join(clauses[max_clauses - 1:])
        clauses = head + [tail]
    return clauses

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
        """知识库或检索语料变更时让 BM25 缓存失效。"""
        hash_path = Path(__file__).parent / 'doc_hashes.json'
        hash_mtime = hash_path.stat().st_mtime if hash_path.exists() else 0
        corpus_mtime = (
            SEARCH_CORPUS_PATH.stat().st_mtime if SEARCH_CORPUS_PATH.exists() else 0
        )
        return (
            'v3-search-corpus',
            self._collection.count(),
            round(hash_mtime, 3),
            round(corpus_mtime, 3),
        )

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

    def _iter_bm25_rows(self):
        """优先用 ingest 写出的 embed 短文本；没有语料文件则退回 metadata。"""
        if SEARCH_CORPUS_PATH.exists():
            with open(SEARCH_CORPUS_PATH, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    yield row.get('id', ''), row.get('metadata') or {}, row.get('search_text') or ''
            return

        all_data = self._collection.get(include=['metadatas'])
        for i, doc_id in enumerate(all_data.get('ids') or []):
            meta = (all_data['metadatas'][i] or {})
            index_text = ' '.join(filter(None, [
                meta.get('name_en', ''),
                meta.get('name_zh', ''),
                meta.get('entity_id', ''),
                meta.get('entity_type', ''),
                meta.get('source_mod', ''),
            ]))
            yield doc_id, meta, index_text

    def _build_bm25_index(self):
        """用 embed 短文本建 BM25；命中磁盘缓存则跳过分词。"""
        signature = self._bm25_signature()
        if self._load_bm25_cache(signature):
            print(' (缓存命中)', end='')
            return

        tokenized_corpus = []
        for doc_id, meta, search_text in self._iter_bm25_rows():
            if not doc_id:
                continue
            self._doc_index.append({
                'id': doc_id,
                'metadata': meta,
            })
            index_text = ' '.join(filter(None, [
                meta.get('name_en', ''),
                meta.get('name_zh', ''),
                meta.get('entity_id', ''),
                search_text,
            ])).lower()
            tokenized_corpus.append(list(jieba.cut(index_text)))

        if tokenized_corpus:
            self._bm25 = BM25Okapi(tokenized_corpus)
            self._save_bm25_cache(signature)

    @staticmethod
    def _blank_hit(doc_id: str, metadata: dict, content=None) -> dict:
        return {
            'id': doc_id,
            'metadata': metadata,
            'content': content,
            'bm25_score': 0.0,
            'vector_score': 0.0,
            'bm25_rank': None,
            'vector_rank': None,
            'votes': [],
            'final_score': 0.0,
        }

    def _ensure_hit(self, results: dict, doc_id: str, metadata: dict, content=None) -> dict:
        if doc_id not in results:
            results[doc_id] = self._blank_hit(doc_id, metadata, content)
        elif content and results[doc_id]['content'] is None:
            results[doc_id]['content'] = content
        return results[doc_id]

    @staticmethod
    def _add_vote(hit: dict, src: str, rank: int, score: float):
        hit['votes'].append({'src': src, 'rank': rank, 'score': score})
        if src == 'bm25':
            if hit['bm25_rank'] is None or rank < hit['bm25_rank']:
                hit['bm25_rank'] = rank
            if score > hit['bm25_score']:
                hit['bm25_score'] = score
        else:
            if hit['vector_rank'] is None or rank < hit['vector_rank']:
                hit['vector_rank'] = rank
            if score > hit['vector_score']:
                hit['vector_score'] = score

    def _prepare_clauses(self, query: str) -> list[str]:
        raw = split_query_clauses(query)
        clauses = []
        seen = set()
        for part in raw:
            enhanced = self._translator.enhance_query(part)
            if enhanced not in seen:
                seen.add(enhanced)
                clauses.append(enhanced)
        return clauses or [query.strip()]

    def _retrieve_bm25_clause(self, results: dict, clause: str, per_k: int) -> int:
        if not (self._bm25 and self._doc_index):
            return 0
        query_tokens = list(jieba.cut(clause.lower()))
        bm25_scores = self._bm25.get_scores(query_tokens)
        top_indices = sorted(
            range(len(bm25_scores)),
            key=lambda i: bm25_scores[i],
            reverse=True,
        )[:per_k]
        max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1
        hits = 0
        rank = 0
        for idx in top_indices:
            if bm25_scores[idx] <= 0:
                continue
            rank += 1
            doc = self._doc_index[idx]
            hit = self._ensure_hit(results, doc['id'], doc['metadata'])
            self._add_vote(hit, 'bm25', rank, bm25_scores[idx] / max_bm25)
            hits += 1
        return hits

    def _retrieve_hybrid(self, query: str, candidate_k: int) -> tuple[dict, dict]:
        """按子句分别 BM25 + 向量检索，票写入 votes 供 RRF。"""
        results = {}
        timings = {}
        clauses = self._prepare_clauses(query)
        timings['clauses'] = clauses
        n_clauses = len(clauses)
        per_k = candidate_k if n_clauses == 1 else max(12, candidate_k // 2)

        t1 = time.time()
        bm25_hits = 0
        for clause in clauses:
            bm25_hits += self._retrieve_bm25_clause(results, clause, per_k)
        timings['bm25'] = time.time() - t1
        timings['bm25_hits'] = bm25_hits

        t1 = time.time()
        vector_hits = 0
        try:
            embeddings = get_embeddings(clauses)
            chroma_results = self._collection.query(
                query_embeddings=embeddings,
                n_results=per_k,
                include=['documents', 'metadatas', 'distances'],
            )
            id_lists = chroma_results.get('ids') or []
            for ci, ids in enumerate(id_lists):
                docs = chroma_results['documents'][ci]
                metas = chroma_results['metadatas'][ci]
                dists = chroma_results['distances'][ci]
                for i, doc_id in enumerate(ids):
                    similarity = 1 - dists[i]
                    hit = self._ensure_hit(results, doc_id, metas[i], docs[i])
                    self._add_vote(hit, 'vector', i + 1, similarity)
                    vector_hits += 1
        except Exception as e:
            print(f'  ⚠️  向量检索失败: {e}')
        timings['vector'] = time.time() - t1
        timings['vector_hits'] = vector_hits
        return results, timings

    def _fuse(self, results: dict, fusion: str) -> list[dict]:
        """按融合策略打分并降序排列（不截断）。"""
        if fusion == 'weighted':
            return self._fuse_weighted(results)
        return self._fuse_rrf(results)

    def _fuse_rrf(self, results: dict) -> list[dict]:
        for r in results.values():
            votes = r.get('votes') or []
            if votes:
                r['final_score'] = sum(1.0 / (RRF_K + v['rank']) for v in votes)
            else:
                score = 0.0
                if r['bm25_rank'] is not None:
                    score += 1.0 / (RRF_K + r['bm25_rank'])
                if r['vector_rank'] is not None:
                    score += 1.0 / (RRF_K + r['vector_rank'])
                r['final_score'] = score
        return sorted(results.values(), key=lambda x: x['final_score'], reverse=True)

    def _fuse_weighted(self, results: dict) -> list[dict]:
        """旧版加权求和，仅保留每路前 20，供评测对照。"""
        type_weight_map = {
            'item': 1.0, 'object': 1.0, 'monster': 1.0,
            'biome': 1.0, 'tech': 1.0, 'liquid': 1.0,
            'wiki': 0.95,
            'statuseffect': 0.85, 'species': 0.85,
            'tenant': 0.8, 'collection': 0.8,
            'quest': 0.7, 'codex': 0.6,
        }
        legacy_k = 20
        ranked = []
        for r in results.values():
            bm25 = r['bm25_score'] if (r['bm25_rank'] or 999) <= legacy_k else 0.0
            vec = r['vector_score'] if (r['vector_rank'] or 999) <= legacy_k else 0.0
            if bm25 <= 0 and vec <= 0:
                continue
            tier_bonus = {'S': 0.1, 'A': 0.05}.get(
                r['metadata'].get('quality_tier', ''), 0
            )
            etype = r['metadata'].get('entity_type', '')
            type_weight = type_weight_map.get(etype, 0.8)
            if bm25 > 0 and vec == 0:
                type_weight *= 0.7
            scored = dict(r)
            scored['bm25_score'] = bm25
            scored['vector_score'] = vec
            scored['final_score'] = (
                BM25_WEIGHT * bm25 + VECTOR_WEIGHT * vec + tier_bonus
            ) * type_weight
            ranked.append(scored)
        return sorted(ranked, key=lambda x: x['final_score'], reverse=True)

    def _fetch_missing_content(self, ranked: list[dict]) -> tuple[int, float]:
        t1 = time.time()
        fetch_count = 0
        for r in ranked:
            if r['content'] is None:
                try:
                    fetched = self._collection.get(
                        ids=[r['id']],
                        include=['documents'],
                    )
                    r['content'] = fetched['documents'][0] if fetched['documents'] else ''
                    fetch_count += 1
                except Exception:
                    r['content'] = ''
        return fetch_count, time.time() - t1

    def search(
        self,
        query: str,
        top_k: int = TOP_K,
        quiet: bool = False,
        fusion: str | None = None,
        candidate_k: int | None = None,
    ) -> list[dict]:
        """混合检索：BM25 + 向量，默认 RRF 融合。"""
        fusion = fusion or FUSION
        candidate_k = CANDIDATE_K if candidate_k is None else candidate_k
        results, timings = self._retrieve_hybrid(query, candidate_k)
        sorted_results = self._fuse(results, fusion)[:top_k]
        fetch_count, fetch_s = self._fetch_missing_content(sorted_results)
        timings['fetch'] = fetch_s

        if not quiet:
            clauses = timings.get('clauses') or []
            clause_info = f'{len(clauses)} 句 | ' if len(clauses) > 1 else ''
            print(f'  🔍 {clause_info}BM25: {timings["bm25_hits"]} hits ({timings["bm25"]:.2f}s) | '
                  f'向量: {timings["vector_hits"]} hits ({timings["vector"]:.2f}s) | '
                  f'{fusion}: {len(results)} → top {len(sorted_results)}')
            if len(clauses) > 1:
                for i, c in enumerate(clauses, 1):
                    preview = c if len(c) <= 40 else c[:40] + '…'
                    print(f'     句{i}: {preview}')
            if fetch_count:
                print(f'     补充加载 {fetch_count} 篇文档 ({timings["fetch"]:.2f}s)')
            for i, r in enumerate(sorted_results[:5]):
                meta = r['metadata']
                name = meta.get('name_zh') or meta.get('name_en') or meta.get('entity_id', '?')
                etype = meta.get('entity_type', '')
                br = r['bm25_rank'] if r['bm25_rank'] is not None else '-'
                vr = r['vector_rank'] if r['vector_rank'] is not None else '-'
                print(f'     #{i+1} [{etype}] {name} '
                      f'(score={r["final_score"]:.4f}, bm25=#{br}, vec=#{vr})')

        return sorted_results

    def search_compare(self, query: str, top_k: int = TOP_K) -> dict:
        """一次召回，分别用旧加权和新 RRF 截断，供评测对照。"""
        results, timings = self._retrieve_hybrid(query, CANDIDATE_K)
        return {
            'rrf': self._fuse(results, 'rrf')[:top_k],
            'weighted': self._fuse(results, 'weighted')[:top_k],
            'pool_size': len(results),
            'timings': timings,
        }

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
            if doc_kind in ('wiki', 'wiki_chunk'):
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
        search_results = self.search(question, top_k, quiet=quiet)
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
        search_results = self.search(question, top_k, quiet=quiet)
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
            request_body['provider'] = openrouter_provider_prefs()
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
