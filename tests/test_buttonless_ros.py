"""Verify proportional commands over actual DDS without publishing to hardware."""

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


def test_buttonless_proportional_transport(monkeypatch):
    monkeypatch.setenv("ROS_DOMAIN_ID", "174")
    context = Context()
    rclpy.init(context=context)
    node = rclpy.create_node("buttonless_test", context=context)
    teleop = SpaceMouseTeleop(
        context=context,
        namespace="/test_buttonless",
        parameter_overrides=[Parameter("input_topic", value="/test_buttonless/joy")],
    )
    executor = SingleThreadedExecutor(context=context)
    executor.add_node(node)
    executor.add_node(teleop)
    received = []
    node.create_subscription(
        TwistStamped,
        "/test_buttonless/servo_twist",
        received.append,
        QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT),
    )
    publisher = node.create_publisher(Joy, "/test_buttonless/joy", 1)

    def spin(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            executor.spin_once(timeout_sec=0.005)

    def send(axis):
        message = Joy()
        message.header.stamp = node.get_clock().now().to_msg()
        message.axes = [axis, 0.0, 0.0, 0.0, 0.0, 0.0]
        message.buttons = []
        publisher.publish(message)
        spin(0.04)

    try:
        spin(0.5)
        send(1.0)
        assert not received
        send(0.0)
        for axis, expected in ((0.325, 0.005), (0.55, 0.01), (0.775, 0.015), (1.0, 0.02)):
            send(axis)
            assert received[-1].twist.linear.x == pytest.approx(expected, abs=1e-8)
        send(0.0)
        spin(0.06)
        assert received[-1].twist.linear.x == 0
        received.clear()
        spin(0.06)
        assert not received
        send(0.0)  # The preceding idle interval can exceed the source timeout.
        send(0.55)
        assert received[-1].twist.linear.x == pytest.approx(0.01)
        spin(0.25)
        assert received[-1].twist.linear.x == 0
        received.clear()
        send(0.55)
        assert not received
        send(0.0)
        send(0.55)
        assert received[-1].twist.linear.x == pytest.approx(0.01)
    finally:
        executor.shutdown()
        teleop.destroy_node()
        node.destroy_node()
        context.shutdown()
