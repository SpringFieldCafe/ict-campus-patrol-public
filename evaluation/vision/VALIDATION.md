# 2026-10-17 离线视觉准备验证

> **历史环境记录与公开范围：**本页记录原开发环境的离线准备验证，模型请求均为替身。公开仓库保留相关代码、空清单和测试；2026-10-19 在公开副本重新检查了空清单、mock 报告与 74 项后端测试，见 [公开应用说明](../../docs/PUBLIC_APPLICATION.md)。机器人与真实仿真执行实现未分发，不影响这里的离线准备，但本页不能证明真实视觉效果或完整应用复现。

分支：`feat/vision-evaluation-preparation-20261017`。
按用户要求，照片与根据实际照片填写的参考事实先留空。
本轮没有机器人、真实场景图片、华为模型调用、付费操作或云资源部署。
未增加仿真截图问答；原实机成功采图与证据检查接口继续保留。

## 实际空清单运行

在仓库根目录实际运行：

```bash
bash cloud/backend/vision-eval.sh check
bash cloud/backend/vision-eval.sh run --mock --output-dir .local/vision-eval/preparation-20261017
bash cloud/backend/vision-eval.sh report .local/vision-eval/preparation-20261017
```

三次退出码均为 0。原始摘要记录见 [preparation.json](validation/preparation.json)。
本机生成的报告位于 `.local/vision-eval/preparation-20261017/report.html`，
不随克隆分发；新环境运行 `run --mock` 可重新生成。
同名目录不覆盖，复查时运行 `report` 或选择新的输出目录。

| 指标 | 实际结果 |
| --- | --- |
| 清单条目 | 3 个待拍摄模板 |
| 可评测图片 | 0 |
| 状态 | `WAITING_FOR_IMAGES` |
| 模型请求／替身请求 | 0 / 0 |
| 获得回答／人工核对 | 0 / 0 |
| 通过率 | `null`，未评测 |
| `model_effect_evaluated` | `false` |

成功退出表示准备流程能处理空清单；不表示识别效果通过。

## 自动验证

```bash
bash cloud/backend/test.sh -q
bash cloud/backend/test.sh -q tests/test_vision_eval.py
cloud/backend/.venv/bin/ruff check cloud/backend/app cloud/backend/scripts cloud/backend/tests
bash -n cloud/backend/vision-eval.sh
git diff --check
```

- 后端全量 **74 项通过**，其中本轮新增视觉评测 **12 项**；修正人工 PNG 测试夹具、格式化后，12 项定向复跑通过。
- 清空后台账号／JWT 环境变量的独立子进程，禁用 socket 连接，验证 help、check 和空清单 mock 流程；没有导入后台配置或机器人 runtime。
- 图片／授权／参考依据缺失、重复编号、图片哈希变化、路径越界、非 PNG/JPEG 标识均在请求前拒绝；不创建已开始运行的目录。
- 人工 1×1 PNG 与 `MockTransport` 验证模型请求复用、参考事实不入请求、单次超时、HTTP 错误保留、失败后继续后续条目、无自动重试。
- 验证保存原图快照、拒绝覆盖运行目录、报告对问题／回答／意见进行 HTML 转义、图片及核对记录的哈希绑定。
- 验证真实模式无图片／缺配置时拒绝，配置错误不输出测试密钥；固定替身回答即使填写人工通过，也不形成模型效果通过率。
- Ruff、shell 语法和补丁空白检查通过。

完整回归出现既有 Starlette 对 httpx 测试客户端的弃用提示，未升级原依赖。
所有测试 HTTP 响应均为替身；测试中“live”分支只验证协议与记录逻辑，未连接真实模型。
临时生成的人工 PNG 无真实场景含义，不是正式视觉评测数据，也未加入清单或仓库。

## 仍待实际条件

现场拍照、来源／使用范围记录、按实际图片填写参考事实，以及模型开通后的真实调用与人工核对。
完成这些之前，识别效果和实机视觉闭环维持“未验证”。
