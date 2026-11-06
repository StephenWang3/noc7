# 恢复时间业务取值规则核验

最新充值后批次已完成：**实际模型请求 22 次，每张一次，21 张成功、1 张拒绝，恢复正式填出 10/22**。修改前保存基线为 9/22；同一批新回答按旧规则禁网重算为 9/22。本批及请求用量详见文末“充值后限额串行试跑”，前段保留首轮试跑与评审历史。

## 首轮试跑结果（历史）

代码已实现，评审修正后通过全量 **694 项测试**。下列首次真实试跑使用修正前提示词，修正说明见末节。相同二十二张已结单工单各发起一次新模型请求，最终禁网重建 **8 张成功、14 张失败**：八次 HTTP 503，六次模型正文／结构不合格；没有自动重试，失败保留在分母。试跑阶段另有一张报告渲染失败，修复模板兼容后用原响应离线恢复，未增加模型调用。以下均为最终重建结果。

| 指标／22 | 修改前完整结果 | 本次新回答＋新规则 |
| --- | ---: | ---: |
| 可交付报告 | 21 | 8 |
| 起障正式填出 | 14 | 6 |
| 恢复正式填出 | 9 | 0 |
| 原因正式填出 | 16 | 5 |
| 拒绝／失败 | 1 | 14 |

**本批不能证明恢复效果提高，也不能将九到零全部归因于新规则。** 用同一批新回答按旧规则禁网重建，恢复本来也是零／二十二；八张成功结果中起障六张、原因五张均与新规则相同。八份原始三栏、全部非恢复要素、事件、处理过程、建议、身份和证据逐项一致。新旧规则都未新增或撤回正式恢复值。

| 同一新回答的恢复状态／22 | 旧冲突规则 | 新来源规则 |
| --- | ---: | ---: |
| `documented`／`confirmed` | 0 | 0 |
| `conflicted` | 5 | 0 |
| `unknown` | 3 | 8 |
| 失败 | 14 | 14 |

五张从冲突变为未知，是因为没有候选同时满足来源和时间资格，**不是来源冲突已被证实解决**；竞争时间全部保留。与历史结果相比，原九张已填中三张本次成功但留空，另外六张本次失败未交付，不能统称为九张“规则撤回”。原十张程序冲突单中四张本次成功且为未知，六张本次失败，不能据此宣称原来源竞争单已经完成真实业务验收。历史已知协议 Up 语义误放也不因本次零填出就视为已修复。

## 留空原因与核验边界

八张成功报告共保留二十条恢复栏候选：十六条来源未知，四条有来源依据。十二条通过既有关系／时间资格，但来源均为未知，不使用系统恢复字段兜底。四条有来源依据的候选分别被以下约束阻止：

| 来源声明 | 候选数 | 未采用原因 |
| --- | ---: | --- |
| 联通网管 | 1 | 关系上下文没有包含候选时间原串 |
| 客户 | 1 | 实际为客户确认动作，不能替代业务恢复 |
| 客户 | 1 | 日期／时区锚点不一致或缺少完整分钟级时间 |
| 客户 | 1 | 时区未知 |

四条来源依据引文均与完整证据严格匹配；引文匹配不证明来源语义或恢复含义正确。未知来源是本次模型声明及关系资格的结果，不代表材料原文没有线索，不用词表补选，也不把缺少独立业务审核写成“已验证正确”。私有逐单核对表保存全部候选、来源依据、原文、排除原因及待独立审核标记。

本批没有同时具备可采用时间和三类明确来源的候选，因此没有真实正例覆盖“阈值内取早／超阈值按来源优先”。这部分算法由合成边界测试验证；十四张模型异常及八张待核实需要和代码测试结果分开看，不能称为业务准确率验收通过。

独立时间表示核验为 **30 条匹配、2 条未评估、0 条不匹配**；未评估不计正确。八份成功结果的保存回放均与提取结果相等，完整证据校验通过，公司 Word 包结构有效。真实输入输出、逐单复核及失败详情仅留在私有目录。

## 取值规则与统计口径

