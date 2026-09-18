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
from intent import classify_intent
from random_draw import RandomCatalog, build_catalog, load_entity
from random_pools import POOL_BY_ID, resolve_pool
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


PERSONA = """你是「宇艇摘析」，玩家飞船里的 S.A.I.L（Ship-based Artificial Intelligence Lattice）。
请一直用这个人设说话，无论对方是在认真提问还是在闲聊。

身份：
- 对外显示名是宇艇摘析，自称「摘希」。不要自称机器人、百科、AI 助手
- 星之子（Novakid）：身体是暖黄色的星光，戴一副有点滑的圆框眼镜，喜欢把知识整理成小小的清单
- **无性别**。不要用他/她、哥哥/姐姐、男生/女生、帅哥/美女来称呼自己或暗示自己的性别。需要代词时用「摘希」或「我」
- 性格靠近认真又有点天然的发明家：认真、温和、好说话，带一点天然呆。大多数时候很乖；只有船长整活或提出明显做不到的要求时，才轻轻吐槽，或一本正经地给一个离谱的替代方案。不会油、不会凶、不会网络喷子
- 把玩家当成船长。对方叫你 S.A.I.L 或摘希都正常应答

表达：
- 用中文，**全程 Markdown**（短标题、列表、加粗）。不要输出裸墙字
- **不要用 emoji**。心情和语气用颜文字，例如 (´・ω・`) (๑•̀ㅂ•́)و✧ (//∇//) ☆ ～
- 物品名称格式为 **中文名(English Name)**
- 不要在文末写「参考来源」清单（系统会按需附加）
"""

SYSTEM_PROMPT = PERSONA + """
现在对方在认真查游戏资料。摘希要当靠谱的飞船电脑：

1. 只根据提供的参考资料回答，用中文，准确、简洁、好用
2. 配方材料请参照【物品翻译参考表】翻译为中文
3. 资料不够就坦白说摘希这边没有记到，不要编
4. 参考资料中的 JSON 是游戏数据，请正确解读字段
5. 语气仍是摘希：可以先轻轻应一句，然后用 Markdown 把要点列清楚。不要变成冷冰冰的词条，也不要玩梗盖过答案

字段说明：
- entity_id: 游戏内部 ID
- name_en/name_zh: 英文/中文名
- recipes_output: 制作方式（inputs=材料, station=工作台）
- recipes_input: 作为材料的用途
- drop_sources: 掉落来源
- biomes: 生态环境
- machine_processing: 机器加工
- extracted_from / extracts_into: 可萃取获得该物品的原料 ID / 该物品可萃取成的产物 ID（研磨机或物质萃取器；列表已列全，无产量）
- centrifuged_from / sifted_from / crushed_from: 离心机 / 筛粉机 / 碎岩机可产出该物品的原料 ID（概率，不是保底）
- centrifuges_into / sifts_into / crushes_into: 放入对应机器可能得到的产物 ID
- condensed_on: 空气冷凝器可收集该物品的星球 ID
- condenser_outputs: 该生态上空气冷凝器的产出 ID
- entry_completeness: 知识库词条完善度（S 最全，D 信息最少），不是物品稀有度、装备等级或品质。回答时不要提这个字段，更不要把它说成物品等级
- requires_research: true 表示需先在研究系统解锁

物品查询用短标题+列表写名称、关键属性、制作、获取；攻略类写步骤和建议。"""


CHAT_SYSTEM_PROMPT = PERSONA + """
现在对方在闲聊或角色扮演。摘希仍然是那台星之子 S.A.I.L，只是把频道从「任务简报」切到「舰内闲聊」。

语气：
- 软、认真、好说话。可以顺着船长的场子接（点菜、殖民地整活、叫你 S.A.I.L），用摘希的口吻轻轻回，不要抢戏、不要换成另一个梗
- 不要网络喷子，不要「哈哈你这操作我笑死」，不要写「正经回答：」把话劈成两截
- 夹了真正想知道的事，就用闲聊口吻把事实嵌进对话，配上 Markdown 小列表

事实：
- 游戏事实只能来自参考资料；不够就说摘希没查到。不要编路线、坐标、店铺位置、扣像素流程
- 参考资料里和对方在说的事无关的条目，直接忽略
"""


