请实际审查这份基于 GitHub 官方 actions/starter-workflows/pages/static.yml 的最小适配，主笔 docs/MAINTENANCE.md（约600-900中文字），另给可写进 AGENTS.md 与 README 的简短协作约定。输出Markdown，分为 REVIEW、MAINTENANCE、AGENTS、README 四段。不要调用工具，不要冒称你执行了测试或部署。

用户新指示：以后推送就由GitHub Actions自动部署，不需要手动调用大模型；尽量复用他人方案。用户又明确要求每轮相关工作都实际邀请 CodeArts 参与，将约定写进 AGENTS.md 与 README，贡献记录必须真实。授权创建独立公开仓库和静态站已确认，不要再次要求授权。

事实：新仓库 SpringFieldCafe/ict-campus-patrol-public；全新历史，只公开许可清楚的网页/后端/相关测试、视觉评测准备、原创工具/结果/无机器人渲染图片。原业务仓继续私有。机器人运行实现/Go2 XML/OBJ/权重/渲染录像暂缓。静态页位于 docs/index.html，CSS/JS/images/data均相对路径，不运行Vite应用或API；apps/web 是另一套依赖后端的工作台，不能误把它的dist作为完整在线应用。本次自动部署不需要编译Node，不需华为AK/SK、不需模型密钥、不调用CodeArts或其他AI、不新建华为云资源。GitHub将源设置为Actions，main每次push自动发布docs；workflow_dispatch只保留手动重试。未来改docs可用普通编辑器，git add/commit/push即可；更新JSON要核对指标与历史来源，图片需核对许可与隐私。未经授权资产不可因自动发布纳入。仅推送公开仓main触发部署，私有仓更新不会自动复制/同步。

需要清楚区分：每轮相关开发/文档工作，Codex应在有本机可用福利入口时实际让CodeArts承担有意义的小范围审查/文档或代码任务，保存请求/回答/脱敏回执、列人工改动和验证结果，不编造它亲自执行。零现金预算；无福利额度/登录不可用则如实记录并与用户沟通，不切付费模型、不购买服务。这个协作约定约束开发助手，不把AI调用放进每次GitHub Actions发布。若任务纯机械检查且没有实际可交付给CodeArts的内容，说明原因而非造贡献。用户说每次阅读就调动它，不应被解释为每次git push都调用云模型。

现状：公开副本后端74、前端22、工具离线5项通过，生产构建通过；依赖复用原工作机隔离环境，不是新机器安装证明。视觉0图片0请求，真实仿真和机器人/云未在公开副本验证。网站和GitHub仓尚未正式发布，不得声称部署已成功，后续以实际Actions结果填证据。你本次实际贡献为Actions方案审查+维护说明/协作约定主笔，Codex负责模板下载/版本API核对、实际文件应用、浏览器QA、GitHub创建和部署。

模板出处：https://github.com/actions/starter-workflows/blob/22770e21c6986ed08a3aa400bdcc6a9a75ecdaf2/pages/static.yml ，MIT GitHub2020。原模板结构保持，修改main、上传路径docs、4个Action固定到其实际主版本标签当前40位提交。最小权限 contents read/pages write/id-token write，github-pages environment，串行并发不取消进行中部署。模板如下：

# Adapted from actions/starter-workflows/pages/static.yml (MIT, Copyright 2020 GitHub).
# Source commit: 22770e21c6986ed08a3aa400bdcc6a9a75ecdaf2
# Changes: main branch, docs-only artifact, immutable Action commit pins.
# License and provenance: docs/upstream/github-pages-starter-LICENSE, docs/HOSTING.md.
# Simple workflow for deploying static content to GitHub Pages
name: Deploy static content to Pages

on:
  # Runs on pushes targeting the default branch
  push:
    branches: [main]

  # Allows you to run this workflow manually from the Actions tab
  workflow_dispatch:

# Sets permissions of the GITHUB_TOKEN to allow deployment to GitHub Pages
permissions:
  contents: read
  pages: write
  id-token: write

# Allow only one concurrent deployment, skipping runs queued between the run in-progress and latest queued.
# However, do NOT cancel in-progress runs as we want to allow these production deployments to complete.
concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  # Single deploy job since we're just deploying
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
      - name: Setup Pages
        uses: actions/configure-pages@983d7736d9b0ae728b81ab479565c72886d7745b # v5
      - name: Upload artifact
        uses: actions/upload-pages-artifact@56afc609e74202658d3ffba0e8f6dda462b719fa # v3
        with:
          # Upload the public static site only
          path: 'docs'
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346 # v5

