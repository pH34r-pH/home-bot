# SPDX-License-Identifier: Apache-2.0
"""Draw the simulated Pixel screen with Webots' Display device."""

import textwrap


def draw_face(display, expression: str, text: str) -> None:
    width, height = display.getWidth(), display.getHeight()
    display.setColor(0x08151C)
    display.fillRectangle(0, 0, width, height)
    display.setColor(0x63E4D8)
    eye_y = int(height * 0.35)
    for x in (int(width * 0.3), int(width * 0.7)):
        if expression == "sleepy":
            display.fillRectangle(x - 12, eye_y, 24, 4)
        elif expression == "happy":
            display.fillOval(x, eye_y, 13, 8)
            display.setColor(0x08151C)
            display.fillRectangle(x - 14, eye_y + 1, 28, 10)
            display.setColor(0x63E4D8)
        else:
            display.fillOval(x, eye_y, 11 if expression == "neutral" else 15, 18)
    if expression == "curious":
        display.drawOval(width // 2, int(height * 0.57), 7, 10)
    else:
        display.drawLine(int(width * 0.39), int(height * 0.56), width // 2, int(height * 0.60))
        display.drawLine(width // 2, int(height * 0.60), int(width * 0.61), int(height * 0.56))
    display.setFont("Arial", 13, True)
    display.setColor(0xE3F1EE)
    for index, line in enumerate(textwrap.wrap(text, width=18)[:3]):
        display.drawText(line, 8, int(height * 0.74) + 17 * index)
