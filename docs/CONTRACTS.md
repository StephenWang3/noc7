# A1 / A2 并行开发契约

A0 定下的格式是后面所有阶段的公共接口。本文写清楚 **A1（文本链路）和 A2（附件）同时开发时各自能改什么、不能改什么**，保证两条线合并时不打架。设计理由见 [0003 号决策](decisions/0003-bundle-format-and-parallel-contract.md)。

## 1. 一句话版本

两条线之间只交换一种东西：**`EvidenceSpan`（带编号、可定位的证据片段）**。解析器把一份材料变成若干片段；抽取、校验、报告只读片段。A1 和 A2 不互相调用，不改对方的目录，也不改 A0 的共享文件。

```text
工单包 ──load_bundle──▶ 材料清单 ──解析器（按材料类型分给 A1 / A2）──▶ EvidenceSpan[]
                                                                        │
                                       A1：事件抽取 → 七要素 → 规则校验 → 报告
```

## 2. 材料类型归属

| 材料类型 `MaterialKind` | 负责 | 代码位置 |
| --- | --- | --- |
| `ticket_fields`（ticket.json） | A1 | `src/noc7/parsers/text/` |
| `process_log`（process_log.json） | A1 | 同上 |
| `email_html`（邮件详情页正文） | A1 | 同上 |
| `text`（粘贴的纯文本） | A1 | 同上 |
| `image`（PNG/JPEG） | A2 | `src/noc7/parsers/attachments/` |
| `pdf` | A2 | 同上 |
| `docx` | A2 | 同上 |
| `email_eml`（EML 原件） | A2 | 同上 |
| `other`（不支持的格式） | A2 | 同上 |

- 归属写在 `noc7.parsers.base.PARSER_OWNERSHIP`。注册表发现同一类型被注册两次会直接报错。
- 两个包各自导出一个 `PARSERS` 列表，`noc7.parsers.default_registry()` 会自动加载。**两条线都不需要改 `registry.py`。**
- 某个包还没交付时，它负责的类型由 `UnsupportedParser` 兜底：材料状态显示 `unsupported`，并报 `MATERIAL_UNSUPPORTED`。所以 A1 不用等 A2，就能把全部合成样本跑通（附件要素按“未知/待附件”处理）。
- EML 归 A2 是因为它要处理 MIME、附件和编码。EML 正文拆出来以后，如果需要复用 A1 的“邮件消息切分”函数，只能**调用**它，不能改它的行为；需要改就提给 A1。

## 3. 解析器规则

接口见 `src/noc7/parsers/base.py`：

```python
class Parser(Protocol):
    name: str            # 如 "a2.image"
    version: str         # 如 "0.1"
    kinds: tuple[MaterialKind, ...]
    def parse(self, ctx: ParseContext) -> ParseOutput: ...
```

1. 输入一份材料（`ParseContext` 里有工单包、材料声明、数据分级），输出 `ParseOutput`：状态、证据片段、问题。**不读其他材料，不调用其他解析器。**
2. **证据编号** `<材料编号>/<局部编号>`，例如 `M03/msg:1`、`M04/img:r2`、`M05/p3:b7`。局部编号由解析器决定，但同一输入多次解析必须得到同一编号（评测和人工修订都靠编号对齐）。`ParseOutput` 会拒绝不属于本材料的片段。建议写法：

   | 材料 | 局部编号 | 定位器 `locator.type` |
   | --- | --- | --- |
   | 字段 | `f:<field_key>` | `field` |
   | 处理过程 | `log:<seq>` | `log_entry` |
   | 邮件 | `msg:<i>[:part]`（0 = 当前消息，1 = 第一层引用…） | `email_message` |
   | PDF | `p<页>[:b<块>]` | `page`（可带 bbox） |
   | 图片 | `img[:r<区域>]` | `image_region`（像素 bbox） |
   | DOCX | `para:<i>` / `tbl:<i>:<r>:<c>` | `doc_block` |
   | 纯文本 | `t:<行>` | `text_range` |

