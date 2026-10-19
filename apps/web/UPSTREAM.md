# 开源资产来源

- 上游：[un-pany/v3-admin-vite](https://github.com/un-pany/v3-admin-vite)
- 拉取日期：2026-10-16。
- 固定提交：`c2c895d71d571e9c18c2453fa85469a479c79fc6`；上游包版本 `5.2.0`。
- 许可：MIT，原始版权与完整许可保存在 [LICENSE](LICENSE)。本目录改造的原有文件继续保留此上游许可基础，根目录 Apache-2.0 不替换第三方声明。
- 完整参考克隆位于本机 Git 忽略区 `.local/upstream/v3-admin-vite`；可从官方仓库检出上述提交重建，无嵌套 Git 仓库或 submodule。

沿用布局、响应式侧栏、导航、面包屑、路由守卫、Pinia、Axios 基础、Element Plus、图标、自动导入、UnoCSS、Vite／TypeScript 工程和部分通用组件。`apps/web` 是可独立安装构建的前端应用。

替换演示登录／验证码、mock 响应封装、假身份切换、示例菜单与推广通知，新增本项目任务工作台／历史／项目页及 FastAPI 适配。未暴露模板演示路由；保留的上游示例和通用资产可供后续复用，不构成本项目已实现的业务功能。移除 Vite MCP 插件及 Husky prepare，不额外开启 MCP 端口或改写本仓库 Git hooks；Vxe Table 资产保留但不再全局加载。

依赖固定在 [package.json](package.json) 和 [pnpm-lock.yaml](pnpm-lock.yaml)，用途与主要许可见根目录 [第三方台账](../../THIRD_PARTY_NOTICES.md)。UI 插画是本项目 CSS／SVG，运行录像来自既有 MuJoCo，不使用网上机器人照片冒充现场画面。
