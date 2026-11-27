# 控制器统一接口 v1.0

本规范以现有 Nero / Piper API v1 的共同接口为基础。`N` 为机器人 namespace，
例如 `/cell_a/arm_left`。控制器一启动就注册订阅和服务；没有遥操时仍可发布状态。
不得因出现订阅者或收到第一条指令而自动使能电机。

## ROS 2 必需接口

| 名称（相对 N） | 类型 | 方向（控制器） | 约定 |
| --- | --- | --- | --- |
| `servo_twist` | `geometry_msgs/msg/TwistStamped` | 订阅 | TCP 线速度 m/s、角速度 rad/s |
| `servo_pose` | `geometry_msgs/msg/PoseStamped` | 订阅 | TCP 绝对位姿，`base_link` |
| `servo_joints` | `sensor_msgs/msg/JointState` | 订阅 | 全部关节位置，按 name 重排 |
| `joint_states` | `sensor_msgs/msg/JointState` | 发布 | 实际反馈，含关节名 |
| `tcp_pose` | `geometry_msgs/msg/PoseStamped` | 发布 | 实际反馈计算的 TCP 位姿 |
| `state` | `std_msgs/msg/String` | 发布 | 与 HTTP state 同语义的 JSON |
| `enable` | `std_srvs/srv/SetBool` | 服务 | true 使能，false 失能；返回 success/message |
| `stop` | `std_srvs/srv/Trigger` | 服务 | 取消活动运动，保持目标，保留使能状态 |
| `follow_joint_trajectory` | `control_msgs/action/FollowJointTrajectory` | action server | 带时间的关节轨迹、反馈、结果及取消 |

实时命令及关节/TCP 状态采用 KEEP_LAST depth=1、BEST_EFFORT、VOLATILE。
JSON state 使用 RELIABLE depth=1、VOLATILE；service/action 采用 ROS 默认 QoS。
工具输入 Joy 使用 BEST_EFFORT depth=1，可接收上游 RELIABLE 发布。
控制器反馈频率由 info 报告；现有桥接关节/TCP 为 200 Hz，JSON state 为 20 Hz。

ROS `frame_id=base_link` 表示以基座坐标表示的 TCP 速度，`tcp` 表示以当前 TCP 坐标表示。
v1 兼容别名 `base`、`tool`；工具只发规范名称。不支持的 frame 必须拒绝，不能直接重标 frame。
多机器人 TF 树命名和变换由工位负责；本版不自动做 TF 转换。

`Joy.axes` 为上游已转换坐标的 `[vx,vy,vz,wx,wy,wz]` 归一化输入；工具不再重复上游轴交换。
默认无需按钮；可选按住模式用按钮门控，不映射使能、失能或硬件急停。

## 单位、发现和 HTTP

SI 单位：转动关节 rad、rad/s、N·m；TCP m、m/s、rad/s；四元数 `[x,y,z,w]`。
首版以转动关节机械臂为基线，移动底盘、直线关节和夹爪应另行定义能力扩展，不能隐式套用。

`GET /api/info` 必需字段：`api_version="1.0"`、`joint_names`、`joint_limits`
（逐关节 lower/upper/velocity）、`capabilities`、`control_rate_hz`、`stream_timeout`、
`feedback_timeout`、`base_frame`、`tcp_frame`、`units`。建议报告实际 TCP 偏移、模型、终点容差及超时参数。
客户端按能力选择功能，不按型号或固定六轴判断。扩展字段允许存在，删除/改义需要主版本升级。

`GET /api/state` 必需字段：`joint_names`、`positions`、`velocities`、`efforts`、
`target_positions`、`tcp_pose`（position/orientation）、`enabled`、`connected`、`feedback_age`、
`mode`、`errors`、`motion`。真机应另有 `command_ready`，表明反馈、固件控制权和执行条件全部满足。
测量值与目标分别报告，不能把目标当成实际反馈。断联/无效反馈必须明确报告，不能伪造全零或到位。

| HTTP 接口 | 请求主体或用途 |
| --- | --- |
| POST `/api/enable`, `/api/stop`, `/api/disable` | 无正文；返回状态 |
| POST `/api/stream/joints` | `{"positions":[...]}` |
| POST `/api/stream/tcp` | `{"pose":{"position":[...],"orientation":[...]}}` |
| POST `/api/stream/twist` | `{"linear":[...],"angular":[...],"frame":"base"}`；frame 为 base/tool |
| POST `/api/movej` | `{"positions":[...],"duration":2.0}`；duration 可空 |
| POST `/api/movel` | `{"pose":{...},"duration":2.0}`；可选参数见控制器 OpenAPI |
| POST `/api/movec` | `{"via":{...},"pose":{...},"duration":3.0}` |
| POST `/api/trajectory` | `{"joint_names":[...],"points":[{"positions":[...],"time_from_start":2.0}]}` |
| GET `/api/motions/{id}` | 查询规划运动终态 |
| WS `/ws/state` | 状态流 |
| WS `/ws/control` | 控制器现有持久流，type 为 joints/tcp/twist；其余字段同对应 HTTP 请求 |

错误输入返回 422，执行冲突返回 409；客户端必须保留服务端错误。
详细可选请求字段通过各控制器 `/openapi.json` 获取。首版工具客户端提供 HTTP 方法，未封装 WebSocket。

## 执行、时间与停止

所有输入数值必须有限；关节维度、名字、时间顺序、四元数、限位及能力在控制器中再次检查。
规划请求成功只表示接受，终态为 `succeeded`、`aborted` 或 `cancelled`，活动态为 `running`
（允许排队实现使用 `queued`）。到位必须依据有效实际反馈、误差和稳定判据，不能只用轨迹计时。
客户端等待超时只是本地错误；调用方决定是否显式 stop，关闭客户端也不改变机器人状态。

实时流接管规划的具体行为须在控制器中记录；现有 Nero/Piper 会接管，工位必须先完成控制权交接。
每个控制器独立实现单调时钟看门狗：首版推荐 0.2 s 无有效实时指令即停止推进目标并保持。
超时后不能执行缓存的旧指令。反馈失效应中止活动任务并拒绝新运动。
stop 允许后续新指令启动，因此工位需同时停掉旧生产者。失能与保持是不同操作。

ROS header 使用 ROS 时间；跨机需要同步时钟。工具拒绝零时间戳、未来或年龄超过 0.15 s 的 Joy，
并使用本地单调时钟检测接收超时。现有 Nero/Piper 桥主要依据接收时刻，尚不检查命令 header 年龄；
新控制器应增加时间戳检查并明确时钟策略，不将旧实现描述为已经满足这项增强要求。

现有 action 仅支持 stamp=0 的即时执行、全关节 positions 和可选 velocities；
不支持每请求 path/goal tolerance、非零 goal_time_tolerance、acceleration/effort 或 multi-DOF，
应明确拒绝。容差由控制器配置，不要悄悄忽略不支持的字段。

`robot_check` 是上述字段的部分静态检查，完整接入还需行为测试和现场验收。
