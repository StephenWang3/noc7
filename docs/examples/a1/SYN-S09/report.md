# SYN\-S09 · 阶段报告

> 合成演示数据，不代表真实工单或真实模型质量。

报告版本：1\.0；待人工审核。生成：2026\-10\-27T13:05:01\.359313\+00:00；数据截止：2026\-09\-29T10:30:00\+08:00。

分析来源：rules；规则 1\.0；输入快照：3b5a15345f1ced9d6c42edd2425ddbb95e2ebd58c990ab81b724eccd0302f21e。

## 事件概述

客户反馈：Circuit ID: SYN\-CKT\-1009<br>Time Circuit Failed: NA<br>Issue: We see about 25% packet loss from our proxy 198\.51\.100\.20 \(Frankfurt\) to target 203\.0\.113\.50 \(Hong Kong\)\.<br>Note: Intrusive testing is NOT approved\. Please schedule a test window with us in advance\.；检查显示：本端 PE ping 客户 CE 互联地址：100 发 100 收，无丢包，平均 RTT 2 ms。；检查显示：本端 PE ping 香港侧目标网段网关：100 发 100 收，无丢包，平均 RTT 3 ms。；检查显示：返单：本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。

最终历时：暂不计算（恢复未知、未核实、时间冲突或工单已撤销）。

## 七要素

| 要素 | 状态 | 结论 | 证据 |
| --- | --- | --- | --- |
| 发生时间 | 原文记载 | 2026\-09\-28 13:00:00（归一：2026\-09\-28T13:00:00\+08:00；时区按系统口径假设） | M01/f:occurred\_at |
| 结束时间 | 原文记载 | 2026\-09\-28 13:36:00（归一：2026\-09\-28T13:36:00\+08:00；时区按系统口径假设） | M01/f:recovered\_at |
| 故障现象 | 原文记载 | 客户反馈：Circuit ID: SYN\-CKT\-1009<br>Time Circuit Failed: NA<br>Issue: We see about 25% packet loss from our proxy 198\.51\.100\.20 \(Frankfurt\) to target 203\.0\.113\.50 \(Hong Kong\)\.<br>Note: Intrusive testing is NOT approved\. Please schedule a test window with us in advance\.；检查显示：本端 PE ping 客户 CE 互联地址：100 发 100 收，无丢包，平均 RTT 2 ms。；检查显示：本端 PE ping 香港侧目标网段网关：100 发 100 收，无丢包，平均 RTT 3 ms。；检查显示：返单：本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。 | M01/f:description、M02/log:3、M02/log:4、M02/log:6 |
| 故障责任方 | 未知 | 未知；见候选和未决事项。 |  |
| 故障原因 | 未知 | 未知；见候选和未决事项。 |  |
| 处理过程 | 原文记载 | 9 条处理记录，见时间线。 | M02/log:1、M02/log:2、M02/log:3、M02/log:4、M02/log:5、M02/log:6、M02/log:7、M02/log:8、M02/log:9 |
| 故障地点 | 未知 | 未知；见候选和未决事项。 |  |


### 发生时间：候选与观测


- C1 / ticket\_created / 系统记载：2026\-09\-28 13:02:41（归一：2026\-09\-28T13:02:41\+08:00；时区按系统口径假设）（M01/f:created\_at）
- C2 / fault\_start\_field / 系统记载：2026\-09\-28 13:00:00（归一：2026\-09\-28T13:00:00\+08:00；时区按系统口径假设）（M01/f:occurred\_at）
- C3 / ticket\_created / 系统记载：2026\-09\-28 13:02:41（归一：2026\-09\-28T13:02:41\+08:00；时区按系统口径假设）（M02/log:1）


### 结束时间：候选与观测


- C1 / recovery\_field / 系统记载：2026\-09\-28 13:36:00（归一：2026\-09\-28T13:36:00\+08:00；时区按系统口径假设）（M01/f:recovered\_at）
- C2 / ticket\_returned / 系统记载：2026\-09\-28 13:20:47（归一：2026\-09\-28T13:20:47\+08:00；时区按系统口径假设）（M02/log:6）


