# SpaceMouse 系统驱动安装

按子模块 [README 的 Prerequisites](../third_party/3dconnexion_ros2/README.md)，使用
FreeSpacenav spacenavd 1.3.1 和原始 systemd unit，安装到 `/usr/local/bin`。
驱动服务负责输入设备；ROS 节点、机器人使能和遥操由应用按需启动。

## 安装

先安装构建依赖。在 Ubuntu 22.04 上，软件源的 spacenavd 0.7.1 不具备正确的 Pro 按钮映射；
如果已经安装旧版，应按上游说明卸载后再安装 1.3.1。

```bash
sudo apt install build-essential git libx11-dev libxi-dev
# 在本仓库根目录执行；已有该源码目录时不要重复 clone
mkdir -p .runtime
git clone --branch v1.3.1 https://github.com/FreeSpacenav/spacenavd.git .runtime/spacenavd-src
cd .runtime/spacenavd-src
./configure --prefix=/usr/local
make -j4
./spacenavd -V
cd ../..
```

安装脚本校验源码 commit `22d9730719fe509780f19d25d40687adb16d0baf`。
切换前停止遥操、让机器人保持停止，退出旧前台 daemon 和 ROS 输入节点，然后运行：

```bash
sudo bash scripts/install_spacemouse_system.sh
```

脚本安装 `libspnav-dev` 及运行库，执行上游 `make install`，复制原始 systemd unit，
并执行 `systemctl daemon-reload`、`systemctl enable --now spacenavd`。
脚本不会启动机器人或遥操；若重复安装，会重启系统驱动服务。

## 检查

```bash
/usr/local/bin/spacenavd -V
systemctl is-enabled spacenavd
systemctl is-active spacenavd
systemctl status spacenavd --no-pager
tail /var/log/spnavd.log
```

预期为 v1.3.1、enabled、active，日志识别 SpaceMouse Pro 和 15 个按钮。
原始 unit 挂在 graphical.target 下；无图形工位应按其启动目标配置服务。
此后不需要保留前台终端，也不需要临时库路径；回到 README 构建并启动 ROS 工具。

2026-11-27 的本机安装验证已通过：daemon 由 PID 1 管理，系统 libspnav 0.2.3-1 链接正常，
3 秒收到 2,992 条有效 Joy。服务的 X11 display 无法打开不影响本项目使用的 Unix socket / ROS 输入。
未为验证自启动重启主机；记录见 [验证摘要](validation/2026-11-27.json)。
