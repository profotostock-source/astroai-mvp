"""Inner Compass — PDF report renderer.

Design direction: light editorial minimalism. Warm paper, one gold accent, a
serif for display type and a sans for reading type, generous margins, hairline
rules instead of boxes and fills. Illustration comes from vector zodiac glyphs
and the reader's own natal wheel (services/glyphs.py, services/chart_wheel.py)
rather than raster art, so the file stays small and prints cleanly.

Structure of a report:
    1  cover                       (canvas-drawn)
    2  profile + the three signs
    3  plate 01                    (full-page section opener)
    4+ personal analysis           (AI text, drop cap, flows over pages)
    n  plate 02
    n+ Sun / Moon / Ascendant, one per page
    n  plate 03
    n+ natal wheel + legend
    n  planet positions + disclaimer
"""

import logging
import os
import re
from datetime import datetime
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

from .ai_interpretation import generate_psychological_report
from .chart_wheel import ChartWheel
from .glyphs import (
    ELEMENT_NAMES, SIGN_ELEMENT, draw_constellation, draw_emblem, draw_planet,
    draw_sign, scatter_stars,
)
from .interpretations import (
    ASCENDANT_DESCRIPTIONS,
    MOON_SIGN_DESCRIPTIONS,
    PLANET_NAMES,
    SIGN_NAMES,
    SUN_SIGN_DESCRIPTIONS,
)

LOGGER = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"

# ── Palette ───────────────────────────────────────────────────────────────────
# Deliberately narrow: paper, ink, one gold, one cool grey for tension.
PAPER = HexColor("#FBF8F2")   # warm near-white
PAPER_2 = HexColor("#F4EDE1")  # plate pages, one step deeper
INK = HexColor("#2B2118")     # body text
INK_SOFT = HexColor("#5C4E40")  # secondary text
MUTED = HexColor("#9A8C7A")   # captions, page numbers
GOLD = HexColor("#B08D57")    # the single accent
GOLD_PALE = HexColor("#E4D3B6")
HAIRLINE = HexColor("#E2D8C8")
COOL = HexColor("#8E7FA6")    # tense aspects, used sparingly

ELEMENT_DOT = {
    "fire": HexColor("#C4703F"),
    "earth": HexColor("#7E8B5B"),
    "air": HexColor("#8E7FA6"),
    "water": HexColor("#5B8296"),
}

PAGE_W, PAGE_H = A4
MARGIN_X = 26 * mm
CONTENT_W = PAGE_W - 2 * MARGIN_X


class PDFGenerationError(Exception):
    pass


# ── Fonts ─────────────────────────────────────────────────────────────────────

def _sans_candidates() -> list[tuple[str, str, str | None]]:
    win = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    dejavu = Path("/usr/share/fonts/truetype/dejavu")
    liberation = Path("/usr/share/fonts/truetype/liberation")
    return [
        ("Arial", str(win / "arial.ttf"), str(win / "arialbd.ttf")),
        ("DejaVuSans", str(win / "DejaVuSans.ttf"), str(win / "DejaVuSans-Bold.ttf")),
        ("DejaVuSans", str(dejavu / "DejaVuSans.ttf"), str(dejavu / "DejaVuSans-Bold.ttf")),
        ("LiberationSans", str(liberation / "LiberationSans-Regular.ttf"),
         str(liberation / "LiberationSans-Bold.ttf")),
    ]


def _serif_candidates() -> list[tuple[str, str, str | None]]:
    """Display face. Georgia first — it has full Cyrillic and reads as editorial."""
    win = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    dejavu = Path("/usr/share/fonts/truetype/dejavu")
    liberation = Path("/usr/share/fonts/truetype/liberation")
    return [
        ("Georgia", str(win / "georgia.ttf"), str(win / "georgiab.ttf")),
        ("TimesNewRoman", str(win / "times.ttf"), str(win / "timesbd.ttf")),
        ("DejaVuSerif", str(dejavu / "DejaVuSerif.ttf"), str(dejavu / "DejaVuSerif-Bold.ttf")),
        ("LiberationSerif", str(liberation / "LiberationSerif-Regular.ttf"),
         str(liberation / "LiberationSerif-Bold.ttf")),
    ]


def _register(candidates) -> tuple[str, str] | None:
    for family, regular_path, bold_path in candidates:
        regular = Path(regular_path)
        if not regular.exists():
            continue
        fn = f"{family}-IC"
        bfn = f"{family}-IC-Bold"
        if fn not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(fn, str(regular)))
        bold = Path(bold_path) if bold_path else None
        if bold and bold.exists():
            if bfn not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(bfn, str(bold)))
        else:
            bfn = fn
        return fn, bfn
    return None


def register_cyrillic_fonts() -> tuple[str, str]:
    """Kept for backward compatibility — returns the sans pair."""
    pair = _register(_sans_candidates())
    if pair is None:
        raise PDFGenerationError("No Cyrillic-compatible TrueType font found on this system")
    return pair


