import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from robot_application_toolkit import RobotClient
from robot_application_toolkit.check import validate_snapshot


@pytest.fixture
def endpoint():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            calls.append(("GET", self.path, None))
            body = {"status": "succeeded", "id": "test"}
            if self.path.endswith("bad"):
                self.send_response(409)
                body = {"detail": "busy"}
            else:
                self.send_response(200)
            self.end_headers()
            if self.path.endswith("nan"):
                payload = b'{"position":NaN}'
            elif self.path.endswith("overflow"):
                payload = b'{"position":1e999}'
            else:
                payload = json.dumps(body).encode()
            self.wfile.write(payload)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length)) if length else None
            calls.append(("POST", self.path, payload))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"accepted": true}')

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield RobotClient(f"http://127.0.0.1:{server.server_port}"), calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_client_has_no_connect_or_close_side_effects(endpoint):
    client, calls = endpoint
    with client:
        client.info()
        client.state()
    assert [c[:2] for c in calls] == [("GET", "/api/info"), ("GET", "/api/state")]


def test_wire_format_wait_and_errors(endpoint):
    client, calls = endpoint
    client.servo_twist([0.01, 0, 0], frame="tool")
    assert calls[-1] == (
        "POST",
        "/api/stream/twist",
        {"linear": [0.01, 0, 0], "angular": [0, 0, 0], "frame": "tool"},
    )
    assert client.wait({"id": "test"}, timeout=1)["status"] == "succeeded"
    with pytest.raises(RuntimeError, match="409.*busy"):
        client.motion("bad")
    with pytest.raises(ValueError, match="Non-finite JSON"):
        client.motion("nan")
    with pytest.raises(ValueError, match="Non-finite JSON"):
        client.motion("overflow")
    before = len(calls)
    with pytest.raises(ValueError):
        client.servo_twist([float("nan"), 0, 0])
    assert len(calls) == before


@pytest.mark.parametrize("joints", [6, 7, 12])
def test_snapshot_is_independent_of_joint_count(joints):
    names = [f"joint_{n}" for n in range(joints)]
    info = dict(
        api_version="1.0",
        joint_names=names,
        capabilities=["servo_twist"],
        stream_timeout=0.2,
        control_rate_hz=200,
        joint_limits=[dict(lower=-1, upper=1, velocity=1)] * joints,
    )
    state = dict(
        joint_names=names,
        positions=[0] * joints,
        velocities=[0] * joints,
        efforts=[0] * joints,
        target_positions=[0] * joints,
        enabled=False,
        connected=True,
        errors=[],
        feedback_age=0,
        tcp_pose=dict(position=[0, 0, 0], orientation=[0, 0, 0, 1]),
    )
    assert validate_snapshot(info, state) == []
    state["positions"][0] = float("nan")
    state["tcp_pose"]["orientation"] = [0] * 4
    assert len(validate_snapshot(info, state)) == 2
