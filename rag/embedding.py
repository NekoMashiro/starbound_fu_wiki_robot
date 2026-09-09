"""
智谱 AI Embedding 客户端

调用智谱 embedding-3 模型将文本转为向量。
"""
import time
import httpx
from config import ZHIPU_API_KEY, ZHIPU_API_BASE, EMBEDDING_MODEL


def get_embeddings(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """
    批量获取文本的 embedding 向量。

    智谱 embedding-3 支持单次最多 32 条文本。
    超过时自动分批处理，带速率限制。
    """
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]

        # 截断过长文本（embedding-3 最大 8192 token，约 3000 汉字）
        batch = [t[:6000] if len(t) > 6000 else t for t in batch]

        response = httpx.post(
            f'{ZHIPU_API_BASE}/embeddings',
            headers={
                'Authorization': f'Bearer {ZHIPU_API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'model': EMBEDDING_MODEL,
                'input': batch,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()

        # 按 index 排序确保顺序正确
        sorted_embs = sorted(data['data'], key=lambda x: x['index'])
        all_embeddings.extend([e['embedding'] for e in sorted_embs])

        # 速率限制：避免触发 API 频率上限
        if i + batch_size < len(texts):
            time.sleep(0.3)

    return all_embeddings


def get_embedding(text: str) -> list[float]:
    """获取单条文本的 embedding 向量。"""
    return get_embeddings([text])[0]
