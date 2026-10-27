# noc7

NOC 故障工单七要素提取：把工单字段、处理过程、邮件和附件整理成**带证据的七要素 JSON**（起障时间、结束时间、故障现象、责任方、原因、处理过程、故障地点），经规则校验后生成 Markdown/HTML 报告。

设计原则是“证据优先”：所有材料先切成带编号、可定位的证据片段，结论必须引用片段；没有依据的要素保持“未知”，互相矛盾的保留全部候选，不静默填满。

> 仓库里的工单全部是**合成数据**（编号以 `SYN-` 开头）。真实工单及分析产物只存放在仓库外的本机目录，不提交。用户已批准开发期向官方 DeepSeek 发送真实文本和本地 OCR 文字；原始截图不外发，其他外部服务不因此获准。批准范围见 [模型接入决策](docs/decisions/llm-text-providers.md)。

## 当前进度

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| A0 地基 | 项目骨架、七要素 schema、工单包格式、15 个合成工单包及标准答案、并行开发契约 | ✅ |
| A1 文本链路 | 字段/处理过程/邮件解析、规则与回放、抽取、规则校验、Markdown/HTML 报告 | ✅（详见 [运行与边界](docs/A1_TEXT_PIPELINE.md)） |
| A2 附件 | 图片、PDF、DOCX、EML、本地 OCR、外发闸门、证据定位 | ✅ 合成样本验收；[使用与边界](docs/A2_ATTACHMENTS.md) |
| A3 审核界面 | 三栏工作台、点击定位原文、人工修订 | 待开始（先要参考图或草图） |
| A4 评测与答辩 | 评测脚本、对照实验、答辩材料 | 待开始 |

## 快速开始

