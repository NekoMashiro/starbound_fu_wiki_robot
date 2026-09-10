"""RAG 配置"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv(Path(__file__).parent / '.env')

# ── API Keys ──
ZHIPU_API_KEY = os.getenv('ZHIPU_API_KEY', '')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')

# ── 模型配置 ──
EMBEDDING_MODEL = 'embedding-3'
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'zhipu')  # zhipu 或 openrouter
LLM_MODEL = os.getenv('LLM_MODEL', 'glm-4-flash')

# ── 路径 ──
PROJECT_ROOT = Path(__file__).parent.parent
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / 'knowledge_base'
INDEX_JSONL = KNOWLEDGE_BASE_DIR / 'index.jsonl'
CHROMA_DB_DIR = Path(__file__).parent / 'chroma_db'
BM25_CACHE_PATH = Path(__file__).parent / 'bm25_cache.pkl'

# ── 检索参数 ──
TOP_K = 10                 # 最终返回 / 喂给 LLM 的文档数
CANDIDATE_K = 40           # 每路（BM25 / 向量）召回候选数
RRF_K = 60                 # Reciprocal Rank Fusion 常数
MAX_CLAUSES = 15           # 长问句最多拆成几段分别检索，超出的尾部合并成一句
FUSION = 'rrf'             # rrf | weighted（weighted 仅作评测对照）
BM25_WEIGHT = 0.4          # 仅 fusion=weighted 时使用
VECTOR_WEIGHT = 0.6        # 仅 fusion=weighted 时使用
MAX_CONTEXT_LENGTH = 48000 # 发给 LLM 的上下文最大字符数（~24K token）

# ── 质量过滤 ──
SKIP_QUALITY_TIERS = {'D'}  # ingest 时跳过的质量等级

# ── 智谱 API ──
ZHIPU_API_BASE = 'https://open.bigmodel.cn/api/paas/v4'

# ── OpenRouter API ──
OPENROUTER_API_BASE = 'https://openrouter.ai/api/v1'
# 优先走的上游；逗号分隔，默认 Wafer，失败再回退其他服务商
OPENROUTER_PROVIDER_ORDER = [
    x.strip() for x in os.getenv('OPENROUTER_PROVIDER_ORDER', 'wafer').split(',') if x.strip()
]


def openrouter_provider_prefs() -> dict:
    """OpenRouter provider 路由：先试 order，不可用再 fallback。"""
    return {
        'order': OPENROUTER_PROVIDER_ORDER,
        'allow_fallbacks': True,
        'ignore': ['OpenInference'],
    }

# ── QQ 官方机器人 ──
QQ_APP_ID = os.getenv('QQ_APP_ID', '')
QQ_APP_SECRET = os.getenv('QQ_APP_SECRET', '')
QQ_ECHO_ONLY = os.getenv('QQ_ECHO_ONLY', '').lower() in ('1', 'true', 'yes')
# 群 openid 白名单，逗号分隔；空则不限制
QQ_ENABLED_GROUPS = {
    x.strip() for x in os.getenv('QQ_ENABLED_GROUPS', '').split(',') if x.strip()
}
try:
    QQ_MAX_CONCURRENCY = max(1, int(os.getenv('QQ_MAX_CONCURRENCY', '2')))
except ValueError:
    QQ_MAX_CONCURRENCY = 2
