# 第三方许可台账 · 公开子集

本台账描述本公开仓库实际分发内容，不沿用私有开发分支的分发结论。原创内容适用根目录 [Apache-2.0](LICENSE)；第三方原声明继续适用。[公开范围](docs/RELEASE_SCOPE.md)中的排除项不因本仓库公开而取得授权。

| 内容 | 来源／版本 | 许可与保留位置 | 分发范围 |
| --- | --- | --- | --- |
| GitHub Pages Actions 模板 | [actions/starter-workflows](https://github.com/actions/starter-workflows/blob/22770e21c6986ed08a3aa400bdcc6a9a75ecdaf2/pages/static.yml) | MIT，Copyright 2020 GitHub；[完整许可](docs/upstream/github-pages-starter-LICENSE)、[最小修改](docs/HOSTING.md) | `.github/workflows/pages.yml`；四个 Action 本身由 GitHub 执行时获取 |
| V3 Admin Vite | [un-pany/v3-admin-vite](https://github.com/un-pany/v3-admin-vite)，5.2.0，提交 `c2c895d71d571e9c18c2453fa85469a479c79fc6` | MIT；[完整许可](apps/web/LICENSE)、[改造说明](apps/web/UPSTREAM.md)、[模板声明](apps/web/public/template-LICENSE.txt) | 改造后的前端源码及测试；不分发 node_modules |
| FastAPI 全栈模板 | [fastapi/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template)，提交 `b1125d8839482cb7bbae603ddc6d0081bf87532e` | MIT；[完整许可](cloud/backend/third_party/fastapi-template-LICENSE)、[改造说明](cloud/backend/UPSTREAM.md) | 认证、配置、模型、会话等裁剪改造源码 |
| 前端依赖 | Vue、Vue Router、Pinia、Element Plus、Axios、Vite、TypeScript、Vitest、UnoCSS 等，版本见 [package.json](apps/web/package.json) 与 [锁文件](apps/web/pnpm-lock.yaml) | 依赖及传递依赖按各自发行声明；以 MIT 为主，不统一替代 | 依赖声明与锁文件；安装包与构建产物不入 Git |
| 后端依赖 | FastAPI、SQLModel、SQLAlchemy、Pydantic、PyJWT、pwdlib、HTTPX、Uvicorn 等，版本见 [锁文件](cloud/backend/uv.lock) | 以 MIT、BSD 条款为主；Argon2 等传递依赖另按其声明 | 依赖声明与锁文件；解释器和虚拟环境不分发 |
| Matplotlib | 历史评测绘图使用工作机已有 3.5.1 | Matplotlib 基于 PSF 的许可；包内其他组件另有声明 | 只分发原创绘图脚本与导出的图，不分发库 |
| Node.js、pnpm、Playwright、CPython、uv | [公开副本验证环境](docs/PUBLIC_APPLICATION.md) | 按各工具及浏览器发行许可 | 不分发本地工具与浏览器 |
| Huawei MaaS Chat API | [华为官方调用文档](https://support.huaweicloud.com/model-call-maas/model-call-020.html) | 服务与模型的账号、额度、计费及使用条款另计，源码许可不替代服务授权 | 仅原创适配代码；无凭据、模型或真实调用结果 |
| CodeArts CLI | 本机已有 26.9.26；福利通道使用记录见[贡献证据](docs/codearts-evidence.md) | 华为产品及账号服务条款；本机入口不是普遍可用承诺 | 只分发原创辅助脚本、离线测试与文档，不分发官方可执行文件 |

## 未随本仓库分发

旧 SEA-Nav／Go2 导航运行实现、Go2 XML／OBJ、策略权重、HIMLoco 归档、安装包及对应机器人渲染图／录像暂缓。旧实现的组件许可、模型获取条件与资产再分发条件仍需确认。HIMLoco 根目录有 CC BY-NC-SA 4.0 声明，但不能据此代替机器人资产独立权利核验。

第三方项目在说明中被提及，不代表它们的源码、权重或资产已分发，也不代表各项目认可本作品。用户自训来源确认与第三方资产再分发授权是不同事项。
