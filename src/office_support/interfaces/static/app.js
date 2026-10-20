// Office Support Console — React 18 + htm (no build step).
// The page decides nothing: it starts a run through the API, replays the steps
// that orchestrate() records and sends the person's answer to a confirmation.

const { useState, useEffect, useRef, useMemo } = React;
const html = htm.bind(React.createElement);

const POLL_MS = 250;      // how often the run is polled
const REVEAL_MS = 520;    // pace at which steps appear (readable even with the instant simulated model)
const AGENT_ORDER = ["classifier", "diagnosis", "knowledge", "escalation"];
const SERVICE_LABELS = { vpn: "vpn", email: "mail", erp: "erp", files: "files",
                         intranet: "intra", printing: "print", guest_wifi: "wifi" };
const FINAL_TITLES = { resolved: "Resolved at first level", escalated: "Escalated to second level",
                       rejected: "Not processed", step_limit_reached: "Step limit reached" };
const KIND_LABELS = { tool: "tool call", call: "asks for a tool", output: "answer",
                      note: "rule check", blocked: "blocked call", invalid: "unreadable response" };

// --- API ----------------------------------------------------------------------

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

// --- Icons ----------------------------------------------------------------------

const PATHS = {
  classifier: "M3 7h18M3 12h12M3 17h7M17 15l2 2 4-4",
  diagnosis: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-4.3-4.3M11 8v6M8 11h6",
  knowledge: "M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zM4 5v16M9 7h6M9 11h6",
  escalation: "M12 19V5M5 12l7-7 7 7",
  orchestrator: "M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z",
  resolved: "M5 12l5 5L20 7",
  escalated: "M12 19V5M5 12l7-7 7 7",
  rejected: "M6 6l12 12M18 6L6 18",
  step_limit_reached: "M12 7v5l3 3M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z",
  sun: "M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M5.6 18.4l-1.4 1.4M19.8 4.2l-1.4 1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
  moon: "M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z",
  play: "M7 5v14l11-7z",
  warn: "M12 3l10 18H2zM12 10v4M12 17.5v.5",
};

function Icon({ name, size = 18 }) {
  return html`<svg width=${size} height=${size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d=${PATHS[name]} /></svg>`;
}

// --- Small helpers ----------------------------------------------------------------

const agentColor = (agent) => `var(--c-${agent})`;

function callText(tool, args) {
  const parts = Object.entries(args || {}).map(([k, v]) => html`<span key=${k}>${k}=${JSON.stringify(v)}</span>`);
  const joined = parts.flatMap((p, i) => (i ? [", ", p] : [p]));
  return html`<span className="call"><span className="fn">${tool}</span>(${joined})</span>`;
}

