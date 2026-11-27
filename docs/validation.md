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

## Replayable smoke evidence

From a Git checkout, pass a fresh output directory or use the automatically
created directory printed by the runner.

```sh
python scripts/run_smoke.py --webots /path/to/webots --output artifacts/smoke-attempt-01
python scripts/run_smoke.py --replay artifacts/smoke-attempt-01
```

- `smoke-receipt.json` records the Git commit and working-tree state, input and
  output SHA-256 values, Webots version and launcher digest, runner and controller
  Python versions, world seed and step size, evaluator result, and replay result.
- `smoke-trace.jsonl` records accepted commands and controller observations at
  each step. The replay recomputes watchdog expiry, applied commands, wheel
  targets and wheel odometry using the recorded simulation and monotonic clocks
  and the wheel feedback.
- `smoke-report.json` contains the evaluator-only poses, terminal state and
  checks. The captured images are separate artifacts. The smoke run has no
  operator API, and evaluator truth stays out of the controller observation trace.
- The runner retains any partial outputs and the process log when a launched
  attempt fails or times out. Offline replay requires a passing receipt, the same
  source inputs, and all recorded artifacts with matching digests.

Offline replay checks recorded controller behavior. A fresh Webots run exercises
the physics, rendered camera and independent evaluator. Webots evidence applies
to simulation. Hardware-in-loop and physical acceptance require their own
measured calibration, actuator permits, independent stop paths and test receipts.

## Compare two retained pilot attempts

Keep each completed bundle, its attempt ID, and its checked receipt digest in
the evidence store. Use the checkout with the input files recorded by both
receipts and keep the bundle directories stable during verification.
[Pilot recording and replay](experiment-protocol.md#record-a-repeatable-simulation-attempt)

```sh
python scripts/compare_pilots.py artifacts/reference artifacts/candidate \
  --reference-receipt-sha256 "$REFERENCE_RECEIPT_SHA256" \
  --candidate-receipt-sha256 "$CANDIDATE_RECEIPT_SHA256"
```

The command replays both independently pinned bundles and records their
runtime identities, evaluator outcomes, and separate digests for the pilot
and evaluator files. It compares the requested actions, the controller's
applied commands and watchdog state at each step, and the evaluator's
sampling grid. The report includes maximum position and wrapped heading
deltas when all three align. Keep both outcomes and the alignment result
when the runs differ.

Use the same scripted actions and unchanged world, seed, and controller
when comparing simulator environments. Record any changed timing or
controls before interpreting the pose results. A completed recording with
a failed mission remains a valid negative outcome. Retain a timeout or
interruption with its original receipt and select two completed recordings
for the comparison. Physical calibration and operating approval require
their own evidence.
