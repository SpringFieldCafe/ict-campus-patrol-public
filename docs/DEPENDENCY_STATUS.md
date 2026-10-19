# 应用依赖状态

2026-10-19，在独立修复分支完成本地前端验证：pnpm10.34.0审计从63条降到1条（0 critical、1 high）。22项测试、类型检查与生产构建、桌面／手机接口替身检查均通过。剩余为无已公布补丁的 [braces GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)，没有通过忽略规则归零。

GitHub默认分支的原61条告警是否关闭，须以合入后实际扫描为准；本分支本地结果不能替代GitHub状态。最新过程与验证见 [依赖修复记录](DEPENDENCY_REPAIR.md)、[机器记录](validation/dependency-repair.json)。

## 保留初始快照

公开首发时GitHub报61条告警记录，2 critical、35 high、23 medium、1 low，对应41个不同GHSA；包声明与锁文件可能重复计数。[初始快照](validation/dependency-alerts.json)保持原样，不能与pnpm的63条基线混用。两项critical来自eslint-plugin-format→oxfmt→tinypool2.1.0，本轮覆盖为2.1.2；不是Vitest直接依赖。

Vxe Table尚无可信修复版本，本项目移除了未使用的示例、插件、专用样式及依赖，不把升级出公告范围当作漏洞已修复。实际业务路由不使用它。

GitHub Pages只部署docs中的静态文件，不安装或加载这些应用依赖；这一区分不替代对源码依赖的维护。原私有导航／仿真环境没有升级。

管理者可查看 [GitHub Dependabot](https://github.com/SpringFieldCafe/ict-campus-patrol-public/security/dependabot)。漏洞反馈见 [SECURITY.md](../SECURITY.md)。
