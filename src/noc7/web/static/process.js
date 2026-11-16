/* 分析过程演示：把一次分析的真实数据（/api/tickets/<ref>/trace）按五步分页播放。
   只为演示后端逻辑；实际工作时不打开它，分析照样在后台跑。
   动画由一个“场景时钟”驱动：元素带 data-at（毫秒），时钟走到就显现；暂停就是时钟停走。 */
(function () {
  "use strict";

  const STAGES = [
    { key: "bundle", name: "拆工单包", lead: "读出工单包里的每份材料，交给对应的解析器" },
    { key: "evidence", name: "原文编号", lead: "原文切成带编号的片段：模型只看这些，引用时必须写编号" },
    { key: "model", name: "模型摘录", lead: "模型只做一件事：从片段里摘出事实，并给出原文引文" },
    { key: "rules", name: "本地规则", lead: "本地规则逐条核对引文，按依据强弱给七要素取值；拿不准就留空或标待核实" },
    { key: "report", name: "生成报告", lead: "七要素写进公司报告，每个结论都能点回原文" },
  ];
  const KIND = { ticket_fields: "工单字段", process_log: "处理过程", email_html: "邮件", email_eml: "邮件", image: "图片", pdf: "PDF", docx: "Word", text: "文本", other: "其他" };
  const KIND_ICON = { ticket_fields: "▤", process_log: "☰", email_html: "✉", email_eml: "✉", image: "▣", pdf: "▧", docx: "▥", text: "¶", other: "?" };
  const PARSE = { parsed: "已解析", needs_review: "解析了，质量存疑", failed: "解析失败", unsupported: "格式不支持，已标出", pending: "未解析" };
  const FACT = { start_time: "发生时间", recovery_time: "恢复时间", phenomenon: "故障现象", cause: "故障原因", responsibility: "责任方",
    location: "故障地点", step: "处理步骤", service_recovered: "业务恢复", customer_followup: "客户回访", alarm: "告警", other: "其他" };

  function create(deps) {
    const { $, esc, LABEL, ELEMENTS, STATUS, valueText, fetchDetail, jobOf, onOpen } = deps;
    const root = document.createElement("div");
    root.className = "proc";
    root.hidden = true;
    root.setAttribute("role", "dialog");
    root.setAttribute("aria-modal", "true");
    root.setAttribute("aria-label", "分析过程");
    document.body.appendChild(root);

    const s = { ref: null, trace: null, analysis: null, stage: 0, clock: 0, playing: true, speed: 1, end: 0, raf: 0, last: 0, wait: null, hold: 0, error: "" };

    // ── 打开、等待、关闭 ──
    async function open(ref, { waiting = false } = {}) {
      stop();
      Object.assign(s, { ref, trace: null, analysis: null, stage: 0, clock: 0, playing: true, error: "", hold: 0 });
      root.hidden = false;
      document.body.classList.add("proc-open");
      if (waiting) return waitFor(ref);
      return load(ref);
    }
    function close() {
      stop();
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
        root.innerHTML = frame(`<div class="p-wait">
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
          root.innerHTML = frame(`<div class="p-wait"><h2>分析没有完成</h2><p class="p-err">${esc((j.problems || []).join("；"))}</p></div>`, true);
          return;
        }
        paint();
      }, 500);
    }
    async function load(ref) {
      const [traceRes, detail] = await Promise.all([fetch(`/api/tickets/${encodeURIComponent(ref)}/trace`), fetchDetail(ref)]);
      if (s.ref !== ref) return;
      if (!traceRes.ok || !detail || detail.status !== "ready") {
        root.innerHTML = frame(`<div class="p-wait"><h2>没有过程记录</h2><p>这次结果是旧版操作台留下的，没有记录过程。点卡片上的“回放”重新跑一次就有了。</p></div>`, true);
        return;
      }
      s.trace = await traceRes.json();
      s.analysis = detail.analysis;
      goStage(0);
    }

    // ── 场景时钟 ──
    function goStage(i) {
      s.stage = Math.max(0, Math.min(STAGES.length - 1, i));
      s.clock = 0; s.hold = 0;
      const scene = SCENES[s.stage]();
      s.end = scene.end;
      root.innerHTML = frame(scene.html);
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
        else if (s.stage < STAGES.length - 1) {
          s.hold += dt * s.speed;
          if (s.hold > 1400) { goStage(s.stage + 1); return; }
        }
        apply();
      }
      s.raf = requestAnimationFrame(tick);
    }
    function apply() {
      const t = s.clock;
      root.querySelectorAll("[data-at]").forEach((el) => {
        const on = t >= +el.dataset.at;
        if (on !== el.classList.contains("in")) el.classList.toggle("in", on);
      });
      root.querySelectorAll("[data-type]").forEach((el) => {
        const at = +el.dataset.at || 0, dur = +el.dataset.dur || 1;
        const full = el.dataset.full ?? (el.dataset.full = el.textContent);
        const n = Math.round(full.length * Math.max(0, Math.min(1, (t - at) / dur)));
        if (el._n !== n) { el._n = n; el.textContent = full.slice(0, n); el.scrollTop = el.scrollHeight; }
      });
      root.querySelectorAll("[data-count]").forEach((el) => {
        const at = +el.dataset.at || 0, dur = +el.dataset.dur || 800, to = +el.dataset.count;
        const v = Math.round(to * Math.max(0, Math.min(1, (t - at) / dur)));
        if (el._v !== v) { el._v = v; el.textContent = v; }
      });
      root.querySelectorAll("[data-grow]").forEach((el) => {
        const at = +el.dataset.at || 0, dur = +el.dataset.dur || 800;
        el.style.width = (+el.dataset.grow * Math.max(0, Math.min(1, (t - at) / dur))).toFixed(1) + "%";
      });
      const bar = root.querySelector(".p-progress span");
      if (bar) bar.style.width = (s.end ? Math.min(100, (s.clock / s.end) * 100) : 100).toFixed(1) + "%";
      const play = root.querySelector("[data-p=play]");
      if (play) play.textContent = s.playing ? "⏸ 暂停" : "▶ 继续";
    }

    // ── 外框：标题、五步、控制条 ──
    function frame(body, bare) {
      const tr = s.trace;
      const job = jobOf(s.ref) || {};
      const title = (tr && tr.ticket && tr.ticket.title) || job.title || s.ref || "";
      const mode = tr ? tr.mode : job.mode;
      const chip = mode === "live" ? `实时调用 · ${esc(shortLabel(tr ? tr.model_label : job.model_label))}` : "回放 · 不联网";
      const steps = STAGES.map((st, i) => `<button type="button" class="p-step ${i === s.stage && !bare ? "on" : ""} ${i < s.stage && !bare ? "done" : ""}" data-p-stage="${i}" ${bare ? "disabled" : ""}>
          <span class="n">${i + 1}</span>${st.name}</button>`).join("");
      const st = STAGES[s.stage];
      return `<div class="p-shell">
        <header class="p-head">
          <div class="p-title"><small>分析过程演示</small><b title="${esc(title)}">${esc(title)}</b></div>
          <span class="p-chip ${mode === "live" ? "live" : ""}">${chip}</span>
          <button type="button" class="p-x" data-p="close" aria-label="关闭">✕</button></header>
        <nav class="p-steps">${steps}</nav>
        ${bare ? "" : `<div class="p-lead"><b>${s.stage + 1} · ${st.name}</b>${st.lead}</div>`}
        <section class="p-stage">${body}</section>
        ${bare ? "" : `<footer class="p-ctrl">
          <button type="button" class="p-btn" data-p="prev" ${s.stage === 0 ? "disabled" : ""}>⏮ 上一步</button>
          <button type="button" class="p-btn main" data-p="play">⏸ 暂停</button>
          <button type="button" class="p-btn" data-p="next" ${s.stage === STAGES.length - 1 ? "disabled" : ""}>下一步 ⏭</button>
          <div class="p-progress"><span></span></div>
          <button type="button" class="p-btn" data-p="speed">${s.speed}×</button>
          <span class="p-keys">空格 暂停 · ←→ 翻步 · Esc 关闭</span></footer>`}</div>`;
    }

    // ── 五个场景：每个返回 html 和时长（毫秒，1× 速度） ──
    const SCENES = [sceneBundle, sceneEvidence, sceneModel, sceneRules, sceneReport];

    function sceneBundle() {
      const ms = s.trace.materials;
      const step = Math.max(160, Math.min(380, 3600 / Math.max(1, ms.length)));
      const tiles = ms.map((m, i) => {
        const at = 300 + i * step;
        const bad = m.parse_status === "unsupported" || m.parse_status === "failed";
        return `<div class="p-tile ${bad ? "bad" : ""} ${m.ocr ? "ocr" : ""}" data-at="${at}" style="--i:${i}">
          <span class="ic">${KIND_ICON[m.kind] || "?"}</span>
          <b>${esc(KIND[m.kind] || m.kind)}</b><small class="mono">${esc(m.id)}</small>
          ${m.ocr ? `<i class="scan" data-at="${at + 150}"></i><em data-at="${at + 150}">本地 OCR 识别文字</em>` : ""}
          <div class="out" data-at="${at + 260}">${bad ? esc(PARSE[m.parse_status]) : `→ <b>${m.spans}</b> 段原文`}</div></div>`;
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
      const shown = ev.slice(0, 96);
      const gap = Math.max(18, Math.min(45, 4200 / Math.max(1, shown.length)));
      const chips = shown.map((e, i) => `<span class="p-ev k-${esc(e.kind)}" data-at="${400 + i * gap}" title="${esc(e.text)}">${esc(e.id)}</span>`).join("");
      const more = ev.length > shown.length ? `<span class="p-ev more" data-at="${400 + shown.length * gap}">+${m.sent - shown.length}</span>` : "";
      const samples = pickSamples(ev, 5);
      const t = 400 + shown.length * gap + 300;
      const lines = samples.map((e, i) => `<div class="p-line" data-at="${t + i * 380}"><span class="mono id">${esc(e.id)}</span><span>${esc(e.text)}</span></div>`).join("");
      return {
        end: t + samples.length * 380 + 1400,
        html: `<div class="p-evidence">
          <div class="p-col"><h3>按来源</h3>${bars}
            <div class="p-note" data-at="${400}">编号规则：<span class="mono">材料/位置</span>，如 <span class="mono">M02/log:5</span> 是第 2 份材料“处理过程”第 5 条。</div></div>
          <div class="p-col wide"><h3>发给模型的片段 <b class="mono" data-count="${m.sent}" data-at="400" data-dur="${shown.length * gap}">0</b> 条 · ${m.request_kb} KB</h3>
            <div class="p-evwall">${chips}${more}</div>
            <div class="p-lines">${lines}</div></div></div>`,
      };
    }

    function sceneModel() {
      const m = s.trace.model;
      const live = s.trace.mode === "live";
      const passes = m.passes.length ? m.passes : [""];
      let t = 2200;
      const term = passes.map((raw, i) => {
        const show = raw.slice(0, 900);
        const dur = Math.max(1200, show.length * 3);
        const html = `<div class="p-pass" data-at="${t - 200}"><div class="p-pass-h">第 ${i + 1} 遍${i ? "（复核：补漏、纠错）" : "（摘录事实）"}${live ? "" : " · 读取保存的原始回复"}</div>
          <pre class="p-term mono" data-type="1" data-at="${t}" data-dur="${dur}">${esc(show || "（这份记录只保存了核对后的事实）")}${raw.length > 900 ? "\n…" : ""}</pre></div>`;
        t += dur + 500;
        return html;
      }).join("");
      const facts = m.facts_kept.slice(0, 10);
      const ft = t;
      const cards = facts.map((f, i) => `<div class="p-fact" data-at="${ft + i * 420}">
          <span class="ft">${esc(FACT[f.type] || f.type)}</span>
          <q>${esc(f.quote)}</q>
          <span class="ok" data-at="${ft + i * 420 + 260}">✓ 引文在原文里 → <span class="mono">${esc(f.evidence_id)}</span></span></div>`).join("");
      const dropped = m.facts_dropped.slice(0, 3).map((f, i) => `<div class="p-fact drop" data-at="${ft + (facts.length + i) * 420}">
          <span class="ft">${esc(FACT[f.type] || f.type)}</span><q>${esc(f.quote)}</q>
          <span class="no">✗ 丢弃：${esc(f.reason || "引文对不上原文")}</span></div>`).join("");
      const end = ft + (facts.length + Math.min(3, m.facts_dropped.length)) * 420;
      const usage = m.usage.reduce((a, u) => a + (+u.total_tokens || 0), 0);
      return {
        end: end + 1600,
        html: `<div class="p-model">
          <div class="p-wire">
            <div class="p-node" data-at="0"><b class="mono">${m.sent}</b> 条片段<small>${m.request_kb} KB · 不含截图</small></div>
            <div class="p-pipe" data-at="300"><i></i><i></i><i></i><i></i><span>${live ? "HTTPS 请求" : "不联网"}</span></div>
            <div class="p-node brain" data-at="700"><b>${live ? esc(shortLabel(s.trace.model_label)) : "保存的模型回复"}</b><small>${live ? `${m.attempts} 次请求${usage ? ` · ${usage} tokens` : ""}` : esc(providerModel(s.trace.provider))}</small></div>
            <div class="p-pipe back" data-at="1300"><i></i><i></i><i></i><i></i><span>${passes.length} 遍回复</span></div>
            <div class="p-node" data-at="1700"><b class="mono" data-count="${m.facts_kept.length}" data-at="${ft}" data-dur="${Math.max(400, facts.length * 420)}">0</b> 条事实<small>丢弃 ${m.facts_dropped.length} 条</small></div></div>
          <div class="p-split">
            <div class="p-col">${term}</div>
            <div class="p-col"><h3>本地逐条核对引文</h3>${cards}${dropped}
              ${m.facts_kept.length > facts.length ? `<div class="p-note" data-at="${end}">还有 ${m.facts_kept.length - facts.length} 条事实，同样都核对过。</div>` : ""}</div></div></div>`,
      };
    }

    function sceneRules() {
      const a = s.analysis;
      const rows = s.trace.rules.map((r, i) => {
        const at = 400 + i * 1100;
        const el = a.elements[r.element];
        const v = valueText(r.element, el);
        const issue = r.issues.find((x) => x.severity !== "info");
        return `<div class="p-rule" data-at="${at}">
          <b class="lbl">${esc(LABEL[r.element] || r.element)}</b>
          <span class="p-cand" data-at="${at + 200}">候选 <b>${r.candidates}</b></span>
          <span class="gear" data-at="${at + 350}">⚙ 核引文 · 比依据 · 查冲突</span>
          <span class="res" data-at="${at + 750}">${badge(r.after)}${v ? `<span class="val" title="${esc(v)}">${esc(v)}</span>` : `<span class="val muted">留空，不猜</span>`}</span>
          ${issue ? `<span class="iss" data-at="${at + 900}" title="${esc(issue.message)}">【待核实】${esc(issue.message)}</span>` : `<span class="iss ok" data-at="${at + 900}">${r.after === "unknown" ? "" : "依据充分"}</span>`}</div>`;
      }).join("");
      const end = 400 + s.trace.rules.length * 1100 + 600;
      return {
        end: end + 1200,
        html: `<div class="p-rules">
          <div class="p-ladder" data-at="0">取值顺序：<span>客户确认 / RFO</span>›<span>处理日志明确记载</span>›<span>按北京时间推定</span>›<span>告警</span>›<span>工单系统字段兜底（标待核实）</span></div>
          ${rows}
          <div class="p-note" data-at="${end}">规则版本 ${esc(s.trace.rules_version || "")}：模型只给候选和引文，取哪一条、标不标待核实，全由这里的规则决定。</div></div>`,
      };
    }

    function sceneReport() {
      const a = s.analysis;
      const c = { confirmed: 0, documented: 0, unknown: 0, conflicted: 0 };
      ELEMENTS.forEach((n) => { c[a.elements[n].status] = (c[a.elements[n].status] || 0) + 1; });
      const open = a.issues.filter((i) => i.severity !== "info").length;
      const dots = ELEMENTS.map((n, i) => `<div class="p-dot" data-at="${200 + i * 220}"><span class="dot ${esc(a.elements[n].status)}"></span><small>${esc(LABEL[n])}</small></div>`).join("");
      const m = s.trace.model;
      const narr = m.narrative === "accepted" ? (m.narrative_replaced ? "模型写了叙述，本地核验时有不符的句子，已改回本地拼接" : "模型写了叙述，本地逐句核验通过")
        : m.narrative ? "叙述没有采用模型的，用本地拼接" : "叙述由本地拼接";
      const sec = s.trace.elapsed_seconds;
      const t = 200 + ELEMENTS.length * 220 + 200;
      const ref = encodeURIComponent(s.ref);
      return {
        end: t + 2200,
        html: `<div class="p-report">
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
            <button type="button" class="p-btn" data-p="again">从头再放</button></div></div>`,
      };
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
    function shortLabel(label) { return String(label || "").replace(/^实时调用\s*/, ""); }
    function providerModel(p) { const parts = String(p || "").split(":"); return parts.length > 2 ? `当时由 ${parts.slice(2).join(":")} 生成` : ""; }

    // ── 事件 ──
    root.addEventListener("click", (e) => {
      const b = e.target.closest("[data-p], [data-p-stage]");
      if (!b) return;
      if (b.dataset.pStage != null) return goStage(+b.dataset.pStage);
      const act = b.dataset.p;
      if (act === "close") return close();
      if (act === "prev") return goStage(s.stage - 1);
      if (act === "next") return goStage(s.stage + 1);
      if (act === "again") { s.playing = true; return goStage(0); }
      if (act === "play") { s.playing = !s.playing; s.last = performance.now(); return apply(); }
      if (act === "speed") { s.speed = s.speed === 1 ? 2 : s.speed === 2 ? 0.5 : 1; b.textContent = s.speed + "×"; return; }
      if (act === "open" || act === "report") { const ref = s.ref; close(); onOpen(ref, act === "report" ? 3 : 2); }
    });
    document.addEventListener("keydown", (e) => {
      if (root.hidden) return;
      if (e.key === "Escape") { e.stopImmediatePropagation(); return close(); }
      if (!s.trace) return;
      if (e.key === " ") { e.preventDefault(); s.playing = !s.playing; s.last = performance.now(); apply(); }
      if (e.key === "ArrowRight") { e.preventDefault(); goStage(s.stage + 1); }
      if (e.key === "ArrowLeft") { e.preventDefault(); goStage(s.stage - 1); }
      e.stopImmediatePropagation();
    }, true);

    return { open, close, isOpen: () => !root.hidden };
  }

  window.noc7Process = create;
})();
