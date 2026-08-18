"""Evidence-based visual and closing pages for Together PDF reports."""

from __future__ import annotations

from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, PageBreak, Paragraph, Spacer, Table, TableStyle

from .pdf_report import CONTENT_W, GOLD, GOLD_PALE, HAIRLINE, INK, MUTED, _Marker, _escape, _hr

THEME_LABELS = {
    "attraction": "Притягання",
    "emotional": "Емоції",
    "communication": "Спілкування",
    "love_style": "Прояви любові",
    "stability": "Стабільність",
    "growth": "Спільне зростання",
    "conflict": "Інтенсивність",
}
PLANET_UA = {
    "sun": "Сонце", "moon": "Місяць", "mercury": "Меркурій",
    "venus": "Венера", "mars": "Марс", "jupiter": "Юпітер",
    "saturn": "Сатурн", "uranus": "Уран", "neptune": "Нептун",
    "pluto": "Плутон", "ascendant": "Асцендент",
}
ASPECT_UA = {
    "conjunction": "сполучення", "opposition": "опозиція", "trine": "тригон",
    "square": "квадрат", "sextile": "секстиль",
}


def _theme_metrics(context: dict) -> list[tuple[str, float, int]]:
    raw = []
    for key, label in THEME_LABELS.items():
        aspects = context.get("themes", {}).get(key, [])
        weight = sum(float(item.get("score", 0) or 0) for item in aspects)
        raw.append((label, weight, len(aspects)))
    peak = max((weight for _, weight, _ in raw), default=0) or 1
    return [(label, round(weight / peak * 100, 1), count) for label, weight, count in raw]


class ThemeBars(Flowable):
    def __init__(self, metrics, width=CONTENT_W, height=78 * mm, font_name="Helvetica"):
        super().__init__()
        self.metrics = metrics
        self.font_name = font_name
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        label_w = 37 * mm
        bar_w = self.width - label_w - 14 * mm
        row_h = self.height / max(1, len(self.metrics))
        for index, (label, value, count) in enumerate(self.metrics):
            y = self.height - (index + 0.72) * row_h
            c.setFont(self.font_name, 7.5)
            c.setFillColor(INK)
            c.drawString(0, y, label)
            x = label_w
            c.setFillColor(GOLD_PALE)
            c.roundRect(x, y - 1.2 * mm, bar_w, 3.2 * mm, 1.6 * mm, stroke=0, fill=1)
            c.setFillColor(GOLD)
            c.roundRect(x, y - 1.2 * mm, bar_w * value / 100, 3.2 * mm, 1.6 * mm, stroke=0, fill=1)
            c.setFillColor(MUTED)
            c.setFont(self.font_name, 6.5)
            c.drawRightString(self.width, y, f"{count} аспектів")


class AspectBalance(Flowable):
    def __init__(self, supportive, tense, neutral, width=CONTENT_W, height=25 * mm, font_name="Helvetica"):
        super().__init__()
        self.font_name = font_name
        self.values = [("Підтримка", supportive, GOLD), ("Напруга", tense, HexColor("#A66A5A")),
                       ("Нейтральні", neutral, HexColor("#C9BCA7"))]
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        total = sum(value for _, value, _ in self.values) or 1
        y = self.height - 8 * mm
        x = 0
        for _, value, color in self.values:
            segment = self.width * value / total
            c.setFillColor(color)
            c.rect(x, y, segment, 6 * mm, stroke=0, fill=1)
            x += segment
        x = 0
        for label, value, color in self.values:
            c.setFillColor(color)
            c.circle(x + 1.5 * mm, 2 * mm, 1.2 * mm, stroke=0, fill=1)
            c.setFillColor(INK)
            c.setFont(self.font_name, 7)
            c.drawString(x + 4 * mm, 0, f"{label}: {value}")
            x += self.width / 3


def _aspect_counts(context: dict) -> tuple[int, int, int]:
    aspects = context.get("strongest_aspects", [])
    supportive = sum(a.get("aspect") in {"trine", "sextile"} for a in aspects)
    tense = sum(a.get("aspect") in {"square", "opposition"} for a in aspects)
    neutral = max(0, len(aspects) - supportive - tense)
    return supportive, tense, neutral


def _aspect_rows(context: dict, styles) -> list[list]:
    rows = [[Paragraph("КОНТАКТ", styles["kicker"]), Paragraph("ТИП", styles["kicker"]),
             Paragraph("ТОЧНІСТЬ", styles["kicker"])]]
    for aspect in context.get("strongest_aspects", [])[:6]:
        left = PLANET_UA.get(aspect.get("planet_a"), aspect.get("planet_a", "—"))
        right = PLANET_UA.get(aspect.get("planet_b"), aspect.get("planet_b", "—"))
        kind = ASPECT_UA.get(aspect.get("aspect"), aspect.get("aspect", "—"))
        orb = aspect.get("orb", 0)
        rows.append([
            Paragraph(_escape(f"{left} А — {right} Б"), styles["caption"]),
            Paragraph(_escape(kind), styles["caption"]),
            Paragraph(_escape(f"орбіс {orb:.1f}°"), styles["caption"]),
        ])
    return rows


