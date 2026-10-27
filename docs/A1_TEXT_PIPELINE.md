# A1 文本链路：运行与接口

A1 沿用 A0 的工单包、`EvidenceSpan` 和 `AnalysisResult`，实现字段/处理过程/邮件 HTML/纯文本解析、事件与七要素抽取、确定性规则及 Markdown/HTML 报告。输入仍先经过 `load_bundle`，没有第二套输入格式。

## 运行

```bash
uv sync
uv run noc7 analyze                         # 全部 15 个合成包，输出到 var/reports/
uv run noc7 analyze fixtures/bundles/SYN-S09 --out var/reports
uv run noc7 analyze fixtures/bundles/SYN-P04 --report-type closure
uv run pytest -q
```

每个工单包输出到 `<输出目录>/<工单包目录名>/`：

| 文件 | 用途 |
| --- | --- |
| `analysis.json` | A0 schema 的完整分析结果：材料状态、原文证据、事件、七要素、规则问题、版本和输入快照 |
| `report.md` | 可审核的 Markdown 报告 |
| `report.html` | 可直接打开的 HTML 报告，依据链接跳转到本页证据索引 |
| `report.css` | HTML 的相对路径样式文件，和 HTML 放在一起 |
| `replay.json` | 仅在 `--save-replay` 时生成；绑定输入与解析证据的离线回放记录 |
| `analysis-rejected.json` | 仅在证据校验拒绝提供方输出时生成；记录问题代码，不保存不合格结论 |

报告包括生成时间、数据截止、事件概述、七要素与全部候选、处理时间线、恢复验证、未决事项、服务身份、关联单、材料完整性、内部证据索引、审核记录。`stage` 是阶段报告，`closure` 是结案草稿，两者均标为待人工审核。正式模板尚未提供，结构按 PRD §8。

已经生成的两份合成示例位于 [S09 阶段报告](examples/a1/SYN-S09/report.html) 和 [P04 结案草稿](examples/a1/SYN-P04/report.html)。在变更审核中对 HTML 文件点击预览即可查看，样式使用同目录的 `report.css`。S09 展示“系统记载恢复，但未见客户确认、根因未知”，P04 展示现场定位、正式定责和恢复确认。

## 两种提供方

`rules` 是实际运行的本地规则基线，不调用外部服务，也不读取标准答案。它保留原文和候选，使用有限的词法规则归类时间、观测、原因、责任与地点。它不是通用语言模型，未识别的表达可能漏抽，需要人工审核。

`replay` 回放预先保存的 `Extraction`。可以录制本地基线输出，也可以由后续获准模型适配器提供同结构输出；回放不是一次新的模型调用，也不能证明模型质量。

```bash
# 先录制全部样本
uv run noc7 analyze --out var/recorded --save-replay
# 再按相同工单和相同解析结果回放
uv run noc7 analyze --provider replay --replay var/recorded --out var/replayed
# 单个包也可以直接指定一份 replay.json
uv run noc7 analyze fixtures/bundles/SYN-S09 --provider replay \
  --replay var/recorded/SYN-S09/replay.json --out var/replayed
```

回放检查两份哈希：A0 的 `manifest.json` 快照和全部实际解析证据的规范化 JSON。材料变更、证据切分、角色或定位器变化都会拒绝旧回放，避免把旧答案误套到新材料上。提供方名称会写入 `run.provider`。

不存在的证据编号、伪造引用原文、伪造时间归一值、无依据地把供应商改成责任方等会抛 `ExtractionRejected`。CLI 返回非零，记录 `analysis-rejected.json`，不生成本次报告。旧报告不会因此被删除；复用输出目录时以快照和生成时间区分运行。其他输入错误也返回非零；批量处理继续分析其余有效工单。

## 给 A2 / A3 的接口

```python
from noc7.extract import analyze
from noc7.report import render

result = analyze("fixtures/bundles/SYN-S09")  # AnalysisResult
html = render(result, format="html", report_type="stage")
```

