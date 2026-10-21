# SPDX-License-Identifier: Apache-2.0
"""Small dependency-free PNG encoder for Webots BGRA camera frames."""

import struct
import zlib


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def bgra_to_png(data: bytes, width: int, height: int) -> bytes:
    if width < 1 or height < 1 or len(data) != width * height * 4:
        raise ValueError("Invalid BGRA frame size")
    pixels = bytearray()
    for y in range(height):
        pixels.append(0)
        for offset in range(y * width * 4, (y + 1) * width * 4, 4):
            pixels.extend((data[offset + 2], data[offset + 1], data[offset]))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(bytes(pixels), 3)) + _chunk(b"IEND", b"")
