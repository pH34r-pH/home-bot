# SPDX-License-Identifier: Apache-2.0
"""The Webots adapter; simulator truth is available only to the smoke evaluator."""

from dataclasses import asdict
import json
import math
from pathlib import Path
import time

from .config import RobotConfig
from .control import Command, CommandLatch, Odometry, wheel_speeds
from .face import draw_face
from .geometry import look_at
from .png import bgra_to_png
from .server import Mailbox, start_server


def finite(values):
    return [float(value) if math.isfinite(value) else 0.0 for value in values]


class SmokeEvaluator:
    """Closed, deterministic maneuver sequence, with no truth given to navigation."""

    def __init__(self, robot, root: Path, config: RobotConfig):
        self.robot, self.config = robot, config
        self.path = root / "artifacts"
        self.path.mkdir(exist_ok=True)
        self.samples = {}

    def command(self, t):
        if t < 1:
            return Command()
        if t < 3:
            return Command(linear_mps=0.12, text="DRIVING")
        if t < 4:
            return Command(angular_rps=1.0, text="TURNING")
        if t < 7.5:
            return Command(pan_rad=math.pi, expression="happy", text="HELLO HOME")
        if t < 9:
            return Command(pan_rad=math.pi, tilt_rad=0.35, expression="curious", text="LOOKING UP")
        if t < 9.5:
            return Command(linear_mps=0.06, pan_rad=math.pi, tilt_rad=0.35, expression="happy", text="HELLO HOME")
        return None

    def observe(self, state, camera):
        t = state["sim_time_s"]
        for name, when in (("settled", 0.95), ("straight", 2.95), ("turned", 3.95),
                           ("face", 7.45), ("tilt", 8.95), ("moving", 9.45), ("stopped", 10.9)):
            if t >= when and name not in self.samples:
                self.samples[name] = {**state, "truth_position": list(self.robot.getSelf().getPosition())}
                if name == "settled":
                    camera.saveImage(str(self.path / "camera-forward.png"), 100)
                    frame = camera.getImage()
                    pixel = (camera.getHeight() // 2 * camera.getWidth() + camera.getWidth() // 2) * 4
                    self.samples[name]["center_rgb"] = [frame[pixel + 2], frame[pixel + 1], frame[pixel]]

    def finish(self, camera, display):
        a, b = self.samples["settled"], self.samples["straight"]
        stopped = self.samples["stopped"]
        png_path = self.path / "rear-camera.png"
        camera.saveImage(str(png_path), 100)
        image = display.imageCopy(0, 0, display.getWidth(), display.getHeight())
        display.imageSave(image, str(self.path / "phone-screen.png"))
        display.imageDelete(image)
        point = self.robot.getSelf().getPosition()
        position = [point[0] + 0.6, point[1] + 0.8, 0.55]
        viewpoint = self.robot.getFromDef("INSPECTION_VIEW")
        viewpoint.getField("position").setSFVec3f(position)
        viewpoint.getField("orientation").setSFRotation(look_at(position, [point[0], point[1], 0.15]))
        self.robot.step(int(self.robot.getBasicTimeStep()))
        self.robot.exportImage(str(self.path / "simulation.png"), 100)
        forward = b["truth_position"][0] - a["truth_position"][0]
        yaw = self.samples["turned"]["odometry"]["yaw_rad"] - b["odometry"]["yaw_rad"]
        checks = {
            "forward_motion": forward > 0.12,
            "forward_tracks_odometry": abs(forward - (b["odometry"]["x_m"] - a["odometry"]["x_m"])) < 0.06,
            "turn_feedback": yaw > 0.45,
            "pan_half_turn": abs(self.samples["face"]["gimbal_rad"][0] - math.pi) < 0.08,
            "tilt_feedback": abs(self.samples["tilt"]["gimbal_rad"][1] - 0.35) < 0.10,
            "face_expression": self.samples["face"]["applied_command"]["expression"] == "happy",
            "watchdog_expired": stopped["watchdog_expired"],
            "watchdog_zero_command": stopped["applied_wheel_rad_s"] == [0.0, 0.0],
            "wheel_motion_stopped": max(abs(x) for x in stopped["wheel_velocity_rad_s"]) < 0.2,
            "camera_frame_saved": png_path.exists() and png_path.stat().st_size > 200,
            "base_upright": all(abs(s["truth_position"][2] - self.config.wheel_radius_m) < 0.015 for s in self.samples.values()),
            "camera_faces_forward_target": a["center_rgb"][0] > 1.5 * a["center_rgb"][1] and a["center_rgb"][0] > 1.8 * a["center_rgb"][2],
            "android_imu_upright": abs(a["phone_accelerometer_mps2"][1] - 9.81) < 0.3 and abs(a["phone_accelerometer_mps2"][2]) < 0.3,
        }
        report = {"passed": all(checks.values()), "checks": checks, "samples": self.samples}
        (self.path / "smoke-report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print("HOME_BOT_SMOKE " + json.dumps(checks), flush=True)
        self.robot.simulationQuit(0 if report["passed"] else 1)


def run(root: Path, smoke=False):
    # Import only inside the adapter so core modules can be tested without Webots.
    from controller import Keyboard, Robot, Supervisor

    config = RobotConfig.load(root / "config/robot.json")
    robot = Supervisor() if smoke else Robot()
    step = int(robot.getBasicTimeStep())
    wheels = [robot.getDevice(name) for name in ("left_wheel", "right_wheel")]
    gimbal = [robot.getDevice(name) for name in ("pan", "tilt")]
    feedback = [robot.getDevice(name) for name in ("left_wheel_feedback", "right_wheel_feedback", "pan_feedback", "tilt_feedback")]
    accel, gyro = [robot.getDevice(name) for name in ("phone_accelerometer", "phone_gyro")]
    camera, display = [robot.getDevice(name) for name in ("rear_camera", "phone_screen")]
    for motor in wheels:
        motor.setPosition(float("inf"))
        motor.setVelocity(0)
    for sensor in (*feedback, accel, gyro):
        sensor.enable(step)
    camera_period = math.ceil(config.camera_period_ms / step) * step
    camera.enable(camera_period)
    keyboard = robot.getKeyboard()
    keyboard.enable(step)
    latch = CommandLatch(config.command_ttl_ms)
    odometry = Odometry()
    mailbox = Mailbox()
    server = None if smoke else start_server(mailbox, config)
    evaluator = SmokeEvaluator(robot, root, config) if smoke else None
    previous_wheels = None
    previous_face = None
    iteration = 0
    print(f"Home Bot ready. Operator panel: http://{config.http_host}:{config.http_port}", flush=True)
    print("Keyboard (3D view focused): W/S drive, A/D turn, X stop, F face, C camera, H happy", flush=True)
    try:
        while robot.step(step) != -1:
            iteration += 1
            t, wall = robot.getTime(), time.monotonic()
            if evaluator:
                command = evaluator.command(t)
                if command:
                    latch.accept(command, t, wall)
            else:
                pending = mailbox.take()
                if pending:
                    latch.accept(pending[0], t, pending[1])
                key = keyboard.getKey()
                latest_key = key
                while key != -1:
                    latest_key, key = key, keyboard.getKey()
                if latest_key != -1:
                    key = latest_key & 0xFFFF
                    current = asdict(latch.command)
                    current.update(version=1, linear_mps=0.0, angular_rps=0.0)
                    drive = {ord("W"): (0.12, 0), ord("S"): (-0.12, 0), ord("A"): (0, 1), ord("D"): (0, -1), ord("X"): (0, 0)}
                    if key in drive:
                        current["linear_mps"], current["angular_rps"] = drive[key]
                    elif key == ord("F"):
                        current.update(pan_rad=config.pan_max_rad, expression="happy", text="HELLO HOME")
                    elif key == ord("C"):
                        current.update(pan_rad=0.0, tilt_rad=0.0)
                    elif key == ord("H"):
                        current.update(expression="happy", text="HELLO")
                    if key in drive or key in (ord("F"), ord("C"), ord("H")):
                        latch.accept(Command.parse(current, config), t, wall)
            applied, expired = latch.sample(t, wall)
            speeds = wheel_speeds(applied, config)
            for motor, velocity in zip(wheels, speeds):
                motor.setVelocity(velocity)
            for motor, angle in zip(gimbal, (applied.pan_rad, applied.tilt_rad)):
                motor.setPosition(angle)
            face = (applied.expression, applied.text)
            if face != previous_face:
                draw_face(display, *face)
                previous_face = face
            positions = finite(sensor.getValue() for sensor in feedback)
            odometry.update(*positions[:2], config)
            velocity = [0.0, 0.0] if previous_wheels is None else [(p - old) / (step / 1000) for p, old in zip(positions[:2], previous_wheels)]
            previous_wheels = positions[:2]
            frame = None
            if iteration % (camera_period // step) == 0:
                bgra = camera.getImage()
                if bgra:
                    frame = bgra_to_png(bgra, camera.getWidth(), camera.getHeight())
            state = {
                "version": 1, "status": "running", "sim_time_s": t,
                "wheels_rad": positions[:2], "wheel_velocity_rad_s": finite(velocity),
                "gimbal_rad": positions[2:],
                "phone_accelerometer_mps2": finite(accel.getValues()),
                "phone_gyro_rps": finite(gyro.getValues()),
                "imu_frame": "android_device_x_screen_right_y_up_z_out_of_screen",
                "odometry": {"x_m": odometry.x_m, "y_m": odometry.y_m, "yaw_rad": odometry.yaw_rad},
                "applied_command": asdict(applied), "applied_wheel_rad_s": list(speeds),
                "watchdog_expired": expired,
            }
            mailbox.publish(state, frame)
            if evaluator:
                evaluator.observe(state, camera)
                if t >= 11:
                    evaluator.finish(camera, display)
                    break
    finally:
        if server:
            server.shutdown()
            server.server_close()
