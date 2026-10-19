# CodeArts 实际贡献 · 公开子集

CodeArts 的真实产出与其他工具的工作分别记录。此前私有开发环境已实际使用 CodeArts 进行部署缺口分析、前后端源码审查、三处文档替换、仿真复现文档主笔与赛事差距审计；本仓库不复制私人聊天、未公开实现或完整原始事件流。以下新增案例的原稿和精选回执随公开仓库分发，可以直接核对。

## 2026-10-19：公开发布范围主笔与审查

- 工具：本机 CodeArts 26.9.26 原生内核，固定福利模型 `benefit-model/glm-5.3-flash`；工具权限 deny，实际零工具调用，无普通模型回退。
- 输入：已确认的发布白名单、许可台账、两个模板来源说明和视觉准备状态；[请求原文](codearts/2026-10-19-public-release-request.md)。不包含密钥或私人历史对话。
- CodeArts 产出：[原始回答](codearts/2026-10-19-public-release-response.txt)，含发布范围文稿及六项审查问题；原回答的 JSON 有未转义引号，保留原文，从中提取文稿后核对，未伪称格式校验通过；最终 [RELEASE_SCOPE.md](RELEASE_SCOPE.md) 由该文稿核对修改后应用。
- 精选[请求回执与 SHA256](codearts/2026-10-19-public-release-receipt.json)：响应成功，81.33 秒；请求和原回答哈希保留。事件报告成本为 0，不等于账号账单证明。
- Codex 负责白名单导出、素材与敏感信息核验、应用测试、静态站开发、GitHub 仓库创建和 Pages 发布。CodeArts 没有亲自编辑工作区、执行扫描／测试、生成主要业务代码或部署。

## 文稿核对与采纳

CodeArts 提醒：不能原样复制私有仓库的许可台账语境；历史测试不能冒充新公开副本的验证；截图、示例 JSON 与服务适配需要检查敏感信息；静态 Pages 不等于华为云业务部署。这些意见分别落实到新的第三方台账、历史文档标注、白名单检查与页面边界说明。

应用原稿时由 Codex 作事实校正：

1. 使用“受限区域现场查看”项目表述，更新拟定仓库名为最终名称。
2. HIMLoco 根目录的 CC BY-NC-SA 4.0 声明不等于机器人资产独立权利已确认。
3. 将“墙体可用率”改为“墙体成功率”。
4. 原回答时公开副本测试尚待完成；后续测试已执行，将对应措辞改为历史结果与[新副本验证](PUBLIC_APPLICATION.md)分别引用。
5. 后续扩大发布仍要验证新增部分，不能因本次应用测试通过而声称真实仿真已复现。

本贡献属于**审查与发布范围文档主笔**。不能计为 CodeArts 已完成导航／Web 业务开发、云服务创建、构建或部署。公开仓库初始提交收录本次核对后的文稿；原回答作为证据保留，不把其中未校正措辞当成项目事实。

## 2026-10-19：GitHub Actions 审查与持续协作约定

用户随后要求推送自动发布、复用官方方案，并将每轮实际邀请 CodeArts 的约定写入 AGENTS.md 与 README。

CodeArts 通过同一固定福利入口完成第二次真实请求，工具权限 deny、实际零工具调用。它审查 GitHub 官方 Static HTML 模板的最小适配，并主笔 `docs/MAINTENANCE.md`、AGENTS 与 README 约定。[请求原文](codearts/2026-10-19-pages-actions-request.md)、[原回答](codearts/2026-10-19-pages-actions-response.txt)、[精选回执](codearts/2026-10-19-pages-actions-receipt.json)均保留，可核对原始字节哈希。

Codex 已实际核对四个 Action 主版本标签对应 SHA，保留官方模板结构、来源与 MIT 声明，只改 main、docs 路径和提交固定；维护文稿核对后应用。持续协作约定写入公开与原私有项目 AGENTS.md、README，避免只在本次聊天中约定。

原回答中“直接打开 docs/index.html”可能因 file:// 的 fetch 限制无法加载交互 JSON，README 保留已验证的本地 HTTP 预览方式；没有照搬这一建议。“无密钥”指无需用户提供外部密钥，GitHub 自动 GITHUB_TOKEN/OIDC 仍按官方流程使用。原稿中的图片边界补为未经授权的真实人员影像。Actions 直接打包静态文件，没有 Jekyll 步骤；`.nojekyll` 已存在，但不是依赖它绕过此流程的构建。

**归属：** CodeArts 完成静态审查与维护／协作文稿；Codex 下载模板、核对版本、应用文件、浏览器 QA、创建仓库并执行部署。GitHub Actions 执行后续发布，不在每次推送时调用 CodeArts。首次部署结果以 [发布记录](PUBLICATION.md) 为准，不把审查意见当作部署成功证据。
