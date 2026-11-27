# SPDX-License-Identifier: Apache-2.0
"""Compare two independently pinned and replayed Webots pilot attempts."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from uuid import UUID

from run_pilot import RECEIPT, json_lines, verify_bundle


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def control_fingerprint(path):
    digest = hashlib.sha256()
    for row in json_lines(path):
        state = row["observation"]
        digest.update(canonical([row["step"], state["applied_command"], state["watchdog_expired"]]) + b"\n")
    return digest.hexdigest()


def verified_attempt(directory, expected_sha256):
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("expected an independently retained receipt SHA-256")
    path = directory / RECEIPT
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("pilot receipt differs from its expected SHA-256")
    receipt = json.loads(raw)
    attempt_id = receipt["attempt_id"]
    if (not isinstance(attempt_id, str) or str(UUID(attempt_id)) != attempt_id
            or receipt["source_dirty"] is not False
            or not re.fullmatch(r"[0-9a-f]{40}", receipt["source_commit"])):
        raise ValueError("comparison requires a clean, identified source attempt")

    replay = verify_bundle(directory)
    if path.read_bytes() != raw:
        raise ValueError("pilot receipt changed during replay")
    pilot = directory / "pilot"
    evaluator = directory / "evaluator"
    actions = [
        [row["action"], row["duration_wall_s"], row["command"]]
        for row in json_lines(pilot / "pilot.jsonl") if row["event"] == "action_start"
    ]
    outputs = receipt["outputs_sha256"]
    groups = {
        group: fingerprint({name: digest for name, digest in outputs.items() if name.startswith(group + "/")})
        for group in ("pilot", "evaluator")
    }
    summary = {
        "attempt_id": attempt_id,
        "receipt_sha256": expected_sha256,
        "source_commit": receipt["source_commit"],
        "input_inventory_sha256": fingerprint(receipt["inputs_sha256"]),
        "world": receipt["world"],
        "runtime": receipt["runtime"],
        "pilot_outputs_sha256": groups["pilot"],
        "evaluator_outputs_sha256": groups["evaluator"],
        "requested_actions_sha256": fingerprint(actions),
        "applied_controls_sha256": control_fingerprint(evaluator / "pilot-motion.jsonl"),
        "replay": replay,
    }
    return summary, list(json_lines(evaluator / "evaluation.jsonl"))


def pose_discrepancy(reference, candidate):
    """Compute observed deltas on the same evaluator sampling grid."""
    return {
        "samples": len(reference),
        "max_position_delta_m": max(
            math.dist(left["truth_position_m"], right["truth_position_m"])
            for left, right in zip(reference, candidate, strict=True)
        ),
        "max_heading_delta_rad": max(
            abs(math.remainder(right["truth_yaw_rad"] - left["truth_yaw_rad"], math.tau))
            for left, right in zip(reference, candidate, strict=True)
        ),
    }


def comparison(reference, candidate):
    left, left_samples = reference
    right, right_samples = candidate
    if left["attempt_id"] == right["attempt_id"]:
        raise ValueError("comparison requires two distinct attempts")
    left_grid = [row["sim_time_s"] for row in left_samples]
    right_grid = [row["sim_time_s"] for row in right_samples]
    paired = {
        "requested_actions_match": left["requested_actions_sha256"] == right["requested_actions_sha256"],
        "applied_controls_match": left["applied_controls_sha256"] == right["applied_controls_sha256"],
        "evaluator_steps_match": left_grid == right_grid,
    }
    return {
        "schema_version": 1,
        "kind": "webots_pilot_comparison",
        "scope": "simulation_only",
        "reference": left,
        "candidate": right,
        "runtime_differences": sorted(
            key for key in left["runtime"].keys() | right["runtime"].keys()
            if left["runtime"].get(key) != right["runtime"].get(key)
        ),
        "alignment": paired,
        "pose_discrepancy": pose_discrepancy(left_samples, right_samples) if all(paired.values()) else None,
        "physical_qualification": "pending",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--reference-receipt-sha256", required=True)
    parser.add_argument("--candidate-receipt-sha256", required=True)
    args = parser.parse_args()
    try:
        reference = verified_attempt(args.reference, args.reference_receipt_sha256)
        candidate = verified_attempt(args.candidate, args.candidate_receipt_sha256)
        sys.stdout.buffer.write(canonical(comparison(reference, candidate)) + b"\n")
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        parser.exit(1, f"pilot comparison failed ({exc})\n")


if __name__ == "__main__":
    main()