def _load_fonts() -> dict[str, str]:
    sans = _register(_sans_candidates())
    if sans is None:
        raise PDFGenerationError("No Cyrillic-compatible TrueType font found on this system")
    serif = _register(_serif_candidates()) or sans
    return {"sans": sans[0], "sans_b": sans[1], "serif": serif[0], "serif_b": serif[1]}


# ── Canvas helpers ────────────────────────────────────────────────────────────

def _tracked(canvas, text, x, y, font, size, tracking, color, align="left"):
    """Letterspaced text. Tracking is what makes small caps look designed."""
    if not text:
        return
    canvas.saveState()
    canvas.setFont(font, size)
    canvas.setFillColor(color)
    width = canvas.stringWidth(text, font, size) + tracking * max(0, len(text) - 1)
    if align == "center":
        x -= width / 2.0
    elif align == "right":
        x -= width
    # Char spacing lives on the text object, not on the canvas itself.
    tobj = canvas.beginText(x, y)
    tobj.setFont(font, size)
    tobj.setFillColor(color)
    tobj.setCharSpace(tracking)
    tobj.textOut(text)
    canvas.drawText(tobj)
    canvas.restoreState()


def _rule(canvas, x1, y, x2, color=HAIRLINE, width=0.5):
    canvas.saveState()
    canvas.setStrokeColor(color)
    canvas.setLineWidth(width)
    canvas.line(x1, y, x2, y)
    canvas.restoreState()


# ── Page templates ────────────────────────────────────────────────────────────

def _paint(canvas, color):
    canvas.setFillColor(color)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)


def _draw_cover(canvas, doc, F, profile, generated_at, signs):
    """Cover: one large constellation, the name, and a lot of air."""
    sun_sign, moon_sign, asc_sign = signs
    _paint(canvas, PAPER)

    # A very faint field of stars keeps the page from feeling empty.
    canvas.setFillAlpha(0.5)
    scatter_stars(canvas, 0, PAGE_H * 0.42, PAGE_W, PAGE_H * 0.55, GOLD_PALE,
                  count=70, seed=11, max_r=0.9)
    canvas.setFillAlpha(1)

    # Masthead
    _tracked(canvas, "INNER COMPASS", MARGIN_X, PAGE_H - 24 * mm,
             F["sans"], 8, 3.4, INK_SOFT)
    _tracked(canvas, generated_at, PAGE_W - MARGIN_X, PAGE_H - 24 * mm,
             F["sans"], 8, 1.2, MUTED, align="right")
    _rule(canvas, MARGIN_X, PAGE_H - 29 * mm, PAGE_W - MARGIN_X)

    # The reader's sun-sign asterism, large and quiet.
    cx, cy = PAGE_W / 2, PAGE_H - 108 * mm
    if sun_sign:
        draw_constellation(canvas, sun_sign, cx, cy, 96 * mm, GOLD,
                           line_color=GOLD_PALE, star_scale=1.5)
        canvas.setFillAlpha(0.10)
        canvas.setStrokeAlpha(0.10)
        draw_sign(canvas, sun_sign, cx, cy, 78 * mm, GOLD, weight=1.0)
        canvas.setFillAlpha(1)
        canvas.setStrokeAlpha(1)

    # Title block
    _tracked(canvas, "ПЕРСОНАЛЬНИЙ ЗВІТ", PAGE_W / 2, PAGE_H - 176 * mm,
             F["sans"], 8.5, 4.2, GOLD, align="center")

    name = (profile.get("name") or "").strip()
    canvas.setFont(F["serif"], 32)
    canvas.setFillColor(INK)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - 194 * mm, name)

    _rule(canvas, PAGE_W / 2 - 16 * mm, PAGE_H - 202 * mm, PAGE_W / 2 + 16 * mm, GOLD, 0.8)

    birth_date = profile.get("birth_date", "")
    birth_time = profile.get("birth_time", "")
    birthplace = profile.get("birthplace", "")
    line = "  ·  ".join([p for p in (birth_date, birth_time, birthplace) if p])
    _tracked(canvas, line.upper(), PAGE_W / 2, PAGE_H - 211 * mm,
             F["sans"], 8, 1.6, MUTED, align="center")

    # Three glyphs along the foot — the reader's own triad.
    triad = [("СОНЦЕ", sun_sign), ("МІСЯЦЬ", moon_sign), ("АСЦЕНДЕНТ", asc_sign)]
    slot = CONTENT_W / 3.0
    base_y = 46 * mm
    for i, (label, code) in enumerate(triad):
        gx = MARGIN_X + slot * (i + 0.5)
        if code:
            draw_sign(canvas, code, gx, base_y + 14 * mm, 13 * mm, INK, weight=1.3)
            title = SIGN_NAMES.get(code, code)
        else:
            _tracked(canvas, "—", gx, base_y + 12 * mm, F["serif"], 14, 0, HAIRLINE,
                     align="center")
            title = "невідомий"
        canvas.setFont(F["serif"], 11)
        canvas.setFillColor(INK)
        canvas.drawCentredString(gx, base_y + 3 * mm, title)
        _tracked(canvas, label, gx, base_y - 3 * mm, F["sans"], 6.5, 2.6, MUTED,
                 align="center")

    _rule(canvas, MARGIN_X, 26 * mm, PAGE_W - MARGIN_X)
    _tracked(canvas, "МАТЕРІАЛ ДЛЯ САМОРЕФЛЕКСІЇ", PAGE_W / 2, 19 * mm,
             F["sans"], 6.5, 2.4, MUTED, align="center")


