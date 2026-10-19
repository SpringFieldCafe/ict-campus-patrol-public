# 本地前后端验证

> **历史环境记录：**下文记录原私有开发环境在 2026-10-16～17 的验证，包含未随公开仓库分发的仿真实现与资产。不能用这些记录推断新克隆可完成真实仿真。公开副本 2026-10-19 的 22 项前端测试、构建及后端范围见 [公开应用说明](../../docs/PUBLIC_APPLICATION.md)。

日期：2026-10-16，Ubuntu 22.04。本轮改动由 Codex 实施；CodeArts 真实审查源码和初次构建日志，并提出失败轮询退避建议，后续代码与运行检查仍由 Codex 完成，见 [CodeArts 核对记录](../../docs/codearts-evidence.md)。

## 实际环境

- Node.js 24.22.0 官方 Linux x64 包，按官方 `SHASUMS256.txt` 校验，SHA256 `cc2f601cee82d9a5a233302fe307abc600727035fd7d2c3a3571755989e95008`。
- pnpm 10.34.0；Vue 3.5.39、Vite 7.3.6、TypeScript 5.9.3、Vitest 4.1.10；完整版本由 `pnpm-lock.yaml` 固定。
- 浏览器工具 Playwright 1.64.1，Chromium 156.0.8078.4；工具与浏览器在 `.local/browser-tools`，不提交二进制。
- 后端使用原有隔离 Python 3.14.8；MuJoCo 沿用已有运行环境与本地资产，没有升级机器人环境。

## 本机检查

| 检查 | 实际结果 |
| --- | --- |
| `bash apps/web/run.sh typecheck` | 通过；生产构建也运行 `vue-tsc` |
| `bash apps/web/run.sh test:run` | 4 文件、22 项通过，其中 8 项新增 FastAPI 协议／认证／媒体约束检查；其余为上游组件／工具测试 |
| `bash apps/web/run.sh build` | 生产构建成功，Vite 7.3.6；成品位于忽略目录 `apps/web/dist` |
| `bash cloud/backend/test.sh -q` | 41 项通过；其中 26 项覆盖 SPA 刷新、资产、未知 API、私有文件及越界符号链接；一个上游 TestClient 弃用提示不影响结果 |
| 前端新增页面 ESLint／后端 Ruff／`git diff --check` | 通过 |

## 真实浏览器与仿真

通过 `http://127.0.0.1:8000` 使用真实账户登录，网页向真实 API 提交 `demo-a` 仿真任务，任务号 `task-106fd51d075b4275a64ff9931216e86c`。

- 状态 `SUCCEEDED`，`goal_reached=true`、`collision=false`、`fallen=false`。
- 仿真摘要 `elapsed_s=17.0386` 是该次 runner 记录的墙钟时间，不是实机性能指标；仅此一次平地／单点场景不能推断导航成功率。
- 认证取回并在 Chromium 解码录像：640×480、2.8 秒。录像是 MuJoCo 场景视角，照片不可用，问答状态 `NO_CAMERA_PHOTO`。
- 未登录重定向、错误密码、JWT 当前标签页存储、刷新恢复、历史详情、离页停止轮询均通过。
- 浏览器拦截只读 GET 模拟断线：保留已有任务／录像、显示中断、手动恢复通过。模拟后端 `403 credentials` 后清理会话并返回登录页。
- 1440×1000 桌面检查；390×844 窄屏实际页面宽度为 390，无页面横向溢出；页面脚本异常为零。

[真实任务报告](../../docs/validation/web-real-simulation.json) · [最终成品浏览器复查](../../docs/validation/web-browser-final.json) · [截图与演示](../../docs/demo.md)。检查脚本没有保存密码、JWT、浏览器存储快照或登录填密码截图。

## UI 接口替身验证

另用隔离浏览器上下文拦截全部 API，照片上及截图内标明 `UI TEST FIXTURE`，不接实机、真实相机或云模型。7 项通过：照片解码／提问成功、任务号错配隐藏、照片 SHA256 错配隐藏、HTML 回答保持普通文本、取消仅等待执行端确认、未知提交先核对再允许手动新任务，以及只读查询失败退避。

连续失败后实测重读约 2 秒、4 秒；手动重试约百毫秒发起，恢复后自动读取约 1 秒；该场景未发送 POST。失败退避只适用于只读查询，不自动重发任务或模型分析。[替身报告](../../docs/validation/web-ui-fixtures.json)。这部分不构成真实照片、模型回答或物理停车证据。

## 复现浏览器检查

以下为历史环境的检查方法。UI 接口替身只需要已构建页面；真实仿真步骤还须另行取得执行实现、资产与权重的使用授权并配置外置环境。先按前后端 README 安装并启动本地成品。浏览器工具独立安装：

```bash
npm install --prefix .local/browser-tools playwright@1.64.1 --no-audit --no-fund
PLAYWRIGHT_BROWSERS_PATH="$PWD/.local/browser-tools/browsers" node .local/browser-tools/node_modules/playwright/cli.js install chromium
# 完全拦截 API 的 UI 替身测试，不读真实密码：
node apps/web/tests/e2e/ui-fixtures.mjs
# 读取本机 .env 登录；只显式启动 MuJoCo 仿真，不接运动 SDK：
WEB_QA_RUN_SIM=1 node apps/web/tests/e2e/live-smoke.mjs
```

本机工具链没有加入系统 PATH 时，先按前端 run.sh 所用的 `.local/toolchains/node-v24.22.0-linux-x64/bin` 设置 PATH。脚本从自身位置寻找仓库，默认 UI 为 `8000`；开发预览可设 `WEB_QA_ORIGIN=http://127.0.0.1:5173`。报告和截图写入忽略区 `.local`。真实仿真检查需要后端完成已有 MuJoCo、模型和场景资产配置；新克隆缺少这些外置资产时不能直接声称复现成功。未设 `WEB_QA_RUN_SIM=1` 的 live-smoke 只读已有任务，需已有可播放仿真录像。

## 仍未验证

真实运动、物理停车、真实相机帧与照片质量；华为模型的真实回答、费用和效果；跨公网的云端到现场端通道、华为云部署、公开访问、云产品关联和干净环境完整比赛复现。当前只监听本机，没有创建云资源。

## 2026-10-16 顺序 checkpoint 增量

工作台增加服务器预设仿真路线选择、路线说明及 checkpoint 完成数展示。22 项测试、TypeScript 和生产构建通过；浏览器已在历史完整环境真实提交三点 MuJoCo 任务并读取完成录像，见 [演示证据](../../docs/demo.md)。

## 2026-10-17 远程任务增量

复用同一工作台，新增执行端在线／准备状态、本地暂停准入、断线待确认和结果回传提示。22 项前端测试、TypeScript 与生产构建通过；10 项浏览器接口替身通过，新增 3 项远程状态场景。真实评委账号已通过两个独立 HTTP 角色驱动三 checkpoint MuJoCo 并播放回传录像，见 [远程验证](../../cloud/backend/REMOTE_VALIDATION.md)。本轮由 Codex 实施，不归入 CodeArts 贡献；未创建云资源。

## 2026-10-17 短墙路线验证

现有路线选择器按 API 动态显示 `checkpoints-walls`，沿用已构建的网页组件，未修改前端运行代码或依赖。浏览器测试增加显式路线选择，通过实际评委账号在独立服务端／执行端间完成三点绕墙和录像回传，Chromium 解码 640×480、19.38 s；刷新、历史、窄屏、会话过期与零页面异常均通过。脚本 ESLint 通过，选择器初次定位失败与修正保留于原开发记录；公开的结果见 [演示证据](../../docs/demo.md)。
