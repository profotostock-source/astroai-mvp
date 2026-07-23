import unittest

from services.human_model import build_human_model


class HumanModelTests(unittest.TestCase):
    def setUp(self):
        self.chart = {
            "sun_sign": "Aqu",
            "moon_sign": "Tau",
            "ascendant_sign": "Lib",
            "birth_time_known": True,
            "planets": {
                "mercury": {"sign": "Pis"},
                "venus": {"sign": "Cap"},
                "mars": {"sign": "Pis"},
                "saturn": {"sign": "Tau"},
                "uranus": {"sign": "Aqu"},
            },
        }

    def test_model_contains_traceable_dimensions(self):
        model = build_human_model(self.chart)
        self.assertEqual(model["model_version"], "1.0")
        self.assertTrue(model["dimensions"])
        self.assertTrue(all(item["evidence"] for item in model["dimensions"]))

    def test_expected_top_themes_exist(self):
        model = build_human_model(self.chart)
        top_ids = {item["id"] for item in model["strongest_dimensions"]}
        self.assertIn("stability", top_ids)
        self.assertIn("independent_thinking", top_ids)

    def test_birth_time_unknown_excludes_ascendant(self):
        chart = dict(self.chart)
        chart["birth_time_known"] = False
        model = build_human_model(chart)
        serialized = str(model)
        self.assertNotIn("Асцендент у знаку", serialized)


if __name__ == "__main__":
    unittest.main()
