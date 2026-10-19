# 本地任务后端

> **公开子集说明：**本目录的 API、账号、任务协议和离线视觉准备可运行。真实仿真／机器人执行实现、Go2 XML／OBJ 和模型权重未分发；默认配置不能执行仿真或实机任务。下文保留集成接口及外置实现接入参考，不能当作完整执行环境已包含。新克隆运行步骤与实际验证见 [公开应用说明](../../docs/PUBLIC_APPLICATION.md)。

基于 FastAPI 官方模板裁剪改造，来源及许可见 [UPSTREAM.md](UPSTREAM.md)。
提供登录、观察点、任务提交／查询／取消、历史、阶段事件、照片／录像读取和华为 MaaS 图片问答入口。
支持同端口提供已构建的网页；本机默认只监听 `127.0.0.1`。真实运动默认关闭，启动服务不会连接机器人。

## 安装与启动

从仓库根目录执行。需要 [uv](https://docs.astral.sh/uv/)，由它准备隔离的 Python 3.14；
不使用或升级现有 ROS、导航、MuJoCo 的 Python 环境。

```bash
uv sync --project cloud/backend --python 3.14 --locked
cloud/backend/.venv/bin/python cloud/backend/scripts/init_local.py
bash cloud/backend/run.sh
```

上述步骤要求 uv 已安装在 PATH。Python 环境、下载工具、`.venv` 和本机配置均不随仓库分发，不要提交到 Git。

`init_local.py` 生成被忽略且权限为 0600 的 `cloud/backend/.env`，已有文件不会覆盖。
默认操作账号是 `operator@example.com`，随机密码在该文件的 `FIRST_SUPERUSER_PASSWORD` 中，
请在本机查看，不发到聊天或提交到 Git。JWT 密钥也只保存在该文件。
`FIRST_SUPERUSER_PASSWORD` 仅用于首次建库；保留数据库时修改该变量不会重置已有账号密码。

- 成品网页与 API：<http://127.0.0.1:8000>（网页需先构建，见下节）
- 交互文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/healthz>
- OpenAPI：<http://127.0.0.1:8000/api/v1/openapi.json>

在 `/docs` 使用 Authorize，输入账号作为 username 及本机密码；随后可直接试接口。
也可调用 `POST /api/v1/login/access-token`，使用表单字段 `username/password`，
以后传 `Authorization: Bearer <access_token>`。令牌默认有效 120 分钟。

## 网页构建与同地址运行

前端构建输出位于 `apps/web/dist`，构建命令见 [前端说明](../../apps/web/README.md)。
构建后重新启动 `bash cloud/backend/run.sh`，即可通过同一个 `http://127.0.0.1:8000`
访问网页与 API；Vite 的 `5173` 端口仅用于前端开发，不是成品运行的必要服务。
当前已有的后端进程不会因源码变更自动加载此整合，需由操作者重启。

后端启动时检查构建目录；没有 `dist/index.html` 时 API 和 `/docs` 仍正常运行，网页路径返回 404。
已有构建时，`/`、`/login`、`/console`、`/history`、`/project` 都支持直接打开及浏览器刷新。
新增网页路由时需要同步更新 `app/frontend.py` 中的明确路由名单。

`/assets` 只提供常见的 JS、CSS、图片和字体等构建文件；根目录仅开放图标、加载样式和浏览器检测脚本。
源码映射、隐藏文件、`private` 目录、越界符号链接和任意其他文件不公开。
未知的 `/api/*` 及其他未知路径返回 404，不返回网页；API、OpenAPI 和 `/docs` 保持原行为。

## 网络端口与业务接口

| 端口 | 用途 | 当前情况 |
| --- | --- | --- |
| `127.0.0.1:8000` | 成品网页、后端 HTTP、文档、任务、照片和录像 | 本地启动脚本默认值，可用 `CAMPUS_API_PORT` 更改 |
| `localhost:5173` / `127.0.0.1:5173` | Vue/Vite 开发服务 | 开发时使用，已加入 CORS；成品无需启动 |
| 无独立数据库端口 | SQLite 账号库和任务文件 | 在本机私有目录持久保存 |
| 出站 HTTPS `443` | 未来 Huawei MaaS | 配置模型后才发送图片请求；本次未开通服务 |

所有业务接口共用后端端口，不是每个功能开一个网络端口。
`CAMPUS_API_PORT=8001 bash cloud/backend/run.sh` 可在端口冲突时改端口；
同地址成品网页随端口一起改变；独立开发服务需同时调整 API 地址，不需要改机器人端口。

除登录、健康与文档外均要求登录：

| 方法与路径（前缀 `/api/v1`） | 行为 |
| --- | --- |
| `GET /users/me` | 当前账号 |
| `GET /capabilities` | 返回配置可用性；不是硬件或云模型连通保证 |
| `GET /points` | 观察点，含示例配置标识、`initial_pose` 坐标参考 |
| `POST /tasks` | 返回 `202` 和任务编号，执行在独立进程中继续 |
| `GET /tasks?offset=0&limit=20` | 任务历史，普通用户只看自己的任务 |
| `GET /tasks/{task_id}` | 状态、错误、仿真进展、照片／录像地址、回答 |
| `POST /tasks/{task_id}/cancel` | 提交取消请求；不表示物理停车已确认 |
| `GET /tasks/{task_id}/events?after=0` | 分页读取阶段变化 |
| `GET /tasks/{task_id}/result` | 当前结果与问答状态 |
| `GET /tasks/{task_id}/video` | 完成后的 MuJoCo MP4，可用于回放 |
| `GET /tasks/{task_id}/photo` | 成功采图后的真实相机图片，重新检查任务号与 SHA256 |
| `POST /tasks/{task_id}/analysis` | 对已有成功照片显式问答，不再次移动或拍照 |

提交示例：

```json
{"point_id":"demo-a","mode":"simulation","question":""}
```

`mode` 必填，可为 `simulation` 或 `motion`。用户不能提交 shell 命令、坐标、文件路径或任意模型地址。
`question` 可留空；有问题时，仅实机成功照片和完整模型配置都满足后才自动调用一次模型。
忙时返回 `409/BUSY`，不排队、不抢占、不自动重试。
业务错误格式为 `{"detail":{"code":"...","message":"..."}}`；参数错误沿用 FastAPI 的 422 校验格式。
前端可每秒查询一次任务状态；不能将 `NAVIGATING` 解释成机器人一定已经运动。
图片／录像也要求 Bearer：前端可带认证请求后用 Blob URL 展示，不把令牌放入 URL。

## 接入独立仿真

本公开仓库保留仿真 API 契约和人工路线配置，不包含实际执行源码、Go2 资产或模型。只有已另行取得这些内容的使用授权并准备兼容外置环境后，才能在本机 `.env` 填写路径，例如：

```dotenv
SIM_PYTHON=/absolute/path/to/authorized-simulation/.venv/bin/python
SIM_SOURCE=/absolute/path/to/authorized-simulation/src
SIM_HIMLOCO_POLICY=/absolute/path/to/authorized-assets/himloco.pt
SIM_NAVIGATION_POLICY=/absolute/path/to/authorized-assets/navigation.pt
```

代码中的 `SIM_SOURCE` 默认仍指向兼容路径 `edge/go2/simulation/src`，但**该实现目录没有随公开仓库分发**；两份默认策略文件也不存在。操作者需要显式配置获准的外置路径。`SIM_ROUTES` 默认为已公开的 `edge/go2/simulation/routes.json`，路线配置不提供执行能力。来源与范围见 [仿真说明](../../edge/go2/simulation/README.md)。

`GET /api/v1/capabilities` 返回 `simulation_routes`。三 checkpoint 仿真请求为 `{"simulation_route_id":"checkpoints-simple","mode":"simulation"}`；与 `point_id` 二选一，路线不能用于 motion。任务接受时保存场景与路线快照，返回 `simulation_route`；为保持旧任务展示，路线任务的 `point_id` 为路线 ID、`point` 为末点摘要，真实逐点坐标以 `simulation_route.waypoints` 为准。
沿用已有 MuJoCo runner、策略和环境；默认 CPU、无 GUI、EGL 录像、固定 seed。
新克隆不附任何本机已验证配置；默认 capabilities 中 `simulation_configured=false`，提交仿真返回 `503/SIMULATION_NOT_CONFIGURED`。
接口保留 `himloco_flat/flat_obstacle/staggered_walls` 场景白名单，原完整环境中单点默认平地；路线按其配置选择侧箱或短墙场景，历史网页演示出生点为 `(0,0)`，朝向 +x。`checkpoints-walls` 为三面错位短墙，路线中的受限 `control` 参数随任务快照保存并传入监督器，不能由浏览器提交任意参数。轻量批测的历史结果与局限见 [演示证据](../../docs/demo.md)。

仿真返回真实状态、进展、最终摘要和录像。只有摘要 `goal_reached=true` 且无跌倒／碰撞才报成功，
不能仅看进程退出码。仿真状态不含拍照阶段；`analysis_state=NO_CAMERA_PHOTO`。
视频是现有场景自由相机视角，不是机器狗机载相机；本轮按用户选择不增加仿真截图问答。
录像只有正常写入结束后才可读取，取消／超时留下的不完整文件不作为完成录像交付。

## 接入已有实机调度

实机接口保留对原 CLI 的调用契约，**原机器人 CLI、导航实现与模型未随公开仓库分发**。默认 `MOTION_ENABLED=false`，提交实机任务返回 `409/MOTION_DISABLED`。下列配置是原完整环境的接入参考，不能单靠修改开关获得实机能力；需先具备获准的兼容执行实现和现场条件：

- `GO2_CONFIG`：已有 `config.local.json`；`GO2_POINTS`：现场校准的点位文件。
- `GO2_PYTHON`：运行现有轻量 CLI 的解释器；导航解释器继续由原配置或 `GO2_NAV_PYTHON` 决定。
- `CAMERA_SOURCE=unitree` 或 `dock`、`CAPTURE_PYTHON`；dock 还需 `DOCK_HOST/DOCK_USER/DOCK_DEVICE`。
- 按已获准执行实现自身的部署与现场说明核查；公开仓库的范围见 [应用边界](../../docs/PUBLIC_APPLICATION.md)。

后端复用原单任务监督、同机同账户运动锁、90 s 默认时限和取消清理。
每个任务沿用编号读取原 `task.json` 和 `observation-result.json`，
只交付 `SUCCEEDED`、编号匹配、`PHOTO_READY`、相机来源与哈希一致的照片。
模型分析失败保持机器人采图成功状态，通过单独 `analysis_state/analysis_error` 表达。

## 远程仿真

远程仿真通道已复用这些任务与媒体接口，服务端和 Ubuntu 执行端通过 HTTP 分开运行。手动开关、评委账号、断线回传、同机准入与独立配置见 [REMOTE.md](REMOTE.md)，本机真实验证见 [REMOTE_VALIDATION.md](REMOTE_VALIDATION.md)。默认不开放远程执行，无实际云部署。

## 华为云配置入口

本轮只实现调用适配和本地配置，没有开通、付费或真实调用模型。
在 `.env` 填写实际支持图片输入的模型：

```dotenv
HUAWEI_CHAT_COMPLETIONS_URL=https://your-authorized-endpoint/v1/chat/completions
HUAWEI_MODEL=your-vision-model
HUAWEI_API_KEY=fill-locally-only
```

完整地址以账号控制台为准，可配置相应 `v1` 或 `v2` 地址，不从接口调用者接收任意 URL。
使用 HTTPS、Bearer、图片 Base64，验证 TLS，不跟随跳转、不自动重试；
网络／超时／上游错误单独返回，不伪造模型回答。
未配置时 capabilities 返回 false；成功采图后有问题则标记 `NOT_CONFIGURED`，显式分析请求返回 503。
模型名、区域与图像能力必须核对账号实际可用服务。
修改 `.env` 后需重启后端使配置生效。
请求格式依据华为 [MaaS V1](https://support.huaweicloud.com/model-call-maas/model-call-020.html)
和 [MaaS V2](https://support.huaweicloud.com/model-call-maas/model-call-019.html)；
本项目没有因此引入 OpenAI SDK，也没有调用其他模型供应商。

## 数据与进程管理

独立图片问答评测可复用同一调用函数，不经过机器人任务接口、不要求后台账号配置。入口为仓库根目录的 `bash cloud/backend/vision-eval.sh`；清单／报告与后续真实调用见 [离线视觉评测](../../evaluation/vision/README.md)。当前图片与参考事实留空，没有实际模型效果。

数据默认保存在被忽略的 `.local/backend/`：SQLite 账号库、`tasks/<id>/request.json`、
`state.json`、阶段事件、监督进程日志、仿真数据／视频、后续模型回答。
实机照片与底层日志沿用原 runtime 配置的 `output_dir`。
均不提交 Git，公开接口不返回密钥、配置路径或任意日志文件。

一个数据目录只运行一个 HTTP worker；`.server.lock` 防止多个 API 实例误用同一目录。
提交加进程文件锁，执行在独立监督进程里，刷新网页不打断任务。
重启可继续查询尚存活任务及历史。本地执行模式下正常关闭 API 会请求取消未结束任务，等待清理；
网页断开不会自动取消。

监督进程意外丢失会标记 `WORKER_LOST` 和 `requires_operator_review=true`，阻止新任务。
它不等于机器狗已停，也不会按记录中的 PID 杀进程。应先检查本机日志、确认执行器和硬件停止，
再停 API、人工处理该本机任务记录的复核标记；不提供远程按钮绕过。
SQLite 当前为本地首版建表初始化，尚无已发布业务数据迁移或云端数据库部署。

执行进程完成结果交付并退出前，后端仍保持忙状态，避免显式问答与自动问答重复执行。
总时限到达时即使底层通过取消入口清理，公开结果仍为 `TIMED_OUT/TASK_TIMEOUT`；
若人工取消与外层时限在同一轮检查中同时出现，外层优先发送人工取消请求；底层已有的超时终态仍保留。

## 验证

```bash
bash cloud/backend/test.sh -q
cloud/backend/.venv/bin/ruff check cloud/backend/app cloud/backend/scripts cloud/backend/tests
```

测试使用临时目录、人工图片和替身进程，不连接机器人或真实模型；
公开副本的实际测试与默认不可执行状态见 [公开应用说明](../../docs/PUBLIC_APPLICATION.md)。原完整环境中 MuJoCo 经 HTTP 提交的历史记录见 [VALIDATION.md](VALIDATION.md)，不能替代公开子集的真实仿真复现。
主机 ROS 的 Python 路径和自动加载 pytest 插件会污染其他解释器，启动／测试脚本已隔离这些变量。
