"""Inner Compass Together -- PDF report renderer.

Produces a 12-16 page PDF for a couple, reusing all styles, fonts, colours,
and canvas helpers from pdf_report.py.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path

from reportlab.lib.units import mm
from reportlab.platypus import (
    NextPageTemplate, PageBreak, Paragraph, Spacer, Table, TableStyle,
)

from .pdf_report import (
    CONTENT_W, GOLD, GOLD_PALE, HAIRLINE, INK, INK_SOFT, MARGIN_X,
    MUTED, PAGE_H, PAGE_W, PAPER, PAPER_2,
    PDFGenerationError,
    _Marker, _build_styles, _clean_markdown, _escape, _hr, _load_fonts,
    _paint, _pull_quote, _rule, _tracked,
    BaseDocTemplate, Frame, PageTemplate,
)
from .glyphs import draw_constellation, draw_sign, scatter_stars
from .interpretations import SIGN_NAMES
from .ai_together import generate_together_report as _ai_generate_together
from .together_evidence import build_together_context
from .synastry import calculate_synastry
from .together_visuals import build_personal_final, build_visual_analysis

LOGGER = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"

SECTION_TITLES = [
    ("01", "Що вас притягує",               "Хімія і перше зближення"),
    ("02", "Емоційна близькість",           "Як ви відчуваєте одне одного"),
    ("03", "Як ви проявляєте любов",        "Мова любові кожного з вас"),
    ("04", "Як ви говорите і чуєте",        "Комунікація і порозуміння"),
    ("05", "Напруга і конфлікти",           "Де виникає тертя"),
    ("06", "Що тримає вас разом",           "Якір і стабільність"),
    ("07", "Чого один може не розуміти",    "Сліпі плями і несподіванки"),
    ("08", "Ваша сила як пари",             "Синергія і спільна потуга"),
    ("09", "Де потрібна увага",             "Що варто усвідомити"),
]

SECTION_TITLES_UA = [
    ("01", "Що вас притягує",                  "Хімія і перше зближення"),
    ("02", "Емоційна близькість",               "Як ви відчуваєте одне одного"),
    ("03", "Як ви проявляєте любов",            "Мова любові кожного з вас"),
    ("04", "Як ви говорите і чуєте одне одного","Комунікація і порозуміння"),
    ("05", "Напруга і конфлікти",                "Де виникає тертя"),
    ("06", "Що тримає вас разом",               "Якір і стабільність"),
    ("07", "Чого один може не розуміти про іншого","Сліпі плями"),
    ("08", "Ваша сила як пари",                  "Синергія і спільна потуга"),
    ("09", "Де потрібна увага",                  "Що варто усвідомити"),
]


def _draw_together_cover(canvas, doc, F, profile_a, profile_b, generated_at):
    _paint(canvas, PAPER)
    canvas.setFillAlpha(0.45)
    scatter_stars(canvas, 0, 0, PAGE_W, PAGE_H, GOLD_PALE, count=90, seed=77, max_r=1.0)
    canvas.setFillAlpha(1)

    _tracked(canvas, "INNER COMPASS TOGETHER", MARGIN_X, PAGE_H - 24 * mm,
             F["sans"], 8, 3.4, INK_SOFT)
    _tracked(canvas, generated_at, PAGE_W - MARGIN_X, PAGE_H - 24 * mm,
             F["sans"], 8, 1.2, MUTED, align="right")
    _rule(canvas, MARGIN_X, PAGE_H - 29 * mm, PAGE_W - MARGIN_X)

    sun_sign_a = profile_a.get("_chart_sun") or "Lib"
    cx, cy = PAGE_W / 2, PAGE_H - 108 * mm
    try:
        draw_constellation(canvas, sun_sign_a, cx, cy, 96 * mm, GOLD,
                           line_color=GOLD_PALE, star_scale=1.5)
        canvas.setFillAlpha(0.08)
        canvas.setStrokeAlpha(0.08)
        draw_sign(canvas, sun_sign_a, cx, cy, 78 * mm, GOLD, weight=1.0)
        canvas.setFillAlpha(1)
        canvas.setStrokeAlpha(1)
    except Exception:
        pass

    _tracked(canvas, "КАРТА ВАШИХ СТОСУНКІВ",
             PAGE_W / 2, PAGE_H - 176 * mm, F["sans"], 8.5, 4.2, GOLD, align="center")

    name_a = (profile_a.get("name") or "").strip()
    name_b = (profile_b.get("name") or "").strip()
    names_line = name_a + "  +  " + name_b
    canvas.setFont(F["serif"], 28)
    canvas.setFillColor(INK)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - 195 * mm, names_line)

    _rule(canvas, PAGE_W / 2 - 20 * mm, PAGE_H - 203 * mm,
          PAGE_W / 2 + 20 * mm, GOLD, 0.8)

    date_a = profile_a.get("birth_date", "")
    date_b = profile_b.get("birth_date", "")
    dates_line = "  .  ".join([p for p in (date_a, date_b) if p])
    _tracked(canvas, dates_line.upper(), PAGE_W / 2, PAGE_H - 212 * mm,
             F["sans"], 8, 1.6, MUTED, align="center")

    slot = CONTENT_W / 2.0
    base_y = 46 * mm
    for i, (profile, label) in enumerate([(profile_a, "ПЕРСОНА А"), (profile_b, "ПЕРСОНА Б")]):
        gx = MARGIN_X + slot * (i + 0.5)
        sign = profile.get("_chart_sun") or "Aqu"
        try:
            draw_sign(canvas, sign, gx, base_y + 14 * mm, 13 * mm, INK, weight=1.3)
            title = SIGN_NAMES.get(sign, sign)
        except Exception:
            title = ""
        canvas.setFont(F["serif"], 11)
        canvas.setFillColor(INK)
        canvas.drawCentredString(gx, base_y + 3 * mm, title)
        _tracked(canvas, label, gx, base_y - 3 * mm, F["sans"], 6.5, 2.6, MUTED,
                 align="center")

    _rule(canvas, MARGIN_X, 26 * mm, PAGE_W - MARGIN_X)
    _tracked(canvas, "МАТЕРІАЛ ДЛЯ ПАРИ", PAGE_W / 2, 19 * mm,
             F["sans"], 6.5, 2.4, MUTED, align="center")


def _draw_together_plate(canvas, doc, F, state):
    _paint(canvas, PAPER_2)
    canvas.setFillAlpha(0.55)
    scatter_stars(canvas, 0, 0, PAGE_W, PAGE_H, GOLD_PALE, count=90, seed=23, max_r=1.0)
    canvas.setFillAlpha(1)
    code = state.get("plate_sign")
    if code:
        try:
            draw_constellation(canvas, code, PAGE_W / 2, PAGE_H * 0.63, 120 * mm,
                               GOLD, line_color=GOLD_PALE, star_scale=1.6)
        except Exception:
            pass
    _rule(canvas, MARGIN_X, 26 * mm, PAGE_W - MARGIN_X, GOLD_PALE)
    _tracked(canvas, "INNER COMPASS TOGETHER", PAGE_W / 2, 19 * mm, F["sans"], 6.5, 3.0,
             MUTED, align="center")


def _draw_together_body(canvas, doc, F, state):
    _tracked(canvas, "INNER COMPASS TOGETHER", MARGIN_X, PAGE_H - 18 * mm,
             F["sans"], 6.5, 2.8, MUTED)
    running = (state.get("section") or "").upper()
    _tracked(canvas, running, PAGE_W - MARGIN_X, PAGE_H - 18 * mm,
             F["sans"], 6.5, 2.4, MUTED, align="right")
    _rule(canvas, MARGIN_X, PAGE_H - 21 * mm, PAGE_W - MARGIN_X)
    _rule(canvas, MARGIN_X, 20 * mm, PAGE_W - MARGIN_X)
    canvas.setFont(F["serif"], 9)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(PAGE_W / 2, 14 * mm, str(doc.page))


def _plate_together(number, title, subtitle, sign_code, styles, state):
    return [
        _Marker(state, plate_sign=sign_code),
        NextPageTemplate("plate"),
        PageBreak(),
        Spacer(1, 118 * mm),
        Paragraph(number, styles["plate_num"]),
        Paragraph(_escape(title), styles["plate_title"]),
        Spacer(1, 1 * mm),
        Paragraph(_escape(subtitle), styles["plate_sub"]),
        NextPageTemplate("body"),
        PageBreak(),
    ]


def _profile_page_together(profile_a, profile_b, chart_a, chart_b, styles, state):
    def person_block(profile, chart, label):
        name      = profile.get("name") or chart.get("name") or "---"
        birth_date = profile.get("birth_date") or chart.get("birth_date") or "---"
        birth_time = profile.get("birth_time") or chart.get("birth_time") or "---"
        birthplace = profile.get("birthplace") or chart.get("birthplace") or "---"
        sun  = chart.get("sun_sign") or "---"
        moon = chart.get("moon_sign") or "---"
        asc  = chart.get("ascendant_sign") or ("невідомий" if not chart.get("birth_time_known") else "---")
        sun_ua  = SIGN_NAMES.get(sun, sun)
        moon_ua = SIGN_NAMES.get(moon, moon)
        asc_ua  = SIGN_NAMES.get(asc, asc)
        return [
            Paragraph(label.upper(), styles["kicker"]),
            Paragraph(_escape(name), styles["h1"]),
            _hr(GOLD, "40%", 0.8, 2, 6),
            Paragraph("Дата: " + _escape(birth_date), styles["caption"]),
            Paragraph("Час: " + _escape(birth_time), styles["caption"]),
            Paragraph("Місто: " + _escape(birthplace), styles["caption"]),
            Spacer(1, 4 * mm),
            Paragraph("Сонце: " + _escape(sun_ua), styles["body"]),
            Paragraph("Місяць: " + _escape(moon_ua), styles["body"]),
            Paragraph("Асцендент: " + _escape(asc_ua), styles["body"]),
        ]

    col_w = (CONTENT_W - 6 * mm) / 2.0
    table = Table(
        [[person_block(profile_a, chart_a, "Персона А"),
          person_block(profile_b, chart_b, "Персона Б")]],
        colWidths=[col_w, col_w],
    )
    table.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LINEAFTER",   (0, 0), (0, -1), 0.4, HAIRLINE),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("RIGHTPADDING",(0, 0), (0, -1), 6 * mm),
        ("LEFTPADDING", (1, 0), (1, -1), 6 * mm),
        ("RIGHTPADDING",(1, 0), (1, -1), 0),
        ("TOPPADDING",  (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0),(-1, -1), 0),
    ]))
    return [
        _Marker(state, section="Профілі"),
        Paragraph("ВИ РАЗОМ", styles["kicker"]),
        Paragraph("Карта ваших стосунків", styles["display"]),
        _hr(GOLD, "18%", 1.2, 5, 9),
        Spacer(1, 6 * mm),
        table,
        Spacer(1, 10 * mm),
        Paragraph(
            "Цей звіт побудований на основі взаємодії двох натальних карт. "
            "Кожен аспект — це точка контакту між вашими внутрішніми темами. "
            "Тут немає вироку, лише матеріал для роздумів.",
            styles["caption"],
        ),
    ]


def _parse_sections_from_ai(ai_text: str) -> dict:
    """Parse AI text into {section_number: body_text} dict.

    Recognises headers like "Секція 01.", "Секція 3.", "### Секція 02" etc.
    Falls back to equal-chunk distribution if no headers found.
    """
    header_re = re.compile(
        r"(?:#{1,3}\s*)?[Сс]екці[яї]\s+(\d+)[^\n]*\n",
        re.IGNORECASE,
    )
    parts = header_re.split(ai_text)
    # parts: [preamble, num, body, num, body, ...]
    result = {}
    if len(parts) >= 3:
        i = 1
        while i + 1 < len(parts):
            num = int(parts[i])
            raw_body = parts[i + 1]
            # strip sub-headers like "Підсумок" / "Практика" that appear at end
            sub = re.split(r"(?:#{1,3}\s*)?(?:Підсумок|Практика)[^\n]*\n", raw_body, flags=re.IGNORECASE)
            body = sub[0].strip()
            result[num] = body
            i += 2
    if not result:
        # fallback: equal chunks
        blocks = [b.strip() for b in re.split(r"\n\s*\n", ai_text) if b.strip()]
        chunk = max(1, len(blocks) // 9)
        for idx in range(9):
            chunk_blocks = blocks[idx * chunk:(idx + 1) * chunk]
            result[idx + 1] = "\n\n".join(chunk_blocks)
    return result


def _parse_ai_sections(ai_text):
    """Legacy shim — prefer _parse_sections_from_ai."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", ai_text) if b.strip()]
    return blocks, ai_text


