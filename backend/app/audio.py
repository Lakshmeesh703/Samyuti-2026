from __future__ import annotations

import io
import math
import wave
from dataclasses import dataclass
from typing import Iterable, Literal


RagaName = Literal["shanti", "meditative", "devotional"]


@dataclass(frozen=True)
class ChantEvent:
    kind: Literal["syllable", "pause"]
    duration_seconds: float
    phoneme: str = ""
    syllable_type: Literal["laghu", "guru"] = "laghu"


@dataclass(frozen=True)
class SynthConfig:
    sample_rate: int = 24000
    base_freq_hz: float = 174.0
    volume: float = 0.55
    glide_ms: int = 35
    brightness: float = 0.55
    raga: RagaName = "shanti"
    include_drone: bool = True
    temple_reverb: float = 0.22
    bell_at_edges: bool = False


def _adsr_envelope(i: int, n: int, is_guru: bool) -> float:
    if n <= 4:
        return 1.0

    attack = max(1, int(n * 0.07))
    decay = max(1, int(n * 0.14))
    release = max(1, int(n * 0.18))
    sustain_level = 0.82 if is_guru else 0.75

    if i < attack:
        return i / attack

    if i < attack + decay:
        p = (i - attack) / decay
        return 1.0 - (1.0 - sustain_level) * p

    if i >= n - release:
        p = (i - (n - release)) / release
        return max(0.0, sustain_level * (1.0 - p))

    return sustain_level


_RAGA_SEMITONES: dict[RagaName, list[int]] = {
    # Hamsadhwani-like
    "shanti": [0, 2, 4, 7, 11, 12],
    # Yaman-like
    "meditative": [0, 2, 4, 6, 7, 9, 11, 12],
    # Bhairavi-like
    "devotional": [0, 1, 3, 5, 7, 8, 10, 12],
}


def _raga_pitch_multiplier(raga: RagaName, syllable_index: int, total_syllables: int, is_guru: bool) -> float:
    scale = _RAGA_SEMITONES[raga]
    note = scale[syllable_index % len(scale)]
    if total_syllables > 1:
        # Gentle melodic arc (phrase contour)
        arch = math.sin(math.pi * syllable_index / max(1, total_syllables - 1)) * 0.35
    else:
        arch = 0.0
    semitones = note + arch + (0.15 if is_guru else 0.0)
    return 2 ** (semitones / 12.0)


def _has_visarga(phoneme: str) -> bool:
    return "ḥ" in phoneme or "ः" in phoneme


def _has_anusvara(phoneme: str) -> bool:
    return any(ch in phoneme for ch in ("ṃ", "ṁ", "ं"))


def _add_bell(float_frames: list[float], sample_rate: int, where: Literal["start", "end"]) -> None:
    n = int(sample_rate * 0.22)
    if n <= 0:
        return
    tone: list[float] = []
    for i in range(n):
        t = i / sample_rate
        env = math.exp(-7.0 * t)
        s = env * (
            0.8 * math.sin(2 * math.pi * 1046.5 * t)
            + 0.35 * math.sin(2 * math.pi * 1568.0 * t)
            + 0.22 * math.sin(2 * math.pi * 2093.0 * t)
        )
        tone.append(0.18 * s)
    if where == "start":
        float_frames[:0] = tone
    else:
        float_frames.extend(tone)


def _apply_temple_reverb(float_frames: list[float], sample_rate: int, mix: float) -> list[float]:
    if mix <= 0:
        return float_frames

    n = len(float_frames)
    wet = [0.0] * n
    delays = [
        int(sample_rate * 0.052),
        int(sample_rate * 0.083),
        int(sample_rate * 0.127),
    ]
    gains = [0.34, 0.22, 0.14]

    for delay, gain in zip(delays, gains):
        for i in range(delay, n):
            wet[i] += float_frames[i - delay] * gain

    out = [(1.0 - mix) * d + mix * w for d, w in zip(float_frames, wet)]
    return out


