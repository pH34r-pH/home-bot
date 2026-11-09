# Mega and servo shield: first USB bench test

On November 9, 2026, the PC identified the Arduino Mega 2560 over USB serial.
The existing flash was read back before uploading the bench sketch. Arduino CLI
1.5.1 and Arduino AVR core 1.8.6 built and uploaded it. The USB camera came online
after reseating; a frame confirmed a usable view of the chassis.

The owner identified channels 0 (right wheel), 1 (left wheel), 2 (right side),
and 3 (left side). The setup was powered only through USB; there was no confirmed
separate servo V+ supply. The shield's red LED indicates logic power; its servo
rail is separate, as shown in the [Adafruit shield guide](https://learn.adafruit.com/adafruit-16-channel-pwm-slash-servo-shield/shield-connections).

| Physical bench check | Observed result |
| --- | --- |
| Serial startup and STOP | `HOME_BOT_PWM 1`, `OK STOP` |
| Shield register readback | `PWM 0x40 121 FFFF`: prescaler 121, all 16 off bits set |
| Disarmed, expired-arm, over-duration, over-width, duplicate-channel commands | Rejected; all 16 off bits verified after each |
| 250 ms, 1500 µs nominal pulse on unused channel 15 | `OK PULSE`, `STATUS ACTIVE`, then `DONE OFF` after 265 ms as observed by the PC; no intervening host STOP |
| After pulse and final stop | All 16 off bits verified, `OK STOP` |

The register and serial tests do not measure waveform timing or servo motion.
No connected servo was pulsed in this USB-only test. The 180° turn and side
servo movement still need servo power and camera-observed calibration. All
19 existing Python control/API tests passed separately. The camera images and
original flash backup were retained locally in ignored `artifacts/mega/`.

## Powered follow-up

The owner connected the separate servo supply at the shield and confirmed its
power indicator. Initial wheel pulses near the rug, including a reversed pair,
did not establish a controlled heading change. The owner observed that the
wheels spun but lacked their rubber traction bands. A clear, hands-off
camera comparison before and after a 1,000 ms opposite-width wheel command
(channel 0 at 1400 µs, channel 1 at 1600 µs) showed no resolvable chassis motion.
An image-plane fit using 100 matched chassis features estimated less than one
pixel of translation and less than one degree of yaw. That is a no-motion
observation, not a calibrated pose measurement.

To help isolate the command path, the firmware was updated to check oscillator
and output mode settings during `VERIFY`, and to read active PWM counts back
before acknowledging each pulse. The updated sketch compiled and was uploaded
to the same Mega. Both powered side servos were then tested independently with
the corresponding horn facing up and the wheel outputs off:

| Actuator | Commands (nominal pulse width, duration) | Camera observation |
| --- | --- | --- |
| Left side, continuous, channel 3 | 1600 µs for 750 ms | Horn visibly rotated during the command and was stationary in the post-command frames |
| Right side, standard, channel 2 | 1400 µs for 650 ms; then 1600 µs for 650 ms | Horn moved to distinct positions for the two targets |

No physical horn angles were inferred from the widths. All three tests ended
with the `FFFF` off-bit readback. Cropped frame sequences are local only under
`artifacts/mega/turn/`. The 180° chassis turn is pending fitted traction bands
and camera-observed wheel calibration. The side tests were run separately
because the turn could not be completed in this setup.
