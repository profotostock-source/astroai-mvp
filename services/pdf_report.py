import logging
import os
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .interpretations import (
    SIGN_NAMES,
    PLANET_NAMES,
    SUN_SIGN_DESCRIPTIONS,
    MOON_SIGN_DESCRIPTIONS,
    ASCENDANT_DESCRIPTIONS,
    get_psychological_portrait,
)


LOGGER = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"


class PDFGenerationError(Exception):
    pass


def _font_candidates() -> list[tuple[str, str, str | None]]:
    windows_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    return [
        ("Arial", str(windows_fonts / "arial.ttf"), str(windows_fonts / "arialbd.ttf")),
        ("DejaVuSans", str(windows_fonts / "DejaVuSans.ttf"), str(windows_fonts / "DejaVuSans-Bold.ttf")),
        ("LiberationSans", str(windows_fonts / "LiberationSans-Regular.ttf"), str(windows_fonts / "LiberationSans-Bold.ttf")),
    ]


def register_cyrillic_fonts() -> tuple[str, str]:
    for family_name, regular_path, bold_path in _font_candidates():
        regular_file = Path(regular_path)
        bold_file = Path(bold_path) if bold_path else None

        if not regular_file.exists():
            continue

        regular_font_name = f"{family_name}-Custom"
        bold_font_name = f"{family_name}-Custom-Bold"

        if regular_font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(regular_font_name, str(regular_file)))

        if bold_file and bold_file.exists():
            if bold_font_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(bold_font_name, str(bold_file)))
        else:
            bold_font_name = regular_font_name

        return regular_font_name, bold_font_name

    raise PDFGenerationError("No Cyrillic-compatible TrueType font found on this system")


def _page_number(canvas, document, font_name: str) -> None:
    canvas.saveState()
    canvas.setFont(font_name, 9)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawRightString(190 * mm, 12 * mm, f"Сторінка {document.page}")
    canvas.restoreState()


def _build_styles(font_name: str, bold_font_name: str) -> dict[str, ParagraphStyle]:
    stylesheet = getSampleStyleSheet()
    return {
        "cover_brand": ParagraphStyle(
            "CoverBrand",
            parent=stylesheet["Title"],
            fontName=bold_font_name,
            fontSize=24,
            leading=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#111827"),
            spaceAfter=18,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=stylesheet["Heading2"],
            fontName=font_name,
            fontSize=16,
            leading=22,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#374151"),
            spaceAfter=12,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=stylesheet["BodyText"],
            fontName=font_name,
            fontSize=11,
            leading=17,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=10,
        ),
        "section_title": ParagraphStyle(
            "SectionTitle",
            parent=stylesheet["Heading2"],
            fontName=bold_font_name,
            fontSize=15,
            leading=20,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#111827"),
            spaceAfter=10,
            spaceBefore=8,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=stylesheet["BodyText"],
            fontName=font_name,
            fontSize=9,
            leading=14,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#6B7280"),
            spaceAfter=6,
        ),
    }


def _build_profile_table(profile: dict, font_name: str, bold_font_name: str) -> Table:
    rows = [
        ["Ім’я", profile["name"]],
        ["Дата народження", profile["birth_date"]],
        ["Час народження", profile["birth_time"]],
        ["Місце народження", profile["birthplace"]],
    ]
    table = Table(rows, colWidths=[55 * mm, 110 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), bold_font_name),
                ("FONTNAME", (1, 0), (1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1F2937")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#F9FAFB"), colors.white]),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def _build_planets_table(planets_data: list[dict], font_name: str, bold_font_name: str) -> Table:
    """Build a table of planets with Ukrainian names and positions."""
    rows = [["Планета", "Знак", "Градус"]]
    for planet in planets_data:
        planet_name = PLANET_NAMES.get(planet.get("name", ""), planet.get("name", ""))
        sign_name = SIGN_NAMES.get(planet.get("sign", ""), planet.get("sign", ""))
        degree = f"{planet.get('degree', 0):.1f}°"
        rows.append([planet_name, sign_name, degree])

    table = Table(rows, colWidths=[50 * mm, 50 * mm, 60 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), bold_font_name),
                ("FONTNAME", (0, 1), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1F2937")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F9FAFB"), colors.white]),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (2, 0), (2, -1), "CENTER"),
            ]
        )
    )
    return table


