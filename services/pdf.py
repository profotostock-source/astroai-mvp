"""PDF report generation service.

This module handles the creation of personalized PDF reports
with user profile information and formatted content.
"""

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

from .ai_interpretation import generate_psychological_report
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
    """Raised when PDF generation fails."""

    pass


def _font_candidates() -> list[tuple[str, str, str | None]]:
    """Get list of candidate font paths for Cyrillic text rendering.

    Returns:
        list[tuple[str, str, str | None]]: List of tuples containing
            (font_family_name, regular_font_path, bold_font_path).
    """
    windows_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    return [
        ("Arial", str(windows_fonts / "arial.ttf"), str(windows_fonts / "arialbd.ttf")),
        (
            "DejaVuSans",
            str(windows_fonts / "DejaVuSans.ttf"),
            str(windows_fonts / "DejaVuSans-Bold.ttf"),
        ),
        (
            "LiberationSans",
            str(windows_fonts / "LiberationSans-Regular.ttf"),
            str(windows_fonts / "LiberationSans-Bold.ttf"),
        ),
    ]


def register_cyrillic_fonts() -> tuple[str, str]:
    """Register Cyrillic-compatible fonts for PDF rendering.

    Attempts to find and register system fonts that support Cyrillic text.
    Tries multiple font families in order of preference.

    Returns:
        tuple[str, str]: Tuple of (regular_font_name, bold_font_name)
            registered font names for use in PDF generation.

    Raises:
        PDFGenerationError: If no Cyrillic-compatible font is found.
    """
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
    """Draw page number in the footer of each PDF page.

    Args:
        canvas: ReportLab canvas object for drawing.
        document: ReportLab document object.
        font_name: Name of the font to use for page numbers.
    """
    canvas.saveState()
    canvas.setFont(font_name, 9)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawRightString(190 * mm, 12 * mm, f"Сторінка {document.page}")
    canvas.restoreState()


