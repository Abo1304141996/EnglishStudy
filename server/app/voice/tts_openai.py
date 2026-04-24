"""
OpenAI 兼容 TTS 客户端（gpt-4o-mini-tts，流式）。
通过第三方代理 https://cn.gptapi.asia/v1/audio/speech。
返回 MP3 字节流（chunked）。
"""
import asyncio
import logging
from typing import AsyncIterator, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class OpenAITTSClient:
    """流式 TTS"""

    def __init__(self):
        self.base_url = settings.openai_base_url.rstrip("/")
        self.api_key = settings.openai_api_key
        self.model = settings.tts_model
        self.voice = settings.tts_voice
        self.fmt = settings.tts_format  # mp3
        if not self.api_key:
            logger.warning("OpenAI TTS 未配置：OPENAI_API_KEY 缺失")

    async def stream_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        cancel_event: Optional[asyncio.Event] = None,
        instructions: Optional[str] = None,
    ) -> AsyncIterator[bytes]:
        """
        流式合成：逐块产出 MP3 bytes。
        cancel_event 触发即中断下载。
        """
        if not self.api_key:
            return

        url = f"{self.base_url}/audio/speech"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "voice": voice or self.voice,
            "input": text,
            "response_format": self.fmt,
            "stream": True,
        }
        if instructions:
            body["instructions"] = instructions

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                async with client.stream("POST", url, headers=headers, json=body) as resp:
                    if resp.status_code != 200:
                        err = await resp.aread()
                        logger.error(f"[TTS] HTTP {resp.status_code}: {err[:500]}")
                        return
                    async for chunk in resp.aiter_bytes(chunk_size=4096):
                        if cancel_event and cancel_event.is_set():
                            logger.info("[TTS] cancelled")
                            return
                        if chunk:
                            yield chunk
        except httpx.HTTPError as e:
            logger.error(f"[TTS] http error: {e}")
        except Exception as e:
            logger.error(f"[TTS] stream error: {e}", exc_info=True)
