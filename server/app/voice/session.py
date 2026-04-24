"""
语音会话状态机

职责：
- 管理与单个前端 WebSocket 的生命周期
- 驱动 ASR -> LLM -> TTS 的流水线
- 支持打断（interrupt）与静音（mute）
"""
import asyncio
import json
import logging
from typing import List, Dict, Optional

from fastapi import WebSocket, WebSocketDisconnect

from app.voice.asr_doubao import DoubaoASRClient
from app.voice.llm_ark import ArkLLMClient
from app.voice.tts_openai import OpenAITTSClient
from app.voice.prompts import OPENING_LINE

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 20  # 保留最近 20 轮（user+assistant 共 40 条）


class VoiceSession:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.history: List[Dict[str, str]] = []

        self.asr: Optional[DoubaoASRClient] = None
        self.llm = ArkLLMClient()
        self.tts = OpenAITTSClient()

        # 当前 AI 响应任务（可取消 = 打断）
        self._reply_task: Optional[asyncio.Task] = None
        self._cancel_event: Optional[asyncio.Event] = None

        # tts 序号（前端据此过滤过期 chunk）
        self._reply_seq = 0

        # 待处理的 ASR final 文本队列
        self._asr_final_queue: asyncio.Queue[str] = asyncio.Queue()

        # 控制
        self._closed = False
        self._muted = False  # 静音 = 前端不发 PCM；后端这里主要是打断策略用

    # ---------- 对外主入口 ----------

    async def run(self):
        """会话主循环：并行跑 ASR 接收 + 前端消息循环 + 回复消费者"""
        try:
            await self._send_json({"type": "session.ready"})
            await self._start_asr()

            # 开场白
            asyncio.create_task(self._handle_user_turn(OPENING_LINE, is_opening=True))

            # 消费 ASR final -> 触发回复
            consumer = asyncio.create_task(self._final_consumer())
            try:
                await self._client_loop()
            finally:
                consumer.cancel()
                try:
                    await consumer
                except asyncio.CancelledError:
                    pass
        finally:
            await self.close()

    # ---------- ASR ----------

    async def _start_asr(self):
        async def on_partial(text: str):
            await self._send_json({"type": "asr.partial", "text": text})

        async def on_final(text: str):
            await self._send_json({"type": "asr.final", "text": text})
            await self._asr_final_queue.put(text)

        self.asr = DoubaoASRClient(on_partial=on_partial, on_final=on_final)
        try:
            await self.asr.connect()
        except Exception as e:
            logger.error(f"[Session] ASR connect failed: {e}", exc_info=True)
            await self._send_json({"type": "error", "code": "asr_connect_failed", "message": str(e)})

    # ---------- 前端消息循环 ----------

    async def _client_loop(self):
        while not self._closed:
            try:
                msg = await self.ws.receive()
            except WebSocketDisconnect:
                logger.info("[Session] client disconnected")
                return

            mtype = msg.get("type")
            if mtype == "websocket.disconnect":
                return

            if "bytes" in msg and msg["bytes"] is not None:
                # 二进制：PCM 音频帧
                if not self._muted and self.asr:
                    await self.asr.send_audio(msg["bytes"])
                continue

            text = msg.get("text")
            if not text:
                continue
            try:
                data = json.loads(text)
            except Exception:
                continue

            await self._on_client_event(data)

    async def _on_client_event(self, data: dict):
        t = data.get("type")
        if t == "mute":
            self._muted = True
            logger.info("[Session] muted")
        elif t == "unmute":
            self._muted = False
            logger.info("[Session] unmuted")
        elif t == "interrupt":
            logger.info("[Session] interrupt requested by client")
            await self._interrupt_reply()
        elif t == "reset":
            await self._interrupt_reply()
            self.history.clear()
            logger.info("[Session] conversation reset")
        elif t == "ping":
            await self._send_json({"type": "pong"})

    # ---------- 回复流水线 ----------

    async def _final_consumer(self):
        while not self._closed:
            try:
                user_text = await self._asr_final_queue.get()
            except asyncio.CancelledError:
                return
            if not user_text.strip():
                continue
            # 新用户话到来 -> 打断当前 AI
            await self._interrupt_reply()
            self._reply_task = asyncio.create_task(self._handle_user_turn(user_text))

    async def _handle_user_turn(self, user_text: str, is_opening: bool = False):
        """
        处理一轮用户输入：调用 LLM 流式 -> 按句送 TTS -> 向前端推送文本与音频。
        is_opening=True 时跳过 LLM，直接 TTS 播开场白，且不写入 history 的 user 侧。
        """
        self._reply_seq += 1
        seq = self._reply_seq
        self._cancel_event = asyncio.Event()
        cancel_event = self._cancel_event

        try:
            if is_opening:
                await self._send_json({"type": "llm.done", "seq": seq, "text": user_text})
                await self._synthesize_and_send(user_text, seq, cancel_event)
                # 开场白计入 assistant 历史
                self.history.append({"role": "assistant", "content": user_text})
                self._trim_history()
                return

            # 正常用户轮次
            await self._send_json({"type": "turn.start", "seq": seq, "user_text": user_text})

            full_reply = ""
            tts_tasks: List[asyncio.Task] = []

            async for item in self.llm.stream_reply(
                history=self.history,
                user_text=user_text,
                cancel_event=cancel_event,
            ):
                if cancel_event.is_set():
                    break
                kind = item.get("type")
                if kind == "delta":
                    await self._send_json({"type": "llm.delta", "seq": seq, "text": item["text"]})
                elif kind == "sentence":
                    sentence = item["text"].strip()
                    if sentence:
                        # 并行跑 TTS（按句串行会更稳，这里先串行保证音频顺序）
                        await self._synthesize_and_send(sentence, seq, cancel_event)
                elif kind == "done":
                    full_reply = item["text"]

            await asyncio.gather(*tts_tasks, return_exceptions=True)

            if cancel_event.is_set():
                await self._send_json({"type": "turn.cancelled", "seq": seq})
                return

            # 写入历史
            self.history.append({"role": "user", "content": user_text})
            if full_reply:
                self.history.append({"role": "assistant", "content": full_reply})
            self._trim_history()

            await self._send_json({"type": "turn.end", "seq": seq, "text": full_reply})

        except Exception as e:
            logger.error(f"[Session] handle_user_turn error: {e}", exc_info=True)
            await self._send_json({"type": "error", "code": "turn_failed", "message": str(e)})

    async def _synthesize_and_send(self, sentence: str, seq: int, cancel_event: asyncio.Event):
        """把一句话转 MP3 chunk 流式发给前端"""
        await self._send_json({"type": "tts.begin", "seq": seq, "text": sentence})
        try:
            async for chunk in self.tts.stream_speech(sentence, cancel_event=cancel_event):
                if cancel_event.is_set():
                    break
                # 二进制帧前加一字节 seq 便于前端匹配（简单做法：通过前置 JSON 通知 seq）
                await self.ws.send_bytes(chunk)
        except Exception as e:
            logger.error(f"[Session] tts error: {e}", exc_info=True)
        await self._send_json({"type": "tts.end", "seq": seq})

    async def _interrupt_reply(self):
        if self._cancel_event:
            self._cancel_event.set()
        if self._reply_task and not self._reply_task.done():
            self._reply_task.cancel()
            try:
                await self._reply_task
            except (asyncio.CancelledError, Exception):
                pass
        self._reply_task = None
        # 通知前端清空当前播放 buffer
        await self._send_json({"type": "tts.flush"})

    # ---------- 工具 ----------

    def _trim_history(self):
        max_items = MAX_HISTORY_TURNS * 2
        if len(self.history) > max_items:
            self.history = self.history[-max_items:]

    async def _send_json(self, obj: dict):
        if self._closed:
            return
        try:
            await self.ws.send_text(json.dumps(obj, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"[Session] send_json failed: {e}")

    async def close(self):
        if self._closed:
            return
        self._closed = True
        if self._cancel_event:
            self._cancel_event.set()
        if self._reply_task:
            self._reply_task.cancel()
        if self.asr:
            await self.asr.close()
        try:
            await self.ws.close()
        except Exception:
            pass
