"""
豆包流式语音识别大模型客户端
协议：https://www.volcengine.com/docs/6561/1354869 （流式语音识别大模型）
WebSocket: wss://openspeech.bytedance.com/api/v3/sauc/bigmodel
二进制协议：4字节 header + (可选)序列号 + 4字节 payload size + payload
"""
import asyncio
import gzip
import json
import logging
import struct
import uuid
from typing import AsyncIterator, Optional

import websockets

from app.config import settings

logger = logging.getLogger(__name__)

# ===== 协议常量 =====
PROTOCOL_VERSION = 0b0001
HEADER_SIZE_4B = 0b0001

# message type
CLIENT_FULL_REQUEST = 0b0001  # 初始化/参数
CLIENT_AUDIO_ONLY = 0b0010
SERVER_FULL_RESPONSE = 0b1001
SERVER_ACK = 0b1011
SERVER_ERROR = 0b1111

# message type specific flags (lower 4 bits of byte 1 extension)
FLAG_NONE = 0b0000
FLAG_POS_SEQ = 0b0001           # 带序列号（正数）
FLAG_NEG_SEQ_LAST = 0b0011      # 带序列号（负数，表示最后一包）

# serialization
SERIAL_NONE = 0b0000
SERIAL_JSON = 0b0001

# compression
COMP_NONE = 0b0000
COMP_GZIP = 0b0001


def _make_header(message_type: int, flags: int, serial: int, comp: int) -> bytes:
    """4 字节 header"""
    b = bytearray(4)
    b[0] = (PROTOCOL_VERSION << 4) | HEADER_SIZE_4B
    b[1] = (message_type << 4) | flags
    b[2] = (serial << 4) | comp
    b[3] = 0x00  # reserved
    return bytes(b)


def _build_full_request(payload: dict, seq: int = 1) -> bytes:
    """初始化请求（JSON + gzip，带正序列号）"""
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    compressed = gzip.compress(raw)
    header = _make_header(CLIENT_FULL_REQUEST, FLAG_POS_SEQ, SERIAL_JSON, COMP_GZIP)
    seq_bytes = struct.pack(">i", seq)
    size_bytes = struct.pack(">I", len(compressed))
    return header + seq_bytes + size_bytes + compressed


def _build_audio_frame(audio: bytes, seq: int, is_last: bool) -> bytes:
    """音频包（PCM 原始，不压缩）"""
    flags = FLAG_NEG_SEQ_LAST if is_last else FLAG_POS_SEQ
    # 最后一包时 seq 应为负数
    signed_seq = -seq if is_last else seq
    header = _make_header(CLIENT_AUDIO_ONLY, flags, SERIAL_NONE, COMP_NONE)
    seq_bytes = struct.pack(">i", signed_seq)
    size_bytes = struct.pack(">I", len(audio))
    return header + seq_bytes + size_bytes + audio


def _parse_response(data: bytes) -> dict:
    """解析服务端响应"""
    if len(data) < 4:
        return {"_error": "response too short"}

    b0, b1, b2, _ = data[0], data[1], data[2], data[3]
    header_size = (b0 & 0x0F) * 4
    message_type = (b1 >> 4) & 0x0F
    flags = b1 & 0x0F
    serial = (b2 >> 4) & 0x0F
    comp = b2 & 0x0F

    offset = header_size
    result: dict = {
        "_message_type": message_type,
        "_flags": flags,
    }

    # 可选序列号（flags 低位 0b0001 / 0b0011 有 seq）
    if flags in (FLAG_POS_SEQ, FLAG_NEG_SEQ_LAST):
        (seq,) = struct.unpack(">i", data[offset:offset + 4])
        result["_seq"] = seq
        offset += 4

    if message_type == SERVER_ERROR:
        (code,) = struct.unpack(">I", data[offset:offset + 4])
        offset += 4
        (size,) = struct.unpack(">I", data[offset:offset + 4])
        offset += 4
        msg = data[offset:offset + size]
        if comp == COMP_GZIP:
            try:
                msg = gzip.decompress(msg)
            except Exception:
                pass
        result["_error_code"] = code
        result["_error_msg"] = msg.decode("utf-8", errors="replace")
        return result

    # payload
    if offset + 4 > len(data):
        return result
    (size,) = struct.unpack(">I", data[offset:offset + 4])
    offset += 4
    payload = data[offset:offset + size]

    if comp == COMP_GZIP and payload:
        try:
            payload = gzip.decompress(payload)
        except Exception as e:
            result["_decompress_error"] = str(e)
            return result

    if serial == SERIAL_JSON and payload:
        try:
            result["payload"] = json.loads(payload.decode("utf-8"))
        except Exception as e:
            result["_json_error"] = str(e)
            result["_raw"] = payload
    else:
        result["_raw"] = payload

    return result


