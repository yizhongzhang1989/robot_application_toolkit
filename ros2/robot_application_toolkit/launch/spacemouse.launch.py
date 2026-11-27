"""Start vendor-independent teleop and optionally the unchanged upstream driver."""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    share = get_package_share_directory("robot_application_toolkit")
    upstream = get_package_share_directory("spacemouse")
    args = [
        DeclareLaunchArgument("robot_namespace", default_value="/robot"),
        DeclareLaunchArgument("config", default_value=share + "/config/spacemouse.yaml"),
        DeclareLaunchArgument("start_driver", default_value="true"),
        DeclareLaunchArgument("input_topic", default_value="/spacenav/joy"),
        DeclareLaunchArgument("frame_id", default_value="base_link"),
        DeclareLaunchArgument("deadman_button", default_value="0"),
        DeclareLaunchArgument("require_deadman", default_value="false"),
    ]
    return LaunchDescription(
        args
        + [
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(upstream + "/launch/spacemouse.launch.py"),
                condition=IfCondition(LaunchConfiguration("start_driver")),
                launch_arguments={"enable_pose": "false"}.items(),
            ),
            Node(
                package="robot_application_toolkit",
                executable="spacemouse_teleop",
                namespace=LaunchConfiguration("robot_namespace"),
                output="screen",
                parameters=[
                    LaunchConfiguration("config"),
                    {
                        "input_topic": LaunchConfiguration("input_topic"),
                        "frame_id": LaunchConfiguration("frame_id"),
                        "deadman_button": ParameterValue(
                            LaunchConfiguration("deadman_button"), value_type=int
                        ),
                        "require_deadman": ParameterValue(
                            LaunchConfiguration("require_deadman"), value_type=bool
                        ),
                    },
                ],
            ),
        ]
    )
