# SPDX-License-Identifier: Apache-2.0
"""Explicit native Pixel speech tests; transcripts remain in ignored local artifacts."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import wave

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "org.homebot.speechlab"
REMOTE = "/data/local/tmp/home-bot-speech"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True)
    commands = parser.add_subparsers(dest="mode", required=True)
    speak = commands.add_parser("speak", help="generate and stream Phonon on the phone")
    speak.add_argument("--text", required=True)
    speak.add_argument("--cancel-after", type=float, help="seconds after the first observed played frame")
    listen = commands.add_parser("listen", help="bounded microphone recognition; no raw recording saved")
    listen.add_argument("--seconds", type=int, default=12, choices=range(1, 31))
    listen.add_argument("--play-wav", type=Path, help="play a known synthetic WAV on the PC after capture starts (requires ffplay)")
    listen.add_argument("--pc-gain", type=int, default=70, choices=range(1, 101))
    file_test = commands.add_parser("file", help="recognize a canonical PCM16 mono WAV on the phone")
    file_test.add_argument("--wav", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "speak":
        if not args.text.strip() or len(args.text.encode("utf-8")) > 2047:
            parser.error("text must contain 1..2047 UTF-8 bytes")
        if args.cancel_after is not None and not 0 <= args.cancel_after <= 30:
            parser.error("cancel-after must be between 0 and 30 seconds")
    output = ROOT / "artifacts/phone-speech"
    output.mkdir(parents=True, exist_ok=True)
    lock = output / "speech.lock"
    try:
        lease = lock.open("x")
    except FileExistsError:
        parser.error("another local speech operation holds artifacts/phone-speech/speech.lock")
    adb = ["adb", "-s", args.serial]

    def run(*command):
        return subprocess.run(adb + list(map(str, command)), check=True, capture_output=True, text=True, timeout=90).stdout

    def stop():
        run("shell", "am", "start-foreground-service", "-n", PACKAGE + "/.SpeechService", "-a", "STOP")

    player = None
    active = False
    temporary = None
    try:
        if args.mode == "speak":
            with tempfile.NamedTemporaryFile(dir=output, suffix=".txt", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(args.text.encode("utf-8"))
            source, destination = temporary, "prompt.txt"
        elif args.mode == "file":
            source, destination = args.wav.resolve(), "input.wav"
            with wave.open(str(source)) as wav:
                if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() not in (16000, 24000) or wav.getcomptype() != "NONE":
                    parser.error("WAV must be mono PCM16 at 16 or 24 kHz")
            if not 46 <= source.stat().st_size <= 10 * 1024 * 1024:
                parser.error("WAV size out of bounds")
        if args.mode != "listen":
            run("push", source, REMOTE + "/session-input")
            run("shell", "run-as", PACKAGE, "cp", REMOTE + "/session-input", "files/" + destination)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            received = run("shell", "run-as", PACKAGE, "sha256sum", "files/" + destination).split()[0]
            if received != digest:
                raise RuntimeError("input transfer hash mismatch")
        run("shell", "run-as", PACKAGE, "rm", "-f", "files/session.json")
        arguments = ["shell", "am", "start-foreground-service", "-n", PACKAGE + "/.SpeechService", "--es", "mode", args.mode]
        if args.mode == "listen":
            arguments += ["--ei", "seconds", str(args.seconds)]
        response = run(*arguments)
        if "Error" in response or "Exception" in response:
            raise RuntimeError(response)
        active = True
        deadline = time.monotonic() + 90
        first_pcm_seen = None
        cancellation_sent = False
        while time.monotonic() < deadline:
            time.sleep(.2)
            try:
                result = json.loads(run("shell", "run-as", PACKAGE, "cat", "files/session.json"))
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                continue
            state = result["state"]
            if args.mode == "listen" and state == "listening" and args.play_wav and player is None:
                player = subprocess.Popen(["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", "-volume", str(args.pc_gain), str(args.play_wav.resolve())], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if args.mode == "speak" and args.cancel_after is not None and result.get("first_played_observed_ms", -1) >= 0:
                if first_pcm_seen is None:
                    first_pcm_seen = time.monotonic()
                if not cancellation_sent and time.monotonic() - first_pcm_seen >= args.cancel_after:
                    stop(); cancellation_sent = True
            if state not in {"completed", "cancelled", "failed", "busy"}:
                continue
            active = False
            if args.mode == "listen" and args.play_wav and player is None:
                raise RuntimeError("capture finished before PC playback could start")
            if player is not None:
                if player.poll() is None:
                    player.wait(timeout=10)
                result["pc_player_exit_code"] = player.returncode
                if player.returncode:
                    raise RuntimeError("PC audio playback failed")
                result["pc_audio_gain_percent"] = args.pc_gain
            if cancellation_sent:
                result["host_requested_cancellation"] = True
            (output / "latest-session.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(result, indent=2))
            if state != ("cancelled" if cancellation_sent else "completed"):
                raise RuntimeError("phone speech session did not complete as requested")
            if args.mode == "speak" and not cancellation_sent and (result.get("playback_head_frames") != result["samples"] or not result.get("speaker_route")):
                raise RuntimeError("stream playback did not drain fully through the speaker")
            if args.mode == "listen" and (not result["samples"] or result.get("client_silenced", True)):
                raise RuntimeError("microphone produced no samples or Android silenced the client")
            return
        raise TimeoutError("phone session did not finish within 90 seconds")
    finally:
        if player is not None and player.poll() is None:
            player.terminate(); player.wait(timeout=10)
        if active:
            try:
                stop()
            except (OSError, subprocess.SubprocessError):
                pass
        if temporary:
            temporary.unlink(missing_ok=True)
        for command in [
            ["shell", "rm", "-f", REMOTE + "/session-input"],
            ["shell", "run-as", PACKAGE, "rm", "-f", "files/prompt.txt", "files/input.wav", "files/session.json"],
        ]:
            try:
                run(*command)
            except (OSError, subprocess.SubprocessError):
                pass
        lease.close(); lock.unlink()


if __name__ == "__main__":
    main()
