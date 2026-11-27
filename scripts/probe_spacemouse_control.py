#!/usr/bin/env python3
"""Move an already enabled robot a few mm using synthetic Joy, and verify stopping.

Run first against a simulator. Requires the ROS and toolkit environments.
This script never enables, resets, or disables a robot.
It explicitly tests the optional hold-button mode, not the default buttonless mode.
"""

import argparse
import json
import math
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from robot_application_toolkit import RobotClient


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def write_report(robot, report, baseline_tcp, output):
    """Keep collected evidence even when the final state request fails."""
    try:
        report["final"] = robot.state()
    except Exception as error:
        report["final"] = None
        report["final_state_failure"] = repr(error)
        report["passed"] = False
    final = report["final"]
    report["summary"] = dict(
        passed=report["passed"],
        measured_tcp_delta=(
            [a - b for a, b in zip(final["tcp_pose"]["position"], baseline_tcp)] if final else None
        ),
        max_joint_speed=max(
            (abs(v) for s in report["samples"] for v in s["velocities"]), default=0
        ),
        command_count=len(report["commands"]),
        final_mode=final["mode"] if final else None,
        final_errors=final["errors"] if final else None,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report["summary"], indent=2), flush=True)


def run(args):
    import rclpy
    from geometry_msgs.msg import TwistStamped
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.parameter import Parameter
    from rclpy.qos import QoSProfile, ReliabilityPolicy
    from robot_application_toolkit.teleop_node import SpaceMouseTeleop
    from sensor_msgs.msg import Joy

    robot = RobotClient(args.url, timeout=0.5)
    info, initial = robot.info(), robot.state()
    if not (
        initial["enabled"]
        and initial["connected"]
        and initial.get("command_ready", True)
        and initial["mode"] == "idle"
        and not initial["errors"]
    ):
        raise RuntimeError("Controller must already be enabled, ready, idle and error-free")
    if max(map(abs, initial["velocities"])) > 0.01:
        raise RuntimeError("Robot is not stationary")
    rclpy.init()
    node = rclpy.create_node("spacemouse_control_probe")
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    teleop = None
    started_motion = False
    report = dict(
        timestamp=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        url=args.url,
        scope="control_workflow",
        max_measured_speed=args.max_measured_speed,
        namespace=args.namespace,
        info=info,
        initial=initial,
        phases=[],
        samples=[],
        commands=[],
        passed=False,
    )
    start = time.monotonic()
    phase_name = "discovery"
    baseline_tcp = initial["tcp_pose"]["position"]
    baseline_q = initial["positions"]
    baseline_target = initial["target_positions"]
    topic = args.namespace.rstrip("/") + "/servo_twist"
    joy_topic = args.namespace.rstrip("/") + "/validation/spacemouse_joy"

    def on_twist(msg):
        report["commands"].append(
            dict(
                t=time.monotonic() - start,
                phase=phase_name,
                linear=[msg.twist.linear.x, msg.twist.linear.y, msg.twist.linear.z],
                angular=[msg.twist.angular.x, msg.twist.angular.y, msg.twist.angular.z],
            )
        )

    def phase(name, duration, held=None, axis=0.0):
        nonlocal phase_name, started_motion
        phase_name = name
        phase_start = time.monotonic()
        before = robot.state()
        next_joy = next_state = phase_start
        while time.monotonic() - phase_start < duration:
            now = time.monotonic()
            if held is not None and now >= next_joy:
                message = Joy()
                message.header.stamp = node.get_clock().now().to_msg()
                message.axes = [0.0, 0.0, axis, 0.0, 0.0, 0.0]
                message.buttons = [int(held)]
                publisher.publish(message)
                if held and axis:
                    started_motion = True
                next_joy = now + 0.01
            executor.spin_once(timeout_sec=0.002)
            if now >= next_state:
                state = robot.state()
                fields = (
                    "timestamp",
                    "positions",
                    "velocities",
                    "target_positions",
                    "tcp_pose",
                    "enabled",
                    "connected",
                    "command_ready",
                    "feedback_age",
                    "mode",
                    "errors",
                )
                report["samples"].append(
                    dict(
                        t=time.monotonic() - start,
                        phase=name,
                        **{key: state.get(key) for key in fields},
                    )
                )
                if not (
                    state["enabled"]
                    and state["connected"]
                    and state.get("command_ready", True)
                    and not state["errors"]
                    and state["feedback_age"] < 0.1
                ):
                    raise RuntimeError("Feedback readiness/error guard tripped")
                arrays = [
                    state["positions"],
                    state["velocities"],
                    state["target_positions"],
                    state["tcp_pose"]["position"],
                ]
                if any(not math.isfinite(v) for arr in arrays for v in arr):
                    raise RuntimeError("Non-finite feedback")
                if (
                    args.max_measured_speed is not None
                    and max(map(abs, state["velocities"])) > args.max_measured_speed
                ):
                    raise RuntimeError(
                        f"Measured joint speed exceeded {args.max_measured_speed} rad/s"
                    )
                if (
                    max(abs(a - b) for a, b in zip(state["positions"], baseline_q)) > 0.025
                    or max(abs(a - b) for a, b in zip(state["target_positions"], baseline_target))
                    > 0.025
                    or distance(state["tcp_pose"]["position"], baseline_tcp) > 0.006
                ):
                    raise RuntimeError("6 mm / 0.025 rad excursion guard tripped")
                if node.count_publishers(topic) != 1:
                    raise RuntimeError("Command publisher conflict")
                next_state = now + 0.02
        after = robot.state()
        record = dict(
            name=name,
            elapsed=time.monotonic() - phase_start,
            before_mode=before["mode"],
            after_mode=after["mode"],
            measured_tcp_delta=[
                a - b for a, b in zip(after["tcp_pose"]["position"], before["tcp_pose"]["position"])
            ],
            before_target=before["target_positions"],
            after_target=after["target_positions"],
        )
        report["phases"].append(record)
        print(json.dumps(record), flush=True)
        return before, after

    try:
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.02)
        for name in ("servo_twist", "servo_pose", "servo_joints"):
            if node.count_publishers(args.namespace.rstrip("/") + "/" + name):
                raise RuntimeError("Existing command producer: " + name)
        if node.count_subscribers(topic) != 1:
            raise RuntimeError("Expected exactly one controller twist subscriber")
        teleop = SpaceMouseTeleop(
            namespace=args.namespace,
            parameter_overrides=[
                Parameter("require_deadman", value=True),
                Parameter("input_topic", value=joy_topic),
                Parameter("linear_speed", value=0.002),
                Parameter("angular_speed", value=0.01),
            ],
        )
        executor.add_node(teleop)
        publisher = node.create_publisher(Joy, joy_topic, 1)
        node.create_subscription(
            TwistStamped,
            topic,
            on_twist,
            QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT),
        )
        phase("connect_idle", 0.5)
        _, state = phase("startup_held", 0.2, True, 1.0)
        if state["mode"] != "idle":
            raise RuntimeError("Held button on startup started motion")
        phase("release_to_arm", 0.15, False)
        before, after = phase("up_then_release", 0.6, True, 1.0)
        if after["mode"] != "servo_twist":
            raise RuntimeError("Controller did not enter servo_twist")
        _, stopped = phase("button_release_stop", 1.2, False)
        if (
            stopped["mode"] != "idle"
            or stopped["tcp_pose"]["position"][2] - before["tcp_pose"]["position"][2] < 0.0002
        ):
            raise RuntimeError("Release stop or measured Z movement failed")
        phase("up_then_disconnect", 0.5, True, 1.0)
        _, stopped = phase("source_timeout_stop", 1.2)
        if stopped["mode"] != "idle":
            raise RuntimeError("Source timeout did not stop controller")
        before, after = phase("reconnect_held", 0.2, True, 1.0)
        if (
            after["mode"] != "idle"
            or max(
                abs(a - b) for a, b in zip(before["target_positions"], after["target_positions"])
            )
            > 1e-6
        ):
            raise RuntimeError("Held reconnect resumed motion")
        phase("release_after_reconnect", 0.15, False)
        before, after = phase("rearmed_motion", 0.2, True, 1.0)
        if (
            after["mode"] != "servo_twist"
            or max(
                abs(a - b) for a, b in zip(before["target_positions"], after["target_positions"])
            )
            < 1e-6
        ):
            raise RuntimeError("Release and repress did not resume motion")
        _, after = phase("final_release", 1.2, False)
        if after["mode"] != "idle":
            raise RuntimeError("Final release did not stop the controller")
        last_samples = [s for s in report["samples"] if s["phase"] == "final_release"][-10:]
        if max(abs(v) for s in last_samples for v in s["velocities"]) > 0.01:
            raise RuntimeError("Final joint velocity did not settle")
        report["passed"] = True
    except BaseException as error:
        report["failure"] = repr(error)
        raise
    finally:
        # Stop before potentially slow DDS teardown. This executor is driven only
        # by this thread, so no further timer callback can publish during stop().
        if teleop:
            teleop.gate.inhibit("probe_finished")
        if started_motion:
            try:
                robot.stop()
            except Exception as error:
                report["stop_failure"] = repr(error)
                report["passed"] = False
        executor.shutdown()
        if teleop:
            teleop.destroy_node()
        node.destroy_node()
        rclpy.shutdown()
        write_report(robot, report, baseline_tcp, args.output)
    if not report["passed"]:
        raise RuntimeError("Probe did not pass")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--max-measured-speed",
        type=float,
        default=None,
        help="optional measured joint speed rejection threshold (rad/s); disabled by default",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="send bounded motion to the selected enabled controller",
    )
    options = parser.parse_args()
    if not options.execute:
        parser.error("--execute is required: this probe moves the selected robot")
    if options.max_measured_speed is not None and (
        not math.isfinite(options.max_measured_speed) or options.max_measured_speed <= 0
    ):
        parser.error("--max-measured-speed must be finite and positive")
    run(options)
