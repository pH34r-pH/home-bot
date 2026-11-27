# SPDX-License-Identifier: Apache-2.0
"""Evaluation-only supervisor. Its files must not be given to a robot pilot."""

import json
import math
import os
from pathlib import Path
import platform
import sys
from urllib.request import urlopen

from controller import Supervisor

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
from home_bot.geometry import look_at
from home_bot.pilot_trace import PilotEvaluation, SAMPLE_PERIOD_S

directory = Path(os.environ.get("HOME_BOT_EXPERIMENT_DIR", str(ROOT / "artifacts/pilot-evaluation")))
directory.mkdir(parents=True, exist_ok=True)
if (directory / "evaluation.jsonl").exists() or (directory / "finish.request").exists():
    raise SystemExit("Evaluation directory already used; choose a fresh HOME_BOT_EXPERIMENT_DIR for each attempt.")
robot = Supervisor()
step = int(robot.getBasicTimeStep())
body = robot.getFromDef("HOME_BOT")
(directory / "evaluation-runtime.json").write_text(
    json.dumps({"python": platform.python_version(), "physics_step_ms": step}) + "\n",
    encoding="utf-8",
)
evaluation = PilotEvaluation(step)
collisions = []
next_sample = 0

while robot.step(step) != -1:
    t = robot.getTime()
    contacts = [list(point.point) for point in body.getContactPoints(True) if point.point[2] > .015]
    if contacts and (not collisions or t - collisions[-1]["sim_time_s"] > .25):
        collisions.append({"sim_time_s": t, "points": contacts})
    if t < next_sample:
        continue
    next_sample = t + SAMPLE_PERIOD_S
    position = list(body.getPosition())
    orientation = body.getOrientation()
    yaw = math.atan2(orientation[3], orientation[0])
    try:
        with urlopen("http://127.0.0.1:8765/api/state", timeout=.2) as response:
            state = json.load(response)
    except (OSError, ValueError):
        continue
    report = {"sim_time_s": t, "truth_position_m": position, "truth_yaw_rad": yaw,
              "truth_velocity": list(body.getVelocity()), "truth_up_axis": orientation[8],
              "above_floor_contact_events": collisions, "sensor_state": state}
    report.update(evaluation.observe(report))
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
        print("HOME_BOT_PILOT_EVALUATION " + json.dumps(
            {"task_achieved": evaluation.achieved, "criteria": report["criteria"]}), flush=True)
        if os.environ.get("HOME_BOT_PILOT_EXIT") == "1":
            robot.simulationQuit(0)
        break
