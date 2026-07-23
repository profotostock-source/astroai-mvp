import unittest

from services.scenario_engine import build_scenario_context


class ScenarioEngineTests(unittest.TestCase):
    def test_builds_change_and_harmony_scenarios_for_reference_chart(self):
        chart = {
            "birth_time_known": True,
            "sun_sign": "Aqu",
            "moon_sign": "Tau",
            "ascendant_sign": "Lib",
            "planets": {
                "mercury": {"sign": "Pis"},
                "venus": {"sign": "Cap"},
                "mars": {"sign": "Pis"},
                "saturn": {"sign": "Tau"},
                "uranus": {"sign": "Aqu"},
            },
        }
        result = build_scenario_context(chart)
        ids = {scenario["id"] for scenario in result["scenarios"]}
        self.assertIn("change_without_losing_ground", ids)
        self.assertIn("harmony_vs_own_position", ids)
        self.assertTrue(all(len(item["evidence"]) >= 2 for item in result["scenarios"]))

    def test_does_not_create_scenario_without_both_dimensions(self):
        chart = {
            "birth_time_known": False,
            "sun_sign": "Aqu",
            "moon_sign": "Gem",
            "planets": {},
        }
        result = build_scenario_context(chart)
        ids = {scenario["id"] for scenario in result["scenarios"]}
        self.assertNotIn("change_without_losing_ground", ids)

    def test_scenarios_are_capped(self):
        chart = {
            "birth_time_known": True,
            "sun_sign": "Aqu",
            "moon_sign": "Tau",
            "ascendant_sign": "Lib",
            "planets": {
                "mercury": {"sign": "Pis"}, "venus": {"sign": "Cap"},
                "mars": {"sign": "Pis"}, "saturn": {"sign": "Tau"},
                "uranus": {"sign": "Aqu"},
            },
        }
        result = build_scenario_context(chart)
        self.assertLessEqual(len(result["scenarios"]), 4)


if __name__ == "__main__":
    unittest.main()
