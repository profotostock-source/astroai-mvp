# Inner Compass AI Architecture

## Overview

The system is modular. Each component has a single responsibility.

```
Telegram Bot
      │
      ▼
Conversation Manager
      │
      ▼
User Database (SQLite)
      │
      ▼
Astrology Engine (Kerykeion + Swiss Ephemeris)
      │
      ▼
AI Interpretation Engine (OpenAI)
      │
      ▼
Report Generator
      │
      ▼
PDF Builder
      │
      ▼
Telegram Delivery
```

---

## Project Structure

```
AstroAI_MVP/

bot.py

database.py

services/
    astrology.py
    ai.py
    pdf.py

reports/

docs/

.env
```

---

## Responsibilities

### bot.py

- Telegram commands
- Conversation flow
- User interaction

### database.py

- SQLite
- User storage
- Report history

### astrology.py

- Natal chart calculation
- Planet positions
- Houses
- Aspects

### ai.py

- OpenAI communication
- Prompt generation
- Interpretation

### pdf.py

- Beautiful report creation
- Layout
- Export to PDF

---

## Future Modules

- Payments
- Subscription
- Dashboard
- Human Design
- Numerology
- Mobile App
- Web App