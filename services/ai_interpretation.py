"""AI-powered psychological interpretation service using OpenAI.

This module generates personalized psychological reports based on natal chart data
using GPT, combining astrological insights with psychological analysis.
"""

import logging
import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

LOGGER = logging.getLogger(__name__)

# Fallback message if OpenAI is unavailable
FALLBACK_MESSAGE = """
Не вдалося отримати детальну AI-інтерпретацію.

Це демонстраційна версія звіту. На наступному етапі розробки тут буде додано
повну астрологічну інтерпретацію, персональні висновки та глибший аналіз вашого профілю.

Технічні дані вашої натальної карти представлені нижче.
"""


def _format_astrology_data_for_gpt(astrology_data: dict) -> str:
    """Build and serialize the constrained Interpretation Engine context."""
    import json

    from services.evidence_builder import build_report_context

    context = build_report_context(astrology_data)
    return json.dumps(context, ensure_ascii=False, indent=2, default=str)


def _first_name(profile: dict | None) -> str:
    """Extract a usable first name from the profile, or "" if unavailable."""
    if not isinstance(profile, dict):
        return ""
    raw = str(profile.get("name") or "").strip()
    if not raw:
        return ""
    first = raw.split()[0]
    # Guard against junk input ending up in the prompt.
    if len(first) < 2 or len(first) > 30 or any(ch.isdigit() for ch in first):
        return ""
    return first


