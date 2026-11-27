# SPDX-License-Identifier: Apache-2.0
"""Replay the smoke command latch and wheel odometry from recorded inputs."""

from dataclasses import asdict
import json
import math
from pathlib import Path

from .config import RobotConfig
from .control import Command, CommandLatch, Odometry, wheel_speeds

SMOKE_STOP_S = 11


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("expected a finite number")
    return value


def _close(actual, expected):
    return math.isclose(_number(actual), expected, rel_tol=1e-12, abs_tol=1e-12)


def write_motion_record(trace, state, command, wall, step, *, accepted_wall=None):
    record = {"step": step, "wall_time_s": wall,
              "accepted_command": asdict(command) if command is not None else None,
              "observation": state}
    if command is not None and accepted_wall is not None:
        record["accepted_wall_time_s"] = accepted_wall
    trace.write(json.dumps(record, allow_nan=False, separators=(",", ":")) + "\n")


def replay_motion(path: Path, config: RobotConfig, step_ms: int) -> dict:
    latch = CommandLatch(config.command_ttl_ms)
    odometry = Odometry()
    previous_wall = -math.inf
    expired_steps = 0
    final_sim_time = 0
    count = 0
    with path.open(encoding="utf-8") as stream:
        for count, line in enumerate(stream, 1):
            try:
                tick = json.loads(line)
                state = tick["observation"]
                t = _number(state["sim_time_s"])
                wall = _number(tick["wall_time_s"])
                if tick["step"] != count or not _close(t, count * step_ms / 1000) or wall < previous_wall:
                    raise ValueError("invalid step or clock sequence")
                if tick["accepted_command"] is not None:
                    accepted_wall = _number(tick.get("accepted_wall_time_s", wall))
                    latch.accept(Command.parse({"version": 1, **tick["accepted_command"]}, config), t, accepted_wall)
                command, expired = latch.sample(t, wall)
                if state["applied_command"] != asdict(command) or state["watchdog_expired"] is not expired:
                    raise ValueError("applied command or watchdog mismatch")
                target = state["applied_wheel_rad_s"]
                if not all(_close(actual, expected) for actual, expected
                           in zip(target, wheel_speeds(command, config), strict=True)):
                    raise ValueError("wheel target mismatch")
                left, right = state["wheels_rad"]
                odometry.update(_number(left), _number(right), config)
                if not all(_close(state["odometry"][field], getattr(odometry, field))
                           for field in ("x_m", "y_m", "yaw_rad")):
                    raise ValueError("wheel odometry mismatch")
                previous_wall = wall
                final_sim_time = t
                expired_steps += expired
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise ValueError(f"smoke trace step {count}: {exc}") from exc
    if count == 0:
        raise ValueError("smoke trace is empty")
    return {"steps": count, "final_sim_time_s": final_sim_time, "watchdog_expired_steps": expired_steps}
