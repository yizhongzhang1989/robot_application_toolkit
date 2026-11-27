"""Read-only API contract checks, usable without ROS or vendor packages."""

import argparse
import json
import math
from pathlib import Path

from .client import RobotClient


def finite_vector(value, size):
    return (
        isinstance(value, list)
        and len(value) == size
        and all(type(v) in (int, float) and math.isfinite(v) for v in value)
    )


def validate_snapshot(info, state):
    errors = []
    if not isinstance(info, dict) or not isinstance(state, dict):
        return ["info and state must be objects"]
    if info.get("api_version") != "1.0":
        errors.append("api_version must be 1.0")
    names = info.get("joint_names")
    if not (
        isinstance(names, list)
        and names
        and all(isinstance(n, str) and n for n in names)
        and len(set(names)) == len(names)
    ):
        return errors + ["info.joint_names must be unique nonempty strings"]
    n = len(names)
    if state.get("joint_names") != names:
        errors.append("state joint order differs from info")
    caps = info.get("capabilities")
    if not isinstance(caps, list) or "servo_twist" not in caps:
        errors.append("servo_twist capability missing")
    for field in ("stream_timeout", "control_rate_hz"):
        value = info.get(field)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            errors.append(f"info.{field} must be finite and positive")
    limits = info.get("joint_limits")
    if not isinstance(limits, list) or len(limits) != n:
        errors.append("joint_limits must match joint_names")
    else:
        for limit in limits:
            if (
                not isinstance(limit, dict)
                or not finite_vector([limit.get(k) for k in ("lower", "upper", "velocity")], 3)
                or limit["lower"] >= limit["upper"]
                or limit["velocity"] <= 0
            ):
                errors.append("invalid joint limit")
    for field in ("positions", "velocities", "efforts", "target_positions"):
        if not finite_vector(state.get(field), n):
            errors.append(f"state.{field} must contain {n} finite values")
    pose = state.get("tcp_pose")
    if not isinstance(pose, dict) or not finite_vector(pose.get("position"), 3):
        errors.append("invalid tcp_pose.position")
    q = pose.get("orientation") if isinstance(pose, dict) else None
    if not finite_vector(q, 4) or abs(sum(x * x for x in q) - 1) > 0.01:
        errors.append("tcp_pose.orientation must be a unit xyzw quaternion")
    for field in ("enabled", "connected"):
        if type(state.get(field)) is not bool:
            errors.append(f"state.{field} must be boolean")
    if not isinstance(state.get("errors"), list):
        errors.append("state.errors must be a list")
    age = state.get("feedback_age")
    if type(age) not in (int, float) or not math.isfinite(age) or age < 0:
        errors.append("state.feedback_age must be finite and nonnegative")
    return errors


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path)
    options = parser.parse_args(args)
    try:
        client = RobotClient(options.url)
        info, state = client.info(), client.state()
        errors = validate_snapshot(info, state)
        report = dict(
            ok=not errors, scope="read_only_snapshot", errors=errors, info=info, state=state
        )
    except (OSError, ValueError, RuntimeError) as error:
        report = dict(ok=False, scope="read_only_snapshot", errors=[str(error)])
    content = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
    print(content)
    if options.output:
        options.output.parent.mkdir(parents=True, exist_ok=True)
        options.output.write_text(content + "\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
