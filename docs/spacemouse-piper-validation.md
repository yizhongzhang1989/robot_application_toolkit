# SpaceMouse 与 Piper 现场验证

日期：2026-11-27。结论：实际输入和低速控制流程通过；运动跟踪质量单独记录，不作本次流程通过条件。
[机器可读摘要](validation/2026-11-27.json)包含测量值和原始记录哈希。

## 配置与范围

SpaceMouse Pro 为 `046d:c62b`，spacenavd 为 1.3.1；ROS 子模块固定 commit
`49d3d57081dfad77d05117ad6d97f4b1fa24135e`，上游源码未改动。
Piper 真机使用 domain 0、namespace `/robot`、HTTP `127.0.0.1:8090`。
仿真使用独立 domain 176。本次未操作 Nero 真机。

真机测试通过 `scripts/probe_spacemouse_control.py` 向独立的
`/robot/validation/spacemouse_joy` 发消息，经适配器输出 `/robot/servo_twist`。
输入为基座 Z 正向 2 mm/s、角速度零，0.6 s 与 0.5 s 短脉冲，恢复检查另有 0.2 s 脉冲。
脚本显式采用按住按钮模式；物理摇帽数据不会混入这一路测试。

## 实际输入

| 检查项 | 结果 |
| --- | --- |
| 45 秒采集 | 44,198 条有效 Joy，约 982.49 Hz |
| 最大消息间隔 | 56.33 ms，低于工具 150 ms 超时 |
| 六轴 | 数值有限，均有正负方向变化 |
| 按钮“1” | 对应索引 0，收到按下与释放 |
| 最后回中 | 六轴全零 |

ROS 消息频率不代表设备独立采样频率。本次没有逐轴标定物理手势与机器人正方向，也未做 USB 拔插测试。

## Piper 控制流程

| 检查项 | 真机结果 |
| --- | --- |
| 接通待机、启动时按钮已按住 | 保持 idle，目标不变 |
| 释放后按住 | 进入 servo_twist，目标和反馈变化 |
| 松键停止 | 约 0.230 s 后观测到 idle |
| 停止发送 Joy | 约 0.379 s 后观测到 idle |
| 恢复消息但仍按住 | 保持 idle，目标不变 |
| 释放再按住 | 恢复 servo_twist，目标推进 |
| 最后释放 | 约 0.231 s 后观测到 idle，无错误 |

时间由约 20 ms 间隔的状态采样估算，表示模式切换观察值，不是外部测得的机械停止时间。
本次累计反馈 TCP 位移为 `[+0.371, +0.004, +2.527] mm`。停止后约 5 秒、100 次采样均为
idle、就绪、速度零，关节位置反馈范围为零。仿真同样通过，累计反馈 Z 变化约 2.903 mm。

## 速度观测与未覆盖项

首次检查设置实测关节速度门槛 0.08 rad/s，第二段 J4 达到 0.09 rad/s 后自动中止。
相邻反馈样本的位置差分约 0.0881 rad/s，名义目标差分约 0.00716 rad/s。
按流程验证要求取消该速度通过条件后的运行中，最大反馈速度为 0.116 rad/s；原始失败记录保留。
这些结果不证明精度、平滑性、停止距离或安全等级，跟踪峰值可在 Piper 控制器中继续分析。

当前遥操默认无需按钮，输入比例为 20 mm/s、0.1 rad/s，回中停止。该模式已通过真实 DDS
比例输出和断流恢复测试，并完成部署状态检查；上述自动真机数据仍限定在 2 mm/s 按住模式。
使用方法见 [遥操文档](teleoperation.md)，系统服务安装见 [安装说明](spacemouse-system-install.md)。

## 复现

下面命令会移动所选已使能机器人，应在已核实的姿态和工作空间使用，先运行仿真。
脚本不使能/复位机器人，默认不以实测速度峰值判失败，但保留反馈、6 mm / 0.025 rad 位移边界和停止检查。

```bash
source ~/Documents/piper_control/scripts/env.sh
cd ~/Documents/robot_application_toolkit
source install/setup.bash
ROS_DOMAIN_ID=0 python scripts/probe_spacemouse_control.py \
  --url http://127.0.0.1:8090 --namespace /robot \
  --output .runtime/spacemouse-validation/retest.json --execute
```

若要复现首次速度检查，额外传入 `--max-measured-speed 0.08`。
默认无需按钮模式由自动化测试覆盖，以上脚本始终验证可选的按住按钮流程。
