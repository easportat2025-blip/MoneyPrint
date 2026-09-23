# MoneyPrint – ReZain YT Autopilot

Faceless space/science YouTube pipeline: plan → research → script → TTS → stock media → ffmpeg → YouTube upload. Runs on GitHub Actions; local machine only runs the dashboard.

## Setup

1. `pip install -r requirements.txt`
2. Copy `.env.example` → `.env`, fill keys.
3. Get YouTube `refresh_token` (one-time local login):

```bash
python scripts/get_refresh_token.py
```

4. Put all `.env` values into GitHub **Settings → Secrets and variables → Actions**.

## Local commands

```bash
python main.py short        # one <60s vertical video full pipeline
python main.py long         # one >5min horizontal video
python main.py plan         # only generate idea bank
python main.py dashboard    # local log dashboard (port 5050)
python main.py retry VIDEO_ID
```

## Automation

- `.github/workflows/shorts.yml` – 3 Shorts/day (cron)
- `.github/workflows/long.yml` – 1 long video every 5 days
- Logs written to `logs` branch as `state.json` (dashboard pulls it).

## M0 checklist (manual)

- [ ] GCP: enable **YouTube Data API v3**
- [ ] GCP: OAuth Client ID (Desktop) → ID/Secret into secrets
- [ ] OAuth consent **Published** (Testing expires refresh_token in 7 days)
- [ ] Gemini keys ×2 (rotate), Pexels key, optional Pixabay key
