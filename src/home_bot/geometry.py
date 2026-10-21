# SPDX-License-Identifier: Apache-2.0
"""Coordinate helpers for the inspection viewpoint, not robot localization."""

import math


def look_at(position, target):
    def unit(vector):
        size = math.sqrt(sum(v * v for v in vector))
        return [v / size for v in vector]

    def cross(a, b):
        return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]

    forward = unit([b - a for a, b in zip(position, target)])
    right = unit(cross(forward, [0, 0, 1]))
    up = cross(right, forward)
    # Webots' current camera/viewpoint convention is +X forward, +Y left, +Z up.
    matrix = [[forward[i], -right[i], up[i]] for i in range(3)]
    angle = math.acos(max(-1, min(1, (sum(matrix[i][i] for i in range(3)) - 1) / 2)))
    axis = unit([matrix[2][1] - matrix[1][2], matrix[0][2] - matrix[2][0], matrix[1][0] - matrix[0][1]])
    return [*axis, angle]
