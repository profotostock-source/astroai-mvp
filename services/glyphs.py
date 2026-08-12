"""Vector zodiac and planet glyphs drawn directly on a ReportLab canvas.

Why vector instead of a symbol font: the report has to render identically on a
Windows dev box and a Linux server, and the font fallback chain (Arial ->
DejaVu -> Liberation) does not reliably contain the astrological block
U+2600..U+2653. A missing glyph renders as an empty box, which already
happened once in this project. Drawing the shapes ourselves removes the
dependency entirely and gives crisp output at any size.

Every glyph is designed inside a 0..100 square and mapped onto the page by
_Pen, so a glyph is always requested as "draw sign X centred at (x, y) with
this height".

Public API:
    draw_sign(canvas, code, cx, cy, size, color, weight)
    draw_planet(canvas, key, cx, cy, size, color, weight)
    draw_constellation(canvas, code, cx, cy, size, color)
    SIGN_ORDER, SIGN_ELEMENT
"""

from __future__ import annotations

import math

# Zodiac order, used for absolute-longitude maths in the chart wheel.
SIGN_ORDER = [
    "Ari", "Tau", "Gem", "Can", "Leo", "Vir",
    "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis",
]

SIGN_ELEMENT = {
    "Ari": "fire", "Leo": "fire", "Sag": "fire",
    "Tau": "earth", "Vir": "earth", "Cap": "earth",
    "Gem": "air", "Lib": "air", "Aqu": "air",
    "Can": "water", "Sco": "water", "Pis": "water",
}

ELEMENT_NAMES = {
    "fire": "Вогонь",
    "earth": "Земля",
    "air": "Повітря",
    "water": "Вода",
}


# ── Pen ───────────────────────────────────────────────────────────────────────

class _Pen:
    """Maps the 0..100 design square onto the page and buffers one path."""

    def __init__(self, canvas, cx: float, cy: float, size: float):
        self.c = canvas
        self.scale = size / 100.0
        self.ox = cx - size / 2.0
        self.oy = cy - size / 2.0
        self.path = None

    def _pt(self, x: float, y: float) -> tuple[float, float]:
        return (self.ox + x * self.scale, self.oy + y * self.scale)

    def move(self, x, y):
        if self.path is None:
            self.path = self.c.beginPath()
        self.path.moveTo(*self._pt(x, y))
        return self

    def line(self, x, y):
        self.path.lineTo(*self._pt(x, y))
        return self

    def curve(self, x1, y1, x2, y2, x3, y3):
        p1 = self._pt(x1, y1)
        p2 = self._pt(x2, y2)
        p3 = self._pt(x3, y3)
        self.path.curveTo(p1[0], p1[1], p2[0], p2[1], p3[0], p3[1])
        return self

    def close(self):
        self.path.close()
        return self

    def stroke(self):
        """Flush the buffered path as a stroke and start a new one."""
        if self.path is not None:
            self.c.drawPath(self.path, fill=0, stroke=1)
            self.path = None
        return self

    def circle(self, x, y, r, fill=0):
        """Standalone circle — flushes any pending path first."""
        self.stroke()
        px, py = self._pt(x, y)
        self.c.circle(px, py, r * self.scale, fill=fill, stroke=0 if fill else 1)
        return self

    def arc_circle(self, x, y, r):
        """Circle as part of the current path (so it strokes with the rest)."""
        if self.path is None:
            self.path = self.c.beginPath()
        px, py = self._pt(x, y)
        rr = r * self.scale
        # ReportLab paths have no arc primitive on Path objects in all versions,
        # so approximate with four beziers (k = 0.5523).
        k = 0.5523 * rr
        self.path.moveTo(px + rr, py)
        self.path.curveTo(px + rr, py + k, px + k, py + rr, px, py + rr)
        self.path.curveTo(px - k, py + rr, px - rr, py + k, px - rr, py)
        self.path.curveTo(px - rr, py - k, px - k, py - rr, px, py - rr)
        self.path.curveTo(px + k, py - rr, px + rr, py - k, px + rr, py)
        return self


# ── Zodiac glyph definitions ──────────────────────────────────────────────────
# Each takes a _Pen and draws inside the 0..100 square. Origin is bottom-left,
# matching PDF coordinates, so y grows upward.

def _ari(p: _Pen):
    # Ram: central stem splitting into two outward-curling horns.
    p.move(50, 8).line(50, 55)
    p.move(50, 55).curve(50, 82, 22, 90, 13, 70).curve(6, 55, 22, 44, 32, 54)
    p.move(50, 55).curve(50, 82, 78, 90, 87, 70).curve(94, 55, 78, 44, 68, 54)
    p.stroke()


