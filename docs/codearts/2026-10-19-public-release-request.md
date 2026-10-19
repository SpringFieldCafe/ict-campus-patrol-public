请只输出可解析JSON，不要代码围栏，结构为{"release_scope_markdown":"...","review_issues":["..."]}。

任务：请作为Huawei CodeArts主笔新独立公开仓库的 docs/RELEASE_SCOPE.md（约1000中文字），并复核下面的发布边界。你仅做审查和文档主笔，没有亲自运行测试/扫描/创建GitHub仓库/部署；事实由Codex检查，不得归为你的工具执行。

用户已明确确认：通过GitHub CLI建立独立公开仓库及固定GitHub Pages静态成果站，尽可能公开许可清楚部分；原业务仓保持私有。新仓库名拟为SpringFieldCafe/ict-campus-patrol-public。用户同意暂缓旧导航源码、Go2模型/XML/OBJ、策略权重，以及含对应机器人渲染的截图/录像。不要再次要求总公开授权。

新公开集合：apps/web（基于V3 Admin Vite MIT，保留LICENSE/UPSTREAM）、cloud/backend（FastAPI模板MIT声明+原创Apache-2.0）、相关测试/依赖锁/示例配置；evaluation/vision（3个pending模板、0照片）、原创tools福利入口及离线测试；原创路线与示例观察点JSON；原创evaluate.py、plot_evaluation.py、evaluation.json；精选脱敏验证JSON与原创评测图；历史记录/项目说明两张无机器人渲染的真实截图。原实现/原模型/安装包/本地凭据和数据不分发，原Git历史不复制，新仓库从白名单建立新历史。

能力：源代码支持网页、认证、任务与远程协议、视觉评测离线准备。真实仿真与运动不能从此公开子集独立启动，仍缺未公开实现与合法资产。前端工作台依赖API，新的GitHub Pages只展示事实/历史结果，不登录、不发任务、不假装在线。新公开副本还要真实验证，当前测试结果暂不写“已通过”。不要声称完整比赛作品已开源或完整复现。

既有实测：侧箱15/15、短墙12/15并3次碰撞，墙体80%，保留较差0.4m/s候选4/15，不用整体27/30替代墙体；2固定场景*3目标*5起始位姿=30个配对用例，不是随机90环境。同机Git导出+新venv已有23锁定依赖、13仿真测试及三点录像记录，不等于新机器/公开完整应用复现。视觉0图片0真实请求、通过率null。上述都是既有记录，今天不重跑仿真和机器人。

官方赛题1要求CodeArts实际使用、智能体/Skills关联创建华为云服务并部署华为云可视化Demo，入围决赛作品需开源。GitHub Pages解决固定静态展示地址，不代表华为云服务关联、业务云部署或所有官方要求完成。官方赛事 https://e.huawei.com/cn/talent/#/ict/innovation-details?zoneCode=027425&compId=85132021&type=C002&zoneId=98269700 ，10/19核对numberVersion89。RDS/Redis为“等”字列举，不擅自承诺必须全开或ECS单项一定够。初赛正式Word、决赛PPT与报名状态未核验，不替用户认定已提交。

请文档包括：本次公开了什么/暂缓什么、许可证和署名边界、可复现/不可复现的具体能力、指标真实性、与官方要求的关系、后续扩大公开需要的来源材料。文件相对链接从docs目录算：../apps/web/UPSTREAM.md、../cloud/backend/UPSTREAM.md、../THIRD_PARTY_NOTICES.md、../evaluation/vision/README.md；不链接新仓未包含的旧源码或私有聊天。不要建议增加功能、买资源或再训练。语言客观简洁，最后注明“本文件由CodeArts主笔，Codex负责事实核对与实际发布验证”；不得冒称CodeArts已发布网站或开发主要业务。

