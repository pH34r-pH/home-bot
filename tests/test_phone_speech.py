# SPDX-License-Identifier: Apache-2.0
"""Capture scheduling guards; acoustic correctness still requires the device tests."""

import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("phone_speech", Path(__file__).resolve().parents[1] / "scripts/phone_speech.py")
speech = importlib.util.module_from_spec(spec)
spec.loader.exec_module(speech)


class AcousticWindowTests(unittest.TestCase):
    def test_long_clip_expands_capture_for_leading_and_trailing_audio(self):
        seconds = speech.acoustic_window(12, 2, 7.52, 4)
        self.assertGreaterEqual(seconds - 2 - 7.52, 4 + 2)
        self.assertLessEqual(seconds, 30)

    def test_explicit_longer_capture_is_preserved(self):
        self.assertEqual(speech.acoustic_window(20, 2, 2.56, 4), 20)

    def test_overlong_clip_is_rejected_instead_of_truncated(self):
        with self.assertRaises(ValueError):
            speech.acoustic_window(12, 2, 25, 4)


if __name__ == "__main__":
    unittest.main()
