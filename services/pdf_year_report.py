"""Inner Compass — Year Ahead PDF report.

Separate product: 4 thematic sections (career, relationships, health, growth)
based on real planetary transits to the natal chart.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, HRFlowable, NextPageTemplate,
    PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

from .pdf_report import (
    PDFGenerationError, _load_fonts, _build_styles, _tracked, _rule,
    _paint, _escape, _clean_markdown, _hr, _pull_quote, _Marker,
    PAPER, PAPER_2, INK, INK_SOFT, MUTED, GOLD, GOLD_PALE, HAIRLINE, COOL,
    PAGE_W, PAGE_H, MARGIN_X, CONTENT_W,
)
from .glyphs import draw_constellation, draw_sign, scatter_stars, SIGN_ELEMENT
from .interpretations import SIGN_NAMES

LOGGER = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"

THEME_ICONS = {
    "career":       "Gem",   # Gemini — communication, work
    "relationships": "Lib",  # Libra — balance, partnership
    "health":       "Tau",   # Taurus — body, stability
    "growth":       "Aqu",   # Aquarius — evolution, freedom
}

THEME_UA = {
    "career":        "Кар’єра і справа",
    "relationships": "Стосунки і близькість",
    "health":        "Ресурс і здоров’я",
    "growth":        "Розвиток і зміни",
}

THEME_SUBTITLES = {
    "career":        "Що активується у сфері роботи та реалізації",
    "relationships": "Що рухається у близькості й контактах",
    "health":        "Де варто стежити за ресурсом",
    "growth":        "Де йде внутрішня робота",
}


def _draw_year_cover(canvas, doc, F, profile, period, signs):
    sun_sign, moon_sign, asc_sign = signs
    _paint(canvas, PAPER)

    canvas.setFillAlpha(0.4)
    scatter_stars(canvas, 0, 0, PAGE_W, PAGE_H, GOLD_PALE, count=120, seed=42, max_r=1.0)
    canvas.setFillAlpha(1)

    _tracked(canvas, "INNER COMPASS", MARGIN_X, PAGE_H - 24 * mm, F["sans"], 8, 3.4, INK_SOFT)
    _tracked(canvas, period["start"] + " — " + period["end"],
             PAGE_W - MARGIN_X, PAGE_H - 24 * mm, F["sans"], 8, 1.2, MUTED, align="right")
    _rule(canvas, MARGIN_X, PAGE_H - 29 * mm, PAGE_W - MARGIN_X)

    # Large constellation
    cx, cy = PAGE_W / 2, PAGE_H - 105 * mm
    if sun_sign:
        draw_constellation(canvas, sun_sign, cx, cy, 96 * mm, GOLD,
                           line_color=GOLD_PALE, star_scale=1.5)
        canvas.setFillAlpha(0.08)
        canvas.setStrokeAlpha(0.08)
        draw_sign(canvas, sun_sign, cx, cy, 80 * mm, GOLD, weight=1.0)
        canvas.setFillAlpha(1)
        canvas.setStrokeAlpha(1)

    # Title
    _tracked(canvas, "РІЧНИЙ ЗВІТ",
             PAGE_W / 2, PAGE_H - 178 * mm, F["sans"], 8.5, 4.2, GOLD, align="center")


    name = (profile.get("name") or "").strip()
    canvas.setFont(F["serif"], 32)
    canvas.setFillColor(INK)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - 196 * mm, name)

    _rule(canvas, PAGE_W / 2 - 16 * mm, PAGE_H - 204 * mm, PAGE_W / 2 + 16 * mm, GOLD, 0.8)

    birth_date = profile.get("birth_date", "")
    birth_place = profile.get("birthplace", "")
    line = "  ·  ".join([p for p in (birth_date, birth_place) if p])
    _tracked(canvas, line.upper(), PAGE_W / 2, PAGE_H - 213 * mm,
             F["sans"], 8, 1.6, MUTED, align="center")

    # Four theme icons at bottom
    themes_row = ["career", "relationships", "health", "growth"]
    slot = CONTENT_W / 4.0
    base_y = 46 * mm
    for i, theme in enumerate(themes_row):
        gx = MARGIN_X + slot * (i + 0.5)
        code = THEME_ICONS.get(theme, "Gem")
        draw_sign(canvas, code, gx, base_y + 10 * mm, 9 * mm, GOLD, weight=1.2)
        _tracked(canvas, THEME_UA.get(theme, theme).upper()[:8],
                 gx, base_y - 1 * mm, F["sans"], 6, 2.0, MUTED, align="center")

    _rule(canvas, MARGIN_X, 26 * mm, PAGE_W - MARGIN_X)
    _tracked(canvas, "ПЕРСОНАЛЬНИЙ ПРОГНОЗ НА ОСНОВІ ТРАНЗИТІВ",
             PAGE_W / 2, 19 * mm, F["sans"], 6.5, 2.4, MUTED, align="center")


def _draw_plate_year(canvas, doc, F, state):
    _paint(canvas, PAPER_2)
    canvas.setFillAlpha(0.5)
    scatter_stars(canvas, 0, 0, PAGE_W, PAGE_H, GOLD_PALE, count=100, seed=77, max_r=1.0)
    canvas.setFillAlpha(1)

    code = state.get("plate_sign")
    if code:
        draw_constellation(canvas, code, PAGE_W / 2, PAGE_H * 0.63, 110 * mm,
                           GOLD, line_color=GOLD_PALE, star_scale=1.5)

    _rule(canvas, MARGIN_X, 26 * mm, PAGE_W - MARGIN_X, GOLD_PALE)
    _tracked(canvas, "INNER COMPASS", PAGE_W / 2, 19 * mm, F["sans"], 6.5, 3.0,
             MUTED, align="center")


def _draw_body_year(canvas, doc, F, state):
    _tracked(canvas, "INNER COMPASS", MARGIN_X, PAGE_H - 18 * mm, F["sans"], 6.5, 2.8, MUTED)
    running = (state.get("section") or "").upper()
    _tracked(canvas, running, PAGE_W - MARGIN_X, PAGE_H - 18 * mm, F["sans"], 6.5, 2.4,
             MUTED, align="right")
    _rule(canvas, MARGIN_X, PAGE_H - 21 * mm, PAGE_W - MARGIN_X)
    _rule(canvas, MARGIN_X, 20 * mm, PAGE_W - MARGIN_X)
    canvas.setFont(F["serif"], 9)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(PAGE_W / 2, 14 * mm, str(doc.page))


def _theme_plate(theme: str, number: str, styles: dict, state: dict) -> list:
    icon_sign = THEME_ICONS.get(theme, "Gem")
    title = THEME_UA.get(theme, theme)
    subtitle = THEME_SUBTITLES.get(theme, "")
    return [
        _Marker(state, plate_sign=icon_sign),
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


def _theme_section(theme: str, text: str, events: list, styles: dict, state: dict) -> list:
    from knowledge.transit_rules import ASPECT_UA, PLANET_UA, POINT_UA, get_moment_desc

    title = THEME_UA.get(theme, theme)
    items: list = [
        _Marker(state, section=title),
        Paragraph(_escape(title), styles["display"]),
        _hr(GOLD, "18%", 1.2, 5, 9),
    ]

    # Main text blocks — fix straight quotes to guillemets before rendering
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text or "") if b.strip()]
    for i, block in enumerate(blocks):
        block = re.sub(r'"([^"]+)"', '«\\1»', block)
        html = _clean_markdown(_escape(block)).replace("\n", "<br/>")
        if i == 0:
            st = styles["body_drop"]
            stripped = html.lstrip()
            if stripped and stripped[0].isalpha():
                items.append(Spacer(1, 4 * mm))
                items.append(Paragraph(
                    f'<font name="{st.bulletFontName}" size="21" '
                    f'color="#{GOLD.hexval()[2:]}">{stripped[0]}</font>'
                    f'{stripped[1:]}', st,
                ))
                continue
        items.append(Paragraph(html, styles["body"]))

    # ── Ключові моменти — expanded transit cards ──────────────────────────────
    if events:
        items += [
            Spacer(1, 6 * mm),
            Paragraph("КЛЮЧОВІ МОМЕНТИ", styles["kicker"]),
            _hr(GOLD, "100%", 0.7, 2, 5),
        ]
        for ev in events[:5]:
            planet_ua = PLANET_UA.get(ev["planet"], ev["planet"])
            aspect_ua = ASPECT_UA.get(ev["aspect"], ev["aspect"])
            point_ua  = POINT_UA.get(ev["natal_point"], ev["natal_point"])
            retro     = " R" if ev.get("retrograde") else ""
            intensity = ev.get("intensity", 1)
            dots      = "●" * intensity + "○" * (3 - intensity)
            moment_title, moment_desc = get_moment_desc(
                ev["planet"], ev["aspect"], ev["natal_point"]
            )

            # Date header + intensity dots
            items.append(Spacer(1, 5 * mm))
            items.append(Paragraph(
                _escape(ev["peak_month"]) + "  " + dots,
                styles["kicker"],
            ))
            # Astrological signature (planet aspect natal_point)
            items.append(Paragraph(
                _escape(f"{planet_ua}{retro} {aspect_ua} {point_ua}"),
                styles["caption"],
            ))
            # Card title — bold
            items.append(Paragraph(
                "<b>" + _escape(moment_title) + "</b>",
                styles["body"],
            ))
            # Card description paragraph
            if moment_desc:
                items.append(Paragraph(_escape(moment_desc), styles["body"]))
            items.append(_hr(HAIRLINE, "100%", 0.4, 4, 2))

    return items


def _intro_page(profile: dict, year_context: dict, styles: dict, state: dict) -> list:
    period = year_context.get("period", {})
    natal = year_context.get("natal_summary", {})
    total_events = sum(len(v) for v in year_context.get("themes", {}).values())

    sun_ua = SIGN_NAMES.get(natal.get("sun_sign", ""), natal.get("sun_sign", ""))
    moon_ua = SIGN_NAMES.get(natal.get("moon_sign", ""), natal.get("moon_sign", ""))
    asc_ua = SIGN_NAMES.get(natal.get("ascendant_sign", ""), natal.get("ascendant_sign", ""))

    return [
        _Marker(state, section="Інформація"),
        Paragraph("РІЧНИЙ ОГЛЯД ДЛЯ", styles["kicker"]),
        Paragraph(_escape(profile.get("name") or ""), styles["display"]),
        _hr(GOLD, "18%", 1.2, 5, 9),
        Spacer(1, 3 * mm),
        Paragraph(
            f"Натальна карта: Сонце — {sun_ua}, "
            f"Місяць — {moon_ua}, Асцендент — {asc_ua}.",
            styles["body"],
        ),
        Paragraph(
            f"Період: {period.get('start', '')} — {period.get('end', '')}. "
            f"Знайдено {total_events} активних транзитів.",
            styles["caption"],
        ),
        Spacer(1, 6 * mm),
        _pull_quote(
            "Цей звіт побудовано на основі реального руху планет у 2026–2027 роках "
            "відносно вашої натальної карти. "
            "Транзити — це не вирок, а клімат. "
            "Вони створюють умови — рішення залишається за вами.",
            styles,
        ),
    ]


def _make_year_doc(output_path, F, profile, period, signs, state):
    frame_body = Frame(MARGIN_X, 26 * mm, CONTENT_W, PAGE_H - 26 * mm - 28 * mm,
                       leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="body")
    frame_plate = Frame(MARGIN_X, 32 * mm, CONTENT_W, PAGE_H - 32 * mm - 20 * mm,
                        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="plate")
    frame_cover = Frame(MARGIN_X, 20 * mm, CONTENT_W, PAGE_H - 40 * mm,
                        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="cover")

    doc = BaseDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=28 * mm, bottomMargin=26 * mm,
        title="Inner Compass — річний звіт",
        author="Inner Compass",
    )
    doc.addPageTemplates([
        PageTemplate("cover", frames=[frame_cover],
                     onPage=lambda c, d: _draw_year_cover(c, d, F, profile, period, signs)),
        PageTemplate("plate", frames=[frame_plate],
                     onPage=lambda c, d: _draw_plate_year(c, d, F, state)),
        PageTemplate("body", frames=[frame_body],
                     onPage=lambda c, d: _paint(c, PAPER),
                     onPageEnd=lambda c, d: _draw_body_year(c, d, F, state)),
    ])
    return doc


def generate_year_report(
    profile: dict,
    telegram_user_id: int,
    astrology_data: dict,
    start_date: date | None = None,
) -> Path:
    """Generate the Year Ahead PDF report.

    Args:
        profile: User profile (name, birth_date, birthplace).
        telegram_user_id: Used for filename.
        astrology_data: Natal chart data from calculate_natal_chart.
        start_date: Start of the year period (default: today).

    Returns:
        Path to the generated PDF.
    """
    from datetime import timedelta
    from services.transits import build_year_context
    from services.ai_interpretation import generate_year_sections

    if start_date is None:
        start_date = date.today()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_DIR / f"year_report_{telegram_user_id}.pdf"
    if output_path.exists():
        try:
            output_path.unlink()
        except PermissionError:
            import time
            output_path = REPORTS_DIR / f"year_report_{telegram_user_id}_{int(time.time())}.pdf"

    F = _load_fonts()
    styles = _build_styles(F)
    state: dict = {"section": "", "plate_sign": None}

    sun_sign = astrology_data.get("sun_sign")
    moon_sign = astrology_data.get("moon_sign")
    asc_sign = astrology_data.get("ascendant_sign")
    signs = (sun_sign, moon_sign, asc_sign)

    year_context = build_year_context(astrology_data, start_date)
    period = year_context["period"]

    # Generate AI text for all 4 themes
    sections_text = generate_year_sections(year_context, profile)

    story: list = [NextPageTemplate("body"), PageBreak()]

    # Intro page
    story += _intro_page(profile, year_context, styles, state)

    themes_order = [("01", "career"), ("02", "relationships"), ("03", "health"), ("04", "growth")]
    for number, theme in themes_order:
        events = year_context["themes"].get(theme, [])
        text = sections_text.get(theme, "")
        story += _theme_plate(theme, number, styles, state)
        story += _theme_section(theme, text, events, styles, state)

    # Disclaimer
    generated_at = datetime.now().strftime("%d.%m.%Y")
    story += [
        PageBreak(),
        _Marker(state, section="Інформація"),
        Spacer(1, 10 * mm),
        _hr(HAIRLINE, "100%", 0.5, 0, 6),
        Paragraph(
            "Цей звіт створено для саморефлексії та особистого розвитку. "
            "Він не є медичною, психологічною, юридичною чи фінансовою рекомендацією "
            "та не передбачає майбутнє. Транзити — це клімат, а не доля.",
            styles["legal"],
        ),
        Spacer(1, 6 * mm),
        Paragraph(f"Inner Compass · звіт створено {generated_at}", styles["caption"]),
    ]

    doc = _make_year_doc(output_path, F, profile, period, signs, state)

    try:
        doc.build(story)
    except Exception as exc:
        raise PDFGenerationError(f"Year report build failed: {exc}") from exc

    LOGGER.info("Year report written to %s", output_path)
    return output_path
