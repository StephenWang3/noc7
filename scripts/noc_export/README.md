# 已登录 Chrome 的只读工单导出

本目录独立于 A1/A2；使用现有 `noc7.bundle.load_bundle()`，不修改共享 schema、CLI 或解析器。真实编号、查询计划、映射、正文、附件和运行日志全部保存在仓库外，默认 `~/.noc7/real/`，不得把本机数据复制到 fixtures。

## 运行

在项目根目录执行：

```sh
uv run python scripts/noc_export/exporter.py run --plan ~/.noc7/real/plan.json
uv run python scripts/noc_export/exporter.py validate
```

需要本机 Node.js/npx 和 Playwright 浏览器扩展。默认启动已经实查过的 `@playwright/mcp@0.0.83 --extension`，不启用无头浏览器、CDP 端口或新的 Chrome 个人资料。首次调用时在浏览器连接页选择已有 NOC 标签页并批准。脚本不会新开页面、点击业务按钮，也不要求导出 cookie。可用 `--mcp-command 'node /本机安装位置/cli.js --extension'` 复用本机安装（自定义命令中的文件路径用绝对路径）；MCP 子进程以私有数据目录为工作目录，自动控制台日志也留在仓库外。错误原文输出到终端，服务端 stderr 只写本机私有日志。一次连接失败就停止，避免反复要求设置浏览器。

`plan.json` 只能放在本机目录。一轮最多 20 个显式任务；先查候选，再挑选确定要导出的行。以下字段全是示意，实际查询时填入获准的时间范围，不能照搬示例编号：

```json
[
  {
    "kind": "list",
    "params": {
      "sta": 1767225600000,
      "end": 1767311999000,
      "pageNo": 1,
      "pageSize": 20,
      "title": "丢包",
      "orderStatusList": ["已撤销"]
    }
  }
]
```

查询仅覆盖指定页，不自动翻完整个工单池。结果写 `candidates.json`，其中 `rows` 是源系统返回的完整工单行。把选定的行完整复制进下一次的计划：

```json
[
  {
    "kind": "export",
    "alias": "本机样本代号",
    "match": "重新查找时核对的特征；原编号不在历史报告中，不能只凭标题认为是原单",
    "row": {"id": "源查询结果", "orderId": "源查询结果", "dataType": "esb"}
  }
]
```

上例的 `row` 仅展示必需字段；实际应完整复制，才能保留列表状态、标题与流程编号。业务单由 `dataType=esb` 识别；流程布局支持 `bpc/common`，还需行中的 `flowId`。网络故障 3.0 的 `dataType=net` 暂不发布完整包：逐条详情和附件读取尚未核实，即使列表标志为无附件也失败，部分字段/日志写入本机失败记录。其余未知布局也显式失败。

还可在本机计划中对指定行使用 `{"kind":"discover","row":{...}}`，先读取两类详情和关联邮件的附件元数据，结果写入 `discoveries/`。这只是候选预检，不是完整包；发现 PDF/EML 后再用 `export` 下载原件并验证签名。单张预检最多读取 20 封关联邮件。`{"kind":"inspect","row":{...}}` 只读取指定流程的表单和状态，写入 `inspections/`，供重新定位共享告警，不把它当工单包。

运行中可以 Ctrl+C。默认每次请求至少间隔 1500ms，另加 0–250ms 随机延迟；硬下限 1000ms，始终只有一个在途请求。`--interval-ms` 可调慢，`--max-requests` 默认 300、上限 500；20 秒单请求超时。HTTP 429/5xx、登录页、业务错误、预算耗尽、详情分页截断都立即停止，不自动重试。

## 在已有浏览器工具会话中运行

已经通过平台共享标签页时，无需再建第二个连接：

```sh
uv run python scripts/noc_export/exporter.py serve
```

该接收器只绑定 `127.0.0.1` 随机端口，随机令牌写在本机 `.bridge.json`，不提供文件浏览、代理、路径参数或跨域接口。用 `browser_evaluate` 在共享页安装 `browser.js` 中的 `createNocCollector`，保存为 `window.__noc7Collector`，然后依次调用 `start(job)`、`status()`。完成后用 `browser_run_code_unsafe` 在 **Playwright 进程**中取得 `page.evaluate(() => window.__noc7Collector.take())`，再用进程内 `fetch` 发给本机接收器；只向对话返回接收器的数量摘要，避免把正文或附件 base64 打到会话。不要从网页向外站传材料。

