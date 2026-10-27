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

上例的 `row` 仅展示必需字段；实际应完整复制，才能保留列表状态、标题与流程编号。业务单由 `dataType=esb` 识别；流程布局支持 `bpc/common`，还需行中的 `flowId`。网络故障 3.0 的 `dataType=net` 支持无附件、无关联邮件和无反馈详情的字段及处理过程；其余布局显式失败。

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
- `process_log.json`：页面编号过程沿用顺序；页面原本无编号的邮件/内部记录放在编号过程之后，不冒充源系统原编号。对应关系在 `source/log-map.json`。
- `details/*.txt`：逐条详情表单可见字段，原始 JSON 同时在 `source/capture.json`。不依赖 `hasAttachments` 过滤详情。追单和派单分别完整分页，每页最多 50、最多 10 页；超过上限即失败。
- `emails/*.html`：完整正文及导出整理的邮件头；未经改写的源字段也保存在原始响应。附件里的 EML 保留原始字节，按文件签名与邮件头识别，不把 HTML 邮件改名成 EML。
- `attachments/`：附件原始字节。文件名使用本机安全序号，原名留在清单和原始响应，不允许附件名影响路径。PDF/PNG/JPEG/DOCX/EML 经过基本签名检查，其他格式保留为 `other`，供后续解析器显式处理。
- `source/capture.json`：本机原始响应存档；附件二进制只在附件材料中保存。授权参数、cookie、token 不落盘，不保留页面初始化脚本。
- `index.json`：真实编号、样本代号及重新匹配的依据，只在本机保存。`candidates.json` 为最后一次有限查询结果。
- `last-failure.json` 与 `.partial-*`：失败和不完整材料，仅供本机排错；不会列入 `validate` 的有效包。

附件归属仅按处理人＋记录时间精确且唯一匹配；不使用页面的十秒容差。匹配不唯一时附件仍保存、标记来源详情索引，归属保持未知，不能挂到“最后一条日志”。真实数据不会交给外部 AI/OCR，导出端没有模型调用。源 HTML 只作为文件存储，不执行脚本或加载图片链接。

流程布局已核实表单、创建日志和追加日志的读取；流程附件控件出现非空数据时停止，等待核实其存储规则，不发出遗漏附件的完整包。网络故障 3.0 已核实字段和过程日志读取；若存在附件、关联邮件或反馈详情，当前版本停止并要求补核这些读取方式。导出能保留 NOC 已记录的内容，不能证明源系统未隐藏资料，也不能把“未找到 PDF/EML”说成系统没有这些文件。

## 验证

```sh
uv run pytest -q tests/noc_export
node tests/noc_export/test_browser.cjs
uv run python scripts/noc_export/exporter.py validate
```

离线测试全部使用虚构内容：验证仓库/符号链接目录拒绝、附件名路径穿越、假 PDF/EML、哈希与引用、精确归属歧义、无附件标志仍下载、只读白名单、登录页、分页截断和请求预算。不会运行真实网络测试。
