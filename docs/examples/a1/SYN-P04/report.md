# SYN\-P04 · 结案草稿

> 合成演示数据，不代表真实工单或真实模型质量。

报告版本：1\.0；待人工审核。生成：2026\-10\-27T13:35:09\.037828\+00:00；数据截止：2026\-10\-11T11:30:00\+08:00。

分析来源：rules；规则 1\.1；输入快照：5eabd404b4c678cdb1be0876c3e4db396a5f06514cd0b86b696303eed9d500b1。

## 事件概述

客户反馈：客户报专线 SYN\-CKT\-1024 业务中断。；检查显示：查告警：15:42 起 SYN\-CKT\-1024 所在光缆段 R\_LOS；OTDR 测试显示断点距 A 端局站约 3\.2 km。；检查显示：19:08 告警清除，业务恢复；19:15 客户电话确认业务正常。

最终历时：206 分钟（有确认依据的起止时间差）。

## 七要素

| 要素 | 状态 | 结论 | 证据 |
| --- | --- | --- | --- |
| 发生时间 | 原文记载 | 2026\-10\-10 15:42:00（归一：2026\-10\-10T15:42:00\+08:00；时区按系统口径假设） | M01/f:occurred\_at |
| 结束时间 | 有确认依据 | 2026\-10\-10 19:08:00（归一：2026\-10\-10T19:08:00\+08:00；时区按系统口径假设） | M01/f:recovered\_at、M02/log:7 |
| 故障现象 | 原文记载 | 客户反馈：客户报专线 SYN\-CKT\-1024 业务中断。；检查显示：查告警：15:42 起 SYN\-CKT\-1024 所在光缆段 R\_LOS；OTDR 测试显示断点距 A 端局站约 3\.2 km。；检查显示：19:08 告警清除，业务恢复；19:15 客户电话确认业务正常。 | M01/f:description、M02/log:3、M02/log:7 |
| 故障责任方 | 有确认依据 | 责任认定：本次中断由第三方施工单位示例建设公司（合成）未按管线交底施工造成，责任方为该施工单位，已启动索赔。 | M02/log:10 |
| 故障原因 | 有确认依据 | 现场确认：示例路与示例大道交叉口人井 SYN\-MH\-0102 东侧约 15 m 处，市政道路施工挖断 24 芯光缆，施工时间约 15:40。开始抢修。 | M02/log:5 |
| 处理过程 | 原文记载 | 11 条处理记录，见时间线。 | M02/log:1、M02/log:2、M02/log:3、M02/log:4、M02/log:5、M02/log:6、M02/log:7、M02/log:8、M02/log:9、M02/log:10、M02/log:11 |
| 故障地点 | 原文记载 | 现场确认：示例路与示例大道交叉口人井 SYN\-MH\-0102 东侧约 15 m 处，市政道路施工挖断 24 芯光缆，施工时间约 15:40。开始抢修。 | M02/log:5 |


### 发生时间：候选与观测


- C1 / ticket\_created / 系统记载：2026\-10\-10 15:50:08（归一：2026\-10\-10T15:50:08\+08:00；时区按系统口径假设）（M01/f:created\_at）
- C2 / fault\_start\_field / 系统记载：2026\-10\-10 15:42:00（归一：2026\-10\-10T15:42:00\+08:00；时区按系统口径假设）（M01/f:occurred\_at）
- C3 / ticket\_created / 系统记载：2026\-10\-10 15:50:08（归一：2026\-10\-10T15:50:08\+08:00；时区按系统口径假设）（M02/log:1）
- C4 / alarm\_raised / 检查显示：15:42（归一：2026\-10\-10T15:42:00\+08:00；时区按系统口径假设）（M02/log:3、M01/f:occurred\_at）；原文只有时刻；日期与同单对应起止字段对齐，保留两处依据。


### 结束时间：候选与观测


