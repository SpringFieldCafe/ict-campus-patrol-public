# 前端依赖修复记录

本轮在独立公开仓分支完成本地修复验证：**22 项前端测试、TypeScript／Vite 构建、桌面／手机生产页面检查通过**。同一 pnpm10.34.0 审计从 **63 条降为 1 条**，critical 从 2 降为 0；仍有一个上游无补丁的 braces high 告警。PR #2已合入，GitHub原61条均确认为fixed、当前open为0；GitHub与pnpm是不同口径，仍保留上述braces风险。

下面方案正文由 CodeArts 主笔，保留其审查时的计划语态；实际结果与人工校正见文末。

## 背景与计数口径

公开仓 SpringFieldCafe/ict-campus-patrol-public 前端工作台收到 GitHub 61 条依赖告警，对应 41 个不同 GHSA，其中 2 条 critical 来自 tinypool；本地 pnpm audit 独立基线为 63 条（2 critical、43 high、17 moderate、1 low）。两套计数口径不同，不可混用，也不得互相推导。

## 分工

本文档由华为 CodeArts 主笔三项内容：apps/web/package.json 包配置（axios 1.20.0、vue 3.5.42、vitest 4.1.11，移除 vxe-table，新增 pnpm.overrides 共 16 条已核对注册表版本）；四个未使用 Vxe 文件的删除清单；依赖审查意见。实际删除、lock 解析、安装、测试与 PR 由 Codex 执行，成稿时尚未验证通过，验证结果以后续真实记录补齐，不得预填。

## Vxe 处理定性

vxe-table 上游 GHSA-89fp-f5mx-748x 仍无补丁版本，first_patched_version 为 null，PR #2791 仍 open。项目锁 vxe-table 4.6.25，但业务 router 仅 console/history/project，dynamic 为 false，plugins/index.ts、main.ts、styles/index.scss 均不加载 Vxe。因此本轮是移除未使用的脆弱组件及孤立传递依赖 dom-zindex、xe-utils，不是修复 Vxe 上游，不能把版本升出受影响范围当作已证明修复。common/apis/tables 仍被 ElementPlus 示例使用，保留；UPSTREAM 中“Vxe 资产保留”表述同步更新为已移除。

## 未解决项与兼容风险

braces@3.0.3（GHSA-vfj7-8cjw-p6xm）当前无修复版本，路径 unplugin-svg-component>fast-glob>micromatch>braces，属受控本地 SVG 构建工具。本轮不为告警归零伪造版本、不静默 audit ignore、不自制无证据安全补丁、不更换整套图标插件，预计仍保留一项明确未解决告警，真实可达性尚未评估。katex 0.16.47 → 0.18.2 跨 0.x 小版本，来自构建期链路 @antfu/eslint-config>@eslint/markdown>micromark-extension-math，非运行时业务依赖，须单列兼容性风险，由 Codex 核对 Markdown 数学解析/渲染 API 并完成构建验证。

## 验证计划与边界

新工作树 fix/frontend-dependency-alerts-20261019 基于 b032b03，创建独立 node_modules，绝不沿用或修改原仓软链接；以 pnpm 10.34.0、Node 24.22.0 解析，frozen-lockfile 安装，前端 22 项测试、TypeScript 与 Vite 构建、audit 前后对照、页面最小浏览器检查，并核对原仓 441 文件与依赖元数据哈希。GitHub 默认分支告警关闭以实际合入与扫描结果为准，不以分支 audit 冒充清零。GitHub Pages 仅上传 docs，不安装前端依赖，不涉及华为云服务创建；零现金预算，原私有仓与导航、仿真环境不升级，暂不运行机器人、仿真或真实视觉模型。


本稿由 CodeArts 主笔，实际验证结果将由 Codex 另行补录。

## 实际验证与人工校正

