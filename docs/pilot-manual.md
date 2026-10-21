# Home Bot operator manual

The robot is a slow differential-drive base carrying a portrait phone on a pan/tilt head. Operate it through the local CLI; no pip packages, model API keys, or network service are needed. This interface contains no route planner or object detector.

Run commands from the repository root with Python. Use the same `--run-dir` for every command in an attempt:

```powershell
python scripts/robot.py --run-dir artifacts/luna-pilot-01 observe
python scripts/robot.py --run-dir artifacts/luna-pilot-01 drive --linear 0.04 --seconds 2
python scripts/robot.py --run-dir artifacts/luna-pilot-01 drive --angular 0.4 --seconds 1
python scripts/robot.py --run-dir artifacts/luna-pilot-01 look --pan 0 --tilt 0
python scripts/robot.py --run-dir artifacts/luna-pilot-01 face --expression happy --text FOUND
python scripts/robot.py --run-dir artifacts/luna-pilot-01 stop
```

Every command saves an onboard camera PNG and matching sensor JSON and prints their absolute paths. Open the PNG to see; the JSON alone does not describe the scene. Images are 160x240 pixels. Image and feedback are sampled together every 128 ms. Files and actions are recorded in `pilot.jsonl`.

Positive linear velocity goes forward; positive angular velocity turns left. Units are meters/second and radians/second. CLI limits are 0.08 m/s, 0.7 rad/s and five wall seconds per movement. Use small movements near obstacles. A local timer refreshes commands during the requested duration, then stops the wheels. The robot also stops on a 400 ms command timeout; gimbal targets and screen content persist. Wheel acceleration and slip affect the actual motion. Compare the resulting feedback after each action. Webots runs in realtime, but motion uses simulation time while the CLI timer uses wall time; inspect the measured result rather than assuming exact distances.

The camera is on the head. Pan zero points the rear camera along the chassis forward direction. Pan pi (3.14159) turns the phone halfway around: the screen then faces chassis-forward and the camera looks behind the robot. Intermediate positive pan angles look left. Tilt ranges from -0.6 to +0.6 radians; positive looks up. Pan ranges from zero to pi. Gimbal feedback is measured joint position, not instantaneous target arrival.

Wheel odometry starts at (0,0,0), with initial forward +x and left +y. It is inferred from wheel rotation, not a map or GPS. Positive yaw turns left. Wheel angles are radians, wheel radius 0.034 m and track width 0.105 m. IMU axes follow Android: x screen-right, y screen-up, z out of the screen. The robot has no depth sensor, obstacle distance tool, global localization or autonomous navigation.

Keep the robot clear of objects. You can inspect the camera, reposition the base, move the head, and set expressions/text. Observe, decide, act briefly, then observe again. Any task completion claim should refer to the images and feedback you actually received.
