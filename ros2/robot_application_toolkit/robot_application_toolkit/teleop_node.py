"""Joy -> TwistStamped adapter; never enables or disables a robot."""

import json
import math
import time

import rclpy
from geometry_msgs.msg import TwistStamped
from rcl_interfaces.msg import SetParametersResult
from rclpy.clock import Clock, ClockType
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Joy
from std_msgs.msg import String

from .teleop import TeleopConfig, TeleopGate


class SpaceMouseTeleop(Node):
    def __init__(self, **kwargs):
        super().__init__("spacemouse_teleop", **kwargs)
        defaults = dict(
            input_topic="/spacenav/joy",
            output_topic="servo_twist",
            frame_id="base_link",
            publish_rate=100.0,
            linear_speed=0.02,
            angular_speed=0.1,
            deadzone=0.1,
            input_timeout=0.15,
            require_deadman=False,
            deadman_button=0,
            axis_map=[0, 1, 2, 3, 4, 5],
            axis_sign=[1, 1, 1, 1, 1, 1],
        )
        values = {k: self.declare_parameter(k, v).value for k, v in defaults.items()}
        self.frame = values["frame_id"]
        if self.frame not in ("base_link", "tcp"):
            raise ValueError("frame_id must be base_link or tcp; no implicit TF transform")
        rate = values["publish_rate"]
        if not math.isfinite(rate) or not 20 <= rate <= 200:
            raise ValueError("publish_rate must be in [20, 200] Hz")
        self.gate = TeleopGate(
            TeleopConfig(**{k: values[k] for k in TeleopConfig.__dataclass_fields__})
        )
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.publisher = self.create_publisher(TwistStamped, values["output_topic"], qos)
        self.subscription = self.create_subscription(Joy, values["input_topic"], self._receive, qos)
        self.status = self.create_publisher(String, "teleop/status", 1)
        self._steady = Clock(clock_type=ClockType.STEADY_TIME)
        self.create_timer(1.0 / rate, self._tick, clock=self._steady)
        self.create_timer(1.0, self._status, clock=self._steady)
        self.add_on_set_parameters_callback(self._reject_parameter_changes)
        operation = (
            "release button, then hold to move"
            if self.gate.config.require_deadman
            else "center cap, then deflect to move proportionally; no button required"
        )
        self.get_logger().info(
            f"{self.subscription.topic_name} -> {self.publisher.topic_name}; "
            f"{operation}; robot enable is separate"
        )

    @staticmethod
    def _reject_parameter_changes(parameters):
        # Avoid a parameter change appearing accepted without changing the gate.
        return SetParametersResult(successful=False, reason="Restart teleop to change parameters")

    def _receive(self, message):
        stamp = message.header.stamp.sec + message.header.stamp.nanosec * 1e-9
        age = self.get_clock().now().nanoseconds * 1e-9 - stamp
        if stamp <= 0 or not 0 <= age <= self.gate.config.input_timeout:
            self.gate.inhibit("stale_stamp")
            return
        self.gate.receive(message.axes, message.buttons, time.monotonic())

    def _tick(self):
        # A target must exist, and a second publisher must not fight this tool.
        if self.publisher.get_subscription_count() == 0:
            self.gate.inhibit("no_controller")
        if self.count_publishers(self.publisher.topic_name) > 1:
            self.gate.inhibit("multiple_command_publishers")
            self.gate.sample(time.monotonic())
            return  # Do not send a competing zero command either.
        command = self.gate.sample(time.monotonic())
        if command is not None:
            message = TwistStamped()
            message.header.stamp = self.get_clock().now().to_msg()
            message.header.frame_id = self.frame
            message.twist.linear.x, message.twist.linear.y, message.twist.linear.z = command[:3]
            message.twist.angular.x, message.twist.angular.y, message.twist.angular.z = command[3:]
            self.publisher.publish(message)

    def _status(self):
        message = String()
        message.data = json.dumps(
            {
                "status": self.gate.reason,
                "output": self.publisher.topic_name,
                "require_deadman": self.gate.config.require_deadman,
                "linear_speed": self.gate.config.linear_speed,
                "angular_speed": self.gate.config.angular_speed,
                "subscribers": self.publisher.get_subscription_count(),
            }
        )
        self.status.publish(message)


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = SpaceMouseTeleop()
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        # Process loss is covered by the controller's own stream watchdog.
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
