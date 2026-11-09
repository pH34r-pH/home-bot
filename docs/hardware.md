# Hardware profile and calibration

## Confirmed by the owner

| Part | Known information |
| --- | --- |
| Base | Parallax Boe-Bot chassis; original BASIC Stamp 2 replaced |
| Actuator controller | Arduino Mega |
| PWM shield | Adafruit 16-channel PCA9685 shield, I²C address `0x40` verified |
| Drive | Two Parallax continuous-rotation wheel servos |
| Speed | Owner estimates about 1 mph; not measured |
| Side actuators | Parallax standard servo on the right; Parallax continuous-rotation servo on the left |
| Brain/sensors | Google Pixel 5, upright portrait, rear cameras forward in driving pose |
| Display | Phone can turn to show its screen, expressions and text |
| Future | Multi-jointed arm with a claw/hand; plant watering and toy collection |

All four servos were purchased around 2014. Exact labels and external feedback
wiring are unverified. Earlier reports of feedback do not establish a readable
position signal; a standard servo's internal position control alone supplies no
measurement to the Mega.

| PCA9685 channel | Actuator | Command meaning |
| --- | --- | --- |
| 0 | Right wheel, continuous | Direction and speed |
| 1 | Left wheel, continuous | Direction and speed |
| 2 | Right side, standard | Position target |
| 3 | Left side, continuous | Direction and speed |

The era-appropriate candidates are Parallax [900-00008 continuous](https://www.mouser.com/datasheet/2/321/900-00008-Continuous-Rotation-Servo-Documentation--273045.pdf)
and [900-00005 analog standard](https://docs.rs-online.com/0e85/0900766b8123f8d7.pdf).
Both manufacturer guides specify 4–6 V and around 140 mA per servo moving without
load at 6 V. This is not a stall-current rating. A separate regulated 5 V supply
on shield V+ and GND is the bench starting point after checking the labels, with
the Mega on USB for serial. [Adafruit lists 5 V / 2 A as an example supply](https://learn.adafruit.com/adafruit-16-channel-pwm-slash-servo-shield/shield-connections);
check voltage under load and available current before relying on it. Do not bridge
V+ to the Mega's 5 V rail.

## Model parameters

Pixel's published bare-device dimensions are 144.7 × 70.4 × 8.0 mm, mass 151 g.
The prototype uses that envelope; the cradle and case are approximations.
Wheel radius 34 mm, track width 105 mm, base mass 450 g, wheel masses 25 g each,
and all gimbal dimensions are provisional. Base mass includes an approximate
battery/controller allowance, rather than the bare chassis mass.

`config/robot.json` supplies the speed and actuator settings to both generated
worlds. The 0.44704 m/s cap is the conversion of the owner's 1 mph estimate.
Interactive driving defaults to 0.12 m/s. Pan 0..π and tilt ±0.6 rad are simulated
design limits, not evidence of real travel. At pan zero the rear camera looks
along chassis +X; at pan π the screen faces chassis +X.

The model's gimbal uses positional rotary joints. A continuous servo cannot use
that same position interface without an external position measurement and control
loop. The eventual gimbal's actuator mapping, travel, cable clearance and ability
to present the screen are unverified.

## Measurements before physical control

1. Photograph/read each actuator label and trace its signal/feedback wires.
2. Measure wheel diameter, wheel center spacing, axle height and caster position.
3. Measure the gimbal joint axes, travel and phone position relative to each axis.
4. Weigh the assembled base, mount and phone/case; estimate their centers of mass.
5. Identify the existing servo power supply, voltage under load and available current.
6. Confirm each feedback signal type, voltage, scale, direction and wrap behavior.
7. Measure drive neutral/deadband, speed versus command, left/right differences,
   response delay and behavior on hard floor, rugs and thresholds.
8. Measure pan/tilt zero, direction, travel, backlash, settling and payload sag.
9. Read camera intrinsics at the chosen stream resolution and verify sensor timestamps.
10. Check sustained phone compute, camera operation, charging and USB connectivity.

The simulation currently models acceleration/torque limits and contact physics.
It does not yet model calibrated servo deadband, feedback quantization, battery
sag, rolling shutter, thermal throttling or Android lifecycle behavior.

## References

- [Google Pixel hardware specifications](https://support.google.com/pixelphone/answer/16043605)
- [Parallax chassis](https://www.parallax.com/product/small-robot-chassis/)
- [Pixel 5 ARCore/Depth support](https://developers.google.com/ar/devices)
- [ARCore depth behavior and limitations](https://developers.google.com/ar/develop/java/depth/developer-guide)
