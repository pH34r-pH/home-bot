# SPDX-License-Identifier: Apache-2.0
"""Verify pilot acceptance from synthetic evaluator observations."""

import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from home_bot.pilot_trace import PilotEvaluation, replay_evaluation


def sample(t, *, sensor_time=None, contacts=None):
    return {"sim_time_s": t, "truth_position_m": [1.1, 0, .03], "truth_yaw_rad": 0,
            "truth_velocity": [0] * 6, "truth_up_axis": 1,
            "above_floor_contact_events": contacts or [],
            "sensor_state": {"sim_time_s": t if sensor_time is None else sensor_time,
                             "gimbal_rad": [math.pi, 0], "applied_command": {"text": "FOUND"}}}


class PilotTraceTests(unittest.TestCase):
    def test_mission_requires_a_full_dwell_and_contact_invalidates_success(self):
        evaluator = PilotEvaluation(16)
        results = [evaluator.observe(sample(t))["task_achieved"] for t in (.256, .512, .768, 1.024, 1.280)]
        self.assertEqual(results, [False, False, False, False, True])
        contact = {"sim_time_s": 1.4, "points": [[0, 0, .02]]}
        self.assertFalse(evaluator.observe(sample(1.536, contacts=[contact]))["task_achieved"])

    def test_stale_data_or_sample_gap_resets_dwell(self):
        evaluator = PilotEvaluation(16)
        for t in (.256, .512, .768):
            self.assertFalse(evaluator.observe(sample(t))["task_achieved"])
        stale = evaluator.observe(sample(1.024, sensor_time=.768))
        self.assertFalse(stale["criteria"]["fresh_sensor_state"])
        for t in (1.280, 1.536, 2.304, 2.560, 2.816, 3.072):
            self.assertFalse(evaluator.observe(sample(t))["task_achieved"])

    def test_replay_does_not_trust_self_report(self):
        evaluator = PilotEvaluation(16)
        rows = []
        for t in (.256, .512, .768, 1.024, 1.280):
            row = sample(t)
            row.update(evaluator.observe(row))
            rows.append(row)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evaluation.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            self.assertTrue(replay_evaluation(path, 16)["task_achieved"])
            rows[-1]["criteria"]["near_target"] = False
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "predicate differs"):
                replay_evaluation(path, 16)
