"""
语音交互 WebSocket 路由
"""
import logging

from fastapi import APIRouter, WebSocket

from app.voice.session import VoiceSession

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/voice")
async def voice_ws(ws: WebSocket):
    """
    前端协议（统一通过同一个 WS）：

    客户端 -> 服务端:
      - binary: 16kHz / 16bit / mono PCM 音频帧
      - text JSON:
          {"type": "mute"}           暂停上行 ASR
          {"type": "unmute"}         恢复上行 ASR
          {"type": "interrupt"}      立即打断 AI
          {"type": "reset"}          清空对话历史
          {"type": "ping"}           心跳

    服务端 -> 客户端:
      - text JSON:
          {"type": "session.ready"}
          {"type": "asr.partial", "text"}
          {"type": "asr.final", "text"}
          {"type": "turn.start", "seq", "user_text"}
          {"type": "llm.delta", "seq", "text"}
          {"type": "tts.begin", "seq", "text"}   # 每句开始
          {"type": "tts.end",   "seq"}           # 每句结束
          {"type": "tts.flush"}                  # 打断通知，清空播放 buffer
          {"type": "turn.end", "seq", "text"}
          {"type": "turn.cancelled", "seq"}
          {"type": "pong"}
          {"type": "error", "code", "message"}
      - binary: 当前句子的 MP3 音频 chunk（依 tts.begin/end 包围）
    """
    await ws.accept()
    logger.info("[Voice WS] connected")
    session = VoiceSession(ws)
    try:
        await session.run()
    except Exception as e:
        logger.error(f"[Voice WS] unexpected error: {e}", exc_info=True)
    finally:
        logger.info("[Voice WS] closed")