class DoubaoASRClient:
    """
    豆包流式 ASR 客户端。
    使用方式：
        async with DoubaoASRClient(on_partial, on_final) as asr:
            await asr.send_audio(pcm_chunk)
            ...
            await asr.finish()
    """

    def __init__(
        self,
        on_partial=None,
        on_final=None,
        language: str = "zh-CN",  # 豆包大模型支持混合识别，设中文即可兼容中英文
        sample_rate: int = 16000,
    ):
        self.on_partial = on_partial
        self.on_final = on_final
        self.language = language
        self.sample_rate = sample_rate

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._seq = 1
        self._recv_task: Optional[asyncio.Task] = None
        self._closed = False
        self._connect_id = str(uuid.uuid4())
        self._request_id = str(uuid.uuid4())

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def connect(self):
        if not (settings.asr_app_id and settings.asr_access_token):
            raise RuntimeError("ASR 未配置：ASR_APP_ID / ASR_ACCESS_TOKEN 缺失")

        headers = {
            "X-Api-App-Key": settings.asr_app_id,
            "X-Api-Access-Key": settings.asr_access_token,
            "X-Api-Resource-Id": settings.asr_resource_id,
            "X-Api-Request-Id": self._request_id,
            "X-Api-Connect-Id": self._connect_id,
        }

        logger.info(f"[ASR] connecting: request_id={self._request_id}")
        # websockets >= 12 用 additional_headers；<= 11 用 extra_headers
        try:
            self._ws = await websockets.connect(
                settings.asr_ws_url,
                additional_headers=headers,
                max_size=None,
            )
        except TypeError:
            self._ws = await websockets.connect(
                settings.asr_ws_url,
                extra_headers=headers,
                max_size=None,
            )

        # 发送初始化参数
        init_payload = {
            "user": {"uid": "english_flashcard_user"},
            "audio": {
                "format": "pcm",
                "sample_rate": self.sample_rate,
                "bits": 16,
                "channel": 1,
                "codec": "raw",
            },
            "request": {
                "model_name": "bigmodel",
                "enable_punc": True,
                "enable_itn": True,
                "show_utterances": True,
                "result_type": "single",
            },
        }
        await self._ws.send(_build_full_request(init_payload, seq=self._seq))
        self._seq += 1

        self._recv_task = asyncio.create_task(self._recv_loop())

    async def _recv_loop(self):
        assert self._ws is not None
        try:
            async for msg in self._ws:
                if isinstance(msg, str):
                    logger.debug(f"[ASR] text frame: {msg[:200]}")
                    continue
                parsed = _parse_response(msg)
                await self._handle_parsed(parsed)
        except websockets.ConnectionClosed as e:
            logger.info(f"[ASR] connection closed: {e.code} {e.reason}")
        except Exception as e:
            logger.error(f"[ASR] recv loop error: {e}", exc_info=True)
        finally:
            self._closed = True

    async def _handle_parsed(self, parsed: dict):
        if "_error_code" in parsed:
            logger.error(f"[ASR] server error {parsed['_error_code']}: {parsed.get('_error_msg')}")
            return
        payload = parsed.get("payload")
        if not payload:
            return

        # 豆包返回格式：{"result": {"text": "...", "utterances": [{"text":"...", "definite": true}]}}
        result = payload.get("result") or {}
        text = result.get("text") or ""
        utterances = result.get("utterances") or []

        # 判断是否是"最终"片段
        is_final = False
        final_text = ""
        if utterances:
            for utt in utterances:
                if utt.get("definite"):
                    is_final = True
                    final_text += utt.get("text", "")

        if is_final and final_text:
            if self.on_final:
                await self._safe_call(self.on_final, final_text)
        elif text:
            if self.on_partial:
                await self._safe_call(self.on_partial, text)

    @staticmethod
    async def _safe_call(cb, *args):
        try:
            r = cb(*args)
            if asyncio.iscoroutine(r):
                await r
        except Exception as e:
            logger.error(f"[ASR] callback error: {e}", exc_info=True)

    async def send_audio(self, pcm: bytes, is_last: bool = False):
        if self._closed or not self._ws:
            return
        frame = _build_audio_frame(pcm, self._seq, is_last)
        self._seq += 1
        try:
            await self._ws.send(frame)
        except websockets.ConnectionClosed:
            self._closed = True

    async def finish(self):
        """发送空的 last 帧标记音频结束"""
        if self._closed or not self._ws:
            return
        try:
            await self.send_audio(b"", is_last=True)
        except Exception:
            pass

    async def close(self):
        self._closed = True
        if self._recv_task and not self._recv_task.done():
            self._recv_task.cancel()
            try:
                await self._recv_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
