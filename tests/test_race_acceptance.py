import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "race_acceptance",
    Path(__file__).resolve().parents[1] / "scripts/check-checkpoint-races.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RaceAcceptanceTests(unittest.TestCase):
    def test_clean_partial_leg_does_not_claim_course_completion(self):
        result = module.assess(
            "smoke=headless-physics status=pass finite=true wheels=4/4 travel=500m resets=0 cp=1/3",
            0,
        )
        self.assertTrue(result["initial_leg_clean"])
        self.assertFalse(result["full_course_clean"])

    def test_finished_race_with_route_escape_is_rejected(self):
        result = module.assess(
            "smoke=headless-physics status=pass finite=true wheels=4/4 travel=1400m resets=0 cp=2/2 outcome=finished p_rec=0r/1e",
            0,
        )
        self.assertFalse(result["initial_leg_clean"])
        self.assertFalse(result["full_course_clean"])

    def test_no_reset_or_reanchor_clean_finish_accepts_despite_disclosed_impacts(self):
        result = module.assess(
            "smoke=headless-physics status=pass finite=true wheels=4/4 travel=1400m resets=0 cp=2/2 outcome=finished impacts=12",
            0,
        )
        self.assertTrue(result["full_course_clean"])
        self.assertEqual(result["metrics"]["impacts"], "12")

    def test_real_actor_finish_counts_do_not_hide_player_recovery(self):
        result = module.assess(
            "smoke=headless-physics status=pass finite=true wheels=4/4 travel=2000m resets=0 cp=2/2 outcome=finished p_rec=0r/1e opps=0:sthlm_racer/2c/F/3e/1r/900w,1:sthlm_racer/1c/2e/60w",
            0,
        )
        self.assertEqual(result["native_actor_finish_count"], 1)
        self.assertEqual(result["native_actors"][0]["reanchors"], 1)
        self.assertFalse(result["full_course_clean"])

    def test_missing_native_completion_summary_fails_closed(self):
        self.assertFalse(module.assess("panic before load", 1)["initial_leg_clean"])