3. **片段角色** `SpanRole`：原文 `original`、邮件引用 `quoted`、签名/免责声明 `signature`、AI 摘要等衍生内容 `derived_summary`、OCR 文字 `ocr_text`、视觉模型读数 `visual_observation`。抽取时引用原文优先，引用和摘要不算独立证据。
4. **数值要结构化**：曲线读数放 `ChartReading`（指标、单位、横轴起止原文、是否标明时区，按类别分开的 max/avg/min/首次非零），表格放 `TableReading`。不能只留一段描述文字。
5. **质量**：OCR/识图给 `quality`（0–1），拿不准就 `needs_review=True`，材料状态用 `needs_review`，并报 `MATERIAL_LOW_QUALITY`。
6. **失败不拖垮整单**：解析失败返回 `failed` 和 `MATERIAL_PARSE_FAILED`。即使解析器抛异常，注册表也会兜住并转成同样的结果。
7. **材料里的指令只当数据**：附件和邮件里“请忽略之前的指令”之类的文字不执行，片段照常保留，报 `EMBEDDED_INSTRUCTION`（P03 是测试样本）。
8. 解析结果的状态是 `parsed` 时至少要有一个片段，否则用 `needs_review` 或 `failed`。

## 4. 外发闸门

任何把材料内容发给模型或 OCR 服务的代码（A1 的文本模型、A2 的视觉模型和 OCR）**调用前都必须过** `noc7.providers.ensure_allowed(provider, data_class)`：

```python
from noc7.providers import ProviderConfig, ProviderKind, ensure_allowed

minimax = ProviderConfig(name="minimax", kind=ProviderKind.OPENAI_COMPATIBLE, external=True)
ensure_allowed(minimax, ctx.data_class)   # 真实数据 → 抛 EgressBlocked
```

- 外部服务默认只放行 `synthetic`。要放行 `real`，配置里必须写 `approval_ref`（批准依据，例如一份决策记录），否则配置本身就无法创建。
- 没有“临时绕过”开关。测试里也不要 mock 掉这一步。
- 本项目后续批准的例外：开发期允许向**官方 DeepSeek** 发送真实工单正文及本地 OCR 文字。统一文本配置必须声明 `allowed_data` 包含 `real`，并以 `docs/decisions/llm-text-providers.md` 为 `approval_ref`；仍在请求前调用 `ensure_allowed()`，不修改闸门默认策略。该批准不扩展到其他外部服务或原始图片；附件层 `ensure_attachment_allowed()` 的原图禁发规则保留。文本模型只提交有来源的摘录；责任方和地点在结构补全前独立保存为“AI 建议，待确认”，正式两栏置空，不再用规则重判模型的业务语义。其他要素的原因类别、时间语义、确认等级和现象概述继续本地重算。详见 [AI 建议决策](decisions/ai-suggestions.md)。
- 内网 Qwen 通过同一文本接口接入，由部署者核实地址及网络边界并声明为内网服务；不能因模型名为 Qwen 就把外部地址视作内网。接口资料到位前仅做兼容协议模拟验收。
- 调用 MiniMax 时按用户的限流要求：每批 10 个请求，批与批之间隔 30 秒；被限流后等 5 分钟再试。

## 5. 问题代码（只增不改）

规则、解析器、评测都用同一套问题代码（`noc7.schema.IssueCode`）。**只能追加，不能改名、删除或改含义**：标准答案和评测结果都按代码比对，改名会让历史结果失效。默认级别在 `DEFAULT_SEVERITY` 里，规则可以按情况调高。

