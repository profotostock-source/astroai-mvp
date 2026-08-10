import logging
import os
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

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

# ── Palette ──────────────────────────────────────────────────────────────────
COVER_BG    = HexColor("#1A1035")   # deep night-purple
COVER_GOLD  = HexColor("#C9A76B")   # warm gold
COVER_GLOW  = HexColor("#2D2060")   # lighter purple for decorative circles
COVER_WHITE = HexColor("#F5EFE6")   # warm off-white text on cover
COVER_MUTED = HexColor("#9A8AB8")   # muted lavender text on cover

CREAM_BG    = HexColor("#FAF6F0")   # warm cream page background
WARM_BROWN  = HexColor("#6B3F26")   # section headings
GOLD_ACCENT = HexColor("#C9A76B")   # dividers, labels
HIGHLIGHT   = HexColor("#FEF3E2")   # insight box background
TEXT_DARK   = HexColor("#231C2E")   # body text
TEXT_MED    = HexColor("#7B6B8A")   # muted / small text
DIVIDER     = HexColor("#D9C4A8")   # soft separator
ROW_ALT     = HexColor("#F3EBE1")   # alternating table row
HEADER_ROW  = HexColor("#E8D5B7")   # table header row


class PDFGenerationError(Exception):
    pass


# ── Fonts ─────────────────────────────────────────────────────────────────────

def _font_candidates() -> list[tuple[str, str, str | None]]:
    windows_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    linux_dejavu = Path("/usr/share/fonts/truetype/dejavu")
    linux_liberation = Path("/usr/share/fonts/truetype/liberation")
    return [
        # Windows paths
        ("Arial", str(windows_fonts / "arial.ttf"), str(windows_fonts / "arialbd.ttf")),
        ("DejaVuSans", str(windows_fonts / "DejaVuSans.ttf"), str(windows_fonts / "DejaVuSans-Bold.ttf")),
        ("LiberationSans", str(windows_fonts / "LiberationSans-Regular.ttf"), str(windows_fonts / "LiberationSans-Bold.ttf")),
        # Linux paths (sandbox / server)
        ("DejaVuSans", str(linux_dejavu / "DejaVuSans.ttf"), str(linux_dejavu / "DejaVuSans-Bold.ttf")),
        ("LiberationSans", str(linux_liberation / "LiberationSans-Regular.ttf"), str(linux_liberation / "LiberationSans-Bold.ttf")),
    ]


def register_cyrillic_fonts() -> tuple[str, str]:
    for family_name, regular_path, bold_path in _font_candidates():
        regular_file = Path(regular_path)
        bold_file = Path(bold_path) if bold_path else None
        if not regular_file.exists():
            continue
        fn = f"{family_name}-Custom"
        bfn = f"{family_name}-Custom-Bold"
        if fn not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(fn, str(regular_file)))
        if bold_file and bold_file.exists():
            if bfn not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(bfn, str(bold_file)))
        else:
            bfn = fn
        return fn, bfn
    raise PDFGenerationError("No Cyrillic-compatible TrueType font found on this system")


# ── Page callbacks ────────────────────────────────────────────────────────────

