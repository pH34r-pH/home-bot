# First model-piloted Webots experiment

Model: `gpt-6-luna`, a fresh subagent without the parent conversation. The human requested this model. Local robot software has no model API dependency; this run uses the existing agent session.

Task: find the orange upright rectangular object, approach without touching objects, stop with the base facing it, turn the phone screen toward it, and display `FOUND`.

The pilot gets the operator manual, local CLI, onboard camera, wheel/gimbal feedback, IMU and wheel odometry. No map, target coordinates, simulator truth, evaluator output or spectator view is provided. It may make at most 35 motion commands within about twelve minutes. No parent steering during the attempt. File access is restricted by instruction, not an operating-system sandbox.

The evaluator is a separate Supervisor; the robot remains a normal Webots Robot. Criteria fixed before the pilot begins:

- Robot center is 0.25–0.50 m from the target center in the floor plane.
- Base forward direction is within 20 degrees of the target.
- Phone pan is within 0.08 rad of pi, tilt within 0.10 rad of zero, and screen text is `FOUND`.
- Translation speed below 0.01 m/s, yaw speed below 0.05 rad/s, and base up-axis dot world-up above 0.95.
- No robot contact points above 0.015 m throughout the attempt (a collision proxy suitable for this flat test room; not a general collision classifier).
- All criteria hold together for at least one simulation second.

The evaluator records ground truth privately at roughly 0.25 s intervals and checks contact points each 16 ms physics step. The CLI records commands and paired observations. A failed attempt remains a failed attempt; retries must receive separate run identifiers and be reported separately.

This is a simple visible-target task in a synthetic room, not validation of unattended home operation, unseen-room navigation, Android integration or physical transfer. No object dimensions are supplied to the pilot for visual range estimation.

To reproduce, set `HOME_BOT_EXPERIMENT_DIR` to a fresh absolute directory outside the pilot's allowed observations, launch `sim/webots/worlds/pilot.wbt` in Webots with `--batch --mode=realtime --stdout --stderr`, then give a fresh pilot the manual and task. Reusing a directory is rejected so old logs and finish signals cannot contaminate a new attempt. To capture the final spectator image and end evaluation, the experiment operator creates `finish.request` in the evaluator directory after the pilot finishes. The simulation remains open.
