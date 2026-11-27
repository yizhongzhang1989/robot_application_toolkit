# Robot Application Toolkit

Robot-independent tools for industrial workstation applications: a ROS 2
SpaceMouse velocity adapter, an HTTP API v1 client, and a read-only interface
checker. Controllers remain responsible for robot-specific execution.

Supported baseline: Python 3.10+, ROS 2 Humble, Ubuntu 22.04.
The HTTP client can be used without ROS or vendor SDKs:

```python
from robot_application_toolkit import RobotClient

with RobotClient("http://127.0.0.1:18089") as robot:
    print(robot.info())
    print(robot.state())
```

Installation, ROS launch instructions, controller interface specification, and
validation records are in the
[repository documentation](https://github.com/yizhongzhang1989/robot_application_toolkit).

Licensed under Apache-2.0. SpaceMouse driver dependencies retain their own licenses.
