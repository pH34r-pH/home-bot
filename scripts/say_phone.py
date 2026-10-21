# SPDX-License-Identifier: Apache-2.0
"""Generate speech on the authorized Android phone, then play it without a browser."""

import argparse
import json
from pathlib import Path
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
REMOTE = "/data/local/tmp/home-bot-speech"
PLAYER = "org.homebot.speechlab"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True, help="authorized device from adb devices")
    parser.add_argument("--text", required=True)
    parser.add_argument("--threads", type=int, choices=[1, 2], default=2)
    parser.add_argument("--save-wav", type=Path, help="explicitly retain synthesized audio on the PC")
    args = parser.parse_args()
    text = args.text.encode("utf-8")
    if not text.strip() or len(text) > 2047:
        parser.error("text must contain 1..2047 UTF-8 bytes")
    output = ROOT / "artifacts/phone-speech"
    output.mkdir(parents=True, exist_ok=True)
    lock = output / "speech.lock"
    try:
        lease = lock.open("x")
    except FileExistsError:
        parser.error("another local speech operation holds artifacts/phone-speech/speech.lock")
    prompt = output / f"prompt-{uuid.uuid4().hex}.txt"
    adb = ["adb", "-s", args.serial]

    def run(*command):
        return subprocess.run(adb + list(command), check=True, capture_output=True, text=True, timeout=90).stdout

    playing = False
    try:
        prompt.write_bytes(text)
        run("push", str(prompt), REMOTE + "/current-prompt.txt")
        run("shell", "env", "LD_LIBRARY_PATH=" + REMOTE, f"RAYON_NUM_THREADS={args.threads}",
            REMOTE + "/phonon-phone", REMOTE + "/model", REMOTE + "/current-prompt.txt",
            REMOTE + "/current.wav", REMOTE + "/current-metrics.json")
        metrics = json.loads(run("shell", "cat", REMOTE + "/current-metrics.json"))
        if not metrics["library_ok"] or not metrics["samples"] or metrics["rms"] <= 0:
            raise RuntimeError("native synthesis did not produce valid nonzero audio")
        if args.save_wav:
            args.save_wav.parent.mkdir(parents=True, exist_ok=True)
            run("pull", REMOTE + "/current.wav", str(args.save_wav))
        run("shell", "run-as", PLAYER, "cp", REMOTE + "/current.wav", "files/test.wav")
        native_hash = run("shell", "sha256sum", REMOTE + "/current.wav").split()[0]
        player_hash = run("shell", "run-as", PLAYER, "sha256sum", "files/test.wav").split()[0]
        if native_hash != player_hash:
            raise RuntimeError("playback WAV transfer integrity failed")
        run("shell", "run-as", PLAYER, "rm", "-f", "files/playback.json")
        run("shell", "am", "start-foreground-service", "-n", PLAYER + "/.PlaybackService")
        playing = True
        deadline = time.monotonic() + metrics["audio_seconds"] + 10
        while time.monotonic() < deadline:
            time.sleep(.5)
            try:
                playback = json.loads(run("shell", "run-as", PLAYER, "cat", "files/playback.json"))
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                continue
            if playback["state"] == "playing":
                continue
            if playback["state"] != "completed" or playback.get("playback_head_frames") != metrics["samples"] or not playback.get("speaker_route") or playback.get("media_volume", 0) <= 0:
                raise RuntimeError("phone playback failed: " + json.dumps(playback))
            playing = False
            report = {"synthesis": metrics, "playback": playback, "wav_sha256": native_hash}
            (output / "latest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, indent=2))
            return
        raise TimeoutError("phone playback did not finish")
    finally:
        prompt.unlink(missing_ok=True)
        # Only these owned temporary speech files are removed; model assets remain.
        cleanup = []
        if playing:
            cleanup.append(["shell", "am", "start-foreground-service", "-n", PLAYER + "/.PlaybackService", "-a", "STOP"])
        cleanup.extend([
            ["shell", "rm", "-f", REMOTE + "/current-prompt.txt", REMOTE + "/current.wav"],
            ["shell", "run-as", PLAYER, "rm", "-f", "files/test.wav"],
        ])
        for command in cleanup:
            try:
                subprocess.run(adb + command, capture_output=True, timeout=10)
            except (OSError, subprocess.SubprocessError):
                pass  # A lost ADB connection must not strand the local command lease.
        lease.close()
        lock.unlink()


if __name__ == "__main__":
    main()
