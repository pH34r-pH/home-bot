# Mega USB serial bench control

`mega_pwm/mega_pwm.ino` is a bounded USB serial test for an Arduino Mega 2560
with the Adafruit 16-channel PCA9685 PWM/servo shield. It uses `Wire` at the
shield's default address `0x40`, and the AVR core has no extra library dependency.
The separate [servo V+ supply](https://learn.adafruit.com/adafruit-16-channel-pwm-slash-servo-shield/shield-connections)
must match the actual servos. USB and the shield's red logic LED do not establish
that servo power is present. The shield supplies PWM; it does not read feedback.

With Arduino CLI and the Arduino AVR core installed:

```sh
arduino-cli core install arduino:avr@1.8.6
arduino-cli compile --fqbn arduino:avr:mega:cpu=atmega2560 firmware/mega_pwm
arduino-cli upload --port COM4 --fqbn arduino:avr:mega:cpu=atmega2560 firmware/mega_pwm
python -m pip install pyserial==3.5
python scripts/mega_pwm.py --port COM4 status
```

Substitute the actual port. `status` sends `STOP` and reads the prescaler and all
16 channel off bits back from the chip; `PWM 0x40 121 FFFF` is the expected result.
The sketch opens at 115200 baud, 8N1. Commands and replies are ASCII lines.

| Command | Result |
| --- | --- |
| `HELLO` | `HOME_BOT_PWM 1` (also printed on boot) |
| `STATUS` | `STATUS OFF`, `STATUS ARMED`, `STATUS ACTIVE` or `STATUS FAULT` |
| `VERIFY` | When disarmed, verify prescale 121 and all 16 off bits |
| `ARM` | Authorize one pulse command, expiring after 2 seconds |
| `PULSE <ms> <channel> <us> [<channel> <us>]` | One or two distinct channels; `OK PULSE`, then `DONE OFF` |
| `STOP` | Clear arming and disable all outputs; `OK STOP` on successful I²C write |

The bench bounds are 20–1000 ms, channels 0–15, and nominal pulses 1400–1600 µs at
approximately 50 Hz. These are command limits, not measured neutral, angle, or
mechanical limits. Pulse width is quantized to PCA9685 ticks and depends on its
oscillator. Use `scripts/mega_pwm.py --port COM4 pulse --ms MS --channel CH:US`
with a confirmed channel and safe width; repeat `--channel` to address the second
servo in the same interval. The CLI checks the end of the pulse and reads back
the off bits. There are no default actuator channels or angle-to-time conversion.

Startup, STOP, malformed input and the pulse deadline disable PWM. An I²C failure
latches a fault and retries disabling outputs. The PCA9685 generates PWM on its
own, so a failed Mega or bus can prevent a software stop; keep servo power within
reach when testing. PWM-off is signal removal; braking, holding and neutral
behavior still need to be verified on the connected servos.

Confirm servo power, connector mapping, wheel polarity, side servo safe travel,
and cable slack before motion. Use short camera-observed wheel pulses to measure
turn direction and speed. A 180° chassis turn (π radians) needs measured heading;
it does not follow from any particular PWM value or elapsed time. Move the side
servos only after the wheels are off: channel 2 (right, standard) takes a safe
position target; channel 3 (left, continuous) takes a brief speed command. Equal
pulse widths do not imply equal angles. Keep this USB bench interface separate
from the future Pixel-to-Mega transport and feedback protocol.

See the [physical bench results](../docs/experiments/mega-pwm-01/README.md) for
readback, rejected-command tests, an unloaded channel pulse, and the owner-confirmed
channel map. The USB-only setup did not establish servo power or motion.
