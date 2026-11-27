"""Read-only, robot-independent capability inspection."""

import argparse
import json

from robot_application_toolkit import RobotClient

parser = argparse.ArgumentParser()
parser.add_argument("--url", required=True)
args = parser.parse_args()
with RobotClient(args.url) as robot:
    print(json.dumps({"info": robot.info(), "state": robot.state()}, indent=2))
