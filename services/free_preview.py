"""Free, deterministic natal mini portrait used as the product demo."""

from __future__ import annotations

from .interpretations import SIGN_NAMES

PLANET_UA = {"sun": "Сонце", "moon": "Місяць", "venus": "Венера", "mars": "Марс"}
SIGN_HINTS = {
    "Ari": "діє прямо й швидко", "Tau": "шукає надійність і відчутний результат",
    "Gem": "пізнає світ через інформацію та діалог", "Can": "орієнтується на безпеку й близькість",
    "Leo": "потребує творчого самовираження", "Vir": "помічає деталі та прагне користі",
    "Lib": "шукає баланс і взаємність", "Sco": "переживає глибоко та не любить поверховості",
    "Sag": "потребує сенсу, свободи й розвитку", "Cap": "будує результат послідовно",
    "Aqu": "цінує незалежність мислення", "Pis": "тонко відчуває атмосферу й підтексти",
}


def _sign(chart: dict, planet: str) -> str | None:
    if planet == "sun":
        return chart.get("sun_sign")
    if planet == "moon":
        return chart.get("moon_sign")
    data = chart.get("planets", {}).get(planet, {})
    return data.get("sign") if isinstance(data, dict) else None


def build_free_preview(profile: dict, chart: dict) -> str:
    name = profile.get("name", "Ваш")
    lines = [f"🧭 Безкоштовний міні-портрет — {name}", ""]
    for planet in ("sun", "moon", "venus", "mars"):
        code = _sign(chart, planet)
        if code:
            lines.append(f"• {PLANET_UA[planet]} у знаку {SIGN_NAMES.get(code, code)} — {SIGN_HINTS.get(code, 'важлива частина вашого стилю') }.")
    asc = chart.get("ascendant_sign") if chart.get("birth_time_known") else None
    if asc:
        lines.append(f"• Асцендент у знаку {SIGN_NAMES.get(asc, asc)} — так ви найчастіше входите в нові ситуації та проявляєтеся назовні.")
    else:
        lines.append("• Асцендент не розраховано, оскільки точний час народження невідомий.")
    lines += [
        "",
        "Це коротке демо. Повний звіт пояснює взаємодію планет, домів та аспектів, містить графіки, життєві сценарії й персональні рекомендації.",
        "",
        "Акційна ціна будь-якого повного PDF — 99 ⭐.",
    ]
    return "\n".join(lines)
