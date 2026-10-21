# SPDX-License-Identifier: Apache-2.0
"""Check the pilot CLI's stop behavior independently of Webots."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("robot_cli", Path(__file__).resolve().parents[1] / "scripts/robot.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class RobotCliTests(unittest.TestCase):
    def test_failed_drive_attempt_still_sends_stop_and_preserves_head(self):
        commands = []
        state = {"applied_command": {"pan_rad": 1.2, "tilt_rad": .1, "expression": "curious", "text": "LOOK"}}

        def request(path, data=None):
            if data is None:
                return state
            commands.append(dict(data))
            if len(commands) == 1:
                raise OSError("simulated connection failure")
            return {"accepted": data}

        with patch.object(cli, "request", side_effect=request), patch.object(cli, "record"), \
                patch.object(cli.time, "monotonic", return_value=0), \
                patch("sys.argv", ["robot.py", "drive", "--linear", ".04", "--seconds", "1"]):
            with self.assertRaises(OSError):
                cli.main()
        self.assertEqual(commands[0]["linear_mps"], .04)
        self.assertEqual(commands[-1]["linear_mps"], 0)
        self.assertEqual(commands[-1]["angular_rps"], 0)
        self.assertEqual(commands[-1]["pan_rad"], 1.2)
        self.assertEqual(commands[-1]["text"], "LOOK")

    def test_drive_limit_rejection_does_not_post_motion(self):
        with patch.object(cli, "request", return_value={"applied_command": {}}) as request, \
                patch("sys.argv", ["robot.py", "drive", "--linear", ".2", "--seconds", "1"]), \
                patch("sys.stderr"):
            with self.assertRaises(SystemExit) as error:
                cli.main()
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args, ("/api/state",))


if __name__ == "__main__":
    unittest.main()
