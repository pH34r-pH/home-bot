# SPDX-License-Identifier: Apache-2.0
"""Check alignment and receipt identity before reporting pose discrepancies."""

import hashlib
import json
import math
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from compare_pilots import comparison, verified_attempt


def rows(x, heading, *, sim_time=1.0):
    return [{"sim_time_s": sim_time, "truth_position_m": [x, 0, 0], "truth_yaw_rad": heading}]


class PilotComparisonTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.reference = {
            "attempt_id": "32fb03a7-bb25-431e-9894-5b563307d3a5",
            "runtime": {"webots_version": "R2025a", "platform": "reference"},
            "requested_actions_sha256": "a" * 64,
            "applied_controls_sha256": "b" * 64,
            "replay": {"evaluation": {"task_achieved": True}},
        }
        self.candidate = {
            **self.reference,
            "attempt_id": "ef5c713b-0710-45f8-af9d-b8103cdb635d",
            "runtime": {"webots_version": "R2025a", "platform": "candidate"},
            "replay": {"evaluation": {"task_achieved": False}},
        }

    def test_matching_controls_and_steps_report_observed_deltas_and_preserve_outcomes(self):
        result = comparison(
            (self.reference, rows(0, math.pi - .01)),
            (self.candidate, rows(.25, -math.pi + .01)),
        )
        self.assertEqual(result["scope"], "simulation_only")
        self.assertEqual(result["physical_qualification"], "pending")
        self.assertEqual(result["runtime_differences"], ["platform"])
        self.assertTrue(all(result["alignment"].values()))
        self.assertEqual(result["pose_discrepancy"]["max_position_delta_m"], .25)
        self.assertAlmostEqual(result["pose_discrepancy"]["max_heading_delta_rad"], .02)
        self.assertTrue(result["reference"]["replay"]["evaluation"]["task_achieved"])
        self.assertFalse(result["candidate"]["replay"]["evaluation"]["task_achieved"])

    def test_each_observed_alignment_mismatch_withholds_pose_comparison(self):
        variants = [
            ("requested_actions_match", {**self.candidate, "requested_actions_sha256": "c" * 64}, rows(1, 0)),
            ("applied_controls_match", {**self.candidate, "applied_controls_sha256": "c" * 64}, rows(1, 0)),
            ("evaluator_steps_match", self.candidate, rows(1, 0, sim_time=2.0)),
        ]
        for key, candidate, samples in variants:
            with self.subTest(key=key):
                result = comparison((self.reference, rows(0, 0)), (candidate, samples))
                self.assertFalse(result["alignment"][key])
                self.assertIsNone(result["pose_discrepancy"])
                self.assertEqual(result["candidate"]["replay"], self.candidate["replay"])

    def test_comparison_requires_two_distinct_attempts(self):
        attempt = (self.reference, rows(0, 0))
        with self.assertRaisesRegex(ValueError, "distinct attempts"):
            comparison(attempt, attempt)

    def test_receipt_pin_is_checked_before_replay(self):
        path = self.root / "pilot-receipt.json"
        path.write_bytes(b'{"arbitrary":"receipt"}')
        with patch("compare_pilots.verify_bundle") as replay:
            with self.assertRaisesRegex(ValueError, "expected SHA-256"):
                verified_attempt(self.root, "0" * 64)
        replay.assert_not_called()

    def test_requested_and_applied_controls_are_bound_separately_from_wall_times(self):
        receipt_file = self.root / "pilot-receipt.json"
        receipt_file.write_text(json.dumps({
            "attempt_id": self.reference["attempt_id"],
            "source_commit": "1" * 40, "source_dirty": False, "inputs_sha256": {},
            "outputs_sha256": {}, "world": {"basicTimeStep": 16, "randomSeed": 7},
            "runtime": self.reference["runtime"],
        }), encoding="utf-8")
        pin = hashlib.sha256(receipt_file.read_bytes()).hexdigest()
        pilot, evaluator = self.root / "pilot", self.root / "evaluator"
        pilot.mkdir()
        evaluator.mkdir()
        action = {"event": "action_start", "action": "drive", "duration_wall_s": 1, "command": {},
                  "wall_time_utc": "first"}
        tick = {"step": 1, "wall_time_s": 1.0,
                "observation": {"applied_command": {"linear_mps": 0}, "watchdog_expired": True}}
        (evaluator / "evaluation.jsonl").write_text(json.dumps(rows(0, 0)[0]), encoding="utf-8")

        def record():
            (pilot / "pilot.jsonl").write_text(json.dumps(action), encoding="utf-8")
            (evaluator / "pilot-motion.jsonl").write_text(json.dumps(tick), encoding="utf-8")
            return verified_attempt(self.root, pin)[0]

        with patch("compare_pilots.verify_bundle", return_value=self.reference["replay"]):
            initial = record()
            action["wall_time_utc"], tick["wall_time_s"] = "later", 3.0
            self.assertEqual(record(), initial)
            tick["observation"]["watchdog_expired"] = False
            changed = record()
        self.assertEqual(changed["requested_actions_sha256"], initial["requested_actions_sha256"])
        self.assertNotEqual(changed["applied_controls_sha256"], initial["applied_controls_sha256"])