`serve` 接收 `POST /capture`，请求头 `X-Noc-Export` 使用本机令牌，JSON 正文为 `take()` 的结果。接收器关闭时删除 `.bridge.json`。这条路径用于已经持有平台浏览器工具的操作者；普通本机运行使用前面的 `run` 即可，不需要自己配置桥。

## 输出与完整性

- `REAL-<无业务含义的摘要>/`：通过清单校验后原子发布的工单包，`data_class=real`、`source.kind=noc_export`，所有文件有大小和 SHA-256；目录 0700，文件 0600。
- `ticket.json`：原字段；列表/详情状态分开。业务单的原、新分类和电路编号分别保留。
- `process_log.json`：页面编号过程沿用顺序；页面原本无编号的邮件/内部记录及仅出现在邮件日志中的记录放在末尾。相同记录的两个视图只保留一个过程，分别保存 `raw_log_index_to_seq` 和 `email_log_index_to_seq`，不冒充源系统原编号。邮件 ID 同时支持数组、分隔字符串、`emailId` 和 `emailIds`，正文和 EML 使用同一份过程关联。
- `details/*.txt`：逐条详情表单可见字段，原始 JSON 同时在 `source/capture.json`。不依赖 `hasAttachments` 过滤详情。追单和派单分别完整分页，每页最多 50、最多 10 页；超过上限即失败。
- `emails/*.html`：完整正文及导出整理的邮件头；纯文本正文经 HTML 转义后也作为可关联的 `email_html` 材料保存；未经改写的源字段也保存在原始响应。附件里的 EML 保留原始字节，按文件签名与邮件头识别，不把 HTML 邮件改名成 EML。
- `attachments/`：附件原始字节。文件名使用本机安全序号，原名留在清单和原始响应，不允许附件名影响路径。PDF/PNG/JPEG/DOCX/EML 经过基本签名检查，其他格式保留为 `other`，供后续解析器显式处理。
- `source/capture.json`：本机原始响应存档；附件二进制只在附件材料中保存。授权参数、cookie、token 不落盘，不保留页面初始化脚本。
- `index.json`：真实编号、样本代号及重新匹配的依据，只在本机保存。`candidates.json` 为最后一次有限查询结果。
- `last-failure.json` 与 `.partial-*`：失败和不完整材料，仅供本机排错；不会列入 `validate` 的有效包。

附件归属仅按处理人＋记录时间精确且唯一匹配；不使用页面的十秒容差。匹配不唯一时附件仍保存、标记来源详情索引，归属保持未知，不能挂到“最后一条日志”。真实数据不会交给外部 AI/OCR，导出端没有模型调用。源 HTML 只作为文件存储，不执行脚本或加载图片链接。

流程布局已核实表单、创建日志和追加日志的读取；流程附件控件出现非空数据时停止，等待核实其存储规则，不发出遗漏附件的完整包。网络故障 3.0 只核实了字段和过程日志，尚不能排除逐条详情中藏有附件，因此采集和打包两端均拒绝发布，不能以顶层空标志放行。导出能保留 NOC 已记录的内容，不能证明源系统未隐藏资料，也不能把“未找到 PDF/EML”说成系统没有这些文件。

发布身份包含 `PACKAGER_VERSION`（当前为 `3`）。重放时先生成并校验完整输出，再比较既有清单；任何内容差异都会报错，不能静默返回旧包。升级打包逻辑要提升版本，让修复后的输出使用新身份。本次已从本机存档离线重打 15 份，旧版本及 1 份未核实网络单保留在 `.superseded/`，不再作为当前有效样本。

## 验证

```sh
uv run pytest -q tests/noc_export
node tests/noc_export/test_browser.cjs
uv run python scripts/noc_export/exporter.py validate
```

离线测试全部使用虚构内容：验证仓库/符号链接目录拒绝、附件名路径穿越、假 PDF/EML、哈希与引用、精确归属歧义、无附件标志仍下载、只读白名单、登录页、分页截断和请求预算。不会运行真实网络测试。

