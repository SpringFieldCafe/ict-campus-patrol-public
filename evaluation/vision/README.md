# 离线视觉评测准备

图片与实际参考事实按用户要求先留空，后续有现场条件再拍摄和填写。
已提供清单检查、批量调用入口、原始回答与失败记录、人工核对 CSV 和本地 HTML 报告。
复用后端的 `app.services.huawei.ask_image`，无需启动网页、API、仿真或机器人。
未开通或调用真实模型；目前没有识别准确率或实机视觉成绩。

## 现在就能运行

从仓库根目录执行，使用后端现有隔离 Python 3.14 和锁定依赖，不新增依赖。
新环境先按 [后端说明](../../cloud/backend/README.md) 安装依赖；离线评测无需运行
`init_local.py`，不要求后台账号、JWT 或机器人配置。

```bash
# 检查模板；不会读取后台 .env 或发起网络请求。
bash cloud/backend/vision-eval.sh check

# 生成等待补图的报告；本命令没有模型请求。
bash cloud/backend/vision-eval.sh run --mock
```

当前清单为 3 个 `pending` 拍摄／问题模板，真实样例数为 **0**。
检查结果为 `WAITING_FOR_IMAGES`；运行报告中的模型效果为 `false`、通过率为 `null`。
成功退出仅表示清单／报告流程可用，不表示图片识别成功。
`--mock` 即使日后有图片，也只用固定流程文本，经 HTTP 替身复用原请求构造；不会联网。
流程替身回答始终不参与模型效果统计。

命令输出本次目录，默认为 `.local/vision-eval/runs/<UTC时间>-<随机标识>/`：

| 文件 | 内容 |
| --- | --- |
| `results.json` | 每题完整清单快照、来源、图像 SHA256、问题、原回答、模型／请求 ID、时间和错误 |
| `images/` | 有可评测图片时，保存本次真正传入模型的原始字节；当前不生成 |
| `review.csv` | 对已获得回答的条目进行人工核对；当前只有表头 |
| `summary.json` | 等待／回答／失败数量、核对覆盖及核对通过率 |
| `report.html` | 浏览器直接打开，逐题查看原图、问题、参考事实、原回答和核对意见 |

`--output-dir` 可指定新目录；已有目录不覆盖。相对路径以执行命令时的目录为准。
运行输出默认在 Git 忽略区，不写入任务库、不生成机器人任务编号。

## 后续补照片

现在不需要准备或上传照片。具备现场条件后，再复制模板到本机私有目录：

```bash
mkdir -p .local/vision-eval/dataset/images
cp evaluation/vision/manifest.example.json .local/vision-eval/dataset/manifest.json
```

把允许使用的照片放进该目录的 `images/`，逐条填写：

| 字段 | 填法 |
| --- | --- |
| `id` | 每个“图片＋问题”唯一编号；多个问题可引用同一图片 |
| `status` | 未准备好保持 `pending`；图片、授权说明与参考依据齐备后改为 `ready` |
| `capture_notes` | 拍摄准备说明，可保留；不是图像事实或参考答案 |
| `image` | 相对于清单所在目录的 PNG/JPEG 路径，例如 `images/scene-a.jpg` |
| `image_sha256` | 对应图片文件的 SHA256，小写 64 位 |
| `source.description` | 真实拍摄来源、设备和场景说明；手机图片如实标注为手机拍摄 |
| `source.usage_permission` | 团队获准如何使用该图；本地评测与公开分发分别说明 |
| `question` | 要询问的现场问题，最长 2000 字符 |
| `reference_facts` | 看图人工确认的可见事实；列要点，不写唯一标准措辞 |
| `unanswerable_points` | 受遮挡、清晰度或视野限制，图片无法支持的判断 |

`ready` 条目的两个参考列表至少填一个。参考依据须在看模型回答之前确定，
并按实际照片填写；模板中的拍摄设想不能当作已经观察到的事实。
一张图片可以复制为多个问题条目，但同图多题不等于多个独立现场样本。