流水线实现位于 `noc7.extract.pipeline`。默认注册表自动加载 A2 的 `PARSERS`；A1 不导入 A2 的具体解析器。A2 尚未交付时，图片/PDF/DOCX/EML 显式显示 `unsupported`，报告不能称材料完整。A1 测试用独立文本注册表固定消融边界，A2 合入后也不会重复注册附件类型。

A2 的 EML 可以复用以下函数，均不读其他材料、不访问网络：

```python
from noc7.parsers.text.email import split_email, email_spans

parts = split_email(body_text, is_html=False)  # list[EmailPart]
spans = email_spans(body_text, material_id="M03", extractor="a2.email_eml@1", is_html=False)
```

`EmailPart` 包含 `message_index`、`part`、`text`、`role`、可选 `reading`。`email_spans` 为当前消息分配 0，引用从 1 起；正文、头、签名、表格各有定位器，多个表格追加稳定序号。HTML 的脚本、样式、iframe 不作为正文，不执行脚本、不请求外链；隐藏的指令性文字仍保留并标记问题。通用文本材料按 UTF-8 行与字符区间定位。

结构化 `ChartReading` 按类别进入观测候选，保留最大/平均/最小读数；首次非零保留为 `chart_first_nonzero`，不自动认定为起障。`TableReading` 保留在证据与报告索引里。低质量/待复核片段不产生自动结论。

本次没有修改 A0 的 schema、注册表、工单包、标准答案或依赖锁文件。需要扩展接口时仍按 `CONTRACTS.md` §8：先记录需求，只追加有默认值的可选字段/枚举/问题码，统一导出 schema 并跑共享检查；不在两条线各造一个字段。事件/抽取提供方的内部结构留在 A1 目录，不扩散到共享契约。

## 规则与业务口径

| 规则组 | 实现行为 |
| --- | --- |
| 时间 | 保留字段、客户陈述、告警、预警、建单、返单、关单、正文日期等语义；冲突不取最早/最后一个覆盖；检查倒置、负历时、占位符、正文/记录日差、时区缺失、返单历时口径差 |
| 时区与日期 | 显式 UTC/GMT+8 按偏移比较；海外设备未标时区时保留未知；裸时刻补日期时注明同条记录/邮件头依据；明确时区的邮件先换到该时区确定日期；跨午夜的告警时刻可以与匹配的发生字段对齐，引用两处证据，不改写原文 |
| 恢复 | 系统恢复字段只能作记载；客户确认可提升状态；“同意结单”“无告警”“范围内正常”不能替代确认；结束时间未知/冲突、未确认或已撤单时不生成最终历时 |
| 原因、责任、地点 | 排查结论、可能原因清单、自恢、资源状态和处理阻塞只保留候选；未来作业不当作已发生原因；供应商/经办人不定责；业务端点/告警位置/测试节点不自动变成故障点 |
| 观测 | 客户与网管观测分别保存归属、数值、单位、原文范围，不用节点正常抹掉客户现象 |
| 身份与关联 | 编号变迁、拆机、未交接、归属疑问给核实提示；共用告警不增加独立证据；撤销/作废/重开保留状态，不合并最终结论 |
| 去重 | 原文全保留，精确重复链接 `derived_from`；重复处理记录不重复进入七要素的处理过程；事件保留 `duplicate_of`；引用和摘要不计作新增独立佐证；无法可靠链接的摘要不臆造来源关系 |
| 证据与材料 | 检查引用存在、原文一致、候选与结论一致及特定语义；单材料失败不拖垮其他材料；缺失/哈希不符由 A0 在分析前拒绝；低质量与不支持均可见 |
| 材料指令 | 指令仍在原文索引，命中的整行不进入自动抽取，不执行工具或外发动作 |

规则问题会写入结果的 `issues`，要素相关问题也同步到要素的 `issues`。报告模板不调用模型，不添加事实。HTML 显式自动转义，Markdown 同时转义 HTML 和链接/图片等语法。

质量阈值暂定 `0.7`（代码常量 `QUALITY_REVIEW_THRESHOLD`），仅是保守工程门槛，依据为本次工程判断，不是经业务校准的准确率或概率。不同 A2 提供方的质量分可能不可直接比较，后续应校准；任何 `needs_review` 标记均优先阻止自动结论。

## 测试边界

