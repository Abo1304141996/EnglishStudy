"""
测试 TTS 流式传输（模拟 OpenAITTSClient.stream_speech 的真实调用路径）。

测试项：
1. 英文短句流式 TTS
2. 中文短句流式 TTS
3. 不同 voice 测试
4. 空文本边界
5. 验证生成的 MP3 格式

用法：python scripts/test_tts_stream.py
"""
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.voice.tts_openai import OpenAITTSClient
from app.config import settings

OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)

# MP3 格式检测
def detect_format(b: bytes) -> str:
    if b.startswith(b"ID3"):
        return "MP3 (ID3v2)"
    if len(b) >= 2 and b[0] == 0xFF and (b[1] & 0xE0) == 0xE0:
        return "MP3 (raw frame)"
    if b.startswith(b"RIFF") and b[8:12] == b"WAVE":
        return "WAV"
    if b.startswith(b"OggS"):
        return "OGG/Opus"
    if b.startswith(b"fLaC"):
        return "FLAC"
    if len(b) >= 12 and b[4:8] == b"ftyp":
        return "MP4/M4A/AAC"
    if b[:1] in (b"{", b"["):
        return "JSON (error?)"
    return "Unknown"


def is_valid_mp3(data: bytes) -> bool:
    fmt = detect_format(data)
    return "MP3" in fmt


results = []


async def test_stream(
    client: OpenAITTSClient,
    name: str,
    text: str,
    voice: str = None,
    expect_empty: bool = False,
):
    """跑一次流式 TTS 并收集结果"""
    out_path = OUT_DIR / f"stream_{name}.mp3"
    print(f"\n{'='*50}")
    print(f"[TEST] {name}")
    print(f"  text  = {text!r}")
    print(f"  voice = {voice or client.voice}")

    chunks = []
    chunk_count = 0
    t0 = time.perf_counter()
    first_chunk_time = None

    try:
        async for chunk in client.stream_speech(text, voice=voice):
            if first_chunk_time is None:
                first_chunk_time = time.perf_counter() - t0
            chunks.append(chunk)
            chunk_count += 1
    except Exception as e:
        elapsed = time.perf_counter() - t0
        print(f"  [FAIL] 异常: {e} ({elapsed:.2f}s)")
        results.append((name, "FAIL", f"Exception: {e}"))
        return

    elapsed = time.perf_counter() - t0
    data = b"".join(chunks)

    if expect_empty:
        if len(data) == 0:
            print(f"  [OK] 预期为空，实际为空")
            results.append((name, "OK", "empty as expected"))
        else:
            print(f"  [WARN] 预期为空但收到 {len(data)} bytes")
            results.append((name, "WARN", f"expected empty, got {len(data)} bytes"))
        return

    if len(data) == 0:
        print(f"  [FAIL] 无数据返回 ({elapsed:.2f}s)")
        results.append((name, "FAIL", "no data"))
        return

    fmt = detect_format(data)
    valid = is_valid_mp3(data)
    out_path.write_bytes(data)

    print(f"  chunks    = {chunk_count}")
    print(f"  total     = {len(data)} bytes")
    print(f"  first_chunk = {first_chunk_time:.2f}s")
    print(f"  elapsed   = {elapsed:.2f}s")
    print(f"  format    = {fmt}")
    print(f"  saved     = {out_path}")

    if valid:
        print(f"  [OK] 有效 MP3")
        results.append((name, "OK", f"{len(data)} bytes, {chunk_count} chunks, {elapsed:.2f}s"))
    else:
        print(f"  [FAIL] 格式异常: {fmt}")
        # 打印前 200 字节帮助调试
        print(f"  head hex: {data[:64].hex()}")
        if fmt == "JSON (error?)":
            try:
                print(f"  body: {data[:500].decode()}")
            except:
                pass
        results.append((name, "FAIL", f"bad format: {fmt}"))


async def test_cancel(client: OpenAITTSClient):
    """测试 cancel_event 能否正常中断流"""
    name = "cancel_interrupt"
    print(f"\n{'='*50}")
    print(f"[TEST] {name} - 测试中断机制")

    cancel = asyncio.Event()
    chunks = []
    t0 = time.perf_counter()

    text = "This is a longer sentence to test the cancellation mechanism during streaming TTS playback."

    async for chunk in client.stream_speech(text, cancel_event=cancel):
        chunks.append(chunk)
        # 收到第一个 chunk 后立即取消
        if len(chunks) == 1:
            cancel.set()
            print(f"  已在第 1 个 chunk 后触发 cancel")

    elapsed = time.perf_counter() - t0
    total = sum(len(c) for c in chunks)
    # 由于取消时可能还有 1-2 个 chunk 在途，允许 <=3
    print(f"  收到 {len(chunks)} 个 chunk, {total} bytes, {elapsed:.2f}s")

    if len(chunks) <= 3:
        print(f"  [OK] 中断有效")
        results.append((name, "OK", f"{len(chunks)} chunks after cancel"))
    else:
        print(f"  [WARN] 中断后仍收到较多 chunk ({len(chunks)})")
        results.append((name, "WARN", f"{len(chunks)} chunks after cancel"))


async def main():
    print("=" * 50)
    print("TTS 流式测试套件")
    print(f"base_url = {settings.openai_base_url}")
    print(f"model    = {settings.tts_model}")
    print(f"voice    = {settings.tts_voice}")
    print("=" * 50)

    if not settings.openai_api_key:
        print("[ERROR] OPENAI_API_KEY 未配置")
        sys.exit(1)

    client = OpenAITTSClient()

    # --- Test 1: 英文短句 ---
    await test_stream(
        client,
        "english_short",
        "Hello! How are you today? Let's practice English together.",
    )

    # --- Test 2: 中文短句 ---
    await test_stream(
        client,
        "chinese_short",
        "你好！欢迎来到英语学习课堂，我是你的AI老师。",
    )

    # --- Test 3: 不同 voice ---
    await test_stream(
        client,
        "voice_nova",
        "Good morning! Ready for today's lesson?",
        voice="nova",
    )

    # --- Test 4: 长句（模拟 LLM 输出） ---
    await test_stream(
        client,
        "long_sentence",
        "That's a great question! The word 'opportunity' is commonly used in business contexts. "
        "For example, you might say 'This is a great opportunity to learn new skills.' "
        "Would you like me to give you more examples with this word?",
    )

    # --- Test 5: 中断测试 ---
    await test_cancel(client)

    # --- 汇总 ---
    print(f"\n{'='*50}")
    print("汇总结果:")
    print(f"{'='*50}")
    ok, fail, warn = 0, 0, 0
    for name, status, detail in results:
        icon = "[OK]" if status == "OK" else ("[FAIL]" if status == "FAIL" else "[WARN]")
        print(f"  {icon} {name}: {status} - {detail}")
        if status == "OK":
            ok += 1
        elif status == "FAIL":
            fail += 1
        else:
            warn += 1

    print(f"\n  通过: {ok}  失败: {fail}  警告: {warn}")
    print(f"  输出目录: {OUT_DIR}")

    if fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
