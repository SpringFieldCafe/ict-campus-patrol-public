# Campus Patrol · 受限区域现场查看

[静态成果站](https://springfieldcafe.github.io/ict-campus-patrol-public/) · [公开范围](docs/RELEASE_SCOPE.md) · [运行与验证](docs/PUBLIC_APPLICATION.md) · [CodeArts 贡献](docs/codearts-evidence.md)

面向预设观察点的现场查看项目。本仓库公开许可清楚的应用源码、相关测试、原创评测工具与历史结果，以全新 Git 历史发布；原业务仓库继续私有。

**这是公开子集。导航运行实现、机器人模型、策略权重与含对应渲染的录像暂未分发，不能仅从此仓库复现真实仿真或实机任务。** GitHub Pages 只展示历史成果，不提供登录、在线任务或云端问答，也不代表完成华为云部署或赛事全部要求。

## 内容与实际进展

| 目录 | 内容与边界 |
| --- | --- |
| [docs](docs/README.md) | 无构建静态成果站、公开范围、验证与贡献记录 |
| [apps/web](apps/web/README.md) | Vue / TypeScript 工作台，依赖后端 API；保留 V3 Admin Vite MIT 许可 |
| [cloud/backend](cloud/backend/README.md) | FastAPI、认证、任务记录、远程任务协议与测试；默认真实执行关闭 |
| [evaluation/vision](evaluation/vision/README.md) | 离线视觉评测准备；3 个待拍摄模板、0 张真实图片、0 次模型请求 |
| [edge/go2/simulation](edge/go2/simulation/README.md) | 示例路线、原创评测脚本与历史记录，不含仿真运行实现 |
| [tools](docs/codearts-free-cli.md) | 本机 CodeArts 福利入口辅助脚本与离线测试；额度依账号规则 |

2026-10-19 公开副本验证：后端 **74 项**、前端 **22 项**、工具离线 **5 项**通过，TypeScript 与生产构建通过。复用了原工作机已隔离安装的依赖，不是全新机器安装证明。[详细范围与结果](docs/PUBLIC_APPLICATION.md)。

历史 MuJoCo 最终评测为侧箱 **15/15**，错位短墙 **12/15、3 次碰撞**；墙体成功率 **80%**。较差候选参数 **4/15** 也保留。[评测来源与限制](docs/demo.md)。这些历史结果来自原开发环境，不能作为本公开子集完整复现的证明。

## 本地查看成果站

需要 Python 3，从仓库根目录运行：

```bash
python3 -m http.server 8768 --bind 127.0.0.1 --directory docs
```

打开 `http://127.0.0.1:8768`。站点只使用本仓库的 HTML、CSS、JavaScript、图片和 JSON，无第三方 CDN、账号或模型密钥。

安装及运行工作台与 API、测试和离线视觉准备，见 [公开应用说明](docs/PUBLIC_APPLICATION.md)。没有外置且许可完备的执行实现时，仿真明确返回未配置，运动保持禁用。

## 比赛、贡献与许可

[赛事要求对照](docs/competition.md)区分初赛材料与决赛后续交付；本次发布不是正式报名或提交。CodeArts 实际主笔发布范围、提出发布审查问题；Codex 负责导出、测试、静态站实现与 GitHub 发布，见[贡献证据](docs/codearts-evidence.md)。

原创内容采用 [Apache-2.0](LICENSE)，第三方内容保留各自许可，见 [NOTICE](NOTICE) 与 [第三方台账](THIRD_PARTY_NOTICES.md)。前端 MIT 许可及 FastAPI 模板 MIT 声明均保留；根许可不覆盖未授权的旧实现、模型和资产。漏洞反馈见 [SECURITY.md](SECURITY.md)。

## 自动发布与协作

推送公开仓库 `main` 后，GitHub Actions 自动将 `docs/` 发布到 Pages；不调用大模型、不需要 Node 编译。复用 GitHub 官方模板，来源、许可与固定版本见 [HOSTING.md](docs/HOSTING.md)，后续编辑和回滚见 [维护说明](docs/MAINTENANCE.md)。私有仓库更新不会自动同步。

根据用户要求，每轮相关开发／文档工作均应实际邀请 CodeArts 承担有意义的小范围任务，遵循 [AGENTS.md](AGENTS.md)，使用已验证的福利入口并保留真实产出。额度或登录不可用时如实沟通，不切付费模型；纯机械检查不制造贡献。每次 GitHub 自动发布无需人工调用 AI。

前端依赖修复与验证见 [依赖状态](docs/DEPENDENCY_STATUS.md)：本地审计63→1，仍有无补丁的braces告警；GitHub默认分支状态按合入后扫描另核。静态成果站不加载或安装这些应用依赖。
