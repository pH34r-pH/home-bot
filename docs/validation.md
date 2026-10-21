# Initial validation

Validated locally on Windows with Python 3.12 and Webots R2025a.

- 13 unit/API tests passed: malformed and out-of-range commands; complete-command
  behavior; curvature-preserving speed saturation; simulation/real-time command
  expiry; stale command handling; straight, rotational and curved wheel odometry;
  BGRA-to-PNG encoding; HTTP command receipt; invalid-input and cross-origin
  rejection; telemetry/static routes.
- Webots integration passed 13 checks: forward motion; forward odometry agreement;
  turn feedback; a half-turn of the pan stage; tilt feedback; happy expression state;
  watchdog expiry; zero wheel targets after expiry; measured wheel stop; saved
  camera output; upright base; forward camera target; Android portrait IMU axes.
- The running HTTP API drove the actual Webots model, delivered wheel telemetry,
  and stopped wheel motion after requests ceased.
- Browser verification confirmed camera output, measured 180° pan, expression
  selection and text entry against the running simulator. The generated robot
  screenshot was visually inspected for portrait mounting and readable screen UI.

Run commands are in the [README](../README.md). Full maneuver reports and images
are generated into ignored `artifacts/`; the illustrative screenshot under
`docs/images/` is produced from the real simulation, not a concept render.

These checks cover the provisional model and local control interface. They do not
validate measured servo dynamics, real feedback signals, Android/ARCore, Mega
firmware, navigation, lifting capacity, or unattended physical operation.
