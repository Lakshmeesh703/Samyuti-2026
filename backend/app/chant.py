from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate


_VOWELS = [
    "ai",
    "au",
    "ā",
    "ī",
    "ū",
    "ṛ",
    "ṝ",
    "ḷ",
    "ḹ",
    "a",
    "i",
    "u",
    "e",
    "o",
]
_LONG_VOWELS = {"ā", "ī", "ū", "e", "o", "ai", "au", "ṝ", "ḹ"}

_ANUSVARA = {"ṃ", "ṁ"}
_VISARGA = {"ḥ"}

# Common IAST consonant digraphs (greedy tokenization)
_DIGRAPHS = {
    "kh",
    "gh",
    "ch",
    "jh",
    "ṭh",
    "ḍh",
    "th",
    "dh",
    "ph",
    "bh",
}


_PUNCT_OR_BREAK = set("|/\\.,;:!?—–-·'\"()[]{}“”‘’") | {"।", "॥"}


@dataclass(frozen=True)
class _SyllableInternal:
    text: str
    vowel: str
    ends_with_consonant: bool
    ends_with_mh: bool


def _looks_devanagari(text: str) -> bool:
    return any("\u0900" <= ch <= "\u097F" for ch in text)


def normalize_verse(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    # Normalize danda variants to '|'
    text = text.replace("॥", "||").replace("।", "|")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def to_iast(text: str) -> str:
    text = normalize_verse(text)
    if _looks_devanagari(text):
        # DEVANAGARI -> IAST
        return transliterate(text, sanscript.DEVANAGARI, sanscript.IAST)
    return text


def _is_vowel_start(s: str, idx: int) -> str | None:
    for v in _VOWELS:
        if s.startswith(v, idx):
            return v
    return None


def _is_anusvara(ch: str) -> bool:
    return ch in _ANUSVARA


def _is_visarga(ch: str) -> bool:
    return ch in _VISARGA


def _is_break(ch: str) -> bool:
    return ch.isspace() or ch in _PUNCT_OR_BREAK


def _next_consonant_run(s: str, idx: int) -> int:
    # Counts letters that are consonants (not vowels/break/anusvara/visarga)
    run = 0
    j = idx
    while j < len(s):
        if _is_break(s[j]):
            break
        if _is_anusvara(s[j]) or _is_visarga(s[j]):
            break
        v = _is_vowel_start(s, j)
        if v is not None:
            break

        # Consume consonant token (digraph if present)
        if j + 2 <= len(s) and s[j : j + 2] in _DIGRAPHS:
            j += 2
        else:
            j += 1
        run += 1
    return run


def split_syllables(verse: str) -> list[_SyllableInternal]:
    s = to_iast(verse)

    syllables: list[_SyllableInternal] = []
    i = 0
    while i < len(s):
        if _is_break(s[i]):
            i += 1
            continue

        onset_start = i
        # Move through consonant onset
        while i < len(s):
            if _is_break(s[i]) or _is_anusvara(s[i]) or _is_visarga(s[i]):
                break
            v = _is_vowel_start(s, i)
            if v is not None:
                break
            if i + 2 <= len(s) and s[i : i + 2] in _DIGRAPHS:
                i += 2
            else:
                i += 1

        v = _is_vowel_start(s, i)
        if v is None:
            # Skip unknown char; avoid infinite loop
            i += 1
            continue

        i += len(v)
        # Optional anusvara/visarga
        ends_with_mh = False
        if i < len(s) and (_is_anusvara(s[i]) or _is_visarga(s[i])):
            ends_with_mh = True
            i += 1

        # Decide if we pull one consonant into coda
        consonant_run = _next_consonant_run(s, i)
        ends_with_consonant = False

        if consonant_run >= 2:
            # Include first consonant token as coda
            ends_with_consonant = True
            if i + 2 <= len(s) and s[i : i + 2] in _DIGRAPHS:
                i += 2
            else:
                i += 1
        else:
            # If word ends with a consonant (rare in Sanskrit but possible in input)
            # Include it as coda when it is immediately followed by break/end.
            if consonant_run == 1:
                # Peek consonant token length
                token_len = 2 if (i + 2 <= len(s) and s[i : i + 2] in _DIGRAPHS) else 1
                after = i + token_len
                if after >= len(s) or _is_break(s[after]):
                    ends_with_consonant = True
                    i = after

        text = s[onset_start:i]
        syllables.append(
            _SyllableInternal(
                text=text,
                vowel=v,
                ends_with_consonant=ends_with_consonant,
                ends_with_mh=ends_with_mh,
            )
        )

    return syllables


def laghu_guru(syl: _SyllableInternal) -> str:
    # STEP 2 rules (plus standard Sanskrit metrical “closing” cues)
    if syl.vowel in _LONG_VOWELS:
        return "guru"
    if syl.ends_with_consonant:
        return "guru"
    if syl.ends_with_mh:
        return "guru"
    return "laghu"


def build_pattern(types: Iterable[str], pada_breaks: list[int] | None = None) -> str:
    letters = ["G" if t == "guru" else "L" for t in types]
    if not pada_breaks:
        return "".join(letters)

    out: list[str] = []
    for idx, ch in enumerate(letters, start=1):
        out.append(ch)
        if idx in set(pada_breaks):
            out.append("|")
    return "".join(out).rstrip("|")


def _split_padas_for_meter(verse: str) -> list[str]:
    v = normalize_verse(verse)

    # Prefer explicit verse-end marker: treat '||' as half-verse boundary.
    if "||" in v:
        halves = [h.strip() for h in v.split("||") if h.strip()]
        # If quarters are explicitly given, use them.
        quarters: list[str] = []
        for h in halves:
            if "|" in h:
                quarters.extend([p.strip() for p in h.split("|") if p.strip()])
            else:
                quarters.append(h)
        return quarters

    # Otherwise, use single '|' separators if present.
    if "|" in v:
        parts = [p.strip() for p in v.split("|")]
        return [p for p in parts if p]

    return [v]


def detect_chandas(
    verse: str,
    allowed_meters: list[str] | None = None,
    preferred_meter: str | None = None,
) -> tuple[str, list[int]]:
    # Returns (name, pada_syllable_counts)
    v_norm = normalize_verse(verse)
    padas = _split_padas_for_meter(v_norm)
    counts = [len(split_syllables(p)) for p in padas]

    # Special heuristic:
    # Many inputs mark only 2 half-verses using `... | ... ||` (common in printed ślokas).
    # For Anuṣṭubh, each half-verse is often ~16 syllables and splits into two pādas of 8.
    core = v_norm.strip()
    if core.endswith("||"):
        core_wo_end = core[:-2].strip()
        raw_halves = [p.strip() for p in core_wo_end.split("|") if p.strip()]
        if len(raw_halves) == 2:
            c1 = len(split_syllables(raw_halves[0]))
            c2 = len(split_syllables(raw_halves[1]))
            if c1 >= 12 and c2 >= 12 and c1 % 2 == 0 and c2 % 2 == 0:
                counts = [c1 // 2, c1 // 2, c2 // 2, c2 // 2]

    # Simple count-based nearest match for common meters
    known = {
        "Anushtubh": [8, 8, 8, 8],
        "Indravajra": [11, 11, 11, 11],
        "Mandakranta": [17, 17, 17, 17],
        "Shardulavikridita": [19, 19, 19, 19],
    }

    if allowed_meters:
        allowed_set = set(allowed_meters)
        known = {name: target for name, target in known.items() if name in allowed_set}
        if not known:
            known = {"Anushtubh": [8, 8, 8, 8]}

    def distance(a: list[int], b: list[int]) -> int:
        # Penalize different pada count heavily
        if len(a) != len(b):
            return 100 + abs(len(a) - len(b)) * 10 + abs(sum(a) - sum(b))
        return sum(abs(x - y) for x, y in zip(a, b))

    best_name = f"Unknown (pada count {len(counts)})"
    best_dist = 10**9
    for name, target in known.items():
        d = distance(counts, target)
        if preferred_meter and name == preferred_meter:
            d -= 1
        if d < best_dist:
            best_dist = d
            best_name = name

    # If no separators, also try total-syllable heuristics
    if len(counts) == 1:
        total = counts[0]
        if total == 32:
            best_name = "Anushtubh (likely, 32 syllables)"
        elif total == 44:
            best_name = "Indravajra (likely, 44 syllables)"
        elif total == 68:
            best_name = "Mandakranta (likely, 68 syllables)"
        elif total == 76:
            best_name = "Shardulavikridita (likely, 76 syllables)"

    return best_name, counts


def pada_break_indices_from_counts(counts: list[int]) -> list[int]:
    indices: list[int] = []
    total = 0
    for c in counts[:-1]:
        total += c
        indices.append(total)
    return indices


def explicit_pause_events(verse: str) -> dict[int, str]:
    """Return map of syllable-index -> pause kind ('short' for |, 'long' for ||)."""
    v = normalize_verse(verse)
    parts = re.split(r"(\|\||\|)", v)

    out: dict[int, str] = {}
    syll_count = 0
    for token in parts:
        if not token:
            continue
        if token == "|":
            out[syll_count] = "short"
            continue
        if token == "||":
            out[syll_count] = "long"
            continue
        syll_count += len(split_syllables(token))

    return out
