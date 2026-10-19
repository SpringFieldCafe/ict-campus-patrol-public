# 公开发布实测记录

2026-10-19 已创建 [SpringFieldCafe/ict-campus-patrol-public](https://github.com/SpringFieldCafe/ict-campus-patrol-public)，以独立的新 Git 历史发布许可清楚的子集。原业务仓仍为私有，没有推送原 Git 历史。

## 首次自动发布

- [公开成果站](https://springfieldcafe.github.io/ict-campus-patrol-public/)：HTTPS，Pages Source 为 `workflow`，`https_enforced=true`。
- 初始提交：`e33c817fca96547e96cdc31ead1407a0f58b76b3`。
- [首次自动工作流](https://github.com/SpringFieldCafe/ict-campus-patrol-public/actions/runs/39194900159)：事件 `push`，结论 `success`；Checkout、Setup Pages、Upload artifact、Deploy to GitHub Pages 全部成功。
- deploy job：UTC `2026-10-19T03:29:08Z` 至 `03:29:21Z`（北京时间 11:29）。
- 原业务仓可见性仍为 private，公开仓为 public，默认分支 main。
- 新公开仓已启用 GitHub 私密漏洞报告；不向其他仓库或账号添加设置。

## 公网浏览器检查

使用现有隔离 Playwright／Chromium 工具实际访问公网地址。桌面 1440×1000 与手机 390×844 均 HTTP 200、图片全部加载、无水平溢出、零脚本异常、零失败请求、零第三方资源请求。

评测切换：墙体 80%、15 个用例含 3 次碰撞；侧箱 100%，失败用例详情可查看。历史结果保留，没有在线任务或模型请求。[公网机器记录](validation/static-site-live.json)与[本机页面记录](validation/static-site.json)分开保存。

第二次更新提交 `cd035fc63f4770b56ad73a1e6eecc2d7e4a08626` 的 [push 工作流 39195012205](https://github.com/SpringFieldCafe/ict-campus-patrol-public/actions/runs/39195012205)也已 success；公网已返回更新后的“静态展示已上线”文案，确认推送更新可以自动生效。以 [Actions 历史](https://github.com/SpringFieldCafe/ict-campus-patrol-public/actions/workflows/pages.yml)查看每次推送的实际结果，不需要人工调用大模型发布。

## 范围与来源

[应用测试](PUBLIC_APPLICATION.md)：后端 74 项、前端 22 项、工具离线 5 项和生产构建通过；依赖复用原工作机隔离环境，不是新机器安装证明。

[官方 Actions 模板与固定版本](HOSTING.md)、[CodeArts 两轮真实贡献](codearts-evidence.md)、[发布前检查](validation/release-preflight.json)、[公开范围](RELEASE_SCOPE.md)均随仓库提供。

本次只发布静态成果和许可明确的源码子集，未创建付费云资源、未调用华为视觉模型、未运行机器人或新跑真实仿真。华为云 Skills 服务关联、华为云业务部署与完整作品开源／复现仍未由本次发布解决。


## 发布后依赖检查

GitHub 后续发现应用前端依赖告警，另见 [依赖快照](DEPENDENCY_STATUS.md)。本轮静态发布不运行这些应用依赖，未对其升级；仍需要独立核查与修复，不能以本次部署成功消除告警。
