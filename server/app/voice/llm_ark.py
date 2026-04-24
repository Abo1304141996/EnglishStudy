"""
豆包 LLM（通过 arkitect 框架）流式对话。
按句切分输出，以便 TTS 可以边合成边播。
"""
import asyncio
import logging
import os
import re
from typing import AsyncIterator, List, Dict, Optional

from app.config import settings
from app.voice.prompts import ENGLISH_TUTOR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# arkitect 需要 ARK_API_KEY 环境变量
if settings.ark_api_key:
    os.environ.setdefault("ARK_API_KEY", settings.ark_api_key)


_SENTENCE_END = re.compile(r"[\.!\?。！？\n]")


def _split_into_sentences(buffer: str) -> tuple[List[str], str]:
    """
    把 buffer 切成"完整句子列表 + 剩余不完整片段"。
    完整句子包含结尾标点。
    """
    sentences: List[str] = []
    last = 0
    for m in _SENTENCE_END.finditer(buffer):
        end = m.end()
        piece = buffer[last:end].strip()
        if piece:
            sentences.append(piece)
        last = end
    remainder = buffer[last:]
    return sentences, remainder


class ArkLLMClient:
    """豆包 LLM 客户端（流式）"""

    def __init__(self):
        self.endpoint = settings.ark_llm_endpoint
        if not (settings.ark_api_key and self.endpoint):
            logger.warning("ARK LLM 未配置：ARK_API_KEY / ARK_LLM_ENDPOINT 缺失")

    async def stream_reply(
        self,
        history: List[Dict[str, str]],
        user_text: str,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> AsyncIterator[Dict[str, str]]:
        """
        流式产出：
          {"type": "delta", "text": "..."}
          {"type": "sentence", "text": "完整句子"}
          {"type": "done", "text": "完整回复"}
        cancel_event 用于外部打断。
        """
        if not (settings.ark_api_key and self.endpoint):
            yield {"type": "delta", "text": "[LLM 未配置]"}
            yield {"type": "sentence", "text": "[LLM not configured]"}
            yield {"type": "done", "text": "[LLM not configured]"}
            return

        # 延迟导入，避免未安装时启动失败
        try:
            from arkitect.core.component.context.context import Context
            from arkitect.types.llm.model import ArkChatParameters
        except ImportError as e:
            logger.error(f"arkitect 未安装: {e}")
            yield {"type": "done", "text": "[arkitect not installed]"}
            return

        ctx = Context(
            model=self.endpoint,
            parameters=ArkChatParameters(
                temperature=0.7,
                max_tokens=400,
            ),
        )
        await ctx.init()

        messages = [{"role": "system", "content": ENGLISH_TUTOR_SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})

        buffer = ""
        full_text = ""

        try:
            stream = await ctx.completions.create(messages=messages, stream=True)
            async for chunk in stream:
                if cancel_event and cancel_event.is_set():
                    logger.info("[LLM] cancelled by upstream")
                    break

                # arkitect 的 chunk 结构与 OpenAI 兼容
                delta = None
                try:
                    choice = chunk.choices[0]
                    delta = getattr(choice, "delta", None)
                    content = getattr(delta, "content", None) if delta else None
                except Exception:
                    content = None

                if not content:
                    continue

                full_text += content
                buffer += content
                yield {"type": "delta", "text": content}

                sentences, remainder = _split_into_sentences(buffer)
                for s in sentences:
                    yield {"type": "sentence", "text": s}
                buffer = remainder
        except Exception as e:
            logger.error(f"[LLM] stream error: {e}", exc_info=True)
        finally:
            # flush 剩余不完整片段（如果模型没以标点结尾）
            tail = buffer.strip()
            if tail:
                yield {"type": "sentence", "text": tail}
            yield {"type": "done", "text": full_text}