def _draw_cover(canvas, doc, fn, bfn, profile, generated_at, sun_name, moon_name, asc_name):
    """Draw the full decorative cover page on the canvas."""
    W, H = A4
    canvas.saveState()

    # --- Background (warm cream) ---
    canvas.setFillColor(CREAM_BG)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)

    # --- Decorative soft circles ---
    canvas.setFillColor(HexColor("#F0E8DA"))
    canvas.circle(W - 18 * mm, H - 18 * mm, 72 * mm, fill=1, stroke=0)
    canvas.circle(18 * mm, 28 * mm, 52 * mm, fill=1, stroke=0)

    # --- Constellation dots (soft gold) ---
    star_positions = [
        (28, H - 48, 1.1), (52, H - 22, 0.7), (78, H - 65, 0.9),
        (W - 48, H - 85, 0.8), (W - 18, H - 125, 1.0), (W - 72, H - 38, 0.6),
        (18, H - 105, 0.7), (44, H - 135, 0.9), (W - 32, 82, 0.8),
        (14, 62, 1.1), (W - 58, 48, 0.7), (W / 2 - 55, H - 15, 0.5),
    ]
    canvas.setFillColor(HexColor("#D4B896"))
    for sx, sy, sr in star_positions:
        canvas.circle(sx, sy, sr * mm, fill=1, stroke=0)

    # --- Top rule + brand ---
    canvas.setStrokeColor(COVER_GOLD)
    canvas.setLineWidth(0.8)
    canvas.line(22 * mm, H - 20 * mm, W - 22 * mm, H - 20 * mm)
    canvas.setFont(bfn, 9)
    canvas.setFillColor(WARM_BROWN)
    canvas.drawString(22 * mm, H - 17 * mm, "INNER COMPASS")

    # --- Large decorative ring ---
    canvas.setStrokeColor(HexColor("#D9C4A8"))
    canvas.setLineWidth(0.8)
    cx, cy = W / 2, H / 2 + 22 * mm
    canvas.circle(cx, cy, 65 * mm, fill=0, stroke=1)
    canvas.setLineWidth(0.4)
    canvas.circle(cx, cy, 58 * mm, fill=0, stroke=1)

    # --- Main title ---
    canvas.setFont(bfn, 34)
    canvas.setFillColor(WARM_BROWN)
    canvas.drawCentredString(W / 2, H / 2 + 48 * mm, "INNER COMPASS")

    # --- Subtitle ---
    canvas.setFont(fn, 13)
    canvas.setFillColor(TEXT_MED)
    canvas.drawCentredString(W / 2, H / 2 + 30 * mm, "Персональний психологiчний звiт")

    # --- Gold divider ---
    canvas.setStrokeColor(COVER_GOLD)
    canvas.setLineWidth(0.8)
    canvas.line(W / 2 - 38 * mm, H / 2 + 22 * mm, W / 2 + 38 * mm, H / 2 + 22 * mm)

    # --- User name ---
    name = profile.get("name", "")
    canvas.setFont(bfn, 22)
    canvas.setFillColor(TEXT_DARK)
    canvas.drawCentredString(W / 2, H / 2 + 8 * mm, name)

    # --- Birth info ---
    birth_date = profile.get("birth_date", "")
    birthplace = profile.get("birthplace", "")
    birth_line = f"{birth_date}  |  {birthplace}" if birth_date else birthplace
    canvas.setFont(fn, 10)
    canvas.setFillColor(TEXT_MED)
    canvas.drawCentredString(W / 2, H / 2 - 4 * mm, birth_line)

    # --- Signs line ---
    signs_line = f"Сонце: {sun_name}   Мiсяць: {moon_name}   Асцендент: {asc_name}"
    canvas.setFont(fn, 10)
    canvas.setFillColor(WARM_BROWN)
    canvas.drawCentredString(W / 2, H / 2 - 16 * mm, signs_line)

    # --- Bottom rule + date ---
    canvas.setStrokeColor(DIVIDER)
    canvas.setLineWidth(0.5)
    canvas.line(22 * mm, 24 * mm, W - 22 * mm, 24 * mm)
    canvas.setFont(fn, 8)
    canvas.setFillColor(TEXT_MED)
    canvas.drawCentredString(W / 2, 16 * mm, f"Дата створення: {generated_at}")

    canvas.restoreState()


def _draw_body_page(canvas, doc, fn):
    """Draw warm cream background, header and footer on body pages."""
    W, H = A4
    canvas.saveState()

    # Warm cream background
    canvas.setFillColor(CREAM_BG)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)

    # Top gold accent bar
    canvas.setFillColor(COVER_GOLD)
    canvas.rect(0, H - 9 * mm, W, 9 * mm, fill=1, stroke=0)

    # Brand name in top bar
    canvas.setFont(fn, 8)
    canvas.setFillColor(COVER_BG)
    canvas.drawString(22 * mm, H - 6 * mm, "INNER COMPASS")

    # Page number top-right
    canvas.setFont(fn, 8)
    canvas.setFillColor(COVER_BG)
    page_label = f"Сторiнка {doc.page - 1}"
    canvas.drawRightString(W - 22 * mm, H - 6 * mm, page_label)

    # Footer line
    canvas.setStrokeColor(DIVIDER)
    canvas.setLineWidth(0.5)
    canvas.line(22 * mm, 17 * mm, W - 22 * mm, 17 * mm)

    # Footer text
    canvas.setFont(fn, 7)
    canvas.setFillColor(TEXT_MED)
    canvas.drawCentredString(W / 2, 11 * mm, "Персональний звiт Inner Compass")

    canvas.restoreState()