def _section_block(number, title, subtitle, body_text, styles, state):
    items = [
        _Marker(state, section=title),
        Paragraph(_escape(number), styles["kicker"]),
        Paragraph(_escape(title), styles["display"]),
        _hr(GOLD, "18%", 1.2, 5, 9),
        Paragraph(_escape(subtitle), styles["caption"]),
        Spacer(1, 6 * mm),
    ]
    blocks = [b.strip() for b in re.split(r"\n\s*\n", body_text or "") if b.strip()]
    if not blocks:
        blocks = [body_text.strip()] if body_text and body_text.strip() else ["Матеріал відсутній."]
    for i, block in enumerate(blocks):
        html = _clean_markdown(_escape(block)).replace("\n", "<br/>")
        if i == 0 and html.strip() and html.strip()[0].isalpha():
            st = styles["body_drop"]
            items.append(Spacer(1, 3 * mm))
            items.append(Paragraph(
                '<font name="' + st.bulletFontName + '" size="21" '
                'color="#' + GOLD.hexval()[2:] + '">' + html.strip()[0] + '</font>'
                + html.strip()[1:],
                st,
            ))
        else:
            items.append(Paragraph(html, styles["body"]))
    return items


def _final_and_disclaimer(ai_text, profile_a, profile_b, generated_at, styles, state):
    name_a = profile_a.get("name", "A")
    name_b = profile_b.get("name", "B")
    items = [
        PageBreak(),
        _Marker(state, section="Підсумок"),
        Paragraph("ПІДСУМОК", styles["kicker"]),
        Paragraph("П'ять речей, які важливо знати", styles["display"]),
        _hr(GOLD, "18%", 1.2, 5, 9),
        Spacer(1, 4 * mm),
    ]
    # Extract five-things from ai_text
    lines = [l.strip() for l in ai_text.splitlines() if l.strip()]
    numbered = [l for l in lines if re.match(r"^\d+[.)]", l)][:7]
    if not numbered:
        numbered = [
            "1. Відмінність у темпах не означає несумісності.",
            "2. Те, що дратує найбільше, часто відзеркалює власні теми.",
            "3. Конфлікт — це спосіб дізнатися одне одного глибше.",
            "4. Кожен у парі потребує власного простору.",
            "5. Стосунки — це жива система, яка змінюється разом із вами.",
        ]
    for line in numbered:
        clean = re.sub(r"^\d+[.)\s]+", "", line)
        items.append(Paragraph(_escape(clean), styles["item"], bulletText="---"))

    items += [
        Spacer(1, 10 * mm),
        Paragraph("ПРАКТИКА", styles["kicker"]),
        Paragraph("Що спробувати", styles["display"]),
        _hr(GOLD, "18%", 1.2, 5, 9),
        Spacer(1, 4 * mm),
        Paragraph("Раз на місяць говорити про те, що зараз добре.", styles["item"], bulletText="---"),
        Paragraph("Коли відчуваєте напругу — запитайте себе: чого я зараз насправді потребую?", styles["item"], bulletText="---"),
        Paragraph("Знайдіть спільну справу або ритуал, який буде тільки вашим.", styles["item"], bulletText="---"),
        Spacer(1, 14 * mm),
        _hr(HAIRLINE, "100%", 0.5, 0, 10),
        Paragraph(
            "Цей матеріал створений для саморефлексії та особистого розвитку пари. "
            "Він не є психологічною, медичною, юридичною або фінансовою рекомендацією. "
            "Астрологічні символи використані як мова для роздумів, а не як інструмент "
            "вимірювання або прогнозування стосунків.",
            styles["legal"],
        ),
        Spacer(1, 4 * mm),
        Paragraph(
            "Inner Compass Together  ·  " + name_a + " + " + name_b + "  ·  звіт створено " + generated_at,
            styles["caption"],
        ),
    ]
    return items


