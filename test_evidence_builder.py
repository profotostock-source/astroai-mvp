import unittest

from services.evidence_builder import build_report_context


class EvidenceBuilderTests(unittest.TestCase):
    def test_builds_expected_test_chart_facts(self):
        context = build_report_context({
            "name": "Олена",
            "sun_sign": "Aqu",
            "moon_sign": "Tau",
            "ascendant_sign": "Lib",
            "birth_time_known": True,
        })
        ids = {fact["id"] for fact in context["facts"]}
        self.assertIn("need_for_independence", ids)
        self.assertIn("need_for_stability", ids)
        self.assertIn("diplomatic_self_presentation", ids)
        self.assertEqual(context["schema_version"], "2.0.0")

    def test_ascendant_is_excluded_when_time_unknown(self):
        context = build_report_context({
            "sun_sign": "Aquarius",
            "moon_sign": "Taurus",
            "ascendant_sign": "Libra",
            "birth_time_known": False,
        })
        self.assertIsNone(context["chart_summary"]["ascendant_sign"])
        self.assertFalse(any(e["factor"] == "Ascendant" for f in context["facts"] for e in f["evidence"]))

    def test_output_is_limited_and_sorted(self):
        context = build_report_context({
            "sun_sign": "Aquarius",
            "moon_sign": "Taurus",
            "ascendant_sign": "Libra",
            "birth_time_known": True,
        })
        self.assertLessEqual(len(context["facts"]), 20)
        priorities = [f["writer_guidance"]["priority"] for f in context["facts"]]
        self.assertEqual(priorities, sorted(priorities))


if __name__ == "__main__":
    unittest.main()
