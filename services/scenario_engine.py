"""Generate traceable life-scenario hypotheses from the symbolic Human Model.

A scenario is not a prediction or a biographical claim. It is a cautious,
behavior-level hypothesis supported by multiple chart-derived dimensions.
"""

from __future__ import annotations

from typing import Any

from services.human_model import build_human_model


SCENARIO_RULES: tuple[dict[str, Any], ...] = (
    {
        "id": "change_without_losing_ground",
        "title": "Зміни без втрати опори",
        "requires": (("innovation", 65), ("stability", 65)),
        "theme": "потяг до нового співіснує з потребою зберігати надійний фундамент",
        "triggers": [
            "велика зміна роботи, проєкту або звичного способу життя",
            "можливість, яка захоплює ідеєю, але порушує усталений порядок",
        ],
        "sequence": [
            "спочатку з'являється інтерес до нової можливості",
            "потім увага переходить до ризиків і того, що доведеться втратити або перебудувати",
            "рішення дозріває легше, коли є чіткий план переходу, а не стрибок у невідоме",
        ],
        "resource": "здатність оновлювати життя без бездумного руйнування того, що вже працює",
        "watch_for": "не плутати обережну підготовку з нескінченним відкладанням",
    },
    {
        "id": "harmony_vs_own_position",
        "title": "Гармонія чи власна позиція",
        "requires": (("diplomacy", 65), ("independent_thinking", 65)),
        "theme": "власне бачення потрібно поєднати з бажанням не загострювати взаємодію",
        "triggers": [
            "розмова, у якій ваша думка відрізняється від очікувань інших",
            "ситуація, де компроміс може коштувати вам важливої потреби",
        ],
        "sequence": [
            "ви швидко бачите кілька точок зору і намагаєтеся знайти прийнятну форму розмови",
            "через це власна позиція іноді звучить м'якше або пізніше, ніж була сформована всередині",
            "напруга зменшується, коли ви відокремлюєте повагу до іншого від відмови від себе",
        ],
        "resource": "уміння висловлювати нестандартні ідеї так, щоб інші могли їх почути",
        "watch_for": "не підтримувати зовнішній спокій ціною внутрішнього невдоволення",
    },
    {
        "id": "sensitivity_needs_structure",
        "title": "Чутливість потребує структури",
        "requires": (("sensitivity", 62), ("structure", 62)),
        "theme": "висока сприйнятливість краще працює, коли має зрозумілі межі та ритм",
        "triggers": [
            "перевантажене середовище, багато чужих емоцій або суперечливих сигналів",
            "робота без ясних пріоритетів і завершених етапів",
        ],
        "sequence": [
            "ви помічаєте більше нюансів, ніж встигаєте одразу впорядкувати",
            "за відсутності меж це може давати втому або розпорошення",
            "повернення до простого плану, тиші й одного наступного кроку допомагає відновити ясність",
        ],
        "resource": "поєднання тонкого сприйняття з умінням надавати ідеям практичної форми",
        "watch_for": "не вимагати від себе однакової продуктивності незалежно від рівня перевантаження",
    },
    {
        "id": "slow_commitment_strong_followthrough",
        "title": "Повільне рішення, сильна послідовність",
        "requires": (("persistence", 68), ("stability", 65)),
        "theme": "до серйозного рішення потрібен час, але після вибору зростає витривалість",
        "triggers": [
            "довгострокове зобов'язання або рішення з незворотними наслідками",
            "проєкт, де результат не з'являється одразу",
        ],
        "sequence": [
            "на старті ви перевіряєте, чи варта справа вкладених сил",
            "зовні це може виглядати як повільність або вагання",
            "після внутрішнього рішення вам легше тримати курс довше, ніж багатьом іншим",
        ],
        "resource": "надійність і здатність доводити важливе до результату",
        "watch_for": "не залишатися в обраному лише тому, що вже було багато вкладено",
    },
    {
        "id": "ideas_need_translation",
        "title": "Ідеї потребують перекладу в конкретику",
        "requires": (("imagination", 62), ("practicality", 62)),
        "theme": "образне бачення стає сильним ресурсом, коли перетворюється на зрозумілі кроки",
        "triggers": [
            "нова ідея, яку легко відчути цілісно, але складно швидко пояснити",
            "необхідність перевести інтуїтивне розуміння у план або домовленість",
        ],
        "sequence": [
            "спочатку ви можете бачити загальний образ або відчувати правильний напрям",
            "деталі формулюються поступово, інколи вже в процесі дії чи розмови",
            "якість рішення зростає, коли є час записати думку, розкласти її на частини й перевірити практикою",
        ],
        "resource": "здатність поєднати нестандартне бачення з реальним втіленням",
        "watch_for": "не вважати ідею зрозумілою для інших до того, як вона отримала чітку форму",
    },
)


def _dimension_map(human_model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in human_model.get("dimensions", [])}


def _build_scenario(rule: dict[str, Any], dimensions: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    matched = []
    for dimension_id, minimum in rule["requires"]:
        dimension = dimensions.get(dimension_id)
        if not dimension or dimension.get("score", 0) < minimum:
            return None
        matched.append(dimension)

    confidence = min(0.95, round(sum(item["score"] for item in matched) / (100 * len(matched)), 2))
    evidence = []
    for item in matched:
        evidence.extend(item.get("evidence", []))

    return {
        "id": rule["id"],
        "title": rule["title"],
        "confidence": confidence,
        "theme": rule["theme"],
        "typical_triggers": rule["triggers"],
        "possible_sequence": rule["sequence"],
        "resource": rule["resource"],
        "watch_for": rule["watch_for"],
        "supporting_dimensions": [item["label"] for item in matched],
        "evidence": list(dict.fromkeys(evidence)),
    }


def build_scenario_context(chart: dict[str, Any], human_model: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the strongest supported behavioral scenarios for report writing."""
    model = human_model or build_human_model(chart)
    dimensions = _dimension_map(model)
    scenarios = []
    for rule in SCENARIO_RULES:
        scenario = _build_scenario(rule, dimensions)
        if scenario:
            scenarios.append(scenario)

    scenarios.sort(key=lambda item: item["confidence"], reverse=True)
    return {
        "engine_version": "1.0",
        "method_note": (
            "Behavioral hypotheses derived from multiple symbolic dimensions; "
            "they are not predictions or established facts about the person's life."
        ),
        "scenarios": scenarios[:4],
        "writing_contract": {
            "use_as_cautious_examples_not_biography": True,
            "do_not_claim_trigger_has_happened": True,
            "prefer_concrete_behavior_over_trait_labels": True,
            "every_scenario_requires_multiple_supported_dimensions": True,
        },
    }