def _make_together_document(output_path, F, profile_a, profile_b, generated_at, state):
    frame_body = Frame(
        MARGIN_X, 26 * mm, CONTENT_W, PAGE_H - 26 * mm - 28 * mm,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="body",
    )
    frame_plate = Frame(
        MARGIN_X, 32 * mm, CONTENT_W, PAGE_H - 32 * mm - 20 * mm,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="plate",
    )
    frame_cover = Frame(
        MARGIN_X, 20 * mm, CONTENT_W, PAGE_H - 40 * mm,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="cover",
    )
    doc = BaseDocTemplate(
        str(output_path),
        pagesize=(PAGE_W, PAGE_H),
        leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=28 * mm, bottomMargin=26 * mm,
        title="Inner Compass Together",
        author="Inner Compass",
        subject="Карта ваших стосунків",
    )
    doc.addPageTemplates([
        PageTemplate(
            id="cover", frames=[frame_cover],
            onPage=lambda c, d: _draw_together_cover(c, d, F, profile_a, profile_b, generated_at),
        ),
        PageTemplate(
            id="plate", frames=[frame_plate],
            onPage=lambda c, d: _draw_together_plate(c, d, F, state),
        ),
        PageTemplate(
            id="body", frames=[frame_body],
            onPage=lambda c, d: _paint(c, PAPER),
            onPageEnd=lambda c, d: _draw_together_body(c, d, F, state),
        ),
    ])
    return doc