def generate_report(profile: dict, telegram_user_id: int, astrology_data: dict) -> Path:
    """Generate a user-friendly PDF report with astrological interpretations.
    
    Args:
        profile: User profile dictionary
        telegram_user_id: Telegram user ID for filename
        astrology_data: Astrological data from calculate_natal_chart
    
    Returns:
        Path to generated PDF file
    
    Raises:
        PDFGenerationError: If PDF generation fails
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_DIR / f"report_{telegram_user_id}.pdf"

    if output_path.exists():
        output_path.unlink()

    font_name, bold_font_name = register_cyrillic_fonts()
    styles = _build_styles(font_name, bold_font_name)
    generated_at = datetime.now().strftime("%d.%m.%Y")

    sun_sign = astrology_data.get("sun_sign", "N/A")
    moon_sign = astrology_data.get("moon_sign", "N/A")
    ascendant_sign = astrology_data.get("ascendant_sign")
    planets_data = astrology_data.get("planets", [])

    sun_name = SIGN_NAMES.get(sun_sign, sun_sign)
    moon_name = SIGN_NAMES.get(moon_sign, moon_sign)
    asc_name = SIGN_NAMES.get(ascendant_sign, ascendant_sign) if ascendant_sign else "невідомий"

    story = [
        # === PAGE 1: Cover ===
        Spacer(1, 55 * mm),
        Paragraph("INNER COMPASS", styles["cover_brand"]),
        Paragraph("Персональний астрологічний звіт", styles["cover_subtitle"]),
        Spacer(1, 10 * mm),
        Paragraph(profile["name"], styles["section_title"]),
        Paragraph(f"Дата створення: {generated_at}", styles["small"]),
        PageBreak(),
        # === PAGE 2: Profile, Signs, and Interpretations ===
        Paragraph("Профіль", styles["section_title"]),
        Spacer(1, 3 * mm),
        _build_profile_table(profile, font_name, bold_font_name),
        Spacer(1, 10 * mm),
        Paragraph(f"Сонце: {sun_name} | Місяць: {moon_name} | Асцендент: {asc_name}", styles["section_title"]),
        Spacer(1, 8 * mm),
        Paragraph("Короткий психологічний портрет", styles["section_title"]),
        Spacer(1, 3 * mm),
        Paragraph(get_psychological_portrait(sun_sign, moon_sign, ascendant_sign), styles["body"]),
        Spacer(1, 10 * mm),
    ]

    # Add Sun interpretation
    if sun_sign in SUN_SIGN_DESCRIPTIONS:
        sun_desc = SUN_SIGN_DESCRIPTIONS[sun_sign]
        story.extend([
            Paragraph(f"☀ Сонце в {sun_desc['name']}", styles["section_title"]),
            Spacer(1, 2 * mm),
            Paragraph(f"<b>Що це означає:</b> {sun_desc['represents']}", styles["body"]),
            Spacer(1, 3 * mm),
            Paragraph(f"<b>Ваші сильні сторони:</b>", styles["body"]),
            Paragraph(sun_desc['strengths'], styles["body"]),
            Spacer(1, 3 * mm),
            Paragraph(f"<b>Можливі виклики:</b>", styles["body"]),
            Paragraph(sun_desc['challenges'], styles["body"]),
            Spacer(1, 3 * mm),
            Paragraph(f"<b>Практична рекомендація:</b>", styles["body"]),
            Paragraph(sun_desc['advice'], styles["body"]),
            Spacer(1, 8 * mm),
        ])

    # Add Moon interpretation
    if moon_sign in MOON_SIGN_DESCRIPTIONS:
        moon_desc = MOON_SIGN_DESCRIPTIONS[moon_sign]
        story.extend([
            Paragraph(f"🌙 Місяць в {moon_desc['name']}", styles["section_title"]),
            Spacer(1, 2 * mm),
            Paragraph(f"<b>Що це означає:</b> {moon_desc['represents']}", styles["body"]),
            Spacer(1, 3 * mm),
            Paragraph(f"<b>Ваші сильні сторони:</b>", styles["body"]),
            Paragraph(moon_desc['strengths'], styles["body"]),
            Spacer(1, 3 * mm),
            Paragraph(f"<b>Можливі виклики:</b>", styles["body"]),
            Paragraph(moon_desc['challenges'], styles["body"]),
            Spacer(1, 3 * mm),
            Paragraph(f"<b>Практична рекомендація:</b>", styles["body"]),
            Paragraph(moon_desc['advice'], styles["body"]),
            Spacer(1, 8 * mm),
        ])

    # Add Ascendant interpretation
    if ascendant_sign and ascendant_sign in ASCENDANT_DESCRIPTIONS:
        asc_desc = ASCENDANT_DESCRIPTIONS[ascendant_sign]
        story.extend([
            Paragraph(f"⬆ Асцендент в {asc_desc['name']}", styles["section_title"]),
            Spacer(1, 2 * mm),
            Paragraph(f"<b>Що це означає:</b> {asc_desc['represents']}", styles["body"]),
            Spacer(1, 3 * mm),
            Paragraph(f"<b>Ваші сильні сторони:</b>", styles["body"]),
            Paragraph(asc_desc['strengths'], styles["body"]),
            Spacer(1, 3 * mm),
            Paragraph(f"<b>Можливі виклики:</b>", styles["body"]),
            Paragraph(asc_desc['challenges'], styles["body"]),
            Spacer(1, 3 * mm),
            Paragraph(f"<b>Практична рекомендація:</b>", styles["body"]),
            Paragraph(asc_desc['advice'], styles["body"]),
            Spacer(1, 8 * mm),
        ])
    elif not ascendant_sign:
        story.extend([
            Paragraph("⬆ Асцендент (невідомий)", styles["section_title"]),
            Spacer(1, 3 * mm),
            Paragraph(
                "Асцендент не розраховується без точного часу народження. "
                "Якщо у вас є цей час, звернеться до нас для оновлення звіту.",
                styles["body"]
            ),
            Spacer(1, 8 * mm),
        ])

    # Page break before technical tables
    story.append(PageBreak())

    # === PAGE 3+: Technical Data ===
    story.extend([
        Paragraph("Технічні дані", styles["section_title"]),
        Spacer(1, 3 * mm),
        Paragraph("Позиції планет", styles["section_title"]),
        Spacer(1, 2 * mm),
        _build_planets_table(planets_data, font_name, bold_font_name),
        Spacer(1, 10 * mm),
    ])

    # Add disclaimer
    story.extend([
        Spacer(1, 8 * mm),
        Paragraph(
            "<i>Цей матеріал створений для саморефлексії та особистого розвитку. "
            "Він не є медичною, психологічною, юридичною чи фінансовою рекомендацією "
            "та не гарантує передбачення майбутнього.</i>",
            styles["small"],
        ),
    ])

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        title="INNER COMPASS - Персональний звіт",
        author="Inner Compass AI",
    )

    try:
        document.build(
            story,
            onFirstPage=lambda canvas, doc: _page_number(canvas, doc, font_name),
            onLaterPages=lambda canvas, doc: _page_number(canvas, doc, font_name),
        )
    except Exception as error:
        LOGGER.exception("PDF generation failed: %s", error)
        raise PDFGenerationError("Failed to generate PDF report") from error

    return output_path


def generate_demo_report(profile: dict, telegram_user_id: int) -> Path:
    """Legacy demo report without astrology data. Kept for backward compatibility.
    
    This function generates a basic report without astrological interpretations.
    Use generate_report() instead when astrology data is available.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_DIR / f"report_{telegram_user_id}.pdf"

    if output_path.exists():
        output_path.unlink()

    font_name, bold_font_name = register_cyrillic_fonts()
    styles = _build_styles(font_name, bold_font_name)
    generated_at = datetime.now().strftime("%d.%m.%Y")

    story = [
        Spacer(1, 55 * mm),
        Paragraph("INNER COMPASS", styles["cover_brand"]),
        Paragraph("Персональний звіт", styles["cover_subtitle"]),
        Spacer(1, 10 * mm),
        Paragraph(profile["name"], styles["section_title"]),
        Paragraph(f"Дата створення: {generated_at}", styles["small"]),
        PageBreak(),
        Paragraph("Профіль", styles["section_title"]),
        Spacer(1, 3 * mm),
        _build_profile_table(profile, font_name, bold_font_name),
        Spacer(1, 12 * mm),
        Paragraph("Ваш внутрішній компас", styles["section_title"]),
        Paragraph(
            "Це демонстраційна версія звіту. На наступному етапі розробки тут буде додано повну астрологічну інтерпретацію, персональні висновки та глибший аналіз вашого профілю.",
            styles["body"],
        ),
        Spacer(1, 6 * mm),
        Paragraph("Питання для саморефлексії", styles["section_title"]),
        Paragraph("1. Які внутрішні якості допомагають мені проходити періоди змін?", styles["body"]),
        Paragraph("2. У яких життєвих сферах я зараз найбільше потребую ясності та опори?", styles["body"]),
        Paragraph("3. Який наступний невеликий крок допоможе мені рухатися більш усвідомлено?", styles["body"]),
        Spacer(1, 8 * mm),
        Paragraph(
            "Цей матеріал створений для саморефлексії та особистого розвитку. Він не є медичною, психологічною, юридичною чи фінансовою рекомендацією та не гарантує передбачення майбутнього.",
            styles["small"],
        ),
    ]

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        title="INNER COMPASS - Персональний звіт",
        author="Inner Compass AI",
    )

    try:
        document.build(
            story,
            onFirstPage=lambda canvas, doc: _page_number(canvas, doc, font_name),
            onLaterPages=lambda canvas, doc: _page_number(canvas, doc, font_name),
        )
    except Exception as error:
        LOGGER.exception("PDF generation failed: %s", error)
        raise PDFGenerationError("Failed to generate PDF report") from error

    return output_path
