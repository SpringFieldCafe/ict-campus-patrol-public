# 应用依赖告警快照

2026-10-19，GitHub 对本公开仓库报出 **61 条未关闭依赖告警记录**，包括 2 critical、35 high、23 medium、1 low；共 **41 个不同 GHSA**，声明与锁文件可能重复计数。来源为 GitHub Dependabot API，不是本项目漏洞利用验证结果。

当前记录均指向 `apps/web/package.json` 或 `apps/web/pnpm-lock.yaml`。两项 critical 对应开发依赖 tinypool（当前锁定 2.1.0）：

- [GHSA-5gmw-xhrv-c9v3](https://github.com/advisories/GHSA-5gmw-xhrv-c9v3)，API 列出的首个修复版本 2.1.1。
- [GHSA-85c8-ppgw-ccpr](https://github.com/advisories/GHSA-85c8-ppgw-ccpr)，API 列出的首个修复版本 2.1.2。

是否能在本项目触发、直接／传递依赖应如何升级，需要独立核查；不把“测试通过”当作没有漏洞，也不把每条声明告警视为已证实的应用可利用问题。本次没有升级依赖、修改原导航／仿真环境或关闭告警。

GitHub Pages 只部署 `docs/` 原生 HTML/CSS/JS/图片/JSON；工作流不安装前端依赖，也不部署 `apps/web/dist`。上述告警属于另一套 Vue 工作台源码；这一区分不替代后续对应用依赖的修复。

建议单独开分支核对锁定版本、上游公告与实际用途，按最小改动修复，再运行前端测试／类型检查／生产构建。原私有仓保留其已验证环境，是否同步修复另行明确。

[机器可读快照](validation/dependency-alerts.json)保存统计及两个公开公告。管理者可在 [Dependabot 告警页](https://github.com/SpringFieldCafe/ict-campus-patrol-public/security/dependabot)查看完整记录。漏洞反馈见 [SECURITY.md](../SECURITY.md)。