- C1 / recovery\_field / 系统记载：2026\-10\-10 19:08:00（归一：2026\-10\-10T19:08:00\+08:00；时区按系统口径假设）（M01/f:recovered\_at）
- C2 / repair\_completed / 检查显示：18:55（归一：2026\-10\-10T18:55:00\+08:00；时区按系统口径假设）（M02/log:6）；仅有时刻，日期按同条记录/邮件头补齐；跨日需复核。
- C3 / alarm\_cleared / 检查显示：19:08（归一：2026\-10\-10T19:08:00\+08:00；时区按系统口径假设）（M02/log:7）；仅有时刻，日期按同条记录/邮件头补齐；跨日需复核。
- C4 / customer\_confirmed\_recovery / 检查显示：19:15（归一：2026\-10\-10T19:15:00\+08:00；时区按系统口径假设）（M02/log:7）；客户确认时刻，仅表示此时已正常，不替代实际恢复时刻。
- C5 / ticket\_returned / 系统记载：2026\-10\-10 19:18:00（归一：2026\-10\-10T19:18:00\+08:00；时区按系统口径假设）（M02/log:8）
- C6 / ticket\_closed / 系统记载：2026\-10\-11 11:00:00（归一：2026\-10\-11T11:00:00\+08:00；时区按系统口径假设）（M02/log:11）


### 故障现象：候选与观测


- C1 / customer / 客户反馈：客户报专线 SYN\-CKT\-1024 业务中断。（M01/f:description）
- C2 / noc\_check / 检查显示：查告警：15:42 起 SYN\-CKT\-1024 所在光缆段 R\_LOS；OTDR 测试显示断点距 A 端局站约 3\.2 km。（M02/log:3）
- C3 / noc\_check / 检查显示：19:08 告警清除，业务恢复；19:15 客户电话确认业务正常。（M02/log:7）


### 故障责任方：候选与观测


- C1 / claimed / 系统记载：第三方施工单位：示例建设公司（合成）（M01/f:responsible\_party）
- C2 / formal\_determination / 检查显示：责任认定：本次中断由第三方施工单位示例建设公司（合成）未按管线交底施工造成，责任方为该施工单位，已启动索赔。（M02/log:10）


### 故障原因：候选与观测


- C1 / root\_cause\_claimed / 系统记载：市政道路施工挖断 24 芯光缆，已熔接恢复。（M01/f:cause）
- C2 / root\_cause\_confirmed / 现场工程师称：现场确认：示例路与示例大道交叉口人井 SYN\-MH\-0102 东侧约 15 m 处，市政道路施工挖断 24 芯光缆，施工时间约 15:40。开始抢修。（M02/log:5）


### 处理过程：候选与观测


- P1 / workflow / 客户反馈：客户来电报障建单。（M02/log:1）
- P2 / workflow / 检查显示：已受理。（M02/log:2）
- P3 / check\_result / 检查显示：查告警：15:42 起 SYN\-CKT\-1024 所在光缆段 R\_LOS；OTDR 测试显示断点距 A 端局站约 3\.2 km。（M02/log:3）
- P4 / technical\_action / 检查显示：派线路维护部现场抢修。（M02/log:4）
- P5 / technical\_action / 现场工程师称：现场确认：示例路与示例大道交叉口人井 SYN\-MH\-0102 东侧约 15 m 处，市政道路施工挖断 24 芯光缆，施工时间约 15:40。开始抢修。（M02/log:5）
- P6 / technical\_action / 检查显示：18:55 熔接完成。（M02/log:6）
- P7 / communication / 检查显示：19:08 告警清除，业务恢复；19:15 客户电话确认业务正常。（M02/log:7）
- P8 / workflow / 检查显示：返单。（M02/log:8）
- P9 / technical\_action / 检查显示：上传现场抢修报告（PDF）。（M02/log:9）
- P10 / communication / 检查显示：责任认定：本次中断由第三方施工单位示例建设公司（合成）未按管线交底施工造成，责任方为该施工单位，已启动索赔。（M02/log:10）
- P11 / workflow / 检查显示：结单。（M02/log:11）


### 故障地点：候选与观测


- C1 / located\_fault\_point / 现场工程师称：现场确认：示例路与示例大道交叉口人井 SYN\-MH\-0102 东侧约 15 m 处，市政道路施工挖断 24 芯光缆，施工时间约 15:40。开始抢修。（M02/log:5）


## 关键处理时间线

