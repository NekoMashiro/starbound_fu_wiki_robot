#!/usr/bin/env python3
"""
qq_bot.py — 官方 QQ 机器人（群 @ + 消息列表单聊）

用法:
    cd rag
    python qq_bot.py          # 完整 RAG 问答
    python qq_bot.py --echo   # 只回声，不加载知识库（先跑通通道）

开放平台步骤见 ../deploy/README.md
"""

from __future__ import annotations

import argparse
import asyncio
import time
import re
import sys
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import botpy
from botpy import logging
from botpy.http import Route
from botpy.message import C2CMessage, GroupMessage

from config import (
    QQ_APP_ID,
    QQ_APP_SECRET,
    QQ_ECHO_ONLY,
    QQ_ENABLED_GROUPS,
    QQ_MAX_CONCURRENCY,
)
from qq_format import (
    BUSY_TEXT,
    EMPTY_TEXT,
    ERROR_TEXT,
    IN_FLIGHT_TEXT,
    STREAM_MAX_CHARS,
    append_sources,
    format_markdown_chunks,
    visible_markdown,
)

_log = logging.get_logger()
_MENTION_RE = re.compile(r'<@!?[^>]+>')

# 群聊被动回复最多 5 条；单聊流式共用一个 msg_seq
_MAX_PASSIVE_REPLIES = 5
_STREAM_MIN_CHARS = 24
_STREAM_MIN_INTERVAL = 0.35


def _clean_question(content: str | None) -> str:
    return _MENTION_RE.sub('', content or '').strip()


def _speaker_key(kind: str, scene_id: str, user_id: str) -> str:
    return f'{kind}:{scene_id}:{user_id}'


