import math

import pytest
from robot_application_toolkit.teleop import ZERO, TeleopConfig, TeleopGate


def moving_gate():
    gate = TeleopGate(TeleopConfig(require_deadman=True))
    gate.receive(ZERO, [0], 1.0)
    gate.receive([1, 0, 0, 0, 0, 0], [1], 1.01)
    assert gate.sample(1.02)[0] == pytest.approx(0.02)
    return gate


def test_start_held_cannot_move_and_idle_never_overrides_station():
    gate = TeleopGate(TeleopConfig(require_deadman=True))
    gate.receive([1] * 6, [1], 1.0)
    assert gate.sample(1.01) is None
    gate.receive(ZERO, [0], 1.02)
    assert gate.sample(1.03) is None


def test_release_stops_then_ceases_publishing():
    gate = moving_gate()
    gate.receive([1] * 6, [0], 1.03)
    assert [gate.sample(1.04) for _ in range(4)] == [ZERO, ZERO, ZERO, None]


@pytest.mark.parametrize(
    "axes,buttons",
    [([math.nan] * 6, [1]), ([math.inf] * 6, [1]), ([1] * 5, [1]), ([1] * 6, []), ([1] * 6, [2])],
)
def test_invalid_input_stops_and_requires_release(axes, buttons):
    gate = moving_gate()
    gate.receive(axes, buttons, 1.03)
    assert gate.sample(1.04) == ZERO
    gate.receive([1] * 6, [1], 1.05)
    assert gate.sample(1.06) in (ZERO, None)
    gate.receive(ZERO, [0], 1.07)
    gate.receive([1] * 6, [1], 1.08)
    assert any(gate.sample(1.09))


@pytest.mark.parametrize("poll_first", [False, True])
def test_timeout_reconnect_held_does_not_restart(poll_first):
    gate = moving_gate()
    if poll_first:
        assert gate.sample(1.3) == ZERO
    gate.receive([1] * 6, [1], 1.31)
    assert gate.sample(1.32) in (None, ZERO)
    gate.receive(ZERO, [0], 1.33)
    gate.receive([1] * 6, [1], 1.34)
    assert any(gate.sample(1.35))


def test_vector_speed_bounds_deadzone_and_axis_mapping():
    gate = TeleopGate(
        TeleopConfig(
            require_deadman=True, axis_map=(2, 1, 0, 5, 4, 3), axis_sign=(-1, 1, 1, 1, 1, 1)
        )
    )
    gate.receive(ZERO, [0], 1.0)
    gate.receive([0.05, 0, 2, 0, 0, 0], [1], 1.01)
    assert gate.sample(1.02) == (-0.02, 0, 0, 0, 0, 0)
    gate.receive([50] * 6, [1], 1.03)
    result = gate.sample(1.04)
    assert math.sqrt(sum(v * v for v in result[:3])) == pytest.approx(0.02)
    assert math.sqrt(sum(v * v for v in result[3:])) == pytest.approx(0.1)


@pytest.mark.parametrize(
    "options",
    [
        dict(input_timeout=0),
        dict(deadzone=1),
        dict(linear_speed=math.nan),
        dict(require_deadman=1),
        dict(deadman_button=-1),
        dict(axis_map=(0,) * 6),
        dict(axis_sign=(0,) * 6),
    ],
)
def test_invalid_configuration_rejected(options):
    with pytest.raises(ValueError):
        TeleopConfig(**options)


@pytest.mark.parametrize(
    "axis,expected",
    [(0.05, 0), (0.325, 0.005), (0.55, 0.01), (0.775, 0.015), (1, 0.02), (-0.55, -0.01)],
)
def test_buttonless_control_is_proportional(axis, expected):
    gate = TeleopGate()
    gate.receive(ZERO, [], 1.0)
    gate.receive([axis, 0, 0, 0, 0, 0], [], 1.01)
    result = gate.sample(1.02)
    assert (result[0] if result else 0) == pytest.approx(expected)
    gate.receive([axis, 0, 0, 0, 0, 0], [1], 1.03)
    assert gate.sample(1.04) == result  # Button state has no effect.


def test_buttonless_neutral_stops_and_reconnect_requires_centering():
    gate = TeleopGate()
    gate.receive([1] * 6, [], 1.0)
    assert gate.sample(1.01) is None
    assert gate.reason == "waiting_for_neutral"
    gate.receive(ZERO, [], 1.02)
    gate.receive([1] * 6, [], 1.03)
    assert any(gate.sample(1.04))
    gate.receive(ZERO, [], 1.05)
    assert [gate.sample(1.06) for _ in range(4)] == [ZERO, ZERO, ZERO, None]
    gate.receive([1] * 6, [], 1.07)
    assert any(gate.sample(1.08))
    assert gate.sample(1.3) == ZERO
    gate.receive([1] * 6, [], 1.31)
    assert gate.sample(1.32) in (ZERO, None)
    gate.receive(ZERO, [], 1.33)
    gate.receive([1] * 6, [], 1.34)
    assert any(gate.sample(1.35))
