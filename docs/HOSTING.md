# 静态托管与 Actions 来源

发布目标为 [GitHub Pages](https://springfieldcafe.github.io/ict-campus-patrol-public/)，公开仓库 [SpringFieldCafe/ict-campus-patrol-public](https://github.com/SpringFieldCafe/ict-campus-patrol-public)。不购买域名或创建付费云资源。

## 复用官方方案

[工作流](../.github/workflows/pages.yml)改自 GitHub 官方 [actions/starter-workflows/pages/static.yml](https://github.com/actions/starter-workflows/blob/22770e21c6986ed08a3aa400bdcc6a9a75ecdaf2/pages/static.yml)，模板提交 `22770e21c6986ed08a3aa400bdcc6a9a75ecdaf2`，MIT Copyright 2020 GitHub；[完整许可](upstream/github-pages-starter-LICENSE)随附。

保留官方四个步骤、权限、并发和 github-pages 环境，仅作必要配置：默认分支占位符改为 `main`，上传路径从整个仓库改为 `docs`，四个 Action 按 2026-10-19 从官方 GitHub API 核验的主版本标签固定为完整提交。没有自写部署脚本，也没有把模型调用写进 CI。

| Action | 官方模板版本 | 固定提交 |
| --- | --- | --- |
| actions/checkout | v4 | `11d5960a326750d5838078e36cf38b85af677262` |
| actions/configure-pages | v5 | `983d7736d9b0ae728b81ab479565c72886d7745b` |
| actions/upload-pages-artifact | v3 | `56afc609e74202658d3ffba0e8f6dda462b719fa` |
| actions/deploy-pages | v5 | `368f82528645a54fb793d4d04e342629a3f51346` |

纯静态成果页不需要 Node 构建；Vue 工作台与 API 是另一套本地应用，不在此部署。Pages Source 设为 **GitHub Actions**；每次推送公开仓库 `main` 触发上传与部署，也保留 `workflow_dispatch` 以便失败重试。私有仓库不会自动同步到这里。

只使用 GitHub 自动提供的 GITHUB_TOKEN 与 Pages OIDC 权限，不需要个人访问令牌、华为 AK/SK 或模型密钥。发布权限为 `contents: read`、`pages: write`、`id-token: write`；不运行不受信任的 pull_request 代码。

公开仓库使用 GitHub 托管的标准 Linux runner 和 Pages；GitHub 官方的[计费说明](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions)与[Pages 说明](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)是免费范围依据，不承诺无限资源或未来政策不变。没有启用大型付费 runner、付费云服务或付费模型。

更新步骤与 CodeArts 协作边界见 [维护说明](MAINTENANCE.md)；首次部署实测另见 [发布记录](PUBLICATION.md)。