function inlineCode(text) {
  return text.split(/(`[^`]+`)/).map((part, i) =>
    part.startsWith("`") ? html`<code key=${i}>${part.slice(1, -1)}</code>` : part);
}

function lastOutput(steps, agent) {
  const outputs = steps.filter((s) => s.agent === agent && s.kind === "output");
  return outputs.length ? outputs[outputs.length - 1].observation : null;
}

// --- Left column -------------------------------------------------------------------

function IncidentForm({ meta, form, setForm, onRun, busy }) {
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const statusOf = (office) => {
    const values = Object.values(meta.services[office]);
    return values.includes("down") ? "down" : values.includes("degraded") ? "degraded" : "ok";
  };
  return html`<section className="card">
    <h2>New incident</h2>
    <textarea value=${form.incident} onChange=${set("incident")}
      placeholder="Describe the problem, e.g. “I have no internet”"
      onKeyDown=${(e) => (e.key === "Enter" && (e.ctrlKey || e.metaKey) ? onRun() : null)}></textarea>
    <div className="field"><span>Office</span>
      <div className="offices">${meta.offices.map((o) => html`
        <button key=${o} className=${"office-btn" + (form.office === o ? " on" : "")}
          onClick=${() => setForm({ ...form, office: o })}>
          <i className=${"dot " + statusOf(o)}></i>${o}</button>`)}
      </div></div>
    <label className="field"><span>Ticket (optional)</span>
      <input className="input" value=${form.ticket} onChange=${set("ticket")} placeholder="T-0007" /></label>
    <button className="primary" onClick=${onRun} disabled=${busy || !form.incident.trim()}>
      <${Icon} name="play" size=${16} /> ${busy ? "Agents working…" : "Run the agents"}</button>
  </section>`;
}

function Examples({ meta, onPick }) {
  return html`<section className="card"><h2>Example cases</h2>
    <div className="examples">${meta.examples.map((e, i) => html`
      <button key=${i} className="example" onClick=${() => onPick(e)}>
        <b>${e.title}</b><small>“${e.incident}” · ${e.office}${e.ticket ? " · " + e.ticket : ""}</small>
      </button>`)}</div></section>`;
}

function NetworkStatus({ meta, office }) {
  const services = Object.keys(meta.services[meta.offices[0]]);
  return html`<section className="card"><h2>Network status</h2>
    <table className="net"><thead><tr><th></th>${services.map((s) => html`
      <th key=${s} title=${s + (meta.critical.includes(s) ? " (critical)" : "")}>
        ${SERVICE_LABELS[s] || s}${meta.critical.includes(s) ? "*" : ""}</th>`)}</tr></thead>
    <tbody>${meta.offices.map((o) => html`<tr key=${o} className=${o === office ? "sel" : ""}>
      <td>${o}</td>${services.map((s) => html`<td key=${s}>
        <i className=${"dot " + meta.services[o][s]} title=${`${s} in ${o}: ${meta.services[o][s]}`}></i></td>`)}
    </tr>`)}</tbody></table>
    <div className="legend"><span><i className="dot ok"></i>ok</span>
      <span><i className="dot degraded"></i>degraded</span><span><i className="dot down"></i>down</span>
      <span>* critical</span></div>
    <p className="note-text">Every run starts from this state; changes are not saved.</p>
  </section>`;
}

// --- Pipeline ------------------------------------------------------------------------

function agentFacts(agent, steps) {
  const out = lastOutput(steps, agent);
  if (agent === "classifier" && out) return [["type", out.type], ["priority", out.priority]];
  if (agent === "diagnosis" && out) return [["service", out.service ?? "device"], ["cause", out.cause]];
  if (agent === "knowledge" && out) return [["citations", (out.citations || []).length],
                                           ["action", out.action ? out.action.tool : "none"]];
  if (agent === "escalation") {
    const created = steps.find((s) => s.tool === "create_escalation" && s.observation && s.observation.escalation);
    if (created) return [["id", created.observation.escalation], ["priority", created.observation.priority]];
  }
  return [];
}

function AgentNode({ agent, status, steps }) {
  const used = new Map();
  steps.filter((s) => s.agent === agent.name && s.kind === "tool")
       .forEach((s) => used.set(s.tool, used.get(s.tool) === "err" || (s.observation && s.observation.error) ? "err" : "used"));
  const labels = { idle: "waiting", active: "working", done: "done", skipped: "not needed" };
  return html`<div className=${"agent " + status} style=${{ "--c": agentColor(agent.name) }}>
    <div className="agent-head">
      <div className="avatar"><${Icon} name=${agent.name} /></div>
      <div><div className="agent-name">${agent.name[0].toUpperCase() + agent.name.slice(1)}</div>
        <div className="agent-state">${labels[status]}</div></div>
    </div>
    <div className="agent-role">${agent.role}</div>
    <div className="chips">${agent.tools.map((t) => html`
      <span key=${t} className=${"chip " + (used.get(t) || "")}>${t}</span>`)}</div>
    <div className="facts">${agentFacts(agent.name, steps).map(([k, v]) => html`
      <div key=${k}><span>${k}</span><b title=${String(v)}>${String(v)}</b></div>`)}</div>
  </div>`;
}

function Outcome({ result, running }) {
  if (!result) {
    return html`<div className="outcome">
      ${running ? html`<span className="typing"><i></i><i></i><i></i></span>` : html`<${Icon} name="resolved" />`}
      <span>${running ? "in progress" : "outcome"}</span></div>`;
  }
  return html`<div className=${"outcome " + result.final}>
    <${Icon} name=${result.final} size=${26} />
    <span className="big">${result.final.replaceAll("_", " ")}</span>
    ${result.escalation ? html`<span className="mono">${result.escalation}</span>` : null}
  </div>`;
}

function Pipeline({ meta, run, shown, result }) {
  const steps = run ? run.steps.slice(0, shown) : [];
  const acting = [...steps].reverse().find((s) => s.agent !== "orchestrator");
  const seen = new Set(steps.map((s) => s.agent));
  const status = (name) => {
    if (result) return result.trajectory.includes(name) ? "done" : "skipped";
    if (acting && acting.agent === name) return "active";
    if (seen.has(name)) return "done";
    return "idle";
  };
  const hits = new Set(steps.map((s) => s.rule).filter(Boolean));
  if (run && (run.pending || run.answer !== null)) hits.add("R1");
  if (result && result.final === "step_limit_reached") hits.add("R3");
  const counted = steps.filter((s) => s.agent !== "orchestrator").length;
  return html`<section className="card">
    <div className="row between">
      <div>
        <p className="incident-line">${run ? `“${run.incident}”` : "Agent pipeline"}</p>
        <div className="incident-meta">${run ? `${run.office}${run.ticket ? " · ticket " + run.ticket : ""} · model ${run.model}`
          : "classifier → diagnosis → knowledge → resolved | escalation"}</div>
      </div>
    </div>
    <div className="rules">
      ${Object.entries(meta.rules).map(([id, text]) => html`
        <span key=${id} className=${"rule" + (hits.has(id) ? " hit" : "")} title=${text}><b>${id}</b>${text.split(":")[0]}</span>`)}
      <span className=${"rule" + (hits.has("priority") ? " hit" : "")} title="The code raises the priority if the data (or a safety hazard) require more.">
        <b>P↑</b>priority check</span>
      <span className=${"rule" + (hits.has("handoff") ? " hit" : "")} title="Safety hazard, reopened ticket or multi-office outage → straight to escalation.">
        <b>⇢</b>handoff rule</span>
    </div>
    <div className="pipeline">
      ${meta.agents.map((a) => html`<${AgentNode} key=${a.name} agent=${a} status=${status(a.name)} steps=${steps} />`)}
      <${Outcome} result=${result} running=${!!run && !result} />
    </div>
    <div className="progress">
      <div className="row between label-sm"><span>Steps used (R3 limit)</span><span>${counted} / ${meta.max_steps}</span></div>
      <div className="bar"><i style=${{ width: `${Math.min(100, (counted / meta.max_steps) * 100)}%` }}></i></div>
    </div>
  </section>`;
}

// --- Timeline -------------------------------------------------------------------------

function StepBody({ step }) {
  const obs = step.observation;
  if (step.kind === "note") return html`<div className="step-body">${String(obs)}</div>`;
  if (step.kind === "call") return html`<div className="step-body">${callText(obs.tool, obs.arguments)}</div>`;
  if (step.kind === "invalid") return html`<div className="step-body">${String(obs)}</div>`;
  if (step.kind === "blocked") {
    return html`<div className="step-body">${callText(step.arguments.requested, step.arguments.arguments)}
      <span className="arrow">→</span><b>${obs.error}</b></div>`;
  }
  if (step.kind === "tool") {
    return html`<div className="step-body">${callText(step.tool, step.arguments)}
      ${obs && obs.error ? html`<span className="arrow">→</span><b>${obs.error}</b>` : null}
      <details><summary>observation</summary><pre>${JSON.stringify(obs, null, 2)}</pre></details></div>`;
  }
  return html`<div className="step-body"><div className="kv">${Object.entries(obs || {}).map(([k, v]) => html`
    <${React.Fragment} key=${k}><span>${k}</span>
      <b>${typeof v === "string" ? (v.length > 220 ? v.slice(0, 220) + "…" : v) : JSON.stringify(v)}</b></${React.Fragment}>`)}
  </div></div>`;
}

function Timeline({ run, shown }) {
  const end = useRef(null);
  useEffect(() => { const box = end.current && end.current.parentNode; if (box) box.scrollTop = box.scrollHeight; }, [shown]);
  const steps = run ? run.steps.slice(0, shown) : [];
  const waiting = run && !run.done && !run.pending && shown >= run.steps.length;
  return html`<section className="card"><h2>Live trace</h2>
    <div className="timeline">
      ${!run ? html`<div className="empty">Each model response, tool call and orchestrator rule will appear here.</div>` : null}
      ${steps.map((s) => html`<div key=${s.n} className=${"step k-" + s.kind} style=${{ "--c": agentColor(s.agent) }}>
        <div className="step-head"><span className="step-n">#${s.n}</span>
          <span className="step-agent">${s.agent}</span><span className="step-kind">${KIND_LABELS[s.kind]}</span>
          ${s.rule ? html`<span className=${"badge " + s.rule}>${s.rule}</span>` : null}</div>
        <${StepBody} step=${s} /></div>`)}
      ${waiting ? html`<div className="empty"><span className="typing"><i></i><i></i><i></i></span></div>` : null}
      <div ref=${end}></div>
    </div></section>`;
}

// --- Result ----------------------------------------------------------------------------

function ResultCard({ meta, run, result }) {
  if (run && run.error) return html`<section className="card"><h2>Result</h2>
    <div className="error-box">The model did not respond: ${run.error}</div></section>`;
  if (!result) return html`<section className="card"><h2>Result</h2>
    <div className="empty">${run ? "The agents are working…" : "Run an incident to see the answer to the employee."}</div></section>`;
  return html`<section className="card"><h2>Result</h2>
    <div className="result-final">
      <div className=${"final-icon " + result.final}><${Icon} name=${result.final} size=${22} /></div>
      <div><h3>${FINAL_TITLES[result.final]}</h3><p>${meta.finals[result.final]}</p></div>
    </div>
    <div className="metrics">
      <div className="metric"><span>Type</span><b>${result.type || "—"}</b></div>
      <div className="metric"><span>Priority</span>
        <b>${result.priority ? html`<span className=${"prio " + result.priority}>${result.priority}</span>` : "—"}</b></div>
      <div className="metric"><span>Escalation</span><b className="mono">${result.escalation || "—"}</b></div>
    </div>
    ${result.priority ? html`<p className="note-text">${result.priority}: ${meta.priorities[result.priority]}.
      First response within ${meta.response_times[result.priority]}.</p>` : null}
    <h2 style=${{ marginTop: "16px" }}>Answer to the employee</h2>
    <div className="answer">${result.answer.split("\n").filter(Boolean).map((l, i) => html`<p key=${i}>${inlineCode(l)}</p>`)}</div>
    ${result.citations.length ? html`<div className="sources">${result.citations.map((c) => html`<span key=${c} className="source">${c}</span>`)}</div>` : null}
    ${run.answer !== null ? html`<p className="note-text">Your answer to the proposed action: ${run.answer ? "confirmed" : "rejected"}.</p>` : null}
    <p className="note-text">${result.steps} steps · path: ${result.trajectory.join(" → ") || "no agents"}</p>
  </section>`;
}

function ConfirmModal({ action, onAnswer }) {
  useEffect(() => {
    const key = (e) => { if (e.key === "Escape") onAnswer(false); };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onAnswer]);
  return html`<div className="overlay" role="dialog" aria-modal="true">
    <div className="modal">
      <span className="warn-tag"><${Icon} name="warn" size=${14} /> Irreversible action · R1</span>
      <h3>Confirmation needed</h3>
      <p className="label-sm">The knowledge agent proposes this action. It only runs if you confirm it.</p>
      ${callText(action.tool, action.arguments)}
      <ul className="checks">
        <li>Passed the R2 guardrail (office, diagnosed service, status, 1 restart)</li>
        <li>Rejecting it does not run it: the incident is escalated instead</li>
      </ul>
      <div className="modal-actions">
        <button className="btn reject" onClick=${() => onAnswer(false)}>Reject</button>
        <button className="btn confirm" onClick=${() => onAnswer(true)} autoFocus>Confirm</button>
      </div>
    </div></div>`;
}

// --- App -------------------------------------------------------------------------------------

function useTheme() {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme ||
    (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("theme", theme); } catch (e) { /* private mode */ }
  }, [theme]);
  return [theme, () => setTheme(theme === "dark" ? "light" : "dark")];
}

