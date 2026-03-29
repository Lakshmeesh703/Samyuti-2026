# Backend (FastAPI)

Run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

If `python3 -m venv` fails (missing `ensurepip`), install:

```bash
sudo apt install python3-venv
```

Endpoints:
- `GET /health`
- `POST /api/analyze`
- `POST /api/synthesize`
- `POST /api/tts`

`/api/synthesize` payload:

```json
{
	"verse": "...",
	"options": {
		"unit_seconds": 0.24,
		"base_freq_hz": 174,
		"glide_ms": 35,
		"brightness": 0.55,
		"include_drone": true
	}
}
```

`/api/tts` payload:

```json
{
	"verse": "...",
	"options": {
		"provider": "edge",
		"voice": "hi-IN-MadhurNeural",
		"rate": "+0%",
		"pitch": "+0Hz",
		"model": "gpt-4o-mini-tts",
		"audio_format": "mp3",
		"prefer_devanagari": true
	}
}
```

Provider notes:
- `edge`: works without API key.
- `openai`: set `OPENAI_API_KEY` before starting backend.
