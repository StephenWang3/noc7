/* 演示页面设计稿：三个画面（选择工单 → 七要素与原文出处 → 公司报告）。
   纯静态、无依赖。所有数据都经过 TicketSource 取得，这是和 NOC 工作台融合的接缝：
   本稿用 demo-data.js 实现，真实前端换成 fetch('/api/…') 即可，画面代码不用动。 */
(function () {
  "use strict";
  const DEMO = window.NOC7_DEMO;

  // ───────────────────────── 融合接口（TicketSource） ─────────────────────────
  // list()               → [{ticket_ref,title,list_status,category,…}]
  // get(ref)             → {ticket, analysis(=AnalysisResult), companyReport, downloads:{docx,html}} | null
  // 真实实现：GET /api/tickets、GET /api/tickets/{ref}/analysis、GET /api/tickets/{ref}/company-report.(docx|html)
  const LocalSource = {
    label: "本地工单包",
    async list() { return DEMO.tickets.map((t) => t.ticket); },
    async get(ref) {
      const t = DEMO.tickets.find((x) => x.ticket.ticket_ref === ref);
      return t ? { ticket: t.ticket, analysis: t.analysis, companyReport: t.company_report, downloads: t.downloads } : null;
    },
  };
  const source = LocalSource;

  // ───────────────────────── 词表：把内部代码翻成评委看得懂的话 ─────────────────────────
  const ELEMENTS = Object.keys(DEMO.element_labels);
  const LABEL = DEMO.element_labels;
  const HELP = {
    start_time: "故障从什么时候开始影响客户",
    end_time: "业务什么时候真正恢复",
    phenomenon: "客户和监控看到了什么异常",
    responsible_party: "谁对这次故障负责（需要有人正式认定）",
    cause: "故障为什么发生（根因，不是排查过程）",
    handling_process: "运维人员做了哪些处理，按时间排列",
    location: "故障发生在哪个具体位置（不是业务两端）",
  };
  const STATUS = {
    confirmed: { label: "已确认", icon: "✓", plain: "有客户确认、现场报告或正式定责等明确依据。" },
    documented: { label: "有明确记录", icon: "●", plain: "工单原文明确写了，系统照录；还没有第二个依据印证。" },
    unknown: { label: "未知", icon: "○", plain: "材料不足，系统宁可留空，也不猜。" },
    conflicted: { label: "矛盾", icon: "≠", plain: "材料之间互相打架，系统把各方说法并列给你，不替你选边。" },
  };
  const ATTR = { customer: "客户反馈", vendor: "供应商称", noc_check: "检查显示", field_engineer: "现场工程师称", system_field: "系统记载", alarm_system: "告警显示", monitoring_chart: "监控截图显示", ai_summary: "AI 摘要称", internal_staff: "内部人员称", unknown: "来源不明" };
  const TIME_KIND = { fault_start_field: "起障字段记载", alarm_raised: "告警时刻", recovery_field: "恢复字段记载", alarm_cleared: "告警清除", ticket_created: "建单时间（不是故障时间）", ticket_returned: "返单时间（不是恢复时间）", ticket_closed: "结单时间（不是恢复时间）", customer_confirmed_recovery: "客户确认恢复", customer_reported_start: "客户报告的起点", observation: "某次检查的时刻", business_start: "业务起点", business_recovery: "业务恢复时刻" };
  const CAUSE_KIND = { root_cause_confirmed: "确认的根因", root_cause_claimed: "某方称的原因，未核实", investigation_finding: "排查结论，不是根因", process_blocker: "处理受阻，不是原因", recovery_mode: "恢复方式，不是根因", planned_work: "计划作业", suspected_mechanism: "推测的机制", candidate_list_item: "“可能原因”清单之一" };
  const ROLE = { located_fault_point: "已定位的故障点", test_node: "测试节点", service_endpoint: "业务端点", customer_site: "客户现场", alarm_location: "告警位置", transit_node: "途经节点" };
  const BASIS = { formal_determination: "正式定责", claimed: "某方自称", inferred_from_role: "仅凭角色推断，不作结论" };
  const FIELD = { ticket_no: "工单编号", customer: "客户名称", circuit_id: "电路编号", created_at: "建单时间", fault_type: "故障类型", occurred_at: "故障发生时间", recovered_at: "故障恢复时间", duration_returned: "返单历时", description: "故障描述", cause: "原因栏", responsible_party: "责任方栏", a_end: "A 端", z_end: "Z 端", vendor: "供应商", handling_dept: "处理部门" };
  const ISSUE = {
    TIME_CANDIDATES_DIFFER: ["同一件事有好几个时间", "建单、告警、字段、客户确认的时间含义不同，系统不会随手挑一个。"],
    TIME_ORDER_INVERTED: ["恢复时间早于发生时间", "多半是工单录入错误；系统保留原值，不擅自改。"],
    NEGATIVE_DURATION: ["历时算出来是负数", "起止时间互相矛盾，所以不给故障历时。"],
    ONGOING_NO_END: ["没有可靠的恢复时间", "因此不计算最终历时。"],
    DURATION_BASIS_MISMATCH: ["“返单历时”和起止时间差对不上", "两个历时口径不同，不能混用。"],
    RECOVERY_UNVERIFIED: ["恢复没有客户确认", "只有系统记录说已恢复，没人确认业务真的好了。"],
    RECOVERY_SCOPE_LIMITED: ["“检查正常”不等于“业务恢复”", "只测了一段或一个指标正常，不能证明客户业务恢复。"],
    CAUSE_NOT_DIAGNOSIS: ["原因栏写的不是根因", "写的是排查结果或恢复方式，只作候选，不当作原因。"],
    RESPONSIBILITY_NO_BASIS: ["没有人认定过责任", "不能因为是供应商在处理，就认定是供应商的责任。"],
    OBSERVATION_SCOPE_DIFFERS: ["客户看到的和我方测到的范围不同", "不能因为我方测试正常就否定客户的感受，两者并列保留。"],
    LOCATION_NOT_LOCATED: ["还没有定位到具体故障点", "现有的只是业务两端、告警位置或测试点，不是故障点。"],
    DUPLICATE_CONTENT: ["同一结论被重复记录", "已合并，不会重复计入。"],
    DERIVED_SOURCE_DUPLICATE: ["引用或摘要不算独立证据", "AI 摘要、邮件引用只是转述，不增加可信度。"],
    TIME_PLACEHOLDER: ["原文有未填写的模板占位符", "例如 {{end_time}}，不当作时间。"],
  };
  const SEVERITY = { critical: ["严重冲突", "critical"], warning: ["待核实", ""], info: ["提示", "info"] };
  const SRC_KIND = { ticket_fields: "工单字段", process_log: "处理过程", email_html: "邮件", email_eml: "邮件", image: "图片", pdf: "PDF 附件", docx: "Word 附件", text: "文本" };

  // ───────────────────────── 工具 ─────────────────────────
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const badge = (status) => `<span class="badge s-${status}"><span aria-hidden="true">${STATUS[status].icon}</span>${STATUS[status].label}</span>`;
  const short = (s, n) => (s.length > n ? s.slice(0, n) + "…" : s);

  function highlight(text, needles) {
    const ranges = [];
    for (const n of needles) {
      if (!n) continue;
      const i = text.indexOf(n);
      if (i >= 0) ranges.push([i, i + n.length]);
    }
    ranges.sort((a, b) => a[0] - b[0]);
    const merged = [];
    for (const r of ranges) {
      const last = merged[merged.length - 1];
      if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]); else merged.push([...r]);
    }
    let out = "", pos = 0;
    for (const [a, b] of merged) { out += esc(text.slice(pos, a)) + "<mark>" + esc(text.slice(a, b)) + "</mark>"; pos = b; }
    return out + esc(text.slice(pos));
  }

  function candText(name, c) {
    if (name === "start_time" || name === "end_time") return c.time.raw;
    return c.description || c.party || c.statement || c.action || "";
  }
  function candKind(name, c) {
    if (c.time_kind) return TIME_KIND[c.time_kind] || c.time_kind;
    if (c.cause_kind) return CAUSE_KIND[c.cause_kind] || c.cause_kind;
    if (c.role) return ROLE[c.role] || c.role;
    if (c.basis) return BASIS[c.basis] || c.basis;
    return c.metric || "";
  }
  function valueText(name, el) {
    const v = el.value;
    if (v == null || v === "") return null;
    if (name === "start_time" || name === "end_time") return v.raw;
    if (name === "handling_process") return `共 ${v.length} 步`;
    return String(v);
  }
  function openIssues(a) { return a.issues.filter((i) => i.severity !== "info"); }
  function counts(a) {
    const c = { confirmed: 0, documented: 0, unknown: 0, conflicted: 0 };
    ELEMENTS.forEach((n) => c[a.elements[n].status]++);
    return c;
  }
  function spanLabel(a, span) {
    const m = a.materials.find((x) => x.id === span.material_id);
    const kind = SRC_KIND[m?.kind] || "材料";
    const l = span.locator;
    if (l.type === "field") return `${kind} · ${FIELD[l.field_key] || l.field_key}`;
    if (l.type === "log_entry") return `${kind} · 第 ${l.seq} 条`;
    if (l.type === "page") return `${kind} · 第 ${l.page} 页`;
    if (l.type === "email_message") return `${kind} · 第 ${l.message_index + 1} 封${l.part === "header" ? "（邮件头）" : ""}`;
    return kind;
  }

  // ───────────────────────── 状态与事件 ─────────────────────────
  const state = { step: 1, entryTab: "local", tickets: [], pick: null, ref: null, data: null, entry: "local", element: ELEMENTS[0], tab: "main", legend: true, log: [] };
  const embedded = window.parent !== window;

  function emit(type, detail) {
    const msg = { source: "noc7", type, ...detail };
    state.log.push({ dir: "out", msg });
    if (embedded) window.parent.postMessage(msg, "*");
    refreshLog();
  }
  // 设计稿不校验来源；前端实现时必须校验 e.origin 是工作台的域名，并把 postMessage 的 "*" 换成该域名。
  window.addEventListener("message", (e) => {
    const d = e.data;
    if (d && d.type === "noc7.open" && typeof d.ticket_ref === "string") {
      state.log.push({ dir: "in", msg: d });
      refreshLog();
      openTicket(d.ticket_ref, "workbench").then((ok) => { if (ok) go(2); });
    }
  });
  function toast(text) {
    const t = $("#toast"); t.textContent = text; t.classList.add("show");
    clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove("show"), 3200);
  }

  async function openTicket(ref, entry) {
    const data = await source.get(ref);
    if (!data) return false;
    Object.assign(state, { data, ref, entry, element: ELEMENTS[0], tab: "main", pick: ref });
    emit("noc7.ticket.opened", { ticket_ref: ref, entry });
    return true;
  }
  function go(step) {
    if (step > 1 && !state.data) return;
    state.step = step;
    render();
    $("#screen").focus({ preventScroll: true });
  }
  function writeHash() {
    const h = `#/${state.step}/${state.ref || ""}/${state.step === 2 ? state.element : ""}${state.step === 2 && state.tab !== "main" ? "/" + state.tab : ""}`;
    try { history.replaceState(null, "", h); } catch (_) { /* file:// 下个别浏览器不允许，忽略 */ }
  }

  // ───────────────────────── 顶栏 ─────────────────────────
  function renderTop() {
    const names = ["选择工单", "七要素与原文出处", "公司报告"];
    $("#stepper").innerHTML = names.map((n, i) => {
      const k = i + 1, cls = k === state.step ? "active" : k < state.step ? "done" : "";
      return `<button class="step ${cls}" data-step="${k}" ${k > 1 && !state.data ? "disabled" : ""} ${k === state.step ? 'aria-current="step"' : ""}><span class="n">${k < state.step ? "✓" : k}</span>${n}</button>`;
    }).join("");
    const from = { local: "来源：本地工单包", workbench: `来源：NOC 工作台传入${state.ref ? " · " + state.ref : ""}`, link: `来源：链接传入${state.ref ? " · " + state.ref : ""}` };
    $("#source-chip").textContent = from[state.entry];
  }

  // ───────────────────────── 画面 1：选择工单 ─────────────────────────
  function renderStep1() {
    const flow = `<div class="flow" aria-label="整体流程">
      <div class="node"><b>① 原始工单</b>字段 · 处理过程 · 邮件 · 附件</div><span class="arrow">→</span>
      <div class="node"><b>② 大模型预处理</b>只读带编号的原文片段，不能凭空下结论</div><span class="arrow">→</span>
      <div class="node"><b>③ 七要素 + 原文出处</b>每条结论点得回原文；拿不准就留空或标待核实</div><span class="arrow">→</span>
      <div class="node"><b>④ 标准化公司报告</b>可下载 Word</div><span class="arrow">→</span>
      <div class="node out-of-scope"><b>人工审核</b>在 NOC 工作台完成，不在本页</div></div>`;
    const local = state.tickets.map((t) => {
      const full = DEMO.tickets.find((x) => x.ticket.ticket_ref === t.ticket_ref);
      const a = full.analysis, c = counts(a), open = openIssues(a).length;
      return `<button class="ticket ${state.pick === t.ticket_ref ? "selected" : ""}" data-pick="${esc(t.ticket_ref)}" aria-pressed="${state.pick === t.ticket_ref}">
        <div class="t-top"><span class="t-ref">${esc(t.ticket_ref)}</span><span class="badge b-info">${esc(t.list_status)}</span></div>
        <div class="t-title">${esc(t.title.replace("【合成】", ""))}</div>
        <div class="dots" title="按顺序：${ELEMENTS.map((n) => LABEL[n] + "=" + STATUS[a.elements[n].status].label).join("；")}">${ELEMENTS.map((n) => `<span class="dot ${a.elements[n].status}"></span>`).join("")}</div>
        <div class="t-sum">${c.confirmed + c.documented} 个有结论 · ${c.unknown} 个未知${c.conflicted ? ` · <b style="color:var(--conf)">${c.conflicted} 个矛盾</b>` : ""} · <span class="badge b-warn">待核实 ${open}</span></div>
        <div class="t-meta"><span>${esc(t.category || "")}</span></div></button>`;
    }).join("");
    const wb = `<div class="wb-note"><b>工作台只需要传入「工单号」</b>，本页自己向接口取分析结果，不要求工作台懂七要素的格式。</div>
      <div class="wb-form"><input id="wb-ref" placeholder="工单号，例如 SYN-S09" value="${esc(state.wbRef || "")}" aria-label="工单号"><button class="btn primary" id="wb-load" type="button">载入</button></div>
      <p class="err" id="wb-err" hidden></p>
      <p class="small muted">等价于工作台打开：<code>index.html?ticket=SYN-S09</code>，或向本页 iframe 发送 <code>postMessage({type:"noc7.open", ticket_ref:"SYN-S09"})</code>。点右上角“接入 NOC 工作台”可看完整约定和实时事件。</p>`;
    $("#screen").innerHTML = `
      <div class="screen-head"><h1>选择一张工单</h1><p>演示集共 ${state.tickets.length} 张合成工单，覆盖“结论清楚”“大量未知”“时间矛盾”等情形。</p></div>
      ${flow}
      <div class="entry">
        <section class="card entry-main" style="padding:0 14px 0">
          <div class="tabs" role="tablist">
            <button class="tab ${state.entryTab === "local" ? "active" : ""}" data-etab="local" role="tab">本地工单包</button>
            <button class="tab ${state.entryTab === "workbench" ? "active" : ""}" data-etab="workbench" role="tab">由 NOC 工作台传入</button></div>
          <div class="tab-body">${state.entryTab === "local" ? `<div class="tickets">${local}</div>` : wb}</div>
        </section>
        <aside class="card entry-side">
          <h2>这一步在做什么</h2>
          <ul>
            <li>选一张工单。演示集里的工单<b>已经预处理好</b>（正式版：选中后触发分析，显示进度）。</li>
            <li>下一页看<b>七要素</b>，每条结论都能点回<b>原文出处</b>。</li>
            <li>再下一页是<b>公司格式报告</b>，可下载 Word。</li>
          </ul>
          <h2 style="margin-top:14px">卡片上的色条</h2>
          <p class="small muted" style="margin:0 0 6px">7 格依次是：${ELEMENTS.map((n) => LABEL[n]).join("、")}。</p>
          <div style="display:grid;gap:5px;font-size:.82rem">
            <span><span class="dot confirmed" style="display:inline-block;vertical-align:middle"></span> 已确认</span>
            <span><span class="dot documented" style="display:inline-block;vertical-align:middle"></span> 有明确记录</span>
            <span><span class="dot unknown" style="display:inline-block;vertical-align:middle"></span> 未知（宁可留空）</span>
            <span><span class="dot conflicted" style="display:inline-block;vertical-align:middle"></span> 矛盾（并列展示）</span></div>
        </aside>
      </div>
      <div class="screen-foot"><span class="hint">${state.pick ? `已选：${esc(state.pick)}` : "请先选择一张工单"}</span>
        <button class="btn primary big" id="next1" ${state.pick ? "" : "disabled"}>查看七要素与原文出处 →</button></div>`;
  }

  // ───────────────────────── 画面 2：七要素与原文出处 ─────────────────────────
  function elementSuggestions(a, name) { return a.suggestions.filter((s) => s.element === name); }

  function renderStep2() {
    const a = state.data.analysis, t = state.data.ticket, c = counts(a), name = state.element, el = a.elements[name];
    const sug = elementSuggestions(a, name);
    const hasCands = Array.isArray(el.candidates) && el.candidates.length > 0;
    const canAI = name === "responsible_party" || name === "location";
    if (state.tab === "cands" && !hasCands) state.tab = "main";
    if (state.tab === "ai" && !canAI) state.tab = "main";

    const rail = ELEMENTS.map((n) => {
      const e = a.elements[n], v = valueText(n, e), warn = a.issues.filter((i) => i.element === n && i.severity !== "info").length;
      const ai = elementSuggestions(a, n).length;
      return `<button class="rail-item ${n === name ? "active" : ""}" data-el="${n}" aria-current="${n === name}">
        <div class="r-top"><span class="r-name">${LABEL[n]}</span>${badge(e.status)}</div>
        <div class="r-val">${v ? esc(short(v.replace(/\s+/g, " "), 24)) : e.status === "conflicted" ? "各方说法并列，未选边" : "— 不填写"}</div>
        <div class="r-flags">${warn ? `<span class="badge b-warn">⚠ 待核实 ${warn}</span>` : ""}${ai ? `<span class="badge b-ai">AI 建议</span>` : ""}</div></button>`;
    }).join("");
    const globals = a.issues.filter((i) => !i.element);
    const globalBox = globals.length ? `<details class="rail-global"><summary>整单提示 ${globals.length} 条</summary><ul>${globals.map((i) => `<li>${esc((ISSUE[i.code] || [i.message])[0])}</li>`).join("")}</ul></details>` : "";

    const tabs = `<div class="tabs d-tabs" role="tablist">
      <button class="tab ${state.tab === "main" ? "active" : ""}" data-tab="main">结论与出处</button>
      ${hasCands ? `<button class="tab ${state.tab === "cands" ? "active" : ""}" data-tab="cands">全部候选（${el.candidates.length}）</button>` : ""}
      ${canAI ? `<button class="tab ${state.tab === "ai" ? "active" : ""}" data-tab="ai">AI 建议，待确认<span class="count">${sug.length}</span></button>` : ""}</div>`;

    const { left, refs } = state.tab === "main" ? mainPane(a, name, el) : state.tab === "cands" ? candsPane(a, name, el) : aiPane(a, name, sug);
    $("#screen").innerHTML = `
      <section class="card summary">
        <span class="who">${esc(t.ticket_ref)}</span><span class="muted">${esc(t.title.replace("【合成】", ""))}</span><span class="sep"></span>
        ${Object.keys(STATUS).map((s) => `<span class="badge s-${s}">${STATUS[s].icon} ${STATUS[s].label} ${c[s]}</span>`).join("")}
        <span class="badge b-warn">⚠ 待核实 ${openIssues(a).length}</span>
        <button class="btn ghost" id="toggle-legend" type="button">${state.legend ? "收起图例" : "怎么读？"}</button></section>
      <section class="card legend" ${state.legend ? "" : "hidden"} aria-label="图例">
        ${Object.entries(STATUS).map(([k, s]) => `<div><span class="badge s-${k}">${s.icon} ${s.label}</span><br>${s.plain}</div>`).join("")}
        <div><span class="badge b-warn">⚠ 待核实</span><br>系统发现疑点，请有业务经验的人看一眼。</div>
        <div><span class="badge b-ai">AI 建议，待确认</span><br>模型的推测，仅限责任方和地点；不进入结论和报告。</div></section>
      <div class="workspace">
        <nav class="card rail" aria-label="七要素">${rail}${globalBox}</nav>
        <section class="card detail">
          <div class="d-head"><h2>${LABEL[name]}</h2>${badge(el.status)}<span class="muted small">${HELP[name]}</span><p class="plain">${STATUS[el.status].plain}</p></div>
          ${tabs}
          <div class="d-body"><div class="pane" id="pane-left">${left}</div><div class="pane" id="pane-ev">${evidencePane(a, name, refs)}</div></div>
        </section></div>
      <div class="screen-foot"><span class="hint guard">本页只展示，没有“通过/修改”按钮——人工审核在 NOC 工作台完成。
        <button class="btn ghost" id="review-req" type="button">在 NOC 工作台中审核 ↗</button></span>
        <button class="btn" data-step="1">← 换一张工单</button><button class="btn primary big" id="next2">生成公司报告 →</button></div>`;
    $("#pane-ev").scrollTop = 0;
  }

  function flagsFor(a, name) {
    const list = a.issues.filter((i) => i.element === name);
    if (!list.length) return "";
    return list.map((i) => {
      const p = ISSUE[i.code] || [i.code, i.message], [sev, cls] = SEVERITY[i.severity];
      return `<div class="flag ${cls}"><b><span class="badge ${i.severity === "info" ? "b-info" : "b-warn"}">${i.severity === "info" ? "ℹ" : "⚠"} ${sev}</span>${esc(p[0])}</b><p>${esc(p[1])}</p><p class="sys">系统原话：${esc(i.message)}</p></div>`;
    }).join("");
  }
  const chips = (refs) => refs.map((r) => `<button class="ref-chip" data-ev="${esc(r)}" type="button" title="定位到原文">${esc(r)}</button>`).join(" ");

  function mainPane(a, name, el) {
    const refs = [], v = valueText(name, el);
    let body;
    if (el.status === "unknown") {
      body = `<div class="verdict empty">不填写</div><p class="muted">材料里没有足够依据，所以这一栏<b>留空</b>。右侧是系统看过的相关原文，供对照。</p>`;
    } else if (el.status === "conflicted") {
      body = `<div class="verdict" style="color:var(--conf)">材料互相矛盾，未选边</div><div class="conflict-grid">${(el.candidates || []).map((c, i) =>
        `<div class="cand side-${i % 2 ? "b" : "a"}"><div class="c-top"><b>${esc(c.id)}</b><span>${esc(ATTR[c.attribution] || "")}</span><span>${esc(candKind(name, c))}</span></div><div class="c-text">${esc(candText(name, c))}</div><div class="refs-line">出处：${chips(c.evidence_refs)}</div></div>`).join("")}</div>`;
    } else if (name === "handling_process") {
      body = `<ol class="steps">${el.value.map((s) => `<li><div class="when">${esc(s.time ? s.time.raw : "时间未知")}${s.duplicate_of ? " · 重复记录" : ""}</div><div><span class="who">${esc(s.actor || "")}</span> ${esc(s.action)}${s.result ? "，" + esc(s.result) : ""}</div><div class="refs-line">${esc(ATTR[s.attribution] || "")} ${chips(s.evidence_refs)}</div></li>`).join("")}</ol>`;
    } else {
      const val = name === "start_time" || name === "end_time" ? el.value : null;
      const sub = val ? `<div class="verdict-sub">${val.tz_source === "assumed" ? '<span class="badge b-info">时区按系统默认 GMT+8 推定</span>' : '<span class="badge b-info">原文写明时区</span>'}<span class="badge b-info">精确到${{ second: "秒", minute: "分钟", day: "日" }[val.precision] || val.precision}</span></div>` : "";
      body = `<div class="verdict">${esc(v)}</div>${sub}${el.note ? `<p class="muted small">系统备注：${esc(el.note)}</p>` : ""}<div class="refs-line">结论出处：${chips(el.evidence_refs)}</div>`;
    }
    (el.evidence_refs || []).forEach((r) => refs.push(r));
    (el.candidates || []).forEach((c) => c.evidence_refs.forEach((r) => refs.push(r)));
    if (name === "handling_process") (el.value || []).forEach((s) => s.evidence_refs.forEach((r) => refs.push(r)));
    return { left: `<h3>结论</h3>${body}${flagsFor(a, name) ? `<h3 style="margin-top:16px">待核实</h3>${flagsFor(a, name)}` : ""}`, refs: [...new Set(refs)] };
  }

  function candsPane(a, name, el) {
    const refs = [];
    const items = el.candidates.map((c) => {
      c.evidence_refs.forEach((r) => refs.push(r));
      const picked = el.selected === c.id;
      return `<div class="cand ${picked ? "picked" : ""}"><div class="c-top"><b>${esc(c.id)}</b>${picked ? '<span class="badge s-documented">被采用为结论</span>' : ""}<span>${esc(ATTR[c.attribution] || "")}</span><span>${esc(candKind(name, c))}</span></div><div class="c-text">${esc(candText(name, c))}</div><div class="refs-line">出处：${chips(c.evidence_refs)}</div></div>`;
    }).join("");
    return { left: `<h3>系统读到的全部说法（并列保留，不丢弃）</h3><div class="conflict-grid">${items}</div>`, refs: [...new Set(refs)] };
  }

  function aiPane(a, name, sug) {
    const refs = [];
    const inner = sug.length ? sug.map((s) => s.candidates.map((c) => {
      c.evidence_refs.forEach((r) => refs.push(r));
      const ok = c.quote_check === "match";
      return `<div class="ai-cand"><div class="c-top"><span class="badge b-ai">AI 建议</span><span class="sample-tag">示例（设计稿手写，结构同 BusinessSuggestion）</span></div>
        <div style="font-weight:600">${esc(c.text)}</div><div class="muted small">${esc(c.role)}</div>
        <blockquote>“${esc(c.quote)}”</blockquote>
        <div class="refs-line">引用出处：${chips(c.evidence_refs)} ${ok ? '<span class="badge s-confirmed">✓ 原文核对通过</span>' : '<span class="badge b-warn">⚠ 待核对：引文在原文里找不到</span>'}</div></div>`;
    }).join("")).join("") : `<div class="none-box">本单模型没有给出${LABEL[name]}的建议。</div>`;
    return { left: `<div class="ai-box"><b>AI 建议，待确认</b><p style="margin:4px 0 0" class="small">这是模型的推测，<b>不是结论</b>：不会写进公司报告，也不会改变上面的“${STATUS[state.data.analysis.elements[name].status].label}”。引用核对只证明那句话在原文里，不证明建议正确。要不要采纳，由 NOC 工作台里的审核人决定。</p></div>${inner}`, refs: [...new Set(refs)] };
  }

  function evidencePane(a, name, refs) {
    const el = a.elements[name];
    const quotes = state.tab === "ai" ? elementSuggestions(a, name).flatMap((s) => s.candidates.map((c) => c.quote)) : [];
    const concl = new Set(el.evidence_refs || []);
    let head = "原文出处";
    if (state.tab === "main" && !concl.size) head = el.status === "conflicted" ? "原文出处：各方说法所依据的原文" : "原文出处：该要素没有结论依据，下面是系统查看过的相关原文";
    if (!refs.length) return `<h3>${head}</h3><div class="none-box">没有可引用的原文。<br>“没有出处”正是系统不敢填写的原因。</div>`;
    const cards = refs.map((r) => {
      const span = a.evidence.find((s) => s.id === r);
      if (!span) return "";
      const ai = state.tab === "ai";
      const citing = ai ? [] : (el.candidates || []).filter((c) => c.evidence_refs.includes(r));
      const needles = ai ? quotes : citing.map((c) => candText(name, c));
      if (!ai && name === "handling_process") (el.value || []).filter((s) => s.evidence_refs.includes(r)).forEach((s) => needles.push(s.action));
      if (!ai && typeof el.value === "string" && el.value.length < 80) needles.push(el.value);
      const who = citing.find((c) => c.attribution) ? ATTR[citing[0].attribution] : "";
      const why = ai ? "AI 建议引用了这条原文" : [concl.has(r) ? "结论依据" : "", citing.length ? "被候选 " + citing.map((c) => c.id).join("、") + " 引用" : ""].filter(Boolean).join(" · ");
      return `<article class="ev" id="ev-${esc(r.replace(/[^\w-]/g, "_"))}"><div class="ev-head"><span class="ref-chip" style="cursor:default">${esc(r)}</span><span class="src">${esc(spanLabel(a, span))}</span>${who ? `<span class="badge b-info">${esc(who)}</span>` : ""}${span.role !== "original" ? `<span class="badge b-warn">衍生材料</span>` : ""}</div>
        <pre class="ev-body">${highlight(span.text, needles)}</pre>${why ? `<div class="ev-why">${esc(why)}</div>` : ""}</article>`;
    }).join("");
    return `<h3>${head}</h3>${cards}<p class="small muted">黄色高亮 = ${state.tab === "ai" ? "AI 建议引用的那句话；没有高亮说明在原文里找不到" : "结论里引用的那句原文"}。证据编号 <code>M02/log:3</code> = 材料 M02 的第 3 条处理记录。</p>`;
  }

  // ───────────────────────── 画面 3：公司报告 ─────────────────────────
  const ROW_LABEL = { 4: "申报时间", 5: "恢复时间", 6: "故障历时", 7: "故障现象", 8: "处理过程", 9: "故障原因分析", 10: "改进及预防措施" };
  function pendingTarget(row, lineIdx, before) {
    if (row === 4) return "start_time";
    if (row === 5 || row === 6) return "end_time";
    if (row === 7) return "phenomenon";
    if (row === 8) return "handling_process";
    if (row === 9) {
      if (lineIdx === 0) return "cause";
      if (before.endsWith("责任方：")) return "responsible_party";
      if (before.endsWith("故障位置：")) return "location";
      return "cause";
    }
    return null;
  }
  function renderStep3() {
    const { companyReport: cr, downloads, ticket } = state.data;
    const pend = [];
    const rows = Array.from({ length: 11 }, () => []);
    cr.cells.forEach((c) => rows[c.row].push(c));
    const html = rows.map((r) => `<tr>${r.sort((x, y) => x.col - y.col).map((c) => {
      const tag = c.label ? "th" : "td";
      const span = `${c.rowspan > 1 ? ` rowspan="${c.rowspan}"` : ""}${c.colspan > 1 ? ` colspan="${c.colspan}"` : ""}${c.label && c.col === 0 ? ' class="group"' : ""}`;
      const ps = c.lines.map((line, li) => {
        let before = "";
        const inner = line.map((p) => {
          if (p.pending) {
            const target = pendingTarget(c.row, li, before);
            pend.push({ row: c.row, text: p.text, target, col: c.col });
            before += p.text;
            return `<mark class="${target ? "jump" : ""}" ${target ? `data-jump="${target}" title="点击查看对应要素"` : ""}>${esc(p.text)}</mark>`;
          }
          before += p.text;
          return esc(p.text);
        }).join("");
        return `<p>${inner}</p>`;
      }).join("");
      return `<${tag}${span}>${ps}</${tag}>`;
    }).join("")}</tr>`).join("");
    const linked = pend.filter((p) => p.target), boiler = pend.length - linked.length;
    const list = linked.map((p) => `<li><span><b>${ROW_LABEL[p.row] || ""}</b> ${esc(p.text)}</span><button class="btn ghost small" data-jump="${p.target}" type="button" style="white-space:nowrap">→ ${LABEL[p.target]}</button></li>`).join("");
    const base = `${ticket.ticket_ref}-company-report`;
    $("#screen").innerHTML = `
      <div class="screen-head"><h1>公司报告预览与下载</h1><p>按公司《故障处理报告》模板排版，与下载的 Word 同源生成。</p></div>
      <div class="report-wrap">
        <div class="paper-scroll"><div class="paper"><h2>故障处理报告 Failure Report</h2>
          ${cr.synthetic ? '<p class="p-syn">合成演示数据，不代表真实工单或真实模型质量。</p>' : ""}<p class="p-date">${esc(cr.report_date)}</p>
          <table><colgroup><col class="c0"><col class="c1"><col class="c2"><col class="c3"></colgroup><tbody>${html}</tbody></table>
          <div class="sig"><p>故障处理报告人(Failure Reporter)：</p><p>故障处理报告审核(Failure Report Audit)：</p><p>审核日期(Audit Date)：</p></div></div></div>
        <aside class="side">
          <section class="card"><div class="draft"><b>草稿 · 未经人工审核</b><div class="small">签字栏留空，由 NOC 工作台里的审核人处理。</div></div>
            <div class="dl">
            <a class="btn primary big" href="${esc(downloads.docx)}" download data-dl="docx">⬇ 下载 Word（.docx）</a>
            <div class="file">${esc(base)}.docx</div>
            <a class="btn" href="${esc(downloads.html)}" download data-dl="html">⬇ 下载网页版（.html）</a></div>
            <p class="small muted" style="margin:8px 0 0">示例文件由真实流水线从合成数据生成（<code>samples/</code>）。</p></section>
          <section class="card"><b>下载前检查</b>
            ${linked.length ? `<p class="small muted" style="margin:2px 0 0"><mark style="background:#fff176">黄色【待核实】</mark>共 ${linked.length} 处，Word 里同样高亮。点“查看”回到对应要素。</p><ul class="checklist">${list}</ul>`
              : `<p class="small" style="margin:6px 0 0"><span class="badge s-confirmed">✓ 七要素里没有待核实项</span></p>`}
            ${boiler ? `<p class="small muted" style="margin:6px 0 0">另有 ${boiler} 处高亮无法对应到某个要素（例如系统默认的“改进措施”表述），审核时一并确认。</p>` : ""}</section>
          <section class="card"><button class="btn" id="review-req" type="button" style="width:100%">在 NOC 工作台中审核 ↗</button>
            <p class="small muted" style="margin:8px 0 0">审核、改写、签字都在工作台里做。本页只负责把预处理结果交出去。</p></section>
          <div class="screen-foot" style="justify-content:space-between"><button class="btn" data-step="2">← 回到七要素</button><button class="btn" data-step="1">换一张工单</button></div>
        </aside></div>`;
  }

  // ───────────────────────── 抽屉：接入方式 ─────────────────────────
  function refreshLog() {
    const box = $("#evlog");
    if (!box) return;
    box.innerHTML = state.log.length ? state.log.map((l) => `<div class="${l.dir}">${l.dir === "in" ? "← 收到" : "→ 发出"}  ${esc(JSON.stringify(l.msg))}</div>`).join("") : "（还没有事件）";
    box.scrollTop = box.scrollHeight;
  }
  function renderDrawer() {
    $("#drawer-body").innerHTML = `
      <h3>原则：页面不关心工单从哪来</h3>
      <p class="small">所有入口最后都只调用一个函数 <code>openTicket(工单号)</code>；页面再向 <code>TicketSource</code> 取数据。工作台不需要懂七要素的内部格式。</p>
      <h3>① 入口（工作台 → 本页）</h3>
      <table><tr><th>方式</th><th>怎么用</th></tr>
        <tr><td>独立使用</td><td>画面 1 里选本地工单包</td></tr>
        <tr><td>链接</td><td><code>index.html?ticket=SYN-S09</code> 或 <code>#/2/SYN-S09/cause</code>，直接落在七要素页</td></tr>
        <tr><td>嵌入</td><td>工作台用 iframe 加载，加 <code>?embed=1</code> 隐藏品牌栏；再发 <code>postMessage({type:"noc7.open", ticket_ref})</code></td></tr></table>
      <h3>② 数据（本页 → 后端）</h3>
      <pre>GET /api/tickets                           工单列表
GET /api/tickets/{ref}/analysis            AnalysisResult JSON
GET /api/tickets/{ref}/company-report.docx 公司报告 Word
GET /api/tickets/{ref}/company-report.html 公司报告网页版</pre>
      <p class="small">页面只吃一种数据：<code>AnalysisResult</code>（<code>schemas/analysis-result.schema.json</code>）。公司报告表格来自同一份结果，前后端不另造格式。以上路径是拟定方案，由前端实现任务定稿。</p>
      <h3>③ 出口（本页 → 工作台）</h3>
      <table><tr><th>事件</th><th>何时发出</th></tr>
        <tr><td><code>noc7.ticket.opened</code></td><td>工单载入成功</td></tr>
        <tr><td><code>noc7.report.downloaded</code></td><td>下载了公司报告</td></tr>
        <tr><td><code>noc7.review.requested</code></td><td>点了“在 NOC 工作台中审核”，由工作台跳转到审核界面</td></tr></table>
      <h3>④ 实时事件（可试）</h3>
      <div class="evlog" id="evlog"></div>
      <p><button class="btn" id="sim-wb" type="button">模拟工作台传入 SYN-S06</button></p>
      <h3>本页不做的事</h3>
      <p class="small">不做审核（通过 / 改写 / 清空）、不改工单、不回写 NOC。那些属于 NOC 工作台。</p>`;
    refreshLog();
  }
  function setDrawer(open) {
    $("#drawer").classList.toggle("show", open); $("#scrim").classList.toggle("show", open);
    $("#drawer").setAttribute("aria-hidden", String(!open));
    if (open) renderDrawer();
  }

  // ───────────────────────── 渲染调度与事件 ─────────────────────────
  function render() {
    renderTop();
    [renderStep1, renderStep2, renderStep3][state.step - 1]();
    writeHash();
  }

  document.addEventListener("click", async (e) => {
    const t = e.target.closest("button, a, mark");
    if (!t) return;
    const d = t.dataset;
    if (d.step) return go(+d.step);
    if (d.etab) { state.entryTab = d.etab; return render(); }
    if (d.pick) { state.pick = d.pick; return render(); }
    if (t.id === "next1" && state.pick) { if (await openTicket(state.pick, "local")) go(2); return; }
    if (t.id === "wb-load") return loadFromWorkbenchTab();
    if (d.el) { state.element = d.el; state.tab = "main"; return render(); }
    if (d.tab) { state.tab = d.tab; return render(); }
    if (t.id === "toggle-legend") { state.legend = !state.legend; return render(); }
    if (t.id === "next2") return go(3);
    if (d.ev) {
      const card = document.getElementById("ev-" + d.ev.replace(/[^\w-]/g, "_"));
      if (card) { card.scrollIntoView({ block: "nearest", behavior: "smooth" }); card.classList.remove("flash"); void card.offsetWidth; card.classList.add("flash"); }
      return;
    }
    if (d.jump) { state.element = d.jump; state.tab = "main"; return go(2); }
    if (d.dl) { emit("noc7.report.downloaded", { ticket_ref: state.ref, format: d.dl }); toast("已下载示例文件（合成数据，页眉为空）"); return; }
    if (t.id === "review-req") { emit("noc7.review.requested", { ticket_ref: state.ref }); toast(embedded ? "已通知 NOC 工作台打开审核界面" : "独立运行：已发出 noc7.review.requested（当前没有工作台接收）"); return; }
    if (t.id === "open-drawer") return setDrawer(true);
    if (t.id === "close-drawer") return setDrawer(false);
    if (t.id === "sim-wb") { window.postMessage({ type: "noc7.open", ticket_ref: "SYN-S06" }, "*"); return; }
  });
  $("#scrim").addEventListener("click", () => setDrawer(false));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") setDrawer(false);
    if (e.target.matches("input")) { if (e.key === "Enter" && e.target.id === "wb-ref") loadFromWorkbenchTab(); return; }
    if (state.step === 2 && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
      const i = ELEMENTS.indexOf(state.element) + (e.key === "ArrowDown" ? 1 : -1);
      if (i >= 0 && i < ELEMENTS.length) { e.preventDefault(); state.element = ELEMENTS[i]; state.tab = "main"; render(); }
    }
  });

  async function loadFromWorkbenchTab() {
    const input = $("#wb-ref"), ref = input.value.trim();
    state.wbRef = ref;
    if (await openTicket(ref, "workbench")) return go(2);
    const err = $("#wb-err"); err.hidden = false;
    err.textContent = `找不到工单 “${ref}”。演示集只有：${state.tickets.map((t) => t.ticket_ref).join("、")}。`;
  }

  // ───────────────────────── 启动 ─────────────────────────
  async function init() {
    const q = new URLSearchParams(location.search);
    if (q.get("embed") === "1") document.body.classList.add("embed");
    state.tickets = await source.list();
    const m = location.hash.match(/^#\/(\d)\/([^/]*)\/?([^/]*)\/?([^/]*)/);
    const ref = q.get("ticket") || (m && m[2]) || "";
    if (ref && (await openTicket(ref, "link"))) {
      state.step = q.get("ticket") ? 2 : Math.min(+m[1], 3) || 2;
      if (m && ELEMENTS.includes(m[3])) state.element = m[3];
      if (m && ["cands", "ai"].includes(m[4])) state.tab = m[4];
    }
    render();
  }
  init();
})();