- 2026\-10\-10 15:50:08（归一：2026\-10\-10T15:50:08\+08:00；时区按系统口径假设） / 流程 / 客户反馈 / 系统：客户来电报障建单。（M02/log:1）
- 2026\-10\-10 15:52:30（归一：2026\-10\-10T15:52:30\+08:00；时区按系统口径假设） / 流程 / 检查显示 / 值班员AF：已受理。（M02/log:2）
- 2026\-10\-10 15:58:14（归一：2026\-10\-10T15:58:14\+08:00；时区按系统口径假设） / 检查结果 / 检查显示 / 值班员AF：查告警：15:42 起 SYN\-CKT\-1024 所在光缆段 R\_LOS；OTDR 测试显示断点距 A 端局站约 3\.2 km。（M02/log:3）
- 2026\-10\-10 16:05:40（归一：2026\-10\-10T16:05:40\+08:00；时区按系统口径假设） / 排障动作 / 检查显示 / 值班员AF：派线路维护部现场抢修。（M02/log:4）
- 2026\-10\-10 16:48:22（归一：2026\-10\-10T16:48:22\+08:00；时区按系统口径假设） / 排障动作 / 现场工程师称 / 线路工程师AG：现场确认：示例路与示例大道交叉口人井 SYN\-MH\-0102 东侧约 15 m 处，市政道路施工挖断 24 芯光缆，施工时间约 15:40。开始抢修。（M02/log:5）
- 2026\-10\-10 18:57:05（归一：2026\-10\-10T18:57:05\+08:00；时区按系统口径假设） / 排障动作 / 检查显示 / 线路工程师AG：18:55 熔接完成。（M02/log:6）
- 2026\-10\-10 19:16:31（归一：2026\-10\-10T19:16:31\+08:00；时区按系统口径假设） / 沟通 / 检查显示 / 值班员AF：19:08 告警清除，业务恢复；19:15 客户电话确认业务正常。（M02/log:7）
- 2026\-10\-10 19:18:00（归一：2026\-10\-10T19:18:00\+08:00；时区按系统口径假设） / 流程 / 检查显示 / 值班员AF：返单。（M02/log:8）
- 2026\-10\-10 20:30:12（归一：2026\-10\-10T20:30:12\+08:00；时区按系统口径假设） / 排障动作 / 检查显示 / 线路工程师AG：上传现场抢修报告（PDF）。（M02/log:9）
- 2026\-10\-11 10:20:45（归一：2026\-10\-11T10:20:45\+08:00；时区按系统口径假设） / 沟通 / 检查显示 / 线路维护部主管AH：责任认定：本次中断由第三方施工单位示例建设公司（合成）未按管线交底施工造成，责任方为该施工单位，已启动索赔。（M02/log:10）
- 2026\-10\-11 11:00:00（归一：2026\-10\-11T11:00:00\+08:00；时区按系统口径假设） / 流程 / 检查显示 / 值班员AI：结单。（M02/log:11）

## 恢复与验证情况

2026\-10\-10 19:08:00（归一：2026\-10\-10T19:08:00\+08:00；时区按系统口径假设）；有确认依据。系统记录、告警清除、客户确认和同意结单保留各自语义。

## 未决事项与待核实清单

- warning / MATERIAL\_UNSUPPORTED：材料 M03（pdf，attachments/M03\-repair\-report\.pdf）暂无可用解析器，相关要素可能不完整（）；待核实。
- warning / TIME\_CANDIDATES\_DIFFER：时间候选有不同语义或数值；建单、告警、关单时间不能替代起障/恢复。（M01/f:created\_at、M01/f:occurred\_at、M02/log:1、M02/log:3）；待核实。
- warning / TIME\_CANDIDATES\_DIFFER：时间候选有不同语义或数值；建单、告警、关单时间不能替代起障/恢复。（M01/f:recovered\_at、M02/log:6、M02/log:7、M02/log:8、M02/log:11）；待核实。

## 服务身份与关联单

unverified：服务身份尚未经独立核实。

- reported：SYN\-CKT\-1024（M01/f:circuit\_id）

- 没有登记关联单。

## 材料完整性