def generate_psychological_report(astrology_data: dict, profile: dict | None = None) -> str:
    """Generate a personalized psychological report using GPT.

    Creates an AI-powered psychological interpretation of the natal chart,
    providing insights based on astrological placements combined with
    psychological analysis.

    Args:
        profile: Optional user profile; only "name" is used, to address the
            reader by name once at the start of the text.
        astrology_data: Dictionary containing natal chart data with keys:
            - sun_sign: Sun sign (e.g., "Pisces")
            - moon_sign: Moon sign (e.g., "Scorpio")
            - ascendant_sign: Ascendant sign (optional)
            - planets: Dict of planets and their placements
            - houses: List of house cusps
            - aspects: List of aspects
            - birth_time_known: Boolean indicating if birth time is known
            - warnings: List of warnings about the chart

    Returns:
        str: Personalized psychological report in Ukrainian (700-1000 words) or
            fallback message if API is unavailable.

    The report includes:
        1. Psychological portrait
        2. Main strengths
        3. Possible blind spots
        4. Emotional needs
        5. Communication style
        6. Practical recommendations
        7. Three questions for self-reflection
    """
    try:
        from openai import OpenAI
    except ImportError:
        LOGGER.warning("OpenAI library not installed. Using fallback message.")
        return FALLBACK_MESSAGE

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        LOGGER.warning("OPENAI_API_KEY not set in environment. Using fallback message.")
        return FALLBACK_MESSAGE

    try:
        client = OpenAI(api_key=api_key)
    except Exception as error:
        LOGGER.error("Failed to initialize OpenAI client: %s", error)
        return FALLBACK_MESSAGE

    # Format astrology data for the prompt
    formatted_data = _format_astrology_data_for_gpt(astrology_data)

    system_prompt = """Ви — український автор, який пише теплий особистий текст для саморефлексії.

Уявіть, що ви пишете людині, яку добре знаєте і поважаєте: спокійно, прямо, без відстані.

Джерело змісту — лише масив facts у report_context_v2.

Правила змісту:
- Не додавайте жодної риси, причини, події чи висновку, якого немає у facts.
- Evidence використовуйте лише для внутрішньої перевірки; службові поля читачеві не показуйте.
- Не ставте діагнозів, не прогнозуйте майбутнє, не вигадуйте біографію або травми.
- Астрологія тут — символічна мова для роздумів про себе, а не наукове вимірювання.
- Не згадуйте AI, JSON, Evidence Engine або внутрішні ідентифікатори.

Правила голосу:
- Звертайтесь на «ви», просто і по-людськи.
- Говоріть прямо: «вам важливо…», «ви помічаєте…», а не «можливо, вам буває властиво…».
- Один пом'якшувальний вислів («часто», «зазвичай», «схоже») — максимум один на абзац, і лише там, де він справді потрібен.
- Живі, конкретні деталі замість абстракцій: не «ви цінуєте комунікацію», а «вам легше, коли все проговорено вголос до кінця».
- Короткі речення поруч із довгими. Жодного канцеляриту й жодних русизмів.
- Ніякої містики, пафосу й гороскопних кліше на кшталт «зорі радять».
- Не пишіть «ви завжди» чи «ви ніколи» — люди складніші за це."""

    birth_time_known = astrology_data.get("birth_time_known", False)
    birth_time_rules = """
Правила щодо часу народження:
- Не інтерпретуйте Асцендент.
- Не інтерпретуйте доми.
- Не вигадуйте жодних даних, що залежать від точного часу народження.
- В одному реченні на початку тепло поясніть: точний час народження невідомий, тому текст спирається лише на те, що від нього не залежить.
"""
    if birth_time_known:
        birth_time_rules = ""

    name = _first_name(profile)
    name_clause = (
        f" для людини на ім'я {name}. Зверніться до неї на ім'я один раз, у першому реченні, "
        f"і більше ім'я не повторюйте. Далі —"
        if name
        else ""
    )

    user_prompt = f"""Напишіть{name_clause} персональний текст українською мовою на основі цього єдиного дозволеного джерела:

{formatted_data}

Ведіть читача через ці питання — але лише ті, для яких є достатньо evidence:
1. Хто ви у своїй основі?
2. Що вас рухає?
3. На що можна спиратися?
4. Що буває найважче?
5. Якими вас бачать інші?
6. Що варто спробувати далі?

Як писати:
- Суцільний текст абзацами. Без заголовків, без нумерації розділів, без списків.
- Починайте одразу з тексту про людину — без вступу про звіт чи карту.
- Абзаци по 3–6 речень, між абзацами порожній рядок.
- Де доречно, розгортайте факт у конкретну сцену: ситуація → що ви відчуваєте всередині → що з цим робити.
- Не пояснюйте, що означають знаки і планети. Пишіть про людину, а не про астрологію.
- Не повторюйте той самий факт двічі.

Межі:
- Кожен висновок має прямо випливати з facts. Нічого не вигадуйте — ні рис, ні життєвих сценаріїв.
- Пропускайте питання, якщо evidence бракує. Порожні розділи не створюйте.
- Рекомендації — лише з writer_guidance або прямо підтверджені facts.
- 650–850 слів.
- Жодного Markdown: ніяких зірочок, решіток, дефісів на початку рядка, таблиць чи HTML.

Завершення:
- Якщо для рекомендацій є evidence, дайте їх у тексті, а потім рівно три запитання для роздуму, кожне з нового рядка, пронумеровані 1. 2. 3.
- Якщо evidence для рекомендацій немає, просто закінчіть цими трьома запитаннями.
- Після третього запитання не додавайте нічого.

Перед відповіддю мовчки перевірте: чи не з'явилася жодна риса, якої немає у facts.
{birth_time_rules}"""

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    try:
        response = client.chat.completions.create(
            model=model_name,
            # Ukrainian tokenizes poorly (~3 tokens/word), so 850 words needs
            # generous headroom or the closing questions get truncated away.
            max_tokens=3000,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            # Slightly higher than the old 0.45: the text was accurate but stiff.
            temperature=0.7,
        )

        report_text = response.choices[0].message.content
        if not isinstance(report_text, str) or not report_text.strip():
            LOGGER.warning("OpenAI response content is empty. Using fallback message.")
            return FALLBACK_MESSAGE

        report_text = report_text.strip()
        LOGGER.info("Successfully generated psychological report via OpenAI")
        return report_text

    except Exception as error:
        LOGGER.exception("Failed to generate psychological report: %s", error)
        return FALLBACK_MESSAGE


