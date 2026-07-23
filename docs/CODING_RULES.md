# Coding Rules

## General

- Python 3.11
- UTF-8 encoding
- English variable names
- Ukrainian user interface
- Modular architecture
- One responsibility per module

---

## Code Style

- Use type hints everywhere
- Every function must have a docstring
- Keep functions under 50 lines whenever possible
- Avoid duplicated code
- Prefer readability over cleverness

---

## Project Structure

bot.py
- Telegram only

database.py
- Database only

services/astrology.py
- Astrology calculations

services/ai.py
- OpenAI integration

services/pdf.py
- PDF generation

---

## Security

- Never hardcode secrets
- Store keys in .env
- Validate all user input

---

## Logging

- Log all important actions
- Log all errors
- Never crash silently

---

## AI Rules

The assistant must:

- Never invent astrological calculations
- Explain results clearly
- Be respectful
- Avoid deterministic predictions

---

## Documentation

Every new module should include:

- Clear docstrings
- Comments where necessary
- Simple examples if appropriate