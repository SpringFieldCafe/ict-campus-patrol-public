# 展示与评测来源

## 公开静态成果站

固定地址：[Campus Patrol](https://springfieldcafe.github.io/ict-campus-patrol-public/)。页面展示历史状态截图、真实历史评测数据及公开源码链接，没有在线账号、任务提交、仿真执行或问答服务。源文件为 [index.html](index.html)、[CSS](assets/site.css)、[JavaScript](assets/site.js)。

公开页面使用已逐张核验的无机器人渲染截图与原创轨迹图：

- [任务历史截图](images/2026-10-16-history.png)：原开发环境的真实界面，示例账号，不含真实现场照片。
- [项目说明截图](images/2026-10-16-project.png)：项目目标说明；其中目标不代表已完成实机与云问答。
- [轨迹与参数对照 PNG](images/2026-10-17-wall-evaluation.png)、[SVG](images/2026-10-17-wall-evaluation.svg)：由真实记录绘制，包含碰撞与较差候选。

机器人渲染截图和 MP4 暂缓，原因见 [公开范围](RELEASE_SCOPE.md)。

## 2026-10-17 历史 MuJoCo 评测

两个固定场景 × 每场景 3 组目标 × 5 个起始位姿，共 30 个配对用例。成功须按序到达全部 3 点，无碰撞且无跌倒。模型与导航方法沿用既有实现；候选比较不等于更换算法。

| 场景／阶段 | 成功 | 碰撞 | 说明 |
| --- | --- | --- | --- |
| 最终侧箱对照 | 15/15 | 0 | 简单场景与有限起点扰动 |
| 最终错位短墙 | 12/15 | 3 | 墙体成功率 80% |
| 短墙候选横向限速 0.4 m/s | 4/15 | 10 | 另 1 次步数耗尽；未采用，最终保留 0.18 m/s |

整体 27/30 不能替代墙体 80%；三个阶段的累计执行次数不等于 90 个独立随机环境，模拟用时不等于实机速度。

原始记录：[基线](../edge/go2/simulation/validation/walls/reference.json)、[候选](../edge/go2/simulation/validation/walls/candidate.json)、[最终](../edge/go2/simulation/validation/walls/final.json)。页面的 [精简展示数据](data/evaluation.json) 来自最终记录，保留全部 30 个用例和失败状态。

其他 [历史应用验证 JSON](validation/) 与 [仿真历史 JSON](../edge/go2/simulation/validation/) 区分接口替身、真实 MuJoCo、同机多进程 HTTP、取消和超时。原始实现与资产未随本公开子集分发，历史结果不能充作公开目录的新仿真验证。

## 当前验证边界

- 新公开副本已验证 API、网页测试与构建，见 [PUBLIC_APPLICATION.md](PUBLIC_APPLICATION.md)；没有新跑真实仿真或硬件。
- 远程通道是原工作机的独立 HTTP 角色验证，跨公网与华为云部署尚未验证。
- 同机 Git 导出与全新 venv 曾完成仿真子系统复现，不等于全新机器安装或本公开子集完整复现。
- 视觉清单当前 3 pending、0 图片、0 请求、人工通过率 null，没有模型效果指标。
- GitHub Pages 发布只说明静态页面可访问，不能代替华为云服务关联或业务部署。