def generate_year_sections(year_context: dict, profile: dict | None = None) -> dict[str, str]:
    """Generate 4 thematic year-ahead sections using GPT.

    Returns dict with keys: career, relationships, health, growth.
    Each value is a Ukrainian paragraph (200-300 words).
    Falls back to template text if OpenAI unavailable.
    """
    import json as _json
    from knowledge.transit_rules import (
        ASPECT_UA, PLANET_GUIDANCE, PLANET_UA, POINT_UA, THEME_ADVICE,
    )

    def _format_events(events: list) -> str:
        if not events:
            return "Активних транзитів у цьому напрямку немає."
        lines = []
        for e in events[:4]:
            planet_ua = PLANET_UA.get(e["planet"], e["planet"])
            aspect_ua = ASPECT_UA.get(e["aspect"], e["aspect"])
            point_ua = POINT_UA.get(e["natal_point"], e["natal_point"])
            guidance = PLANET_GUIDANCE.get(e["planet"], {}).get(e["aspect"], "")
            r = " (ретроградний)" if e.get("retrograde") else ""
            lines.append(
                f"- {planet_ua}{r} {aspect_ua} натальним {point_ua} "
                f"(пік: {e['peak_month']}, інтенсивність: {e['intensity']}/3). {guidance}"
            )
        return "\n".join(lines)

    themes = year_context.get("themes", {})
    period = year_context.get("period", {})
    natal = year_context.get("natal_summary", {})

    # Build prompt context
    context_text = f"""
Натальна карта: Сонце — {natal.get("sun_sign")}, Місяць — {natal.get("moon_sign")}, Асцендент — {natal.get("ascendant_sign")}.
Період: {period.get("start")} — {period.get("end")}.

КАР\'ЄРА І СПРАВА:
{_format_events(themes.get("career", []))}

СТОСУНКИ І БЛИЗЬКІСТЬ:
{_format_events(themes.get("relationships", []))}

РЕСУРС І ЗДОРОВ\'Я:
{_format_events(themes.get("health", []))}

РОЗВИТОК І ЗМІНИ:
{_format_events(themes.get("growth", []))}
"""

    name = _first_name(profile) if profile else ""
    name_clause = f" для {name}" if name else ""

    system_prompt = """Ви — автор теплих персональних текстів про астрологічні транзити.

Пишіть українською, як досвідчений консультант, який поважає людину і не лякає її.
Транзити — це не вирок, а клімат. Завдання тексту: допомогти людині зорієнтуватися.

Правила:
- Кожна секція — 3-4 абзаци (180-250 слів)
- Конкретні поради, прив'язані до транзитів
- Без містики, без "зорі кажуть", без гороскопної мови
- Транзити з інтенсивністю 3 — основна увага, 2 — підтримка, 1 — фон
- Не перераховуйте транзити як список — вплітайте їх в текст природно
- Ретроградні планети = сповільнення, переосмислення, повернення до старого
- Якщо транзитів немає — напишіть про стабільний або тихий рік у цій темі"""

    user_prompt = f"""Напишіть річний огляд{name_clause} на основі транзитів.

{context_text}

Поверніть ТІЛЬКИ JSON такого формату (без markdown, без ```):
{{
  "career": "текст...",
  "relationships": "текст...",
  "health": "текст...",
  "growth": "текст..."
}}

Кожна секція — 180-250 слів, українською, суцільним текстом абзацами."""

    fallback = {
        "career": "Цей рік активує вашу сферу реалізації. Звертайте увагу на нові контакти і можливості, що з'являтимуться несподівано. Хороший час перевірити, чи відповідає поточна робота вашим справжнім цілям.",
        "relationships": "У стосунках цей рік може принести як нові зустрічі, так і переосмислення існуючих зв'язків. Те, що давно мало бути сказане — знайде спосіб прозвучати.",
        "health": "Ресурс потребує уваги. Режим відновлення важливий навіть тоді, коли здається, що все добре. Фізична активність буде хорошим буфером.",
        "growth": "Рік внутрішньої роботи. Деякі речі завершаться — не тримайте їх силою. Те, що народжується замість них, варте довіри.",
    }

    try:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return fallback
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            max_tokens=3000,
            temperature=0.65,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content.strip()
        import json as _json2
        data = _json2.loads(raw)
        return {k: str(data.get(k, fallback[k])) for k in ("career", "relationships", "health", "growth")}
    except Exception as err:
        LOGGER.warning("Year report GPT failed: %s", err)
        return fallback


def _build_theme_text(theme: str, events: list) -> str:
    """Build rich text for a theme from its transit events (rule-based, no GPT needed)."""
    from knowledge.transit_rules import GENERIC_PARAGRAPHS, TRANSIT_PARAGRAPHS

    paragraphs = []
    used_keys = set()

    # Sort events by intensity descending
    for event in sorted(events, key=lambda e: -e.get("intensity", 1)):
        key = (event["planet"], event["aspect"], event["natal_point"])
        if key in used_keys:
            continue
        used_keys.add(key)

        entry = TRANSIT_PARAGRAPHS.get(key, {})
        if entry and theme in entry:
            paragraphs.extend(entry[theme])
            if len(paragraphs) >= 4:
                break

    # Also check other natal points for this planet+aspect if we have space
    if len(paragraphs) < 3:
        for event in sorted(events, key=lambda e: -e.get("intensity", 1)):
            for key, entry in TRANSIT_PARAGRAPHS.items():
                if key[0] == event["planet"] and key[1] == event["aspect"] and key in used_keys:
                    continue
                if not entry or theme not in entry:
                    continue
                used_keys.add(key)
                paragraphs.extend(entry[theme])
                if len(paragraphs) >= 3:
                    break
            if len(paragraphs) >= 3:
                break

    # Fill with generic if still short
    if len(paragraphs) < 2:
        paragraphs.extend(GENERIC_PARAGRAPHS.get(theme, []))

    return "\n\n".join(paragraphs[:5])


