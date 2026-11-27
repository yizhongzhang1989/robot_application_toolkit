import sys
from pathlib import Path

# Also supports Ubuntu 22.04's pytest 6, which has no pythonpath config option.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ros2/robot_application_toolkit"))
