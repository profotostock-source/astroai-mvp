"""Minimal hardcoded evidence base for MVP1.

Only the first validation chart is covered deliberately. New signs are added only
after real-user feedback confirms the report format works.
"""

RULES = {
    ("Sun", "Aquarius"): [
        {
            "id": "need_for_independence",
            "title": "Потреба у самостійності",
            "category": "identity",
            "confidence": 0.91,
            "statement": "Вам важливо зберігати свободу вибору та самостійно визначати свій напрямок.",
            "rule_id": "sun_aquarius_independence",
            "weight": 0.91,
            "priority": 1,
        },
        {
            "id": "independent_thinking",
            "title": "Незалежність мислення",
            "category": "thinking",
            "confidence": 0.84,
            "statement": "Ви схильні перевіряти усталені погляди й формувати власну позицію, а не автоматично погоджуватися з більшістю.",
            "rule_id": "sun_aquarius_independent_thinking",
            "weight": 0.84,
            "priority": 1,
        },
        {
            "id": "future_orientation",
            "title": "Орієнтація на нове",
            "category": "decision_making",
            "confidence": 0.76,
            "statement": "Вашу увагу можуть особливо привертати нові підходи, нестандартні рішення та можливості покращити звичний порядок.",
            "rule_id": "sun_aquarius_future_orientation",
            "weight": 0.76,
            "priority": 2,
        },
    ],
    ("Moon", "Taurus"): [
        {
            "id": "need_for_stability",
            "title": "Потреба у стабільності",
            "category": "emotional_needs",
            "confidence": 0.89,
            "statement": "Емоційне відчуття безпеки посилюється, коли життя передбачуване, а зміни відбуваються без зайвого поспіху.",
            "rule_id": "moon_taurus_stability",
            "weight": 0.89,
            "priority": 1,
        },
        {
            "id": "sensory_recovery",
            "title": "Відновлення через прості відчутні речі",
            "category": "stress_response",
            "confidence": 0.78,
            "statement": "Під час напруги вам може допомагати повернення до простих тілесних і побутових опор: спокійного ритму, комфорту та зрозумілої рутини.",
            "rule_id": "moon_taurus_sensory_recovery",
            "weight": 0.78,
            "priority": 2,
        },
        {
            "id": "slow_emotional_decisions",
            "title": "Потреба не поспішати з емоційними рішеннями",
            "category": "decision_making",
            "confidence": 0.74,
            "statement": "У питаннях, що зачіпають безпеку й близькі стосунки, вам може бути важливо мати час, щоб внутрішньо дозріти до рішення.",
            "rule_id": "moon_taurus_slow_decisions",
            "weight": 0.74,
            "priority": 2,
        },
    ],
    ("Ascendant", "Libra"): [
        {
            "id": "diplomatic_self_presentation",
            "title": "Дипломатична подача себе",
            "category": "communication",
            "confidence": 0.84,
            "statement": "У контакті з людьми вам природно шукати коректний тон, рівновагу та взаємну повагу.",
            "rule_id": "asc_libra_diplomacy",
            "weight": 0.84,
            "priority": 1,
        },
        {
            "id": "relationship_balance",
            "title": "Потреба у взаємності",
            "category": "relationships",
            "confidence": 0.80,
            "statement": "У взаєминах вам може бути особливо важливо відчувати взаємність, справедливість і готовність обох сторін враховувати одна одну.",
            "rule_id": "asc_libra_relationship_balance",
            "weight": 0.80,
            "priority": 1,
        },
        {
            "id": "conflict_delay",
            "title": "Схильність відкладати пряме зіткнення",
            "category": "stress_response",
            "confidence": 0.66,
            "statement": "Коли незгода загрожує порушити рівновагу, ви можете спершу пом'якшувати позицію або відкладати пряму розмову.",
            "rule_id": "asc_libra_conflict_delay",
            "weight": 0.66,
            "priority": 3,
        },
    ],
}
