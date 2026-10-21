# SPDX-License-Identifier: Apache-2.0
"""Validated commands, differential drive, and a dual-clock dead-man timer."""

from dataclasses import dataclass, replace
import math
from typing import Any

from .config import RobotConfig

EXPRESSIONS = ("neutral", "happy", "curious", "sleepy")


@dataclass(frozen=True)
class Command:
    linear_mps: float = 0.0
    angular_rps: float = 0.0
    pan_rad: float = 0.0
    tilt_rad: float = 0.0
    expression: str = "neutral"
    text: str = "HELLO"
    ttl_ms: int = 400

    @classmethod
    def parse(cls, data: Any, config: RobotConfig) -> "Command":
        if not isinstance(data, dict):
            raise ValueError("Command must be a JSON object")
        allowed = {"version", "linear_mps", "angular_rps", "pan_rad", "tilt_rad", "expression", "text", "ttl_ms"}
        if set(data) - allowed:
            raise ValueError("Unknown command fields")
        if type(data.get("version")) is not int or data["version"] != 1:
            raise ValueError("version must be 1")
        limits = {
            "linear_mps": (-config.max_linear_mps, config.max_linear_mps),
            "angular_rps": (-config.max_angular_rps, config.max_angular_rps),
            "pan_rad": (config.pan_min_rad, config.pan_max_rad),
            "tilt_rad": (config.tilt_min_rad, config.tilt_max_rad),
        }
        numbers = {}
        for key, (low, high) in limits.items():
            value = data.get(key, 0.0)
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                raise ValueError(f"{key} must be finite")
            if not low <= value <= high:
                raise ValueError(f"{key} must be in [{low}, {high}]")
            numbers[key] = float(value)
        expression = data.get("expression", "neutral")
        if not isinstance(expression, str) or expression not in EXPRESSIONS:
            raise ValueError(f"expression must be one of {EXPRESSIONS}")
        text = data.get("text", "HELLO")
        if not isinstance(text, str) or len(text) > 48 or any(ord(c) < 32 or ord(c) > 126 for c in text):
            raise ValueError("text must contain at most 48 printable ASCII characters")
        ttl = data.get("ttl_ms", config.command_ttl_ms)
        if type(ttl) is not int or not 50 <= ttl <= 1000:
            raise ValueError("ttl_ms must be an integer from 50 to 1000")
        return cls(**numbers, expression=expression, text=text, ttl_ms=ttl)


def wheel_speeds(command: Command, config: RobotConfig) -> tuple[float, float]:
    left = (command.linear_mps - command.angular_rps * config.track_width_m / 2) / config.wheel_radius_m
    right = (command.linear_mps + command.angular_rps * config.track_width_m / 2) / config.wheel_radius_m
    scale = max(1.0, abs(left) / config.max_wheel_rad_s, abs(right) / config.max_wheel_rad_s)
    return left / scale, right / scale


class CommandLatch:
    """Expire on either clock, including a simulator pause or accelerated run."""

    def __init__(self, ttl_ms: int = 400):
        self.command = Command(ttl_ms=ttl_ms)
        self.expires_sim = float("-inf")
        self.expires_wall = float("-inf")

    def accept(self, command: Command, sim_time: float, received_wall: float) -> None:
        self.command = command
        self.expires_sim = sim_time + command.ttl_ms / 1000
        self.expires_wall = received_wall + command.ttl_ms / 1000

    def sample(self, sim_time: float, wall_time: float) -> tuple[Command, bool]:
        expired = sim_time >= self.expires_sim or wall_time >= self.expires_wall
        if expired:
            # Latch the stop. A subsequent clock change cannot revive old motion.
            self.command = replace(self.command, linear_mps=0.0, angular_rps=0.0)
        return self.command, expired


@dataclass
class Odometry:
    """Wheel-only planar estimate; deliberately has no simulator truth input."""

    x_m: float = 0.0
    y_m: float = 0.0
    yaw_rad: float = 0.0
    previous: tuple[float, float] | None = None

    def update(self, left_rad: float, right_rad: float, config: RobotConfig) -> None:
        if self.previous is not None:
            dl = (left_rad - self.previous[0]) * config.wheel_radius_m
            dr = (right_rad - self.previous[1]) * config.wheel_radius_m
            distance = (dl + dr) / 2
            turn = (dr - dl) / config.track_width_m
            # Exact integration for a constant-curvature differential-drive step.
            sinc = 1.0 if abs(turn) < 1e-10 else math.sin(turn / 2) / (turn / 2)
            self.x_m += distance * sinc * math.cos(self.yaw_rad + turn / 2)
            self.y_m += distance * sinc * math.sin(self.yaw_rad + turn / 2)
            self.yaw_rad = math.atan2(math.sin(self.yaw_rad + turn), math.cos(self.yaw_rad + turn))
        self.previous = (left_rad, right_rad)
