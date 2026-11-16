/* 分析过程演示：把一次分析的真实数据（/api/tickets/<ref>/trace + 分析结果）按五步分页播放。
   只为演示后端逻辑；实际工作时不打开它，分析照样在后台跑。
   - 动画由一个“场景时钟”驱动：元素带 data-at（毫秒），时钟走到就显现；暂停就是时钟停走。
   - 带 data-d 的东西都能点：点了就暂停，右侧详情面板讲清它是什么、从哪来、规则怎么用它。
   - 自动挑一条“线索”（一个已取值的要素），五步里一路高亮，看结论从哪来。 */
(function () {
  "use strict";

  const STAGES = [
    { name: "拆工单包", lead: "读出工单包里的每份材料，交给对应的解析器（点任一份看它是什么）" },
    { name: "原文编号", lead: "原文切成带编号的片段：模型只看这些，引用时必须写编号（点编号看原文）" },
    { name: "模型摘录", lead: "模型只摘事实、必须带原文引文，不做取舍；本地逐条核对引文（点事实看对照）" },
    { name: "本地规则", lead: "本地规则按依据强弱给七要素取值，淘汰的候选写明原因；拿不准就留空或标待核实（点要素看裁决）" },
    { name: "生成报告", lead: "七要素写进公司报告，每个结论都能点回原文" },
  ];
  const KIND = { ticket_fields: "工单字段", process_log: "处理过程", email_html: "邮件", email_eml: "邮件", image: "图片", pdf: "PDF", docx: "Word", text: "文本", other: "其他" };
  const KIND_ICON = { ticket_fields: "▤", process_log: "☰", email_html: "✉", email_eml: "✉", image: "▣", pdf: "▧", docx: "▥", text: "¶", other: "?" };
  const KIND_HELP = {
    ticket_fields: "工单系统里的结构化字段（客户、电路、建单时间、故障描述等），每个字段切成一段，编号形如 M01/f:字段名。",
    process_log: "工单的处理过程，一条记录一段，编号形如 M16/log:序号。",
    email_html: "邮件正文，按封切段。", email_eml: "邮件原件，按封切段。",
    image: "图片附件：在本机用 OCR 识别出文字，截图本身不发给模型。", pdf: "PDF 附件：按页取文字，扫描件在本机 OCR。",
    docx: "Word 附件：按段落和表格取文字。",
    text: "导出时整理成纯文本的材料（如追单记录、邮件转写），按行切段，编号形如 M04/t:行号。",
    other: "格式不在解析范围内。系统不猜它的内容，不交给模型，只在核对报告的“材料完整性”里列出，提醒人工看。",
  };
  const PARSE = { parsed: "已解析", needs_review: "解析了，质量存疑", failed: "解析失败", unsupported: "格式不支持，已标出", pending: "未解析" };
  const FACT = { start_time: "发生时间", recovery_time: "恢复时间", alarm_clear: "告警清除", phenomenon: "故障现象", cause: "故障原因", responsibility: "责任方",
    fault_location: "故障地点", location: "故障地点", step: "处理步骤", service_recovered: "业务恢复", customer_followup: "客户追问",
    customer_device_fault: "客户侧设备", self_check: "客户自查", vendor_onsite: "供应商上门", unicom_onsite: "联通上门", not_fault: "不是故障", other: "其他" };
  // 各要素怎么取值（与使用说明“第 4 步”一致）
  const RULE_HELP = {
    start_time: "起点按依据强弱取：客户报告的开始时刻、业务记载 → 告警产生 → 工单系统“发生时间”字段兜底（标待核实）。客户报告早于系统字段时采用客户时刻。",
    end_time: "恢复时间按依据强弱取：客户、供应商 RFO、联通日志写明的业务恢复 → 按北京时间推定 → 告警清除 → 客户确认 → 工单系统恢复字段兜底。几个合格时间相差不大时取最早的。协议 Up、修复完成、结单时间都不算恢复。",
    phenomenon: "故障现象照录原文里客户和监控看到的异常（中断、丢包、时延等），多条并列。",
    responsible_party: "责任方：原文明确写的 → 按 RFO 原因或割接通知推定 → 原文写“怀疑”的。供应商所说的故障时刻和本次中断对不上的不作依据；原文明确否定的不会被兜底成该方；工单系统“故障区域”字段不作依据。",
    cause: "原因要的是根因：RFO、供应商反馈、分公司反馈里明确说明的原因优先；排查过程、“未发现异常”、恢复方式都不算根因；只是怀疑的标出来。",
    handling_process: "处理过程按时间排列实际处理动作和关键沟通；签收、转派、挂起、结单等流程流转不算。",
    location: "故障地点：城市 → 省州 → 线路段（两端地名）→ 国家 → 工单系统故障地址字段兜底。只写站点、距离或坐标的留空。业务两端地址、告警设备位置不算故障点。",
  };
  const THREAD_ORDER = ["end_time", "start_time", "cause", "responsible_party", "location"];

  function create(deps) {
    const { esc, LABEL, ELEMENTS, STATUS, ATTR, valueText, candText, candKind, spanLabel, highlight, fetchDetail, jobOf, onOpen } = deps;
    const root = document.createElement("div");
    root.className = "proc";
    root.hidden = true;
    root.setAttribute("role", "dialog");
    root.setAttribute("aria-modal", "true");
    root.setAttribute("aria-label", "分析过程");
    root.innerHTML = `<div class="p-main"></div><aside class="p-panel" aria-label="详情"></aside>`;
    document.body.appendChild(root);
    const main = root.querySelector(".p-main");
    const panel = root.querySelector(".p-panel");

    const s = { ref: null, trace: null, analysis: null, idx: null, thread: null, stage: 0, clock: 0, playing: true, speed: 1,
      end: 0, raf: 0, last: 0, wait: null, hold: 0, panel: [], auto: false };  // auto：本步播完后自动翻到下一步（默认关，手动翻）

    // ── 打开、等待、关闭 ──
    async function open(ref, { waiting = false } = {}) {
      stop();
      Object.assign(s, { ref, trace: null, analysis: null, idx: null, thread: null, stage: 0, clock: 0, playing: true, hold: 0, panel: [] });
      closePanel();
      root.hidden = false;
      document.body.classList.add("proc-open");
      if (waiting) return waitFor(ref);
      return load(ref);
    }
    function close() {
      stop();
      closePanel();
      root.hidden = true;
      document.body.classList.remove("proc-open");
      s.ref = null;
    }
    function stop() {
      cancelAnimationFrame(s.raf); s.raf = 0;
      clearInterval(s.wait); s.wait = null;
    }
    function waitFor(ref) {
      const began = Date.now();
      const job = jobOf(ref) || {};
      const live = job.mode === "live";
      const paint = () => {
        const sec = Math.floor((Date.now() - began) / 1000);
        main.innerHTML = frame(`<div class="p-wait">
          <div class="p-orbit"><span></span><span></span><span></span></div>
          <h2>${live ? `正在请求 ${esc(shortLabel(job.model_label))}` : "正在回放保存的模型结果"}</h2>
          <p>${live ? "实时调用模型通常一两分钟，期间后端在拆包、编号、等模型回复。" : "回放不联网，读取以前保存的模型回复，再完整走一遍本地规则。"}</p>
          <p class="p-big mono">${sec}s</p></div>`, true);
      };
      paint();
      s.wait = setInterval(() => {
        const j = jobOf(ref);
        if (j && j.status === "ready") { clearInterval(s.wait); s.wait = null; load(ref); return; }
        if (j && j.status === "failed") {
          clearInterval(s.wait); s.wait = null;
          main.innerHTML = frame(`<div class="p-wait"><h2>分析没有完成</h2><p class="p-err">${esc((j.problems || []).join("；"))}</p></div>`, true);
          return;
        }
        paint();
      }, 500);
    }
    async function load(ref) {
      const [traceRes, detail] = await Promise.all([fetch(`/api/tickets/${encodeURIComponent(ref)}/trace`), fetchDetail(ref)]);
      if (s.ref !== ref) return;
      if (!traceRes.ok || !detail || detail.status !== "ready") {
        main.innerHTML = frame(`<div class="p-wait"><h2>没有过程记录</h2><p>这次结果是旧版操作台留下的，没有记录过程。点卡片上的“回放”重新跑一次就有了。</p></div>`, true);
        return;
      }
      s.trace = await traceRes.json();
      s.analysis = detail.analysis;
      s.idx = buildIndex(s.trace, s.analysis);
      s.thread = pickThread();
      goStage(0);
    }

    // ── 索引与线索 ──
    function buildIndex(tr, a) {
      const span = new Map(a.evidence.map((e) => [e.id, e]));
      const mat = new Map(a.materials.map((m) => [m.id, m]));
      const sent = new Set(tr.model.evidence.map((e) => e.id));
      const factsByEv = new Map();
      tr.model.facts_kept.forEach((f, i) => { if (!factsByEv.has(f.evidence_id)) factsByEv.set(f.evidence_id, []); factsByEv.get(f.evidence_id).push(i); });
      const elemsByEv = new Map();
      ELEMENTS.forEach((n) => {
        const el = a.elements[n];
        const refs = new Set([...(el.evidence_refs || []), ...(el.candidates || []).flatMap((c) => c.evidence_refs || [])]);
        refs.forEach((r) => { if (!elemsByEv.has(r)) elemsByEv.set(r, []); elemsByEv.get(r).push(n); });
      });
      return { span, mat, sent, factsByEv, elemsByEv };
    }
    // 一条线索 = 一个要素被采用的候选及其原文出处；能追溯到原文的要素都可以选
    function makeThread(name) {
      const el = s.analysis.elements[name];
      if (!el) return null;
      const c = el.selected ? (el.candidates || []).find((x) => x.id === el.selected) : null;
      const refs = (c ? c.evidence_refs || [] : el.evidence_refs || []).filter((r) => s.idx.span.has(r));
      if (!refs.length) return null;
      const facts = new Set(refs.flatMap((r) => s.idx.factsByEv.get(r) || []));
      return { element: name, cand: c, evs: new Set(refs), mats: new Set(refs.map((r) => r.split("/")[0])), facts,
        value: valueText(name, el) || (c ? candText(name, c) : "") };
    }
    function threadChoices() { return ELEMENTS.filter((n) => makeThread(n)); }
    function pickThread() {
      for (const name of [...THREAD_ORDER, ...ELEMENTS]) { const t = makeThread(name); if (t) return t; }
      return null;
    }
    function setThread(name) {
      const t = makeThread(name);
      if (!t) return;
      s.thread = t;
      const clock = s.clock;
      const scene = SCENES[s.stage]();
      s.end = scene.end;
      main.innerHTML = frame(scene.html);
      if (scene.after) scene.after();
      s.clock = Math.min(clock, s.end);
      apply();
      if (s.panel.length) openPanel(s.panel[s.panel.length - 1], false);
    }
    const th = {
      mat: (id) => !!(s.thread && s.thread.mats.has(id)),
      ev: (id) => !!(s.thread && s.thread.evs.has(id)),
      fact: (i) => !!(s.thread && s.thread.facts.has(i)),
      el: (n) => !!(s.thread && s.thread.element === n),
    };

    // ── 场景时钟 ──
    function goStage(i) {
      s.stage = Math.max(0, Math.min(STAGES.length - 1, i));
      s.clock = 0; s.hold = 0;
      const scene = SCENES[s.stage]();
      s.end = scene.end;
      main.innerHTML = frame(scene.html);
      if (scene.after) scene.after();
      cancelAnimationFrame(s.raf);
      s.last = performance.now();
      s.raf = requestAnimationFrame(tick);
      apply();
    }
    function tick(now) {
      const dt = Math.min(100, now - s.last);
      s.last = now;
      if (s.playing) {
        if (s.clock < s.end) s.clock = Math.min(s.end, s.clock + dt * s.speed);
        else if (s.auto && s.stage < STAGES.length - 1) {
          s.hold += dt * s.speed;
          if (s.hold > 1400) { goStage(s.stage + 1); return; }
        }
        apply();
      }
      s.raf = requestAnimationFrame(tick);
    }
    function apply() {
      const t = s.clock;
      main.querySelectorAll("[data-at]").forEach((el) => {
        const on = t >= +el.dataset.at;
        if (on !== el.classList.contains("in")) el.classList.toggle("in", on);
      });
      main.querySelectorAll("[data-type]").forEach((el) => {
        const at = +el.dataset.at || 0, dur = +el.dataset.dur || 1;
        const full = el.dataset.full ?? (el.dataset.full = el.textContent);
        const n = Math.round(full.length * Math.max(0, Math.min(1, (t - at) / dur)));
        if (el._n !== n) { el._n = n; el.textContent = full.slice(0, n); el.scrollTop = el.scrollHeight; }
      });
      main.querySelectorAll("[data-count]").forEach((el) => {
        const at = +el.dataset.at || 0, dur = +el.dataset.dur || 800, to = +el.dataset.count;
        const v = Math.round(to * Math.max(0, Math.min(1, (t - at) / dur)));
        if (el._v !== v) { el._v = v; el.textContent = v; }
      });
      main.querySelectorAll("[data-grow]").forEach((el) => {
        const at = +el.dataset.at || 0, dur = +el.dataset.dur || 800;
        el.style.width = (+el.dataset.grow * Math.max(0, Math.min(1, (t - at) / dur))).toFixed(1) + "%";
      });
      const wall = main.querySelector(".p-evwall");
      if (wall && s.playing) {
        const ins = wall.querySelectorAll(".p-ev.in");
        const lastIn = ins[ins.length - 1];
        if (lastIn && lastIn !== wall._last) { wall._last = lastIn; wall.scrollTop = Math.max(0, lastIn.offsetTop - wall.offsetTop - wall.clientHeight + lastIn.offsetHeight + 6); }
      }
      drawWires();
      const bar = main.querySelector(".p-progress span");
      if (bar) bar.style.width = (s.end ? Math.min(100, (s.clock / s.end) * 100) : 100).toFixed(1) + "%";
      const done = s.end > 0 && s.clock >= s.end;
      const play = main.querySelector("[data-p=play]");
      if (play) play.textContent = done ? "↻ 重播本步" : s.playing ? "⏸ 暂停" : "▶ 继续";
      const next = main.querySelector("[data-p=next]");
      if (next) next.classList.toggle("ready", done && !s.auto);
    }
    // 模型摘录：每条事实出现时，从模型回复画一条发光连线过去
    function drawWires() {
      const box = main.querySelector(".p-split");
      const svg = box && box.querySelector("svg.p-wires");
      if (!svg) return;
      const terms = box.querySelectorAll(".p-pass.in .p-term");
      const from = terms[terms.length - 1] || box.querySelector(".p-col.src");
      box.querySelectorAll(".p-fact.in:not([data-wired])").forEach((card) => {
        const b = box.getBoundingClientRect(), f = from.getBoundingClientRect(), c = card.getBoundingClientRect();
        if (!c.height) return;
        card.dataset.wired = "1";
        // 都从最近那遍回复的右缘中点发出，扇形连到每条事实
        const x1 = f.right - b.left, y1 = f.top - b.top + f.height / 2;
        const x2 = c.left - b.left, y2 = c.top - b.top + c.height / 2;
        const mx = (x1 + x2) / 2;
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`);
        path.setAttribute("class", `wire ${card.classList.contains("thread") ? "thread" : ""} ${card.classList.contains("drop") ? "drop" : ""}`);
        svg.appendChild(path);
      });
    }

    // 布局变了（打开/关闭详情面板、窗口缩放）就按新位置重画连线
    function redrawWires() {
      const svg = main.querySelector("svg.p-wires");
      if (!svg) return;
      svg.innerHTML = "";
      main.querySelectorAll(".p-fact[data-wired]").forEach((c) => delete c.dataset.wired);
      drawWires();
    }
    window.addEventListener("resize", redrawWires);

    // ── 外框：标题、五步、线索条、控制条 ──
    function frame(body, bare) {
      const tr = s.trace;
      const job = jobOf(s.ref) || {};
      const title = (tr && tr.ticket && tr.ticket.title) || job.title || s.ref || "";
      const mode = tr ? tr.mode : job.mode;
      const chip = mode === "live" ? `实时调用 · ${esc(shortLabel(tr ? tr.model_label : job.model_label))}` : "回放 · 不联网";
      const steps = STAGES.map((st, i) => `<button type="button" class="p-step ${i === s.stage && !bare ? "on" : ""} ${i < s.stage && !bare ? "done" : ""}" data-p-stage="${i}" ${bare ? "disabled" : ""}>
          <span class="n">${i + 1}</span>${st.name}</button>`).join("");
      const st = STAGES[s.stage];
      const opts = !bare && s.thread ? threadChoices().map((n) => `<option value="${esc(n)}" ${n === s.thread.element ? "selected" : ""}>${esc(LABEL[n])}</option>`).join("") : "";
      const thread = !bare && s.thread ? `<div class="p-thread"><span class="torch">◉</span>跟着一条线索：<select class="p-pick" data-thread aria-label="选择线索要素">${opts}</select> = <span class="v">${esc(short(s.thread.value || "", 40))}</span>
          <span class="muted">（发光的就是它，一路从材料走到报告；下拉可换要素）</span><button type="button" class="p-link" data-d="el:${esc(s.thread.element)}">看它的来龙去脉 →</button></div>` : "";
      return `<div class="p-shell">
        <header class="p-head">
          <div class="p-title"><small>分析过程演示</small><b title="${esc(title)}">${esc(title)}</b></div>
          <span class="p-chip ${mode === "live" ? "live" : ""}">${chip}</span>
          <button type="button" class="p-x" data-p="close" aria-label="关闭">✕</button></header>
        <nav class="p-steps">${steps}</nav>
        ${bare ? "" : `<div class="p-lead"><b>${s.stage + 1} · ${st.name}</b>${st.lead}</div>`}
        ${thread}
        <section class="p-stage">${body}</section>
        ${bare ? "" : `<footer class="p-ctrl">
          <button type="button" class="p-btn" data-p="prev" ${s.stage === 0 ? "disabled" : ""}>⏮ 上一步</button>
          <button type="button" class="p-btn main" data-p="play">⏸ 暂停</button>
          <button type="button" class="p-btn" data-p="next" ${s.stage === STAGES.length - 1 ? "disabled" : ""}>下一步 ⏭</button>
          <div class="p-progress"><span></span></div>
          <button type="button" class="p-btn" data-p="speed">${s.speed}×</button>
          <button type="button" class="p-btn ${s.auto ? "on" : ""}" data-p="auto" aria-pressed="${s.auto}">自动翻步：${s.auto ? "开" : "关"}</button>
          <span class="p-keys">点任何一项看详情 · 空格 暂停 · → 下一步 · Esc 关闭</span></footer>`}</div>`;
    }

    // ── 五个场景：每个返回 html 和时长（毫秒，1× 速度） ──
    const SCENES = [sceneBundle, sceneEvidence, sceneModel, sceneRules, sceneReport];

    function sceneBundle() {
      const ms = s.trace.materials;
      const step = Math.max(160, Math.min(380, 3600 / Math.max(1, ms.length)));
      const tiles = ms.map((m, i) => {
        const at = 300 + i * step;
        const bad = m.parse_status === "unsupported" || m.parse_status === "failed";
        return `<button type="button" class="p-tile ${bad ? "bad" : ""} ${m.ocr ? "ocr" : ""} ${th.mat(m.id) ? "thread" : ""}" data-at="${at}" data-d="mat:${esc(m.id)}">
          <span class="ic">${KIND_ICON[m.kind] || "?"}</span>
          <b>${esc(KIND[m.kind] || m.kind)}</b><small class="mono">${esc(m.id)}</small>
          ${m.ocr ? `<i class="scan" data-at="${at + 150}"></i><em data-at="${at + 150}">本地 OCR 识别文字</em>` : ""}
          <div class="out" data-at="${at + 260}">${bad ? esc(PARSE[m.parse_status]) : `→ <b>${m.spans}</b> 段原文`}</div>
          ${th.mat(m.id) ? `<span class="tag">线索在这里</span>` : ""}</button>`;
      }).join("");
      const t = 300 + ms.length * step + 300;
      const byKind = {};
      ms.forEach((m) => { const k = KIND[m.kind] || m.kind; byKind[k] = (byKind[k] || 0) + 1; });
      return {
        end: t + 1200,
        html: `<div class="p-bundle">
          <div class="p-left">
            <div class="p-pack" data-at="0"><span class="ic">📦</span><b>工单包</b><small>${ms.length} 份材料 · 带哈希清单，先核对完整性</small>
              <div class="kinds">${Object.entries(byKind).map(([k, n]) => `<span>${esc(k)} ${n}</span>`).join("")}</div></div>
            <div class="p-total" data-at="${t}">共得到<b class="mono" data-count="${s.trace.spans}" data-at="${t}" data-dur="900">0</b>段可定位的原文
              <small>附件里的图片在本机 OCR，不把截图发给模型</small></div></div>
          <div class="p-tiles">${tiles}</div></div>`,
      };
    }

    function sceneEvidence() {
      const m = s.trace.model;
      const ev = m.evidence;
      const groups = {};
      ev.forEach((e) => { const k = KIND[e.kind] || "其他"; groups[k] = (groups[k] || 0) + 1; });
      const max = Math.max(1, ...Object.values(groups));
      const bars = Object.entries(groups).sort((a, b) => b[1] - a[1]).map(([k, n], i) => `<div class="p-barrow" data-at="${200 + i * 200}">
          <span>${esc(k)}</span><div class="p-bar"><i data-grow="${(n / max) * 100}" data-at="${300 + i * 200}" data-dur="1000"></i></div><b class="mono">${n}</b></div>`).join("");
      const shown = ev;  // 全部列出，片段墙可以滚动
      const gap = Math.max(18, Math.min(45, 4200 / Math.max(1, shown.length)));
      const chips = shown.map((e, i) => `<button type="button" class="p-ev k-${esc(e.kind)} ${th.ev(e.id) ? "thread" : ""}" data-at="${400 + i * gap}" data-d="ev:${esc(e.id)}" title="${esc(e.text)}">${esc(e.id)}</button>`).join("");
      const more = ev.length > shown.length ? `<span class="p-ev more" data-at="${400 + shown.length * gap}">+${m.sent - shown.length}</span>` : "";
      const threadEv = ev.find((e) => th.ev(e.id));
      const samples = pickSamples(ev.filter((e) => e !== threadEv), threadEv ? 4 : 5);
      if (threadEv) samples.push(threadEv);
      const t = 400 + shown.length * gap + 300;
      const lines = samples.map((e, i) => `<button type="button" class="p-line ${th.ev(e.id) ? "thread" : ""}" data-at="${t + i * 380}" data-d="ev:${esc(e.id)}"><span class="mono id">${esc(e.id)}</span><span>${esc(e.text)}</span></button>`).join("");
      return {
        end: t + samples.length * 380 + 1400,
        html: `<div class="p-evidence">
          <div class="p-col"><h3>按来源</h3>${bars}
            <div class="p-note" data-at="400">编号规则：<span class="mono">材料/位置</span>，如 <span class="mono">M02/log:5</span> 是第 2 份材料“处理过程”第 5 条。模型引用时必须写编号，本地据此逐字核对。</div></div>
          <div class="p-col wide"><h3>发给模型的片段 <b class="mono" data-count="${m.sent}" data-at="400" data-dur="${shown.length * gap}">0</b> 条 · ${m.request_kb} KB</h3>
            <div class="p-evwall">${chips}${more}</div>
            <div class="p-lines">${lines}</div></div></div>`,
      };
    }

    function sceneModel() {
      const m = s.trace.model;
      const live = s.trace.mode === "live";
      const passes = m.passes.length ? m.passes : [""];
      let t = 2600;
      const term = passes.map((raw, i) => {
        const show = raw.slice(0, 900);
        const dur = Math.max(1200, show.length * 3);
        const html = `<div class="p-pass" data-at="${t - 200}"><div class="p-pass-h">第 ${i + 1} 遍${i ? "（复核：补漏）" : "（摘录事实）"}${live ? "" : " · 读取保存的原始回复"}</div>
          <pre class="p-term mono" data-type="1" data-at="${t}" data-dur="${dur}">${esc(show || "（这份记录只保存了核对后的事实）")}${raw.length > 900 ? "\n…" : ""}</pre></div>`;
        t += dur + 500;
        return html;
      }).join("");
      // 线索相关的事实排在前面，保证露面
      const order = m.facts_kept.map((f, i) => i).sort((a, b) => (th.fact(b) ? 1 : 0) - (th.fact(a) ? 1 : 0)).slice(0, 9);
      const ft = t;
      const cards = order.map((fi, k) => {
        const f = m.facts_kept[fi];
        return `<button type="button" class="p-fact ${th.fact(fi) ? "thread" : ""}" data-at="${ft + k * 420}" data-d="fact:${fi}">
          <span class="ft">${esc(FACT[f.type] || f.type)}</span>
          <q>${esc(f.quote)}</q>
          <span class="ok" data-at="${ft + k * 420 + 260}">✓ 引文逐字在原文里 → <span class="mono">${esc(f.evidence_id)}</span></span></button>`;
      }).join("");
      const dropped = m.facts_dropped.slice(0, 3).map((f, i) => `<button type="button" class="p-fact drop" data-at="${ft + (order.length + i) * 420}" data-d="drop:${i}">
          <span class="ft">${esc(FACT[f.type] || f.type)}</span><q>${esc(f.quote)}</q>
          <span class="no">✗ 丢弃：${esc(f.reason || "引文对不上原文")}</span></button>`).join("");
      const end = ft + (order.length + Math.min(3, m.facts_dropped.length)) * 420;
      const usage = m.usage.reduce((a, u) => a + (+u.total_tokens || 0), 0);
      return {
        end: end + 1600,
        html: `<div class="p-model">
          <div class="p-wire">
            <div class="p-node" data-at="0"><b class="mono">${m.sent}</b> 条片段<small>${m.request_kb} KB · 不含截图</small></div>
            <div class="p-pipe" data-at="300"><i></i><i></i><i></i><i></i><span>${live ? "HTTPS 请求" : "不联网"}</span></div>
            <div class="p-node brain" data-at="700"><b>${live ? esc(shortLabel(s.trace.model_label)) : "保存的模型回复"}</b><small>${live ? `${m.attempts} 次请求${usage ? ` · ${usage} tokens` : ""}` : esc(providerModel(s.trace.provider))}</small></div>
            <div class="p-pipe back" data-at="1300"><i></i><i></i><i></i><i></i><span>${passes.length} 遍回复</span></div>
            <div class="p-node" data-at="1700"><b class="mono" data-count="${m.facts_kept.length}" data-at="${ft}" data-dur="${Math.max(400, order.length * 420)}">0</b> 条事实<small>丢弃 ${m.facts_dropped.length} 条</small></div></div>
          <div class="p-split"><svg class="p-wires" aria-hidden="true"></svg>
            <div class="p-col src">
              <button type="button" class="p-task" data-at="1900" data-d="prompt">
                <b>模型的任务</b>
                <span>① 只摘给出的片段里写明的内容，不用常识补</span>
                <span>② 每条事实必须带证据编号 + 逐字引文</span>
                <span>③ 不做取舍、不下结论，取舍交给本地规则</span>
                <span>④ 第 2 遍复核：找回漏摘的责任、恢复时间、地点</span>
                <em>看提示词原文 →</em></button>
              ${term}</div>
            <div class="p-col"><h3>本地逐条核对引文</h3>${cards}${dropped}
              ${m.facts_kept.length > order.length ? `<div class="p-note" data-at="${end}">还有 ${m.facts_kept.length - order.length} 条事实，同样都核对过。</div>` : ""}</div></div></div>`,
      };
    }

    function sceneRules() {
      const a = s.analysis;
      const rows = s.trace.rules.map((r, i) => {
        const at = 400 + i * 1100;
        const el = a.elements[r.element];
        const v = valueText(r.element, el);
        const issue = r.issues.find((x) => x.severity !== "info");
        const cands = el.candidates || [];
        const pills = cands.slice(0, 6).map((c) => {
          const keep = el.selected ? c.id === el.selected : el.status !== "unknown";
          return `<span class="pill ${keep ? "sel" : ""}" title="${esc(candText(r.element, c))}">${esc(c.id)}</span>`;
        }).join("") + (cands.length > 6 ? `<span class="pill more">+${cands.length - 6}</span>` : "");
        return `<button type="button" class="p-rule ${th.el(r.element) ? "thread" : ""}" data-at="${at}" data-d="el:${esc(r.element)}">
          <b class="lbl">${esc(LABEL[r.element] || r.element)}</b>
          <span class="p-pills" data-at="${at + 200}"><span class="cnt">候选 ${r.candidates}</span>${pills}<i class="decide" data-at="${at + 650}"></i></span>
          <span class="gear" data-at="${at + 350}">⚙ 核引文 · 比依据 · 查冲突</span>
          <span class="res" data-at="${at + 750}">${badge(r.after)}${v ? `<span class="val" title="${esc(v)}">${esc(v)}</span>` : `<span class="val muted">留空，不猜</span>`}</span>
          ${issue ? `<span class="iss" data-at="${at + 900}" title="${esc(issue.message)}">【待核实】${esc(issue.message)}</span>` : `<span class="iss ok" data-at="${at + 900}">${r.after === "unknown" ? "" : "依据充分"}</span>`}</button>`;
      }).join("");
      const end = 400 + s.trace.rules.length * 1100 + 600;
      return {
        end: end + 1200,
        html: `<div class="p-rules">
          <div class="p-ladder" data-at="0">取值顺序：<span>客户确认 / RFO</span>›<span>处理日志明确记载</span>›<span>按北京时间推定</span>›<span>告警</span>›<span>工单系统字段兜底（标待核实）</span></div>
          ${rows}
          <div class="p-note" data-at="${end}">规则版本 ${esc(s.trace.rules_version || "")}：模型只给候选和引文，取哪一条、淘汰哪一条、标不标待核实，全由这里的规则决定。点一行看每个候选的去留理由。</div></div>`,
      };
    }

    function sceneReport() {
      const a = s.analysis;
      const c = { confirmed: 0, documented: 0, unknown: 0, conflicted: 0 };
      ELEMENTS.forEach((n) => { c[a.elements[n].status] = (c[a.elements[n].status] || 0) + 1; });
      const open = a.issues.filter((i) => i.severity !== "info").length;
      const dots = ELEMENTS.map((n, i) => `<button type="button" class="p-dot ${th.el(n) ? "thread" : ""}" data-at="${200 + i * 220}" data-d="el:${esc(n)}"><span class="dot ${esc(a.elements[n].status)}"></span><small>${esc(LABEL[n])}</small></button>`).join("");
      const m = s.trace.model;
      const narr = m.narrative === "accepted" ? (m.narrative_replaced ? "模型写了叙述，本地核验时有不符的句子，已改回本地拼接" : "模型写了叙述，本地逐句核验通过")
        : m.narrative ? "叙述没有采用模型的，用本地拼接" : "叙述由本地拼接";
      const sec = s.trace.elapsed_seconds;
      const t = 200 + ELEMENTS.length * 220 + 200;
      const ref = encodeURIComponent(s.ref);
      return {
        end: t + 2200,
        after: loadReport,
        html: `<div class="p-report">
          <div class="p-sum">
          <div class="p-dots">${dots}</div>
          <div class="p-stats" data-at="${t}">
            <div><b class="mono" data-count="${c.confirmed + c.documented}" data-at="${t}">0</b><small>项有结论</small></div>
            <div><b class="mono" data-count="${c.unknown}" data-at="${t}">0</b><small>项留空</small></div>
            <div class="warn"><b class="mono" data-count="${open}" data-at="${t}">0</b><small>处待核实</small></div>
            <div><b class="mono">${sec < 10 ? sec.toFixed(1) : Math.round(sec)}</b><small>秒 · ${s.trace.mode === "live" ? "含等待模型" : "回放不联网"}</small></div></div>
          <p class="p-note" data-at="${t + 500}">成文：${esc(narr)}。</p>
          <div class="p-actions" data-at="${t + 900}">
            <button type="button" class="p-btn main" data-p="open">查看七要素与原文出处</button>
            <button type="button" class="p-btn" data-p="report">公司报告</button>
            <a class="p-btn" href="/api/tickets/${ref}/company-report.docx" download>下载 Word</a>
            <button type="button" class="p-btn" data-p="again">从头再放</button></div></div>
          <div class="p-paper" data-at="${t + 300}">
            <div class="p-paper-h"><b>公司报告预览</b><small>与下载的 Word 同源生成 · 草稿，签字栏留空</small></div>
            <iframe class="p-frame" title="公司报告预览" sandbox="" referrerpolicy="no-referrer"></iframe>
            <div class="p-paper-wait">正在取报告…</div></div></div>`,
      };
    }
    // 报告是这张单输出目录里的 company_report.html；按下载接口取回文字，放进沙箱 iframe（不跑脚本）
    async function loadReport() {
      const ref = s.ref;
      if (s.reportHtml == null || s.reportRef !== ref) {
        const res = await fetch(`/api/tickets/${encodeURIComponent(ref)}/company-report.html`);
        if (s.ref !== ref) return;
        let html = res.ok ? await res.text() : "";
        // 报告用相对路径引用同目录的 report.css；沙箱里不一定按 base 去取，直接内联进来
        const css = html ? await fetch(`/api/tickets/${encodeURIComponent(ref)}/report.css`).then((r) => (r.ok ? r.text() : "")) : "";
        if (s.ref !== ref) return;
        if (css) html = html.replace(/<link[^>]*href="report\.css"[^>]*>/i, () => `<style>${css.replace(/<\/style/gi, "<\\/style")}</style>`);
        s.reportRef = ref;
        s.reportHtml = html;
      }
      const frame = main.querySelector(".p-frame");
      if (!frame) return;
      const wait = main.querySelector(".p-paper-wait");
      if (!s.reportHtml) { if (wait) wait.textContent = "这张单还没有公司报告。"; return; }
      const base = `<base href="${location.origin}/api/tickets/${encodeURIComponent(ref)}/">`;
      frame.srcdoc = s.reportHtml.replace(/<head>/i, `<head>${base}`);
      frame.addEventListener("load", () => { if (wait) wait.remove(); }, { once: true });
    }

    // ── 右侧详情面板 ──
    function openPanel(key, push = true) {
      const html = detail(key);
      if (html == null) return;
      if (push) s.panel.push(key);
      s.playing = false;
      apply();
      panel.innerHTML = `<div class="pp-head">
          <button type="button" class="p-btn" data-pp="back" ${s.panel.length > 1 ? "" : "disabled"}>← 返回</button>
          <span class="pp-crumb">${s.panel.length > 1 ? `第 ${s.panel.length} 层` : ""}</span>
          <button type="button" class="p-x" data-pp="close" aria-label="关闭详情">✕</button></div>
        <div class="pp-body">${html}</div>`;
      if (!root.classList.contains("panel-open")) setTimeout(redrawWires, 420);
      root.classList.add("panel-open");
      panel.scrollTop = 0;
    }
    function closePanel() {
      s.panel = [];
      if (root.classList.contains("panel-open")) setTimeout(redrawWires, 420);
      root.classList.remove("panel-open");
      panel.innerHTML = "";
    }
    function detail(key) {
      const i = key.indexOf(":");
      const kind = i < 0 ? key : key.slice(0, i), id = i < 0 ? "" : key.slice(i + 1);
      if (kind === "mat") return matDetail(id);
      if (kind === "ev") return evDetail(id);
      if (kind === "fact") return factDetail(+id);
      if (kind === "drop") return dropDetail(+id);
      if (kind === "el") return elDetail(id);
      if (kind === "prompt") return promptDetail();
      return null;
    }
    const evChip = (id) => `<button type="button" class="pp-chip mono ${th.ev(id) ? "thread" : ""}" data-d="ev:${esc(id)}">${esc(id)}</button>`;
    const elChip = (n) => `<button type="button" class="pp-chip ${th.el(n) ? "thread" : ""}" data-d="el:${esc(n)}">${esc(LABEL[n] || n)}</button>`;

    function matDetail(id) {
      const m = s.idx.mat.get(id);
      const tm = s.trace.materials.find((x) => x.id === id) || {};
      if (!m) return null;
      const spans = s.analysis.evidence.filter((e) => e.material_id === id);
      const file = String(m.path || "").split("/").pop();
      return `<small class="pp-kicker">材料 ${esc(id)}</small><h2>${esc(KIND[m.kind] || m.kind)}</h2>
        <p class="pp-lead">${esc(KIND_HELP[m.kind] || "")}</p>
        <dl class="pp-dl">
          <dt>文件</dt><dd class="mono">${esc(file)}</dd>
          <dt>格式</dt><dd>${esc(m.media_type)} · ${(m.size_bytes / 1024).toFixed(1)} KB</dd>
          ${m.origin && m.origin.note ? `<dt>导出说明</dt><dd>${esc(m.origin.note)}</dd>` : ""}
          <dt>解析</dt><dd>${esc(PARSE[m.parse_status] || m.parse_status)}${tm.parser ? ` · <span class="mono">${esc(tm.parser)}</span>` : ""}${m.parse_note ? `<br><span class="muted">${esc(m.parse_note)}</span>` : ""}</dd>
          <dt>切出</dt><dd>${spans.length} 段原文${m.parse_status === "unsupported" ? "（不交给模型）" : ""}</dd></dl>
        ${spans.length ? `<h3>这份材料的片段</h3><div class="pp-list">${spans.slice(0, 60).map((e) => `<button type="button" class="pp-row ${th.ev(e.id) ? "thread" : ""}" data-d="ev:${esc(e.id)}"><span class="mono">${esc(e.id)}</span><span>${esc(short(e.text, 70))}</span></button>`).join("")}
          ${spans.length > 60 ? `<p class="muted">还有 ${spans.length - 60} 段。</p>` : ""}</div>` : ""}`;
    }
    function evDetail(id) {
      const e = s.idx.span.get(id);
      const sent = s.idx.sent.has(id);
      const facts = s.idx.factsByEv.get(id) || [];
      const els = [...new Set(s.idx.elemsByEv.get(id) || [])];
      if (!e) {
        const t = s.trace.model.evidence.find((x) => x.id === id);
        return t ? `<small class="pp-kicker">片段</small><h2 class="mono">${esc(id)}</h2><blockquote class="pp-quote">${esc(t.text)}</blockquote>` : null;
      }
      return `<small class="pp-kicker">片段 · ${esc(spanLabel(s.analysis, e))}</small><h2 class="mono">${esc(id)}</h2>
        <div class="pp-flags">${sent ? `<span class="ok">发给了模型</span>` : `<span class="muted">没有发给模型</span>`}${e.needs_review ? `<span class="warn">解析质量存疑</span>` : ""}${e.quality != null ? `<span>OCR 质量 ${(e.quality * 100).toFixed(0)}%</span>` : ""}</div>
        <blockquote class="pp-quote">${esc(e.text)}</blockquote>
        <h3>模型从这段摘出的事实</h3>
        ${facts.length ? `<div class="pp-list">${facts.map((fi) => factRow(fi)).join("")}</div>` : `<p class="muted">没有。不是每段都有可摘的事实。</p>`}
        <h3>引用这段的要素</h3>
        ${els.length ? `<div class="pp-chips">${els.map(elChip).join("")}</div>` : `<p class="muted">没有要素的候选引用这一段。</p>`}
        <button type="button" class="p-link" data-d="mat:${esc(e.material_id)}">看它所在的材料 ${esc(e.material_id)} →</button>`;
    }
    function factRow(fi) {
      const f = s.trace.model.facts_kept[fi];
      return `<button type="button" class="pp-row ${th.fact(fi) ? "thread" : ""}" data-d="fact:${fi}"><span class="pp-tag">${esc(FACT[f.type] || f.type)}</span><span>${esc(short(f.quote, 70))}</span></button>`;
    }
    function factDetail(fi) {
      const f = s.trace.model.facts_kept[fi];
      if (!f) return null;
      const e = s.idx.span.get(f.evidence_id);
      const needle = f.quote.replace(/…$/, "");
      const els = [...new Set(s.idx.elemsByEv.get(f.evidence_id) || [])];
      return `<small class="pp-kicker">模型摘录的事实</small><h2>${esc(FACT[f.type] || f.type)}${f.time ? ` <span class="mono pp-time">${esc(f.time)}</span>` : ""}</h2>
        <h3>模型给的引文</h3><blockquote class="pp-quote model">${esc(f.quote)}</blockquote>
        <h3>原文 ${evChip(f.evidence_id)}</h3>
        <blockquote class="pp-quote">${e ? highlight(e.text, [needle]) : "（原文不在本次材料里）"}</blockquote>
        <div class="pp-verdict ok">✓ 本地核对：引文逐字出现在 ${esc(f.evidence_id)} 里，这条事实保留。对不上的事实只丢这一条，不影响整张单。</div>
        <h3>这条事实去了哪</h3>
        ${els.length ? `<p class="muted">本地把事实编成候选，下面这些要素引用了它所在的片段：</p><div class="pp-chips">${els.map(elChip).join("")}</div>` : `<p class="muted">它所在的片段没有被要素候选引用（例如处理步骤只进处理过程的时间线）。</p>`}`;
    }
    function dropDetail(i) {
      const f = s.trace.model.facts_dropped[i];
      if (!f) return null;
      const e = s.idx.span.get(f.evidence_id);
      return `<small class="pp-kicker">被丢弃的事实</small><h2>${esc(FACT[f.type] || f.type)}</h2>
        <div class="pp-verdict bad">✗ ${esc(f.reason || "引文对不上原文")}</div>
        <h3>模型给的引文</h3><blockquote class="pp-quote model">${esc(f.quote)}</blockquote>
        ${e ? `<h3>它声称出自 ${evChip(f.evidence_id)}</h3><blockquote class="pp-quote">${esc(e.text)}</blockquote>` : ""}
        <p class="muted">模型的话一律要能在原文里逐字找到，找不到就不用，避免“编”出来的结论进报告。</p>`;
    }
    function elDetail(name) {
      const a = s.analysis;
      const el = a.elements[name];
      if (!el) return null;
      const v = valueText(name, el);
      const sa = a.semantic_assessment || {};
      const checks = (sa.checks || []).filter((c) => c.element === name);
      const rec = name === "end_time" ? sa.recovery_selection : null;
      const issues = a.issues.filter((i) => i.element === name);
      const cands = (el.candidates || []).map((c) => {
        const chosen = el.selected ? c.id === el.selected : el.status !== "unknown";
        const reasons = [...new Set(checks.filter((k) => k.candidate_id === c.id).map((k) => k.reason))];
        const excluded = rec && rec.excluded && rec.excluded[c.id];
        const kind = candKind(name, c);
        return `<div class="pp-cand ${chosen ? "sel" : "out"} ${s.thread && s.thread.cand === c ? "thread" : ""}">
          <div class="pp-cand-h"><span class="mark">${chosen ? "✓ 采用" : "✗ 未采用"}</span><span class="mono">${esc(c.id)}</span>
            ${kind ? `<span class="pp-tag">${esc(kind)}</span>` : ""}${c.attribution ? `<span class="pp-tag soft">${esc(ATTR[c.attribution] || c.attribution)}</span>` : ""}</div>
          <div class="pp-cand-v">${esc(candText(name, c) || "")}</div>
          ${(c.evidence_refs || []).length ? `<div class="pp-chips">${c.evidence_refs.map(evChip).join("")}</div>` : `<div class="muted small">没有原文出处（工单系统字段）</div>`}
          ${excluded ? `<div class="pp-why bad">淘汰理由：${esc(excluded)}</div>` : ""}
          ${reasons.map((r) => `<div class="pp-why">${esc(r)}</div>`).join("")}
          ${c.note ? `<div class="pp-why">${esc(c.note)}</div>` : ""}</div>`;
      }).join("");
      const steps = name === "handling_process" && Array.isArray(el.value) ? el.value : [];
      return `<small class="pp-kicker">要素 · 本地规则裁决</small><h2>${esc(LABEL[name])} ${badge(el.status)}</h2>
        <div class="pp-value">${v ? esc(v) : `<span class="muted">留空：原文没有可用依据，系统不猜</span>`}</div>
        <h3>规则怎么取</h3><p class="pp-lead">${esc(RULE_HELP[name] || "")}</p>
        ${rec && rec.reason ? `<div class="pp-verdict ok">裁决：${esc(rec.reason)}</div>` : ""}
        ${(el.candidates || []).length ? `<h3>候选 ${el.candidates.length} 个</h3>${cands}` : ""}
        ${steps.length ? `<h3>处理步骤 ${steps.length} 条</h3><div class="pp-chips">${(el.evidence_refs || []).slice(0, 30).map(evChip).join("")}</div>` : ""}
        ${el.note ? `<p class="pp-lead">${esc(el.note)}</p>` : ""}
        <h3>待核实与提示</h3>
        ${issues.length ? issues.map((i) => `<div class="pp-why ${i.severity === "info" ? "" : "warn"}">${i.severity === "info" ? "提示" : "【待核实】"}${esc(i.message)}</div>`).join("") : `<p class="muted">没有。</p>`}`;
    }
    function promptDetail() {
      const p = s.trace.prompt || {};
      return `<small class="pp-kicker">第一段：事实摘录</small><h2>模型拿到的指令</h2>
        <p class="pp-lead">模型不填结论、不做取舍，只把原文里写明的东西按类型摘出来，每条带证据编号和逐字引文。取哪条、怎么推定、标不标待核实，全部由本地规则决定，所以换模型（DeepSeek ↔ 公司本地模型）不改规则。</p>
        ${p.changed ? `<div class="pp-why warn">这次回放用的记录是旧版提示词生成的；下面是当前版本。</div>` : ""}
        ${p.recheck ? `<h3>第 2 遍（复核）多加的一句</h3><blockquote class="pp-quote">${esc(p.recheck)}</blockquote>` : ""}
        <h3>提示词原文</h3><pre class="pp-pre">${esc(p.instruction || "（没有记录）")}</pre>`;
    }

    // ── 小工具 ──
    function badge(st) {
      const x = STATUS[st] || { label: st, icon: "" };
      return `<span class="badge s-${esc(st)}"><span aria-hidden="true">${x.icon}</span>${esc(x.label)}</span>`;
    }
    function pickSamples(ev, n) {
      const good = ev.filter((e) => /log:|msg:/.test(e.id) && e.text.length > 12);
      const pool = good.length >= n ? good : ev;
      const out = [];
      for (let i = 0; i < n && pool.length; i++) out.push(pool[Math.floor((i * pool.length) / n)]);
      return out;
    }
    function short(t, n) { t = String(t || ""); return t.length > n ? t.slice(0, n) + "…" : t; }
    function shortLabel(label) { return String(label || "").replace(/^实时调用\s*/, ""); }
    function providerModel(p) { const parts = String(p || "").split(":"); return parts.length > 2 ? `当时由 ${parts.slice(2).join(":")} 生成` : ""; }

    // ── 事件 ──
    root.addEventListener("change", (e) => { if (e.target.matches("[data-thread]")) setThread(e.target.value); });
    root.addEventListener("click", (e) => {
      const d = e.target.closest("[data-d]");
      if (d && s.trace) return openPanel(d.dataset.d);
      const pp = e.target.closest("[data-pp]");
      if (pp) {
        if (pp.dataset.pp === "close") return closePanel();
        if (pp.dataset.pp === "back" && s.panel.length > 1) { s.panel.pop(); return openPanel(s.panel[s.panel.length - 1], false); }
        return;
      }
      const b = e.target.closest("[data-p], [data-p-stage]");
      if (!b) return;
      if (b.dataset.pStage != null) { s.playing = true; return goStage(+b.dataset.pStage); }
      const act = b.dataset.p;
      if (act === "close") return close();
      if (act === "prev") { s.playing = true; return goStage(s.stage - 1); }
      if (act === "next") { s.playing = true; return goStage(s.stage + 1); }
      if (act === "again") { s.playing = true; return goStage(0); }
      if (act === "auto") { s.auto = !s.auto; s.hold = 0; b.classList.toggle("on", s.auto); b.setAttribute("aria-pressed", s.auto); b.textContent = `自动翻步：${s.auto ? "开" : "关"}`; return apply(); }
      if (act === "play" && s.clock >= s.end) { s.playing = true; return goStage(s.stage); }
      if (act === "play") { s.playing = !s.playing; s.last = performance.now(); return apply(); }
      if (act === "speed") { s.speed = s.speed === 1 ? 2 : s.speed === 2 ? 0.5 : 1; b.textContent = s.speed + "×"; return; }
      if (act === "open" || act === "report") { const ref = s.ref; close(); onOpen(ref, act === "report" ? 3 : 2); }
    });
    document.addEventListener("keydown", (e) => {
      if (root.hidden) return;
      if (e.key === "Escape") { e.stopImmediatePropagation(); return root.classList.contains("panel-open") ? closePanel() : close(); }
      if (!s.trace || e.target.matches && e.target.matches("select")) return;
      if (e.key === " " && s.clock >= s.end) { e.preventDefault(); s.playing = true; goStage(s.stage); }
      else if (e.key === " ") { e.preventDefault(); s.playing = !s.playing; s.last = performance.now(); apply(); }
      if (e.key === "ArrowRight") { e.preventDefault(); s.playing = true; goStage(s.stage + 1); }
      if (e.key === "ArrowLeft") { e.preventDefault(); s.playing = true; goStage(s.stage - 1); }
      e.stopImmediatePropagation();
    }, true);

    return { open, close, isOpen: () => !root.hidden };
  }

  window.noc7Process = create;
})();