def _draw_plate(canvas, doc, F, state):
    """Full-page section opener: deeper paper, one constellation, big numeral."""
    _paint(canvas, PAPER_2)
    canvas.setFillAlpha(0.55)
    scatter_stars(canvas, 0, 0, PAGE_W, PAGE_H, GOLD_PALE, count=90, seed=23, max_r=1.0)
    canvas.setFillAlpha(1)

    code = state.get("plate_sign")
    if code:
        draw_constellation(canvas, code, PAGE_W / 2, PAGE_H * 0.63, 120 * mm,
                           GOLD, line_color=GOLD_PALE, star_scale=1.6)

    _rule(canvas, MARGIN_X, 26 * mm, PAGE_W - MARGIN_X, GOLD_PALE)
    _tracked(canvas, "INNER COMPASS", PAGE_W / 2, 19 * mm, F["sans"], 6.5, 3.0,
             MUTED, align="center")


def _draw_body(canvas, doc, F, state):
    """Running head, hairlines and folio for reading pages.

    Runs in onPageEnd, so it must not paint the background — that happens in
    onPage, before the flowables draw. Painting here would cover the text.
    """
    _tracked(canvas, "INNER COMPASS", MARGIN_X, PAGE_H - 18 * mm,
             F["sans"], 6.5, 2.8, MUTED)
    running = (state.get("section") or "").upper()
    _tracked(canvas, running, PAGE_W - MARGIN_X, PAGE_H - 18 * mm,
             F["sans"], 6.5, 2.4, MUTED, align="right")
    _rule(canvas, MARGIN_X, PAGE_H - 21 * mm, PAGE_W - MARGIN_X)

    _rule(canvas, MARGIN_X, 20 * mm, PAGE_W - MARGIN_X)
    folio = str(doc.page)
    canvas.setFont(F["serif"], 9)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(PAGE_W / 2, 14 * mm, folio)


# ── Styles ────────────────────────────────────────────────────────────────────

def _build_styles(F: dict) -> dict[str, ParagraphStyle]:
    sans, sans_b = F["sans"], F["sans_b"]
    serif, serif_b = F["serif"], F["serif_b"]
    return {
        "display": ParagraphStyle(
            # spaceAfter clears the descenders before the gold rule below.
            "Display", fontName=serif, fontSize=30, leading=34,
            textColor=INK, alignment=TA_LEFT, spaceAfter=6,
        ),
        "plate_num": ParagraphStyle(
            "PlateNum", fontName=serif, fontSize=64, leading=64,
            textColor=GOLD_PALE, alignment=TA_CENTER, spaceAfter=4,
        ),
        "plate_title": ParagraphStyle(
            "PlateTitle", fontName=serif, fontSize=26, leading=32,
            textColor=INK, alignment=TA_CENTER, spaceAfter=6,
        ),
        "plate_sub": ParagraphStyle(
            "PlateSub", fontName=sans, fontSize=9.5, leading=16,
            textColor=INK_SOFT, alignment=TA_CENTER,
        ),
        "h1": ParagraphStyle(
            "H1", fontName=serif, fontSize=20, leading=25,
            textColor=INK, alignment=TA_LEFT, spaceAfter=3, spaceBefore=0,
        ),
        "h2": ParagraphStyle(
            "H2", fontName=serif, fontSize=13.5, leading=19,
            textColor=INK, alignment=TA_LEFT, spaceAfter=2, spaceBefore=8,
        ),
        "kicker": ParagraphStyle(
            "Kicker", fontName=sans, fontSize=7.5, leading=12,
            textColor=GOLD, alignment=TA_LEFT, spaceAfter=1,
        ),
        "lede": ParagraphStyle(
            "Lede", fontName=serif, fontSize=12.5, leading=20,
            textColor=INK_SOFT, alignment=TA_LEFT, spaceAfter=10,
        ),
        # Ragged right, not justified: Ukrainian words are long and ReportLab
        # does not hyphenate, so justification opens rivers between words.
        "body": ParagraphStyle(
            "Body", fontName=sans, fontSize=10.2, leading=17.4,
            textColor=INK, alignment=TA_LEFT, spaceAfter=9,
        ),
        # bulletFontName is unused as a bullet; _ai_section reads it to know
        # which serif face to set the raised initial in.
        "body_drop": ParagraphStyle(
            "BodyDrop", fontName=sans, fontSize=10.2, leading=17.4,
            textColor=INK, alignment=TA_LEFT, spaceAfter=9,
            bulletFontName=serif,
        ),
        "item": ParagraphStyle(
            "Item", fontName=sans, fontSize=9.6, leading=15.2,
            textColor=INK, alignment=TA_LEFT, spaceAfter=4.5,
            leftIndent=6 * mm, bulletIndent=0,
            bulletFontName=sans, bulletFontSize=9.6, bulletColor=GOLD,
        ),
        "pull": ParagraphStyle(
            "Pull", fontName=serif, fontSize=11.5, leading=18.5,
            textColor=INK, alignment=TA_LEFT, spaceAfter=0,
        ),
        "caption": ParagraphStyle(
            "Caption", fontName=sans, fontSize=8.2, leading=13,
            textColor=MUTED, alignment=TA_LEFT, spaceAfter=4,
        ),
        "caption_c": ParagraphStyle(
            "CaptionC", fontName=sans, fontSize=8.2, leading=13,
            textColor=MUTED, alignment=TA_CENTER, spaceAfter=4,
        ),
        "legal": ParagraphStyle(
            "Legal", fontName=sans, fontSize=7.8, leading=12.5,
            textColor=MUTED, alignment=TA_JUSTIFY, spaceAfter=4,
        ),
    }


