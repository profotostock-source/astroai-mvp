"""Natal chart wheel drawn as a ReportLab Flowable.

This is the one graphic in the report that is genuinely unique to the reader:
every planet sits at its real longitude, and the aspect lines in the middle are
computed from those longitudes rather than decorated in.

The wheel is deliberately quiet — hairlines, one accent colour, no fills — so
it reads as an editorial diagram rather than an occult sigil.

Usage:
    story.append(ChartWheel(astrology_data, size=118 * mm, font=fn))
"""

from __future__ import annotations

import logging
import math

from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.platypus import Flowable

from .glyphs import SIGN_ELEMENT, SIGN_ORDER, draw_planet, draw_sign

LOGGER = logging.getLogger(__name__)

# Planets in drawing order; only these are placed on the wheel.
WHEEL_PLANETS = [
    "sun", "moon", "mercury", "venus", "mars",
    "jupiter", "saturn", "uranus", "neptune", "pluto",
]

# name -> (exact angle, orb). Tight orbs keep the centre readable.
ASPECTS = {
    "conjunction": (0.0, 7.0),
    "opposition": (180.0, 7.0),
    "trine": (120.0, 6.0),
    "square": (90.0, 6.0),
    "sextile": (60.0, 4.0),
}

# Harmonious aspects get the warm accent, tense ones the cool grey-violet.
ASPECT_STYLE = {
    "conjunction": ("#C9A76B", 0.55, None),
    "trine": ("#C9A76B", 0.5, None),
    "sextile": ("#C9A76B", 0.4, (1.4, 1.6)),
    "square": ("#8E7FA6", 0.5, None),
    "opposition": ("#8E7FA6", 0.55, None),
}

ELEMENT_TINT = {
    "fire": HexColor("#E8CDB4"),
    "earth": HexColor("#CFD3BD"),
    "air": HexColor("#D8D2E4"),
    "water": HexColor("#C6D6DD"),
}

RING_LINE = HexColor("#D9C4A8")
HAIRLINE = HexColor("#E3D6C3")
GOLD = HexColor("#C9A76B")
INK = HexColor("#3A2E20")
MUTED = HexColor("#9A8C7A")


def _polar(cx, cy, r, deg):
    a = math.radians(deg)
    return (cx + r * math.cos(a), cy + r * math.sin(a))


def absolute_longitude(sign: str, degree: float) -> float | None:
    """Convert a (sign, degree-in-sign) pair to 0..360 ecliptic longitude."""
    if sign not in SIGN_ORDER:
        return None
    try:
        deg = float(degree or 0.0)
    except (TypeError, ValueError):
        deg = 0.0
    return SIGN_ORDER.index(sign) * 30.0 + max(0.0, min(29.999, deg))


def collect_positions(astrology_data: dict) -> list[dict]:
    """Pull planets out of astrology_data into a flat, wheel-ready list."""
    planets = astrology_data.get("planets") or {}
    if not isinstance(planets, dict):
        # Defensive: the rest of the codebase also accepts a list of dicts.
        planets = {
            str(p.get("name", "")).lower(): p
            for p in planets if isinstance(p, dict)
        }

    out = []
    for key in WHEEL_PLANETS:
        data = planets.get(key)
        if not isinstance(data, dict):
            continue
        lon = absolute_longitude(data.get("sign", ""), data.get("degree", 0))
        if lon is None:
            continue
        out.append({
            "key": key,
            "sign": data.get("sign", ""),
            "degree": float(data.get("degree", 0) or 0),
            "lon": lon,
            "retrograde": bool(data.get("retrograde")),
        })
    return out


def find_aspects(positions: list[dict]) -> list[tuple[int, int, str]]:
    """Return (index_a, index_b, aspect_name) for every aspect within orb."""
    found = []
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            sep = abs(positions[i]["lon"] - positions[j]["lon"]) % 360.0
            if sep > 180.0:
                sep = 360.0 - sep
            for name, (exact, orb) in ASPECTS.items():
                if abs(sep - exact) <= orb:
                    found.append((i, j, name))
                    break
    return found


def _spread(angles: list[float], min_gap: float, passes: int = 60) -> list[float]:
    """Nudge label angles apart so glyphs stop overlapping.

    Simple relaxation: repeatedly push any pair closer than min_gap away from
    each other. Converges quickly for ten bodies and never moves a planet far
    enough to misrepresent its sign.
    """
    out = list(angles)
    n = len(out)
    if n < 2:
        return out
    for _ in range(passes):
        moved = False
        order = sorted(range(n), key=lambda i: out[i])
        for k in range(n):
            a = order[k]
            b = order[(k + 1) % n]
            gap = (out[b] - out[a]) % 360.0
            if 0 < gap < min_gap:
                push = (min_gap - gap) / 2.0
                out[a] -= push
                out[b] += push
                moved = True
        if not moved:
            break
    return [a % 360.0 for a in out]


