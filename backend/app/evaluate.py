from __future__ import annotations

import io
import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate
from openai import AsyncOpenAI

from .chant import split_syllables, to_iast
from .models import PronunciationEvaluationResponse, PronunciationIssue, WordPronunciationReport


_IastWordRe = re.compile(r"[a-zA-Zāīūṛṝḷḹṅñṭḍṇśṣḥṃṁ]+")
_DevaWordRe = re.compile(r"[\u0900-\u097F]+")

_LONG_TO_SHORT = str.maketrans({
    "ā": "a",
    "ī": "i",
    "ū": "u",
    "ṝ": "ṛ",
    "ḹ": "ḷ",
})


@dataclass
class _ObservedWord:
    text_iast: str
    start: float | None
    end: float | None


def _tokenize_iast_words(text: str) -> list[str]:
    return [w.lower() for w in _IastWordRe.findall(text)]


def _to_devanagari_word(iast_word: str) -> str:
    return transliterate(iast_word, sanscript.IAST, sanscript.DEVANAGARI)


def _normalize_iast_word(word: str) -> str:
    return "".join(_IastWordRe.findall(word.lower()))


def _timestamp_str(start: float | None, end: float | None) -> str | None:
    if start is None and end is None:
        return None
    if start is None:
        return f"~{end:.2f}s"
    if end is None:
        return f"~{start:.2f}s"
    return f"{start:.2f}s-{end:.2f}s"


def _has_any(word: str, chars: str) -> bool:
    return any(c in word for c in chars)


def _compare_word(expected: str, observed: str, ts: str | None) -> list[PronunciationIssue]:
    issues: list[PronunciationIssue] = []

    # Missing visarga
    if "ḥ" in expected and "ḥ" not in observed and not observed.endswith("h"):
        issues.append(
            PronunciationIssue(
                status="incorrect",
                category="visarga",
                expected=expected,
                observed=observed,
                explanation="❌ Missing visarga breath release (ḥ) in pronunciation.",
                timestamp=ts,
            )
        )

    # Anusvara handling
    if _has_any(expected, "ṃṁ") and not _has_any(observed, "ṃṁṅñṇnm"):
        issues.append(
            PronunciationIssue(
                status="incorrect",
                category="anusvara",
                expected=expected,
                observed=observed,
                explanation="❌ Anusvāra nasal resonance missing or replaced incorrectly.",
                timestamp=ts,
            )
        )

    # Short vs long vowels
    exp_short = expected.translate(_LONG_TO_SHORT)
    obs_short = observed.translate(_LONG_TO_SHORT)
    if exp_short == obs_short and expected != observed:
        if _has_any(expected, "āīūṝḹ") and not _has_any(observed, "āīūṝḹ"):
            issues.append(
                PronunciationIssue(
                    status="incorrect",
                    category="vowel_length",
                    expected=expected,
                    observed=observed,
                    explanation="❌ Long vowel shortened (quantity error: guru -> laghu tendency).",
                    timestamp=ts,
                )
            )

    # Conjunct consonants
    for cluster in ("ktv", "ddhy", "cya", "jñ", "kṣ", "tr", "dhy", "ty", "sth"):
        if cluster in expected and cluster not in observed:
            issues.append(
                PronunciationIssue(
                    status="incorrect",
                    category="conjunct",
                    expected=expected,
                    observed=observed,
                    explanation=f"❌ Conjunct cluster '{cluster}' not articulated correctly.",
                    timestamp=ts,
                )
            )
            break

    # Nasalization errors
    if any(c in expected for c in ("ṅ", "ñ", "ṇ")) and not any(c in observed for c in ("ṅ", "ñ", "ṇ")):
        issues.append(
            PronunciationIssue(
                status="incorrect",
                category="nasalization",
                expected=expected,
                observed=observed,
                explanation="❌ Retroflex/palatal/velar nasal distinction collapsed.",
                timestamp=ts,
            )
        )

    # Specific letter errors
    if "ñ" in expected and "ñ" not in observed and "n" in observed:
        issues.append(
            PronunciationIssue(
                status="incorrect",
                category="letter",
                expected=expected,
                observed=observed,
                explanation="❌ ñ pronounced as n (palatal nasal lost).",
                timestamp=ts,
            )
        )

    # Missing/added syllables
    expected_syl = len(split_syllables(expected))
    observed_syl = len(split_syllables(observed)) if observed else 0
    if expected_syl != observed_syl:
        issues.append(
            PronunciationIssue(
                status="incorrect",
                category="missing_or_added",
                expected=expected,
                observed=observed,
                explanation=f"❌ Syllable count mismatch (expected {expected_syl}, observed {observed_syl}).",
                timestamp=ts,
            )
        )

    if not issues:
        issues.append(
            PronunciationIssue(
                status="correct",
                category="letter",
                expected=expected,
                observed=observed,
                explanation="✅ Correct pronunciation for this word at classical Sanskrit level.",
                timestamp=ts,
            )
        )

    return issues