### 故障现象：候选与观测


- C1 / customer / 客户反馈：Circuit ID: SYN\-CKT\-1009<br>Time Circuit Failed: NA<br>Issue: We see about 25% packet loss from our proxy 198\.51\.100\.20 \(Frankfurt\) to target 203\.0\.113\.50 \(Hong Kong\)\.<br>Note: Intrusive testing is NOT approved\. Please schedule a test window with us in advance\.（M01/f:description）
- C2 / noc\_check / 检查显示：本端 PE ping 客户 CE 互联地址：100 发 100 收，无丢包，平均 RTT 2 ms。（M02/log:3）
- C3 / noc\_check / 检查显示：本端 PE ping 香港侧目标网段网关：100 发 100 收，无丢包，平均 RTT 3 ms。（M02/log:4）
- C4 / noc\_check / 检查显示：返单：本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。（M02/log:6）


### 故障责任方：候选与观测


- 没有可用候选。


### 故障原因：候选与观测


- C1 / investigation\_finding / 系统记载：本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。（M01/f:cause）
- C2 / investigation\_finding / 检查显示：本端 PE ping 客户 CE 互联地址：100 发 100 收，无丢包，平均 RTT 2 ms。（M02/log:3）
- C3 / investigation\_finding / 检查显示：本端 PE ping 香港侧目标网段网关：100 发 100 收，无丢包，平均 RTT 3 ms。（M02/log:4）
- C4 / investigation\_finding / 检查显示：返单：本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。（M02/log:6）
- C5 / process\_blocker / 检查显示：客户暂未提供测试资料。（M02/log:8）


### 处理过程：候选与观测


- P1 / workflow / 检查显示：根据客户邮件建单。（M02/log:1）
- P2 / workflow / 检查显示：已受理。（M02/log:2）
- P3 / check\_result / 检查显示：本端 PE ping 客户 CE 互联地址：100 发 100 收，无丢包，平均 RTT 2 ms。（M02/log:3）
- P4 / check\_result / 检查显示：本端 PE ping 香港侧目标网段网关：100 发 100 收，无丢包，平均 RTT 3 ms。（M02/log:4）
- P5 / check\_result / 检查显示：检查 PE 端口流量与错包计数：流量正常，无 CRC 错包。（M02/log:5）
- P6 / workflow / 检查显示：返单：本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。（M02/log:6）
- P7 / check\_result / 检查显示：已转告客户，请其提供故障时源/目的地址及 ping/trace 结果。（M02/log:7）
- P8 / check\_result / 检查显示：客户暂未提供测试资料。（M02/log:8）
- P9 / workflow / 检查显示：工单进入索要报告/结单签收环节。（M02/log:9）


### 故障地点：候选与观测


- C1 / test\_node / 客户反馈：Circuit ID: SYN\-CKT\-1009<br>Time Circuit Failed: NA<br>Issue: We see about 25% packet loss from our proxy 198\.51\.100\.20 \(Frankfurt\) to target 203\.0\.113\.50 \(Hong Kong\)\.<br>Note: Intrusive testing is NOT approved\. Please schedule a test window with us in advance\.（M01/f:description）
- C2 / test\_node / 系统记载：本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。（M01/f:cause）
- C3 / test\_node / 检查显示：本端 PE ping 客户 CE 互联地址：100 发 100 收，无丢包，平均 RTT 2 ms。（M02/log:3）
- C4 / test\_node / 检查显示：本端 PE ping 香港侧目标网段网关：100 发 100 收，无丢包，平均 RTT 3 ms。（M02/log:4）
- C5 / test\_node / 检查显示：返单：本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。（M02/log:6）
- C6 / test\_node / 检查显示：已转告客户，请其提供故障时源/目的地址及 ping/trace 结果。（M02/log:7）


## 关键处理时间线

