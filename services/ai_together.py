"""AI writer for Inner Compass Together report."""

from __future__ import annotations
import logging
import os
import re

LOGGER = logging.getLogger(__name__)

ASPECT_UA = {
    "conjunction": "spoluchennia",
    "opposition": "opozytsiia",
    "trine": "tryhon",
    "square": "kvadrat",
    "sextile": "sekstyl",
}

PLANET_UA = {
    "sun": "Sontse", "moon": "Misiats", "mercury": "Merkuriy",
    "venus": "Venera", "mars": "Mars", "jupiter": "Yupiter",
    "saturn": "Saturn", "uranus": "Uran", "neptune": "Neptun",
    "pluto": "Pluton", "ascendant": "Atstendent",
}

THEME_UA = {
    "attraction": "Що вас притягує",
    "emotional": "Емоційна близькість",
    "communication": "Komunikatsiia",
    "love_style": "Mova liubovi",
    "conflict": "Напруга і конфлікти",
    "stability": "Stabilnist",
    "growth": "Rist",
}

_NL = chr(10)

_FALLBACK = _NL.join([
    "Секція 01. Що вас притягує",
    "",
    "Mizh vamy ie spravzhnie prytiahannia na rivni vnutrishnoi rezonannosti.",
    "Odyn pryvnosyt u paru te, choho brakuie inshomu: rizni tempy,",
    "rizne spryiniattia, ale razom tsi vidminnosti stvoriuiut zhyvyi obmin.",
    "",
    "Секція 02. Емоційна близькість",
    "",
    "Емоційна взаємодія потребує часу і уважності. Те, як один проявляє",
    "pochuttia, mozhe spochatku zdavatys inshomu nezrozumilym. Ale za tsym --",
    "ne vidsutniuet pochuttiv, a vidminnist u movi emotsii.",
    "",
    "Секція 03. Як ви проявляєте любов",
    "",
    "Kozhen u pari vyrazhaie liubov po-svoiemu. Odyn cherez dii,",
    "inshyi cherez slova i prysutnist. Vazhlyvo pobachyty tsi proiavy.",
    "",
    "Секція 04. Як ви говорите і чуєте одне одного",
    "",
    "Komunikatsiia -- kliuchova tochka. U vas ie potentsial dlia vidkrytoho",
    "dialohu, ale vin potrebuie usvidomlenosti.",
    "",
    "Секція 05. Напруга і конфлікти",
    "",
    "U bud-yakykh stosunkakh ie tochky tertia. Vony ne oznachaiut nesumisnosti.",
    "",
    "Секція 06. Що тримає вас разом",
    "",
    "Ie shchos stabilne: spilni tsinnosti abo vidchuttia nadiinosti poruch.",
    "",
    "Секція 07. Чого один може не розуміти про іншого",
    "",
    "Kozhna liudyna prynosyt svoiu vnutrishniu lohiku.",
    "Zatsikavlenist zamist otsinky dopomozhe bilshe za vse.",
    "",
    "Секція 08. Ваша сила як пари",
    "",
    "Razom vy zdatni na bilshe. Ie sfery, de vashi yakosti vzaiemno pidsiluiuiutsia.",
    "",
    "Секція 09. Де потрібна увага",
    "",
    "Vazhlyvo rehuliarno perevirniaty, chy komfortno obydva pochuvaiutsia.",
    "",
    "P'iat rechei, yaki vazhlyvo znaty:",
    "1. Vidminnist u tempakh ne oznachaie nesumisnosti.",
    "2. Te, shcho dratuie, chasto vidzerkalniuie vlasni temy.",
    "3. Konflikt -- sposib diznatysia odne odnoho hlybshe.",
    "4. Kozhen potrebuie vlasnoho prostoru.",
    "5. Stosunky -- zhyva systema.",
    "",
    "Що спробувати:",
    "- Raz na misiats hovority pro te, shcho dobre.",
    "- Koly napruha -- zapytaite sebe: shcho ia potrebuiu?",
    "- Znaidity spilnu spravu, yaka bude tilky vashym.",
])


