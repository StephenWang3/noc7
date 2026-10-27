# 工单包格式（bundle format 1.0）

工单包是系统的**唯一输入格式**：合成样本、界面上传、真实工单导出脚本，最后都整理成同一种目录，再由 `noc7.bundle.load_bundle()` 校验后进入解析。JSON Schema 在 `schemas/`，由代码生成（`uv run noc7 schema export`）。设计理由见 [0003 号决策](decisions/0003-bundle-format-and-parallel-contract.md)。

## 1. 目录结构

```text
SYN-S10/
├── manifest.json        # 清单：数据分级、时间口径、每份材料的路径/类型/哈希
├── ticket.json          # 工单字段（M01，kind = ticket_fields）
├── process_log.json     # 处理过程（M02，kind = process_log）
├── emails/              # 邮件详情 HTML / EML
└── attachments/         # 图片、PDF、DOCX 等
```

`emails/`、`attachments/` 只是约定，路径以清单为准。目录里的每个文件都必须在清单里登记（`manifest.json` 本身和以 `.` 开头的文件除外）。

## 2. manifest.json

| 字段 | 说明 |
| --- | --- |
| `bundle_format_version` | 固定 `"1.0"` |
| `bundle_id` | 工单包编号。合成包必须以 `SYN-` 开头 |
| `data_class` | `synthetic` 或 `real`，决定外发闸门放不放行 |
| `source` | 来源：`kind`（synthetic / noc_export / upload）、工具、说明 |
| `captured_at` | 抓取/数据截止时间，带时区的 ISO 8601。“当前仍未恢复”这类判断以它为准，不用运行时的当前时间 |
| `default_timezone` | 源系统时间口径，如 `+08:00`。原文无时区的时间按它解析并标 `assumed`；为空表示口径未知 |
| `synthetic_notice` | 合成数据声明，合成包必填 |
| `materials[]` | 材料清单，见下 |

每份材料：

| 字段 | 说明 |
| --- | --- |
| `id` | 材料编号 `M01`、`M02`…，证据编号以它为前缀 |
| `kind` | `ticket_fields` / `process_log` / `email_html` / `email_eml` / `image` / `pdf` / `docx` / `text` / `other` |
| `path` | 相对工单包根目录的路径，不能是绝对路径，不能含 `..` |
| `sha256`、`size_bytes` | 导入时逐一核对，不符即拒绝，防止材料被替换或截断 |
| `media_type` | MIME 类型 |
| `origin.log_seq` | 出自处理过程第几条 |
| `derived`、`derived_from` | 是否衍生材料（如源系统 AI 摘要）及其来源 |
| `description` | 给人看的说明 |

## 3. ticket.json

| 字段 | 说明 |
| --- | --- |
| `ticket_ref` | 源系统工单编号（合成包与 `bundle_id` 相同） |
| `title` | 标题 |
| `ticket_family` | `business` / `key_account` / `trunk` / `device` / `other`。业务单和自动大客户/中继/设备单在源系统里是两套详情布局 |
| `category` | 源系统分类原文，如“业务性能-丢包”。分类**不是**诊断 |
| `status` | `list_status` 与 `detail_status` 分开保存，二者可能不一致（S04、S05） |
| `fields[]` | `key`、`label`（源系统显示名）、`value`（原文，不做任何改写）、`section` |
| `related_tickets[]` | 关联单：`shared_alarm`（共用告警）、`reopened_from`、`same_circuit`、`parent_child`，附状态原文 |

`fields[].key` 的推荐词表（`KNOWN_FIELD_KEYS`）。不在表里的字段也可以用，键名需符合 `^[a-z][a-z0-9_]*$`。**字段名不等于语义**：`cause` 字段里常常只是排查结论，`responsible_party` 可能只是处理部门，这些由 A1 的规则判断，导入层只保留原文。

