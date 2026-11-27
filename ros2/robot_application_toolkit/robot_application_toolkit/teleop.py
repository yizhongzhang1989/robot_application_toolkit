"""ROS-independent SpaceMouse input gate. All elapsed times are monotonic."""

import math
from dataclasses import dataclass

ZERO = (0.0,) * 6


@dataclass(frozen=True)
class TeleopConfig:
    linear_speed: float = 0.02
    angular_speed: float = 0.1
    deadzone: float = 0.1
    input_timeout: float = 0.15
    require_deadman: bool = False
    deadman_button: int = 0
    axis_map: tuple = (0, 1, 2, 3, 4, 5)
    axis_sign: tuple = (1, 1, 1, 1, 1, 1)

    def __post_init__(self):
        for name in ("linear_speed", "angular_speed", "input_timeout"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if not math.isfinite(self.deadzone) or not 0 <= self.deadzone < 1:
            raise ValueError("deadzone must be in [0, 1)")
        if type(self.deadman_button) is not int or self.deadman_button < 0:
            raise ValueError("deadman_button must be a nonnegative integer")
        if type(self.require_deadman) is not bool:
            raise ValueError("require_deadman must be boolean")
        if (
            len(self.axis_map) != 6
            or any(type(i) is not int for i in self.axis_map)
            or sorted(self.axis_map) != list(range(6))
        ):
            raise ValueError("axis_map must be a permutation of 0..5")
        if len(self.axis_sign) != 6 or any(s not in (-1, 1) for s in self.axis_sign):
            raise ValueError("axis_sign must contain six signs (-1 or 1)")


class TeleopGate:
    def __init__(self, config=TeleopConfig()):
        self.config = config
        self.reason = "waiting_for_release" if config.require_deadman else "waiting_for_neutral"
        self._armed = False
        self._last_input = None
        self._command = ZERO
        self._streaming = False
        self._stop_remaining = 0

    def inhibit(self, reason):
        self._armed = False
        self._command = ZERO
        self._last_input = None
        self.reason = reason

    def receive(self, axes, buttons, now):
        c = self.config
        if (
            not math.isfinite(now)
            or len(axes) != 6
            or any(not math.isfinite(v) for v in axes)
            or (
                c.require_deadman
                and (len(buttons) <= c.deadman_button or any(b not in (0, 1) for b in buttons))
            )
        ):
            self.inhibit("invalid_input")
            return
        if self._last_input is not None and not 0 <= now - self._last_input <= c.input_timeout:
            self.inhibit("input_timeout")
        self._last_input = now
        if c.require_deadman:
            if not buttons[c.deadman_button]:
                self._armed = True
                self._command = ZERO
                self.reason = "released"
                return
            if not self._armed:
                self.reason = "waiting_for_release"
                return
        elif not self._armed:
            # No button is needed. Require a centered sample at startup and
            # after interruption so a deflected device cannot restart a stream.
            if any(abs(value) > c.deadzone for value in axes):
                self.reason = "waiting_for_neutral"
                return
            self._armed = True
        values = []
        for i, sign in zip(c.axis_map, c.axis_sign):
            value = max(-1.0, min(1.0, axes[i])) * sign
            values.append(
                math.copysign(max(0.0, abs(value) - c.deadzone) / (1 - c.deadzone), value)
            )
        # Bound vector norms so diagonals cannot exceed the configured speeds.
        for start, speed in ((0, c.linear_speed), (3, c.angular_speed)):
            norm = math.sqrt(sum(v * v for v in values[start : start + 3]))
            values[start : start + 3] = [
                v * speed / max(1.0, norm) for v in values[start : start + 3]
            ]
        self._command = tuple(values)
        self.reason = "active" if any(values) else "neutral"

    def sample(self, now):
        if (
            self._last_input is not None
            and not 0 <= now - self._last_input <= self.config.input_timeout
        ):
            self.inhibit("input_timeout")
        if any(self._command):
            self._streaming = True
            self._stop_remaining = 0
            return self._command
        if self._streaming:
            self._streaming = False
            self._stop_remaining = 3
        if self._stop_remaining:
            self._stop_remaining -= 1
            return ZERO
        # Idle teleop must not keep overriding a station's planned motion.
        return None
