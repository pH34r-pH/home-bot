# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import struct
import sys
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from home_bot.png import bgra_to_png


class PngTests(unittest.TestCase):
    def test_camera_bgra_becomes_rgb_with_correct_size_and_checksum(self):
        png = bgra_to_png(bytes([3, 2, 1, 255, 30, 20, 10, 255]), 2, 1)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        offset = 8
        chunks = {}
        while offset < len(png):
            length = struct.unpack(">I", png[offset:offset + 4])[0]
            kind = png[offset + 4:offset + 8]
            content = png[offset + 8:offset + 8 + length]
            checksum = struct.unpack(">I", png[offset + 8 + length:offset + 12 + length])[0]
            self.assertEqual(checksum, zlib.crc32(kind + content) & 0xFFFFFFFF)
            chunks[kind] = content
            offset += length + 12
        self.assertEqual(struct.unpack(">II", chunks[b"IHDR"][:8]), (2, 1))
        self.assertEqual(zlib.decompress(chunks[b"IDAT"]), b"\0\1\2\3\x0a\x14\x1e")


if __name__ == "__main__":
    unittest.main()