- CodeArts 的 package.json 与四文件删除清单经核对后应用；Codex 将 brace-expansion 的覆盖下限由4收窄到5，避免未来跨主版本覆盖。锁文件全部由pnpm解析，没有手工删条目。
- 使用独立 node_modules 与本工作树 .local 下的独立包存储；官方 pnpm10.34.0 tarball 的 SHA512 已核验。原机现有pnpm实际为10.34.7，未修改；Node24.22.0复用原机已有二进制。
- 初次构建遇到Axios1.20条件泛型类型错误。CodeArts根据实际报错生成单处类型断言，Codex简化注释并应用；没有禁用vue-tsc或降级Axios。随后TypeScript与Vite生产构建通过，四个测试文件22项通过。
- KaTeX0.18.2的Markdown数学扩展解析／渲染通过，继承trust选项不启用链接、显式自有trust仍按预期工作；Tinypool2.1.2启动线程并完成合成任务。它们是兼容性与定向行为检查，不是对所有公告的利用验证。
- 真实Chromium访问生产构建，桌面1440×1000、手机390×844均通过：合成登录、工作台、未配置执行禁用、历史、项目、刷新会话；零脚本异常、零意外API、零外部资源请求，没有机器人或模型请求。全部API均为传输替身，不构成真实云或硬件闭环。
- 原私有仓441个受跟踪文件及3个依赖／工具元数据哈希均未变化；未升级导航／仿真环境、未重跑后端或真实仿真。
- pnpm默认未执行@parcel/watcher和esbuild的安装脚本；平台包足以完成实际构建，没有放宽为任意安装脚本许可。仍有上游弃用包提示，不等于本轮新增漏洞或已全面消除维护风险。
- 构建自动生成的6条无关Element Plus类型声明已还原；本轮业务源码只增加Axios封装的局部类型断言，不改任务行为。

[机器记录](validation/dependency-repair.json)、[浏览器记录](validation/dependency-browser.json)、[定向兼容检查](validation/dependency-compatibility.json)、[CodeArts真实贡献](codearts-evidence.md)可核对。

## 保留的未修复风险

[braces公告](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)当前没有公布修复版本；[上游讨论](https://github.com/micromatch/braces/issues/70)仍未形成可核验的已发布补丁。已检查的SVG插件路径使用固定扩展名模式与固定图标目录，未发现任务文本、网页请求或API参数直接进入glob模式；这不证明整个工具链不可利用。保留该告警，不加入audit忽略、不手动关闭GitHub告警、不把公告范围之外的版本当作已证实修复。

新增前端CI复用官方Node模板，[来源与适配](FRONTEND_CI.md)保留；GitHub执行结果随后单独记录。静态Pages继续由原官方Pages工作流发布，本轮不新增云服务或模型调用。

## GitHub 实际交付

[PR #2](https://github.com/SpringFieldCafe/ict-campus-patrol-public/pull/2)已合入，合并提交 `22401e9ebb990544914963c52ed5f59c1844f5fe`。

- [PR前端CI 39200901434](https://github.com/SpringFieldCafe/ict-campus-patrol-public/actions/runs/39200901434)：独立锁定安装、生产构建和22项测试success。
- [main前端CI 39201120737](https://github.com/SpringFieldCafe/ict-campus-patrol-public/actions/runs/39201120737)：合入后同样success。
- [main Pages 39201120710](https://github.com/SpringFieldCafe/ict-campus-patrol-public/actions/runs/39201120710)：success，公网修复报告JSON与提交文件逐字节匹配。
- 合入后GitHub分别查询open与fixed：当前open=0，最初61条全部在fixed结果中匹配，fixed时间为北京时间2026-10-19约12:46。没有通过手动dismiss关闭；[机器快照](validation/dependency-github-after.json)可核对。

本机公开main已同步源代码并放入测试通过的新前端构建；此前指向原私有node_modules的临时软链接已移除，旧生成构建仅移到本机忽略区备份，原私有依赖没有变化。原私有仓仅追加真实贡献台账。
