from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SyllableType = Literal["laghu", "guru"]
EasyMeterName = Literal["Anushtubh", "Indravajra", "Mandakranta", "Shardulavikridita"]


class AnalyzeRequest(BaseModel):
    verse: str = Field(..., min_length=1, description="Sanskrit verse (IAST or Devanagari)")
    meter_options: list[EasyMeterName] | None = Field(
        default=None,
        description="Optional meter candidates for constrained detection",
    )
    preferred_meter: EasyMeterName | None = Field(
        default=None,
        description="Optional preferred meter used as a soft tiebreaker",
    )


class SynthesisOptions(BaseModel):
    unit_seconds: float = Field(0.24, ge=0.12, le=0.6, description="Seconds for one laghu unit")
    base_freq_hz: float = Field(174.0, ge=110.0, le=330.0, description="Base tonic frequency")
    glide_ms: int = Field(35, ge=0, le=200, description="Pitch glide time between syllables")
    brightness: float = Field(0.55, ge=0.1, le=1.0, description="Harmonic brightness")
    raga: Literal["shanti", "meditative", "devotional"] = Field("shanti", description="Raga profile")
    include_drone: bool = Field(True, description="Add a low-level tonic drone")
    temple_reverb: float = Field(0.22, ge=0.0, le=0.6, description="Subtle temple reverb mix")
    bell_at_edges: bool = Field(False, description="Play gentle bell at start and end")
    preferred_meter: EasyMeterName | None = Field(
        default=None,
        description="Optional preferred meter to shape chant rhythm",
    )


class SynthesizeRequest(BaseModel):
    verse: str = Field(..., min_length=1, description="Sanskrit verse (IAST or Devanagari)")
    options: SynthesisOptions = Field(default_factory=SynthesisOptions)


class TTSOptions(BaseModel):
    provider: Literal["edge", "openai"] = Field("edge", description="TTS backend provider")
    voice: str = Field("hi-IN-MadhurNeural", description="Neural voice id")
    rate: str = Field("-18%", description="Speech rate, e.g. +0%, -10%")
    pitch: str = Field("+0Hz", description="Pitch shift, e.g. +0Hz, +20Hz")
    raga: Literal["shanti", "meditative", "devotional"] = Field("shanti", description="Raga mood for TTS prosody")
    model: str = Field("gpt-4o-mini-tts", description="OpenAI TTS model")
    audio_format: Literal["mp3", "wav", "opus", "flac", "pcm"] = Field("mp3", description="OpenAI output format")
    prefer_devanagari: bool = Field(True, description="Convert IAST input to Devanagari before TTS")
    chant_mode: bool = Field(True, description="Speak verse as syllable-wise chanting pathana")


class TTSRequest(BaseModel):
    verse: str = Field(..., min_length=1, description="Sanskrit verse (IAST or Devanagari)")
    options: TTSOptions = Field(default_factory=TTSOptions)


class Syllable(BaseModel):
    text: str
    type: SyllableType
    duration: int
    pitch: float


class ChantItem(BaseModel):
    phoneme: str
    duration: int
    pitch: float


class AnalyzeResponse(BaseModel):
    verse: str
    syllables: list[Syllable]
    chandas: str
    detected_meter: str
    pattern: str
    chant_sequence: list[ChantItem]


class PronunciationIssue(BaseModel):
    status: Literal["correct", "incorrect"]
    category: Literal[
        "visarga",
        "anusvara",
        "vowel_length",
        "conjunct",
        "nasalization",
        "letter",
        "missing_or_added",
    ]
    expected: str
    observed: str
    explanation: str
    timestamp: str | None = None


class WordPronunciationReport(BaseModel):
    word_devanagari: str
    word_iast: str
    observed_iast: str
    timestamp: str | None
    issues: list[PronunciationIssue]


class PronunciationEvaluationResponse(BaseModel):
    verse_input: str
    verse_iast: str
    transcript_raw: str
    transcript_iast: str
    word_by_word_analysis: list[WordPronunciationReport]
    rhythm_meter_evaluation: str
    clarity_fluency_evaluation: str
    error_summary: dict[str, int]
    overall_score: int
    suggestions: list[str]