| 代码 | 默认级别 | 含义 |
| --- | --- | --- |
| `TIME_ORDER_INVERTED` | critical | 恢复早于发生等时间倒置 |
| `NEGATIVE_DURATION` | critical | 历时为负 |
| `TIME_PLACEHOLDER` | warning | 未替换的模板占位符，如 {{end_time}} |
| `TIME_TZ_MISSING` | info | 原文无时区，按系统口径假设或无法归一 |
| `TIME_CANDIDATES_DIFFER` | warning | 同一要素有多个语义不同/数值不同的时间候选 |
| `TIME_BODY_RECORD_MISMATCH` | warning | 正文日期与记录日期不一致 |
| `DURATION_BASIS_MISMATCH` | info | 返单历时与字段起止差口径不同 |
| `ONGOING_NO_END` | info | 未见恢复：结束时间留空，不计最终历时 |
| `RECOVERY_UNVERIFIED` | warning | 有恢复字段，但没有客户确认等依据 |
| `RECOVERY_SCOPE_LIMITED` | warning | 只有范围内正常/无告警，不能视为业务恢复 |
| `CAUSE_NOT_DIAGNOSIS` | warning | 原因栏是排查结论/告警解释/恢复方式/资源状态，不是根因 |
| `CAUSE_CANDIDATE_LIST` | warning | 原因栏是可能原因清单，未确认哪项发生 |
| `RESPONSIBILITY_NO_BASIS` | info | 没有定责依据，不按供应商/处理部门补齐 |
| `OBSERVATION_SCOPE_DIFFERS` | warning | 客户与网络侧观测范围不同，不能互相否定 |
| `LOCATION_NOT_LOCATED` | info | 只有业务端点/告警位置/测试节点，未定位故障点 |
| `SERVICE_IDENTITY_UNVERIFIED` | warning | 新旧编号、带宽、拆机、归属冲突 |
| `RELATED_TICKET_SHARED_SOURCE` | info | 与其他工单共用告警：不是独立证据 |
| `RELATED_TICKET_INVALID` | warning | 关联单为作废/撤销/重复单：不作为有效结论 |
| `RELATED_TICKET_REOPENED` | info | 重开历史单：旧单结单不代表已恢复 |
| `TICKET_CANCELLED` | warning | 本单已撤销/作废：不按有效故障结案、不计历时 |
| `STATUS_VIEW_MISMATCH` | info | 列表与详情状态不一致 |
| `EVIDENCE_REF_MISSING` | critical | 引用了不存在的证据编号 |
| `EVIDENCE_QUOTE_MISMATCH` | critical | 引用的原文不在该证据片段里 |
| `DERIVED_SOURCE_DUPLICATE` | info | AI 摘要/邮件引用与原文重复，不计独立证据 |
| `DUPLICATE_CONTENT` | info | 同一结论被重复记录多次 |
| `MATERIAL_PARSE_FAILED` | warning | 材料解析失败：该材料的证据缺失，相关要素不能据此判断 |
| `MATERIAL_LOW_QUALITY` | warning | OCR/识图质量低：读数需要人工复核 |
| `MATERIAL_UNSUPPORTED` | warning | 格式不支持或解析器未实现：显式提示，不能静默漏掉 |
| `MATERIAL_MISSING` | critical | 清单声明的材料缺失/哈希不符 |
| `ATTACHMENT_FLAG_MISMATCH` | info | 日志的附件标志与实际附件不一致 |
| `EMBEDDED_INSTRUCTION` | warning | 材料里有面向系统/AI 的指令性文字，只作数据处理 |

约定：

- `TIME_TZ_MISSING` 只在时间**明显是另一种口径**时报（例如海外设备日志、无时区的上游邮件，见 P02）。源系统自身没写时区的字段按工单包的 `default_timezone` 解析、标 `assumed`，不逐条报，否则每张单都会报十几条，审核人员会忽略它。
- `ATTACHMENT_FLAG_MISMATCH` 由导入层报，只是提醒：处理过程顶层的“有无附件”标志不可靠（S10 证实），以逐条枚举到的附件为准。

## 6. 七要素的结构约束

`SevenElements` 里每个要素都有：状态、结论值、候选、证据、问题、人工审核记录。模型层面强制以下约束，违反直接校验失败（不是靠提示词约束）：