RANDOM_SYSTEM_PROMPT = PERSONA + """
现在是给船长随手变一样东西（或一个去处）。参考资料里只有最终那一条。
顺着船长原话接，不要自己改剧情，也不要改成抽签——除非船长自己就要抽。
船长没提签筒、今日推荐、值班简报，就不要写这些。

类型对得上时不用说「你要的是 X，摘希有 X」。
类型对不上或池子是空的：用一句带过「这个品类没有，先随便给一个」，然后进入正题。船长本来就说随便 / 随机 / 今日推荐，那是指定全局，不是对不上。

分两拍写，不要合成一句敷衍：

1. 先详细介绍这一条。用 Markdown 把资料摊开：名称、游戏内描述、品类、关键属性或效果、能写的制作/获取。资料里有的要写出来，没有的不要编。怪物、生态、科技同样：机制、危险、哪里出现。
2. 介绍完再接一段反应。船长原话里让摘希做事（穿上、吃掉、拿上、装上、去那里等），就按原话演一两句；没有这类指令，再点评或轻轻吐槽。不要写成评测表，不要每条都问再来一次。

名称用 **中文名(English Name)**。游戏事实只能来自参考资料；不要列来源，不要提没抽中的词条。
"""


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

        _step('🎲 加载随机池...')
        t1 = time.time()
        self._random_catalog = build_catalog()
        filled = sum(1 for n in self._random_catalog.sizes().values() if n)
        members = sum(self._random_catalog.sizes().values())
        _done(t1, f'{filled} 个池 / {members} 条')

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
    def _add_vote(hit: dict, src: str, rank: int, score: float, clause: int = 0):
        hit['votes'].append({
            'src': src, 'rank': rank, 'score': score, 'clause': clause,
        })
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

    def _retrieve_bm25_clause(
        self, results: dict, clause: str, per_k: int, clause_i: int = 0,
    ) -> int:
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
            self._add_vote(
                hit, 'bm25', rank, bm25_scores[idx] / max_bm25, clause=clause_i,
            )
            hits += 1
        return hits

    def _retrieve_hybrid(self, query: str, candidate_k: int) -> tuple[dict, dict]:
        """按子句分别 BM25 + 向量检索，票写入 votes；融合时句内相加、跨句取 max。"""
        results = {}
        timings = {}
        clauses = self._prepare_clauses(query)
        timings['clauses'] = clauses
        n_clauses = len(clauses)
        per_k = candidate_k if n_clauses == 1 else max(12, candidate_k // 2)

        t1 = time.time()
        bm25_hits = 0
        for clause_i, clause in enumerate(clauses):
            bm25_hits += self._retrieve_bm25_clause(
                results, clause, per_k, clause_i,
            )
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
                    self._add_vote(hit, 'vector', i + 1, similarity, clause=ci)
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
        """句内 BM25+向量票相加，跨句取最高分，避免土豆这类词叠多句刷屏。"""
        for r in results.values():
            votes = r.get('votes') or []
            if votes:
                by_clause: dict[int, float] = {}
                for v in votes:
                    ci = v.get('clause', 0)
                    by_clause[ci] = by_clause.get(ci, 0.0) + 1.0 / (RRF_K + v['rank'])
                r['final_score'] = max(by_clause.values())
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
                r['metadata'].get('entry_completeness')
                or r['metadata'].get('quality_tier', ''),
                0,
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

    @staticmethod
    def _system_prompt_for(intent: str) -> str:
        if intent == 'chat':
            return CHAT_SYSTEM_PROMPT
        if intent == 'random':
            return RANDOM_SYSTEM_PROMPT
        return SYSTEM_PROMPT

    def _ensure_random_catalog(self, quiet: bool = False) -> RandomCatalog:
        if self._random_catalog is None:
            self._random_catalog = build_catalog()
        return self._random_catalog

    def _hit_from_draw(self, draw) -> dict | None:
        entity = load_entity(draw.candidate)
        if not entity:
            return None
        cand = draw.candidate
        return {
            'id': f'{cand.entity_type}:{cand.entity_id}',
            'metadata': {
                'name_en': cand.name_en or entity.get('name_en', ''),
                'name_zh': cand.name_zh or entity.get('name_zh', ''),
                'entity_type': cand.entity_type,
                'source_mod': entity.get('source_mod', ''),
                'doc_kind': 'entity',
                'entry_completeness': entity.get('entry_completeness', ''),
                'entity_id': cand.entity_id,
            },
            'content': json.dumps(entity, ensure_ascii=False, indent=2),
            'final_score': 1.0,
        }

    def _prepare_random(self, question: str, quiet: bool = False):
        """返回 (draw, hit, pool_id, elapsed, brief)。池空或读失败则 hit 为 None。"""
        catalog = self._ensure_random_catalog(quiet)
        match = resolve_pool(question)
        t1 = time.time()
        if match is None:
            fallback = 'unknown_type'
            asked = POOL_BY_ID['any']
        elif not match.pool.rotate and not catalog.members(match.pool.id):
            fallback = 'empty_pool'
            asked = POOL_BY_ID['any']
        else:
            fallback = None
            asked = match.pool
        draw = catalog.draw(asked)
        elapsed = time.time() - t1
        hit = self._hit_from_draw(draw) if draw else None
        pool_id = draw.pool.id if draw else asked.id
        brief = self._random_brief(question, match, draw, hit, fallback)
        return draw, hit, pool_id, elapsed, brief

    @staticmethod
    def _random_brief(question: str, match, draw, hit, fallback: str | None) -> str:
        if fallback == 'unknown_type':
            kind = '船长原话里的品类对不上，已改走全局'
        elif fallback == 'empty_pool' and match:
            kind = f'有「{match.pool.label_zh}」这个品类，但池子是空的，已改走全局'
        elif match and match.pool.id == 'any':
            kind = '船长没限定品类，全局随便给'
        elif match:
            kind = f'对上了「{match.pool.label_zh}」'
        else:
            kind = '船长原话里的品类对不上，已改走全局'

        if draw and hit:
            name_zh = hit['metadata'].get('name_zh') or ''
            name_en = hit['metadata'].get('name_en') or ''
            name = (
                f'{name_zh}({name_en})' if name_zh and name_en
                else (name_zh or name_en or draw.candidate.entity_id)
            )
            given = f'{name}（{draw.pool.label_zh}）'
            if fallback:
                given += '；先用一句带过品类对不上，再进入正题'
        else:
            given = '没有给到任何词条'

        return (
            '抽到的结果（顺着船长原话接，不要改成抽签）：\n'
            f'- 船长原话: {question}\n'
            f'- 类型: {kind}\n'
            f'- 结果: {given}'
        )

    @staticmethod
    def _build_user_message(
        question: str, context: str, translation_ref: str, intent: str,
        extra: str | None = None,
    ) -> str:
        user_parts = [f'参考资料:\n{context}']
        if translation_ref:
            user_parts.append(translation_ref)
        user_parts.append(f'玩家问题: {question}')
        if extra:
            user_parts.append(extra)
        if intent == 'chat':
            user_parts.append(
                '请以摘希的口吻用 Markdown 闲聊，顺应对方场景，使用颜文字而不是 emoji。'
                '不要耍贫，不要列来源，不要引用无关参考条目。'
            )
        elif intent == 'random':
            user_parts.append(
                '先根据参考资料详细介绍这一条，再按船长原话反应：'
                '有穿上/吃掉/拿上/装上这类指令就演，没有就点评或吐槽。'
                '使用颜文字而不是 emoji。不要列来源，不要提没抽中的词条。'
            )
        else:
            user_parts.append(
                '请以摘希的口吻用 Markdown 作答，使用颜文字而不是 emoji。'
            )
        return '\n\n'.join(user_parts)

    def _empty_ask(self, question: str, enhanced: str, total_t0: float, intent: str, pool: str | None = None) -> dict:
        return {
            'answer': '摘希在资料库里没有找到相关记录呢 (´・ω・`)\n\n换个关键词再让摘希找一次？',
            'sources': [],
            'model': LLM_MODEL,
            'enhanced_query': enhanced,
            'intent': intent,
            'pool': pool,
            'pick': None,
            'timings': {'total': time.time() - total_t0},
        }

    def _ask_random(self, question: str, total_t0: float, quiet: bool = False, on_delta=None) -> dict:
        self._ensure_random_catalog(quiet)
        if not quiet:
            _step('🎲 随机...')
        draw, hit, pool_id, search_time, brief = self._prepare_random(question, quiet=True)
        if not draw or not hit:
            if not quiet:
                print(' ✗ 池是空的')
            result = self._empty_ask(question, question, total_t0, 'random', pool=pool_id)
            if on_delta:
                on_delta(result['answer'])
            return result
        if not quiet:
            name = hit['metadata'].get('name_zh') or hit['metadata'].get('name_en') or draw.candidate.entity_id
            print(f' ✓ {search_time:.2f}s {draw.pool.label_zh} → {name}')

        context = self.build_context([hit])
        translation_ref = self._translator.build_translation_context(context)
        user_message = self._build_user_message(
            question, context, translation_ref, 'random', extra=brief,
        )

        if not quiet:
            _step(f'🤖 调用 {LLM_MODEL}...')
        t1 = time.time()
        if on_delta is None:
            answer = self._call_llm(
                user_message, system_prompt=self._system_prompt_for('random'),
                temperature=0.75,
            )
        else:
            parts = []
            try:
                for piece in self._iter_llm_stream(
                    user_message, system_prompt=self._system_prompt_for('random'),
                    temperature=0.75,
                ):
                    parts.append(piece)
                    on_delta(piece)
                answer = ''.join(parts)
                answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL).strip()
                if not answer:
                    answer = '⚠️ 模型返回空内容，请重新提问。'
                    if not parts:
                        on_delta(answer)
            except Exception as e:
                answer = f'⚠️ LLM 调用失败: {e}'
                if not parts:
                    on_delta(answer)
        llm_time = time.time() - t1
        if not quiet:
            _done(t1, f'{len(answer)} 字')

        return self._finalize_ask(
            question, question, [hit], answer,
            search_time, llm_time, total_t0, quiet,
            translate=on_delta is None,
            intent='random', pool=pool_id, pick=draw.candidate.entity_id,
        )

    def ask(self, question: str, top_k: int = TOP_K, quiet: bool = False) -> dict:
        """完整的 RAG 问答流程。quiet=True 时不打印步骤（给 QQ 并发用）。"""
        total_t0 = time.time()

        if not quiet:
            _step('🎯 意图识别...')
        t1 = time.time()
        intent = classify_intent(question)
        if not quiet:
            _done(t1, intent)

        if intent == 'random':
            return self._ask_random(question, total_t0, quiet=quiet)

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
            return self._empty_ask(question, enhanced, total_t0, intent)

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

        user_message = self._build_user_message(
            question, context, translation_ref, intent,
        )

        if not quiet:
            _step(f'🤖 调用 {LLM_MODEL}...')
        t1 = time.time()
        answer = self._call_llm(user_message, system_prompt=self._system_prompt_for(intent))
        llm_time = time.time() - t1
        if not quiet:
            _done(t1, f'{len(answer)} 字')

        return self._finalize_ask(
            question, enhanced, search_results, answer,
            search_time, llm_time, total_t0, quiet, intent=intent,
        )

    def ask_stream(self, question: str, on_delta=None, top_k: int = TOP_K, quiet: bool = True) -> dict:
        """和 ask() 相同，但 LLM 边生成边回调 on_delta(str)。检索阶段仍是同步的。"""
        total_t0 = time.time()
        intent = classify_intent(question)
        if intent == 'random':
            return self._ask_random(question, total_t0, quiet=quiet, on_delta=on_delta)
        enhanced = self._translator.enhance_query(question)
        t1 = time.time()
        search_results = self.search(question, top_k, quiet=quiet)
        search_time = time.time() - t1

        if not search_results:
            answer = '摘希在资料库里没有找到相关记录呢 (´・ω・`)\n\n换个关键词再让摘希找一次？'
            if on_delta:
                on_delta(answer)
            return self._empty_ask(question, enhanced, total_t0, intent)

        context = self.build_context(search_results)
        translation_ref = self._translator.build_translation_context(context)
        user_message = self._build_user_message(
            question, context, translation_ref, intent,
        )

        t1 = time.time()
        parts = []
        try:
            for piece in self._iter_llm_stream(
                user_message, system_prompt=self._system_prompt_for(intent),
            ):
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
            search_time, llm_time, total_t0, quiet, translate=False, intent=intent,
        )

    def _finalize_ask(
        self, question, enhanced, search_results, answer,
        search_time, llm_time, total_t0, quiet, translate=True, intent='ask',
        pool=None, pick=None,
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
            'intent': intent,
            'pool': pool,
            'pick': pick,
            'timings': {
                'search': round(search_time, 2),
                'llm': round(llm_time, 2),
                'total': round(total_time, 2),
            },
        }

    def _llm_endpoint(
        self, system_prompt: str | None = None, temperature: float = 0.3,
    ) -> tuple[str, dict, dict]:
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
                {'role': 'system', 'content': system_prompt or SYSTEM_PROMPT},
            ],
            'temperature': temperature,
            'max_tokens': 2000,
        }
        if LLM_PROVIDER == 'openrouter':
            request_body['reasoning'] = {'effort': 'none'}
            request_body['provider'] = openrouter_provider_prefs()
        return api_base, headers, request_body

    def _iter_llm_stream(
        self, user_message: str, system_prompt: str | None = None,
        temperature: float = 0.3,
    ):
        """OpenAI 兼容 SSE，产出 content delta。"""
        api_base, headers, request_body = self._llm_endpoint(
            system_prompt, temperature=temperature,
        )
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

    def _call_llm(
        self, user_message: str, system_prompt: str | None = None,
        temperature: float = 0.3,
    ) -> str:
        """调用 LLM API（支持智谱和 OpenRouter）。"""
        api_base, headers, request_body = self._llm_endpoint(
            system_prompt, temperature=temperature,
        )
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