图片路径须位于清单目录内（越界符号链接也拒绝），单图上限 10 MiB。
检查图片编码标识与 SHA256；不新增图片解码依赖，不代替拍摄后的人工图像质量检查。
整个批次的 `ready` 条目先检查完才开始调用，任何缺字段、哈希变化或越界均先报错。
`pending` 条目保持等待状态，不请求模型、不虚构答案。

```bash
sha256sum .local/vision-eval/dataset/images/scene-a.jpg
bash cloud/backend/vision-eval.sh check --manifest .local/vision-eval/dataset/manifest.json
bash cloud/backend/vision-eval.sh run --mock --manifest .local/vision-eval/dataset/manifest.json
```

真实影像继续保存在本机忽略区；公开样例及许可另行确认后再纳入仓库。

## 模型就绪后

当前先准备入口，不在本轮开通服务、付费或真实调用。
未来确认模型可用和费用后，操作者才能显式运行下面的 `--live`。
未指定 `--live` 不会发起真实调用。

```bash
bash cloud/backend/vision-eval.sh run --live \
  --manifest .local/vision-eval/dataset/manifest.json \
  --env-file cloud/backend/.env
```

仅加载显式 env 文件（或进程环境）中的 `HUAWEI_CHAT_COMPLETIONS_URL`、`HUAWEI_MODEL`、
`HUAWEI_API_KEY`、可选 `HUAWEI_TIMEOUT_SECONDS`。不自动加载后台 `.env`，
不要求其他后台配置；凭据不要写进清单、命令参数或 Git。
无 `ready` 图片时先拒绝真实运行。
复用原 HTTPS/Base64、TLS 校验、不跟随重定向、不自动重试、单次超时设置。
参考事实与人工意见仅用于评测，**不发送给模型**。

每个条目显式调用一次。超时／HTTP 失败会保留原因并继续后续条目，
有请求失败时进程退出码为 1；清单或配置错误为 2。
运行过程中逐题保存，调用开始前记录 `REQUESTING`；中断不自动重跑或续传，
原始 JSON 可供检查，手动再次运行会创建另一份记录。
时间使用 UTC。没有图片时的流程报告不能替代实际调用记录。

## 人工核对

打开 `report.html` 对照实际图片和预先填写的参考要点，看回答是否：

- 覆盖问题所需的可见事实，物体和大致位置是否正确。
- 加入图片无法支持的物体、数量、位置或现场情况。
- 对预先标明无法判断的内容保留不确定性。

不按答案措辞完全一致判分。单张照片中的“有物品占用”也不等于已经测量出
机器狗是否能安全通过；参考依据只能使用图像确实提供的信息。

在 `review.csv` 只编辑 `verdict` 和 `notes`：`verdict` 留空表示尚未核对，
`pass` 表示符合本题依据，`fail` 表示不符合并在备注说明。
`case_id` 和 `case_sha256` 不改动；后者绑定图片哈希、问题、来源与参考依据，
避免把另一题或另一版本的核对结果混入。

```bash
bash cloud/backend/vision-eval.sh report .local/vision-eval/runs/<本次目录>
```

刷新报告不会再调用模型或覆盖人工 CSV；会重新检查案例快照及保存图片的哈希。
真实模式只统计已人工核对回答的通过率，同时展示请求失败、等待图片与未核对数量。
空数据、未核对和流程替身的通过率保持 `null`，不能记为 0% 或 100%。
这只是当前样例的人工核对结果，不代表复杂环境或实机闭环的准确率。

## 验证

```bash
bash cloud/backend/test.sh -q tests/test_vision_eval.py
```

测试在临时目录创建人工 1×1 PNG，使用固定 HTTP 响应验证请求、错误、报告和核对绑定，
没有场景识别意义，也不作为正式评测图片。实际运行记录见 [VALIDATION.md](VALIDATION.md)。
