# SPDX-License-Identifier: Apache-2.0
"""Load the provisional hardware profile; never infer a servo model or pinout."""

from dataclasses import dataclass, fields
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class RobotConfig:
    schema_version: int = 1
    wheel_radius_m: float = 0.034
    track_width_m: float = 0.105
    max_linear_mps: float = 0.44704
    max_angular_rps: float = 3.0
    wheel_acceleration_rad_s2: float = 18.0
    wheel_torque_nm: float = 0.25
    pan_min_rad: float = 0.0
    pan_max_rad: float = math.pi
    tilt_min_rad: float = -0.6
    tilt_max_rad: float = 0.6
    gimbal_speed_rad_s: float = 1.2
    gimbal_torque_nm: float = 0.25
    command_ttl_ms: int = 400
    camera_width: int = 160
    camera_height: int = 240
    camera_horizontal_fov_rad: float = 0.9
    camera_period_ms: int = 128
    http_host: str = "127.0.0.1"
    http_port: int = 8765

    @property
    def max_wheel_rad_s(self) -> float:
        return self.max_linear_mps / self.wheel_radius_m

    @classmethod
    def load(cls, path: Path) -> "RobotConfig":
        data = json.loads(path.read_text(encoding="utf-8"))
        allowed = {f.name for f in fields(cls)}
        unknown = set(data) - allowed - {"notes"}
        if unknown:
            raise ValueError(f"Unknown configuration fields: {sorted(unknown)}")
        config = cls(**{key: value for key, value in data.items() if key in allowed})
        for f in fields(config):
            value = getattr(config, f.name)
            if f.name == "http_host":
                if value not in {"127.0.0.1", "localhost"}:
                    raise ValueError("This prototype serves loopback only; LAN pairing is not implemented")
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{f.name} must be a finite number")
        if config.schema_version != 1:
            raise ValueError("Unsupported configuration schema")
        for key in ("wheel_radius_m", "track_width_m", "max_linear_mps", "max_angular_rps",
                    "wheel_acceleration_rad_s2", "wheel_torque_nm", "gimbal_speed_rad_s",
                    "gimbal_torque_nm", "command_ttl_ms", "camera_period_ms"):
            if getattr(config, key) <= 0:
                raise ValueError(f"{key} must be positive")
        if not (config.pan_min_rad <= 0 < config.pan_max_rad
                and config.tilt_min_rad < 0 < config.tilt_max_rad):
            raise ValueError("Gimbal limits must include the forward pose")
        for key in ("schema_version", "command_ttl_ms", "camera_width", "camera_height",
                    "camera_period_ms", "http_port"):
            if type(getattr(config, key)) is not int:
                raise ValueError(f"{key} must be an integer")
        if not (1 <= config.http_port <= 65535 and 1 <= config.camera_width <= 1920
                and 1 <= config.camera_height <= 1920 and 0 < config.camera_horizontal_fov_rad < math.pi):
            raise ValueError("Invalid port or camera configuration")
        if not (50 <= config.command_ttl_ms <= 1000):
            raise ValueError("command_ttl_ms must be between 50 and 1000")
        return config