def _tau(p: _Pen):
    # Bull: circle with a wide upward-opening crescent resting on it.
    p.arc_circle(50, 30, 22).stroke()
    p.move(15, 84).curve(15, 56, 32, 50, 50, 50).curve(68, 50, 85, 56, 85, 84)
    p.stroke()


def _gem(p: _Pen):
    # Twins: two uprights closed by a bowed bar top and bottom.
    p.move(34, 22).line(34, 78)
    p.move(66, 22).line(66, 78)
    p.move(22, 74).curve(35, 88, 65, 88, 78, 74)
    p.move(22, 26).curve(35, 12, 65, 12, 78, 26)
    p.stroke()


def _can(p: _Pen):
    # Crab: two opposed curls (the "69" figure laid on its side).
    p.move(30, 56).curve(38, 80, 68, 82, 82, 66)
    p.move(70, 44).curve(62, 20, 32, 18, 18, 34)
    p.stroke()
    p.circle(28, 62, 10)
    p.circle(72, 38, 10)


def _leo(p: _Pen):
    # Lion: small head-circle with a long mane loop and an upturned tail.
    p.arc_circle(30, 30, 14).stroke()
    p.move(43, 36).curve(52, 58, 42, 80, 62, 80).curve(80, 80, 82, 58, 70, 46)
    p.curve(60, 36, 76, 26, 88, 38)
    p.stroke()


def _vir(p: _Pen):
    # Maiden: three uprights, the last one closing into a loop.
    p.move(16, 22).line(16, 68)
    p.move(16, 68).curve(16, 82, 38, 82, 38, 68)
    p.move(38, 68).line(38, 22)
    p.move(38, 68).curve(38, 82, 60, 82, 60, 68)
    p.move(60, 68).line(60, 30)
    p.move(60, 40).curve(66, 22, 92, 26, 88, 48)
    p.curve(85, 64, 66, 62, 58, 46)
    p.stroke()


def _lib(p: _Pen):
    # Scales: a base line, and above it a bar broken by a half circle.
    p.move(12, 20).line(88, 20)
    p.move(12, 42).line(32, 42)
    p.move(32, 42).curve(32, 66, 68, 66, 68, 42)
    p.move(68, 42).line(88, 42)
    p.stroke()


def _sco(p: _Pen):
    # Scorpion: Virgo's uprights ending in a raised sting.
    p.move(14, 22).line(14, 68)
    p.move(14, 68).curve(14, 82, 36, 82, 36, 68)
    p.move(36, 68).line(36, 22)
    p.move(36, 68).curve(36, 82, 58, 82, 58, 68)
    p.move(58, 68).line(58, 26)
    p.move(58, 26).line(88, 56)
    p.move(88, 56).line(70, 56)
    p.move(88, 56).line(88, 38)
    p.stroke()


def _sag(p: _Pen):
    # Archer: arrow to the upper right with the bow-string crossbar.
    p.move(16, 16).line(82, 82)
    p.move(82, 82).line(56, 82)
    p.move(82, 82).line(82, 56)
    p.move(30, 60).line(58, 32)
    p.stroke()


def _cap(p: _Pen):
    # Sea-goat: a sharp V rising into the fish tail's spiral.
    p.move(14, 74).line(36, 24).line(54, 62)
    p.move(54, 62).curve(66, 86, 90, 78, 84, 54)
    p.curve(79, 36, 58, 38, 58, 54)
    p.stroke()


def _wave(p: _Pen, base: float):
    p.move(12, base)
    p.curve(20, base + 14, 28, base + 14, 36, base)
    p.curve(44, base - 14, 52, base - 14, 60, base)
    p.curve(68, base + 14, 76, base + 14, 88, base + 4)


def _aqu(p: _Pen):
    # Water-bearer: two parallel waves.
    _wave(p, 60)
    _wave(p, 34)
    p.stroke()


def _pis(p: _Pen):
    # Fishes: two arcs turned away from each other, tied by a bar.
    p.move(30, 84).curve(12, 66, 12, 34, 30, 16)
    p.move(70, 84).curve(88, 66, 88, 34, 70, 16)
    p.move(18, 50).line(82, 50)
    p.stroke()


_SIGN_DRAW = {
    "Ari": _ari, "Tau": _tau, "Gem": _gem, "Can": _can,
    "Leo": _leo, "Vir": _vir, "Lib": _lib, "Sco": _sco,
    "Sag": _sag, "Cap": _cap, "Aqu": _aqu, "Pis": _pis,
}


# ── Planet glyph definitions ──────────────────────────────────────────────────

