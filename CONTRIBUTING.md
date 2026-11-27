# 开发与子模块维护

普通改动在本仓库新分支开发，记录用途、接口影响和验证结果。
通用逻辑不得导入某个厂商 SDK，不根据机器人名称选择控制算法。
根目录运行 pytest；ROS 改动还需验证真实 topic 传输和匹配 QoS。

开发环境安装 `requirements-dev.txt`，提交前运行：

```bash
python -m ruff check .
python -m ruff format --check .
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
python -m build ./ros2/robot_application_toolkit --outdir dist
git diff --check
```

ROS 构建及控制器仿真入口见 [验证文档](docs/validation.md)。提交源码、配置和必要的结果摘要；
`.runtime/`、`build/`、`install/`、`log/`、虚拟环境和原始现场记录不进入 Git。
不要在清理时删除运行中的安装目录或改动现场机器人服务。

## SpaceMouse 上游修改流程

子模块固定到明确 commit。首版未修改上游代码，不存在待合并的上游 PR。
如果后续确需改动，必须先在子模块创建新分支，尽量维持原 topic、消息类型、参数和 launch 接口：

```bash
git -C third_party/3dconnexion_ros2 switch -c feat/toolkit-compatible-improvement
# 编辑、测试并在子模块内提交
git -C third_party/3dconnexion_ros2 add <changed-files>
git -C third_party/3dconnexion_ros2 commit -m 'Describe the compatible change'
# 准备审查材料后推送该分支，并向 upstream main 提交 PR
git -C third_party/3dconnexion_ros2 push -u origin feat/toolkit-compatible-improvement
```

验收前不直接修改/推送上游 main。PR 说明包含旧接口兼容性、设备型号和测试结果；
验收通过后通过 PR 合并 main，再更新本仓库的 gitlink 并提交。
联调可固定未合并分支的 commit，但提交必须在远端可取得，且文档注明状态。
不提交指向仅存在本机的子模块 commit。

上游依赖应通过 `git submodule update --init --recursive` 获取固定版本。
不要用 `git submodule update --remote` 隐式升级。新增或修改硬件行为时单独记录设备验收，
不能用模拟 Joy 的测试代替实物输入验证。
