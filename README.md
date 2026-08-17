# Inner Compass / AstroAI MVP

Telegram bot that creates three astrological PDF reports:

- Inner Compass — natal report
- Inner Compass Year — yearly transit report
- Inner Compass Together — relationship report

The user interface and generated reports are in Ukrainian.

## Requirements

- Python 3.11
- A Telegram bot token
- An OpenAI API key for AI-generated interpretations
- A GeoNames username for reliable geocoding

## Local setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Fill in `.env`, then start the bot:

```powershell
.\.venv\Scripts\python.exe bot.py
```

The bot currently uses long polling and is intended for local development.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The default pytest configuration runs the deterministic suite in `tests/`.
Legacy root-level `test_*.py` files are manual and integration checks; some of
them use external services or generate files and should be run explicitly.

## Configuration

| Variable | Purpose |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Telegram bot authentication |
| `OPENAI_API_KEY` | AI report generation; code provides fallbacks when absent |
| `OPENAI_MODEL` | OpenAI model, defaults to `gpt-4o-mini` |
| `KERYKEION_GEONAMES_USERNAME` | GeoNames account used for geocoding |

Never commit `.env`, generated reports, local databases, or logs.