def generate_together_report(
    profile_a,
    profile_b,
    telegram_user_id,
    chart_a,
    chart_b,
):
    """Generate the Together PDF report for a couple.

    Args:
        profile_a: Profile dict for Person A.
        profile_b: Profile dict for Person B.
        telegram_user_id: Used in filename.
        chart_a: Natal chart for Person A (from calculate_natal_chart).
        chart_b: Natal chart for Person B.

    Returns:
        Path to the generated PDF.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_DIR / ("together_" + str(telegram_user_id) + ".pdf")
    if output_path.exists():
        output_path.unlink()

    F = _load_fonts()
    styles = _build_styles(F)
    state = {"section": "", "plate_sign": None}
    generated_at = datetime.now().strftime("%d.%m.%Y")

    profile_a = dict(profile_a)
    profile_b = dict(profile_b)
    profile_a["_chart_sun"] = chart_a.get("sun_sign")
    profile_b["_chart_sun"] = chart_b.get("sun_sign")

    synastry = calculate_synastry(chart_a, chart_b)
    context = build_together_context(chart_a, chart_b, profile_a, profile_b, synastry)
    ai_text = _ai_generate_together(context, profile_a, profile_b)

    plate_signs = ["Lib", "Can", "Leo", "Gem", "Sco", "Aqu", "Pis", "Tau", "Vir"]

    # Parse AI text by section headers
    section_bodies = _parse_sections_from_ai(ai_text)

    story = [NextPageTemplate("body"), PageBreak()]
    story += _profile_page_together(profile_a, profile_b, chart_a, chart_b, styles, state)
    story += build_visual_analysis(context, styles, state)
    story += _plate_together("", "ВИ РАЗОМ", "Карта взаємодії двох натальних карт",
                              "Lib", styles, state)

    for i, (num, title, subtitle) in enumerate(SECTION_TITLES):
        body_text = section_bodies.get(int(num), "")
        if i > 0:
            story.append(PageBreak())
        sign_code = plate_signs[i % len(plate_signs)]
        story += _section_block(num, title, subtitle, body_text, styles, state)

    story += build_personal_final(context, profile_a, profile_b, generated_at, styles, state)

    doc = _make_together_document(output_path, F, profile_a, profile_b, generated_at, state)
    try:
        doc.build(story)
    except Exception as exc:
        raise PDFGenerationError("ReportLab Together build failed: " + str(exc)) from exc

    LOGGER.info("Together report written to %s (%d synastry aspects)", output_path, len(synastry))
    return output_path