`tests/a1/` 覆盖 15 个合成工单包的结构、期望问题与文本可判定的状态，以及伪造提供方、报告转义、回放快照、附件失败/低质量、A2 结构化读数接口和批量 CLI。

实施计划 §7 的逐项映射：

| 必测用例 | 测试位置 / 边界 |
| --- | --- |
| 原因栏正常检查，根因未知 | `test_pipeline.py::test_normal_checks_are_not_cause_or_recovery`，`test_provider_and_rules.py::test_cause_semantics_generalize_without_ticket_ids` |
| 供应商无定责依据 | `test_pipeline.py::test_vendor_role_and_alarm_location_do_not_become_conclusions` |
| 系统恢复无客户确认 | `test_pipeline.py::test_normal_checks_are_not_cause_or_recovery`，`test_provider_and_rules.py::test_model_cannot_fabricate_customer_confirmation` |
| 客户高丢包、某节点正常 | `test_pipeline.py::test_normal_checks_are_not_cause_or_recovery`（合成集用 25% 等改写值，保持同一问题模式） |
| 旧 CID 取消、新 CID 未交接 | `test_pipeline.py::test_identity_resource_state_is_not_root_cause`；保留编号与资源状态候选，不认作根因 |
| 告警、预警、建单时刻不同 | `test_pipeline.py::test_start_candidates_keep_semantics_not_earliest_timestamp` |
| UTC / GMT+8 跨日 | `test_provider_and_rules.py::test_explicit_cross_day_times`、`test_mail_clock_uses_date_in_explicit_zone_not_utc_header_date` |
| 海外设备无时区 | `test_provider_and_rules.py::test_overseas_log_timezone_is_not_inferred_from_city` |
| 正文与记录日期冲突 | `test_pipeline.py::test_body_date_conflict_is_retained` |
| 作废单与有效单同电路 | `test_pipeline.py::test_injection_quarantine_and_invalid_related_ticket` |
| 原邮件及 AI 摘要重复 | `test_pipeline.py::test_dedup_preserves_raw_spans_and_source_links`、`test_text_parsers.py::test_nested_email_retains_headers_quotes_and_signatures` |
| 模型返回不存在证据 | `test_provider_and_rules.py::test_nonexistent_evidence_is_rejected_and_failure_has_code`、`test_reports_cli.py::test_cli_rejects_corrupt_replay_without_creating_report` |
| 附件缺失、OCR 模糊/表格错位 | `test_reports_cli.py::test_missing_attachment_refuses_import_and_batch_continues`、`test_provider_and_rules.py::test_attachment_failure_and_low_quality_do_not_create_conclusions`；实际 OCR/表格识别准确性由 A2 测试 |
| 附件/邮件中忽略规则、发送数据的指令 | `test_pipeline.py::test_injection_quarantine_and_invalid_related_ticket`；A2 的相同问题码也进入结果 |
| 并发人工修订与分析重跑 | 依赖 A3 的持久化修订与版本接口；A1 无审核写入入口，并拒绝提供方注入 `ReviewInfo`。不能用离线测试冒充已验证并发审核 |
| 未授权用户获取原文/预览/导出 | 依赖 A3 的服务端身份和工单权限；A1 是本机库/CLI，没有 HTTP 或用户会话，不提供网络服务，不宣称权限用例已通过 |

架构文档 §6 的 A1 是离线文本链路，界面属于 A3，因此旧实施计划 §7 中最后两项按实际依赖留给 A3。其余条目在本阶段落实；附件格式识别和真实 OCR 由 A2 承担。测试不连接真实 NOC，不调用外部模型。合成样本回归通过不等于真实工单准确率已达标，完整指标评测仍属 A4。

真实工单及分析结果、报告、回放一律写在仓库外。CLI 默认输出在仓库内的 `var/`，处理真实工单时应显式使用 `--out ~/.noc7/real-reports`，程序会拒绝向源码仓库写真实产物。本次未读取真实工单、未使用任何密钥、未调用 MiniMax；未来外部适配器仍必须经过 A0 外发闸门，MiniMax 按每批 10 个、批间 30 秒、限流后 5 分钟重试执行。
