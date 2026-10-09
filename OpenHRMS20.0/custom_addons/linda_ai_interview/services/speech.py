"""Speech adapters: speech-to-text (Whisper) and text-to-speech (Kokoro).

Both self-hosted engines are reached over their OpenAI-compatible HTTP APIs
(e.g. faster-whisper-server / speaches for ``/v1/audio/transcriptions`` and
Kokoro-FastAPI for ``/v1/audio/speech``). Audio never leaves our servers.
"""
import io
import math
import struct
import time
import wave

import requests


# Domain words Whisper otherwise mishears (e.g. "Odoo" -> "Odu"); sent as the transcription prompt.
VOCABULARY_HINT = ("Interview for an Odoo developer role at Cybrosys. Terms: Odoo, Cybrosys, Python, "
                   "JavaScript, PostgreSQL, ORM, XML, QWeb, OWL, API, GitHub.")


class SpeechError(Exception):
    pass


def _headers(config):
    return {"Authorization": f"Bearer {config['api_key']}"} if config.get("api_key") else {}


def transcribe(config, audio_bytes, filename="answer.webm", mimetype="audio/webm"):
    """Return dict(text, segments, duration, latency_ms)."""
    kind = config.get("kind") or "mock"
    started = time.time()
    if kind == "mock":
        return {"text": "Hello, my name is the candidate. I studied computer science and I enjoy building "
                        "web applications with Python.", "segments": [], "duration": 0,
                "latency_ms": int((time.time() - started) * 1000)}
    if kind != "whisper":
        raise SpeechError(f"Unsupported STT provider '{kind}'")
    url = (config.get("base_url") or "http://localhost:8000/v1").rstrip("/") + "/audio/transcriptions"
    data = {"model": config.get("model") or "Systran/faster-whisper-small", "language": "en",
            "response_format": "verbose_json", "prompt": VOCABULARY_HINT}
    try:
        resp = requests.post(url, headers=_headers(config), data=data,
                             files={"file": (filename, io.BytesIO(audio_bytes), mimetype)},
                             timeout=config.get("timeout") or 120)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise SpeechError(f"Transcription failed: {exc}") from exc
    body = resp.json()
    return {"text": (body.get("text") or "").strip(), "segments": body.get("segments") or [],
            "duration": body.get("duration") or 0, "latency_ms": int((time.time() - started) * 1000)}


def _mock_wav(text):
    """A short, quiet tone so the browser audio pipeline can be exercised offline."""
    rate, seconds = 16000, min(2.0, 0.3 + len(text) / 80.0)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        frames = b"".join(struct.pack("<h", int(800 * math.sin(2 * math.pi * 440 * i / rate)))
                          for i in range(int(rate * seconds)))
        wav.writeframes(frames)
    return buf.getvalue()


def synthesize(config, text, voice=None):
    """Return (audio_bytes, mimetype)."""
    kind = config.get("kind") or "mock"
    if kind == "mock":
        return _mock_wav(text), "audio/wav"
    if kind != "kokoro":
        raise SpeechError(f"Unsupported TTS provider '{kind}'")
    url = (config.get("base_url") or "http://localhost:8880/v1").rstrip("/") + "/audio/speech"
    payload = {"model": config.get("model") or "kokoro", "input": text,
               "voice": voice or config.get("voice") or "af_heart", "response_format": "mp3"}
    try:
        resp = requests.post(url, headers=_headers(config), json=payload, timeout=config.get("timeout") or 60)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise SpeechError(f"Speech synthesis failed: {exc}") from exc
    mimetype = (resp.headers.get("Content-Type") or "audio/mpeg").split(";")[0].strip()
    return resp.content, mimetype if mimetype.startswith("audio/") else "audio/mpeg"