def _align_words(expected_words: list[str], observed_words: list[_ObservedWord]) -> list[int | None]:
    used: set[int] = set()
    alignment: list[int | None] = []
    for i, exp in enumerate(expected_words):
        best_j: int | None = None
        best_score = -1.0
        lo = max(0, i - 3)
        hi = min(len(observed_words), i + 4)
        for j in range(lo, hi):
            if j in used:
                continue
            score = SequenceMatcher(None, exp, observed_words[j].text_iast).ratio()
            if score > best_score:
                best_score = score
                best_j = j
        if best_j is not None and best_score >= 0.34:
            alignment.append(best_j)
            used.add(best_j)
        else:
            alignment.append(None)
    return alignment


async def _transcribe_audio_with_openai(audio_bytes: bytes, filename: str, content_type: str | None) -> tuple[str, list[_ObservedWord]]:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    client = AsyncOpenAI()
    model_name = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")

    bio = io.BytesIO(audio_bytes)
    bio.name = filename or "audio.wav"

    try:
        resp = await client.audio.transcriptions.create(
            model=model_name,
            file=bio,
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )
    except TypeError:
        bio.seek(0)
        resp = await client.audio.transcriptions.create(
            model=model_name,
            file=bio,
            response_format="verbose_json",
        )

    if hasattr(resp, "model_dump"):
        data = resp.model_dump()
    elif isinstance(resp, dict):
        data = resp
    else:
        data = {"text": str(resp)}

    text = (data.get("text") or "").strip()

    words_raw = data.get("words") or []
    words: list[_ObservedWord] = []
    for w in words_raw:
        token = _normalize_iast_word((w.get("word") or ""))
        if not token:
            continue
        words.append(_ObservedWord(text_iast=token, start=w.get("start"), end=w.get("end")))

    # Fallback when word timestamps are missing
    if not words:
        for tok in _tokenize_iast_words(to_iast(text)):
            words.append(_ObservedWord(text_iast=tok, start=None, end=None))

    return text, words


def _rhythm_eval(expected_iast: str, observed_iast: str) -> str:
    exp_s = len(split_syllables(expected_iast))
    obs_s = len(split_syllables(observed_iast))
    delta = abs(exp_s - obs_s)
    if delta <= 1:
        return "Rhythm/meter: strong alignment with expected akshara count."
    if delta <= 3:
        return "Rhythm/meter: moderate mismatch; some aksharas compressed or extended."
    return "Rhythm/meter: significant deviation from expected metrical flow."


def _clarity_eval(incorrect_count: int, total_words: int) -> str:
    if total_words == 0:
        return "Clarity/fluency: unable to evaluate due to missing transcript."
    ratio = incorrect_count / total_words
    if ratio < 0.25:
        return "Clarity/fluency: clear and mostly fluent Sanskrit articulation."
    if ratio < 0.55:
        return "Clarity/fluency: understandable, but with multiple classical pronunciation lapses."
    return "Clarity/fluency: low classical clarity; strong Hindi-like or distorted articulation detected."


