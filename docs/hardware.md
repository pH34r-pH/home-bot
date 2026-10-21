# Hardware profile and calibration

## Confirmed by the owner

| Part | Known information |
| --- | --- |
| Base | Parallax Boe-Bot chassis; original BASIC Stamp 2 replaced |
| Actuator controller | Arduino Mega |
| Drive | Two matched continuous-rotation wheel servos, position feedback reported |
| Speed | Owner estimates about 1 mph; not measured |
| Gimbal | Two similarly sized/voltage feedback actuators, described as “stepper-servos”; existing plate formerly carried ultrasonic sensors |
| Brain/sensors | Google Pixel 5, upright portrait, rear cameras forward in driving pose |
| Display | Phone can turn to show its screen, expressions and text |
| Future | Multi-jointed arm with a claw/hand; plant watering and toy collection |

Original kit membership alone does not establish the servo model. Honor the
reported feedback capability while leaving the signal type and calibration open.
Do not assume feedback is directly readable through the stock Arduino Servo library.

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

The physical ability to make a half-turn depends on servo travel, the mounting
angle, cable routing and clearance. Feedback does not establish the travel range.
The model's gimbal uses positional rotary joints without choosing whether the
actual hardware is a hobby servo or a stepper assembly.

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
