# SPDX-License-Identifier: Apache-2.0
"""Small, model-independent operator CLI for the running robot."""

import argparse
import base64
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8765"


def request(path, data=None):
    headers = {"Content-Type": "application/json"} if data is not None else {}
    body = json.dumps(data, allow_nan=False).encode() if data is not None else None
    with urlopen(Request(BASE + path, data=body, headers=headers), timeout=3) as response:
        return json.load(response)


def record(directory, event):
    directory.mkdir(parents=True, exist_ok=True)
    event = {"wall_time_utc": datetime.now(timezone.utc).isoformat(), **event}
    with (directory / "pilot.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, allow_nan=False) + "\n")


def observe(directory):
    observation = request("/api/observation")
    stamp = time.time_ns()
    image = directory / f"observation-{stamp}.png"
    state_file = directory / f"observation-{stamp}.json"
    directory.mkdir(parents=True, exist_ok=True)
    image.write_bytes(base64.b64decode(observation["camera_png_base64"], validate=True))
    state_file.write_text(json.dumps(observation["state"], indent=2) + "\n", encoding="utf-8")
    result = {"image": str(image.resolve()), "state_file": str(state_file.resolve()), "state": observation["state"]}
    record(directory, {"event": "observation", **result})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=Path("artifacts/pilot"))
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("observe")
    sub.add_parser("stop")
    drive = sub.add_parser("drive")
    drive.add_argument("--linear", type=float, default=0, help="m/s, -0.08..0.08")
    drive.add_argument("--angular", type=float, default=0, help="rad/s, -0.7..0.7; positive left")
    drive.add_argument("--seconds", type=float, required=True, help="wall seconds, 0..5")
    look = sub.add_parser("look")
    look.add_argument("--pan", type=float, required=True, help="radians, 0..pi")
    look.add_argument("--tilt", type=float, default=0, help="radians, -0.6..0.6; positive up")
    face = sub.add_parser("face")
    face.add_argument("--expression", choices=["neutral", "happy", "curious", "sleepy"], default="happy")
    face.add_argument("--text", required=True)
    args = parser.parse_args()
    if args.action == "observe":
        print(json.dumps(observe(args.run_dir), indent=2))
        return
    state = request("/api/state")
    command = {**state["applied_command"], "version": 1, "linear_mps": 0, "angular_rps": 0, "ttl_ms": 400}
    duration = 0.3
    if args.action == "drive":
        if not (math.isfinite(args.linear) and abs(args.linear) <= .08 and math.isfinite(args.angular) and abs(args.angular) <= .7 and 0 < args.seconds <= 5):
            parser.error("drive requires |linear|<=0.08, |angular|<=0.7, 0<seconds<=5")
        command.update(linear_mps=args.linear, angular_rps=args.angular)
        duration = args.seconds
    elif args.action == "look":
        if not (0 <= args.pan <= math.pi and -.6 <= args.tilt <= .6):
            parser.error("look requires 0<=pan<=pi, -0.6<=tilt<=0.6")
        command.update(pan_rad=args.pan, tilt_rad=args.tilt)
        duration = 3.5
    elif args.action == "face":
        if not args.text.isascii() or not args.text.isprintable() or len(args.text) > 48:
            parser.error("text must contain at most 48 printable ASCII characters")
        command.update(expression=args.expression, text=args.text)
    record(args.run_dir, {"event": "action_start", "action": args.action, "duration_wall_s": duration, "command": command, "state_before": state})
    try:
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            request("/api/command", command)
            time.sleep(min(.1, max(0, deadline - time.monotonic())))
    finally:
        command.update(linear_mps=0, angular_rps=0)
        request("/api/command", command)
    # Let wheel acceleration limits settle and obtain a fresh camera sample.
    time.sleep(.5)
    result = observe(args.run_dir)
    record(args.run_dir, {"event": "action_end", "action": args.action, "state_after": result["state"]})
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
