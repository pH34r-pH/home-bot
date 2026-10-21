# SPDX-License-Identifier: Apache-2.0
"""Run the actual Webots maneuver test and check the generated report."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--webots", default=os.environ.get("WEBOTS_EXECUTABLE", shutil.which("webots")))
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    if not args.webots:
        parser.error("Pass --webots PATH or set WEBOTS_EXECUTABLE")
    subprocess.run([sys.executable, str(ROOT / "scripts/build_worlds.py"), "--check"], check=True)
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    report = output / "smoke-report.json"
    report.unlink(missing_ok=True)
    command = [args.webots, "--batch", "--minimize", "--mode=fast", "--stdout", "--stderr", str(ROOT / "sim/webots/worlds/smoke.wbt")]
    options = {}
    if os.name == "nt":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        options["startupinfo"] = startup
    with (output / "webots-smoke.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT, **options)
        try:
            process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            else:
                process.kill()
            raise SystemExit(f"Webots exceeded {args.timeout}s; see artifacts/webots-smoke.log")
    if not report.exists():
        raise SystemExit("Webots did not write a report; see artifacts/webots-smoke.log")
    data = json.loads(report.read_text(encoding="utf-8"))
    for name, passed in data["checks"].items():
        print(f"{'PASS' if passed else 'FAIL'} {name}")
    if process.returncode != 0 or not data["passed"]:
        raise SystemExit(f"Webots test failed (exit {process.returncode}); inspect artifacts/")
    print("Webots integration passed. Images and report: artifacts/")


if __name__ == "__main__":
    main()