# ── Small flowables ───────────────────────────────────────────────────────────

class _Marker(Flowable):
    """Zero-size marker that updates page-furniture state as the story lays out.

    The body template paints its running head in onPageEnd, after the page's
    flowables have drawn, so a marker placed at the top of a section is already
    reflected in that same page's header.
    """

    def __init__(self, state: dict, **updates):
        super().__init__()
        self.state = state
        self.updates = updates
        self.width = 0
        self.height = 0

    def wrap(self, aw, ah):
        return (0, 0)

    def draw(self):
        self.state.update(self.updates)


class GlyphBadge(Flowable):
    """A zodiac glyph inside a hairline circle — the sign-section anchor."""

    def __init__(self, code: str, size: float = 22 * mm, ring: bool = True):
        super().__init__()
        self.code = code
        self.size = size
        self.ring = ring
        self.width = size
        self.height = size

    def draw(self):
        c = self.canv
        r = self.size / 2.0
        if self.ring:
            c.saveState()
            c.setStrokeColor(GOLD_PALE)
            c.setLineWidth(0.7)
            c.circle(r, r, r - 0.4, fill=0, stroke=1)
            c.restoreState()
        draw_sign(c, self.code, r, r, self.size * 0.52, GOLD, weight=1.5)


class SignEmblem(Flowable):
    """The full-width illustration that closes a sign page.

    Drawn as vector rather than placed as an image: it stays in the report's
    own palette, prints crisply at any size and costs nothing in file weight.
    """

    def __init__(self, code: str, width: float, size: float = 64 * mm,
                 min_size: float = 34 * mm,
                 pad_top: float = 9 * mm, pad_bottom: float = 3 * mm):
        super().__init__()
        self.code = code
        self.max_size = size
        self.min_size = min_size
        self.width = width
        self.pad_top = pad_top
        self.pad_bottom = pad_bottom
        self.size = size
        self.height = size + pad_top + pad_bottom

    def wrap(self, aw, ah):
        """Take whatever room is left, and step aside entirely if there is none.

        The emblem is decoration; it must never push itself onto a page of its
        own, so it shrinks to fit and disappears below a legible minimum.
        """
        self.width = aw
        room = min(ah - self.pad_top - self.pad_bottom, aw, self.max_size)
        if room < self.min_size:
            self.size = 0
            self.height = 0
            return (0, 0)
        self.size = room
        self.height = room + self.pad_top + self.pad_bottom
        return (aw, self.height)

    def draw(self):
        if self.size <= 0:
            return
        draw_emblem(self.canv, self.code, self.width / 2.0,
                    self.pad_bottom + self.size / 2.0, self.size,
                    INK, GOLD, GOLD_PALE)


