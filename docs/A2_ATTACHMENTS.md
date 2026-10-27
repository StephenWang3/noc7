# A2 附件处理使用与接入

默认全程本地运行，不需要 API 密钥。输入沿用 [A0 工单包](BUNDLE_FORMAT.md)，逐一解析清单里的附件，不依赖日志顶层附件标志。输出保持 [并行契约](CONTRACTS.md) 的 `ParseOutput` / `EvidenceSpan`。

## 运行

```bash
uv sync
uv run python -m noc7.parsers.attachments fixtures/bundles/SYN-S10 --out var/a2/s10.json
uv run python -m noc7.parsers.attachments fixtures/bundles/SYN-X01 --out var/a2/x01.json
uv run python -m noc7.parsers.attachments fixtures/bundles/SYN-P04 --out var/a2/pdf.json
uv run python -m noc7.parsers.attachments fixtures/bundles/SYN-P03 --out var/a2/docx.json
uv run python -m noc7.parsers.attachments fixtures/bundles/SYN-P02 --out var/a2/eml.json
uv run python scripts/check_a2.py
uv run pytest tests/a2 -q
```

不传 `--out` 时输出 JSON 到标准输出。`failed` / `unsupported` 返回退出码 1；`needs_review` 默认返回 0，使用 `--strict` 可让待复核也返回 1；输入包不合法或输出位置不允许返回 2。JSON 的 `outputs` 为附件结果，含状态、证据、问题与解析说明；`bundle_warnings` 保留附件标志不一致等导入提醒。

真实工单包与解析结果须存仓库外，例如 `~/.noc7/real/` 与 `~/.noc7/results/`。不要把真实内容、OCR 输出或模型响应提交进仓库。CLI 会拒绝把真实解析结果写进源码仓库。

## A1 接入与证据定位

`default_registry()` 已自动发现 A2，无需修改注册表或数据模型：

```python
from noc7.bundle import load_bundle
from noc7.parsers import ParseContext, default_registry

bundle = load_bundle("fixtures/bundles/SYN-S10")
registry = default_registry()
outputs = [registry.parse(ParseContext(bundle, m)) for m in bundle.manifest.materials]
spans = [span for output in outputs for span in output.spans]
```

| 内容 | 证据编号示例 | 定位语义 |
| --- | --- | --- |
| 图片 OCR | `M04/img:r0` | 原图片像素 bbox，左上原点，不隐式应用 EXIF 旋转 |
| 每类统计 | `M04/img:chart:BE` | 表格 BE 行；`derived_from` 指向 OCR 单元与表头 |
| 拼图区域 / 表格 | `M03/img:section:0` / `M03/img:table:22` | 图片标题区域 / 表格 bbox |
| PDF 文本 / OCR / 表格 | `M03/p1:b0` / `M03/p1:ocr:0` / `M03/p1:tbl:0` | 1 起页码，未旋转 PDF 页坐标 pt |
| DOCX 段落 / 单元格 / 整表 | `M04/para:1` / `M04/tbl:0:1:1` / `M04/tbl:0` | 段落、表格、行列均从 0 起 |
| EML 头 / 正文 / 内嵌附件信息 | `M03/msg:0:header` / `M03/msg:0:body:0` / `M03/msg:0:mime:3` | 当前消息为 0，引用片段分组递增；MIME 证据仅列附件信息 |

同输入、同 OCR 版本的编号稳定；OCR 升级可能改变分块，复用人工修订前需核对版本与材料哈希。统计类别编号不依赖 OCR 行次序。OCR 文字与其结构化转录不是两份独立证据，`derived_from` 表达这个关联。

曲线读数示例：

```json
{
  "type": "chart", "metric": "丢包率", "unit": "%",
  "x_start": "01:55", "x_end": "02:47", "timezone_shown": false,
  "series": [{"series": "BE", "max": 21.8, "avg": 4.76, "min": 0.0, "first_nonzero": null}]
}
```

`first_nonzero` 空表示没有可靠测量，A1 不应从标准答案补值，也不能把首个非零直接当起障时间。无可读统计表、类别缺失、低分 OCR、无法分类的图均待复核。图片规则分类和文档标题分区是启发式；不识别签字真伪或照片设备状态。七要素、规则与报告仍由 A1 负责。

EML 内嵌 PDF / 图片、DOCX 嵌入图像等尚未递归解析，会报 `MATERIAL_UNSUPPORTED`，保留正文并标 `needs_review`。须在导入阶段把原件单独登记到清单；解析器不改清单、不写出附件、不伪造跨材料定位。邮件引用切分不能覆盖所有客户端的转发版式。

## 回放与替换提供方

接口见 `noc7.ocr.base`：OCR 返回文字、像素 bbox 和分数；视觉返回图片类别与区域观测。调用经过 `read_layout` / `describe_image`，检查闸门、区域边界与曲线统计合法性。

```bash
# 录制合成 PNG 的本地 OCR，再回放；不修改原始工单包
uv run python scripts/check_a2.py --record-replay var/a2/replay
uv run python -m noc7.parsers.attachments fixtures/bundles/SYN-S10 --ocr replay --replay-dir var/a2/replay
# 可选 Tesseract 基线，需系统程序和 chi_sim+eng 语言包
uv run python scripts/check_a2.py --compare-tesseract
```

回放按尺寸与 RGB 像素哈希匹配，文件名为 `<digest>.ocr.json` / `<digest>.vision.json`，保存 `LayoutResult` / `ImageObservation`。缺录制立即失败，只允许合成数据。

外部服务须显式构造后注入，不会因存在密钥自动启用：

```python
from noc7.providers.vision_http import OpenAICompatibleAttachmentProvider
from noc7.parsers.attachments import ImageParser

vision = OpenAICompatibleAttachmentProvider(
    base_url="https://vision.example/v1",  # 换成实际服务基址，不含 chat/completions
    model="approved-vision-model",
    api_key_env="NOC7_VISION_API_KEY",
)
parser = ImageParser(vision=vision)  # 本地 OCR，加可选视觉观测
# 也可 ImageParser(ocr=vision)，显式使用图片 JSON OCR 接口。
```

密钥仅通过团队 Secrets 注入环境，不写代码、JSON 或聊天。适配器只允许合成数据；每批 10 请求，批间 30 秒；429 等 300 秒再重试，默认重试 1 次。调用方须复用同一实例，当前不跨进程协调限流。接口只经过模拟 HTTP 验证，未实调 MiniMax；不支持图片或 JSON 响应模式的服务需进一步适配。

设计与资源上限见 [ADR 0005](decisions/0005-attachment-parsing-and-local-ocr.md)，验证边界见 [答辩记录](defense/a2-validation.md)。