def generate_year_sections(year_context: dict, profile: dict | None = None) -> dict[str, str]:
    """Generate 4 thematic year-ahead sections.

    First tries GPT for a richer, more personalized output.
    Falls back to rule-based rich text generation if GPT unavailable.
    """
    import json as _json
    from knowledge.transit_rules import (
        ASPECT_UA, PLANET_UA, POINT_UA, THEME_UA,
    )

    themes = year_context.get("themes", {})
    period = year_context.get("period", {})
    natal = year_context.get("natal_summary", {})

    # Always build rule-based text first (used as fallback and GPT grounding)
    rule_based = {
        theme: _build_theme_text(theme, themes.get(theme, []))
        for theme in ("career", "relationships", "health", "growth")
    }

    def _format_events_for_gpt(events: list) -> str:
        if not events:
            return "Активних транзитів у цьому напрямку немає."
        lines = []
        for e in events[:5]:
            planet_ua = PLANET_UA.get(e["planet"], e["planet"])
            aspect_ua = ASPECT_UA.get(e["aspect"], e["aspect"])
            point_ua = POINT_UA.get(e["natal_point"], e["natal_point"])
            r = " (ретроградний)" if e.get("retrograde") else ""
            lines.append(
                f"- {planet_ua}{r} {aspect_ua} натальним {point_ua} "
                f"(пік: {e['peak_month']}, інтенсивність: {e['intensity']}/3)"
            )
        return "\n".join(lines)

    try:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return rule_based

        client = OpenAI(api_key=api_key)
        name = _first_name(profile) if profile else ""
        name_clause = f" для {name}" if name else ""

        context_text = f"""Натальна карта: Сонце — {natal.get("sun_sign")}, Місяць — {natal.get("moon_sign")}, Асцендент — {natal.get("ascendant_sign")}.
Період: {period.get("start")} — {period.get("end")}.

КАР\'ЄРА І СПРАВА:
{_format_events_for_gpt(themes.get("career", []))}
Підготовлений текст (розшир та покращ):
{rule_based["career"]}

СТОСУНКИ І БЛИЗЬКІСТЬ:
{_format_events_for_gpt(themes.get("relationships", []))}
Підготовлений текст:
{rule_based["relationships"]}

РЕСУРС І ЗДОРОВ\'Я:
{_format_events_for_gpt(themes.get("health", []))}
Підготовлений текст:
{rule_based["health"]}

РОЗВИТОК І ЗМІНИ:
{_format_events_for_gpt(themes.get("growth", []))}
Підготовлений текст:
{rule_based["growth"]}"""

        system_prompt = """Ви — автор персональних астрологічних текстів. Пишете теплою, прямою українською мовою.

Правила:
- Розширте та покращте підготовлений текст для кожної секції
- Кожна секція — 350-450 слів, суцільним текстом абзацами
- Конкретні рекомендації з реальними прикладами (наприклад: "якщо ви в найманій роботі — X; якщо у власному проєкті — Y")
- Без містики, без "зорі кажуть", без загальних фраз
- Правильна сучасна українська орфографія: проєкт, відповідальність, пов'язаний тощо
- Транзити вплітайте природно, не переліком
- Повертайте тільки JSON без markdown"""

        user_prompt = f"""Напишіть річний огляд{name_clause}.

{context_text}

Формат відповіді — тільки JSON (без ``` і без пояснень):
{{
  "career": "текст...",
  "relationships": "текст...",
  "health": "текст...",
  "growth": "текст..."
}}"""

        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            max_tokens=4000,
            temperature=0.65,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = _json.loads(raw)
        return {k: str(data.get(k, rule_based[k])) for k in ("career", "relationships", "health", "growth")}

    except Exception as err:
        LOGGER.warning("Year report GPT failed: %s", err)
        return rule_based
