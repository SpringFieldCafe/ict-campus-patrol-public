请作为华为CodeArts审查这个新增前端CI工作流，输出简洁 REVIEW 和 DOC_PATCH（Markdown段落即可），无需包配置或重复第一轮。你实际仅静态审查，不直接执行工具或部署。用户要求复用别人的GitHub Actions，且每轮实际邀请你参与。下面工作流基于GitHub官方Node.js starter commit1830845916d09bee7327d12cbf1e387edfdb9846，原MIT GitHub2020许可已在仓保留。仅将main、apps/web目录、Node24、pnpm10.34.0、frozen安装/build/test:run和3个官方Action经GitHubAPI核验的完整SHA适配。无workflow秘密，contents read，无pull_request_target，不运行机器人/后端/模型。pnpm action-setup@v4的package_json_file=apps/web/package.json和显式version10.34.0均相同，以免版本冲突。Node24安装在pnpm setup后且cache-dependency-path明确。请核对目录、版本、权限、PR执行语义、缓存和最小改动是否正确；如果确有问题，给具体最小改动，不能凭空建议升级所有Action。

原项目本机pnpm工具实际是10.34.7，Codex未修改它；在独立工作树下载官方10.34.0 tarball并校验SHA512完整性，安装/验证均用隔离10.34.0与已有Node24.22.0。原仓node_modules不触碰。前轮由你生成的package.json已核对应用，仅收窄brace-expansion >=4到>=5以避免潜在跨主版本；16overrides与axios/vue/vitest版本更新、4个未使用Vxe文件删除方案其他内容采纳。当前锁重新解析已完成，正在独立安装；尚未测试，不可预填通过。

后续会推独立修复分支，创建PR，CI执行成功后再更新GitHub状态。默认分支关闭告警必须实际合入/扫描确认，分支audit与GitHub61记录不可混用。pnpm基线63，braces无补丁保留未解决，不通过忽略规则归零。CodeArts已提醒真实分工与风险，记录继续保留。

请给适合纳入docs/FRONTEND_CI.md的一个中文段落，主笔明确：CI复用官方模板、做哪些检查、不会上传docs到该流程（Pages另一个workflow）、没有真实模型/云资源、实际结果待GitHub运行验证。

工作流：
# Adapted from GitHub actions/starter-workflows/ci/node.js.yml (MIT, Copyright 2020 GitHub).
# Source commit: 1830845916d09bee7327d12cbf1e387edfdb9846
# Changes: pnpm 10.34.0, apps/web, Node 24, fixed Action commits, project test/build scripts.
# License: docs/upstream/github-pages-starter-LICENSE; provenance: docs/FRONTEND_CI.md.
# This workflow will do a clean installation of node dependencies, cache/restore them, build the source code and run tests across different versions of node
# For more information see: https://docs.github.com/en/actions/automating-builds-and-tests/building-and-testing-nodejs

name: Frontend checks

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

permissions:
  contents: read

jobs:
  build:

    runs-on: ubuntu-latest

    defaults:
      run:
        working-directory: apps/web

    strategy:
      matrix:
        node-version: [24.x]
        # See supported Node.js release schedule at https://nodejs.org/en/about/releases/

    steps:
    - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
    - uses: pnpm/action-setup@f40ffcd9367d9f12939873eb1018b921a783ffaa # v4
      with:
        version: 10.34.0
        package_json_file: apps/web/package.json
        run_install: false
    - name: Use Node.js ${{ matrix.node-version }}
      uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4
      with:
        node-version: ${{ matrix.node-version }}
        cache: 'pnpm'
        cache-dependency-path: apps/web/pnpm-lock.yaml
    - run: pnpm install --frozen-lockfile
    - run: pnpm build
    - run: pnpm test:run

