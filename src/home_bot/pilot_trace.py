# SPDX-License-Identifier: Apache-2.0
"""Re-evaluate the pilot mission from evaluator-owned simulator samples."""

import json
import math

SAMPLE_PERIOD_S = .25
TARGET_POSITION_M = (1.5, 0.0, .16)


def finite_number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("pilot evidence requires finite numbers")
    return value


class PilotEvaluation:
    def __init__(self, step_ms):
        self.step_s = step_ms / 1000
        self.previous_time = None
        self.dwell_start = None
        self.achieved = False

    def observe(self, sample):
        t = finite_number(sample["sim_time_s"])
        if self.previous_time is not None:
            gap = t - self.previous_time
            if gap <= 0:
                raise ValueError("evaluation time must increase")
            if gap > SAMPLE_PERIOD_S + self.step_s + 1e-9:
                self.dwell_start = None
        self.previous_time = t
        state = sample["sensor_state"]
        sensor_time = finite_number(state["sim_time_s"])
        x, y, _ = map(finite_number, sample["truth_position_m"])
        yaw = finite_number(sample["truth_yaw_rad"])
        dx, dy = TARGET_POSITION_M[0] - x, TARGET_POSITION_M[1] - y
        distance = math.hypot(dx, dy)
        delta = math.atan2(dy, dx) - yaw
        heading = math.atan2(math.sin(delta), math.cos(delta))
        vx, vy, _, _, _, yaw_speed = map(finite_number, sample["truth_velocity"])
        pan, tilt = map(finite_number, state["gimbal_rad"])
        checks = {
            "fresh_sensor_state": 0 <= t - sensor_time <= 2 * self.step_s + 1e-9,
            "near_target": .25 <= distance <= .50,
            "base_faces_target": abs(heading) <= math.radians(20),
            "screen_faces_forward": abs(pan - math.pi) < .08 and abs(tilt) < .10,
            "screen_says_found": state["applied_command"]["text"] == "FOUND",
            "stopped": math.hypot(vx, vy) < .01 and abs(yaw_speed) < .05,
            "upright": finite_number(sample["truth_up_axis"]) > .95,
            "no_above_floor_contacts": not sample["above_floor_contact_events"],
        }
        if all(checks.values()):
            self.dwell_start = t if self.dwell_start is None else self.dwell_start
            self.achieved |= t - self.dwell_start >= 1
        else:
            self.dwell_start = None
        self.achieved &= checks["no_above_floor_contacts"]
        return {"task_achieved": self.achieved, "criteria": checks,
                "target_distance_m": distance, "heading_error_rad": heading}


def replay_evaluation(path, step_ms):
    evaluation = PilotEvaluation(step_ms)
    count = 0
    last = None
    previous_contacts = []
    with path.open(encoding="utf-8") as stream:
        for count, line in enumerate(stream, 1):
            row = json.loads(line)
            contacts = row["above_floor_contact_events"]
            if contacts[:len(previous_contacts)] != previous_contacts:
                raise ValueError(f"pilot sample {count}: contact history changed")
            if any(contact["sim_time_s"] > row["sim_time_s"] for contact in contacts):
                raise ValueError(f"pilot sample {count}: future contact in history")
            previous_contacts = contacts
            expected = evaluation.observe(row)
            if any(value != row[key] for key, value in expected.items()):
                raise ValueError(f"pilot sample {count}: recorded predicate differs from replay")
            last = row
    if last is None:
        raise ValueError("pilot evaluator trace is empty")
    return {"samples": count, "terminal_sim_time_s": last["sim_time_s"],
            "task_achieved": evaluation.achieved, "terminal_criteria": last["criteria"],
            "contact_events": len(last["above_floor_contact_events"])}