需要 [uv](https://docs.astral.sh/uv/)，Python 版本由 `.python-version` 指定（3.12）。

```bash
uv sync                                  # 安装依赖
uv run pytest -q                         # 运行测试
uv run noc7 bundle validate              # 校验 fixtures/bundles/ 下全部工单包
uv run noc7 gold check                   # 检查 evals/gold/ 下的标准答案与工单包是否对得上
uv run noc7 schema check                 # 检查 schemas/ 是否与代码一致
uv run noc7 schema export                # 代码改动后重新导出 JSON Schema
uv run noc7 analyze                      # 分析全部合成包，生成 JSON、审核报告（Markdown/HTML）和公司格式报告（Word/HTML 预览）
uv run noc7 analyze --save-replay        # 同时录制离线回放快照
uv run noc7 analyze --provider replay --replay var/reports --out var/replayed
uv run noc7 local-batch ~/.noc7/real --out ~/.noc7/integration-next --expected-count 15  # 仓库外新批次
uv run python scripts/check_integration.py  # 默认全链路对照合成 gold，有差异则退出 1
uv run python scripts/check_company_report.py <生成的.docx> <本机样例.docx>  # 只比版式，不打印内容
uv run noc7 bundle rehash <工单包目录>    # 编写合成样本时重算清单里的哈希
uv run --group fixtures python scripts/make_fixture_assets.py   # 重新生成合成附件（PNG/PDF/DOCX）
uv run python -m noc7.parsers.attachments fixtures/bundles/SYN-S10 --out var/a2/s10.json  # 独立解析附件
uv run python scripts/check_a2.py          # 复现合成附件验收，不调用外部模型
```

公司格式报告的页眉（公司名、logo）只从仓库外的 `~/.noc7/report_profile/profile.json` 读取（`{"company_name": "…", "logo": "logo.png"}`，可用 `NOC7_REPORT_PROFILE` 改目录），未配置时页眉留空；取值与待核实规则见 [ADR 0007](docs/decisions/0007-company-report-format.md)。

合并后的全量测试、本机 15 张真实工单统计和待核实项见 [联调问题清单](docs/INTEGRATION_ISSUES.md)。真实报告仅在本机，不进仓库；测试通过与语义提取正确分别陈述。

## 文本模型与配置切换

默认仍是离线 `rules`，`local-batch` 仍固定本机规则。使用统一模型入口时只替换 `--model-config`，解析、证据校验与报告流程相同：

```bash
uv run noc7 analyze fixtures/bundles/SYN-S01 --provider llm \
  --model-config config/models/deepseek.json \
  --out ~/.noc7/deepseek-synthetic-new --save-replay

uv run noc7 analyze ~/.noc7/real --provider llm \
  --model-config config/models/deepseek.json \
  --out ~/.noc7/deepseek-real-new --save-replay

uv run noc7 analyze ~/.noc7/real --provider replay \
  --replay ~/.noc7/deepseek-real-new --out ~/.noc7/replayed-real-new
```

DeepSeek 密钥只从团队密钥注入的 `DEEPSEEK_API_KEY` 读取，不能写入配置、命令参数或 git。配置默认使用官方兼容端点、`deepseek-flash`、JSON 模式与思考模式；推理正文不保存。没有自动切换模型或服务的行为。

部署内网 Qwen 时，将 `config/models/qwen.example.json` 复制到仓库外，例如 `~/.noc7/qwen.json`，填写以下字段再使用：

| 字段 | 配置含义 |
| --- | --- |
| `base_url` | 运维核实的内网 HTTP(S) 基址，例如 `http://qwen.internal:8000/v1`，不含 `/chat/completions` |
| `model` | 内网服务实际注册的模型名，不按参数量猜名字 |
| `api_key_env` | 无鉴权时为 `null`；Bearer 鉴权时填写团队密钥环境变量名，不能填写密钥值 |
| `max_request_bytes` | 整个 UTF-8 JSON 请求体的字节上限，包含提示词和证据；需根据服务器上下文容量核实，字节数不等于 token 数 |
| `max_tokens` | 输出 token 上限，需与输入共同满足服务器上下文限制 |
| `json_mode` | 支持 `response_format` 时设为 `true`；模板为 `false`，仍要求返回严格 JSON 并在本地校验 |
| `thinking_mode` | 服务支持 `thinking` 参数时可填 `enabled` 或 `disabled`；Qwen 模板为 `null`，不向未知接口发送此参数 |

```bash
uv run noc7 analyze fixtures/bundles/SYN-S01 --provider llm \
  --model-config ~/.noc7/qwen.json --out ~/.noc7/qwen-synthetic-new
```

模板的空地址、空模型和空容量会被拒绝。Qwen 的 `external=false` 是部署者对受控内网服务的声明，代码不会通过模型名称自动识别网络边界；内网请求不使用环境中的外部 HTTP 代理。内网真实接口尚未提供，本次用模拟兼容服务验收，不代表已经内网联调。

模型只收到经现有质量门槛筛选的证据片段及必要时间、来源元数据，包含保留定位的 OCR 文字，不读取或上传原图。每条候选必须引用原文，现有 `validate_extraction()` 和业务规则继续执行。输入超限不截断；空响应、无效 JSON、输出截断、错误引用和不合格结论均拒绝，不自动回退规则。超时、连接错误、限流和服务端错误最多重试两次，其他 HTTP 错误不重试。

模型模式要求新的输出目录，避免旧报告冒充本次成功；每单失败后继续，整批有失败返回非零退出码。结果记录模型、配置指纹和提示词指纹；回放保存通过验证的抽取结果及输入摘要，不保存完整 HTTP 响应或推理正文。对真实工单生成的报告、回放和拒绝记录同样只能写仓库外。

## 目录

```text
src/noc7/
  schema/        七要素、证据、工单包、问题代码、标准答案的数据结构（Pydantic）
  bundle.py      工单包加载与校验（导入层唯一入口）
  timeparse.py   时间原文 → TimeValue
  parsers/       解析器接口与注册表；A1 放 parsers/text/，A2 放 parsers/attachments/
  extract/       文本事件、七要素抽取与分析流水线
  fuse/          精确重复与衍生来源链接
  rules/         证据引用校验、时间/恢复/原因/身份等业务规则
  report/        审核报告 Markdown/HTML 模板、公司格式故障报告（company.py，Word/HTML）与独立样式
  providers/     模型/OCR 提供方；gate.py 是数据外发闸门
  goldcheck.py   标准答案检查
  cli.py         命令行入口 noc7
schemas/         由代码导出的 JSON Schema
fixtures/
  bundles/       15 个合成工单包（见 fixtures/README.md）
  examples/      手写的示例分析结果
evals/gold/      标准答案
scripts/         合成附件生成脚本
docs/
  CONTRACTS.md           A1/A2 并行开发契约（先读这个）
  A1_TEXT_PIPELINE.md    文本链路用法、提供方、规则、测试边界
  BUNDLE_FORMAT.md       工单包格式
  ARCHITECTURE_OPTIONS.md  架构方案与已做决定
  decisions/             设计决策记录
  defense/progress.md    各阶段进度与答辩素材
```