# ── Styles ────────────────────────────────────────────────────────────────────

def _build_styles(fn: str, bfn: str) -> dict[str, ParagraphStyle]:
    ss = getSampleStyleSheet()
    return {
        "section_title": ParagraphStyle(
            "SectionTitle", parent=ss["Heading2"],
            fontName=bfn, fontSize=14, leading=20,
            alignment=TA_LEFT, textColor=WARM_BROWN,
            spaceAfter=4, spaceBefore=10,
        ),
        "section_sub": ParagraphStyle(
            "SectionSub", parent=ss["Heading3"],
            fontName=bfn, fontSize=11, leading=16,
            alignment=TA_LEFT, textColor=HexColor("#8B6914"),
            spaceAfter=3, spaceBefore=6,
        ),
        "body": ParagraphStyle(
            "Body", parent=ss["BodyText"],
            fontName=fn, fontSize=11, leading=18,
            alignment=TA_JUSTIFY, textColor=TEXT_DARK,
            spaceAfter=8,
        ),
        "highlight_text": ParagraphStyle(
            "HighlightText", parent=ss["BodyText"],
            fontName=fn, fontSize=11, leading=18,
            alignment=TA_JUSTIFY, textColor=HexColor("#4A3520"),
            spaceAfter=0,
        ),
        "label": ParagraphStyle(
            "Label", parent=ss["BodyText"],
            fontName=bfn, fontSize=9, leading=13,
            alignment=TA_LEFT, textColor=HexColor("#8B6914"),
            spaceAfter=2, spaceBefore=4,
        ),
        "small": ParagraphStyle(
            "Small", parent=ss["BodyText"],
            fontName=fn, fontSize=9, leading=14,
            alignment=TA_LEFT, textColor=TEXT_MED,
            spaceAfter=6,
        ),
        "small_italic": ParagraphStyle(
            "SmallItalic", parent=ss["BodyText"],
            fontName=fn, fontSize=9, leading=14,
            alignment=TA_JUSTIFY, textColor=TEXT_MED,
            spaceAfter=6,
        ),
    }


# ── Reusable elements ─────────────────────────────────────────────────────────

def _divider():
    """Subtle full-width divider."""
    return HRFlowable(width="100%", thickness=0.4, color=DIVIDER, spaceAfter=8, spaceBefore=2)


def _gold_divider():
    """Short gold accent divider under section titles."""
    return HRFlowable(width="35%", thickness=1.2, color=GOLD_ACCENT, spaceAfter=8, spaceBefore=2)


def _insight_box(text: str, styles: dict) -> Table:
    """Highlighted box with gold left border — used for key insights and advice."""
    inner = Paragraph(text, styles["highlight_text"])
    t = Table([[inner]], colWidths=[155 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HIGHLIGHT),
        ("LINEBEFORE", (0, 0), (0, -1), 3, GOLD_ACCENT),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    return t


def _build_profile_table(profile: dict, fn: str, bfn: str) -> Table:
    rows = [
        ["Iм'я", profile.get("name", "—")],
        ["Дата народження", profile.get("birth_date", "—")],
        ["Час народження", profile.get("birth_time", "—")],
        ["Мiсце народження", profile.get("birthplace", "—")],
    ]
    t = Table(rows, colWidths=[52 * mm, 113 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), bfn),
        ("FONTNAME", (1, 0), (1, -1), fn),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), HexColor("#8B6914")),
        ("TEXTCOLOR", (1, 0), (1, -1), TEXT_DARK),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [ROW_ALT, CREAM_BG]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, DIVIDER),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _build_planets_table(planets_data: list[dict], fn: str, bfn: str) -> Table:
    rows = [["Планета", "Знак", "Градус"]]
    for p in planets_data:
        planet_name = PLANET_NAMES.get(p.get("name", ""), p.get("name", ""))
        sign_name = SIGN_NAMES.get(p.get("sign", ""), p.get("sign", ""))
        degree = f"{p.get('degree', 0):.1f}°"
        rows.append([planet_name, sign_name, degree])

    t = Table(rows, colWidths=[58 * mm, 65 * mm, 42 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), bfn),
        ("FONTNAME", (0, 1), (-1, -1), fn),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#4A3520")),
        ("TEXTCOLOR", (0, 1), (-1, -1), TEXT_DARK),
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_ROW),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [ROW_ALT, CREAM_BG]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, DIVIDER),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (2, -1), "CENTER"),
    ]))
    return t