采用用户确认的“全部接近取最早，否则按客户→供应商 RFO→联通网管优先”的规则。单来源可采用，三类皆无留空；最高优先来源内部超过阈值且无明确更正时保留冲突，不降级取其他来源。阈值默认三十分钟，可通过 `NOC7_RECOVERY_CLOSE_MINUTES` 调整，数值暂定、待业务方确认。完整边界见 [决策记录](decisions/recovery-time-selection.md)。

主分母固定为原映射中详情已结单的二十二张，失败和拒绝不从分母删除。前置修复正式恢复填出为九／二十二；其中程序状态为 `conflicted` 的有十张，前置报告另描述八张来源竞争；本次不将该调查数当成全部程序冲突分母，以保存结果重新计数的十张为准。已填出及引文存在都不等于业务语义正确，基线已知误放继续单列。

本次新增来源关系，因此需要每张一次新模型回答；旧原回答缺来源不能冒充新能力。新旧回答之间比较只能反映整体结果变化，不能全部归因于本地规则；另把同一新回答分别用旧冲突策略和新来源策略禁网重算，单独量化本地规则作用。

## 复现方法与私有留档

原包映射为 `~/.noc7/full-ticket-trial-20261029-r1/`；前置响应为 `~/.noc7/time-cause-validation-trial/`；修改前完整结果为 `~/.noc7/recovery-time-fixes-review-replay/`。冻结记录在 `~/.noc7/recovery-selection-freeze/`，包括输入包／请求证据／响应绑定、历史文件哈希、规则预期与逐单复核表；包加载同时校验全部材料哈希。

新输出均使用不存在的独立私有目录。以下目录为本次实际留档，复现须换新目录；真实原文、身份、逐单输出、完整请求和响应均不进入 git。

```sh
uv run python scripts/check_time_cause.py trial \
  --baseline ~/.noc7/full-ticket-trial-20261029-r1 \
  --responses ~/.noc7/time-cause-validation-trial --closed-only \
  --expectations ~/.noc7/recovery-selection-freeze/expectations.json \
  --compare-results ~/.noc7/recovery-time-fixes-review-replay \
  --compare-new-responses --workers 3 \
  --out ~/.noc7/recovery-selection-trial

uv run python scripts/check_time_cause.py replay \
  --baseline ~/.noc7/full-ticket-trial-20261029-r1 \
  --responses ~/.noc7/recovery-selection-trial --closed-only \
  --keep-request-failures --legacy-recovery \
  --expectations ~/.noc7/recovery-selection-freeze/expectations.json \
  --out ~/.noc7/recovery-selection-same-response-legacy

uv run python scripts/check_time_cause.py replay \
  --baseline ~/.noc7/full-ticket-trial-20261029-r1 \
  --responses ~/.noc7/recovery-selection-trial --closed-only \
  --keep-request-failures \
  --expectations ~/.noc7/recovery-selection-freeze/expectations.json \
  --compare-results ~/.noc7/recovery-time-fixes-review-replay \
  --compare-new-responses \
  --compare-local-results ~/.noc7/recovery-selection-same-response-legacy \
  --out ~/.noc7/recovery-selection-final
```

`trial` 使用获准的 DeepSeek 官方文本配置，关闭自动重试；`--responses` 在该模式只提供旧请求证据绑定，仍发送一次新请求。离线模式禁用 socket，HTTP／连接失败只在唯一审计证实请求已失败时保留，没有审计或只有准备状态不能猜成失败。`--compare-new-responses` 只放开响应哈希差异，仍核对原包与实际请求证据；`--compare-local-results` 严格要求同一响应。

每单保存 `comparison.json`、`local-comparison.json`、`metrics.json`、审核报告、公司 HTML／Word 和回放；失败保留审计及错误类别。来源未知是模型声明／未提供可用来源关系的结果，不证明材料没有恢复线索；不能用来源字段存在或精确引用匹配替代独立业务审核。

## 兼容与程序验证

