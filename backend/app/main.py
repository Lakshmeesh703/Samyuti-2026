from __future__ import annotations

import os

from fastapi import File, Form, HTTPException, UploadFile
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from dotenv import load_dotenv

from .audio import ChantEvent, SynthConfig, synthesize_wav
from .chant import detect_chandas, explicit_pause_events, laghu_guru, pada_break_indices_from_counts, split_syllables, build_pattern
from .evaluate import evaluate_pronunciation
from .models import AnalyzeRequest, AnalyzeResponse, ChantItem, PronunciationEvaluationResponse, Syllable, SynthesizeRequest, TTSRequest
from .tts import synthesize_tts_audio

load_dotenv()


app = FastAPI(title="Samyuti 2026 Chant PoC", version="0.1.0")

EASY_METERS = ["Anushtubh", "Indravajra", "Mandakranta", "Shardulavikridita"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"] ,
    allow_headers=["*"],
)


def _analyze(
    verse: str,
    meter_options: list[str] | None = None,
    preferred_meter: str | None = None,
) -> AnalyzeResponse:
    internal = split_syllables(verse)
    if not internal:
        raise HTTPException(status_code=400, detail="Could not detect syllables. Provide a valid Sanskrit verse.")

    types = [laghu_guru(s) for s in internal]

    chandas, pada_counts = detect_chandas(
        verse,
        allowed_meters=meter_options,
        preferred_meter=preferred_meter,
    )
    breaks = pada_break_indices_from_counts(pada_counts) if len(pada_counts) > 1 else None

    syllables: list[Syllable] = []
    chant_sequence: list[ChantItem] = []

    for s, t in zip(internal, types):
        duration = 1 if t == "laghu" else 2
        pitch = 1.0 if t == "laghu" else 1.5
        syllables.append(Syllable(text=s.text, type=t, duration=duration, pitch=pitch))
        chant_sequence.append(ChantItem(phoneme=s.text, duration=duration, pitch=pitch))

    pattern = build_pattern(types, breaks)

    return AnalyzeResponse(
        verse=verse,
        syllables=syllables,
        chandas=chandas,
        detected_meter=chandas,
        pattern=pattern,
        chant_sequence=chant_sequence,
    )


def _meter_rhythm_profile(meter_name: str) -> dict[str, float]:
    meter = meter_name.lower()
    if meter.startswith("mandakranta"):
        return {
            "duration_scale": 1.14,
            "guru_emphasis": 1.08,
            "pause_short": 0.84,
            "pause_long": 1.68,
        }
    if meter.startswith("shardulavikridita"):
        return {
            "duration_scale": 1.08,
            "guru_emphasis": 1.07,
            "pause_short": 0.78,
            "pause_long": 1.54,
        }
    if meter.startswith("indravajra"):
        return {
            "duration_scale": 0.96,
            "guru_emphasis": 1.03,
            "pause_short": 0.64,
            "pause_long": 1.34,
        }
    # Anushtubh and fallback profile.
    return {
        "duration_scale": 1.0,
        "guru_emphasis": 1.05,
        "pause_short": 0.7,
        "pause_long": 1.45,
    }


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    return _analyze(req.verse, meter_options=req.meter_options, preferred_meter=req.preferred_meter)


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_alias(req: AnalyzeRequest) -> AnalyzeResponse:
    return _analyze(req.verse, meter_options=req.meter_options, preferred_meter=req.preferred_meter)


@app.post("/api/synthesize")
def synthesize(req: SynthesizeRequest) -> Response:
    analysis = _analyze(
        req.verse,
        meter_options=EASY_METERS,
        preferred_meter=req.options.preferred_meter,
    )
    rhythm_profile = _meter_rhythm_profile(analysis.detected_meter)

    unit_seconds = req.options.unit_seconds
    pause_map = explicit_pause_events(req.verse)

    events: list[ChantEvent] = []
    for idx, syl in enumerate(analysis.syllables, start=1):
        long_bonus = 0.14 if any(ch in syl.text for ch in ("ā", "ī", "ū", "ṝ", "ḹ")) else 0.0
        duration_seconds = syl.duration * unit_seconds * (1.0 + long_bonus) * rhythm_profile["duration_scale"]
        if syl.type == "guru":
            duration_seconds *= rhythm_profile["guru_emphasis"]
        events.append(
            ChantEvent(
                kind="syllable",
                duration_seconds=duration_seconds,
                phoneme=syl.text,
                syllable_type=syl.type,
            )
        )
        if idx in pause_map:
            pause_mult = rhythm_profile["pause_short"] if pause_map[idx] == "short" else rhythm_profile["pause_long"]
            events.append(
                ChantEvent(kind="pause", duration_seconds=unit_seconds * pause_mult)
            )

    wav_bytes = synthesize_wav(
        events,
        config=SynthConfig(
            base_freq_hz=req.options.base_freq_hz,
            glide_ms=req.options.glide_ms,
            brightness=req.options.brightness,
            raga=req.options.raga,
            include_drone=req.options.include_drone,
            temple_reverb=req.options.temple_reverb,
            bell_at_edges=req.options.bell_at_edges,
        ),
    )

    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={"Content-Disposition": "inline; filename=chant.wav"},
    )


@app.post("/chant")
def synthesize_alias(req: SynthesizeRequest) -> Response:
    return synthesize(req)


@app.post("/api/tts")
async def tts(req: TTSRequest) -> Response:
    try:
        # Locked pathana defaults for consistent Sanskrit recitation output.
        locked_prefer_devanagari = True
        locked_chant_mode = True
        resolved_provider = req.options.provider
        if resolved_provider == "edge":
            if os.getenv("OPENAI_API_KEY") and os.getenv("AUTO_PREMIUM_TTS", "1") != "0":
                resolved_provider = "openai"

        locked_rate = "-18%" if resolved_provider == "edge" else req.options.rate

        audio_bytes, media_type, filename = await synthesize_tts_audio(
            req.verse,
            provider=resolved_provider,
            voice=req.options.voice,
            rate=locked_rate,
            pitch=req.options.pitch,
            raga=req.options.raga,
            model=req.options.model,
            audio_format=req.options.audio_format,
            prefer_devanagari=locked_prefer_devanagari,
            chant_mode=locked_chant_mode,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TTS generation failed: {exc}") from exc

    if not audio_bytes:
        raise HTTPException(status_code=502, detail="TTS generation failed: empty audio stream")

    return Response(
        content=audio_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )


@app.post("/tts")
async def tts_alias(req: TTSRequest) -> Response:
    return await tts(req)


@app.post("/api/evaluate-pronunciation", response_model=PronunciationEvaluationResponse)
async def evaluate_pronunciation_endpoint(
    verse: str = Form(...),
    audio_file: UploadFile = File(...),
) -> PronunciationEvaluationResponse:
    if not verse.strip():
        raise HTTPException(status_code=400, detail="Verse must not be empty")

    audio_bytes = await audio_file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio file is empty")

    try:
        return await evaluate_pronunciation(
            verse_input=verse,
            audio_bytes=audio_bytes,
            filename=audio_file.filename or "audio.wav",
            content_type=audio_file.content_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Evaluation failed: {exc}") from exc


@app.post("/evaluate-pronunciation", response_model=PronunciationEvaluationResponse)
async def evaluate_pronunciation_alias(
    verse: str = Form(...),
    audio_file: UploadFile = File(...),
) -> PronunciationEvaluationResponse:
    return await evaluate_pronunciation_endpoint(verse=verse, audio_file=audio_file)