def _section_block(icon_label: str, title: str, desc: dict | str, styles: dict) -> list:
    """Build a full styled section: title + gold divider + insight box + sub-sections."""
    items = []
    items.append(Paragraph(f"{icon_label} {title}", styles["section_title"]))
    items.append(_gold_divider())

    if isinstance(desc, str):
        items.append(Paragraph(desc, styles["body"]))

    elif isinstance(desc, dict):
        if desc.get("represents"):
            items.append(_insight_box(desc["represents"], styles))
            items.append(Spacer(1, 5 * mm))

        if desc.get("strengths"):
            items.append(Paragraph("Сильнi сторони", styles["label"]))
            items.append(Paragraph(desc["strengths"], styles["body"]))

        if desc.get("challenges"):
            items.append(Paragraph("Можливi виклики", styles["label"]))
            items.append(Paragraph(desc["challenges"], styles["body"]))

        if desc.get("advice"):
            items.append(Paragraph("Практична рекомендацiя", styles["label"]))
            items.append(_insight_box(desc["advice"], styles))

    items.append(Spacer(1, 8 * mm))
    return items


# ── Public API ────────────────────────────────────────────────────────────────

def generate_report(profile: dict, telegram_user_id: int, astrology_data: dict) -> Path:
    """Generate a warm, psychologically-styled PDF report.

    Args:
        profile: User profile dict (name, birth_date, birth_time, birthplace).
        telegram_user_id: Used as filename identifier.
        astrology_data: Output from calculate_natal_chart.

    Returns:
        Path to the generated PDF.

    Raises:
        PDFGenerationError: If generation fails.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_DIR / f"report_{telegram_user_id}.pdf"
    if output_path.exists():
        output_path.unlink()

    fn, bfn = register_cyrillic_fonts()
    styles = _build_styles(fn, bfn)
    generated_at = datetime.now().strftime("%d.%m.%Y")

    sun_sign = astrology_data.get("sun_sign", "N/A")
    moon_sign = astrology_data.get("moon_sign", "N/A")
    ascendant_sign = astrology_data.get("ascendant_sign")
    planets_data = astrology_data.get("planets", [])

    sun_name = SIGN_NAMES.get(sun_sign, sun_sign)
    moon_name = SIGN_NAMES.get(moon_sign, moon_sign)
    asc_name = SIGN_NAMES.get(ascendant_sign, ascendant_sign) if ascendant_sign else "невiдомий"

    # Page 1 is entirely drawn by the cover canvas callback.
    # PageBreak() moves story content to page 2.
    story: list = [PageBreak()]

    # === PAGE 2: Profile + Portrait ===
    story += [
        Paragraph("Ваш профiль", styles["section_title"]),
        _gold_divider(),
        _build_profile_table(profile, fn, bfn),
        Spacer(1, 8 * mm),
        Paragraph(
            f"Сонце: {sun_name}   ·   Мiсяць: {moon_name}   ·   Асцендент: {asc_name}",
            styles["section_sub"],
        ),
        Spacer(1, 8 * mm),
        Paragraph("Психологiчний портрет", styles["section_title"]),
        _gold_divider(),
        Paragraph(get_psychological_portrait(sun_sign, moon_sign, ascendant_sign), styles["body"]),
        Spacer(1, 10 * mm),
    ]

    # === Sun ===
    if sun_sign in SUN_SIGN_DESCRIPTIONS:
        story += _section_block(
            "Сонце",
            f"в {SUN_SIGN_DESCRIPTIONS[sun_sign]['name']}",
            SUN_SIGN_DESCRIPTIONS[sun_sign],
            styles,
        )

    # === Moon ===
    if moon_sign in MOON_SIGN_DESCRIPTIONS:
        story += _section_block(
            "Мiсяць",
            f"в {MOON_SIGN_DESCRIPTIONS[moon_sign]['name']}",
            MOON_SIGN_DESCRIPTIONS[moon_sign],
            styles,
        )

    # === Ascendant ===
    if ascendant_sign and ascendant_sign in ASCENDANT_DESCRIPTIONS:
        story += _section_block(
            "Асцендент",
            f"в {ASCENDANT_DESCRIPTIONS[ascendant_sign]['name']}",
            ASCENDANT_DESCRIPTIONS[ascendant_sign],
            styles,
        )
    elif not ascendant_sign:
        story += [
            Paragraph("Асцендент", styles["section_title"]),
            _gold_divider(),
            Paragraph(
                "Асцендент не розраховується без точного часу народження. "
                "Якщо у вас є цей час — зверніться до нас для оновлення звiту.",
                styles["body"],
            ),
            Spacer(1, 8 * mm),
        ]

    # === Technical page ===
    story += [
        PageBreak(),
        Paragraph("Технiчнi данi", styles["section_title"]),
        _gold_divider(),
        Paragraph("Позицiї планет", styles["section_sub"]),
        Spacer(1, 2 * mm),
        _build_planets_table(planets_data, fn, bfn),
        Spacer(1, 14 * mm),
        _divider(),
        Spacer(1, 4 * mm),
        Paragraph(
            "<i>Цей матерiал створено для саморефлексiї та особистого розвитку. "
            "Вiн не є медичною, психологiчною, юридичною чи фiнансовою рекомендацiєю "
            "та не гарантує передбачення майбутнього.</i>",
            styles["small_italic"],
        ),
    ]

    cover_cb = lambda c, d: _draw_cover(
        c, d, fn, bfn, profile, generated_at, sun_name, moon_name, asc_name
    )
    body_cb = lambda c, d: _draw_body_page(c, d, fn)

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title="INNER COMPASS — Персональний звiт",
        author="Inner Compass AI",
    )

    try:
        document.build(story, onFirstPage=cover_cb, onLaterPages=body_cb)
    except Exception as error:
        LOGGER.exception("PDF generation failed: %s", error)
        raise PDFGenerationError("Failed to generate PDF report") from error

    return output_path


def generate_demo_report(profile: dict, telegram_user_id: int) -> Path:
    """Legacy demo report without astrology data. Kept for backward compatibility."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_DIR / f"report_{telegram_user_id}.pdf"
    if output_path.exists():
        output_path.unlink()

    fn, bfn = register_cyrillic_fonts()
    styles = _build_styles(fn, bfn)
    generated_at = datetime.now().strftime("%d.%m.%Y")

    story: list = [PageBreak()]

    story += [
        Paragraph("Ваш профiль", styles["section_title"]),
        _gold_divider(),
        _build_profile_table(profile, fn, bfn),
        Spacer(1, 10 * mm),
        Paragraph("Ваш внутрiшнiй компас", styles["section_title"]),
        _gold_divider(),
        Paragraph(
            "Це демонстрацiйна версiя звiту. На наступному етапi тут буде повна "
            "астрологiчна iнтерпретацiя та персональний психологiчний аналiз.",
            styles["body"],
        ),
        Spacer(1, 8 * mm),
        Paragraph("Питання для саморефлексiї", styles["section_title"]),
        _gold_divider(),
        _insight_box(
            "Якi внутрiшнi якостi допомагають менi проходити перiоди змiн?", styles
        ),
        Spacer(1, 4 * mm),
        _insight_box(
            "У яких сферах життя я зараз найбiльше потребую яcностi та опори?", styles
        ),
        Spacer(1, 4 * mm),
        _insight_box(
            "Який наступний невеликий крок допоможе менi рухатися бiльш усвiдомлено?", styles
        ),
        Spacer(1, 10 * mm),
        _divider(),
        Paragraph(
            "<i>Цей матерiал створено для саморефлексiї та особистого розвитку. "
            "Вiн не є медичною, психологiчною, юридичною чи фiнансовою рекомендацiєю.</i>",
            styles["small_italic"],
        ),
    ]

    cover_cb = lambda c, d: _draw_cover(
        c, d, fn, bfn, profile, generated_at, "—", "—", "—"
    )
    body_cb = lambda c, d: _draw_body_page(c, d, fn)

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title="INNER COMPASS — Персональний звiт",
        author="Inner Compass AI",
    )

    try:
        document.build(story, onFirstPage=cover_cb, onLaterPages=body_cb)
    except Exception as error:
        LOGGER.exception("PDF generation failed: %s", error)
        raise PDFGenerationError("Failed to generate PDF report") from error


    return output_path
