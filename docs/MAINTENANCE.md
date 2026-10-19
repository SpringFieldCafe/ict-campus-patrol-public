# 维护说明（公开静态站）

## 部署链路
公开仓 SpringFieldCafe/ict-campus-patrol-public 使用 GitHub Actions 部署静态站。
将 Pages 源设置为 GitHub Actions 后，main 分支每次 push 会自动把 docs/ 发布到
GitHub Pages；workflow_dispatch 仅用于手动重试。部署不需要 Node 编译，不需要
华为 AK/SK 或模型密钥，也不在发布流程中调用任何 AI。

## 前置设置
- 仓库 Settings → Pages → Build and deployment → Source 选择 "GitHub Actions"。
- github-pages 环境由首次部署自动创建，站点 URL 取自部署步骤输出。
- workflow 文件必须位于 .github/workflows/ 下；改动需提交并推送到公开仓才生效。

## 日常维护
1. 用普通编辑器修改 docs/（index.html、CSS/JS、images/data 均为相对路径），
   git add/commit/push 即可发布，无需本地构建。
2. 更新 docs/data 下 JSON 前，先核对指标数值与历史来源，避免覆盖既有统计口径。
3. 新增图片前核对许可与隐私；未经授权或含未获同意的真实人员影像的资产不得因自动发布纳入。
4. 推送后在 Actions 页观察运行结果，以实际部署结果填写证据与文档。

## 修改 workflow 的注意点
- 本 workflow 改编自 actions/starter-workflows/pages/static.yml（MIT，
  Copyright 2020 GitHub），来源提交已记录在文件头，许可见
  docs/upstream/github-pages-starter-LICENSE，部署背景见 docs/HOSTING.md。
- 4 个 Action 固定到 40 位提交；升级版本时必须重新核对提交与官方 tag 的对应。
- 上传工件仅为 docs 目录；apps/web 是依赖后端的独立工作台，其 dist 不能作为
  完整在线应用上传。
- 权限保持最小（contents read、pages write、id-token write）；并发组串行且
  不取消进行中的部署，勿随意放宽。

## 回滚与排查
- 回滚站点：revert 对应提交后 push，自动重新发布；workflow_dispatch 只重跑，
  不改变已提交内容。
- 部署失败优先检查：workflow 文件位置、Pages 源设置、docs 内文件体积、
  Action 提交与 tag 的对应关系；必要时用 workflow_dispatch 手动重跑确认。
- 仅公开仓 main 的 push 触发部署；私有仓更新不会自动复制或同步到公开仓。

本维护说明由 CodeArts 主笔，Codex 核对并应用；[原始审查与说明](codearts/2026-10-19-pages-actions-response.txt)、[贡献与校正](codearts-evidence.md)。本文件描述运维方式；实际首次部署结果见 [发布记录](PUBLICATION.md)。
