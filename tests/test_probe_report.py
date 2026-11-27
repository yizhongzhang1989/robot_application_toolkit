import json
import runpy
from pathlib import Path


def test_probe_keeps_evidence_when_final_state_is_unavailable(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts/probe_spacemouse_control.py"
    write_report = runpy.run_path(str(script))["write_report"]

    class DisconnectedRobot:
        def state(self):
            raise TimeoutError("controller unavailable")

    report = {
        "passed": False,
        "failure": "Feedback readiness/error guard tripped",
        "samples": [{"velocities": [0.01, -0.02]}],
        "commands": [{"linear": [0, 0, 0.002]}],
    }
    output = tmp_path / "report.json"
    write_report(DisconnectedRobot(), report, [0, 0, 0], output)
    saved = json.loads(output.read_text())
    assert saved["failure"] == report["failure"]
    assert "controller unavailable" in saved["final_state_failure"]
    assert saved["samples"] == report["samples"]
    assert saved["final"] is None
    assert saved["summary"]["passed"] is False
    assert saved["summary"]["measured_tcp_delta"] is None
    assert saved["summary"]["max_joint_speed"] == 0.02