class WikiClient(botpy.Client):
    def __init__(self, intents, echo_only: bool = False, log_level: int = 20):
        # SDK 默认 timeout=5，api.sgroup.qq.com 偶发超时后返回 None，再去 Robot(None) 直接崩
        super().__init__(intents=intents, log_level=log_level, timeout=30)
        self._echo_only = echo_only
        self._engine = None
        self._pool: ThreadPoolExecutor | None = None
        self._sema: asyncio.Semaphore | None = None
        self._seen_ids: set[str] = set()
        self._seen_queue: deque[str] = deque(maxlen=512)
        self._in_flight: set[str] = set()

    async def _bot_login(self, token):
        from botpy.connection import ConnectionSession
        from botpy.robot import Robot

        _log.info('[botpy] 登录机器人账号中...')
        user = None
        for attempt in range(1, 4):
            user = await self.http.login(token)
            if user:
                break
            wait = 2 * attempt
            _log.warning(f'GET /users/@me 超时，{wait}s 后重试 ({attempt}/3)')
            await asyncio.sleep(wait)
        if not user:
            raise RuntimeError(
                'GET https://api.sgroup.qq.com/users/@me 连续超时。'
                'Access Token 已拿到，凭证没问题，是开放接口网络抖动。请再运行一次。'
            )

        self._ws_ap = await self.api.get_ws_url()
        if not self._ws_ap:
            raise RuntimeError('获取 WebSocket 地址失败，请稍后重试。')

        self._connection = ConnectionSession(
            max_async=self._ws_ap['session_start_limit']['max_concurrency'],
            connect=self.bot_connect,
            dispatch=self.ws_dispatch,
            loop=self.loop,
            api=self.api,
        )
        self._connection.state.robot = Robot(user)

    def attach_engine(self, engine):
        self._engine = engine
        self._pool = ThreadPoolExecutor(
            max_workers=QQ_MAX_CONCURRENCY,
            thread_name_prefix='rag',
        )

    async def on_ready(self):
        # 在 botpy 的事件循环里建信号量，避免绑定到错误的 loop
        if self._sema is None and not self._echo_only:
            self._sema = asyncio.Semaphore(QQ_MAX_CONCURRENCY)
        mode = 'echo' if self._echo_only else 'RAG'
        _log.info(f'robot ready name={getattr(self.robot, "name", "?")} mode={mode}')

    def _remember_msg(self, msg_id: str) -> bool:
        """True = 首次见到，应处理；False = 重复推送。"""
        if not msg_id:
            return True
        if msg_id in self._seen_ids:
            return False
        if len(self._seen_queue) == self._seen_queue.maxlen:
            old = self._seen_queue[0]
            self._seen_ids.discard(old)
        self._seen_queue.append(msg_id)
        self._seen_ids.add(msg_id)
        return True

    async def _reply_group(self, message: GroupMessage, content: str, msg_seq: int, markdown: bool = False):
        if markdown:
            await self.api.post_group_message(
                group_openid=message.group_openid,
                msg_type=2,
                content='',
                msg_id=message.id,
                msg_seq=msg_seq,
                markdown={'content': content},
            )
            return
        await self.api.post_group_message(
            group_openid=message.group_openid,
            msg_type=0,
            msg_id=message.id,
            msg_seq=msg_seq,
            content=content,
        )

    async def _reply_c2c(self, message: C2CMessage, content: str, msg_seq: int, markdown: bool = False):
        if markdown:
            await self.api.post_c2c_message(
                openid=message.author.user_openid,
                msg_type=2,
                content='',
                msg_id=message.id,
                msg_seq=msg_seq,
                markdown={'content': content},
            )
            return
        await self.api.post_c2c_message(
            openid=message.author.user_openid,
            msg_type=0,
            msg_id=message.id,
            msg_seq=msg_seq,
            content=content,
        )

    async def _post_c2c_stream(
        self,
        openid: str,
        msg_id: str,
        content_raw: str,
        index: int,
        stream_msg_id: str | None,
        done: bool,
    ) -> str | None:
        payload = {
            'input_mode': 'replace',
            'input_state': 10 if done else 1,
            'index': index,
            'content_type': 'markdown',
            'content_raw': content_raw,
            'msg_id': msg_id,
            'msg_seq': 1,
        }
        if stream_msg_id:
            payload['stream_msg_id'] = stream_msg_id
        data = await self.http.request(
            Route('POST', '/v2/users/{openid}/stream_messages', openid=openid),
            json=payload,
        )
        if isinstance(data, dict):
            return data.get('id') or stream_msg_id
        return stream_msg_id

    async def on_group_at_message_create(self, message: GroupMessage):
        if QQ_ENABLED_GROUPS and message.group_openid not in QQ_ENABLED_GROUPS:
            _log.info(f'skip group not in whitelist: {message.group_openid}')
            return
        user_id = (
            getattr(message.author, 'member_openid', None)
            or getattr(message.author, 'user_openid', '')
            or ''
        )
        await self._handle(
            kind='group',
            scene_id=message.group_openid,
            user_id=user_id,
            msg_id=message.id,
            content=message.content,
            send=lambda text, seq, md=False: self._reply_group(message, text, seq, markdown=md),
        )

    async def on_c2c_message_create(self, message: C2CMessage):
        user_id = getattr(message.author, 'user_openid', '') or ''
        await self._handle(
            kind='c2c',
            scene_id=user_id,
            user_id=user_id,
            msg_id=message.id,
            content=message.content,
            send=lambda text, seq, md=False: self._reply_c2c(message, text, seq, markdown=md),
            stream_openid=user_id,
        )

    async def _handle(self, *, kind, scene_id, user_id, msg_id, content, send, stream_openid=None):
        if not self._remember_msg(msg_id):
            _log.info(f'drop duplicate msg_id={msg_id}')
            return

        question = _clean_question(content)
        if not question:
            await send(EMPTY_TEXT, 1)
            return

        if self._echo_only:
            await send(question, 1)
            return

        speaker = _speaker_key(kind, scene_id, user_id)
        if speaker in self._in_flight:
            await send(IN_FLIGHT_TEXT, 1)
            return

        if self._pool is None or self._engine is None:
            await send(ERROR_TEXT, 1)
            return
        if self._sema is None:
            self._sema = asyncio.Semaphore(QQ_MAX_CONCURRENCY)

        if self._sema.locked():
            await send(BUSY_TEXT, 1)
            return

        self._in_flight.add(speaker)
        await self._sema.acquire()
        try:
            if kind == 'c2c' and stream_openid:
                result = await self._answer_c2c_stream(
                    question, stream_openid, msg_id, send,
                )
            else:
                result = await self._answer_group_markdown(question, send)
            total = (result.get('timings') or {}).get('total')
            intent = result.get('intent') or 'ask'
            pool = result.get('pool') or '-'
            pick = result.get('pick') or '-'
            _log.info(
                f'answered kind={kind} intent={intent} pool={pool} pick={pick} '
                f'q={question[:40]!r} time={total}'
            )
        except Exception:
            _log.exception('RAG ask failed')
            try:
                await send(ERROR_TEXT, 1)
            except Exception:
                _log.exception('failed to send error reply')
        finally:
            self._sema.release()
            self._in_flight.discard(speaker)

    async def _answer_group_markdown(self, question: str, send) -> dict:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            self._pool,
            lambda: self._engine.ask(question, quiet=True),
        )
        chunks = format_markdown_chunks(result)
        for i, chunk in enumerate(chunks[:_MAX_PASSIVE_REPLIES]):
            await send(chunk, i + 1, True)
        return result

    async def _answer_c2c_stream(self, question: str, openid: str, msg_id: str, send) -> dict:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def worker():
            def on_delta(piece: str):
                loop.call_soon_threadsafe(queue.put_nowait, piece)
            result = self._engine.ask_stream(question, on_delta=on_delta, quiet=True)
            loop.call_soon_threadsafe(queue.put_nowait, None)
            return result

        fut = loop.run_in_executor(self._pool, worker)
        raw = ''
        last_sent = ''
        last_flush = 0.0
        index = 0
        stream_id = None
        stream_ok = True

        async def flush(text: str, done: bool = False):
            nonlocal index, stream_id, last_sent, last_flush, stream_ok
            text = text[:STREAM_MAX_CHARS]
            if not text and not done:
                return
            if not stream_ok:
                return
            if text == last_sent and not done:
                return
            try:
                stream_id = await self._post_c2c_stream(
                    openid, msg_id, text, index, stream_id, done,
                )
                last_sent = text
                index += 1
                last_flush = time.monotonic()
            except Exception:
                _log.exception('c2c stream failed, fallback to one markdown')
                stream_ok = False

        while True:
            try:
                piece = await asyncio.wait_for(queue.get(), timeout=_STREAM_MIN_INTERVAL)
            except asyncio.TimeoutError:
                visible = visible_markdown(raw)
                if stream_ok and visible and visible != last_sent:
                    await flush(visible, False)
                if fut.done() and queue.empty():
                    break
                continue
            if piece is None:
                break
            raw += piece
            visible = visible_markdown(raw)
            enough = len(visible) - len(last_sent) >= _STREAM_MIN_CHARS
            newline = visible.endswith('\n') and visible != last_sent
            cooled = (time.monotonic() - last_flush) >= _STREAM_MIN_INTERVAL
            if stream_ok and visible and (enough or newline) and cooled:
                await flush(visible, False)

        result = await fut
        visible = visible_markdown(raw) or visible_markdown(result.get('answer') or '')
        sources = result.get('sources') or []
        if result.get('intent') in ('chat', 'random'):
            sources = []
        final = append_sources(visible, sources)
        if last_sent and not final.startswith(last_sent):
            final = last_sent
        if stream_ok and (final or last_sent):
            await flush(final or last_sent or ERROR_TEXT, True)
        if not stream_ok:
            chunks = format_markdown_chunks(result)
            await send(chunks[0], 1, True)
        return result


