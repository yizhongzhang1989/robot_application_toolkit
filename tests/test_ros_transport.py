"""Actual DDS transport, no physical input or controller required."""

import time

import pytest

rclpy = pytest.importorskip("rclpy")
from geometry_msgs.msg import TwistStamped
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile, ReliabilityPolicy
from robot_application_toolkit.teleop_node import SpaceMouseTeleop
from sensor_msgs.msg import Joy

pytestmark = pytest.mark.ros


def test_transport_release_timeout_stale_and_namespace(monkeypatch):
    monkeypatch.setenv("ROS_DOMAIN_ID", "171")
    context = Context()
    rclpy.init(context=context)
    node = rclpy.create_node("teleop_test", context=context)
    teleop = SpaceMouseTeleop(
        context=context,
        namespace="/test_arm",
        parameter_overrides=[
            Parameter("require_deadman", value=True),
            Parameter("input_topic", value="/test_mouse/joy"),
        ],
    )
    executor = SingleThreadedExecutor(context=context)
    executor.add_node(node)
    executor.add_node(teleop)
    qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)
    received, other = [], []
    node.create_subscription(TwistStamped, "/test_arm/servo_twist", received.append, qos)
    node.create_subscription(TwistStamped, "/other_arm/servo_twist", other.append, qos)
    publisher = node.create_publisher(Joy, "/test_mouse/joy", 1)

    def spin(seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.005)

    def send(held, stale=False):
        message = Joy()
        if not stale:
            message.header.stamp = node.get_clock().now().to_msg()
        message.axes = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        message.buttons = [int(held)]
        publisher.publish(message)
        spin(0.03)

    try:
        spin(0.5)
        send(True)
        assert not received
        send(False)
        send(True)
        assert any(m.twist.linear.x > 0 for m in received)
        assert all(m.header.frame_id == "base_link" for m in received)
        assert not other
        spin(0.25)
        assert received[-1].twist.linear.x == 0
        received.clear()
        send(True)
        assert not received
        send(False)
        send(True, stale=True)
        assert not received
        send(False)
        send(True)
        assert any(m.twist.linear.x > 0 for m in received)
        send(False)
        spin(0.06)
        assert received[-1].twist.linear.x == 0
        received.clear()
        spin(0.1)
        assert not received
        # A competing writer inhibits output; removal still requires release.
        competitor = node.create_publisher(TwistStamped, "/test_arm/servo_twist", qos)
        spin(0.15)
        send(True)
        assert not received
        node.destroy_publisher(competitor)
        spin(0.15)
        send(True)
        assert not received
        send(False)
        send(True)
        assert any(m.twist.linear.x > 0 for m in received)
    finally:
        executor.shutdown()
        teleop.destroy_node()
        node.destroy_node()
        context.shutdown()
