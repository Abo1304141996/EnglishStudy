"""
对比测试：stream=True vs stream=False（非流式） 
验证第三方代理对流式 TTS 的支持情况。
"""
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx
from app.config import settings

OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)

TEXTS = {
    "short": "Hello, how are you?",
    "medium": "Hello! How are you today? Let's practice English together.",
    "long": (
        "That is a great question! The word opportunity is commonly used in business contexts. "
        "For example, you might say This is a great opportunity to learn new skills. "
        "Would you like me to give you more examples with this word?"
    ),
}


async def test_request(label: str, text: str, stream: bool, timeout: float = 30.0):
    url = f"{settings.openai_base_url.rstrip('/')}/audio/speech"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.tts_model,
        "voice": settings.tts_voice,
        "input": text,
        "response_format": "mp3",
        "stream": stream,
    }
    mode = "stream" if stream else "non-stream"
    print(f"\n[{label}] {mode}, text_len={len(text)}")

    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0)) as client:
            if stream:
                data = bytearray()
                first_chunk = None
                chunk_count = 0
                async with client.stream("POST", url, headers=headers, json=body) as resp:
                    if resp.status_code != 200:
                        err = await resp.aread()
                        print(f"  HTTP {resp.status_code}: {err[:300]}")
                        return False
                    async for chunk in resp.aiter_bytes(chunk_size=4096):
                        if chunk:
                            if first_chunk is None:
                                first_chunk = time.perf_counter() - t0
                            data.extend(chunk)
                            chunk_count += 1
                elapsed = time.perf_counter() - t0
                out_path = OUT_DIR / f"cmp_{label}_stream.mp3"
                out_path.write_bytes(bytes(data))
                print(f"  OK: {len(data)} bytes, {chunk_count} chunks, "
                      f"first_chunk={first_chunk:.2f}s, total={elapsed:.2f}s -> {out_path.name}")
                return True
            else:
                resp = await client.post(url, headers=headers, json=body)
                elapsed = time.perf_counter() - t0
                if resp.status_code != 200:
                    print(f"  HTTP {resp.status_code}: {resp.text[:300]}")
                    return False
                out_path = OUT_DIR / f"cmp_{label}_nonstream.mp3"
                out_path.write_bytes(resp.content)
                print(f"  OK: {len(resp.content)} bytes, total={elapsed:.2f}s -> {out_path.name}")
                return True
    except httpx.ReadTimeout:
        elapsed = time.perf_counter() - t0
        print(f"  TIMEOUT after {elapsed:.2f}s")
        return False
    except Exception as e:
        elapsed = time.perf_counter() - t0
        print(f"  ERROR: {e} ({elapsed:.2f}s)")
        return False


async def main():
    print("=" * 60)
    print("TTS 流式 vs 非流式 对比测试")
    print(f"base_url = {settings.openai_base_url}")
    print(f"model    = {settings.tts_model}")
    print("=" * 60)

    results = []
    for name, text in TEXTS.items():
        # 非流式
        ok1 = await test_request(name, text, stream=False)
        results.append((f"{name}_nonstream", ok1))
        
        # 流式
        ok2 = await test_request(name, text, stream=True, timeout=30.0)
        results.append((f"{name}_stream", ok2))

    print(f"\n{'='*60}")
    print("汇总:")
    for name, ok in results:
        print(f"  {'[OK]' if ok else '[FAIL]'} {name}")


if __name__ == "__main__":
    asyncio.run(main())
