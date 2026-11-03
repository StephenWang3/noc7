# 恢复时间业务取值规则核验

## 结果

代码已实现并通过全量 **683 项测试**。相同二十二张已结单工单各发起一次新模型请求，最终禁网重建 **8 张成功、14 张失败**：八次 HTTP 503，六次模型正文／结构不合格；没有自动重试，失败保留在分母。试跑阶段另有一张报告渲染失败，修复模板兼容后用原响应离线恢复，未增加模型调用。以下均为最终重建结果。

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
