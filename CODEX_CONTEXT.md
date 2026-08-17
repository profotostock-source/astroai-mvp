# AstroAI MVP — Контекст для Codex / нової сесії

> Цей файл містить повний стан проекту станом на **17.08.2026**.  
> Використовуй його як стартовий контекст у новій сесії Codex або Claude.

---

## Що це за продукт

**Inner Compass** — Telegram-бот астрологічних PDF-звітів. Три продукти:

| Продукт | Опис | PDF |
|---|---|---|
| **Inner Compass** | Персональний натальний звіт (9 секцій) | `services/pdf_report.py` |
| **Inner Compass Year** | Річний прогноз транзитів на рік | `services/pdf_year_report.py` |
| **Inner Compass Together** | Синастрія для пари (9 секцій) | `services/pdf_together_report.py` |

Лендінг: `index.html` (~1700 рядків, V3, з реальними WebP-скриншотами PDF і lightbox).

---

## Структура файлів

```
AstroAI_MVP/
├── index.html                  # Лендінг (V3, готовий)
├── bot.py                      # Telegram-бот (python-telegram-bot 20.x)
├── database.py                 # SQLite: user_profiles, city_cache, together_reports
├── config.py                   # .env: BOT_TOKEN, OPENAI_API_KEY, GEOCODING_API_KEY
├── requirements.txt
│
├── services/
│   ├── astrology.py            # calculate_natal_chart() через kerykeion
│   ├── transits.py             # calculate_transits() для річного звіту
│   ├── synastry.py             # calculate_synastry() → список аспектів
│   ├── evidence_builder.py     # build_context() → JSON для GPT (персональний)
│   ├── together_evidence.py    # build_together_context() → JSON для GPT (пара)
│   ├── ai_interpretation.py    # generate_psychological_report() через GPT-4o
│   ├── ai_together.py          # generate_together_report() через GPT-4o
│   ├── pdf_report.py           # PDF персонального звіту (ReportLab)
│   ├── pdf_year_report.py      # PDF річного звіту (ReportLab)
│   ├── pdf_together_report.py  # PDF для пари (ReportLab)
│   ├── pdf.py                  # Старий генератор (не використовується)
│   ├── interpretation_engine.py
│   ├── interpretations.py      # SIGN_NAMES та інші константи
│   ├── glyphs.py               # draw_constellation(), draw_sign(), scatter_stars()
│   ├── chart_wheel.py
│   ├── human_model.py
│   ├── scenario_engine.py
│   └── __init__.py
│
├── knowledge/
│   ├── evidence_rules.py       # Правила побудови контексту (персональний)
│   ├── synastry_orbs.py        # SYNASTRY_ORBS, ASPECT_WEIGHTS, TYPE_WEIGHTS
│   └── transit_rules.py        # Правила інтерпретації транзитів
│
├── tests/
│   └── test_together.py        # 16 тестів Together (всі pass)
│
├── assets/                     # WebP-скриншоти для лендінгу
│   ├── report-cover.webp
│   ├── report-page-1.webp
│   ├── report-page-2.webp
│   ├── year-report-cover.webp
│   ├── year-report-career.webp
│   └── year-report-development.webp
│
├── data/
│   └── astroai.db              # SQLite база
└── reports/                    # Згенеровані PDF (gitignore)
```

---

## Ключові технічні рішення

### Астрологія
- Бібліотека: **kerykeion** (`AstrologicalSubject(name, day, month, year, hour, minute, lat, lng, tz_str, online=False)`)
- Геокодинг: зовнішній API (nominatim або аналог) + кеш у SQLite `city_cache`
- Синастрія: `services/synastry.py` → аспекти між двома картами, score = planet_weight × type_modifier × (1 − orb/max_orb), сортування по score desc

### PDF (ReportLab)
- Всі три генератори використовують спільні константи і хелпери з `pdf_report.py`:
  - `PAPER, GOLD, GOLD_PALE, INK, INK_SOFT, MUTED, HAIRLINE, PAPER_2`
  - `_tracked()`, `_rule()`, `_paint()`, `_hr()`, `_escape()`, `_clean_markdown()`
  - `_Marker` (Flowable для running head), `_build_styles()`, `_load_fonts()`
