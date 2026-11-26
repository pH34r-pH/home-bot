# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from home_bot.config import RobotConfig
from home_bot.control import Command
from home_bot.smoke_trace import replay_motion


class SmokeTraceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "trace.jsonl"
        moving = Command(linear_mps=0.102, ttl_ms=50)
        stopped = replace(moving, linear_mps=0.0)
        self.rows = [
            {
                "step": 1, "wall_time_s": 100.0, "accepted_command": asdict(moving),
                "observation": {
                    "sim_time_s": 0.016, "applied_command": asdict(moving), "watchdog_expired": False,
                    "applied_wheel_rad_s": [3, 3], "wheels_rad": [0, 0],
                    "odometry": {"x_m": 0, "y_m": 0, "yaw_rad": 0},
                },
            },
            {
                "step": 2, "wall_time_s": 100.06, "accepted_command": None,
                "observation": {
                    "sim_time_s": 0.032, "applied_command": asdict(stopped), "watchdog_expired": True,
                    "applied_wheel_rad_s": [0, 0], "wheels_rad": [1, 1],
                    "odometry": {"x_m": 0.034, "y_m": 0, "yaw_rad": 0},
                },
            },
        ]

    def replay(self, rows):
        self.path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return replay_motion(self.path, RobotConfig(), step_ms=16)

    def test_replays_wall_clock_expiry_and_odometry(self):
        self.assertEqual(self.replay(self.rows), {
            "steps": 2, "final_sim_time_s": 0.032, "watchdog_expired_steps": 1,
        })

    def test_rejects_corrupt_control_evidence(self):
        for field, value, reason in (
            ("watchdog_expired", False, "watchdog mismatch"),
            ("applied_wheel_rad_s", [3, 3], "wheel target mismatch"),
            ("odometry", {"x_m": 0, "y_m": 0, "yaw_rad": 0}, "wheel odometry mismatch"),
        ):
            rows = deepcopy(self.rows)
            rows[1]["observation"][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, f"step 2: .*{reason}"):
                self.replay(rows)

    def test_rejects_gap_or_missing_trace(self):
        rows = deepcopy(self.rows)
        rows[1]["step"] = 3
        with self.assertRaisesRegex(ValueError, "step 2: invalid step or clock sequence"):
            self.replay(rows)
        with self.assertRaisesRegex(ValueError, "trace is empty"):
            self.replay([])