| 材料 | 文件 | 状态 | 说明 |
| --- | --- | --- | --- |
| M01 | ticket\.json | 已解析 |  |
| M02 | process\_log\.json | 已解析 |  |
| M03 | attachments/M03\-repair\-report\.pdf | 不支持/待实现 |  |

## 内部证据索引

### M01/f:ticket\_no · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;ticket\_no&quot;\}；a1\.ticket\_fields@1\.0。

> SYN\-P04

### M01/f:customer · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;customer&quot;\}；a1\.ticket\_fields@1\.0。

> 示例客户壬（合成）

### M01/f:circuit\_id · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;circuit\_id&quot;\}；a1\.ticket\_fields@1\.0。

> SYN\-CKT\-1024

### M01/f:created\_at · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;created\_at&quot;\}；a1\.ticket\_fields@1\.0。

> 2026\-10\-10 15:50:08

### M01/f:fault\_type · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;fault\_type&quot;\}；a1\.ticket\_fields@1\.0。

> 业务中断

### M01/f:occurred\_at · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;occurred\_at&quot;\}；a1\.ticket\_fields@1\.0。

> 2026\-10\-10 15:42:00

### M01/f:recovered\_at · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;recovered\_at&quot;\}；a1\.ticket\_fields@1\.0。

> 2026\-10\-10 19:08:00

### M01/f:duration\_returned · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;duration\_returned&quot;\}；a1\.ticket\_fields@1\.0。

> 206分钟

### M01/f:description · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;description&quot;\}；a1\.ticket\_fields@1\.0。

> 客户报专线 SYN\-CKT\-1024 业务中断。

### M01/f:cause · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;cause&quot;\}；a1\.ticket\_fields@1\.0。

> 市政道路施工挖断 24 芯光缆，已熔接恢复。

### M01/f:responsible\_party · 原文

定位：\{&quot;type&quot;:&quot;field&quot;,&quot;field\_key&quot;:&quot;responsible\_party&quot;\}；a1\.ticket\_fields@1\.0。

> 第三方施工单位：示例建设公司（合成）

### M02/log:1 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:1\}；a1\.process\_log@1\.0。

> 客户来电报障建单。

### M02/log:2 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:2\}；a1\.process\_log@1\.0。

> 已受理。

### M02/log:3 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:3\}；a1\.process\_log@1\.0。

> 查告警：15:42 起 SYN\-CKT\-1024 所在光缆段 R\_LOS；OTDR 测试显示断点距 A 端局站约 3\.2 km。

### M02/log:4 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:4\}；a1\.process\_log@1\.0。

> 派线路维护部现场抢修。

### M02/log:5 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:5\}；a1\.process\_log@1\.0。

> 现场确认：示例路与示例大道交叉口人井 SYN\-MH\-0102 东侧约 15 m 处，市政道路施工挖断 24 芯光缆，施工时间约 15:40。开始抢修。

### M02/log:6 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:6\}；a1\.process\_log@1\.0。

> 18:55 熔接完成。

### M02/log:7 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:7\}；a1\.process\_log@1\.0。

> 19:08 告警清除，业务恢复；19:15 客户电话确认业务正常。

### M02/log:8 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:8\}；a1\.process\_log@1\.0。

> 返单。

### M02/log:9 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:9\}；a1\.process\_log@1\.0。

> 上传现场抢修报告（PDF）。

### M02/log:10 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:10\}；a1\.process\_log@1\.0。

> 责任认定：本次中断由第三方施工单位示例建设公司（合成）未按管线交底施工造成，责任方为该施工单位，已启动索赔。

### M02/log:11 · 原文

定位：\{&quot;type&quot;:&quot;log\_entry&quot;,&quot;seq&quot;:11\}；a1\.process\_log@1\.0。

> 结单。


## 审核记录

- 发生时间：尚未人工审核。
- 结束时间：尚未人工审核。
- 故障现象：尚未人工审核。
- 故障责任方：尚未人工审核。
- 故障原因：尚未人工审核。
- 处理过程：尚未人工审核。
- 故障地点：尚未人工审核。

本报告为草稿，不表示已批准结案。