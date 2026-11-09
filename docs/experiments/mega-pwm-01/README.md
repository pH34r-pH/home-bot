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
