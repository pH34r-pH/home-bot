# SPDX-License-Identifier: Apache-2.0
"""Bench-only USB serial control for the Home Bot Mega/PCA9685 sketch."""

import argparse
import time


class ProtocolError(RuntimeError):
    pass


class MegaPwm:
    def __init__(self, serial_port):
        self.port = serial_port

    def send(self, command):
        self.port.write((command + "\n").encode("ascii"))

    def wait_for(self, expected, seconds=1):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            response = self.port.readline().decode("ascii", errors="replace").strip()
            if response == expected:
                return response
            if response.startswith("ERR "):
                raise ProtocolError(response)
            if response == "STATUS FAULT":
                raise ProtocolError("shield I2C fault")
        raise ProtocolError(f"no {expected!r} response")

    def connect(self):
        # USB serial opening can reset a Mega. Wait for our versioned banner.
        self.wait_for("HOME_BOT_PWM 1", seconds=3)
        self.stop()

    def stop(self):
        self.send("STOP")
        return self.wait_for("OK STOP")

    def verify_off(self):
        self.send("STATUS")
        self.wait_for("STATUS OFF")
        self.send("VERIFY")
        return self.wait_for("PWM 0x40 121 FFFF")

    def pulse(self, milliseconds, channels):
        if not 20 <= milliseconds <= 1000 or not 1 <= len(channels) <= 2:
            raise ValueError("expected 20..1000 ms and one or two channels")
        if len({channel for channel, _ in channels}) != len(channels) or any(
            not 0 <= channel <= 15 or not 1400 <= width <= 1600 for channel, width in channels
        ):
            raise ValueError("use distinct channels 0..15 with nominal widths 1400..1600 us")
        self.send("ARM")
        self.wait_for("OK ARM")
        self.send(f"PULSE {milliseconds} " + " ".join(f"{channel} {width}" for channel, width in channels))
        self.wait_for("OK PULSE")
        self.wait_for("DONE OFF", seconds=milliseconds / 1000 + 1)
        return self.verify_off()


def channel_width(value):
    try:
        channel, width = map(int, value.split(":"))
        if 0 <= channel <= 15 and 1400 <= width <= 1600:
            return channel, width
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("expected CHANNEL:MICROSECONDS (0..15, 1400..1600)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="disable all outputs and verify the shield registers")
    pulse = commands.add_parser("pulse", help="move one or two confirmed channels for a bounded interval")
    pulse.add_argument("--ms", required=True, type=int)
    pulse.add_argument("--channel", required=True, action="append", type=channel_width)
    args = parser.parse_args()
    try:
        import serial
    except ImportError:
        parser.error("install pyserial (python -m pip install pyserial==3.5)")
    try:
        with serial.Serial(args.port, 115200, timeout=.1, write_timeout=.5) as port:
            robot = MegaPwm(port)
            robot.connect()
            try:
                if args.command == "pulse":
                    print(robot.pulse(args.ms, args.channel))
                else:
                    print(robot.verify_off())
            finally:
                robot.stop()
    except (ProtocolError, ValueError, serial.SerialException) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