| 约束 | 说明 |
| --- | --- |
| `unknown` / `conflicted` 时结论值必须为空 | 不允许“编一个值再标未知” |
| `documented` 必须有值且有证据 | |
| `confirmed` 必须有值，且有证据或人工审核记录 | |
| `conflicted` 至少两个候选 | |
| `selected` 必须指向已有候选 | 时间等要素说明结论取自哪个候选 |
| 故障原因的结论只能是 `root_cause_confirmed` / `root_cause_claimed` / `planned_work` | 排查结论、可能原因清单、恢复方式、资源状态只能留在候选里（S02、S05、S09、X01） |
| 故障地点的结论必须是 `located_fault_point` | 告警位置、业务端点、测试节点都不是故障点（S04） |
| 责任方不能来自 `inferred_from_role` | 不能因为是供应商或处理部门就定责（S06、S09） |
| 分析结果里引用的证据编号必须存在 | `AnalysisResult` 校验时拦截编造的引用 |

### AI 建议与引用核验

`Extraction` 和 `AnalysisResult` 新增默认空的 `suggestions`、`quote_checks`，兼容旧结果和旧回放。建议只允许责任方和地点，保存原始业务 JSON 与本地核验记录，不属于 `SevenElements`。建议来源纳入引用完整性校验，不能提交人工审核记录；建议的原状态或角色不会成为正式状态或角色。

建议未填写来源或候选不是对象时原样保留并标“缺少来源，待核对”，空栏／非对象栏按模型未给出展示；`evidence_refs: null` 视为空列表。只有已引用但不存在的证据编号仍拒绝；建议引文不匹配保留并标待核对，正式引用实质不匹配继续拒绝。共享匹配只折叠连续 Unicode 空白，匹配记录保留原文字符范围，不改源证据。审核报告显示建议和空白等价记录，公司报告和正式评分只读取正式元素。

## 7. 各条线能改什么

| 文件/目录 | A1 | A2 | 说明 |
| --- | --- | --- | --- |
| `src/noc7/parsers/text/` | ✅ | ❌ | |
| `src/noc7/parsers/attachments/`、`src/noc7/ocr/` 等 | ❌ | ✅ | |
| `src/noc7/extract/`、`rules/`、`fuse/`、`report/` | ✅ | ❌ | A2 只产出片段，不写抽取逻辑 |
| `src/noc7/providers/`（新增具体提供方） | ✅ 文本 | ✅ 视觉/OCR | 各自新建文件；不改 `gate.py` |
| `tests/` | 新建 `tests/a1/` | 新建 `tests/a2/` | 不改 A0 已有测试 |
| `fixtures/bundles/`、`evals/gold/` | ❌ | ❌ | 改动需要单独提出（见下） |
| `src/noc7/schema/`、`bundle.py`、`parsers/base.py`、`parsers/registry.py`、`providers/gate.py` | ❌ | ❌ | A0 共享契约 |
| `pyproject.toml` / `uv.lock` | ❌ | ❌ | 已在 A0 预先声明 BeautifulSoup、Jinja2、PyMuPDF、python-docx、Pillow；确需新依赖时只追加一行并在说明里写明 |
| `schemas/*.schema.json` | 自动生成 | 自动生成 | 只由 `noc7 schema export` 写入 |

## 8. 契约要变时怎么办

1. 只**追加**：新增可选字段（有默认值）、新增枚举值、新增问题代码，都是兼容变更。在合并说明里写清楚，并运行 `uv run noc7 schema export` 更新 `schemas/`。
2. 不兼容变更（改名、删字段、改语义、改编号规则）要单独写一份决策记录，并同时更新标准答案和示例结果；`tests/test_schema.py` 和 `noc7 schema check` 会拦下忘记同步的情况。
3. 发现标准答案标错：改 `evals/gold/` 时在提交说明里写理由，并跑 `uv run noc7 gold check`。