## 已有人工结论与评估

`references` 是独立只读任务：

```json
[{"kind":"references","row":{"id":"源行编号","orderId":"源流程编号","dataType":"esb"}}]
```

完整行来自限定查询的结果。任务只调用详情 GET 与 `esbProcess/faultReport/list` GET；静态页面服务的 `list()` 已核实返回保存记录及 `reportJson`。生成、保存、报告下载、上传接口不在白名单，报告按钮本身会生成，不能点击。返回值单独留在 `references/`，不进入工单材料或提取输入，打包身份没有改变。`human_verified=false` 表示保存记录并不能证明经过人工确认；报告来源资格仍须核对作者、审核依据和明确最终结论。

评估采用独立命令，不改变原始包、共享 schema 或现有提取器：

```sh
uv run python scripts/noc_export/exporter.py --root ~/.noc7/real-eval/captures run \
  --plan ~/.noc7/real-eval/collect.json
uv run python -m noc7.evaluation prepare \
  --selection ~/.noc7/real-eval/selection.json --out ~/.noc7/real-eval/dataset
uv run python -m noc7.evaluation run \
  --dataset ~/.noc7/real-eval/dataset --out ~/.noc7/real-eval/baseline
uv run python -m noc7.evaluation score \
  --dataset ~/.noc7/real-eval/dataset --results ~/.noc7/real-eval/baseline \
  --out ~/.noc7/real-eval/scored
```

输出必须是全新仓库外目录，不能与输入互相包含。已有共享工具会话使用 `serve` 桥接，无需再启动第二个浏览器连接；真实响应、浏览器日志与计划同样留在仓库外。

### 标注文件

`selection.json` 的顶层是 `cases` 数组（最多二十例）及 `notes`。每例包含：

- `alias`：如 `E01`；`bundle`：原工单包的绝对路径。
- `sources`：来源编号 `id`，类型 `kind`（`formal_report`、`closure_note`、`final_email`），原件绝对路径 `path`、格式 `format`、`sha256`、作者 `author`、原记录时间 `recorded_at`、审核状态 `audit`、明确人工结论依据 `human_basis`。`audited` 必须提供 `reviewer`、`reviewed_at`、`audit_quote` 并在原件核验引文。审核人空白使用 `unaudited`，不能只看审核日期。工单内结论还填 `anchor`（原 `material_id` 与 `log_seq` 等）；转录文件必须与锚点原文吻合。
- `facts`：稀疏标注，只列参考真正提及的要素。填 `element`、`source_id`、精确 `quote`、可选解析块 `block_id`（如 DOCX 的 `M99/tbl:0:1:1`）。文本用 `key_points: [{"any_of":["原文写法","事先确定的同义词"]}]`；时间用 `expected_time: {"iso":"带偏移的时间","tolerance_minutes":0}`、`time_kind` 和 `time_precision`（`second`／`minute`）。时间引文必须能解析并核验值，申报、关单和起障不能混用。
- 每个事实的 `support` 列出截止前独立依据：`anchor` 加精确 `quote`；时间支持还须注明独立核对的 `time_kind`。可支持性不调用被测提取器判断。准备阶段重新定位和核对，不接受手填的“已有支持”布尔值。已被隔离的依据不会计入；一条事实的全部要点都要在保留依据的引文中得到支持。模型结果不参与生成参考或同义词。
- `allowed_statuses` 约束允许的结论状态，`value_kind` 约束原因／责任／地点语义。供应商声称的原因使用 `documented` 和 `root_cause_claimed`，不能因为正式报告转述就升级为确诊。`contradicts` 只填事先明确的互斥事实；`conflict` 标记无法裁定的参考冲突。
- `field_proofs` 默认空。只有字段值能与保留的截止前日志逐字核对时，才能填 `key` 和 `support`；最终字段没有历史版本时不直接交给提取器。`excluded_materials` 指定人工核对后必须隔离的材料编号。
- `independent_emails` 默认空。仅对预先审查过、独立于最终报告的截止前原始上游邮件，登记 `log_seq`、`material_id`、当前正文的逐字 `quote`（至少十二字符）与来源审查说明 `provenance`。先核对源响应中的邮件 ID、发送方、时间及导出正文；准备阶段还会验证截止、邮件类型、唯一原始挂接和正文互证。这不是业务审核或责任认定。参考锚点、最终报告、衍生或不完整材料不能据此放行；AI 摘要对同邮件的引用不增加独立来源。详见 [补充决策](../../docs/decisions/preclosure-email-and-fact-recall.md)。

