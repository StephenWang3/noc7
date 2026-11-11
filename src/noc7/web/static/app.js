/* 三个画面。数据只经过 TicketSource，来自本机演示服务。 */
(function () {
  "use strict";

  const source = {
    async catalog() {
      const res = await fetch("/api/tickets");
      if (!res.ok) throw new Error("无法读取工单列表");
      return res.json();
    },
    async list() { return (await this.catalog()).tickets; },
    async get(ref) {
      const res = await fetch("/api/tickets/" + encodeURIComponent(ref));
      if (!res.ok) return null;
      const body = await res.json();
      if (body.status !== "ready") return body;
      return {
        status: "ready",
        ticket: body.ticket,
        analysis: body.analysis,
        companyReport: body.company_report,
        downloads: body.downloads,
      };
    },
  };

  // ───────────────────────── 词表：把内部代码翻成评委看得懂的话 ─────────────────────────
  let ELEMENTS = [];
  let LABEL = {};
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
  const TIME_KIND = { fault_start_field: "起障字段记载", alarm_raised: "告警时刻", recovery_field: "恢复字段记载", alarm_cleared: "告警清除", ticket_created: "建单时间（不是故障时间）", ticket_returned: "返单时间（不是恢复时间）", ticket_closed: "结单时间（不是恢复时间）", customer_confirmed_recovery: "客户确认恢复", customer_reported_start: "客户报告的起点", observation: "某次检查的时刻", business_start: "业务起点", business_recovery: "业务恢复时刻", confirmation_action: "确认动作的时刻", protocol_down: "协议中断时刻", protocol_up: "协议恢复时刻", vendor_reported: "供应商陈述的时间", repair_completed: "现场修复完成", warning_raised: "预警产生", chart_first_nonzero: "曲线首次出现非零", chart_window: "监控截图的时间窗口", ticket_cancelled: "撤单时间", record_time: "处理记录的时间", body_text_date: "正文里写的日期", message_sent: "邮件发送时间", planned: "计划或预约时间", historical_service_event: "与本次故障无关的历史日期", other: "其他时间" };
  const CAUSE_KIND = { root_cause_confirmed: "确认的根因", root_cause_claimed: "某方称的原因，未核实", investigation_finding: "排查结论，不是根因", process_blocker: "处理受阻，不是原因", recovery_mode: "恢复方式，不是根因", planned_work: "计划作业", suspected_mechanism: "推测的机制", candidate_list_item: "“可能原因”清单之一", unclassified: "尚未归类", alarm_explanation: "告警机制说明，不是根因", resource_state: "资源状态，不是根因", customer_suspicion: "客户的怀疑，不是定论" };
  const ROLE = { located_fault_point: "已定位的故障点", test_node: "测试节点", service_endpoint: "业务端点", customer_site: "客户现场", alarm_location: "告警位置", transit_node: "途经节点" };
  const BASIS = { formal_determination: "正式定责", claimed: "某方自称", inferred_from_role: "仅凭角色推断，不作结论", system_field: "工单系统字段兜底，待核实" };
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
    SEMANTIC_ASSERTIONS_CONFLICT: ["时间或原因的说法互相冲突", "系统保留各方说法，不替你选边。"],
    SEMANTIC_RELATION_INCOMPLETE: ["时间或原因的关系不完整", "缺少对照关系，先不当成定论。"],
    SEMANTIC_STATUS_DOWNGRADED: ["结论被降级", "依据不够，没有保持模型自标的确认等级。"],
    TIME_TZ_MISSING: ["时间没有写明时区", "能按工单口径假定的会标明；不能假定的就不归一。"],
    TIME_BODY_RECORD_MISMATCH: ["正文日期和记录日期不一致", "两个日期都保留，不把其中一个改掉。"],
    CAUSE_CANDIDATE_LIST: ["原因栏是一张可能原因清单", "还没有确认哪一项真的发生。"],
    SERVICE_IDENTITY_UNVERIFIED: ["服务身份对不上", "新旧编号、带宽或归属有冲突，先不要当成同一条电路。"],
    RELATED_TICKET_SHARED_SOURCE: ["和其他工单共用告警", "这不是一份独立证据。"],
    RELATED_TICKET_INVALID: ["关联单已作废或撤销", "不把它当成有效结论。"],
    RELATED_TICKET_REOPENED: ["这是一张重开的历史单", "旧单结单不代表业务已经恢复。"],
    TICKET_CANCELLED: ["本单已撤销或作废", "不按有效故障结案，也不计算历时。"],
    STATUS_VIEW_MISMATCH: ["列表状态和详情状态不一致", "两处原文都保留。"],
    EVIDENCE_REF_MISSING: ["引用了不存在的证据", "这份结果不能当成报告。"],
    EVIDENCE_QUOTE_MISMATCH: ["引用的话不在原文里", "对不上的摘录不能进入结论。"],
    MATERIAL_PARSE_FAILED: ["有材料没有解析成功", "缺了的那份材料不能用来下结论。"],
    MATERIAL_LOW_QUALITY: ["附件读得不够清楚", "识别结果需要人工再看一眼。"],
    MATERIAL_UNSUPPORTED: ["有材料格式暂不支持", "没有静默丢掉，但也还不能用它下结论。"],
    MATERIAL_MISSING: ["清单里的材料缺失或被改过", "哈希对不上，这份材料不能用。"],
    ATTACHMENT_FLAG_MISMATCH: ["附件标志和实际附件不一致", "以实际登记的附件为准。"],
    EMBEDDED_INSTRUCTION: ["材料里有面向系统的指令性文字", "只把它当数据处理，不执行。"],
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
  const state = { step: 1, entryTab: "local", tickets: [], pick: null, ref: null, data: null, entry: "local", element: "start_time", tab: "main", legend: true, log: [], workbenchOrigins: [], importError: "", importProvider: "rules", poll: null, listSig: "" };
  const embedded = window.parent !== window;

  function extraOrigins() { return (state.workbenchOrigins || []).join(","); }
  function parentTarget() {
    if (window.parent === window) return null;
    let origin = "";
    try { origin = new URL(document.referrer).origin; } catch (err) { return null; }
    return noc7AcceptOrigin(origin, location.origin, extraOrigins()) ? origin : null;
  }
  function emit(type, detail) {
    const msg = { source: "noc7", type, ...detail };
    state.log.push({ dir: "out", msg });
    const target = parentTarget();
    if (target) window.parent.postMessage(msg, target);
    refreshLog();
  }
  window.addEventListener("message", (e) => {
    if (!noc7AcceptOrigin(e.origin, location.origin, extraOrigins())) return;
    const d = e.data;
    if (d && d.type === "noc7.open" && typeof d.ticket_ref === "string") {
      state.log.push({ dir: "in", msg: d });
      refreshLog();
      openTicket(d.ticket_ref, "workbench").then((ok) => { if (ok) go(2); else if (state.step === 1) render(); });
    }
  });
  function toast(text) {
    const t = $("#toast"); t.textContent = text; t.classList.add("show");
    clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove("show"), 3200);
  }

  function pickedTicket() { return state.tickets.find((t) => t.ticket_ref === state.pick) || null; }
  async function openTicket(ref, entry) {
    const data = await source.get(ref);
    if (!data) return false;
    state.pick = ref;
    if (data.status !== "ready") {
      state.pendingNote = data.status === "failed"
        ? (data.problems || (data.issues || []).map((i) => i.message) || ["分析失败"]).join("；")
        : "还在分析，完成后才能打开七要素。";
      return false;
    }
    state.pendingNote = "";
    Object.assign(state, { data, ref, entry, element: ELEMENTS[0] || "start_time", tab: "main", pick: ref });
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
    // 只在当前打开的那张是合成数据时提示。列表上不把导入的工单说成 fixtures。
    const bar = $(".synthetic-bar");
    const opened = state.data && state.data.analysis && state.data.analysis.data_class === "synthetic";
    bar.hidden = !opened;
    if (opened) {
      const ref = (state.data.ticket && state.data.ticket.ticket_ref) || state.ref || "";
      const prepared = ["SYN-P04", "SYN-S09", "SYN-P01", "SYN-S06", "SYN-S02"];
      bar.textContent = prepared.indexOf(ref) >= 0
        ? "合成演示数据（来自仓库 fixtures/），不是真实工单，也不代表真实模型质量。"
        : "合成数据，不是真实工单，也不代表真实模型质量。";
    }
  }

  // ───────────────────────── 画面 1：选择工单 ─────────────────────────
  function ticketCards() {
    return state.tickets.map((t) => {
      const selected = state.pick === t.ticket_ref;
      if (t.status !== "ready" || !t.element_status) {
        const failed = t.status === "failed";
        return `<button class="ticket ${selected ? "selected" : ""}" data-pick="${esc(t.ticket_ref)}" aria-pressed="${selected}">
          <div class="t-top"><span class="t-ref">${esc(t.ticket_ref)}</span><span class="badge ${failed ? "b-warn" : "b-info"}">${failed ? "失败" : "分析中"}</span></div>
          <div class="t-title">${esc(t.title || "")}</div>
          <div class="t-sum">${failed ? esc((t.problems || []).join("；") || "分析失败，没有生成报告") : "正在计算，完成后才能查看七要素。"}</div>
          <div class="t-meta"><span>${esc(t.category || "")}</span></div></button>`;
      }
      const c = { confirmed: 0, documented: 0, unknown: 0, conflicted: 0 };
      ELEMENTS.forEach((n) => { if (c[t.element_status[n]] != null) c[t.element_status[n]]++; });
      const open = t.open_issues || 0;
      return `<button class="ticket ${selected ? "selected" : ""}" data-pick="${esc(t.ticket_ref)}" aria-pressed="${selected}">
        <div class="t-top"><span class="t-ref">${esc(t.ticket_ref)}</span><span class="badge b-info">${esc(t.list_status)}</span></div>
        <div class="t-title">${esc(t.title)}</div>
        <div class="dots" title="按顺序：${ELEMENTS.map((n) => LABEL[n] + "=" + (STATUS[t.element_status[n]] || {}).label).join("；")}">${ELEMENTS.map((n) => `<span class="dot ${esc(t.element_status[n] || "")}"></span>`).join("")}</div>
        <div class="t-sum">${c.confirmed + c.documented} 个有结论 · ${c.unknown} 个未知${c.conflicted ? ` · <b style="color:var(--conf)">${c.conflicted} 个矛盾</b>` : ""} · <span class="badge b-warn">待核实 ${open}</span></div>
        <div class="t-meta"><span>${esc(t.category || "")}</span></div></button>`;
    }).join("");
  }
  function patchStep1List() {
    const box = document.querySelector("#screen .tickets");
    if (!box || state.step !== 1 || state.entryTab !== "local") return false;
    box.innerHTML = ticketCards();
    const picked = pickedTicket();
    const hint = document.querySelector("#screen .screen-foot .hint");
    const next = document.getElementById("next1");
    if (hint) {
      hint.textContent = state.pick
        ? `已选：${state.pick}${picked && picked.status !== "ready" ? " · " + (picked.status === "failed" ? "失败" : "分析中") : ""}`
        : "请先选择一张工单";
    }
    if (next) next.disabled = !(picked && picked.status === "ready");
    return true;
  }
  function renderStep1() {
    const flow = `<div class="flow" aria-label="整体流程">
      <div class="node"><b>① 已结单工单</b>完整导出材料 · 含结案说明与附件</div><span class="arrow">→</span>
      <div class="node"><b>② 大模型预处理</b>只读带编号的原文片段，不能凭空下结论</div><span class="arrow">→</span>
      <div class="node"><b>③ 七要素 + 原文出处</b>每条结论点得回原文；拿不准就留空或标待核实</div><span class="arrow">→</span>
      <div class="node"><b>④ 标准化公司报告</b>可下载 Word</div><span class="arrow">→</span>
      <div class="node out-of-scope"><b>人工审核</b>在 NOC 工作台完成，不在本页</div></div>`;
    const local = ticketCards();
    const chosen = state.importProvider === "llm" ? "llm" : "rules";
    const importer = `<form id="import-form" class="wb-form import-row">
        <input id="import-file" type="file" accept=".zip,application/zip" aria-label="工单包 zip" required>
        <label><input type="radio" name="provider" value="rules"${chosen === "rules" ? " checked" : ""}> 规则</label>
        <label><input type="radio" name="provider" value="llm"${chosen === "llm" ? " checked" : ""}> 用模型分析</label>
        <button class="btn primary" type="submit">导入</button></form>
      <p class="err" id="import-err" ${state.importError ? "" : "hidden"}>${esc(state.importError || "")}</p>
      <p class="job-note small muted">预先放好的五张合成单用规则计算。导入标准工单包时，可以选规则，或用当前模型配置现场分析。模型通常要等一两分钟，卡片会停在「分析中」。</p>`;
    const wb = `<div class="wb-note"><b>工作台只需要传入「工单号」</b>，本页自己向接口取分析结果，不要求工作台懂七要素的格式。</div>
      <div class="wb-form"><input id="wb-ref" placeholder="工单号，例如 SYN-S09" value="${esc(state.wbRef || "")}" aria-label="工单号"><button class="btn primary" id="wb-load" type="button">载入</button></div>
      <p class="err" id="wb-err" ${state.wbError ? "" : "hidden"}>${esc(state.wbError || "")}</p>
      <p class="small muted">等价于工作台打开：<code>index.html?ticket=SYN-S09</code>，或向本页 iframe 发送 <code>postMessage({type:"noc7.open", ticket_ref:"SYN-S09"})</code>。点右上角“接入 NOC 工作台”可看完整约定和实时事件。</p>`;
    $("#screen").innerHTML = `
      <div class="screen-head"><h1>选择一张工单</h1><p>预先放好五张合成工单。也可以导入一张从没见过的标准工单包，算完再看。</p></div>
      ${flow}
      <div class="entry">
        <section class="card entry-main" style="padding:0 14px 0">
          <div class="tabs" role="tablist">
            <button class="tab ${state.entryTab === "local" ? "active" : ""}" data-etab="local" role="tab">本地工单包</button>
            <button class="tab ${state.entryTab === "workbench" ? "active" : ""}" data-etab="workbench" role="tab">由 NOC 工作台传入</button></div>
          <div class="tab-body">${state.entryTab === "local" ? `${importer}<div class="tickets">${local}</div>` : wb}</div>
        </section>
        <aside class="card entry-side">
          <h2>这一步在做什么</h2>
          <ul>
            <li>五张合成单在打开页面时用<b>规则</b>计算。导入的包可以改选<b>用模型分析</b>，没算完会停在「分析中」，失败会写出原因。</li>
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
      <div class="screen-foot"><span class="hint">${state.pick ? `已选：${esc(state.pick)}${pickedTicket() && pickedTicket().status !== "ready" ? " · " + (pickedTicket().status === "failed" ? "失败" : "分析中") : ""}` : "请先选择一张工单"}</span>
        <button class="btn primary big" id="next1" ${pickedTicket() && pickedTicket().status === "ready" ? "" : "disabled"}>查看七要素与原文出处 →</button></div>`;
  }

  // ───────────────────────── 画面 2：七要素与原文出处 ─────────────────────────
  function elementSuggestions(a, name) { return (a.suggestions || []).filter((s) => s.element === name); }

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
        <span class="who">${esc(t.ticket_ref)}</span><span class="muted">${esc(t.title)}</span><span class="sep"></span>
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

  // info 属于“提示”，不挂在“待核实”标题下：kind = "verify"（warning/critical）或 "info"
  function flagsFor(a, name, kind) {
    const list = a.issues.filter((i) => i.element === name && (i.severity === "info") === (kind === "info"));
    if (!list.length) return "";
    const cands = a.elements[name].candidates || [];
    return list.map((i) => {
      let p = ISSUE[i.code] || [i.code, i.message];
      // 候选里已有“已定位的故障点”时，不能再说“没有定位到故障点”
      if (i.code === "LOCATION_NOT_LOCATED" && cands.some((c) => c.role === "located_fault_point")) {
        p = ["候选都是已定位的故障点，只是写法不同", "各处说法指向同一处故障点的不同措辞，系统不擅自合并，所以并列展示、不选边。下方“系统原话”是基线对“没有唯一结论”的通用提示。"];
      }
      const [sev, cls] = SEVERITY[i.severity];
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
    return { left: `<h3>结论</h3>${body}${flagsFor(a, name, "verify") ? `<h3 style="margin-top:16px">待核实</h3>${flagsFor(a, name, "verify")}` : ""}${flagsFor(a, name, "info") ? `<h3 style="margin-top:16px">提示</h3>${flagsFor(a, name, "info")}` : ""}`, refs: [...new Set(refs)] };
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

  // 读 BusinessSuggestion：original.candidates[] 里的 party / description，checks[].status 为 strict / whitespace / mismatch
  function aiPane(a, name, sug) {
    const refs = [];
    const rules = a.run.provider === "rules";
    const items = sug.flatMap((s) => (s.original && Array.isArray(s.original.candidates) ? s.original.candidates : []).map((c, i) => ({ s, c, i })));
    const inner = items.length ? items.map(({ s, c, i }) => {
      (c.evidence_refs || []).forEach((r) => refs.push(r));
      const text = c.party || c.description || "", check = (s.checks || []).find((k) => k.path === `candidates/${i}`);
      const ok = check && check.status !== "mismatch";
      const kind = c.basis ? BASIS[c.basis] : c.role ? ROLE[c.role] : "";
      return `<div class="ai-cand"><div class="c-top"><span class="badge b-ai">AI 建议</span>${rules ? '<span class="sample-tag">示例：规则基线不产生建议，这条是设计稿手写的</span>' : ""}</div>
        <div style="font-weight:600">${esc(text)}</div><div class="muted small">${esc([kind, c.note].filter(Boolean).join("；"))}</div>
        <div class="refs-line">引用出处：${chips(c.evidence_refs || [])} ${ok ? `<span class="badge s-confirmed">✓ 原文核对通过${check.status === "whitespace" ? "（仅空白不同）" : ""}</span>` : '<span class="badge b-warn">⚠ 待核对：这句话在原文里找不到</span>'}</div></div>`;
    }).join("") : rules
      ? `<div class="none-box">规则基线不产生 AI 建议。导入时选择「用模型分析」，才会出现模型给出的建议。</div>`
      : `<div class="none-box">本单模型没有给出${LABEL[name]}的建议。</div>`;
    return { left: `<div class="ai-box"><b>AI 建议，待确认</b><p style="margin:4px 0 0" class="small">这是模型的推测，<b>不是结论</b>：不会写进公司报告，也不会改变上面的“${STATUS[state.data.analysis.elements[name].status].label}”。引用核对只证明那句话在原文里，不证明建议正确。要不要采纳，由 NOC 工作台里的审核人决定。</p></div>${inner}`, refs: [...new Set(refs)] };
  }

  function evidencePane(a, name, refs) {
    const el = a.elements[name];
    const quotes = state.tab === "ai" ? elementSuggestions(a, name).flatMap((s) => (s.checks || []).filter((k) => k.status !== "mismatch")).map((k) => k.quote) : [];
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
    const els = state.data.analysis.elements;
    if (row === 4) return "start_time";
    if (row === 5) return "end_time";
    // 历时算不出来：起障没有可用结论（未知/矛盾）先去发生时间，否则是恢复未确认，去结束时间
    if (row === 6) return els.start_time.value == null ? "start_time" : "end_time";
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
GET /api/tickets/{ref}                     分析结果（未完成时只有状态）
GET /api/tickets/{ref}/company-report.docx 公司报告 Word
GET /api/tickets/{ref}/company-report.html 公司报告网页版
POST /api/tickets                          上传工单包 zip，provider=rules 或 llm</pre>
      <p class="small">页面只吃一种数据：<code>AnalysisResult</code>（<code>schemas/analysis-result.schema.json</code>）。公司报告表格来自同一份结果。工作台只传工单号；新工单用上面的上传接口送进标准工单包。</p>
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
    if (d.pick) {
      state.pick = d.pick;
      if (patchStep1List()) return;
      return render();
    }
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
    if (d.dl) { emit("noc7.report.downloaded", { ticket_ref: state.ref, format: d.dl }); toast("已开始下载公司报告"); return; }
    if (t.id === "review-req") { emit("noc7.review.requested", { ticket_ref: state.ref }); toast(embedded ? "已通知 NOC 工作台打开审核界面" : "独立运行：已发出 noc7.review.requested（当前没有工作台接收）"); return; }
    if (t.id === "open-drawer") return setDrawer(true);
    if (t.id === "close-drawer") return setDrawer(false);
    if (t.id === "sim-wb") { window.postMessage({ type: "noc7.open", ticket_ref: "SYN-S06" }, location.origin); return; }
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
    if (await openTicket(ref, "workbench")) { state.wbError = ""; return go(2); }
    state.wbError = state.pendingNote || `找不到工单 “${ref}”。当前有：${state.tickets.map((t) => t.ticket_ref).join("、")}。`;
    render();
  }

  function listSignature(tickets) {
    return tickets.map((t) => `${t.ticket_ref}:${t.status}:${t.open_issues || 0}`).join("|");
  }
  function ensurePoll() {
    if (state.poll || !state.tickets.some((t) => t.status === "running")) return;
    state.poll = setInterval(async () => {
      try {
        const tickets = await source.list();
        const sig = listSignature(tickets);
        const changed = sig !== state.listSig;
        state.tickets = tickets;
        state.listSig = sig;
        if (changed && state.step === 1 && !patchStep1List()) render();
        if (!tickets.some((t) => t.status === "running")) {
          clearInterval(state.poll);
          state.poll = null;
        }
      } catch (err) { /* 下一轮再试 */ }
    }, 1000);
  }

  document.addEventListener("change", (e) => {
    const input = e.target;
    if (!input || input.name !== "provider" || !input.form || input.form.id !== "import-form") return;
    state.importProvider = input.value === "llm" ? "llm" : "rules";
  });

  document.addEventListener("submit", async (e) => {
    const form = e.target;
    if (!form || form.id !== "import-form") return;
    e.preventDefault();
    const file = form.querySelector("#import-file").files[0];
    if (!file) { state.importError = "请选择一个 zip 工单包"; render(); return; }
    const provider = state.importProvider === "llm" ? "llm" : "rules";
    const body = new FormData();
    body.append("bundle", file, file.name);
    body.append("provider", provider);
    let payload = {};
    let res;
    try {
      res = await fetch("/api/tickets", { method: "POST", body });
      payload = await res.json();
    } catch (err) {
      state.importError = "导入请求没有完成";
      render();
      return;
    }
    if (!res.ok) {
      state.importError = (payload.problems || ["导入没有成功"]).join("；");
      render();
      return;
    }
    state.importError = "";
    state.pick = payload.ticket_ref;
    state.pendingNote = "";
    state.tickets = await source.list();
    state.listSig = listSignature(state.tickets);
    ensurePoll();
    render();
  });

  // ───────────────────────── 启动 ─────────────────────────
  // 地址里的 ?ticket= 或 #/步骤/工单号/要素/标签 → 页面状态。工作台改 hash 时也走这里（replaceState 不触发它）。
  async function applyLocation() {
    const q = new URLSearchParams(location.search);
    const m = location.hash.match(/^#\/(\d)\/([^/]*)\/?([^/]*)\/?([^/]*)/);
    const ref = q.get("ticket") || (m && m[2]) || "";
    if (ref && (await openTicket(ref, "link"))) {
      state.step = q.get("ticket") && !m ? 2 : Math.min(+m[1], 3) || 2;
      if (m && ELEMENTS.includes(m[3])) state.element = m[3];
      if (m && ["cands", "ai"].includes(m[4])) state.tab = m[4];
    }
    render();
  }
  async function init() {
    if (new URLSearchParams(location.search).get("embed") === "1") document.body.classList.add("embed");
    const catalog = await source.catalog();
    LABEL = catalog.element_labels;
    ELEMENTS = Object.keys(LABEL);
    state.element = ELEMENTS[0] || "start_time";
    state.workbenchOrigins = catalog.workbench_origins || [];
    state.tickets = catalog.tickets;
    state.listSig = listSignature(state.tickets);
    ensurePoll();
    await applyLocation();
    window.addEventListener("hashchange", applyLocation);
  }
  init();
})();