def build_visual_analysis(context: dict, styles, state) -> list:
    metrics = _theme_metrics(context)
    supportive, tense, neutral = _aspect_counts(context)
    table = Table(_aspect_rows(context, styles), colWidths=[78 * mm, 45 * mm, 34 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, HAIRLINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2 * mm),
    ]))
    return [
        PageBreak(), _Marker(state, section="Профіль взаємодії"),
        Paragraph("АНАЛІТИКА", styles["kicker"]),
        Paragraph("Профіль вашої взаємодії", styles["display"]),
        _hr(GOLD, "18%", 1.2, 5, 7),
        Paragraph(
            "Смуги показують не «оцінку сумісності», а відносну силу тем у знайдених аспектах. "
            "Довша смуга означає, що ця тема частіше й точніше активується між вашими картами.",
            styles["caption"],
        ),
        Spacer(1, 5 * mm), ThemeBars(metrics, font_name=styles["caption"].fontName), Spacer(1, 5 * mm),
        Paragraph("Баланс аспектів", styles["h2"]),
        Paragraph(
            "Гармонійні аспекти підтримують легкість; напружені створюють рух і потребують навички; "
            "сполучення підсилюють тему, але самі по собі не є позитивними чи негативними.",
            styles["caption"],
        ),
        Spacer(1, 3 * mm), AspectBalance(supportive, tense, neutral, font_name=styles["caption"].fontName),
        PageBreak(), _Marker(state, section="Ключові аспекти"),
        Paragraph("ДОКАЗОВА ОСНОВА", styles["kicker"]),
        Paragraph("Шість найсильніших контактів", styles["display"]),
        _hr(GOLD, "18%", 1.2, 5, 7),
        Paragraph(
            "Саме ці контакти мають найбільшу вагу в розрахунку: враховано тип планет, аспект і його точність.",
            styles["caption"],
        ),
        Spacer(1, 5 * mm), table,
    ]


def _top_theme_names(context: dict) -> list[str]:
    metrics = sorted(_theme_metrics(context), key=lambda item: item[1], reverse=True)
    return [label for label, value, count in metrics if count][:2] or ["емоційний контакт", "спілкування"]


def build_personal_final(context: dict, profile_a: dict, profile_b: dict, generated_at: str, styles, state) -> list:
    name_a = profile_a.get("name", "Перша людина")
    name_b = profile_b.get("name", "Друга людина")
    top = _top_theme_names(context)
    aspects = context.get("strongest_aspects", [])
    tense = [a for a in aspects if a.get("aspect") in {"square", "opposition"}]
    tension_text = "У провідній двадцятці немає виразного напруженого аспекту."
    if tense:
        a = tense[0]
        tension_text = (
            f"Перша зона уваги — {PLANET_UA.get(a.get('planet_a'), a.get('planet_a'))} А та "
            f"{PLANET_UA.get(a.get('planet_b'), a.get('planet_b'))} Б: "
            f"{ASPECT_UA.get(a.get('aspect'), a.get('aspect'))}, орбіс {a.get('orb', 0):.1f}°."
        )
    return [
        PageBreak(), _Marker(state, section="Ваш план"),
        Paragraph("ПЕРСОНАЛЬНИЙ ПІДСУМОК", styles["kicker"]),
        Paragraph(f"Опори {name_a} та {name_b}", styles["display"]),
        _hr(GOLD, "18%", 1.2, 5, 8),
        Paragraph(
            f"Найсильніше у вашій карті проявлені теми «{top[0]}» та «{top[1]}». "
            "Це ті сфери, де взаємодія запускається найшвидше: саме тут ви найбільше впливаєте одне на одного. "
            "Використовуйте їх як ресурс під час складних періодів, а не лише коли між вами все легко.",
            styles["body"],
        ),
        Paragraph(tension_text + " Це не прогноз конфлікту, а конкретне місце, де варто повільніше реагувати й перевіряти наміри одне одного.", styles["body"]),
        Spacer(1, 6 * mm),
        Paragraph("План на найближчі 30 днів", styles["h1"]),
        _hr(GOLD, "18%", 0.8, 3, 5),
        Paragraph("Тиждень 1 — кожен називає три дії партнера, які справді дають відчуття турботи.", styles["item"], bulletText="01"),
        Paragraph("Тиждень 2 — одна година без телефонів для розмови не про побут, а про ваш поточний стан.", styles["item"], bulletText="02"),
        Paragraph("Тиждень 3 — обговоріть одну повторювану напругу за схемою: факт, почуття, прохання.", styles["item"], bulletText="03"),
        Paragraph("Тиждень 4 — зафіксуйте одну домовленість, яку обоє вважаєте реалістичною на наступний місяць.", styles["item"], bulletText="04"),
        Spacer(1, 7 * mm),
        Paragraph("Запитання для розмови", styles["h2"]),
        Paragraph("Що я роблю з любові, але ти не завжди розпізнаєш як любов?", styles["item"], bulletText="—"),
        Paragraph("У який момент ти найбільше відчуваєш, що ми команда?", styles["item"], bulletText="—"),
        Paragraph("Яку мою реакцію тобі найважче зрозуміти — і що ти тоді припускаєш?", styles["item"], bulletText="—"),
        Spacer(1, 7 * mm), _hr(HAIRLINE, "100%", 0.5, 0, 5),
        Paragraph(
            "Матеріал призначений для саморефлексії. Астрологічні символи тут є мовою для роздумів, "
            "а не психологічною діагностикою чи гарантією розвитку стосунків.",
            styles["legal"],
        ),
        Spacer(1, 3 * mm),
        Paragraph(f"Inner Compass Together · {name_a} + {name_b} · {generated_at}", styles["caption"]),
    ]