正式报告不必假装填满七要素；未提及责任方就不标注责任方。转录不是业务复核，标注者不能替 NOC 补写诊断。

### 隔离与结果

`dataset/inputs/E01/` 是提取器唯一读取的目录，只有重新登记哈希的截止前白名单材料。截止取销障、结单签收、回访结单、本地关单等结案动作里最早的一条时间，该条及不早于它的日志不进入输入；缺失时间或详情状态不是已结单则排除该例。参考原件、参考锚点、长引文副本、故障报告标记、AI 摘要、源响应留档、截止后材料及无法核实归属／完整检查的附件不进入输入。邮件附件须唯一关联一条保留日志；`origin.log_seq` 单独存在不构成证明。标题、状态、真实工单号、分类与关联单也不作为输入元数据。

`references.json` 保存参考原文块、稀疏事实、输入支持、逐项排除原因、原包及输入哈希；`selection.json` 保存标注，`freeze.json` 绑定参考文件。它们与输入并列，不是输入包的一部分。准备完成后不要改写标注；改动需创建新数据集。没有数字签名，冻结哈希用于检测意外改动，不能证明人为篡改从未发生。

独立且已核验的截止前上游邮件可以与结案转录表达相同事实，按 `independent_preclosure_email` 留下明确决定；没有该核验的参考同文继续隔离。输入支持须同步登记实际保留邮件和日志的锚点，不能因为旧 `support=[]` 就断言原文没有进入模型。同事件的邮件与转录不增加独立佐证，修订口径须新建冻结集，不直接与旧分数比较。

`baseline/E01/analysis.json` 是规则基线。其他模型沿用相同隔离包和解析器，输出到同样的目录结构即可用 `score` 比较；必须绑定该包清单及解析证据快照，不能导入之前对完整结案包生成的结果。

`scored/summary.json` 只含枚举和计数；`details.json`、`report.md` 有真实原文和结果，只在本机打开。评分单位为“样本中的一条来源事实”，同一事实的不同来源分别统计，不把它们当作独立故障数量：

- 一致、遗漏、明确冲突、待判定分别计数；只检查结论值，不把候选命中当成功。普通文本未命中、时区／语义不足或局部否定不武断算错。
- 时间按语义、时区及冻结精度比较；处理过程的冻结动作要点须保持顺序；有来源声称却升级为确诊也记冲突。
- 一致率＝一致／（一致＋遗漏＋明确冲突）；可判定覆盖率＝（一致＋遗漏＋明确冲突）／（一致＋遗漏＋明确冲突＋待判定）。两个比例同时呈现。
- 未确认截止前输入支持、参考来源冲突另列，不进入上述分母；分母为零时为 `null`，不写零准确率或百分百正确。未标注要素没有评分事实。

无可用样本、无可判定事实、输入不匹配或提取／评分失败返回非零。单例排除原因见 `dataset/references.json`，运行失败明细见本机对应 `failure.json`；终端只输出计数，不回显原文或异常。真实批次和脱敏汇总见 [人工参考评估说明](../../docs/HUMAN_REFERENCE_EVALUATION.md)。

### 按责任方／地点定向扩样

先对新抓取的 `main` 独立副本执行 `uv run pytest -q`，通过后才开始采集。不切换会话分支，也不在共享只读仓库缓存中安装依赖或运行测试。

本轮采用人工结论优先：最近三个月创建且已结案的业务单，按创建时间从近到远检查最多 200 条去重候选，排除已有评估工单，最多新增 20 张。责任方和地点各争取覆盖至少 10 张有独立输入支持的工单；达到候选上限后按实际数量结束。单次计划仍最多 20 项，列表页和任务计划均在本机留档；核对分页顺序、跨页重复和返回时间范围，不能把源系统的总条数当成检查数。