def _cross(p: _Pen, cx, cy, half):
    p.move(cx, cy - half).line(cx, cy + half)
    p.move(cx - half, cy).line(cx + half, cy)


def _pl_sun(p: _Pen):
    p.arc_circle(50, 50, 32).stroke()
    p.circle(50, 50, 7, fill=1)


def _pl_moon(p: _Pen):
    # Crescent as one closed shape: outer arc out, inner arc back.
    p.move(66, 86).curve(30, 74, 30, 26, 66, 14)
    p.curve(44, 34, 44, 66, 66, 86)
    p.stroke()


def _pl_mercury(p: _Pen):
    p.arc_circle(50, 52, 20).stroke()
    p.move(34, 74).curve(34, 94, 66, 94, 66, 74)   # horns
    _cross(p, 50, 20, 12)
    p.stroke()


def _pl_venus(p: _Pen):
    p.arc_circle(50, 62, 22).stroke()
    _cross(p, 50, 26, 14)
    p.stroke()


def _pl_mars(p: _Pen):
    p.arc_circle(42, 40, 24).stroke()
    p.move(59, 57).line(86, 84)
    p.move(86, 84).line(64, 84)
    p.move(86, 84).line(86, 62)
    p.stroke()


def _pl_jupiter(p: _Pen):
    p.move(22, 74).curve(22, 92, 52, 92, 50, 68)
    p.line(50, 16)
    p.move(24, 16).line(80, 16)
    p.stroke()


def _pl_saturn(p: _Pen):
    p.move(28, 74).line(66, 74)
    p.move(44, 88).line(44, 40)
    p.move(44, 40).curve(56, 20, 82, 26, 78, 44)
    p.curve(75, 58, 58, 58, 52, 46)
    p.stroke()


def _pl_uranus(p: _Pen):
    p.move(50, 88).line(50, 40)
    p.move(24, 70).line(76, 70)
    p.move(24, 88).line(24, 52)
    p.move(76, 88).line(76, 52)
    p.stroke()
    p.circle(50, 24, 12)
    p.circle(50, 24, 4, fill=1)


def _pl_neptune(p: _Pen):
    p.move(20, 80).line(20, 52)
    p.move(80, 80).line(80, 52)
    p.move(50, 88).line(50, 16)
    p.move(20, 52).curve(20, 26, 80, 26, 80, 52)
    p.move(28, 16).line(72, 16)
    p.stroke()


def _pl_pluto(p: _Pen):
    p.move(24, 16).line(24, 88).line(56, 88)
    p.curve(76, 88, 76, 58, 56, 58).line(24, 58)
    p.stroke()
    p.circle(58, 74, 9)


_PLANET_DRAW = {
    "sun": _pl_sun, "moon": _pl_moon, "mercury": _pl_mercury,
    "venus": _pl_venus, "mars": _pl_mars, "jupiter": _pl_jupiter,
    "saturn": _pl_saturn, "uranus": _pl_uranus, "neptune": _pl_neptune,
    "pluto": _pl_pluto,
}


# ── Public API ────────────────────────────────────────────────────────────────

def draw_sign(canvas, code: str, cx: float, cy: float, size: float,
              color, weight: float = 1.4) -> bool:
    """Draw a zodiac glyph centred at (cx, cy). Returns False if unknown."""
    draw = _SIGN_DRAW.get(code)
    if draw is None:
        return False
    canvas.saveState()
    canvas.setStrokeColor(color)
    canvas.setFillColor(color)
    canvas.setLineWidth(weight * size / 40.0)
    canvas.setLineCap(1)
    canvas.setLineJoin(1)
    try:
        draw(_Pen(canvas, cx, cy, size))
    finally:
        canvas.restoreState()
    return True


def draw_planet(canvas, key: str, cx: float, cy: float, size: float,
                color, weight: float = 1.3) -> bool:
    """Draw a planet glyph centred at (cx, cy). Returns False if unknown."""
    draw = _PLANET_DRAW.get(str(key).lower())
    if draw is None:
        return False
    canvas.saveState()
    canvas.setStrokeColor(color)
    canvas.setFillColor(color)
    canvas.setLineWidth(weight * size / 40.0)
    canvas.setLineCap(1)
    canvas.setLineJoin(1)
    try:
        draw(_Pen(canvas, cx, cy, size))
    finally:
        canvas.restoreState()
    return True


# ── Constellations ────────────────────────────────────────────────────────────
# Star positions in the same 0..100 square, roughly following the real
# asterisms. Used as a light decorative motif behind section titles.