def _format_aspects(aspects, max_items=8):
    if not aspects:
        return "Aspektiv nemaie."
    rows = []
    for asp in aspects[:max_items]:
        pa = PLANET_UA.get(asp.get("planet_a", ""), asp.get("planet_a", ""))
        pb = PLANET_UA.get(asp.get("planet_b", ""), asp.get("planet_b", ""))
        atype = ASPECT_UA.get(asp.get("aspect", ""), asp.get("aspect", ""))
        rows.append(f"  - {pa} (A) {atype} {pb} (B), orb {asp.get('orb', 0):.1f}")
    return _NL.join(rows)


def _build_context_text(context, profile_a, profile_b):
    name_a = context.get("person_a", {}).get("name") or profile_a.get("name", "A")
    name_b = context.get("person_b", {}).get("name") or profile_b.get("name", "B")
    pa = context.get("person_a", {})
    pb = context.get("person_b", {})
    themes = context.get("themes", {})
    parts = [
        "PERSONS:",
        f"  {name_a}: Sun={pa.get('sun','')}, Moon={pa.get('moon','')}, Asc={pa.get('ascendant') or 'unknown'}",
        f"  {name_b}: Sun={pb.get('sun','')}, Moon={pb.get('moon','')}, Asc={pb.get('ascendant') or 'unknown'}",
        "",
        "TOP ASPECTS:",
        _format_aspects(context.get("strongest_aspects", []), 10),
        "",
    ]
    for key, title in THEME_UA.items():
        asp_list = themes.get(key, [])
        if asp_list:
            parts.append(title.upper() + ":")
            parts.append(_format_aspects(asp_list, 5))
            parts.append("")
    return _NL.join(parts)


def generate_together_report(context: dict, profile_a: dict, profile_b: dict) -> str:
    """Generate Together report text using GPT; fallback if unavailable."""
    try:
        from openai import OpenAI
    except ImportError:
        return _FALLBACK.strip()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _FALLBACK.strip()

    try:
        client = OpenAI(api_key=api_key)
    except Exception as err:
        LOGGER.error("OpenAI client init failed: %s", err)
        return _FALLBACK.strip()

    name_a = context.get("person_a", {}).get("name") or profile_a.get("name", "A")
    name_b = context.get("person_b", {}).get("name") or profile_b.get("name", "B")
    evidence_text = _build_context_text(context, profile_a, profile_b)

    system_prompt = (
        "Ty pyshesh personalnyi zvit Inner Compass Together -- analiz vzaiemodii dvokh kart." + _NL
        + "Ton: liudskyi, pylyi, bez ezoteryki ta fatalizmu." + _NL
        + "Spyraisia TILKY na nadani structured evidence. Ne vyhadvui aspekty." + _NL
        + "Ne vykorystovuy: zirky hovoriath, karmichna liubov, sumysnist X%."
    )

    section_list = _NL.join([
        "Секція 01. Що вас притягує",
        "Секція 02. Емоційна близькість",
        "Секція 03. Як ви проявляєте любов",
        "Секція 04. Як ви говорите і чуєте одне одного",
        "Секція 05. Напруга і конфлікти",
        "Секція 06. Що тримає вас разом",
        "Секція 07. Чого один може не розуміти про іншого",
        "Секція 08. Ваша сила як пари",
        "Секція 09. Де потрібна увага",
    ])

    user_prompt = (
        f"Napyshy zvit Inner Compass Together dlia {name_a} i {name_b}:" + _NL + _NL
        + evidence_text + _NL + _NL
        + "Struktura:" + _NL
        + section_list + _NL + _NL
        + "Після 9 секцій додай: П'ять речей, які важливо знати + Що спробувати." + _NL
        + "Kozhen sektsiia -- 120-180 sliv. Bez markdown."
    )

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            max_tokens=4500,
            temperature=0.7,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = response.choices[0].message.content
        if not isinstance(text, str) or not text.strip():
            return _FALLBACK.strip()
        LOGGER.info("Together report generated via GPT for %s + %s", name_a, name_b)
        return text.strip()
    except Exception as err:
        LOGGER.warning("Together GPT failed: %s -- using fallback.", err)
        return _FALLBACK.strip()
