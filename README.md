# noc7

NOC 故障工单七要素提取：把工单字段、处理过程、邮件和附件整理成**带证据的七要素 JSON**（起障时间、结束时间、故障现象、责任方、原因、处理过程、故障地点），经规则校验后生成 Markdown/HTML 报告。

设计原则是“证据优先”：所有材料先切成带编号、可定位的证据片段，结论必须引用片段；没有依据的要素保持“未知”，互相矛盾的保留全部候选，不静默填满。

> 仓库里的工单全部是**合成数据**（编号以 `SYN-` 开头）。真实工单只存放在仓库外的本机目录（默认 `~/.noc7/real/`），不提交、不发给外部服务。

## 当前进度

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| A0 地基 | 项目骨架、七要素 schema、工单包格式、15 个合成工单包及标准答案、并行开发契约 | ✅ |
| A1 文本链路 | 字段/处理过程/邮件解析、规则与回放、抽取、规则校验、Markdown/HTML 报告 | ✅（详见 [运行与边界](docs/A1_TEXT_PIPELINE.md)） |
| A2 附件 | 图片、PDF、DOCX、EML 解析，OCR 与视觉模型 | 待开始 |
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
uv run noc7 analyze                      # 分析全部合成包，生成 JSON/Markdown/HTML
uv run noc7 analyze --save-replay        # 同时录制离线回放快照
uv run noc7 analyze --provider replay --replay var/reports --out var/replayed
uv run noc7 bundle rehash <工单包目录>    # 编写合成样本时重算清单里的哈希
uv run --group fixtures python scripts/make_fixture_assets.py   # 重新生成合成附件（PNG/PDF/DOCX）
```

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
  report/        Markdown/HTML 模板与独立样式
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
