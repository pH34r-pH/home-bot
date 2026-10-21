# Roadmap

## 0 — Simulator foundation (implemented)

- Original, configurable chassis + phone/gimbal model and a room with doorway.
- Wheel/gimbal feedback, portrait camera, Android-frame IMU and phone screen.
- Local manual control and a documented JSON command/observation contract.
- Command expiry, motion limits, unit/API tests and Webots maneuver checks.

## 1 — Calibrated hardware description

Identify all actuator models and feedback signals. Measure the wheelbase, gimbal,
phone/case and masses. Confirm 180° screen presentation is physically possible.
Replace the provisional dimensions/limits without relying on kit-era assumptions.
Model servo deadband, delay, left/right variation and feedback noise from measured
data. Keep the initial house environment simple and dimensionally useful.

Exit: a hardware profile with sources or measurements for each key parameter,
plus tests that still pass with realistic variation.

## 2 — Pixel brain connected to simulation

Build a native Android app with interchangeable simulated/real sensor sources and
actuator sinks. Implement local network pairing to a desktop bridge, then run the
same behavior on the actual phone while Webots supplies virtual observations.
Add native facial expressions/text using the same expression vocabulary. Check
on-phone latency and sustained compute before selecting perception models.

Exit: the Pixel drives, looks around and changes its simulated screen state;
disconnecting its bridge stops motion. ARCore itself is tested separately on-device.

## 3 — Single-room inspection

Implement frame transforms and wheel odometry fusion. Start with stationary
camera scans and forward-facing driving. Add obstacle detection and a local map,
then an inspection waypoint task. Test sensor loss, blocked paths, shifted objects,
lighting changes and command delays without simulator truth in the controller.

Exit: repeatedly drive to an inspection point, stop, scan/capture, and return,
with logged success/failure measures rather than a single successful demonstration.

## 4 — Physical Mega adapter and calibration

Implement verified actuator control and feedback decoding, independent command
expiry, stop/arm behavior and the chosen phone link. Bench-test with drive wheels
unloaded, then calibrate against real floor motion. Feed measurements back into
the model, followed by supervised room trials.

Exit: the same task logic runs through either adapter with measured differences,
and tracking/link/feedback failures result in a controlled stop.

## 5 — House inspection

Build a measured floorplan, room transitions, rug/threshold cases and restricted
regions. Add return-to-home behavior, battery/runtime handling, remote viewing and
recovery. Validate the Android camera/service lifecycle and startup. Progress to
unattended operation only after repeated supervised trials and failure tests.

## 6 — Arm and gripper

Simulate mounting, reach, payload, tipping margin, joint torque, self-collision and
grasping. Reassess the base if the required arm/payload exceeds its capacity.
Start with lightweight dry objects before tasks involving water. Evaluate whether
contact-heavy manipulation needs an additional MuJoCo-based test environment.
