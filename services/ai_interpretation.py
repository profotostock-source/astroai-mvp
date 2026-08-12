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

Джерело змісту — лише масив facts у report_context_v1.

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