CONSTELLATIONS: dict[str, tuple[list[tuple[float, float, float]], list[tuple[int, int]]]] = {
    "Ari": ([(18, 30, 1.0), (46, 46, 1.6), (70, 62, 1.2), (86, 72, 0.9)],
            [(0, 1), (1, 2), (2, 3)]),
    "Tau": ([(14, 26, 1.0), (40, 44, 1.7), (58, 40, 1.0), (78, 66, 1.2), (86, 24, 0.9)],
            [(0, 1), (1, 2), (1, 3), (2, 4)]),
    "Gem": ([(24, 20, 1.0), (30, 52, 1.4), (36, 80, 1.6), (66, 78, 1.5), (72, 50, 1.2), (78, 20, 1.0)],
            [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (1, 4)]),
    "Can": ([(30, 70, 1.0), (48, 52, 1.5), (46, 26, 1.0), (74, 62, 1.1), (68, 84, 0.9)],
            [(0, 1), (1, 2), (1, 3), (3, 4)]),
    "Leo": ([(16, 34, 1.6), (28, 60, 1.2), (22, 80, 1.0), (46, 78, 1.1), (58, 56, 1.0), (82, 46, 1.5), (76, 70, 1.0)],
            [(0, 1), (1, 2), (2, 3), (3, 4), (4, 6), (6, 5), (0, 4)]),
    "Vir": ([(18, 74, 1.1), (38, 62, 1.3), (54, 74, 1.0), (58, 44, 1.6), (80, 34, 1.1), (34, 30, 1.0)],
            [(0, 1), (1, 2), (1, 3), (3, 4), (3, 5)]),
    "Lib": ([(22, 40, 1.3), (44, 66, 1.4), (72, 58, 1.2), (60, 28, 1.0)],
            [(0, 1), (1, 2), (2, 3), (3, 0)]),
    "Sco": ([(20, 78, 1.2), (26, 60, 1.0), (40, 52, 1.7), (56, 42, 1.1), (70, 30, 1.0), (84, 36, 1.2)],
            [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]),
    "Sag": ([(20, 34, 1.1), (36, 58, 1.3), (52, 40, 1.2), (66, 66, 1.4), (84, 48, 1.0), (44, 78, 1.0)],
            [(0, 1), (1, 2), (2, 3), (3, 4), (1, 5), (5, 3)]),
    "Cap": ([(16, 62, 1.2), (34, 74, 1.0), (58, 60, 1.1), (78, 38, 1.3), (48, 28, 1.0)],
            [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)]),
    "Aqu": ([(18, 70, 1.1), (36, 60, 1.3), (52, 68, 1.0), (68, 54, 1.2), (82, 36, 1.0), (44, 32, 0.9)],
            [(0, 1), (1, 2), (2, 3), (3, 4), (1, 5)]),
    "Pis": ([(16, 40, 1.0), (34, 52, 1.2), (54, 46, 1.1), (74, 62, 1.3), (86, 80, 1.0), (24, 74, 0.9)],
            [(0, 1), (1, 2), (2, 3), (3, 4), (1, 5)]),
}


def draw_constellation(canvas, code: str, cx: float, cy: float, size: float,
                       color, line_color=None, star_scale: float = 1.0) -> bool:
    """Draw the sign's asterism: faint connecting lines plus filled stars."""
    data = CONSTELLATIONS.get(code)
    if data is None:
        return False
    stars, edges = data
    pen_scale = size / 100.0
    ox = cx - size / 2.0
    oy = cy - size / 2.0

    def pt(i):
        sx, sy, _ = stars[i]
        return (ox + sx * pen_scale, oy + sy * pen_scale)

    canvas.saveState()
    canvas.setStrokeColor(line_color if line_color is not None else color)
    canvas.setLineWidth(max(0.25, size / 220.0))
    canvas.setLineCap(1)
    for a, b in edges:
        pa, pb = pt(a), pt(b)
        canvas.line(pa[0], pa[1], pb[0], pb[1])
    canvas.setFillColor(color)
    for i, (_, _, mag) in enumerate(stars):
        px, py = pt(i)
        canvas.circle(px, py, max(0.6, mag * star_scale * size / 90.0), fill=1, stroke=0)
    canvas.restoreState()
    return True


def scatter_stars(canvas, x: float, y: float, w: float, h: float, color,
                  count: int = 40, seed: int = 7, max_r: float = 1.1):
    """Deterministic star field for cover / divider pages.

    Uses a fixed LCG rather than random so a regenerated report is identical.
    """
    canvas.saveState()
    canvas.setFillColor(color)
    state = seed * 2654435761 % 2147483647
    for _ in range(count):
        state = (state * 1103515245 + 12345) % 2147483648
        fx = (state / 2147483648.0)
        state = (state * 1103515245 + 12345) % 2147483648
        fy = (state / 2147483648.0)
        state = (state * 1103515245 + 12345) % 2147483648
        fr = (state / 2147483648.0)
        canvas.circle(x + fx * w, y + fy * h, 0.3 + fr * max_r, fill=1, stroke=0)
    canvas.restoreState()


