# BharathAI Chant Engine

## Chanda + Rhythm + Melody Sanskrit Recitation (Jury Submission)

BharathAI Chant Engine is a full-stack proof-of-concept that converts a Sanskrit verse into:

1. metrical analysis (laghu/guru + detected chandas)
2. melody-constrained chant audio
3. neural TTS recitation
4. pronunciation evaluation against the source verse

The project demonstrates how computational linguistics and audio synthesis can support guided Sanskrit pathana.

## Why this project matters

- Sanskrit recitation quality depends on both pronunciation and meter.
- Existing tools usually cover either text analysis or generic speech, not both in one loop.
- BharathAI Chant Engine integrates analysis, synthesis, listening, and feedback in a single interface.

## Highlights

- End-to-end flow: verse input -> meter analysis -> chant/TTS generation -> pronunciation scoring.
- Supports both IAST and Devanagari input.
- Meter-aware chant synthesis with timing, glide, drone, and raga profile controls.
- Two TTS backends: free Edge voices and premium OpenAI voices.
- Pronunciation evaluator that reports word-level issues and category-wise error summary.

## Architecture

- Frontend: React + Vite + TypeScript
- Backend: FastAPI + Python
- Audio:
  - rule-driven chant synthesis to WAV
  - neural TTS to MP3/WAV/OPUS/FLAC/PCM
- Evaluation:
  - transcription + alignment + Sanskrit-specific pronunciation checks

## Repository Structure

```text
.
├── backend/          # FastAPI app and synthesis/evaluation logic
├── frontend/         # React UI
├── run.sh            # One-command launcher (auto ports + logs)
└── README.md
```

## Quick Start (Recommended)

From repository root:

```bash
bash run.sh
```

What this script does:

- creates/uses backend virtual environment when possible
- falls back safely on systems with strict Python packaging
- installs missing dependencies
- auto-selects free ports if defaults are busy
- writes logs to:
  - `.logs/backend.log`
  - `.logs/frontend.log`

Default URLs:

- Frontend: `http://127.0.0.1:5173`
- Backend: `http://127.0.0.1:8000`

## Manual Setup

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

If virtual environment creation fails (`ensurepip` missing):

```bash
sudo apt install python3-venv
```

If PEP 668 blocks pip and you cannot use a venv:

```bash
python3 -m pip install --break-system-packages -r requirements.txt
/usr/bin/python3 -m uvicorn app.main:app --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

If Node.js/npm is missing (Debian/Ubuntu):

```bash
sudo apt install nodejs npm
```

## Environment Variables

Create a root `.env` file when using OpenAI features:

```bash
cp .env.example .env
```

Minimum variable:

```env
OPENAI_API_KEY=sk-your-openai-api-key
```

Notes:

- `.env` is auto-loaded by `run.sh` and backend startup.
- OpenAI key enables:
  - OpenAI TTS provider
  - pronunciation evaluation endpoint

## API Reference

Base URL: `http://localhost:8000`

### Health

- `GET /health`

### Analysis

- `POST /api/analyze` (alias: `POST /analyze`)
- Returns syllables, laghu/guru pattern, and detected meter.

Example:

```bash
curl -s http://localhost:8000/api/analyze \
  -H 'content-type: application/json' \
  -d '{
    "verse":"tataḥ śvetair hayair yukte mahati syandane sthitau | mādhavaḥ pāṇḍavaś caiva divyau śaṅkhau pradadhmatuḥ ||",
    "meter_options":["Anushtubh","Indravajra","Mandakranta","Shardulavikridita"]
  }' | jq
```

### Chant Synthesis

- `POST /api/synthesize` (alias: `POST /chant`)
- Returns `audio/wav`.

Request body:

```json
{
  "verse": "...",
  "options": {
    "unit_seconds": 0.24,
    "base_freq_hz": 174,
    "glide_ms": 35,
    "brightness": 0.55,
    "raga": "shanti",
    "include_drone": true,
    "temple_reverb": 0.22,
    "bell_at_edges": false,
    "preferred_meter": "Anushtubh"
  }
}
```

### Neural TTS

- `POST /api/tts` (alias: `POST /tts`)
- Returns neural speech audio.

Request body:

```json
{
  "verse": "...",
  "options": {
    "provider": "edge",
    "voice": "hi-IN-MadhurNeural",
    "rate": "-18%",
    "pitch": "+0Hz",
    "raga": "shanti",
    "model": "gpt-4o-mini-tts",
    "audio_format": "mp3",
    "prefer_devanagari": true,
    "chant_mode": true
  }
}
```

Providers:

- `edge` (default): free `edge-tts`
- `openai`: higher quality, requires `OPENAI_API_KEY`

### Pronunciation Evaluation

- `POST /api/evaluate-pronunciation` (alias: `POST /evaluate-pronunciation`)
- `multipart/form-data` with:
  - `verse` (text)
  - `audio_file` (recorded recitation)

Response includes:

- word-by-word issue detection
- rhythm/meter alignment summary
- clarity/fluency evaluation
- category-wise error counts
- overall score and suggestions

## Jury Demo Script (3-5 minutes)

1. Enter a verse in IAST or Devanagari.
2. Run analysis and show detected meter + laghu/guru sequence.
3. Generate chant audio and demonstrate audible meter discipline.
4. Generate TTS with Edge, then OpenAI (if key configured) to compare quality.
5. Upload a spoken recording and display pronunciation feedback report.

## Current Scope and Limitations

- Meter detection is heuristic and optimized for common classical meters.
- Synthesis is musically guided recitation, not a full studio-grade singing engine.
- TTS and pronunciation evaluation require internet access.

## Next Milestones

- broaden meter coverage and improve disambiguation
- tighter phoneme-duration modeling for complex sandhi regions
- richer analytics dashboard for repeated learner practice

## Tech Stack

- FastAPI
- Pydantic
- React + TypeScript + Vite
- edge-tts
- OpenAI APIs
- indic-transliteration

## Submission Notes

This repository is intentionally organized for reproducible judging:

- one-command start via `run.sh`
- explicit API contracts
- clear fallback behavior for Python environment constraints