先用 `references` 查询已保存报告，再核对明确人工结案说明，最后追溯原始邮件和 RFO。现有 `references` 仅保存报告记录；结案日志可从已导出的 `source/capture.json` 核对。本轮本机筛查副本在该任务内额外读取已在白名单的 `/esbProcess/log`，并保留同次详情和日志；仍经过 `request()` 的限速、预算及失败停止，不使用页面业务方法。该预检不是完整包，选中后必须继续完整导出和校验。不要因报告列表为空就跳过人工结案说明，也不要把“等待 RFO”算成已有报告。

人工来源、审核状态与截止前输入支持分别核对。客户侧归因仅按声称记载，供应商名称、分类编码、告警位置或业务端点不能直接成为答案。参考要点、允许状态及同义词须在看提取结果前冻结；邮件例外按上节逐事实审定，不能给整封邮件放行。先查看 `references.json` 的实际支持和排除记录，不能把选择文件中填写的支持等同于隔离后仍有效。

`prepare` 纳入一例不等于该例所有事实均可评分。先保存完整来源预审，再按实际保留的支持建立新的正式选择文件和数据集，未确认支持的参考另列。核对完整断言和定位关系：邮件提到客户设备不证明已归因于客户，站点名相同也不能把距站点一定距离的故障改成站点处故障。逐字引文的 HTML、换行差异须与实际解析片段核对，不能通过截短限定语取得放行。来源与支持在规则及模型运行前固定，之后不改同义词或分母。

以下 `$batch` 为 `~/.noc7/` 下新私有目录；已完成采集和标注后运行，所有输出目录必须尚不存在：

```sh
uv run python -m noc7.evaluation prepare \
  --selection "$batch/selection.json" --out "$batch/dataset"
uv run python -m noc7.evaluation run \
  --dataset "$batch/dataset" --out "$batch/rules"
uv run noc7 analyze "$batch/dataset/inputs" \
  --provider llm --model-config config/models/deepseek.json \
  --model-audit-dir "$batch/model-audit" --save-replay \
  --out "$batch/deepseek"
uv run python -m noc7.evaluation score \
  --dataset "$batch/dataset" --results "$batch/rules" \
  --out "$batch/scored-rules"
uv run python -m noc7.evaluation score \
  --dataset "$batch/dataset" --results "$batch/deepseek" \
  --out "$batch/scored-deepseek"
replay_inputs=()
for input_dir in "$batch"/dataset/inputs/E*; do
  case_alias=${input_dir##*/}
  if [[ -f "$batch/deepseek/$case_alias/analysis.json" && \
        -f "$batch/deepseek/$case_alias/replay.json" ]]; then
    replay_inputs+=("$input_dir")
  fi
done
if (( ${#replay_inputs[@]} > 0 )); then
  uv run noc7 analyze "${replay_inputs[@]}" \
    --provider replay --replay "$batch/deepseek" --out "$batch/replayed"
fi
uv run python -m noc7.evaluation score \
  --dataset "$batch/dataset" --results "$batch/replayed" \
  --out "$batch/scored-replayed"
```

无合格输入时不发模型请求，保留排除台账；零分母报告为不可计算。两侧结果由评分器核验相同输入清单及解析证据快照，不能用完整包旧结果代入。模型失败和拒绝单独报告，不删去后计算成功率；回放在新目录核对要素结果与评分。来源事实数、覆盖工单数和独立事件数须区分，不将相同故障的多张工单当成独立故障样本。真实明细、响应、配置副本和浏览器日志仅留在本机，脱敏结果见 [扩样报告](../../docs/RESPONSIBILITY_LOCATION_SAMPLE_EXPANSION.md)。

模型内容拒绝后不因退出非零就重跑整批。先核对 `analysis-rejected.json` 与模型诊断，保留原始运行目标；回放仅传入已有合格分析和回放快照的输入目录，评分仍传完整 `dataset`。因此原运行有失败时，回放评分也应保留失败，非零返回不能自动触发新的付费请求。本轮正式集、结果和最终断点见扩样报告；本机旧筛查及恢复计划作为历史保留，不再执行。
