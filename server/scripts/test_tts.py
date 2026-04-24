"""
独立 TTS 测试脚本
用法（在 server 目录下）：

    python scripts/test_tts.py
    python scripts/test_tts.py --text "Hello there, how are you?"
    python scripts/test_tts.py --voice alloy --out out.mp3
    python scripts/test_tts.py --endpoint speech      # 标准 /v1/audio/speech
    python scripts/test_tts.py --endpoint chat        # /v1/chat/completions 兼容写法
    python scripts/test_tts.py --endpoint both        # 两种都试

会把音频保存到 server/scripts/out/*.mp3。
"""
import argparse
import asyncio
import base64
import json
import sys
import time
from pathlib import Path

# 允许从 server 根目录直接 `python scripts/test_tts.py` 运行
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx
from app.config import settings  # noqa: E402


DEFAULT_TEXT = (
    "Hi there! I'm your English speaking partner today. "
    "How are you doing? Let's start whenever you're ready."
)

OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)


def _check_config():
    missing = []
    if not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    if not settings.openai_base_url:
        missing.append("OPENAI_BASE_URL")
    if missing:
        print(f"[ERROR] 缺失配置：{missing}. 请检查 server/.env")
        sys.exit(1)
    print(f"[INFO] base_url = {settings.openai_base_url}")
    print(f"[INFO] model    = {settings.tts_model}")
    print(f"[INFO] voice    = {settings.tts_voice}")


async def try_speech_endpoint(text: str, voice: str, out_path: Path, fmt: str = "mp3") -> bool:
    """标准 /v1/audio/speech 端点（OpenAI 官方规范）"""
    url = f"{settings.openai_base_url.rstrip('/')}/audio/speech"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.tts_model,
        "voice": voice,
        "input": text,
        "response_format": fmt,
    }
    print(f"\n[TEST] POST {url}")
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=body)
            elapsed = time.perf_counter() - t0
            print(f"[TEST] status={resp.status_code}, elapsed={elapsed:.2f}s, "
                  f"bytes={len(resp.content)}, content-type={resp.headers.get('content-type')}")
            if resp.status_code != 200:
                print(f"[TEST] body: {resp.text[:800]}")
                return False
            ct = resp.headers.get("content-type", "")
            data = resp.content
            # 有些代理会返回 json { data: base64 } 而不是 raw
            if "application/json" in ct:
                try:
                    j = resp.json()
                    b64 = j.get("data") or (j.get("audio") if isinstance(j.get("audio"), str) else None)
                    if b64:
                        data = base64.b64decode(b64)
                        print("[TEST] 从 JSON.data 解出 base64 音频")
                    else:
                        print(f"[TEST] JSON 响应但无 data 字段: {str(j)[:400]}")
                        return False
                except Exception as e:
                    print(f"[TEST] 解析 JSON 失败: {e}; body head: {resp.text[:400]}")
                    return False
            out_path.write_bytes(data)
            print(f"[OK] 已写入 {out_path} ({len(data)} bytes)")
            return True
    except Exception as e:
        print(f"[TEST] 异常: {e}")
        return False


async def try_chat_endpoint(text: str, voice: str, out_path: Path) -> bool:
    """兼容方式：通过 chat/completions + audio modalities 合成（图中代理面板显示的端点）"""
    url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.tts_model,
        "modalities": ["text", "audio"],
        "audio": {"voice": voice, "format": "mp3"},
        "messages": [{"role": "user", "content": text}],
    }
    print(f"\n[TEST] POST {url}")
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=body)
            elapsed = time.perf_counter() - t0
            print(f"[TEST] status={resp.status_code}, elapsed={elapsed:.2f}s, "
                  f"content-type={resp.headers.get('content-type')}")
            if resp.status_code != 200:
                print(f"[TEST] body: {resp.text[:800]}")
                return False
            data = resp.json()
            # OpenAI audio output 规范: choices[0].message.audio.data (base64)
            try:
                audio = data["choices"][0]["message"]["audio"]
                b64 = audio.get("data")
                if not b64:
                    print(f"[TEST] 响应里找不到 audio.data: {json.dumps(data)[:600]}")
                    return False
                mp3 = base64.b64decode(b64)
                out_path.write_bytes(mp3)
                print(f"[OK] 已写入 {out_path} ({len(mp3)} bytes)")
                return True
            except Exception as e:
                print(f"[TEST] 解析响应失败: {e}")
                print(f"[TEST] body head: {json.dumps(data)[:600]}")
                return False
    except Exception as e:
        print(f"[TEST] 异常: {e}")
        return False


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default=DEFAULT_TEXT)
    ap.add_argument("--voice", default=settings.tts_voice or "alloy")
    ap.add_argument("--endpoint", choices=["speech", "chat", "both"], default="both")
    ap.add_argument("--format", default="mp3", choices=["mp3", "wav", "opus", "aac", "flac", "pcm"],
                    help="response_format（wav 兼容性最好，mp3 文件最小）")
    ap.add_argument("--out", default=None, help="输出文件名（默认 out/tts_<endpoint>.<fmt>）")
    args = ap.parse_args()

    _check_config()

    tasks = []
    results = {}

    if args.endpoint in ("speech", "both"):
        out = Path(args.out) if (args.out and args.endpoint == "speech") else OUT_DIR / f"tts_speech.{args.format}"
        results["speech"] = await try_speech_endpoint(args.text, args.voice, out, args.format)

    if args.endpoint in ("chat", "both"):
        out = Path(args.out) if (args.out and args.endpoint == "chat") else OUT_DIR / "tts_chat.mp3"
        results["chat"] = await try_chat_endpoint(args.text, args.voice, out)

    print("\n==== 汇总 ====")
    for name, ok in results.items():
        print(f"  {name}: {'OK' if ok else 'FAIL'}")
    if any(results.values()):
        print(f"\n生成的 mp3 在：{OUT_DIR}")
    else:
        print("\n全部失败，检查上面的错误日志。")


if __name__ == "__main__":
    asyncio.run(main())