- 旧三十一张原响应按原恢复规则禁网重建：三十成功、一张原有引文拒绝；已结单恢复维持九／二十二，起障十四／二十二，原因十六／二十二；其他状态九张结果不变。三十份旧保存回放直接读取并通过当前完整证据校验，没有自动升级或改写。
- 冻结的一百二十五份历史文件哈希未变；本次二十二份唯一请求审计与最终响应哈希绑定逐项核对。最终 `source-binding.json` 指向实际新响应，旧请求输入绑定另存 `input-binding.json`，审计原文保留。
- 全量 `uv run pytest -q`：683 项通过，七条既有依赖弃用警告；`uv run noc7 schema check`、`git diff --check` 通过。
- 默认合成完整链路十五包可运行，仍有两包与历史 gold 的原因／地点状态存在差异。修改前后输出逐项相同；没有新增差异，也没有改 gold 使检查变绿。
- 合成测试覆盖阈值内／边界／超限、零阈值、单来源、来源缺失、同级冲突、低优先来源矛盾披露、不同事件／范围／恢复轮次、更正与编号歧义、失效更正不复活旧值、不同偏移同瞬间、缺日期／精度／时区、协议与确认动作、恢复早于起障、来源引文硬拒绝、非法配置发送前失败，以及回放不受环境变量后续变化影响。

旧链路兼容重建的复现命令如下，同样必须换新的输出目录：

```sh
uv run python scripts/check_time_cause.py replay \
  --baseline ~/.noc7/full-ticket-trial-20261029-r1 \
  --responses ~/.noc7/time-cause-validation-trial --legacy-recovery \
  --expectations ~/.noc7/time-cause-review-fixes-final/frozen-expectations.json \
  --compare-results ~/.noc7/recovery-time-fixes-review-replay \
  --out ~/.noc7/recovery-selection-legacy-compatibility
```

最终汇总为 `~/.noc7/recovery-selection-final/summary.json`，逐单结构和来源复核为 `~/.noc7/recovery-selection-freeze/final-review.json`，绑定／非恢复字段／历史哈希核验为同目录 `final-verification.json`。这些是本地核验位置，仓库只保存本报告的脱敏统计。

## 评审修正：明确来源标注与无效更正链接

前述二十二张结果对应修正前提示词。复核八份原始模型回答确认，二十条恢复候选都显式提交了来源，其中十六条直接为 `unknown`，不是缺字段被 Schema 补上。先前提示词缺少正向归类要求及完整恢复示例，不能把该批未知来源全部解释为材料没有来源。

现提示词要求通读整份证据：客户报告、供应商 RFO 正文、联通自行追加的实际业务恢复陈述分别明确归类；字段只有时间戳时继续查找另一段对应来源原文，填入依据并同时引用字段和正文。只有找不到与该时刻、事件及范围对应的来源时才使用未知。完整 `end_time` 示例采用 `customer`，来源依据来自另一日志证据。联通恢复陈述无需出现“网管”二字，双向流量等观测不升级为业务恢复。Schema 缺省仍用于旧数据兼容，不作为新模型的默认答案。

对时间本身合格的候选，缺少更正依据、编号无效、自指或跨来源／分组的更正链接只记入审计，忽略链接后继续比较并存时间。新增十分钟、三十分钟边界反例确认仍取最早；跨来源无效更正相差两小时仍取客户时间。时间本身不合格却声明更正的保护、循环更正冲突及实质引文不匹配硬拒绝保留。

三类来源的字段时间＋另一段来源引文均通过完整解码、引用核验及最终采用测试；这是结构与流水线测试，不是模型实际分类效果测试。定向测试一百六十五项、全量六百九十四项通过，七条既有依赖警告不变；Schema 与差异检查通过。本轮不追加真实模型请求，不修改先前统计，也不宣称修订提示词已经提高来源识别或恢复填出。

使用同一批二十二张保存响应执行禁网完整回归，输出到新的 `~/.noc7/recovery-selection-review-replay/`：仍为八张成功、十四张既有模型失败；全部状态与比较字段无变化，八张原始三栏一致，回放及 Word 包结构通过。二十二张响应哈希绑定逐项相同，一百二十五份历史文件哈希未变。旧响应不会因修改提示词就重分类，因此该回归不证明新提示词的实际来源识别效果。

