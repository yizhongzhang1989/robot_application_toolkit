"""Opt-in integration against actual local controller simulators, never hardware."""

import importlib
import os
import sys
import time
from pathlib import Path

import pytest

pytestmark = [pytest.mark.ros, pytest.mark.controllers]


@pytest.mark.parametrize("model_name,joints", [("nero", 7), ("piper", 6)])
def test_actual_controller_simulation(monkeypatch, model_name, joints):
    if os.environ.get("RAT_TEST_CONTROLLERS") != "1":
        pytest.skip("Set RAT_TEST_CONTROLLERS=1 with controller simulation dependencies")
    rclpy = pytest.importorskip("rclpy")
    pytest.importorskip("control_msgs.action")
    root = Path(os.environ.get("RAT_CONTROLLER_ROOT", str(Path.home() / "Documents")))
    sys.path.insert(0, str(root / f"{model_name}_control"))
    package = f"{model_name}_control"
    RobotModel = importlib.import_module(package + ".model").RobotModel
    SimulationBackend = importlib.import_module(package + ".backends.simulation").SimulationBackend
    RobotController = importlib.import_module(package + ".controller").RobotController
    RosBridge = importlib.import_module(package + ".ros_bridge").RosBridge
    from rclpy.context import Context
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.parameter import Parameter
    from robot_application_toolkit.check import validate_snapshot
    from robot_application_toolkit.teleop_node import SpaceMouseTeleop
    from sensor_msgs.msg import Joy

    monkeypatch.setenv("ROS_DOMAIN_ID", "172")
    model = RobotModel()
    controller = RobotController(SimulationBackend(model), model).start()
    bridge = RosBridge(controller, namespace=f"/sim_{model_name}")
    context = Context()
    rclpy.init(context=context)
    node = rclpy.create_node("simulation_input", context=context)
    teleop = SpaceMouseTeleop(
        context=context,
        namespace=f"/sim_{model_name}",
        parameter_overrides=[
            Parameter("require_deadman", value=True),
            Parameter("input_topic", value=f"/sim_{model_name}/joy"),
        ],
    )
    executor = SingleThreadedExecutor(context=context)
    executor.add_node(node)
    executor.add_node(teleop)
    publisher = node.create_publisher(Joy, f"/sim_{model_name}/joy", 1)

    def spin(seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.005)

    def send(held):
        message = Joy()
        message.header.stamp = node.get_clock().now().to_msg()
        message.axes = [0.0, 0.0, 0.0, 0.0, 0.0, 0.2]
        message.buttons = [int(held)]
        publisher.publish(message)
        spin(0.025)

    try:
        spin(0.5)
        assert not controller.state()["enabled"]
        controller.enable()  # Explicitly enable only the simulator created above.
        assert len(controller.info()["joint_names"]) == joints
        assert not validate_snapshot(controller.info(), controller.state())
        initial = controller.state()["target_positions"][:]
        send(False)
        for _ in range(12):
            send(True)
        assert controller.state()["mode"] == "servo_twist"
        assert not controller.state()["errors"]
        target = controller.state()["target_positions"]
        assert max(abs(a - b) for a, b in zip(initial, target)) > 1e-6
        # No more Joy: adapter sends a short zero burst then the controller times out.
        spin(0.55)
        assert controller.state()["mode"] == "idle"
        stopped = controller.state()["target_positions"][:]
        for _ in range(5):
            send(True)  # Reconnection while held must not resume.
        assert controller.state()["mode"] == "idle"
        assert controller.state()["target_positions"] == stopped
        send(False)
        send(True)
        assert controller.state()["mode"] == "servo_twist"
        send(False)
        spin(0.35)
        assert controller.state()["mode"] == "idle"
    finally:
        executor.shutdown()
        teleop.destroy_node()
        node.destroy_node()
        context.shutdown()
        bridge.close()
        controller.close()
