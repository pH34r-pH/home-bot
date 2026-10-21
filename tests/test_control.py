# SPDX-License-Identifier: Apache-2.0
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from home_bot.config import RobotConfig
from home_bot.control import Command, CommandLatch, Odometry, wheel_speeds


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.config = RobotConfig()

    def test_invalid_motion_cannot_enter_control_loop(self):
        for value in (float("nan"), float("inf"), True, "fast", [], None, 0.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Command.parse({"version": 1, "linear_mps": value}, self.config)
        for data in ({}, [], {"version": True}, {"version": 1, "ttl_ms": -1},
                     {"version": 1, "pan_rad": 4}, {"version": 1, "expression": []},
                     {"version": 1, "text": "\n"}, {"version": 1, "extra": 1}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                Command.parse(data, self.config)

    def test_omitted_motion_stops_rather_than_reusing_old_velocity(self):
        command = Command.parse({"version": 1, "expression": "happy"}, self.config)
        self.assertEqual(wheel_speeds(command, self.config), (0.0, 0.0))

    def test_saturation_preserves_turn_curvature(self):
        command = Command(linear_mps=self.config.max_linear_mps, angular_rps=2)
        left, right = wheel_speeds(command, self.config)
        self.assertAlmostEqual(right, self.config.max_wheel_rad_s)
        v = (left + right) * self.config.wheel_radius_m / 2
        yaw = (right - left) * self.config.wheel_radius_m / self.config.track_width_m
        self.assertAlmostEqual(v / yaw, command.linear_mps / command.angular_rps)

    def test_watchdog_stops_in_fast_simulation(self):
        latch = CommandLatch()
        latch.accept(Command(linear_mps=0.1, pan_rad=1), 0, 100)
        self.assertFalse(latch.sample(0.2, 100.01)[1])
        command, expired = latch.sample(0.401, 100.02)
        self.assertTrue(expired)
        self.assertEqual(command.linear_mps, 0)
        self.assertEqual(command.pan_rad, 1)

    def test_watchdog_stops_after_pause_and_does_not_revive(self):
        latch = CommandLatch()
        latch.accept(Command(linear_mps=0.1, angular_rps=1), 0, 100)
        stopped, expired = latch.sample(0.1, 101)
        self.assertTrue(expired)
        self.assertEqual((stopped.linear_mps, stopped.angular_rps), (0, 0))
        self.assertEqual(latch.sample(0.1, 100.1)[0].linear_mps, 0)

    def test_a_queued_stale_command_does_not_start_motion(self):
        latch = CommandLatch()
        latch.accept(Command(linear_mps=0.1), 10, 100)
        self.assertEqual(latch.sample(10, 102)[0].linear_mps, 0)

    def test_odometry_straight_and_pure_rotation(self):
        estimate = Odometry()
        estimate.update(0, 0, self.config)
        estimate.update(1, 1, self.config)
        self.assertAlmostEqual(estimate.x_m, self.config.wheel_radius_m)
        estimate.update(0, 2, self.config)
        self.assertAlmostEqual(estimate.x_m, self.config.wheel_radius_m)
        self.assertAlmostEqual(estimate.y_m, 0)
        self.assertAlmostEqual(estimate.yaw_rad, 2 * self.config.wheel_radius_m / self.config.track_width_m)

    def test_odometry_exact_arc(self):
        estimate = Odometry()
        estimate.update(0, 0, self.config)
        right = math.pi * self.config.track_width_m / self.config.wheel_radius_m
        estimate.update(0, right, self.config)
        self.assertAlmostEqual(estimate.x_m, 0, places=8)
        self.assertAlmostEqual(estimate.y_m, self.config.track_width_m, places=8)


if __name__ == "__main__":
    unittest.main()