def main():
    parser = argparse.ArgumentParser(description='FU Wiki 官方 QQ 机器人')
    parser.add_argument(
        '--echo',
        action='store_true',
        help='只回声，不加载 RAG（用于先跑通开放平台通道）',
    )
    args = parser.parse_args()
    echo_only = args.echo or QQ_ECHO_ONLY

    if not QQ_APP_ID or not QQ_APP_SECRET:
        print('❌ 缺少 QQ_APP_ID / QQ_APP_SECRET，请写入 rag/.env')
        print('   开放平台步骤见 deploy/README.md')
        sys.exit(1)

    engine = None
    if not echo_only:
        try:
            from query import RAGEngine
            engine = RAGEngine()
        except Exception as e:
            print(f'❌ RAG 初始化失败: {e}')
            print('   请确保已运行 python ingest.py --reset 导入知识库')
            sys.exit(1)

    # 先建完索引再拉起 botpy，避免它把 jieba 日志打成 DEBUG、看起来像卡死
    intents = botpy.Intents(public_messages=True)
    client = WikiClient(intents=intents, echo_only=echo_only, log_level=20)
    if engine is not None:
        client.attach_engine(engine)

    client.run(appid=QQ_APP_ID, secret=QQ_APP_SECRET)


if __name__ == '__main__':
    main()