function App() {
  const [meta, setMeta] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [form, setForm] = useState({ incident: "", office: "MAD-01", ticket: "" });
  const [model, setModel] = useState("simulated");
  const [run, setRun] = useState(null);
  const [shown, setShown] = useState(0);
  const [theme, toggleTheme] = useTheme();
  const runRef = useRef(null);

  useEffect(() => { api("/api/meta").then(setMeta).catch((e) => setLoadError(e.message)); }, []);

  // ?example=N starts an example case on load (handy links for a demo).
  useEffect(() => {
    const n = new URLSearchParams(location.search).get("example");
    if (meta && n !== null && meta.examples[Number(n)]) start(meta.examples[Number(n)]);
  }, [meta]);

  // Poll the run until it finishes; pause while a question is pending.
  useEffect(() => {
    if (!run || run.done || run.pending) return undefined;
    const timer = setInterval(async () => {
      const current = runRef.current;
      try {
        const snap = await api(`/api/runs/${current.id}?since=${current.steps.length}`);
        if (runRef.current !== current) return;
        const next = { ...current, steps: [...current.steps, ...snap.steps], pending: snap.pending,
                       done: snap.done, result: snap.result, error: snap.error, answer: snap.answer };
        runRef.current = next;
        setRun(next);
      } catch (e) { /* transient: try again on the next tick */ }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [run && run.id, run && run.done, run && !!run.pending]);

  // Reveal the received steps one by one.
  useEffect(() => {
    if (!run || shown >= run.steps.length) return undefined;
    const timer = setTimeout(() => setShown((n) => n + 1), REVEAL_MS);
    return () => clearTimeout(timer);
  }, [run, shown]);

  const start = async (input) => {
    const data = { ...input, model };
    setForm({ incident: data.incident, office: data.office, ticket: data.ticket || "" });
    const { id } = await api("/api/runs", data);
    const fresh = { id, ...data, steps: [], pending: null, done: false, result: null, error: null, answer: null };
    runRef.current = fresh;
    setShown(0);
    setRun(fresh);
  };

  const answer = async (yes) => {
    const current = runRef.current;
    await api(`/api/runs/${current.id}/answer`, { yes });
    const next = { ...current, pending: null, answer: yes };
    runRef.current = next;
    setRun(next);
  };

  if (loadError) return html`<div className="layout"><div className="error-box">Could not load the console: ${loadError}</div></div>`;
  if (!meta) return html`<div className="layout"><div className="empty">Loading…</div></div>`;

  const caughtUp = run && shown >= run.steps.length;
  const result = run && run.done && caughtUp ? run.result : null;
  const busy = !!run && !run.done;
  const showModal = run && run.pending && caughtUp;

  return html`<${React.Fragment}>
    <header className="topbar">
      <div className="brand"><div className="logo"><${Icon} name="orchestrator" /></div>
        <div><h1>Office Support Console</h1><p>Multi-agent first-level technical support</p></div></div>
      <div className="spacer"></div>
      <span className="label-sm">Model</span>
      <select className="select" value=${model} onChange=${(e) => setModel(e.target.value)} disabled=${busy}>
        ${meta.models.map((m) => html`<option key=${m} value=${m}>${m === "simulated" ? "Simulated (instant)" : "Ollama · " + m}</option>`)}
      </select>
      <button className="icon-btn" onClick=${toggleTheme} title="Switch theme" aria-label="Switch theme">
        <${Icon} name=${theme === "dark" ? "sun" : "moon"} /></button>
    </header>
    <main className="layout">
      <aside className="stack">
        <${IncidentForm} meta=${meta} form=${form} setForm=${setForm} busy=${busy}
          onRun=${() => form.incident.trim() && !busy && start(form)} />
        <${Examples} meta=${meta} onPick=${(e) => !busy && start(e)} />
        <${NetworkStatus} meta=${meta} office=${form.office} />
      </aside>
      <div className="stack">
        ${!run ? html`<section className="card hero">
          <h2>Watch four agents handle an incident</h2>
          <p>The classifier sets type and priority, the diagnosis checks the real status of services
            and devices, the knowledge agent cites the documented procedure and, if it cannot be solved,
            the escalation agent hands it to second level. The orchestrator enforces rules R1–R5 in code:
            highlighted below whenever they act.</p></section>` : null}
        <${Pipeline} meta=${meta} run=${run} shown=${shown} result=${result} />
        <div className="split">
          <${Timeline} run=${run} shown=${shown} />
          <${ResultCard} meta=${meta} run=${run} result=${result} />
        </div>
      </div>
    </main>
    <footer>Every decision is made by orchestrate() in Python; this page only shows it.</footer>
    ${showModal ? html`<${ConfirmModal} action=${run.pending} onAnswer=${answer} />` : null}
  </${React.Fragment}>`;
}

ReactDOM.createRoot(document.getElementById("root")).render(html`<${App} />`);
