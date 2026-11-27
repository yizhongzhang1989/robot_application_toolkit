"""Dependency-free client for the existing controller HTTP API v1."""

import json
import math
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


def _reject_constant(value):
    raise ValueError(f"Non-finite JSON constant from controller: {value}")


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Non-finite JSON number from controller: {value}")
    return number


class RobotClient:
    def __init__(self, url, timeout=5.0):
        if urlsplit(url).scheme not in ("http", "https"):
            raise ValueError("url must use http or https")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        self.url, self.timeout = url.rstrip("/"), timeout

    def _request(self, method, path, payload=None, timeout=None):
        data = None if payload is None else json.dumps(payload, allow_nan=False).encode()
        request = Request(
            self.url + "/api/" + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout if timeout is None else timeout) as response:
                return json.load(
                    response, parse_constant=_reject_constant, parse_float=_finite_float
                )
        except HTTPError as error:
            detail = error.read().decode(errors="replace")
            raise RuntimeError(f"HTTP {error.code}: {detail}") from error

    def info(self):
        return self._request("GET", "info")

    def state(self):
        return self._request("GET", "state")

    def enable(self):
        return self._request("POST", "enable")

    def stop(self):
        return self._request("POST", "stop")

    def disable(self):
        return self._request("POST", "disable")

    def motion(self, motion_id):
        return self._request("GET", "motions/" + quote(motion_id, safe=""))

    def movej(self, positions, duration=None):
        return self._request("POST", "movej", dict(positions=list(positions), duration=duration))

    def movel(self, pose, **options):
        return self._request("POST", "movel", dict(pose=pose, **options))

    def movec(self, via, pose, **options):
        return self._request("POST", "movec", dict(via=via, pose=pose, **options))

    def trajectory(self, points, joint_names=None):
        return self._request("POST", "trajectory", dict(points=points, joint_names=joint_names))

    def servo_joints(self, positions):
        return self._request("POST", "stream/joints", dict(positions=list(positions)))

    def servo_pose(self, pose):
        return self._request("POST", "stream/tcp", dict(pose=pose))

    def servo_twist(self, linear, angular=(0, 0, 0), frame="base"):
        return self._request(
            "POST", "stream/twist", dict(linear=list(linear), angular=list(angular), frame=frame)
        )

    def wait(self, motion, timeout=None, poll_interval=0.02):
        """Wait for measured completion. A local timeout does not stop the robot."""
        task = self.motion(motion) if isinstance(motion, str) else motion
        if timeout is None:
            timeout = task.get("duration", 30.0) + self.info().get("goal_timeout", 5.0) + 2.0
        if (
            not math.isfinite(timeout)
            or timeout <= 0
            or not math.isfinite(poll_interval)
            or poll_interval <= 0
        ):
            raise ValueError("timeout and poll_interval must be finite and positive")
        deadline = time.monotonic() + timeout
        path = "motions/" + quote(task["id"], safe="")
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("motion wait timed out; use stop() explicitly if needed")
            result = self._request("GET", path, timeout=min(self.timeout, remaining))
            if result["status"] == "succeeded":
                return result
            if result["status"] in ("cancelled", "aborted"):
                raise RuntimeError(f"motion {result['status']}: {result.get('error')}")
            if result["status"] not in ("queued", "running"):
                raise RuntimeError(f"unknown motion status: {result['status']}")
            time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))

    def close(self):
        """No persistent connection; closing never changes controller state."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
