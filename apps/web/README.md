# 本地任务工作台

> **公开子集说明：**本目录的源码、测试和构建可运行，但完整工作台需要 FastAPI。机器人／MuJoCo 执行实现、Go2 资产与权重未随本仓库分发，默认不能实际执行仿真或运动。下文保留接口及历史集成用法；新克隆的实际运行范围和 2026-10-19 验证见 [公开应用说明](../../docs/PUBLIC_APPLICATION.md)。本目录不是静态成果站的发布目录。

基于 V3 Admin Vite 的 Vue 3／TypeScript／Element Plus 应用，连接 `cloud/backend` 的真实 FastAPI 接口。电脑浏览器优先，保留窄屏布局。

## 安装和启动

前置：Node.js >=22.12（本机使用官方 Node 24.22.0）、pnpm 10.34.0；后端独立 Python 环境见 [后端说明](../../cloud/backend/README.md)。锁文件安装：

```bash
cd apps/web
pnpm install --frozen-lockfile
pnpm build
cd ../..
bash cloud/backend/run.sh
```

成品入口 `http://127.0.0.1:8000`，API 文档 `http://127.0.0.1:8000/docs`。构建后首次接入页面需重启后端；服务只监听本机。不需要额外静态服务器。

若 Node／pnpm 已安装在 PATH，可在仓库根目录使用封装脚本；脚本也支持操作者自行准备的 `.local/toolchains`，该本机目录不随仓库分发：

```bash
bash apps/web/run.sh install --frozen-lockfile
bash apps/web/run.sh build
bash cloud/backend/run.sh
```

开发时另开终端运行 `bash apps/web/run.sh dev`，预览 `http://127.0.0.1:5173`；开发代理将 `/api/v1` 转到 `8000`。端口占用会明确退出，不自动换端口。后端已启动则沿用，不再启动第二个进程。可通过非公开构建变量 `CAMPUS_API_TARGET` 修改开发代理；成品默认使用同源 API。

账户和初始密码在本机 `cloud/backend/.env`，由后端初始化脚本创建；使用 `FIRST_SUPERUSER`／`FIRST_SUPERUSER_PASSWORD`，不要粘贴到聊天或提交。前端不提供演示密码或注册入口。

```bash
bash apps/web/run.sh typecheck
bash apps/web/run.sh test:run
bash apps/web/run.sh build
```

## 页面和接口

| 页面／交互 | 后端接口 |
| --- | --- |
| 登录／恢复会话 | `POST /api/v1/login/access-token`（OAuth2 表单）、`GET /api/v1/users/me` |
| 工作台配置与观察点 | `GET /api/v1/capabilities`、`GET /api/v1/points` |
| 发任务／最新状态 | `POST /api/v1/tasks`、`GET /api/v1/tasks/{id}` |
| 任务阶段／取消请求 | `GET /api/v1/tasks/{id}/events?after=...`、`POST /api/v1/tasks/{id}/cancel` |
| 历史与详情恢复 | `GET /api/v1/tasks?offset=...&limit=...`、`/console?task={id}` |
| 原图／录像 | `GET /api/v1/tasks/{id}/photo`、`GET /api/v1/tasks/{id}/video` |
| 对已有照片提问 | `POST /api/v1/tasks/{id}/analysis` |

使用后端原生 JSON，不要求改成模板 mock 的 `{code,data}`；所有业务及媒体请求带 Bearer。当前部署约定同源 `/api/v1`，媒体地址严格限定此路径下的任务照片／录像；修改 API 前缀时需同步开发代理及媒体白名单，不能仅改 VITE_BASE_URL。JWT 仅存当前标签页的 sessionStorage，不把密钥放进 VITE 变量、URL 或媒体链接。媒体经认证取 Blob，在换任务／离页时撤销 Blob URL。分析结果按普通文本呈现。

任务状态正常时按秒查询，连续读取失败则退避至最多 10 秒，手动重试立即查询，恢复后回到 1 秒；不重发创建／取消／分析请求。刷新页面可继续查看后端任务。取消只是提交请求，是否停车以最终状态及执行端应答为准。单任务、忙时拒绝、90 s 默认时限和不自动重试仍由后端执行。请求失败时显示真实错误，不生成假照片、假回答或假任务成功。

`simulation` 只显示已有 MuJoCo 进展与场景录像，明确不是机器狗相机。`motion` 默认关闭；本次未执行实机。华为模型尚未开通，模型／密钥配置在后端；前端依 capability 状态开放图片问答。

来源和改动范围见 [UPSTREAM.md](UPSTREAM.md)，历史检查见 [VALIDATION.md](VALIDATION.md)。可视化 Demo 是本地进展，华为云部署、云服务关联、实机与真实模型评测仍需完成，见 [公开应用边界](../../docs/PUBLIC_APPLICATION.md)。

## 顺序 checkpoint 仿真

后端 capabilities 提供仿真路线时，工作台默认选择 `checkpoints-simple`；也可改为“单个观察点”。路线卡片显示按序点位与到点半径，任务进度显示已完成数／总点数。路线只用于仿真，不改变实机观察点配置。公开仓库保留示例路线与接口，执行实现和模型需操作者另行取得使用授权；仅看到路线不表示仿真已配置。范围见 [仿真说明](../../edge/go2/simulation/README.md)，历史结果见 [演示证据](../../docs/demo.md)。

## 依赖维护与自动检查

2026-10-19公开副本的依赖修复与剩余风险见 [记录](../../docs/DEPENDENCY_REPAIR.md)。新增前端CI复用GitHub官方Node模板，对apps/web或工作流改动做锁定安装、生产构建与测试；[来源与范围](../../docs/FRONTEND_CI.md)。原私有导航／仿真环境不自动同步更新。
