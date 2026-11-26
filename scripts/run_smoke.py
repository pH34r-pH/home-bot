# SPDX-License-Identifier: Apache-2.0
"""Run a fresh Webots smoke exercise or replay its recorded motion trace."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from home_bot.config import RobotConfig
from home_bot.smoke_trace import SMOKE_STOP_S, replay_motion

WORLD = ROOT / "sim/webots/worlds/smoke.wbt"
CONFIG = ROOT / "config/robot.json"
FILES = ("webots-smoke.log", "smoke-report.json", "smoke-trace.jsonl",
         "camera-forward.png", "rear-camera.png", "phone-screen.png", "simulation.png")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def input_digests():
    root = ROOT / "sim/webots"
    inputs = [
        WORLD, CONFIG, Path(__file__).resolve(), ROOT / "scripts/build_worlds.py",
        root / "protos/HomeBot.proto", root / "textures/screen.png",
        root / "controllers/home_bot_controller/home_bot_controller.py",
        *sorted((ROOT / "src/home_bot").glob("*.py")),
    ]
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in inputs}


def world_settings():
    text = WORLD.read_text(encoding="utf-8")
    return {
        name: int(re.search(rf"^\s*{name} (\d+)\s*$", text, re.MULTILINE)[1])
        for name in ("basicTimeStep", "randomSeed")
    }


def git_output(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def new_output(path):
    if path is not None:
        path = path.resolve()
        path.mkdir(parents=True)
        return path
    directory = ROOT / "artifacts"
    directory.mkdir(exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="smoke-", dir=directory))


def run_webots(executable, output, timeout):
    command = [str(executable), "--batch", "--minimize", "--mode=fast", "--stdout", "--stderr", str(WORLD)]
    options = {"start_new_session": True}
    if os.name == "nt":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        options = {"startupinfo": startup}
    env = {**os.environ, "HOME_BOT_SMOKE_OUTPUT": str(output)}
    with (output / "webots-smoke.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT, env=env, **options)
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
                if process.poll() is None:
                    process.kill()
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait()
            raise


def replay_recorded(directory, settings):
    replay = replay_motion(directory / "smoke-trace.jsonl", RobotConfig.load(CONFIG), settings["basicTimeStep"])
    if not SMOKE_STOP_S <= replay["final_sim_time_s"] < SMOKE_STOP_S + settings["basicTimeStep"] / 1000:
        raise ValueError("trace ended outside the expected smoke terminal step")
    return replay


def verify_bundle(directory):
    receipt = json.loads((directory / "smoke-receipt.json").read_text(encoding="utf-8"))
    if receipt["schema_version"] != 1 or receipt["kind"] != "webots_smoke" or receipt["status"] != "passed":
        raise ValueError("a passing Webots smoke receipt is required")
    if receipt["inputs_sha256"] != input_digests() or receipt["world"] != world_settings():
        raise ValueError("smoke inputs differ from the receipt")
    if receipt["outputs_sha256"] != {name: digest(directory / name) for name in FILES}:
        raise ValueError("smoke outputs differ from the receipt")
    replay = replay_recorded(directory, receipt["world"])
    if replay != receipt["motion_replay"]:
        raise ValueError("motion replay differs from the receipt")
    return replay


def run_smoke(executable, output_path, timeout):
    subprocess.run([sys.executable, str(ROOT / "scripts/build_worlds.py"), "--check"], check=True)
    version = subprocess.run([str(executable), "--version"], check=True, capture_output=True, text=True, timeout=15)
    match = re.search(r"(?mi)^Webots(?: version:)? (R\d{4}[a-z][^\r\n]*)$", version.stdout + "\n" + version.stderr)
    if not match:
        raise ValueError("Webots did not report its version")
    receipt = {
        "schema_version": 1, "kind": "webots_smoke", "source_commit": git_output("rev-parse", "HEAD"),
        "source_dirty": bool(git_output("status", "--porcelain")), "inputs_sha256": input_digests(),
        "world": world_settings(),
        "runtime": {"webots_version": match[1], "webots_launcher_sha256": digest(executable),
                    "runner_python": platform.python_version(), "platform": platform.platform()},
    }
    output = new_output(output_path)
    receipt["status"] = "failed"
    try:
        receipt["exit_code"] = run_webots(executable, output, timeout)
        report = json.loads((output / "smoke-report.json").read_text(encoding="utf-8"))
        checks = report["checks"]
        receipt["checks"] = checks
        receipt["runtime"]["controller_python"] = report["controller_python"]
        receipt["terminal_sim_time_s"] = report["terminal_sim_time_s"]
        for name, passed in checks.items():
            print(f"{'PASS' if passed else 'FAIL'} {name}")
        if receipt["exit_code"] != 0 or report["passed"] is not True or not checks or not all(
            passed is True for passed in checks.values()
        ):
            raise ValueError("Webots smoke checks failed")
        if input_digests() != receipt["inputs_sha256"]:
            raise ValueError("smoke inputs changed during the run")
        receipt["motion_replay"] = replay_recorded(output, receipt["world"])
        if receipt["motion_replay"]["final_sim_time_s"] != receipt["terminal_sim_time_s"]:
            raise ValueError("trace and evaluator report ended at different steps")
        if any(not (output / name).is_file() for name in FILES):
            raise ValueError("required smoke outputs were missing")
        receipt["status"] = "passed"
    except subprocess.TimeoutExpired:
        receipt.update(status="timeout", error=f"Webots exceeded {timeout}s")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        receipt["error"] = str(exc)
    receipt["outputs_sha256"] = {name: digest(output / name) for name in FILES if (output / name).is_file()}
    (output / "smoke-receipt.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return output, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--webots", default=os.environ.get("WEBOTS_EXECUTABLE") or shutil.which("webots"))
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output", type=Path, help="Fresh directory for one attempt")
    parser.add_argument("--replay", type=Path, help="Verify a passing bundle and replay its motion without Webots")
    args = parser.parse_args()
    try:
        if args.replay is not None:
            if args.output is not None:
                parser.error("--output is only used for a new run")
            replay = verify_bundle(args.replay)
            print(f"Motion replay passed for {replay['steps']} steps.")
            return
        if not args.webots or args.timeout <= 0:
            parser.error("Provide a Webots executable and a positive timeout")
        executable = Path(shutil.which(args.webots) or args.webots).resolve(strict=True)
        output, receipt = run_smoke(executable, args.output, args.timeout)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        raise SystemExit(str(exc)) from exc
    if receipt["status"] != "passed":
        raise SystemExit(f"{receipt['status']}: {receipt['error']}. Evidence: {output}")
    print(f"Webots smoke and motion replay passed. Evidence: {output}")


if __name__ == "__main__":
    main()
