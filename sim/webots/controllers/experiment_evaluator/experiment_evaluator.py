# SPDX-License-Identifier: Apache-2.0
"""Evaluation-only supervisor. Its files must not be given to a robot pilot."""

import json
import math
import os
from pathlib import Path
import sys
from urllib.request import urlopen

from controller import Supervisor

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
from home_bot.geometry import look_at

directory = Path(os.environ.get("HOME_BOT_EXPERIMENT_DIR", str(ROOT / "artifacts/pilot-evaluation")))
directory.mkdir(parents=True, exist_ok=True)
if (directory / "evaluation.jsonl").exists() or (directory / "finish.request").exists():
    raise SystemExit("Evaluation directory already used; choose a fresh HOME_BOT_EXPERIMENT_DIR for each attempt.")
robot = Supervisor()
step = int(robot.getBasicTimeStep())
body = robot.getFromDef("HOME_BOT")
target = [1.5, 0, .16]  # Evaluation truth; never exposed by the robot API.
collisions = []
next_sample = 0
dwell_start = None
achieved = False

while robot.step(step) != -1:
    t = robot.getTime()
    contacts = [list(point.point) for point in body.getContactPoints(True) if point.point[2] > .015]
    if contacts and (not collisions or t - collisions[-1]["sim_time_s"] > .25):
        collisions.append({"sim_time_s": t, "points": contacts})
    if t < next_sample:
        continue
    next_sample = t + .25
    position = list(body.getPosition())
    orientation = body.getOrientation()
    yaw = math.atan2(orientation[3], orientation[0])
    dx, dy = target[0] - position[0], target[1] - position[1]
    distance = math.hypot(dx, dy)
    error = math.atan2(math.sin(math.atan2(dy, dx) - yaw), math.cos(math.atan2(dy, dx) - yaw))
    try:
        with urlopen("http://127.0.0.1:8765/api/state", timeout=.2) as response:
            state = json.load(response)
    except (OSError, ValueError):
        continue
    speed = body.getVelocity()
    checks = {
        "near_target": .25 <= distance <= .50,
        "base_faces_target": abs(error) <= math.radians(20),
        "screen_faces_forward": abs(state["gimbal_rad"][0] - math.pi) < .08 and abs(state["gimbal_rad"][1]) < .10,
        "screen_says_found": state["applied_command"]["text"] == "FOUND",
        "stopped": math.hypot(speed[0], speed[1]) < .01 and abs(speed[5]) < .05,
        "upright": orientation[8] > .95,
        "no_above_floor_contacts": not collisions,
    }
    if all(checks.values()):
        dwell_start = t if dwell_start is None else dwell_start
        achieved = achieved or t - dwell_start >= 1
    else:
        dwell_start = None
    report = {"task_achieved": achieved, "criteria": checks, "sim_time_s": t,
              "truth_position_m": position, "truth_yaw_rad": yaw,
              "target_distance_m": distance, "heading_error_rad": error,
              "above_floor_contact_events": collisions, "sensor_state": state}
    with (directory / "evaluation.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(report, allow_nan=False) + "\n")
    # Atomic replacement lets a read-only observer inspect an intact report.
    temporary = directory / "evaluation.tmp"
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(directory / "evaluation.json")
    if (directory / "finish.request").exists():
        viewpoint = robot.getFromDef("INSPECTION_VIEW")
        view = [position[0] + .8, position[1] + .8, .65]
        viewpoint.getField("position").setSFVec3f(view)
        viewpoint.getField("orientation").setSFRotation(look_at(view, [position[0], position[1], .15]))
        robot.step(step)
        robot.exportImage(str(directory / "final-scene.png"), 100)
        print("HOME_BOT_PILOT_EVALUATION " + json.dumps({"task_achieved": achieved, "criteria": checks}), flush=True)
        break