| key | 含义 |
| --- | --- |
| `ticket_no` | 工单编号 |
| `fault_type` | 故障类型 |
| `customer` | 客户名称 |
| `circuit_id` | 电路编号 |
| `bandwidth` | 带宽 |
| `a_end` | A 端 |
| `z_end` | Z 端 |
| `created_at` | 建单时间 |
| `occurred_at` | 故障发生时间 |
| `recovered_at` | 故障恢复时间 |
| `duration_returned` | 返单历时 |
| `description` | 故障描述 |
| `cause` | 故障原因 |
| `responsible_party` | 故障责任方 |
| `handling_dept` | 处理部门 |
| `handler` | 处理人 |
| `vendor` | 供应商 |
| `region` | 国家/城市 |
| `alarm_serial` | 告警流水号 |
| `alarm_title` | 告警标题 |
| `alarm_level` | 告警级别 |
| `alarm_time` | 告警时间 |
| `alarm_cleared_at` | 告警清除时间 |
| `warning_title` | 预警标题 |
| `warning_time` | 预警时间 |
| `underlying_alarm` | 底层告警 |
| `possible_causes` | 可能原因 |
| `device_type` | 设备类型 |
| `device_name` | 设备名称 |
| `shelf_slot_port` | 槽位/端口 |
| `device_location` | 位置信息 |
| `trunk_name` | 中继名称 |

## 4. process_log.json

`{"entries": [...]}`，按 `seq` 严格递增、不重复。每条：

| 字段 | 说明 |
| --- | --- |
| `seq` | 源系统显示的序号 |
| `recorded_at` | 记录时间原文 |
| `actor`、`actor_org` | 记录人和所在部门（**不是**定责依据） |
| `action` | 源系统动作名：建单、受理、转派、处理意见、信息追加、挂起、返单、结单、撤单申请…… |
| `content` | 正文原文 |
| `entry_kind` | `human` / `system` / `email` / `ai_summary`（源系统的 AI 追单摘要，属于衍生内容） |
| `attachment_flag` | 源系统列表顶层的“有附件”标志原值，**只留档**。S10 证实它会和实际附件不一致 |
| `attachments[]`、`emails[]` | 本条实际关联的材料编号。附件必须指向附件类材料，邮件必须指向 `email_html` / `email_eml` |

## 5. 导入时的校验（`noc7 bundle validate`）

错误（拒绝导入，一次列出全部问题）：

- 清单不符合 schema：编号/路径重复，`ticket_fields` 不是恰好一份，`process_log` 多于一份，`derived_from` 指向不存在的材料，合成包没有声明；
- 材料文件不存在、大小或 sha256 不符；
- 目录里有清单未登记的文件；
- ticket.json / process_log.json 不合法；
- 处理过程引用了不存在的材料，或把非附件当附件、非邮件当邮件；
- `data_class = real` 的工单包放在源码仓库里（真实工单只能放在仓库外，默认 `~/.noc7/real/`）；
- 合成包编号不以 `SYN-` 开头，或 `ticket_ref` 与 `bundle_id` 不同。

警告（照常导入，记在 `Bundle.warnings`，后续由规则转成问题）：

- 没有处理过程；
- 某条处理过程的附件标志与实际附件数量不符（`ATTACHMENT_FLAG_MISMATCH`）；
- 某份材料既没有被处理过程引用，也没有注明出处。

## 6. 数据分级

| | `synthetic` | `real` |
| --- | --- | --- |
| 存放位置 | 仓库 `fixtures/bundles/` | 仓库外本机目录（默认 `~/.noc7/real/`），`.gitignore` 也排除了 `real/`、`.noc7/` |
| 编号 | `SYN-` 开头 | 源系统编号 |
| 可用的提供方 | rules、replay、本地模型、外部服务（如 MiniMax） | rules、replay、本地模型；外部服务需要写明批准依据 |
| 内容要求 | 全部虚构；IP 只用文档保留网段，域名只用 example 域 | 原样保存，不提交 |

## 7. 编写合成工单包

1. 手写 `ticket.json`、`process_log.json` 和邮件 HTML；图片、PDF、DOCX 用脚本生成：`uv run --group fixtures python scripts/make_fixture_assets.py`；
2. 写好清单后运行 `uv run noc7 bundle rehash fixtures/bundles/SYN-XXX` 填入哈希和大小；
3. `uv run noc7 bundle validate` 和 `uv run pytest` 通过。`tests/test_bundles.py` 会检查合成包里没有真实形态的 IP、域名和编号。