def synthesize_wav(
    items: Iterable[ChantEvent],
    *,
    config: SynthConfig | None = None,
) -> bytes:
    """Synthesize chant-like audio.

    items: iterable of chant events
    """
    cfg = config or SynthConfig()
    events = list(items)
    voiced_events = [ev for ev in events if ev.kind == "syllable"]

    sample_rate = cfg.sample_rate
    glide_samples = max(1, int(sample_rate * cfg.glide_ms / 1000.0))

    float_frames: list[float] = []
    phase_f0 = 0.0
    phase_f1 = 0.0
    phase_f2 = 0.0
    phase_f3 = 0.0
    phase_nasal = 0.0
    prev_freq = cfg.base_freq_hz
    syllable_idx = 0
    total_syllables = max(1, len(voiced_events))

    for idx, ev in enumerate(events):
        n = max(1, int(sample_rate * max(0.02, ev.duration_seconds)))
        if ev.kind == "pause":
            float_frames.extend([0.0] * n)
            continue

        is_guru = ev.syllable_type == "guru"
        pitch_mult = _raga_pitch_multiplier(cfg.raga, syllable_idx, total_syllables, is_guru)
        target_freq = cfg.base_freq_hz * pitch_mult
        note_glide = min(glide_samples, max(1, n // 3))

        has_visarga = _has_visarga(ev.phoneme)
        has_anusvara = _has_anusvara(ev.phoneme)

        for i in range(n):
            # Frequency glide for smooth pitch transitions
            if i < note_glide:
                blend = i / note_glide
                freq = prev_freq + (target_freq - prev_freq) * blend
            else:
                freq = target_freq

            # Very subtle slow vibrato for chant texture
            t_global = len(float_frames) / sample_rate
            vibrato = 1.0 + 0.004 * math.sin(2.0 * math.pi * 5.2 * t_global)
            f0 = freq * vibrato

            # Keep phase continuous across syllables (eliminates click/beep feeling)
            phase_f0 += (2.0 * math.pi * f0) / sample_rate
            phase_f1 += (2.0 * math.pi * (f0 * 2.0)) / sample_rate
            phase_f2 += (2.0 * math.pi * (f0 * 3.0)) / sample_rate
            phase_f3 += (2.0 * math.pi * (f0 * 4.0)) / sample_rate

            b = cfg.brightness
            harmonic = (
                0.66 * math.sin(phase_f0)
                + (0.23 + 0.13 * b) * math.sin(phase_f1)
                + (0.10 + 0.08 * b) * math.sin(phase_f2)
                + (0.05 + 0.06 * b) * math.sin(phase_f3)
            )

            env = _adsr_envelope(i, n, is_guru)
            sample = harmonic * env

            # Anusvāra nasal resonance (soft hum overtone)
            if has_anusvara:
                phase_nasal += (2.0 * math.pi * (f0 * 0.5)) / sample_rate
                sample += 0.12 * math.sin(phase_nasal) * env

            # Visarga breath tail: airy fade in last quarter
            if has_visarga and i > int(n * 0.72):
                p = (i - int(n * 0.72)) / max(1, int(n * 0.28))
                breath = (math.sin(2 * math.pi * 3200 * t_global) + math.sin(2 * math.pi * 2800 * t_global)) * 0.03
                sample += breath * p * (1.0 - p)

            # Optional low-level tonic drone to reduce isolated beeps
            if cfg.include_drone:
                drone = 0.11 * math.sin(2.0 * math.pi * cfg.base_freq_hz * t_global)
                drone += 0.07 * math.sin(2.0 * math.pi * cfg.base_freq_hz * 2.0 * t_global)
                drone += 0.04 * math.sin(2.0 * math.pi * cfg.base_freq_hz * 3.0 * t_global)
                sample += drone

            float_frames.append(sample)

        prev_freq = target_freq
        syllable_idx += 1

        # Tiny natural pause only at very long notes
        if idx < len(events) - 1 and ev.duration_seconds > 0.35:
            pause_n = int(sample_rate * 0.006)
            if pause_n > 0:
                float_frames.extend([0.0] * pause_n)

    if cfg.bell_at_edges:
        _add_bell(float_frames, sample_rate, "start")
        _add_bell(float_frames, sample_rate, "end")

    float_frames = _apply_temple_reverb(float_frames, sample_rate, cfg.temple_reverb)

    # Peak normalize to avoid clipping and keep stable loudness
    if not float_frames:
        float_frames = [0.0]
    peak = max(1e-9, max(abs(x) for x in float_frames))
    gain = min(0.95 / peak, cfg.volume)

    frames = [int(max(-1.0, min(1.0, s * gain)) * 32767) for s in float_frames]

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(int(s).to_bytes(2, "little", signed=True) for s in frames))

    return buf.getvalue()