def _score_from_issues(issue_list: list[PronunciationIssue]) -> int:
    weights = {
        "visarga": 4,
        "anusvara": 4,
        "vowel_length": 5,
        "conjunct": 6,
        "nasalization": 4,
        "letter": 3,
        "missing_or_added": 7,
    }
    score = 100
    for issue in issue_list:
        if issue.status == "incorrect":
            score -= weights.get(issue.category, 3)
    return max(0, min(100, score))


def _suggestions(summary: dict[str, int]) -> list[str]:
    tips: list[str] = []
    if summary.get("vowel_length", 0) > 0:
        tips.append("Force duration control for long vowels (ā ī ū ṝ) with minimum 1.8x short-vowel length.")
    if summary.get("visarga", 0) > 0:
        tips.append("Add explicit visarga breath release (ḥ) at word endings using a short aspirated tail.")
    if summary.get("anusvara", 0) > 0 or summary.get("nasalization", 0) > 0:
        tips.append("Use context-sensitive nasal mapping (ṅ/ñ/ṇ/n/m) rather than generic 'n'.")
    if summary.get("conjunct", 0) > 0:
        tips.append("Train/evaluate on conjunct-heavy Sanskrit pairs (ktv, ddhy, jñ, kṣ, tr) with forced articulation.")
    if summary.get("missing_or_added", 0) > 0:
        tips.append("Enable akshara-level alignment loss to prevent dropped/inserted syllables.")
    if not tips:
        tips.append("Maintain current model settings; only minor prosody smoothing is needed.")
    return tips


async def evaluate_pronunciation(verse_input: str, audio_bytes: bytes, filename: str, content_type: str | None) -> PronunciationEvaluationResponse:
    verse_iast = to_iast(verse_input)
    expected_words_iast = _tokenize_iast_words(verse_iast)

    transcript_raw, observed_words = await _transcribe_audio_with_openai(audio_bytes, filename, content_type)
    transcript_iast = to_iast(transcript_raw)

    alignment = _align_words(expected_words_iast, observed_words)

    reports: list[WordPronunciationReport] = []
    all_issues: list[PronunciationIssue] = []

    for i, expected in enumerate(expected_words_iast):
        j = alignment[i]
        if j is None:
            observed = ""
            ts = None
        else:
            observed = observed_words[j].text_iast
            ts = _timestamp_str(observed_words[j].start, observed_words[j].end)

        issues = _compare_word(expected, observed, ts)
        all_issues.extend(issues)

        reports.append(
            WordPronunciationReport(
                word_devanagari=_to_devanagari_word(expected),
                word_iast=expected,
                observed_iast=observed,
                timestamp=ts,
                issues=issues,
            )
        )

    summary = {
        "visarga": 0,
        "anusvara": 0,
        "vowel_length": 0,
        "conjunct": 0,
        "nasalization": 0,
        "letter": 0,
        "missing_or_added": 0,
    }
    incorrect_count = 0
    for issue in all_issues:
        if issue.status == "incorrect":
            summary[issue.category] += 1
            incorrect_count += 1

    score = _score_from_issues(all_issues)

    return PronunciationEvaluationResponse(
        verse_input=verse_input,
        verse_iast=verse_iast,
        transcript_raw=transcript_raw,
        transcript_iast=transcript_iast,
        word_by_word_analysis=reports,
        rhythm_meter_evaluation=_rhythm_eval(verse_iast, transcript_iast),
        clarity_fluency_evaluation=_clarity_eval(incorrect_count, max(1, len(expected_words_iast))),
        error_summary=summary,
        overall_score=score,
        suggestions=_suggestions(summary),
    )