def polar(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    """Helper shared with the chart wheel: point at r, deg (0 = east, CCW)."""
    a = math.radians(deg)
    return (cx + r * math.cos(a), cy + r * math.sin(a))


def _element_band(canvas, element: str, cx: float, cy: float,
                  r_lo: float, r_hi: float, color):
    """Ornament ring between two radii. Each element gets its own texture, so
    the four families read differently at a glance without any labels.
    """
    band = (r_lo + r_hi) / 2.0
    span = r_hi - r_lo
    canvas.setStrokeColor(color)
    canvas.setFillColor(color)

    if element == "fire":
        # Radiating ticks, every third one longer.
        for k in range(72):
            ang = k * 5.0
            tall = (k % 3 == 0)
            canvas.setLineWidth(0.55 if tall else 0.35)
            p1 = polar(cx, cy, r_lo + span * 0.18, ang)
            p2 = polar(cx, cy, r_hi - span * (0.16 if tall else 0.46), ang)
            canvas.line(p1[0], p1[1], p2[0], p2[1])

    elif element == "earth":
        # A measured course of small squares.
        half = max(0.5, span * 0.13)
        for k in range(36):
            px, py = polar(cx, cy, band, k * 10.0)
            canvas.rect(px - half, py - half, 2 * half, 2 * half, fill=1, stroke=0)

    elif element == "air":
        # Two dashed rings, offset — motion without weight.
        canvas.saveState()
        canvas.setLineWidth(0.5)
        canvas.setDash(2.2, 3.2)
        canvas.circle(cx, cy, r_lo + span * 0.30, fill=0, stroke=1)
        canvas.setDash(1.2, 3.6)
        canvas.circle(cx, cy, r_hi - span * 0.26, fill=0, stroke=1)
        canvas.restoreState()

    else:  # water
        # A sine wave closed into a ring.
        canvas.setLineWidth(0.55)
        amp = span * 0.30
        path = canvas.beginPath()
        steps = 360
        for k in range(steps + 1):
            ang = k * 360.0 / steps
            r = band + amp * math.sin(math.radians(ang * 12.0))
            px, py = polar(cx, cy, r, ang)
            if k == 0:
                path.moveTo(px, py)
            else:
                path.lineTo(px, py)
        path.close()
        canvas.drawPath(path, fill=0, stroke=1)


def draw_emblem(canvas, code: str, cx: float, cy: float, size: float,
                ink, gold, pale, weight: float = 1.3) -> bool:
    """The illustration for a sign: a roundel holding its glyph, its asterism
    and an ornament ring keyed to its element.

    Drawn rather than generated, so it stays on-brand, prints crisply at any
    size and adds nothing to the file weight.
    """
    if code not in SIGN_ORDER:
        return False

    element = SIGN_ELEMENT.get(code, "fire")
    r_out = size * 0.50
    r_mid = size * 0.405
    r_in = size * 0.345

    canvas.saveState()
    canvas.setLineCap(1)

    canvas.setStrokeColor(pale)
    canvas.setLineWidth(0.8)
    canvas.circle(cx, cy, r_out, fill=0, stroke=1)
    canvas.setLineWidth(0.4)
    canvas.circle(cx, cy, r_mid, fill=0, stroke=1)
    canvas.circle(cx, cy, r_in, fill=0, stroke=1)

    canvas.saveState()
    canvas.setStrokeAlpha(0.75)
    canvas.setFillAlpha(0.75)
    _element_band(canvas, element, cx, cy, r_mid, r_out, gold)
    canvas.restoreState()

    # The asterism sits behind the glyph, quiet enough not to compete with it.
    canvas.saveState()
    canvas.setStrokeAlpha(0.55)
    canvas.setFillAlpha(0.55)
    draw_constellation(canvas, code, cx, cy, size * 0.60, gold,
                       line_color=pale, star_scale=0.75)
    canvas.restoreState()

    draw_sign(canvas, code, cx, cy, size * 0.30, ink, weight=weight)

    # Four cardinal dots pin the roundel to the page.
    canvas.setFillColor(gold)
    for ang in (0.0, 90.0, 180.0, 270.0):
        px, py = polar(cx, cy, r_out, ang)
        canvas.circle(px, py, max(0.8, size * 0.009), fill=1, stroke=0)

    canvas.restoreState()
    return True