- 2026\-09\-28 13:02:41（归一：2026\-09\-28T13:02:41\+08:00；时区按系统口径假设） / 流程 / 检查显示 / 系统：根据客户邮件建单。（M02/log:1）
- 2026\-09\-28 13:05:10（归一：2026\-09\-28T13:05:10\+08:00；时区按系统口径假设） / 流程 / 检查显示 / 值班员N：已受理。（M02/log:2）
- 2026\-09\-28 13:09:55（归一：2026\-09\-28T13:09:55\+08:00；时区按系统口径假设） / 检查结果 / 检查显示 / 值班员N：本端 PE ping 客户 CE 互联地址：100 发 100 收，无丢包，平均 RTT 2 ms。（M02/log:3）
- 2026\-09\-28 13:14:20（归一：2026\-09\-28T13:14:20\+08:00；时区按系统口径假设） / 检查结果 / 检查显示 / 值班员N：本端 PE ping 香港侧目标网段网关：100 发 100 收，无丢包，平均 RTT 3 ms。（M02/log:4）
- 2026\-09\-28 13:18:02（归一：2026\-09\-28T13:18:02\+08:00；时区按系统口径假设） / 检查结果 / 检查显示 / 值班员N：检查 PE 端口流量与错包计数：流量正常，无 CRC 错包。（M02/log:5）
- 2026\-09\-28 13:20:47（归一：2026\-09\-28T13:20:47\+08:00；时区按系统口径假设） / 流程 / 检查显示 / 值班员N：返单：本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。（M02/log:6）
- 2026\-09\-28 13:40:30（归一：2026\-09\-28T13:40:30\+08:00；时区按系统口径假设） / 检查结果 / 检查显示 / 客户经理P：已转告客户，请其提供故障时源/目的地址及 ping/trace 结果。（M02/log:7）
- 2026\-09\-29 10:00:12（归一：2026\-09\-29T10:00:12\+08:00；时区按系统口径假设） / 检查结果 / 检查显示 / 客户经理P：客户暂未提供测试资料。（M02/log:8）
- 2026\-09\-29 10:02:00（归一：2026\-09\-29T10:02:00\+08:00；时区按系统口径假设） / 流程 / 检查显示 / 系统：工单进入索要报告/结单签收环节。（M02/log:9）

## 恢复与验证情况

2026\-09\-28 13:36:00（归一：2026\-09\-28T13:36:00\+08:00；时区按系统口径假设）；原文记载。系统记录、告警清除、客户确认和同意结单保留各自语义。

## 未决事项与待核实清单

- info / DURATION\_BASIS\_MISMATCH：返单历时 18 分钟与系统字段差 36 分钟不同，不能混用口径。（M01/f:duration\_returned）；待核实。
- warning / TIME\_CANDIDATES\_DIFFER：时间候选有不同语义或数值；建单、告警、关单时间不能替代起障/恢复。（M01/f:created\_at、M01/f:occurred\_at、M02/log:1）；待核实。
- warning / TIME\_CANDIDATES\_DIFFER：时间候选有不同语义或数值；建单、告警、关单时间不能替代起障/恢复。（M01/f:recovered\_at、M02/log:6）；待核实。
- warning / RECOVERY\_UNVERIFIED：仅有系统恢复记载，未见客户恢复确认；同意结单不等于确认恢复。（M01/f:recovered\_at）；待核实。
- warning / CAUSE\_NOT\_DIAGNOSIS：排查结论、恢复方式和资源状态保留为候选，不能当作根因。（M01/f:cause、M02/log:3、M02/log:4、M02/log:6、M02/log:8）；待核实。
- info / RESPONSIBILITY\_NO\_BASIS：未见明确责任认定，不按供应商或处理部门补齐。（）；待核实。
- warning / RECOVERY\_SCOPE\_LIMITED：检查范围内正常不能替代业务恢复确认。（M01/f:cause、M02/log:3、M02/log:4、M02/log:5、M02/log:6）；待核实。
- warning / OBSERVATION\_SCOPE\_DIFFERS：客户感知与网管观测来源、时刻或范围不同，分别保留。（M01/f:description、M02/log:3、M02/log:4、M02/log:6）；待核实。
- info / LOCATION\_NOT\_LOCATED：未定位实际故障点，业务端点、告警位置和测试节点只作候选。（M01/f:description、M01/f:cause、M02/log:3、M02/log:4、M02/log:6、M02/log:7）；待核实。