class ChartWheel(Flowable):
    """The natal wheel. Width is fixed to `size`; height matches."""

    def __init__(self, astrology_data: dict, size: float = 118 * mm,
                 font: str = "Helvetica"):
        super().__init__()
        self.size = size
        self.width = size
        self.height = size
        self.hAlign = "CENTER"
        self.font = font
        self.positions = collect_positions(astrology_data)
        self.aspects = find_aspects(self.positions)
        asc = astrology_data.get("ascendant_sign")
        self.asc_sign = asc if asc in SIGN_ORDER else None
        # Ascendant to the left, as in a conventional chart. Without a birth
        # time there is no ascendant, so 0° Aries takes that place instead.
        asc_lon = SIGN_ORDER.index(self.asc_sign) * 30.0 if self.asc_sign else 0.0
        self._rotation = 180.0 - asc_lon

    def _screen(self, lon: float) -> float:
        return (lon + self._rotation) % 360.0

    def draw(self):
        c = self.canv
        s = self.size
        cx = cy = s / 2.0

        r_out = s * 0.480     # outer rim
        r_sign = s * 0.410    # inner edge of the sign band
        r_tick = s * 0.385    # degree ticks live just inside it
        r_planet = s * 0.320  # planet glyph ring
        r_aspect = s * 0.250  # aspect web radius

        c.saveState()
        c.setLineCap(1)

        # --- element tints behind the sign band -----------------------------
        for i, code in enumerate(SIGN_ORDER):
            start = self._screen(i * 30.0)
            c.setFillColor(ELEMENT_TINT.get(SIGN_ELEMENT.get(code, ""), HAIRLINE))
            path = c.beginPath()
            path.moveTo(*_polar(cx, cy, r_sign, start))
            steps = 10
            for k in range(steps + 1):
                path.lineTo(*_polar(cx, cy, r_out, start + 30.0 * k / steps))
            for k in range(steps + 1):
                path.lineTo(*_polar(cx, cy, r_sign, start + 30.0 * (steps - k) / steps))
            path.close()
            c.drawPath(path, fill=1, stroke=0)

        # --- rings ----------------------------------------------------------
        c.setStrokeColor(RING_LINE)
        c.setLineWidth(0.7)
        c.circle(cx, cy, r_out, fill=0, stroke=1)
        c.circle(cx, cy, r_sign, fill=0, stroke=1)
        c.setStrokeColor(HAIRLINE)
        c.setLineWidth(0.4)
        c.circle(cx, cy, r_planet + s * 0.045, fill=0, stroke=1)
        c.circle(cx, cy, r_aspect, fill=0, stroke=1)

        # --- sector dividers and degree ticks -------------------------------
        for i in range(12):
            ang = self._screen(i * 30.0)
            c.setStrokeColor(RING_LINE)
            c.setLineWidth(0.6)
            p1 = _polar(cx, cy, r_aspect, ang)
            p2 = _polar(cx, cy, r_out, ang)
            c.line(p1[0], p1[1], p2[0], p2[1])

        c.setStrokeColor(HAIRLINE)
        c.setLineWidth(0.35)
        for d in range(0, 360, 5):
            ang = self._screen(float(d))
            inner = r_tick if d % 30 == 0 else (r_tick + s * 0.012 if d % 10 else r_tick + s * 0.006)
            p1 = _polar(cx, cy, inner, ang)
            p2 = _polar(cx, cy, r_sign, ang)
            c.line(p1[0], p1[1], p2[0], p2[1])

        # --- sign glyphs ----------------------------------------------------
        glyph_r = (r_out + r_sign) / 2.0
        for i, code in enumerate(SIGN_ORDER):
            ang = self._screen(i * 30.0 + 15.0)
            gx, gy = _polar(cx, cy, glyph_r, ang)
            draw_sign(c, code, gx, gy, s * 0.052, INK, weight=1.2)

        # --- aspect web -----------------------------------------------------
        for i, j, name in self.aspects:
            hexcolor, alpha, dash = ASPECT_STYLE.get(name, ("#B9AC98", 0.4, None))
            c.saveState()
            c.setStrokeColor(HexColor(hexcolor))
            c.setStrokeAlpha(alpha)
            c.setLineWidth(0.55 if name in ("conjunction", "opposition") else 0.45)
            if dash:
                c.setDash(dash[0], dash[1])
            a = _polar(cx, cy, r_aspect, self._screen(self.positions[i]["lon"]))
            b = _polar(cx, cy, r_aspect, self._screen(self.positions[j]["lon"]))
            c.line(a[0], a[1], b[0], b[1])
            c.restoreState()

        # --- planets --------------------------------------------------------
        raw = [self._screen(p["lon"]) for p in self.positions]
        placed = _spread(raw, min_gap=360.0 * (s * 0.052) / (2 * math.pi * r_planet) * 1.15)

        for idx, p in enumerate(self.positions):
            true_ang = raw[idx]
            lab_ang = placed[idx]

            # leader line from the true degree out to the shifted glyph
            c.setStrokeColor(MUTED)
            c.setStrokeAlpha(0.55)
            c.setLineWidth(0.35)
            t1 = _polar(cx, cy, r_tick, true_ang)
            t2 = _polar(cx, cy, r_planet + s * 0.045, lab_ang)
            c.line(t1[0], t1[1], t2[0], t2[1])
            c.setStrokeAlpha(1)

            gx, gy = _polar(cx, cy, r_planet, lab_ang)
            if not draw_planet(c, p["key"], gx, gy, s * 0.050, INK, weight=1.2):
                continue

            # degree label, tucked just inside the glyph
            lx, ly = _polar(cx, cy, r_planet - s * 0.048, lab_ang)
            label = f"{int(p['degree'])}°"
            if p["retrograde"]:
                label += " R"
            c.setFont(self.font, s * 0.026)
            c.setFillColor(MUTED)
            c.drawCentredString(lx, ly - s * 0.009, label)

        # --- ascendant marker ------------------------------------------------
        if self.asc_sign:
            c.setStrokeColor(GOLD)
            c.setLineWidth(1.1)
            a1 = _polar(cx, cy, r_aspect, 180.0)
            a2 = _polar(cx, cy, r_out + s * 0.020, 180.0)
            c.line(a1[0], a1[1], a2[0], a2[1])
            c.setFont(self.font, s * 0.028)
            c.setFillColor(GOLD)
            c.drawRightString(a2[0] + s * 0.030, a2[1] + s * 0.014, "ASC")

        c.restoreState()
