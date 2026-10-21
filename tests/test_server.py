# SPDX-License-Identifier: Apache-2.0
from dataclasses import replace
import base64
import json
from pathlib import Path
import socket
import sys
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from home_bot.config import RobotConfig
from home_bot.server import Mailbox, start_server


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Tests use an available ephemeral port; runtime uses the configured port.
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        cls.box = Mailbox()
        cls.server = start_server(cls.box, replace(RobotConfig(), http_port=port))
        cls.base = f"http://127.0.0.1:{port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.box.take()

    def post(self, command, origin=None):
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        return urlopen(Request(self.base + "/api/command", data=json.dumps(command).encode(), headers=headers), timeout=2)

    def test_command_is_queued_with_receipt_time(self):
        with self.post({"version": 1, "linear_mps": 0.1}) as response:
            self.assertEqual(response.status, 202)
        command, timestamp = self.box.take()
        self.assertEqual(command.linear_mps, 0.1)
        self.assertGreater(timestamp, 0)

    def test_invalid_command_does_not_refresh_watchdog(self):
        with self.assertRaises(HTTPError) as error:
            self.post({"version": 1, "pan_rad": 99})
        self.assertEqual(error.exception.code, 400)
        self.assertIsNone(self.box.take())

    def test_unrelated_browser_origin_cannot_drive(self):
        with self.assertRaises(HTTPError) as error:
            self.post({"version": 1}, "https://example.com")
        self.assertEqual(error.exception.code, 403)
        self.assertIsNone(self.box.take())

    def test_state_and_static_files(self):
        self.box.publish({"status": "running", "sim_time_s": 1})
        with urlopen(self.base + "/api/state", timeout=2) as response:
            self.assertEqual(json.load(response)["sim_time_s"], 1)
        with urlopen(self.base, timeout=2) as response:
            self.assertIn(b"Home Bot", response.read())
        with self.assertRaises(HTTPError):
            urlopen(self.base + "/../../config/robot.json", timeout=2)

    def test_observation_keeps_image_and_sample_state_together(self):
        self.box.publish({"sim_time_s": 1}, b"frame-one")
        self.box.publish({"sim_time_s": 2})
        with urlopen(self.base + "/api/observation", timeout=2) as response:
            observation = json.load(response)
        self.assertEqual(observation["state"]["sim_time_s"], 1)
        self.assertEqual(base64.b64decode(observation["camera_png_base64"]), b"frame-one")


if __name__ == "__main__":
    unittest.main()
