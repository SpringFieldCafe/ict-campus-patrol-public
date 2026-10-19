# FastAPI 模板来源与改造边界

- 上游：https://github.com/fastapi/full-stack-fastapi-template
- 本次获取提交：`b1125d8839482cb7bbae603ddc6d0081bf87532e`。
- 原始完整克隆位于仓库忽略区 `.local/upstream/full-stack-fastapi-template/`，不嵌套提交它的 Git 历史。
- 上游 MIT 许可原文保存在 [third_party/fastapi-template-LICENSE](third_party/fastapi-template-LICENSE)。

实际复用 `app/core/security.py` 的密码哈希与 JWT，`app/api/deps.py` 的认证／数据库依赖，
以及用户模型、认证 CRUD、登录路由、配置、数据库初始化和主应用／路由组合的实现。
本项目在这些代码上裁剪改造，保留 MIT 来源声明；新增机器人／仿真任务、文件结果与华为云适配属于本项目代码，
遵循仓库根目录 Apache-2.0。根目录许可不覆盖上游声明。

改造内容：

- 独立 Python 3.14 环境，依赖实际解析版本由 `uv.lock` 固定；不升级机器人／MuJoCo 环境。
- 本地账号数据库改为 SQLite；JWT `sub` 显式解析 UUID，适应 SQLite UUID 字段。
- 仅公开模板的登录与当前用户接口；未引入演示 Items、开放注册、邮件、密码找回、React 页面及 FastAPI Cloud CLI。
- CORS 为未来 Vue 开发地址配置；任务通过独立进程接现有执行器，不在 HTTP 请求线程中运行机器人。
- 任务使用原子 JSON 和事件文件，默认单任务、忙时拒绝、不排队、不重试。无模型配置时不调用云服务。

后续升级应按上述固定提交比较差异，重新运行后端测试；不能直接将上游整个应用覆盖本目录。
