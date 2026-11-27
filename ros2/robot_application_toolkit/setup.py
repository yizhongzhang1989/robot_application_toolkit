from glob import glob
from pathlib import Path

from setuptools import find_packages, setup

setup(
    name="robot_application_toolkit",
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/robot_application_toolkit"]),
        ("share/robot_application_toolkit", ["package.xml", "README.md", "LICENSE"]),
        ("share/robot_application_toolkit/launch", glob("launch/*.launch.py")),
        ("share/robot_application_toolkit/config", glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    python_requires=">=3.10",
    zip_safe=True,
    maintainer="Robot Application Toolkit contributors",
    maintainer_email="yizhongzhang1989@users.noreply.github.com",
    description="Robot-independent tools for workstation applications",
    long_description=Path(__file__).resolve().with_name("README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    url="https://github.com/yizhongzhang1989/robot_application_toolkit",
    license="Apache-2.0",
    license_files=["LICENSE"],
    entry_points={
        "console_scripts": [
            "spacemouse_teleop = robot_application_toolkit.teleop_node:main",
            "robot_check = robot_application_toolkit.check:main",
        ]
    },
)
