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


def generate_psychological_report(astrology_data: dict) -> str:
    """Generate a personalized psychological report using GPT.

    Creates an AI-powered psychological interpretation of the natal chart,
    providing insights based on astrological placements combined with
    psychological analysis.

    Args:
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

    system_prompt = """Ви — український автор психологічного тексту для саморефлексії.

Ви не аналізуєте натальну карту. Джерело правди — лише масив facts у report_context_v1.

Правила:
- Не додавайте жодної риси, причини, події чи висновку, якого немає у facts.
- Evidence використовуйте лише для внутрішньої перевірки; службові поля читачеві не показуйте.
- Не ставте діагнозів, не прогнозуйте майбутнє, не вигадуйте біографію або травми.
- Астрологія подається як символічна рамка для саморефлексії, а не як науковий тест.
- Пишіть природною сучасною українською, тепло, конкретно і без містики.
- Уникайте категоричних фраз «ви завжди», «ви ніколи», «карта доводить».
- Гіпотетичні життєві приклади мають лише ілюструвати передані facts, а не створювати нові факти.
- Не згадуйте AI, JSON, Evidence Engine або внутрішні ідентифікатори."""

    birth_time_known = astrology_data.get("birth_time_known", False)
    birth_time_rules = """
Правила щодо часу народження:
- Не інтерпретуйте Асцендент.
- Не інтерпретуйте доми.
- Не вигадуйте жодних даних, що залежать від точного часу народження.
- Коротко вкажіть у розділі "Психологічний портрет", що інтерпретація спирається лише на положення, які не потребують точного часу народження.
"""
    if birth_time_known:
        birth_time_rules = ""

    user_prompt = f"""Підготуйте персональний текст українською мовою на основі цього єдиного дозволеного контексту:

{formatted_data}

Відповідайте на ці питання лише тоді, коли для них є достатньо evidence:
1. Хто ви в своїй основі?
2. Що вас рухає?
3. На які сильні сторони можна спиратися?
4. Які виклики або сліпі зони можуть з'являтися?
5. Як вас зазвичай сприймають інші люди?
6. Що варто спробувати далі?

Правила:
- Розділи є необов'язковими.
- Не створюйте порожніх розділів.
- Пропускайте розділ, якщо для нього недостатньо evidence.
- Ніколи не вигадуйте психологічні риси.
- Ніколи не вигадуйте життєві сценарії.
- Ніколи не інтерпретуйте інформацію, яка не підтримана report_context.
- Ніколи не повторюйте той самий факт у кількох розділах.
- Рекомендації мають спиратися лише на writer_guidance або прямо підтримані facts.
- Якщо для рекомендацій немає evidence, завершіть текст питанням для роздуму.
- Тон має бути теплим, природним, ясним і професійним.
- Без містичної мови.
- Без загальних гороскопних формулювань.
- Без перебільшеної впевненості.
- 650–850 слів.
- Жодного Markdown, маркерів, таблиць або HTML.
- Кожен змістовний висновок має прямо випливати з одного чи кількох facts.
- Не пояснюйте знаки та планети як навчальний матеріал.
- Де доречно, поєднуйте два факти в конкретну, але обережну послідовність: ситуація → внутрішня реакція → можливий спосіб дії.
- Якщо ви даєте питання для саморефлексії, дайте рівно три нумеровані запитання.
- Після третього запитання нічого не додавайте.

Перед відповіддю непомітно перевірте, що не додали жодної нової риси поза facts.
{birth_time_rules}"""

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    try:
        response = client.chat.completions.create(
            model=model_name,
            max_tokens=2000,
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
            temperature=0.45,
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
