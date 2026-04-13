import asyncio
import os
import subprocess
import tempfile
from pydub import AudioSegment
from pydub.silence import split_on_silence

WHISPER_BIN = "/home/zoe_ai/whisper.cpp/build/bin/whisper-cli"
WHISPER_MODEL = "/home/zoe_ai/whisper.cpp/models/ggml-medium.bin"

def _to_wav(audio: AudioSegment) -> str:
    """轉成 whisper 需要的 16kHz mono WAV，回傳 tmp 路徑"""
    audio = audio.set_frame_rate(16000).set_channels(1)
    f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    audio.export(f.name, format="wav")
    return f.name

def _whisper(wav_path: str) -> str:
    """呼叫 whisper-cli，回傳轉錄文字"""
    result = subprocess.run(
        [WHISPER_BIN, "-m", WHISPER_MODEL, "-f", wav_path,
         "-l", "auto", "--output-txt", "-nt", "--no-prints"],
        capture_output=True, text=True, timeout=120
    )
    txt_path = wav_path + ".txt"
    if os.path.exists(txt_path):
        text = open(txt_path).read().strip()
        os.unlink(txt_path)
        return text
    return result.stdout.strip()

def _split_audio(audio: AudioSegment) -> list[AudioSegment]:
    """靜音偵測切段，fallback 固定 30 秒"""
    chunks = split_on_silence(
        audio, min_silence_len=800, silence_thresh=-40, keep_silence=300
    )
    if not chunks:
        # fallback: 固定 30 秒切
        ms = 30_000
        chunks = [audio[i:i+ms] for i in range(0, len(audio), ms)]
    # 合併太短的片段（<3秒）
    merged, buf = [], AudioSegment.empty()
    for c in chunks:
        buf += c
        if len(buf) >= 3_000:
            merged.append(buf)
            buf = AudioSegment.empty()
    if len(buf) > 500:
        merged.append(buf)
    return merged or [audio]

def transcribe_bytes(content: bytes, ext: str) -> str:
    """音訊 bytes → 全文字串（同步，給 asyncio.to_thread 用）"""
    fmt = ext.lower().strip(".")
    if fmt == "m4a":
        fmt = "mp4"
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as f:
        f.write(content)
        src_path = f.name
    try:
        audio = AudioSegment.from_file(src_path, format=fmt)
    finally:
        os.unlink(src_path)

    chunks = _split_audio(audio)
    texts = []
    for chunk in chunks:
        wav = _to_wav(chunk)
        try:
            texts.append(_whisper(wav))
        finally:
            os.unlink(wav)
    return "\n".join(t for t in texts if t)

def transcribe_wav_bytes(wav_bytes: bytes) -> str:
    """給 WebSocket live 用：WAV bytes → 文字"""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_bytes)
        wav_path = f.name
    try:
        return _whisper(wav_path)
    finally:
        os.unlink(wav_path)

async def transcribe_async(content: bytes, ext: str) -> str:
    return await asyncio.to_thread(transcribe_bytes, content, ext)

async def transcribe_wav_async(wav_bytes: bytes) -> str:
    return await asyncio.to_thread(transcribe_wav_bytes, wav_bytes)
