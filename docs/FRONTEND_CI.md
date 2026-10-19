# 前端回归工作流来源

[frontend.yml](../.github/workflows/frontend.yml)复用 GitHub 官方 [Node.js CI 模板](https://github.com/actions/starter-workflows/blob/1830845916d09bee7327d12cbf1e387edfdb9846/ci/node.js.yml)，MIT，Copyright 2020 GitHub；[完整许可](upstream/github-pages-starter-LICENSE)已保留。

保留官方 checkout → 设置工具 → 安装 → 构建 → 测试流程，针对本项目将工作目录设为 apps/web，Node 为24，npm替换为锁定pnpm10.34.0；采用 [pnpm 官方 action-setup](https://github.com/pnpm/action-setup)安装包管理器。三个Action固定为2026-10-19从官方API核验的完整提交。

main push 和目标 main 的 pull_request 在改动 apps/web 或本工作流时执行 frozen-lockfile 安装、TypeScript/Vite生产构建与非交互测试。使用标准GitHub托管Ubuntu runner，contents只读，没有用户密钥或模型请求；不运行机器人、仿真或部署业务后端。Pages自动部署仍由原独立工作流负责。

本文件说明配置；实际CI结论在修复完成后根据GitHub运行结果记录，不把本地结果当作已运行的CI。

## CodeArts 审查与补充说明

前端 CI 复用 GitHub 官方 Node.js starter workflow（MIT，Copyright 2020 GitHub，来源提交 `1830845916d09bee7327d12cbf1e387edfdb9846`），仅做项目适配：触发范围收窄为 `main` 的 push 与 PR，工作目录限定 `apps/web`，使用 Node.js 24.x 与 pnpm 10.34.0 以 `--frozen-lockfile` 安装依赖，依次执行 `pnpm build` 与 `pnpm test:run`；`actions/checkout`、`pnpm/action-setup`、`actions/setup-node` 三个官方 Action 均以经 GitHub API 核验的完整提交 SHA 固定，权限仅 `contents: read`，无 workflow 秘密、无 `pull_request_target`，不运行机器人、后端或任何模型调用。该 workflow 只做依赖安装、构建与测试，不会上传或部署 `docs/`——GitHub Pages 发布由另一个独立 workflow 负责；本仓亦无真实云模型调用或云资源创建。实际运行结果以推送独立修复分支并创建 PR 后的 GitHub Actions 运行为准，运行成功前不预填通过状态。

该段由 CodeArts 主笔、Codex 核对应用。其“pnpm先安装”的说明仅针对当前启用pnpm缓存的步骤顺序，不是所有CI的唯一顺序。PR权限与配置审查不代表任意PR代码已被证明安全。

Codex 在审查后为 push／PR 补充 apps/web 与该工作流本身的路径过滤，纯成果文档更新继续只走 Pages；本次修复包含 apps/web 变更，会触发回归。