- Три PageTemplate: `cover`, `plate` (темний фон з сузір'ям), `body`
- Шрифти: серіф + без серіф (підключаються через `_load_fonts()`)

### AI
- GPT-4o через OpenAI API
- Промпт отримує структурований JSON-контекст (не сирі дати народження)
- `evidence_builder.py` → контекст для персонального звіту
- `together_evidence.py` → контекст для пари (strongest_aspects top 12-20, themes)
- Graceful fallback якщо API недоступний

### Telegram-бот
- `python-telegram-bot` 20.x (async)
- `ConversationHandler` для збору даних (name → date → time_known → time → place)
- Два окремих ConversationHandler: основний і `together_conversation_handler`
- Стани Together: `TOGETHER_PERSON_B_NAME/DATE/TIME_KNOWN/TIME/PLACE/CONFIRM`

### База даних (SQLite)
- `user_profiles`: telegram_user_id, name, birth_date, birth_time, birthplace
- `city_cache`: нормалізований ключ → lat/lng/tz
- `together_reports`: user_id_a, user_id_b, pdf_path, created_at

---

## Парсинг AI-тексту у Together PDF

`pdf_together_report.py` → `_parse_sections_from_ai(ai_text)`:
- Шукає заголовки `Секція N.` regex-ом
- Повертає `{1: "текст секції 1", 2: "текст секції 2", ...}`
- Fallback: рівні чанки якщо заголовків немає

AI має повертати текст у форматі:
```
Секція 01. Що вас притягує
<текст 2-4 параграфи>

Секція 02. Емоційна близькість
<текст>
...
Підсумок
<текст>

Практика для пари
<текст>
```

---

## Лендінг (index.html)

- V3, ~1700 рядків
- Vanilla JS lightbox: `lbOpen(images, alts, startIdx)` — клік на стек → модальне вікно
- Demo-секція: `pdf-real-stack` з `data-lb-images` і `data-lb-alts`
- CSS hover spread: `.pdf-real-stack:hover .pdf-p2 { transform: rotate(-8deg) translate(-44px, 32px); }`
- `@media (hover: hover)` — hover тільки на пристроях з мишею
- `@media (prefers-reduced-motion: reduce)` — вимикає анімації
- Demo-особа: **Марія** (та сама натальна карта що у Ілона Маска, але анонімізована)
- WebP-зображення: 175 DPI, 1447×2047 px, з `loading="lazy"` і `width`/`height`

---

## NTFS / Sandbox застереження

**КРИТИЧНО**: Не використовуй `Edit` tool для великих файлів з кирилицею — виникають null bytes.

Завжди пиши через Python:
```python
with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
```

Перевірка після запису:
```python
with open(path, 'rb') as f:
    raw = f.read()
nulls = raw.count(b'\x00')
if nulls:
    raw = raw.replace(b'\x00', b'')
    with open(path, 'wb') as f:
        f.write(raw)
```

**Shell paths (bash)**:
- `C:\Users\Home\Documents\AstroAI_MVP` → `/sessions/.../mnt/AstroAI_MVP/`
- Не запускай `git` команди з bash на NTFS-маунті — використовуй VS Code Terminal

---

## Поточний стан: що готово

- [x] Натальний PDF-звіт (9 секцій, теплий стиль, кирилиця)
- [x] Річний PDF-звіт (транзити, Ключові моменти з картками)
- [x] Together PDF-звіт (синастрія, 9 секцій, кирилиця)
- [x] Telegram-бот з трьома типами звітів
- [x] Лендінг V3 з реальними WebP-скриншотами і lightbox
- [x] SQLite база (профілі, кеш міст, together-звіти)
- [x] 16 unit-тестів для Together (всі pass)

## Що можна розвивати далі

- [ ] Додати оплату (Stripe або LiqPay)
- [ ] Додати знижки / промокоди
- [ ] A/B тест лендінгу
- [ ] Webhook замість polling для боту (production)
- [ ] Адмін-панель зі статистикою
- [ ] Підтримка англійської мови
- [ ] Кешування готових PDF (не регенерувати якщо є)

---

## Команди для запуску

```bash
# Встановити залежності
pip install -r requirements.txt

# Запустити бот
python bot.py

# Запустити тести
python -m pytest tests/test_together.py -v

# Згенерувати тестовий Together PDF
python -c "
from services.pdf_together_report import generate_together_report
# ... (дивись tests/test_together.py для прикладу)
"
```

---

## .env (шаблон)

```
BOT_TOKEN=...
OPENAI_API_KEY=sk-...
GEOCODING_API_KEY=...
```
