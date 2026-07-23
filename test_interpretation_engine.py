import json
import unittest

from services.ai_interpretation import _format_astrology_data_for_gpt
from services.interpretation_engine import build_interpretation_context, build_personality_core


class InterpretationEngineTests(unittest.TestCase):
    def setUp(self):
        self.chart = {
            "name": "Test",
            "birth_time_known": True,
            "sun_sign": "Aquarius",
            "moon_sign": "Taurus",
            "ascendant_sign": "Libra",
            "planets": {
                "sun": {"sign": "Aquarius", "degree": 3.0, "retrograde": False},
                "moon": {"sign": "Taurus", "degree": 8.0, "retrograde": False},
                "venus": {"sign": "Capricorn", "degree": 12.0, "retrograde": False},
            },
            "houses": [{"house": 1, "sign": "Libra", "degree": 10.0}],
            "aspects": [{"planet1": "Sun", "planet2": "Moon", "aspect": "Square", "orb": 2.1}],
            "warnings": [],
        }

    def test_builds_traceable_core(self):
        result = build_personality_core(self.chart)
        factor_ids = {factor["id"] for factor in result["factors"]}
        self.assertIn("sun_sign", factor_ids)
        self.assertIn("ascendant_sign", factor_ids)
        self.assertIn("ascendant_ruler_sign", factor_ids)
        self.assertTrue(result["dominant_patterns"])
        self.assertTrue(all(item["evidence_ids"] for item in result["dominant_patterns"]))

    def test_unknown_birth_time_excludes_time_dependent_factors(self):
        chart = dict(self.chart, birth_time_known=False)
        context = build_interpretation_context(chart)
        factor_ids = {factor["id"] for factor in context["personality_core"]["factors"]}
        self.assertNotIn("ascendant_sign", factor_ids)
        self.assertNotIn("ascendant_ruler_sign", factor_ids)
        self.assertEqual(context["evidence_catalog"]["houses"], [])

    def test_formatter_returns_json_context(self):
        payload = json.loads(_format_astrology_data_for_gpt(self.chart))
        self.assertEqual(payload["schema_version"], "1.0.0")
        self.assertIn("facts", payload)
        self.assertIn("chart_summary", payload)

    def test_kerykeion_abbreviated_signs_are_supported(self):
        chart = dict(self.chart, sun_sign="Aqu", moon_sign="Tau", ascendant_sign="Lib")
        result = build_personality_core(chart)
        signs = {factor["sign"] for factor in result["factors"]}
        self.assertIn("Aquarius", signs)
        self.assertIn("Taurus", signs)
        self.assertIn("Libra", signs)


if __name__ == "__main__":
    unittest.main()
