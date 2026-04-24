"""
检查 TTS 返回的音频文件真实格式。
用法：python scripts/inspect_mp3.py [path]
"""
import sys
from pathlib import Path

p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "out" / "tts_speech.mp3"
b = p.read_bytes()
head = b[:64]

print(f"Path: {p}")
print(f"Size: {len(b)} bytes")
print(f"Hex head (64): {head.hex()}")
print(f"ASCII head: {head!r}")

# 识别常见格式 magic
def detect(b: bytes) -> str:
    if b.startswith(b"ID3"):
        return "MP3 (with ID3v2 tag)"
    if len(b) >= 2 and b[0] == 0xFF and (b[1] & 0xE0) == 0xE0:
        return "MP3 (raw frame sync)"
    if b.startswith(b"RIFF") and b[8:12] == b"WAVE":
        return "WAV"
    if b.startswith(b"OggS"):
        return "OGG / Opus"
    if b.startswith(b"fLaC"):
        return "FLAC"
    if len(b) >= 12 and b[4:8] == b"ftyp":
        return "MP4 / M4A / AAC (ISO BMFF)"
    if b.startswith(b"\xff\xf1") or b.startswith(b"\xff\xf9"):
        return "AAC (ADTS)"
    if b[:1] == b"{" or b[:1] == b"[":
        return "Looks like JSON"
    return "Unknown / likely raw PCM"

print(f"Detected: {detect(b)}")

# 如果看起来像 raw PCM，再做一次尝试：保存成 wav 再播
if detect(b).startswith("Unknown") or detect(b).startswith("Looks"):
    print("\n[Hint] 前 1KB 是否可读为文本（便于看是不是 JSON 错误）:")
    try:
        print(b[:1024].decode("utf-8", errors="replace"))
    except Exception as e:
        print(f"decode error: {e}")
