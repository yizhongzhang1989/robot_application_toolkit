# SpaceMouse 遥操

数据通路为 `spacenav → /spacenav/joy → spacemouse_teleop → N/servo_twist → 控制器`。
上游累计位姿和增量位姿不直接用于机器人绝对位置控制；工具启动文件关闭 pose_node，保留原始接口。
这样不需要把 SpaceMouse 的原点当作机器人工具位置，也无需在工具库内实现机器人 IK。

`spacenavd` 应按 [系统安装说明](spacemouse-system-install.md)作为后台服务运行。
它随系统启动，ROS 驱动和遥操桥仍由本工具按需启动。

## 配置

```bash
ros2 launch robot_application_toolkit spacemouse.launch.py \
  robot_namespace:=/nero frame_id:=tcp

# 已独立启动上游驱动时，复用它，避免启动两个驱动
ros2 launch robot_application_toolkit spacemouse.launch.py \
  robot_namespace:=/robot start_driver:=false input_topic:=/spacenav/joy
```

速度、轴映射、死区、超时可复制 `config/spacemouse.yaml` 修改后通过 `config:=/absolute/path.yaml` 传入。
参数启动时校验，运行中更改会拒绝，重新启动后生效。launch 显式的 frame、按钮、input_topic 优先。

| 参数 | 默认 | 语义 |
| --- | --- | --- |
| linear_speed | 0.02 | 线速度向量模长上限 m/s |
| angular_speed | 0.1 | 角速度向量模长上限 rad/s |
| deadzone | 0.1 | 每轴归一化死区；剩余范围线性映射 |
| input_timeout | 0.15 | 接收超时及最大 Joy 时间戳年龄 s |
| require_deadman | false | 默认不需要按钮；true 启用原按住按钮模式 |
| publish_rate | 100.0 | 输出 Hz，允许 20–200 |
| axis_map | `[0,1,2,3,4,5]` | 输出各轴使用的输入轴，必须为排列 |
| axis_sign | `[1,1,1,1,1,1]` | 各轴 ±1 |
| output_topic | servo_twist | 相对机器人 namespace |

默认按钮不参与运动控制，也不要求 Joy 有按钮数组。启动或输入中断后先让摇帽回中一次，
随后偏转直接控制速度，回中停止。`require_deadman:=true` 可恢复原先释放再按住的操作模式，
该模式下默认按钮 0，缺失按钮或非法按钮值会关闭门控。

超过范围的归一化轴裁剪到 ±1。单轴速度为
`sign(axis) × max(0, abs(axis) - deadzone) / (1 - deadzone) × max_speed`。
这是一段死区后的线性映射，不把非零输入变成固定速度。默认死区 0.1 时，
偏转 0.325 / 0.55 / 0.775 / 1.0 分别对应 5 / 10 / 15 / 20 mm/s。
多轴同时推动后对线/角速度分别按向量限幅。
加速度、jerk、关节限位、奇异点和碰撞相关检查仍由控制器负责。

回中、消息非法或输入超时后发 3 个零速度样本，随后停止发布；按住按钮模式松键也采用同样处理。
启动后尚未动作时不发送零指令，避免抢占其他规划任务。进程退出或被杀依靠控制器自身看门狗。
在推荐参数下，源消息失联最长约 0.15 s 加一个发布周期才由适配器发现；
如果零指令丢失，控制器还有约 0.2 s 的独立超时。这些是软件指令时序，不是实测机械停止时间。

## 诊断

```bash
ros2 topic echo /nero/teleop/status
ros2 topic info /nero/servo_twist --verbose
ros2 topic echo /spacenav/joy --once
ros2 topic hz /spacenav/joy
```

| status | 处理 |
| --- | --- |
| no_controller | 先启动控制器 `--ros`，检查 namespace、domain、网络和 QoS |
| waiting_for_release | 先释放所配置按钮，再按住 |
| waiting_for_neutral | 先让摇帽回中，再推动；不需要按钮 |
| released / neutral | 正常待机 |
| active | 正在发布非零速度 |
| stale_stamp / input_timeout | 检查驱动和跨机时钟，恢复后回中；按住模式则释放再按住 |
| invalid_input | 检查六轴、按钮数组和有限数值 |
| multiple_command_publishers | 停止同 topic 的其他生产者，完成控制权交接 |

订阅者计数只说明 ROS 图连接，不表示机器人使能或就绪。状态无运动时应再检查控制器自身 errors、
enabled、connected 和 command_ready。`ros2 topic echo` 也会成为订阅者，图检查不是控制器身份验证。

## 上游行为与边界

固定的上游版本用 `zero_when_static=true` 在无运动事件时将轴清零。
上游会继续发布 Joy，按钮是缓存状态，因此本工具的“消息超时”不能证明 USB 实物连接状态，
也不能可靠识别所有拔插后仍按住按钮的情况。物理拔插与 daemon 崩溃恢复必须在具体设备上验收；
如要增强连接诊断，应先在上游新分支增加兼容接口，按 CONTRIBUTING 流程提交评审。

SpaceMouse Pro 至少三键同时按下可能产生上游已记录的硬件鬼键；默认模式忽略按钮。
可选的按住按钮模式属于操作门控，不能替代工业使能装置和机器人自身的安全系统。
首版不含夹爪、双臂广播、TF 自动转换、速度命令跨通道租约或现场工作流程。
