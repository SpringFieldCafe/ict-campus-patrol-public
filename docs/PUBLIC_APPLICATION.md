# 公开应用源码的运行范围

> 本文表格和JSON为公开首发验证记录，源码哈希对应当时版本。后续前端依赖修复使用独立安装环境，最新结果与哈希见 [依赖修复记录](DEPENDENCY_REPAIR.md)。

本仓库公开静态成果展示、Vue 工作台、FastAPI 服务、任务与媒体协议、离线视觉评测准备和原创工具。机器人／仿真原始实现、Go2 XML／OBJ、模型权重和私有业务数据没有随本仓库分发。**该公开子集不能单独复现真实导航或 MuJoCo 仿真，也不代表已完成赛事的完整开源复现、华为云部署或云服务关联要求。**

成果展示站与工作台是两个入口：成果站直接展示已核实的历史结果；`apps/web` 工作台需要本地 FastAPI、登录账号和相应执行端，不能直接上传其 `dist` 就变成完整静态应用。源码中的仿真／运动接口保留集成契约；没有对应外置实现时，实际执行功能不可用。

## 新克隆安装与本地运行

从仓库根目录执行。需要 Node.js >=22.12、pnpm 10.34.0 和 uv；后端锁文件要求 Python 3.14。安装动作会访问各自软件源，平台下载及依赖服务的条款另计；不需要创建华为云资源。

```bash
uv sync --project cloud/backend --python 3.14 --locked
cloud/backend/.venv/bin/python cloud/backend/scripts/init_local.py
pnpm --dir apps/web install --frozen-lockfile
pnpm --dir apps/web build
bash cloud/backend/run.sh
```

浏览器打开 `http://127.0.0.1:8000`，接口文档为 `http://127.0.0.1:8000/docs`。服务默认只监听本机、单 worker。`init_local.py` 创建本机私有 `.env` 和随机凭据；在本机查看账号密码，不将文件或凭据提交到 Git。账号 SQLite 和任务文件存于被忽略的 `.local` 数据目录。

只使用此公开仓库、保持默认配置时，可以登录、查看两条人工示例路线、一个示例观察点和空的任务历史。`simulation_configured`、`motion_enabled`、`huawei_configured` 均为 `false`；仿真请求返回 `503 / SIMULATION_NOT_CONFIGURED`，运动请求返回 `409 / MOTION_DISABLED`，不会制造成功任务或真实模型回答。

`edge/go2/simulation/routes.json` 与 `edge/go2/runtime/observation-points.example.json` 只是人工示例配置；两个路径的存在不代表相关执行实现已分发。`SIM_SOURCE` 等变量可指向操作者已取得使用许可的外置仿真环境与权重。真实机器人接口仍依赖未随本仓库分发的运行部分，不能仅凭设置 `MOTION_ENABLED=true` 使用；不提供实机可用承诺。

## 离线视觉准备

只需安装后端依赖，不需要生成后台账号配置、启动 API、连接机器人或配置模型。

```bash
bash cloud/backend/vision-eval.sh check
bash cloud/backend/vision-eval.sh run --mock
```

当前清单是 **3 个待拍摄模板、0 张实际图片**。两条命令得到 `WAITING_FOR_IMAGES`；报告的模型效果为 `false`，人工通过率为 `null`。本次没有真实模型请求，也没有替身题目请求。报告写入本机忽略区 `.local/vision-eval`。补图、授权、参考事实、显式真实调用和人工核对流程见 [视觉评测说明](../evaluation/vision/README.md)。

## 已执行的验证

2026-10-19，在此公开副本中复用原工作机已有的隔离依赖，没有升级或重新下载环境。因此这是**公开目录下的验证**，不是全新机器安装证明。Python 为 3.14.8、Node 为 24.22.0、pnpm 为 10.34.0。

| 检查 | 结果 |
| --- | --- |
| `bash cloud/backend/test.sh -q` | 74 项通过 |
| `pnpm --dir apps/web test:run` | 4 个文件、22 项通过 |
| `pnpm --dir apps/web build` | TypeScript 检查与 Vite 生产构建通过 |
| CodeArts 工具离线测试 | 5 项通过；没有调用真实 CodeArts |
| 视觉空清单检查与 mock 报告 | 3 pending、0 ready、0 模型请求 |
| FastAPI TestClient 应用检查 | 健康、登录、权限、示例配置、空历史、明确拒绝未配置执行、构建页面与刷新路径通过 |

后端首轮有 9 项照片／问答夹具因缺少未公开机器人 CLI 失败，另 65 项通过。公开副本的 `tests/conftest.py` 已将这处夹具改为读取显式的临时人工配置，随后原有 74 项全通过；没有复制未许可代码，也没有修改业务执行逻辑。这些测试中的图片、视频和执行器均是人工替身，不提供真实视觉或机器人效果指标。

后端出现一条上游 TestClient 对 httpx 的弃用提示；前端构建忽略两处上游 VueUse 的 PURE 注释，构建成功。未因此升级依赖。

机器可读结果和关键源码哈希见 [public-application.json](validation/public-application.json)。历史开发验证文档中的真实仿真结果来自原私有开发环境；它们不能代替此公开子集的完整复现证明。本次没有新建云资源、调用华为视觉模型、运行真实机器人或重跑 MuJoCo。
