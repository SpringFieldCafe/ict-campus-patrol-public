# 后端验证记录

> **历史环境记录：**下文是原私有开发环境在 2026-10-16～17 的验证，部分依赖未随公开仓库分发的机器人／MuJoCo 源码和资产。公开副本的 74 项测试、夹具适配与默认执行边界见 [公开应用说明](../../docs/PUBLIC_APPLICATION.md)；历史真实仿真不代表本公开子集可完整复现。

日期：2026-10-16（Asia/Shanghai）。代码由 Codex 完成；本记录不是 CodeArts 操作证据。

## 环境与复用来源

- Ubuntu 本机；官方 FastAPI 模板提交 `b1125d8839482cb7bbae603ddc6d0081bf87532e`。
- 隔离 CPython 3.14.8；FastAPI 0.143.2、SQLModel 0.0.48、SQLAlchemy 2.1.4、Pydantic 2.14.1、HTTPX 0.28.1、Uvicorn 0.54.0。
- `uv.lock` 固定依赖并通过 `uv lock --check`；原导航／仿真环境未升级。
- 服务实际只监听 `127.0.0.1:8000`。账号、JWT 密钥、真实资产路径、视频与运行日志均在 Git 忽略区。

## 自动验证

`bash cloud/backend/test.sh -q`：15 项通过。测试使用临时目录、人工 PNG 数据和替身执行进程，覆盖：

- 登录、当前用户、未认证拒绝、CORS、OpenAPI 和配置状态。
- 提交返回 202，不等待执行完成；忙时 409，两个并行提交只接受一个。
- 成功、取消、超时；仿真进程退出码 0 但未到点时仍失败。
- 状态事件、历史、完成录像读取；仿真不提供相机照片或模型回答。
- 成功照片交付：任务状态、任务号、路径边界、SHA256；超时残留图片拒绝交付。
- 真实任务适配器用替身 CLI 验证成功与非零退出，不初始化 SDK。
- 丢失监督进程后标记失败、要求复核且不自动重跑。
- Huawei 请求格式、回答、超时、上游错误；模型失败保持机器人采图成功状态。
- 历史任务启动新的照片问答时，并发状态查询不会将旧的已退出执行进程误判成新问答失败。
- 成功交付中的存活执行进程保持忙状态，阻止显式／自动问答重复调用；外层任务超时不会因底层取消接口而误报为人工取消。

初次检查发现两项本机／模板兼容差异，已修正：
主机 ROS Python 3.10 的路径与 pytest 插件会污染隔离环境，启动／测试脚本会隔离；
模板 JWT 的字符串用户 ID 在 SQLite UUID 字段上需显式解析 UUID。
测试环境上游 Starlette 对 HTTPX TestClient 发出一条弃用提示；断言均通过。

`ruff check`、`ruff format --check`、`git diff --check` 通过。
原机器人 `bash edge/go2/run.sh offline`：99 项通过，不连接机器狗。

## 实际 MuJoCo 经 HTTP 的验证

这是对本机已存在物理仿真、模型和资产的真实运行，不是替身进程，也不是实机。
默认单点 `demo-a` 为起始位姿下前方 1 m，场景 `himloco_flat`，seed 0，CPU，开启 EGL 录像。

- `GET /healthz`：200；登录：200。
- capabilities：仿真配置存在；`motion_enabled=false`、`huawei_configured=false`。
- `POST /api/v1/tasks`：202，初始 PREPARING，之后 NAVIGATING → SUCCEEDED。
- 实际任务 `task-b57e9e684eab438893ba26c21df02ade`；仿真最终摘要 `goal_reached=true`、`collision=false`、`fallen=false`，到达 1/1 航点。
- runner 报告墙钟耗时约 18.89 s，轨迹长度约 1.123 m。
- `GET /tasks/{id}/video`：200，156050 字节；Range `bytes=0-1023`：206、1024 字节。
- FFprobe：H.264，640×480，2.8 s；来自现有 MuJoCo 场景自由相机。
- 未认证读取录像：401；仿真任务读取相机照片：409；`analysis_state=NO_CAMERA_PHOTO`。
- 正常停止并重新启动 API 后，历史与同一任务仍为 200／SUCCEEDED，录像仍可读取；OpenAPI 返回 200，共 13 个业务／健康路径。

本机详细 HTTP 核对摘要在 `.local/backend/validation-http.json`，原始日志与视频在
`.local/backend/tasks/<task_id>/`，不提交生成产物。

## 未验证边界

尚未连接真实 Go2、ROS 传感器或相机，不能保证实际导航、取景、物理停车或现场网络。
真实运动仍禁用；没有远程急停或现场接管验证。
用户尚未开通华为视觉模型，因此没有真实模型调用、账单或答案效果验证。
业务前端已经完成并联调；尚未开通云资源或完成云端部署。Windows 原生后端运行未验证。

## 2026-10-16 独立仿真与路线增量

原私有开发版本当时使用该版本管理的独立仿真源码与本机准备后的模型，支持 simulation-only 三 checkpoint 路线；本公开子集没有分发这些执行实现和模型。单点／实机 API 保持原语义，路线不能用于实机。当时完整回归 48 项通过，Ruff 通过。公开的历史运行结果见 [演示证据](../../docs/demo.md)，源码范围见 [仿真说明](../../edge/go2/simulation/README.md)。

## 2026-10-17 远程仿真增量

任务服务与执行端分离，复用现有记录／监督／取消／媒体；61 项回归通过，新增 13 项远程协议与故障检查。实际独立进程与数据目录的 HTTP 联调、真实 MuJoCo、TCP 断线补传、取消和主动停止均通过，见 [远程验证](REMOTE_VALIDATION.md)。当前仅本机验证，远程默认关闭，无云资源或实机执行。

## 2026-10-17 短墙路线增量

新增 `staggered_walls` 路线白名单和服务器受限控制参数快照／CLI 传递，完整回归 62 项通过。真实浏览器通过远程执行端完成三点短墙任务；同一路线断线补传、取消、主动关闭与独立 6 s 时限超时检查通过，历史结果见 [演示证据](../../docs/demo.md)。模型、机器人控制与云服务未变更。
