from __future__ import annotations

import os
from typing import Optional

import edge_tts
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate
from openai import AsyncOpenAI

from .chant import detect_chandas, normalize_verse, split_syllables, to_iast


_RAGA_TTS_PRESETS = {
    "shanti": {
        "edge_rate": "-18%",
        "edge_pitch": "+0Hz",
        "instruction_tone": "calm, serene, and balanced",
    },
    "meditative": {
        "edge_rate": "-22%",
        "edge_pitch": "-8Hz",
        "instruction_tone": "deeply meditative, soft, and contemplative",
    },
    "devotional": {
        "edge_rate": "-14%",
        "edge_pitch": "+10Hz",
        "instruction_tone": "devotional, uplifting, and expressive",
    },
}


def _looks_devanagari(text: str) -> bool:
    return any("\u0900" <= ch <= "\u097F" for ch in text)


def _to_devanagari_if_needed(text: str, prefer_devanagari: bool) -> str:
    normalized = normalize_verse(text)
    if not prefer_devanagari:
        return normalized
    if _looks_devanagari(normalized):
        return normalized
    return transliterate(normalized, sanscript.IAST, sanscript.DEVANAGARI)


def _build_chant_text(text: str, prefer_devanagari: bool) -> str:
    syllables = split_syllables(text)
    if not syllables:
        return _to_devanagari_if_needed(text, prefer_devanagari)

    _, counts = detect_chandas(text)
    break_indices: set[int] = set()
    running = 0
    for c in counts[:-1]:
        running += c
        break_indices.add(running)

    if prefer_devanagari:
        tokens = [transliterate(s.text, sanscript.IAST, sanscript.DEVANAGARI) for s in syllables]
    else:
        tokens = [s.text for s in syllables]

    out: list[str] = []
    for idx, token in enumerate(tokens, start=1):
        out.append(token)
        if idx in break_indices:
            out.append(" । ")
        else:
            out.append(" ")

    final_text = "".join(out).strip()
    if not final_text.endswith("॥"):
        final_text = f"{final_text} ॥"
    return final_text


async def synthesize_tts_mp3(
    text: str,
    *,
    voice: str = "hi-IN-MadhurNeural",
    rate: str = "+0%",
    pitch: str = "+0Hz",
    prefer_devanagari: bool = True,
) -> bytes:
    spoken_text = _to_devanagari_if_needed(text, prefer_devanagari)
    communicate = edge_tts.Communicate(spoken_text, voice=voice, rate=rate, pitch=pitch)

    chunks: list[bytes] = []
    async for event in communicate.stream():
        if event.get("type") == "audio":
            audio_chunk: Optional[bytes] = event.get("data")
            if audio_chunk:
                chunks.append(audio_chunk)

    return b"".join(chunks)


async def synthesize_tts_audio(
    text: str,
    *,
    provider: str = "edge",
    voice: str = "hi-IN-MadhurNeural",
    rate: str = "+0%",
    pitch: str = "+0Hz",
    raga: str = "shanti",
    model: str = "gpt-4o-mini-tts",
    audio_format: str = "mp3",
    prefer_devanagari: bool = True,
    chant_mode: bool = True,
) -> tuple[bytes, str, str]:
    spoken_text = _build_chant_text(text, prefer_devanagari) if chant_mode else _to_devanagari_if_needed(text, prefer_devanagari)
    preset = _RAGA_TTS_PRESETS.get(raga, _RAGA_TTS_PRESETS["shanti"])

    if provider == "edge":
        edge_rate = rate
        edge_pitch = pitch
        if chant_mode and rate == "+0%":
            edge_rate = preset["edge_rate"]
        if chant_mode and pitch == "+0Hz":
            edge_pitch = preset["edge_pitch"]

        mp3 = await synthesize_tts_mp3(
            spoken_text,
            voice=voice,
            rate=edge_rate,
            pitch=edge_pitch,
            prefer_devanagari=False,
        )
        return mp3, "audio/mpeg", "tts-edge.mp3"

    if provider == "openai":
        allow_fallback = os.getenv("OPENAI_FALLBACK_TO_EDGE", "1") != "0"

        normalized_voice = voice
        if normalized_voice.startswith("hi-IN-") or normalized_voice.endswith("Neural"):
            normalized_voice = "shimmer" if "swara" in normalized_voice.lower() else "alloy"

        if not os.getenv("OPENAI_API_KEY"):
            if allow_fallback:
                mp3 = await synthesize_tts_mp3(
                    spoken_text,
                    voice="hi-IN-MadhurNeural",
                    rate=preset["edge_rate"],
                    pitch=preset["edge_pitch"],
                    prefer_devanagari=False,
                )
                return mp3, "audio/mpeg", "tts-edge-fallback.mp3"
            raise RuntimeError("OPENAI_API_KEY is not set")

        client = AsyncOpenAI()
        try:
            try:
                response = await client.audio.speech.create(
                    model=model,
                    voice=normalized_voice,
                    input=spoken_text,
                    format=audio_format,
                    instructions=(
                        "Recite in steady Sanskrit mantra pathana style, clear akshara boundaries, "
                        "with respectful pauses at danda marks, and keep a "
                        f"{preset['instruction_tone']} delivery reflecting {raga} raga mood."
                        if chant_mode
                        else "Natural speech pronunciation."
                    ),
                )
            except TypeError:
                response = await client.audio.speech.create(
                    model=model,
                    voice=normalized_voice,
                    input=spoken_text,
                    response_format=audio_format,
                )
        except Exception:
            if allow_fallback:
                mp3 = await synthesize_tts_mp3(
                    spoken_text,
                    voice="hi-IN-MadhurNeural",
                    rate=preset["edge_rate"],
                    pitch=preset["edge_pitch"],
                    prefer_devanagari=False,
                )
                return mp3, "audio/mpeg", "tts-edge-fallback.mp3"
            raise

        data = bytes(response.content)
        mime = {
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
            "opus": "audio/opus",
            "flac": "audio/flac",
            "pcm": "audio/L16",
        }.get(audio_format, "application/octet-stream")
        filename = f"tts-openai.{audio_format}"
        return data, mime, filename

    raise RuntimeError(f"Unsupported TTS provider: {provider}")
