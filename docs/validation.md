# 验证

自动化测试默认不连接真机。现场数据检查、仿真验证和真机流程结果分别记录。
[2026-11-27 结果摘要](validation/2026-11-27.json)随仓库提交，包含原始记录的 SHA-256；
完整高频记录保留在本机忽略目录 `.runtime/spacemouse-validation/`，不随源码发布。

## 自动化检查

在仓库根目录执行：

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m ruff format --check .
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
python -m build ./ros2/robot_application_toolkit --outdir dist
```

普通 Python 环境运行核心测试，缺少 ROS 时跳过 ROS 测试；source ROS 后额外运行
真实 DDS 传输测试。控制器仿真需要独立仓库及其依赖，显式启用：

```bash
source ~/Documents/nero_control/scripts/env.sh
RAT_TEST_CONTROLLERS=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
```

本机 Nero 环境包含双方需要的仿真依赖（含 Ruckig）和 control_msgs overlay。
非默认目录可用 `RAT_CONTROLLER_ROOT` 指定两个型号仓库的父目录。
控制器测试只构造 SimulationBackend，使用 ROS domain 172；传输测试使用 171、174，
与现场 domain 0 隔离。构建使用 README 中的 colcon 命令。

覆盖：比例映射、死区和向量限幅，回中/按钮停止、输入超时及恢复门控，非法输入、时间戳、
多发布者和 namespace 隔离，HTTP 请求/错误处理，六/七/十二轴快照校验，Nero/Piper 仿真执行。

提交前已验证核心与 ROS/控制器仿真测试、三个 ROS 包构建、Python 分发包构建及安装入口。
本次提交检查结果：核心环境 30 项通过（4 项跳过），ROS/控制器仿真环境 34 项全部通过。
CI 包含格式检查、核心测试和 ROS 构建/传输测试；远端执行结果以 GitHub Actions 为准。
公共 CI 不自动获取独立控制器仓库。

## 现场结果与范围

2026-11-27，SpaceMouse Pro 六轴、按钮“1”及回中数据检查通过；Piper 的低速合成 Joy
控制流程通过。具体参数、停止观察、首次速度检查失败及后续流程验证范围见
[SpaceMouse/Piper 报告](spacemouse-piper-validation.md)。

当前无需按钮模式已通过比例输出和停止/恢复的 DDS 测试，部署比例为 20 mm/s、0.1 rad/s。
自动真机流程报告来自 2 mm/s 的按住按钮模式；不能将它表述为所有模式、速度和姿态的真机验收。

[系统安装](spacemouse-system-install.md)已验证 spacenavd v1.3.1 active/enabled、系统 libspnav
链接和实际 ROS 输入。未通过重启整台机器验证启动过程，未完成 USB 拔插、六轴方向标定、
全工作空间运动质量或外部精度测量。UR/Duco 尚未有可运行的型号控制器。
