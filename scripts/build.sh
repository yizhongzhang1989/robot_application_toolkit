#!/usr/bin/env bash
set -e
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
source /opt/ros/"${ROS_DISTRO:-humble}"/setup.bash
git submodule update --init --recursive
colcon build --symlink-install --base-paths ros2 third_party --packages-up-to robot_application_toolkit
