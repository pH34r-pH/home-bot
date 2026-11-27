# SPDX-License-Identifier: Apache-2.0
"""Run a Webots pilot attempt or verify and replay a retained pilot bundle."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
from uuid import uuid4

from run_smoke import (
    CONFIG, ROOT, digest, git_output, input_digests, new_output, run_webots, webots_identity, world_settings,
)
from home_bot.config import RobotConfig
from home_bot.pilot_trace import replay_evaluation
from home_bot.smoke_trace import replay_motion

WORLD = ROOT / "sim/webots/worlds/pilot.wbt"
INPUTS = (
    WORLD, ROOT / "scripts/run_pilot.py", ROOT / "scripts/robot.py", ROOT / "docs/experiment-protocol.md",
    ROOT / "sim/webots/controllers/experiment_evaluator/experiment_evaluator.py",
)
RECEIPT = "pilot-receipt.json"
PNG = b"\x89PNG\r\n\x1a\n"


def pilot_inputs():
    shared = input_digests()
    del shared["sim/webots/worlds/smoke.wbt"]
    return {**shared, **{path.relative_to(ROOT).as_posix(): digest(path) for path in INPUTS}}


def output_digests(directory):
    return {path.relative_to(directory).as_posix(): digest(path)
            for path in sorted(directory.rglob("*"))
            if path.is_file() and path != directory / RECEIPT}


def json_lines(path):
    with path.open(encoding="utf-8") as stream:
        yield from map(json.loads, stream)


def observations(pilot, config):
    states = []
    pending = None
    actions = 0
    frames = set()
    for row in json_lines(pilot / "pilot.jsonl"):
        kind = row["event"]
        if kind == "observation":
            frame = Path(row["image"].replace("\\", "/")).name
            state_name = Path(row["state_file"].replace("\\", "/")).name
            if (not re.fullmatch(r"observation-\d+\.png", frame) or frame in frames
                    or state_name != frame.removesuffix(".png") + ".json"):
                raise ValueError("invalid or repeated pilot observation path")
            header = (pilot / frame).read_bytes()[:24]
            if (header[:8] != PNG or header[12:16] != b"IHDR"
                    or tuple(int.from_bytes(header[offset:offset + 4], "big") for offset in (16, 20))
                    != (config.camera_width, config.camera_height)):
                raise ValueError("pilot frame does not match the configured camera")
            state = json.loads((pilot / state_name).read_text(encoding="utf-8"))
            if row["state"] != state:
                raise ValueError("pilot observation and sensor file differ")
            frames.add(frame)
            states.append(state)
        elif kind == "action_start" and pending is None:
            pending = row["action"]
            states.append(row["state_before"])
        elif kind == "action_end" and pending == row["action"]:
            states.append(row["state_after"])
            actions += 1
            pending = None
        else:
            raise ValueError("invalid pilot action sequence")
    if pending is not None or not frames:
        raise ValueError("pilot actions or camera observations are incomplete")
    if actions > 35:
        raise ValueError("the pilot command budget was exceeded")
    return states, {"actions": actions, "camera_samples": len(frames)}


def verify_capture(directory, settings):
    config = RobotConfig.load(CONFIG)
    step = settings["basicTimeStep"]
    evaluator = directory / "evaluator"
    motion_path = evaluator / "pilot-motion.jsonl"
    motion = replay_motion(motion_path, config, step)
    evaluation = replay_evaluation(evaluator / "evaluation.jsonl", step)
    states, pilot = observations(directory / "pilot", config)
    samples = list(json_lines(evaluator / "evaluation.jsonl"))
    states.extend(row["sensor_state"] for row in samples)
    needed = {state["sim_time_s"] for state in states}
    timed_states = {}
    for row in json_lines(motion_path):
        state = row["observation"]
        if state["sim_time_s"] in needed:
            timed_states[state["sim_time_s"]] = state
    if any(timed_states.get(state["sim_time_s"]) != state for state in states):
        raise ValueError("pilot or evaluator sensor state differs from the controller trace")
    terminal = json.loads((evaluator / "evaluation.json").read_text(encoding="utf-8"))
    if terminal != samples[-1]:
        raise ValueError("terminal evaluation differs from the trace")
    if not (evaluator / "final-scene.png").read_bytes().startswith(PNG):
        raise ValueError("evaluator scene image is missing or invalid")
    return {"motion": motion, "evaluation": evaluation, "pilot": pilot}


def verify_bundle(directory):
    receipt = json.loads((directory / RECEIPT).read_text(encoding="utf-8"))
    if receipt["kind"] != "webots_pilot" or receipt["schema_version"] != 1 or receipt["status"] != "completed":
        raise ValueError("a completed Webots pilot receipt is required")
    if receipt["inputs_sha256"] != pilot_inputs() or receipt["world"] != world_settings(WORLD):
        raise ValueError("pilot inputs differ from the receipt")
    if receipt["outputs_sha256"] != output_digests(directory):
        raise ValueError("pilot outputs differ from the receipt")
    result = verify_capture(directory, receipt["world"])
    if result != receipt["replay"]:
        raise ValueError("pilot replay differs from the receipt")
    return result


def require_idle_port(config):
    try:
        connection = socket.create_connection((config.http_host, config.http_port), timeout=1)
    except ConnectionRefusedError:
        return
    connection.close()
    raise ValueError("the loopback port is already occupied by an operator session")


def run_pilot(executable, output_path, timeout, label):
    subprocess.run([sys.executable, str(ROOT / "scripts/build_worlds.py"), "--check"], check=True)
    config = RobotConfig.load(CONFIG)
    # Do not join an existing operator session. Only the new simulation owns this port.
    require_idle_port(config)
    receipt = {
        "schema_version": 1, "kind": "webots_pilot", "attempt_id": str(uuid4()),
        "pilot_label": label, "source_commit": git_output("rev-parse", "HEAD"),
        "source_dirty": bool(git_output("status", "--porcelain")), "inputs_sha256": pilot_inputs(),
        "world": world_settings(WORLD), "runtime": webots_identity(executable), "status": "failed",
    }
    output = new_output(output_path, prefix="pilot-")
    evaluator = output / "evaluator"
    evaluator.mkdir()
    pilot = output / "pilot"
    pilot.mkdir()
    print(f"Pilot observations: {pilot}\nEvaluator directory: {evaluator}", flush=True)
    try:
        receipt["exit_code"] = run_webots(
            executable, output, timeout, world=WORLD, mode="realtime", log_name="webots-pilot.log",
            settings={"HOME_BOT_EXPERIMENT_DIR": str(evaluator), "HOME_BOT_PILOT_EXIT": "1",
                      "HOME_BOT_PILOT_TRACE": str(evaluator / "pilot-motion.jsonl")},
        )
        if (receipt["exit_code"] != 0 or pilot_inputs() != receipt["inputs_sha256"]
                or digest(executable) != receipt["runtime"]["webots_launcher_sha256"]):
            raise ValueError("pilot failed or its inputs changed")
        receipt["replay"] = verify_capture(output, receipt["world"])
        receipt["runtime"]["evaluator"] = json.loads((evaluator / "evaluation-runtime.json").read_text(encoding="utf-8"))
        receipt["status"] = "completed"
    except subprocess.TimeoutExpired:
        receipt.update(status="timeout", error=f"Webots exceeded {timeout}s")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        receipt["error"] = str(exc)
    receipt["outputs_sha256"] = output_digests(output)
    (output / RECEIPT).write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return output, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--webots", default=os.environ.get("WEBOTS_EXECUTABLE") or shutil.which("webots"))
    parser.add_argument("--timeout", type=int, default=750)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pilot-label", help="Operator-declared pilot identity for this attempt")
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    try:
        if args.replay is not None:
            print(json.dumps(verify_bundle(args.replay), indent=2))
            return
        if not args.webots or not args.pilot_label or args.timeout <= 0:
            parser.error("Provide a Webots executable, pilot label, and positive timeout")
        executable = Path(shutil.which(args.webots) or args.webots).resolve(strict=True)
        output, receipt = run_pilot(executable, args.output, args.timeout, args.pilot_label)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        raise SystemExit(str(exc)) from exc
    if receipt["status"] != "completed":
        raise SystemExit(f"{receipt['status']}: {receipt['error']}. Evidence: {output}")
    print(f"Webots pilot evidence: {output}. Task achieved: {receipt['replay']['evaluation']['task_achieved']}.")


if __name__ == "__main__":
    main()