## 服务身份与关联单

unverified：服务身份尚未经独立核实。

- reported：SYN\-CKT\-1009（M01/f:circuit\_id）

- 没有登记关联单。

## 材料完整性

| 材料 | 文件 | 状态 | 说明 |
| --- | --- | --- | --- |
| M01 | ticket\.json | 已解析 |  |
| M02 | process\_log\.json | 已解析 |  |

## 内部证据索引

### M01/f:ticket\_no · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;ticket\_no&quot;\}；a1\.ticket\_fields@1\.0。

> SYN\-S09

### M01/f:customer · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;customer&quot;\}；a1\.ticket\_fields@1\.0。

> Example Corp B（合成）

### M01/f:circuit\_id · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;circuit\_id&quot;\}；a1\.ticket\_fields@1\.0。

> SYN\-CKT\-1009

### M01/f:created\_at · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;created\_at&quot;\}；a1\.ticket\_fields@1\.0。

> 2026\-09\-28 13:02:41

### M01/f:fault\_type · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;fault\_type&quot;\}；a1\.ticket\_fields@1\.0。

> 业务性能\-丢包

### M01/f:occurred\_at · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;occurred\_at&quot;\}；a1\.ticket\_fields@1\.0。

> 2026\-09\-28 13:00:00

### M01/f:recovered\_at · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;recovered\_at&quot;\}；a1\.ticket\_fields@1\.0。

> 2026\-09\-28 13:36:00

### M01/f:duration\_returned · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;duration\_returned&quot;\}；a1\.ticket\_fields@1\.0。

> 18分钟

### M01/f:description · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;description&quot;\}；a1\.ticket\_fields@1\.0。

> Circuit ID: SYN\-CKT\-1009<br>Time Circuit Failed: NA<br>Issue: We see about 25% packet loss from our proxy 198\.51\.100\.20 \(Frankfurt\) to target 203\.0\.113\.50 \(Hong Kong\)\.<br>Note: Intrusive testing is NOT approved\. Please schedule a test window with us in advance\.<br><br>Best regards,<br>John Doe \| Network Operations \| Example Corp B<br>Tel: \+1\-555\-0100<br>This email and any attachments are confidential and intended solely for the addressee\.

### M01/f:cause · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;cause&quot;\}；a1\.ticket\_fields@1\.0。

> 本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。

### M02/log:1 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:1\}；a1\.process\_log@1\.0。

> 根据客户邮件建单。

### M02/log:2 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:2\}；a1\.process\_log@1\.0。

> 已受理。

### M02/log:3 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:3\}；a1\.process\_log@1\.0。

> 本端 PE ping 客户 CE 互联地址：100 发 100 收，无丢包，平均 RTT 2 ms。

### M02/log:4 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:4\}；a1\.process\_log@1\.0。

> 本端 PE ping 香港侧目标网段网关：100 发 100 收，无丢包，平均 RTT 3 ms。

### M02/log:5 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:5\}；a1\.process\_log@1\.0。

> 检查 PE 端口流量与错包计数：流量正常，无 CRC 错包。

### M02/log:6 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:6\}；a1\.process\_log@1\.0。

> 返单：本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。

### M02/log:7 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:7\}；a1\.process\_log@1\.0。

> 已转告客户，请其提供故障时源/目的地址及 ping/trace 结果。

### M02/log:8 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:8\}；a1\.process\_log@1\.0。

> 客户暂未提供测试资料。

### M02/log:9 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:9\}；a1\.process\_log@1\.0。

> 工单进入索要报告/结单签收环节。


## 审核记录

- 发生时间：尚未人工审核。
- 结束时间：尚未人工审核。
- 故障现象：尚未人工审核。
- 故障责任方：尚未人工审核。
- 故障原因：尚未人工审核。
- 处理过程：尚未人工审核。
- 故障地点：尚未人工审核。

本报告为草稿，不表示已批准结案。