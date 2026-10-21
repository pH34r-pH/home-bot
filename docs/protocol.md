# Simulation API v1

Base URL: `http://127.0.0.1:8765`. Local development only; no LAN pairing or
authentication. The HTTP API is a simulation transport, not a specification for
electrical servo pulses or a finalized Mega serial protocol.

## Commands

`POST /api/command` with `Content-Type: application/json`:

```json
{
  "version": 1,
  "linear_mps": 0.12,
  "angular_rps": 0.0,
  "pan_rad": 0.0,
  "tilt_rad": 0.0,
  "expression": "happy",
  "text": "HELLO HOME",
  "ttl_ms": 400
}
```

`version` is required and must be integer 1. Every command is a complete snapshot;
omitted velocity, pan and tilt fields are zero. Expression defaults to `neutral`,
text to `HELLO`, and TTL to the configured default. A successful request returns
HTTP 202 with the validated command under `accepted`. Application happens on the
next simulation step, so acceptance is not an acknowledgement from physical motors.

| Field | Units / meaning | Current bounds |
| --- | --- | --- |
| `linear_mps` | Forward chassis speed, meters/second | ±0.44704 |
| `angular_rps` | Left-turn yaw rate, radians/second | ±3 |
| `pan_rad` | Left rotation about pan axis | 0..π |
| `tilt_rad` | Camera-up tilt | -0.6..0.6 |
| `expression` | Screen appearance | `neutral`, `happy`, `curious`, `sleepy` |
| `text` | Screen message | ≤48 printable ASCII characters |
| `ttl_ms` | Motion command lifetime | Integer 50..1000 ms |

All numeric values must be finite; booleans and unknown fields are rejected.
Out-of-range values return HTTP 400. Invalid commands never refresh the watchdog.
Text/expression-only commands stop the wheels because omitted motion is zero.
Gimbal/screen updates should include their desired full state.

Positive wheel speeds roll the robot forward:

```text
left_rad_s  = (linear_mps - angular_rps * track_width_m / 2) / wheel_radius_m
right_rad_s = (linear_mps + angular_rps * track_width_m / 2) / wheel_radius_m
```

If a combined command would exceed a wheel limit, both wheel speeds are scaled
by the same factor to preserve turning curvature. Motor acceleration/torque limits
also apply, so feedback can lag targets. HTTP receipt time is monotonic real time;
the controller separately starts a simulation-time expiry when consuming the queue.
Either expiry stops wheel targets. Send held-drive commands every 100 ms in real
time mode; expiry is not extended by telemetry reads.

## Observations

`GET /api/state` returns:

- `version`, `status` and `sim_time_s`.
- `wheels_rad`: continuous unwrapped simulated joint angles `[left, right]`.
- `wheel_velocity_rad_s`: rates calculated from consecutive feedback samples.
- `gimbal_rad`: measured `[pan, tilt]` joint positions.
- `phone_accelerometer_mps2` and `phone_gyro_rps`, in Android device axes.
- `imu_frame`: `android_device_x_screen_right_y_up_z_out_of_screen`.
- `odometry`: wheel-only `x_m`, `y_m`, `yaw_rad`, relative to startup.
- `applied_command`, `applied_wheel_rad_s`, and `watchdog_expired`.

The current simulated feedback is ideal joint feedback. Quantization, wrap
decoding and signal faults will be added after the physical feedback is identified.
Webots accelerometer samples include gravity as proper acceleration; this is not
Android's gravity-removed linear acceleration signal.

`GET /api/camera.png` returns the latest rear camera frame as PNG (503 until the
first frame is ready). Image size, horizontal FOV and sample period are configured
in `config/robot.json`. Camera output is downsampled portrait imagery and is not
the Pixel camera HAL or an ARCore emulation. No depth or world pose is supplied.

`GET /api/observation` returns `{ "state": {...}, "camera_png_base64": "..." }`.
The state is sampled on the controller step that publishes that camera frame;
later telemetry updates do not replace its state without a new frame. It returns
503 until a frame is ready. The camera samples every configured whole number of
physics steps (128 ms by default). Use this paired endpoint for model observations
rather than separately fetching a moving image and current telemetry.

`scripts/robot.py` provides a local operator CLI over these same endpoints. It
retains the current gimbal/screen state, applies narrower experiment speed limits,
refreshes a bounded drive command locally, and attempts an explicit stop in a
`finally` block. If the connection is unavailable, the controller watchdog remains
the fallback. Local action and image logs go to its `--run-dir`. This CLI is a
transport helper, not a navigation controller.

## Browser behavior

The panel sends commands only on interaction or while a drive button is held.
Pointer release/cancel, losing browser focus, or hiding the tab requests a stop;
the watchdog handles lost requests. Pan presets stop driving before moving the
gimbal. The API has no multi-client arbitration; the latest valid command wins.
It rejects browser POSTs from unrelated origins and serves only fixed asset paths.