## 充值后限额串行试跑

### 请求预算与实际次数

本次同一批二十二张已结单工单全部处理完毕，**一共发起二十二次真实 DeepSeek 模型请求**：每张恰好一次，`workers=1`、`max_retries=0`，没有自动重试或补发。二十二份请求审计的 `request_attempts` 均为一，均使用本次冻结的最新提示词。没有发起用于余额探测、修改前基线、合成测试、兼容回归或同回答规则对照的额外模型请求。

| 本批调用控制 | 实际结果 |
| --- | --- |
| 目标／已处理／已请求 | 22／22／22 |
| 真实模型请求总次数 | **22** |
| 单张最大请求次数／并发数 | 1／1 |
| 自动重试／补发／未开始 | 0／0／0 |
| HTTP 402／HTTP 503 | 0／0 |
| 返回内容不合格 | 1 张，引用了不存在的证据编号，`EVIDENCE_REF_MISSING` |
| 连续异常达到三张 | 未发生；该次拒绝后下一张成功，计数清零 |
| 停发原因 | 未触发停发条件，按授权处理完全部二十二张 |

接口二十二次响应均返回 `usage`：输入 token 合计 1,060,932，生成 token（含推理）合计 398,715，总计 1,459,647。以上为接口字段汇总，不估算金额；请求总次数以本地请求审计为准。原始响应和用量记录仅保存在私有目录。

串行执行器在下一张开始前判定停发，未预提交后续任务；402 立即停发，503／内容不合格混合连续三张时停发。未开始的工单单列，不会伪装成失败。停发规则已用本地模拟结果验证，真实批次没有触发这两种停发条件。

### 与保存基线及同一回答的对照

修改前直接读取 `~/.noc7/recovery-time-fixes-review-replay/`，没有重新请求。最终结果全部用本次保存回答禁网重建；同一回答下的旧规则结果也完全禁网生成。

| 指标／22 | 修改前保存结果 | 本次新回答＋新规则 |
| --- | ---: | ---: |
| 可交付报告 | 21 | 21 |
| 起障正式填出 | 14 | 14 |
| 恢复正式填出 | 9 | **10** |
| 原因正式填出 | 16 | 16 |
| 拒绝 | 1 | 1 |

拒绝身份发生变化：原一张拒绝单本次可交付，另一张原可交付单本次因不存在的证据引用被拒。共同交付的二十张中，恢复新增采用四张、撤回两张；另有一张原恢复已填的工单本次整单拒绝，原拒绝单本次恢复仍未填。总数相同不代表起障、原因或候选逐单未变；这些是新模型回答与本地处理共同作用的前后结果，**不是准确率**。

固定本次新回答，只切换本地恢复规则，得到以下独立对照：

| 同一新回答／22 | 旧冲突规则 | 新来源规则 |
| --- | ---: | ---: |
| 恢复正式填出 | 9 | **10** |
| `documented`／`confirmed` | 5／4 | 6／4 |
| `conflicted`／`unknown` | 11／1 | 0／11 |
| 拒绝 | 1 | 1 |

新规则相对同回答旧规则**新增采用五张、撤回四张**，净增一张；共同保留的五张正式恢复，其最终 UTC 时刻没有变化。二十一份成功结果的原始三栏相同，全部非恢复要素、事件、处理过程、身份、建议及完整证据逐项不变。撤回与未知状态由来源及时间资格决定，不能把冲突转为未知当成真实分歧已经解决。

保存基线中的十张程序恢复冲突单，本次四张正式采用、六张仍未知；不沿用前置“约八张”调查描述作为全部程序冲突分母，也不宣称原有竞争来源已全部验收通过。

### 来源、采用原因与核验边界

本次二十二份原始回答的恢复栏共五十五条候选，来源显式值为：客户十一、供应商 RFO 六、联通网管五、`unknown` 二十九、`null` 四。该统计包含最终被拒绝的回答，不能等同正式来源结论；尤其不能把显式未知或空值都说成 Schema 默认填充。