class PlanetLegend(Flowable):
    """Two rows of planet glyphs with names — legend under the wheel."""

    def __init__(self, keys: list[str], font: str, width: float, per_row: int = 5):
        super().__init__()
        self.keys = keys
        self.font = font
        self.width = width
        self.per_row = per_row
        rows = max(1, -(-len(keys) // per_row))
        self.row_h = 13 * mm
        self.height = rows * self.row_h

    def draw(self):
        c = self.canv
        col_w = self.width / self.per_row
        for i, key in enumerate(self.keys):
            row = i // self.per_row
            col = i % self.per_row
            cx = col_w * (col + 0.5)
            cy = self.height - row * self.row_h - 5 * mm
            draw_planet(c, key, cx, cy, 6.5 * mm, INK_SOFT, weight=1.2)
            c.setFont(self.font, 7.4)
            c.setFillColor(MUTED)
            c.drawCentredString(cx, cy - 6.5 * mm, PLANET_NAMES.get(key.capitalize(), key))


class AspectLegend(Flowable):
    """Line-style key for the aspect web."""

    def __init__(self, font: str, width: float):
        super().__init__()
        self.font = font
        self.width = width
        self.height = 16 * mm

    def draw(self):
        c = self.canv
        entries = [
            ("Сполучення", "#B08D57", None, "0°"),
            ("Тригон", "#B08D57", None, "120°"),
            ("Секстиль", "#B08D57", (1.4, 1.6), "60°"),
            ("Квадрат", "#8E7FA6", None, "90°"),
            ("Опозиція", "#8E7FA6", None, "180°"),
        ]
        col_w = self.width / len(entries)
        for i, (label, hexcolor, dash, angle) in enumerate(entries):
            x = col_w * i
            y = self.height - 5 * mm
            c.saveState()
            c.setStrokeColor(HexColor(hexcolor))
            c.setLineWidth(0.8)
            if dash:
                c.setDash(dash[0], dash[1])
            c.line(x, y, x + 11 * mm, y)
            c.restoreState()
            c.setFont(self.font, 7.6)
            c.setFillColor(INK_SOFT)
            c.drawString(x, y - 5 * mm, label)
            c.setFillColor(MUTED)
            c.drawString(x, y - 9.5 * mm, angle)


def _hr(color=HAIRLINE, width="100%", thickness=0.5, before=2, after=8):
    return HRFlowable(width=width, thickness=thickness, color=color,
                      spaceBefore=before, spaceAfter=after)


# ── Content builders ──────────────────────────────────────────────────────────

def _escape(text: str) -> str:
    """Escape characters ReportLab's mini-HTML parser would choke on."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _clean_markdown(text: str) -> str:
    """Strip Markdown the model sometimes emits despite being told not to.

    Raw "**зірочки**" and "### заголовки" leaked into earlier reports. Bold is
    converted to ReportLab's <b> tag (applied after _escape, so the tag itself
    survives); everything else is removed.
    """
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)
    text = re.sub(r"(?<!\w)[*_](?=\S)(.+?)(?<=\S)[*_](?!\w)", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"`+", "", text)
    return text


def _bullet_items(raw: str, styles: dict) -> list:
    """Split a "• a\n• b" string into individually bulleted paragraphs."""
    items = []
    for line in str(raw or "").splitlines():
        line = line.strip().lstrip("•").strip()
        if line:
            items.append(Paragraph(_escape(line), styles["item"], bulletText="—"))
    return items


def _column_pair(left_title, left_raw, right_title, right_raw, styles) -> Table:
    """Strengths and challenges side by side, each under a gold rule."""
    def column(title, raw):
        cells = [
            Paragraph(title.upper(), styles["kicker"]),
            _hr(GOLD, "100%", 0.9, 1, 6),
        ]
        cells += _bullet_items(raw, styles)
        return cells

    col_w = (CONTENT_W - 8 * mm) / 2.0
    t = Table([[column(left_title, left_raw), column(right_title, right_raw)]],
              colWidths=[col_w, col_w])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 8 * mm),
        ("LEFTPADDING", (1, 0), (1, -1), 0),
        ("RIGHTPADDING", (1, 0), (1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _pull_quote(text: str, styles: dict) -> Table:
    """Advice block: a gold rule on the left, no fill. Quieter than a box."""
    t = Table([[Paragraph(_escape(text), styles["pull"])]], colWidths=[CONTENT_W - 6 * mm])
    t.setStyle(TableStyle([
        ("LINEBEFORE", (0, 0), (0, -1), 1.6, GOLD),
        ("LEFTPADDING", (0, 0), (-1, -1), 7 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def _element_chip(code: str, styles: dict) -> Table:
    """Tiny coloured dot + element name, e.g. a rust dot for fire."""
    element = SIGN_ELEMENT.get(code)
    if not element:
        return None
    label = Paragraph(f"СТИХІЯ — {ELEMENT_NAMES.get(element, '').upper()}", styles["kicker"])
    dot = _Dot(ELEMENT_DOT.get(element, GOLD))
    t = Table([[dot, label]], colWidths=[5 * mm, 60 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


class _Dot(Flowable):
    def __init__(self, color, r: float = 1.5 * mm):
        super().__init__()
        self.color = color
        self.r = r
        self.width = 2 * r
        self.height = 2 * r

    def draw(self):
        self.canv.setFillColor(self.color)
        self.canv.circle(self.r, self.r, self.r, fill=1, stroke=0)


def _sign_section(kicker: str, code: str, desc: dict, styles: dict, state: dict) -> list:
    """One full page for Sun / Moon / Ascendant."""
    name = desc.get("name") or SIGN_NAMES.get(code, code)
    header = Table(
        [[GlyphBadge(code, 22 * mm),
          [Paragraph(kicker.upper(), styles["kicker"]),
           Paragraph(_escape(name), styles["display"])]]],
        colWidths=[26 * mm, CONTENT_W - 26 * mm],
    )
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    items: list = [
        _Marker(state, section=f"{kicker} · {name}"),
        header,
        Spacer(1, 4 * mm),
    ]
    chip = _element_chip(code, styles)
    if chip is not None:
        items.append(chip)
    items += [_hr(HAIRLINE, "100%", 0.5, 4, 7)]

    if desc.get("represents"):
        items.append(Paragraph(_escape(desc["represents"]), styles["lede"]))

    if desc.get("strengths") or desc.get("challenges"):
        items.append(Spacer(1, 2 * mm))
        items.append(_column_pair(
            "Сильні сторони", desc.get("strengths", ""),
            "Можливі виклики", desc.get("challenges", ""),
            styles,
        ))

    if desc.get("advice"):
        items += [
            Spacer(1, 8 * mm),
            Paragraph("ЩО З ЦИМ РОБИТИ", styles["kicker"]),
            Spacer(1, 2 * mm),
            _pull_quote(desc["advice"], styles),
        ]

    # Closes the page: fills the empty lower half and gives each sign a face.
    items.append(SignEmblem(code, CONTENT_W))
    return items


def _plate(number: str, title: str, subtitle: str, sign_code: str | None,
           styles: dict, state: dict) -> list:
    """A full-page section opener rendered on the 'plate' template."""
    return [
        # The marker has to fire on the *previous* page: the plate template
        # paints its constellation in onPage, which runs before the plate
        # page's own flowables get a chance to draw.
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


def _profile_page(profile: dict, signs: tuple, styles: dict, F: dict, state: dict) -> list:
    """Page 2: who this report is about, in a clean definition list."""
    sun_sign, moon_sign, asc_sign = signs
    rows = [
        ("Ім'я", profile.get("name") or "—"),
        ("Дата народження", profile.get("birth_date") or "—"),
        ("Час народження", profile.get("birth_time") or "—"),
        ("Місце народження", profile.get("birthplace") or "—"),
    ]
    data = [[Paragraph(k.upper(), styles["kicker"]),
             Paragraph(_escape(str(v)), styles["body"])] for k, v in rows]
    table = Table(data, colWidths=[48 * mm, CONTENT_W - 48 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, HAIRLINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    # Three sign cards
    def card(label, code):
        if not code:
            return [
                Paragraph(label.upper(), styles["kicker"]),
                Spacer(1, 3 * mm),
                Paragraph("невідомий", styles["caption"]),
            ]
        return [
            Paragraph(label.upper(), styles["kicker"]),
            Spacer(1, 3 * mm),
            GlyphBadge(code, 18 * mm),
            Spacer(1, 3 * mm),
            Paragraph(_escape(SIGN_NAMES.get(code, code)), styles["h2"]),
            Paragraph(ELEMENT_NAMES.get(SIGN_ELEMENT.get(code, ""), ""), styles["caption"]),
        ]

    col_w = CONTENT_W / 3.0
    cards = Table([[card("Сонце", sun_sign), card("Місяць", moon_sign),
                    card("Асцендент", asc_sign)]],
                  colWidths=[col_w, col_w, col_w])
    cards.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEAFTER", (0, 0), (-2, -1), 0.4, HAIRLINE),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("LEFTPADDING", (1, 0), (-1, -1), 8 * mm),
        ("RIGHTPADDING", (0, 0), (-2, -1), 8 * mm),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    return [
        _Marker(state, section="Профіль"),
        Paragraph("ЗВІТ ПІДГОТОВАНО ДЛЯ", styles["kicker"]),
        Paragraph(_escape(profile.get("name") or ""), styles["display"]),
        _hr(GOLD, "18%", 1.2, 5, 9),
        Spacer(1, 4 * mm),
        table,
        Spacer(1, 14 * mm),
        Paragraph("ТРИ ОПОРИ ВАШОЇ КАРТИ", styles["kicker"]),
        _hr(HAIRLINE, "100%", 0.5, 3, 8),
        cards,
        Spacer(1, 14 * mm),
        Paragraph(
            "Сонце описує напрям, у якому ви рухаєтесь. Місяць — те, що ви відчуваєте "
            "по дорозі. Асцендент — те, яким вас бачать інші, перш ніж дізнаються ближче. "
            "Далі кожна з цих опор розглянута окремо.",
            styles["caption"],
        ),
    ]


def _ai_section(astrology_data: dict, styles: dict, profile: dict | None,
                state: dict) -> list:
    """The AI-written personal text, opened with a drop cap."""
    try:
        ai_text = generate_psychological_report(astrology_data, profile)
        LOGGER.info("AI psychological report added to PDF")
    except Exception as error:
        LOGGER.exception("AI report generation failed: %s", error)
        ai_text = (
            "Не вдалося отримати детальну інтерпретацію для цього звіту. "
            "Нижче наведено базовий аналіз на основі вашої натальної карти."
        )

    blocks = [b.strip() for b in re.split(r"\n\s*\n", ai_text or "") if b.strip()]
    if not blocks:
        blocks = [ai_text.strip()] if ai_text and ai_text.strip() else []

    items: list = [_Marker(state, section="Персональний аналіз")]

    for i, block in enumerate(blocks):
        html = _clean_markdown(_escape(block)).replace("\n", "<br/>")
        if i == 0:
            # Raised initial set inline. A true drop cap would need the next
            # lines to wrap around the letter, which platypus cannot do, and a
            # bullet-based initial leaves a visible gap before the first word.
            stripped = html.lstrip()
            if stripped and stripped[0].isalpha():
                st = styles["body_drop"]
                items.append(Spacer(1, 5 * mm))
                items.append(Paragraph(
                    f'<font name="{st.bulletFontName}" size="21" '
                    f'color="#{GOLD.hexval()[2:]}">{stripped[0]}</font>'
                    f'{stripped[1:]}',
                    st,
                ))
                continue
        items.append(Paragraph(html, styles["body"]))

    return items


def _wheel_page(astrology_data: dict, styles: dict, F: dict, state: dict) -> list:
    """The natal wheel with its legends."""
    present = [p["key"] for p in ChartWheel(astrology_data).positions]
    return [
        _Marker(state, section="Карта неба"),
        Paragraph("МАПА МОМЕНТУ", styles["kicker"]),
        Paragraph("Ваша натальна карта", styles["display"]),
        _hr(GOLD, "18%", 1.2, 5, 8),
        Paragraph(
            "Кожна планета стоїть на своєму справжньому градусі на момент вашого "
            "народження. Лінії всередині — кути між ними: теплим кольором позначені "
            "м'які зв'язки, холодним — напружені.",
            styles["caption"],
        ),
        Spacer(1, 5 * mm),
        ChartWheel(astrology_data, size=CONTENT_W - 12 * mm, font=F["sans"]),
        Spacer(1, 8 * mm),
        _hr(HAIRLINE, "100%", 0.5, 0, 6),
        PlanetLegend(present, F["sans"], CONTENT_W),
        Spacer(1, 3 * mm),
        _hr(HAIRLINE, "100%", 0.5, 0, 6),
        AspectLegend(F["sans"], CONTENT_W),
    ]


def _normalize_planets(planets_data) -> list[dict]:
    """Accept either a list of dicts (with a "name" key) or a dict keyed by
    planet name, as produced by services.astrology._extract_planets_data.

    Returns a list of dicts with keys: key, name, sign, degree, retrograde.
    """
    normalized: list[dict] = []

    if isinstance(planets_data, dict):
        items = list(planets_data.items())
    elif isinstance(planets_data, (list, tuple)):
        items = [(p.get("name", "") if isinstance(p, dict) else str(p), p)
                 for p in planets_data]
    else:
        return normalized

    for raw_name, data in items:
        if not isinstance(data, dict):
            continue
        name = str(raw_name or data.get("name", ""))
        # astrology.py uses lowercase keys ("sun"); PLANET_NAMES uses "Sun".
        key = name if name in PLANET_NAMES else name.capitalize()
        try:
            degree = float(data.get("degree", 0) or 0)
        except (TypeError, ValueError):
            degree = 0.0
        normalized.append({
            "key": name.lower(),
            "name": PLANET_NAMES.get(key, name),
            "sign": data.get("sign", ""),
            "degree": degree,
            "retrograde": bool(data.get("retrograde")),
        })

    return normalized


class _PlanetGlyphCell(Flowable):
    def __init__(self, key: str, size: float = 5 * mm):
        super().__init__()
        self.key = key
        self.size = size
        self.width = size
        self.height = size

    def draw(self):
        draw_planet(self.canv, self.key, self.size / 2, self.size / 2,
                    self.size, INK_SOFT, weight=1.2)


class _SignGlyphCell(Flowable):
    def __init__(self, code: str, size: float = 4.6 * mm):
        super().__init__()
        self.code = code
        self.size = size
        self.width = size
        self.height = size

    def draw(self):
        draw_sign(self.canv, self.code, self.size / 2, self.size / 2,
                  self.size, INK_SOFT, weight=1.2)


def _build_planets_table(planets_data, styles: dict) -> Table:
    """Minimal ledger: hairlines only, glyphs in the gutters, no fills."""
    head = [
        "", Paragraph("ПЛАНЕТА", styles["kicker"]), "",
        Paragraph("ЗНАК", styles["kicker"]), Paragraph("ГРАДУС", styles["kicker"]),
    ]
    rows = [head]
    for p in _normalize_planets(planets_data):
        sign_name = SIGN_NAMES.get(p["sign"], p["sign"])
        degree = f"{p['degree']:.1f}°"
        if p["retrograde"]:
            degree += "  R"
        rows.append([
            _PlanetGlyphCell(p["key"]),
            Paragraph(_escape(p["name"]), styles["body"]),
            _SignGlyphCell(p["sign"]) if p["sign"] in SIGN_ELEMENT else "",
            Paragraph(_escape(sign_name), styles["body"]),
            Paragraph(degree, styles["body"]),
        ])

    col = [10 * mm, 46 * mm, 9 * mm, 50 * mm, CONTENT_W - 115 * mm]
    t = Table(rows, colWidths=col, repeatRows=1)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, GOLD),
        ("LINEBELOW", (0, 1), (-1, -2), 0.35, HAIRLINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (4, 0), (4, -1), "RIGHT"),
    ]))
    return t


# ── Document assembly ─────────────────────────────────────────────────────────

def _make_document(output_path: Path, F: dict, profile: dict, generated_at: str,
                   signs: tuple, state: dict) -> BaseDocTemplate:
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
        pagesize=A4,
        leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=28 * mm, bottomMargin=26 * mm,
        title="Inner Compass — персональний звіт",
        author="Inner Compass",
        subject="Персональний психологічний звіт",
    )
    doc.addPageTemplates([
        PageTemplate(
            id="cover", frames=[frame_cover],
            onPage=lambda c, d: _draw_cover(c, d, F, profile, generated_at, signs),
        ),
        PageTemplate(
            id="plate", frames=[frame_plate],
            onPage=lambda c, d: _draw_plate(c, d, F, state),
        ),
        PageTemplate(
            id="body", frames=[frame_body],
            # onPageEnd, not onPage: markers placed inside the page's flowables
            # must already have run before the running head is painted.
            onPage=lambda c, d: _paint(c, PAPER),
            onPageEnd=lambda c, d: _draw_body(c, d, F, state),
        ),
    ])
    return doc


# ── Public API ────────────────────────────────────────────────────────────────

def generate_report(profile: dict, telegram_user_id: int, astrology_data: dict) -> Path:
    """Generate the designed PDF report.

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

    F = _load_fonts()
    styles = _build_styles(F)
    state: dict = {"section": "", "plate_sign": None}
    generated_at = datetime.now().strftime("%d.%m.%Y")

    sun_sign = astrology_data.get("sun_sign")
    moon_sign = astrology_data.get("moon_sign")
    asc_sign = astrology_data.get("ascendant_sign")
    signs = (sun_sign, moon_sign, asc_sign)
    planets_data = astrology_data.get("planets", {})

    story: list = [NextPageTemplate("body"), PageBreak()]

    # Page 2 — profile
    story += _profile_page(profile, signs, styles, F, state)

    # 01 — personal analysis
    story += _plate("01", "Персональний аналіз",
                    "Написано на основі вашої карти", sun_sign, styles, state)
    story += _ai_section(astrology_data, styles, profile, state)

    # 02 — the three pillars, one page each
    story += _plate("02", "Три опори",
                    "Сонце · Місяць · Асцендент", moon_sign or sun_sign, styles, state)

    pillars = [
        ("Сонце", sun_sign, SUN_SIGN_DESCRIPTIONS.get(sun_sign or "")),
        ("Місяць", moon_sign, MOON_SIGN_DESCRIPTIONS.get(moon_sign or "")),
        ("Асцендент", asc_sign, ASCENDANT_DESCRIPTIONS.get(asc_sign or "")),
    ]
    first = True
    for kicker, code, desc in pillars:
        if code and desc:
            if not first:
                story.append(PageBreak())
            story += _sign_section(kicker, code, desc, styles, state)
            first = False
        elif kicker == "Асцендент" and not code:
            if not first:
                story.append(PageBreak())
            story += [
                _Marker(state, section="Асцендент"),
                Paragraph("АСЦЕНДЕНТ", styles["kicker"]),
                Paragraph("Не розрахований", styles["display"]),
                _hr(GOLD, "18%", 1.2, 5, 9),
                Paragraph(
                    "Асцендент змінюється приблизно щодві години, тому його неможливо "
                    "визначити без точного часу народження. Якщо ви знайдете цей час у "
                    "документах — надішліть його нам, і ми перерахуємо звіт: додасться "
                    "цілий шар про те, як вас сприймають ззовні.",
                    styles["body"],
                ),
            ]
            first = False

    # 03 — the chart itself
    story += _plate("03", "Карта неба",
                    "Положення планет і кути між ними", asc_sign or sun_sign,
                    styles, state)
    story += _wheel_page(astrology_data, styles, F, state)

    story += [
        PageBreak(),
        _Marker(state, section="Позиції планет"),
        Paragraph("ТЕХНІЧНІ ДАНІ", styles["kicker"]),
        Paragraph("Позиції планет", styles["display"]),
        _hr(GOLD, "18%", 1.2, 5, 9),
        Spacer(1, 3 * mm),
        _build_planets_table(planets_data, styles),
        Spacer(1, 16 * mm),
        _hr(HAIRLINE, "100%", 0.5, 0, 6),
        Paragraph(
            "Цей матеріал створено для саморефлексії та особистого розвитку. "
            "Він не є медичною, психологічною, юридичною чи фінансовою рекомендацією "
            "та не передбачає майбутнє. Астрологічні символи використані як мова для "
            "роздумів про себе, а не як інструмент вимірювання.",
            styles["legal"],
        ),
        Spacer(1, 6 * mm),
        Paragraph(f"Inner Compass · звіт створено {generated_at}", styles["caption"]),
    ]

    doc = _make_document(output_path, F, profile, generated_at, signs, state)

    try:
        doc.build(story)
    except Exception as error:
        LOGGER.exception("PDF generation failed: %s", error)
        raise PDFGenerationError("Failed to generate PDF report") from error

    return output_path


def generate_demo_report(profile: dict, telegram_user_id: int) -> Path:
    """Legacy demo report without astrology data. Kept for backward compatibility."""
    return generate_report(
        profile,
        telegram_user_id,
        {
            "sun_sign": None, "moon_sign": None, "ascendant_sign": None,
            "planets": {}, "houses": [], "aspects": [], "birth_time_known": False,
        },
    )