def _build_styles(font_name: str, bold_font_name: str) -> dict[str, ParagraphStyle]:
    """Build ReportLab paragraph styles for PDF elements.

    Args:
        font_name: Name of the regular font.
        bold_font_name: Name of the bold font.

    Returns:
        dict[str, ParagraphStyle]: Dictionary mapping style names to
            ParagraphStyle objects for use in document building.
    """
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
    """Build formatted table with user profile information.

    Args:
        profile: Dictionary containing user profile data with keys:
            - name: User's name
            - birth_date: Birth date string
            - birth_time: Birth time string
            - birthplace: Place of birth
        font_name: Name of the regular font.
        bold_font_name: Name of the bold font.

    Returns:
        Table: ReportLab Table object with styled profile data.
    """
    rows = [
        ["Ім'я", profile["name"]],
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


def _build_astrology_section(astrology_data: dict, font_name: str, bold_font_name: str) -> list:
    """Build astrology section content for PDF with AI-generated interpretations and technical data.

    Args:
        astrology_data: Dictionary containing natal chart data from calculate_natal_chart.
        font_name: Name of the regular font.
        bold_font_name: Name of the bold font.

    Returns:
        list: List of ReportLab elements for the astrology section.
    """
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    styles_dict = _build_styles(font_name, bold_font_name)
    section_elements = []

    sun_sign = astrology_data.get("sun_sign", "N/A")
    moon_sign = astrology_data.get("moon_sign", "N/A")
    ascendant_sign = astrology_data.get("ascendant_sign")
    birth_time_known = astrology_data.get("birth_time_known", False)

    # === AI-Generated Psychological Report ===
    section_elements.append(Paragraph("Ваш психологічний портрет", styles_dict["section_title"]))
    section_elements.append(Spacer(1, 3 * mm))
    
    try:
        ai_report = generate_psychological_report(astrology_data)
        section_elements.append(Paragraph(ai_report, styles_dict["body"]))
        LOGGER.info("Successfully added AI-generated psychological report to PDF")
    except Exception as error:
        LOGGER.error("Failed to generate AI report, using fallback: %s", error)
        fallback_text = (
            "Не вдалося отримати детальну AI-інтерпретацію. "
            "Це демонстраційна версія звіту."
        )
        section_elements.append(Paragraph(fallback_text, styles_dict["body"]))
    
    section_elements.append(Spacer(1, 8 * mm))

    # === Page Break before Technical Data ===
    section_elements.append(PageBreak())

    # === Technical Data Section ===
    section_elements.append(Paragraph("Технічні дані натальної карти", styles_dict["section_title"]))
    section_elements.append(Spacer(1, 3 * mm))

    if not birth_time_known and ascendant_sign is None:
        ascendant_display = "Не визначено без точного часу"
    else:
        ascendant_display = ascendant_sign if ascendant_sign else "N/A"

    # Core signs table with Ukrainian names
    sun_name = SIGN_NAMES.get(sun_sign, sun_sign)
    moon_name = SIGN_NAMES.get(moon_sign, moon_sign)
    asc_name = SIGN_NAMES.get(ascendant_display, ascendant_display) if ascendant_display != "Не визначено без точного часу" else ascendant_display

    core_signs_rows = [
        ["Сонце", sun_name],
        ["Місяць", moon_name],
        ["Асцендент", asc_name],
    ]

    core_signs_table = Table(core_signs_rows, colWidths=[55 * mm, 110 * mm])
    core_signs_table.setStyle(
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
    section_elements.append(core_signs_table)
    section_elements.append(Spacer(1, 8 * mm))

    section_elements.append(Paragraph("Планети", styles_dict["section_title"]))
    section_elements.append(Spacer(1, 3 * mm))

    planets_data = astrology_data.get("planets", {})
    if planets_data:
        planets_rows = [["Планета", "Знак", "Градус", "Ретроградна"]]
        for planet_name, planet_info in planets_data.items():
            planet_ua = PLANET_NAMES.get(planet_name.capitalize(), planet_name.capitalize())
            sign_ua = SIGN_NAMES.get(planet_info.get("sign", ""), planet_info.get("sign", ""))
            retrograde_status = "Так" if planet_info.get("retrograde", False) else "Ні"
            planets_rows.append([
                planet_ua,
                sign_ua,
                f"{planet_info.get('degree', 0):.2f}°",
                retrograde_status,
            ])

        planets_table = Table(planets_rows, colWidths=[40 * mm, 35 * mm, 40 * mm, 50 * mm])
        planets_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), bold_font_name),
                    ("FONTNAME", (0, 1), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1F2937")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F9FAFB")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F9FAFB"), colors.white]),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        section_elements.append(planets_table)
        section_elements.append(Spacer(1, 8 * mm))

    houses_data = astrology_data.get("houses", [])
    if houses_data:
        section_elements.append(Paragraph("Дома", styles_dict["section_title"]))
        section_elements.append(Spacer(1, 3 * mm))

        houses_rows = [["Дім", "Знак", "Градус"]]
        for house_info in houses_data:
            sign_ua = SIGN_NAMES.get(house_info.get("sign", ""), house_info.get("sign", ""))
            houses_rows.append([
                f"Дім {house_info.get('house', 'N/A')}",
                sign_ua,
                f"{house_info.get('degree', 0):.2f}°",
            ])

        houses_table = Table(houses_rows, colWidths=[50 * mm, 50 * mm, 50 * mm])
        houses_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), bold_font_name),
                    ("FONTNAME", (0, 1), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1F2937")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F9FAFB")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F9FAFB"), colors.white]),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        section_elements.append(houses_table)
        section_elements.append(Spacer(1, 8 * mm))

    aspects_data = astrology_data.get("aspects", [])
    if aspects_data:
        section_elements.append(Paragraph("Аспекти", styles_dict["section_title"]))
        section_elements.append(Spacer(1, 3 * mm))

        aspects_rows = [["Планета 1", "Планета 2", "Аспект", "Орб"]]
        for aspect_info in aspects_data:
            planet1_ua = PLANET_NAMES.get(aspect_info.get("planet1", "").capitalize(), aspect_info.get("planet1", ""))
            planet2_ua = PLANET_NAMES.get(aspect_info.get("planet2", "").capitalize(), aspect_info.get("planet2", ""))
            aspects_rows.append([
                planet1_ua,
                planet2_ua,
                aspect_info.get("aspect", "N/A"),
                f"{aspect_info.get('orb', 0):.2f}°",
            ])

        aspects_table = Table(aspects_rows, colWidths=[45 * mm, 45 * mm, 40 * mm, 40 * mm])
        aspects_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), bold_font_name),
                    ("FONTNAME", (0, 1), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1F2937")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F9FAFB")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F9FAFB"), colors.white]),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        section_elements.append(aspects_table)
        section_elements.append(Spacer(1, 8 * mm))

    warnings = astrology_data.get("warnings", [])
    filtered_warnings = [
        warning
        for warning in warnings
        if warning != "Aspect calculation is not supported in this Kerykeion version."
    ]

    if filtered_warnings:
        section_elements.append(Paragraph("Примітки", styles_dict["section_title"]))
        section_elements.append(Spacer(1, 3 * mm))
        for warning in filtered_warnings:
            section_elements.append(Paragraph(f"⚠️ {warning}", styles_dict["body"]))
        section_elements.append(Spacer(1, 8 * mm))

    return section_elements


def generate_report(profile: dict, telegram_user_id: int, astrology_data: dict) -> Path:
    """Generate a personalized PDF report for the user.

    Creates a formatted PDF document with the user's profile information,
    astrology data, and report content. The report includes a cover page,
    profile section, astrology section, reflection questions, and disclaimer.
    Automatically handles font registration for Cyrillic text support.

    Args:
        profile: Dictionary containing user profile data with keys:
            - name: User's name
            - birth_date: Birth date string (DD.MM.YYYY format)
            - birth_time: Birth time string (HH:MM format)
            - birthplace: Place of birth
        telegram_user_id: Unique Telegram user ID for report file naming.
        astrology_data: Dictionary containing natal chart data from calculate_natal_chart.

    Returns:
        Path: Path to the generated PDF file.

    Raises:
        PDFGenerationError: If font registration or PDF generation fails.

    Example:
        >>> profile = {
        ...     'name': 'John',
        ...     'birth_date': '15.03.1990',
        ...     'birth_time': '14:30',
        ...     'birthplace': 'London'
        ... }
        >>> astrology_data = calculate_natal_chart(profile)
        >>> report_path = generate_report(profile, 123456789, astrology_data)
        >>> print(report_path)
        /path/to/reports/report_123456789.pdf
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
    ]

    story.extend(_build_astrology_section(astrology_data, font_name, bold_font_name))

    story.extend([
        Spacer(1, 8 * mm),
        Paragraph(
            "Цей матеріал створений для саморефлексії та особистого розвитку. Він не є медичною, психологічною, юридичною чи фінансовою рекомендацією та не гарантує передбачення майбутнього.",
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