二十一份成功结果保留五十一条候选：二十条形成明确三类来源记录、二十七条来源未知，另四条关系未形成可用结构。最终十个正式恢复的来源为**客户五、供应商 RFO 二、联通网管三**；其中六个采用系统默认时区并披露 `assumed`，四个为显式时区。其余十一张在本次模型关系与本地校验下没有同时满足来源、上下文及完整时间要求的候选，不证明原材料没有恢复陈述。

十项正式采用中，九项在资格筛选后只有一个合格候选，一项为同来源多个接近候选；本批未产生两个合格不同来源之间触发阈值取早或超阈值优先的真实正例。这两种跨来源边界仍由合成测试验证。四个自动 `confirmed` 不是人工审核；来源引文可定位、时间归一有据和填出增多均不等于业务语义正确，基线已知语义误放也不能仅因本次拒绝或改选就宣布修复。

独立时间表示核验为八十条匹配、六条未评估、零条不匹配；未评估不计正确。二十一份成功结果均通过完整证据校验、保存回放一致性和公司 Word 包结构核验。模型判断及全部逐单排除理由保存在私有复核表，正式值仍需业务审核。

### 程序验证与留档

全量测试 **701 项通过**，七条既有依赖弃用警告；测试进程禁止连接外网，HTTP 测试只使用本机模拟服务，没有真实模型调用。新增验证覆盖 402 后不启动下一张、503 与不合格内容混合累计三张、成功打断连续计数、停发后保留未开始集合，以及离线只读取已请求子集。Schema 与差异检查通过。

实际留档如下；真实原文、身份、请求响应、逐单报告及复核记录均不进 git。

- `~/.noc7/recovery-selection-budget-trial/`：在线审计、`execution-policy.json`、逐张完成后的 `run-control.json`、实际响应绑定及请求次数。在线结束后没有继续调用 DeepSeek。
- `~/.noc7/recovery-selection-budget-legacy/`：同一新回答按旧规则禁网重算。
- `~/.noc7/recovery-selection-budget-final/`：新规则禁网完整结果、保存基线对照及同回答本地对照。
- `~/.noc7/recovery-selection-budget-freeze/`：冻结提示词、保存基线哈希、`verification.json`、`coverage.json` 和 `case-review.json`。二十二份实际响应绑定逐项核对，保存基线的一百五十九份 JSON 哈希未变。

以下在线命令仅记录本批已经执行的操作，本次不再执行。复核本批保存回答使用后两条禁网命令，输出目录须换成不存在的新目录。

```sh
uv run python scripts/check_time_cause.py trial \
  --baseline ~/.noc7/full-ticket-trial-20261029-r1 \
  --responses ~/.noc7/time-cause-validation-trial --closed-only \
  --expectations ~/.noc7/recovery-selection-budget-freeze/expectations.json \
  --compare-results ~/.noc7/recovery-time-fixes-review-replay --compare-new-responses \
  --workers 1 --conservative-trial --out ~/.noc7/recovery-selection-budget-trial

uv run python scripts/check_time_cause.py replay \
  --baseline ~/.noc7/full-ticket-trial-20261029-r1 \
  --responses ~/.noc7/recovery-selection-budget-trial --closed-only \
  --attempted-only --keep-request-failures --legacy-recovery \
  --expectations ~/.noc7/recovery-selection-budget-freeze/expectations.json \
  --out ~/.noc7/recovery-selection-budget-legacy

uv run python scripts/check_time_cause.py replay \
  --baseline ~/.noc7/full-ticket-trial-20261029-r1 \
  --responses ~/.noc7/recovery-selection-budget-trial --closed-only \
  --attempted-only --keep-request-failures \
  --expectations ~/.noc7/recovery-selection-budget-freeze/expectations.json \
  --compare-results ~/.noc7/recovery-time-fixes-review-replay --compare-new-responses \
  --compare-local-results ~/.noc7/recovery-selection-budget-legacy \
  --out ~/.noc7/recovery-selection-budget-final
```

离线命令中的 worker 只并行本机解析与回放，执行时禁用 socket，不产生模型请求。
