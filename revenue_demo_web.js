/* Source -> finding -> independent approval -> committed SIM receipt. No remote assets. */
"use strict";
const $ = (id) => document.getElementById(id);
const state = {
  user: null,
  epoch: 0,
  sequence: 0,
  cases: [],
  analysis: null,
  payload: null,
  workbench: null,
  keys: new Map(),
  authQueue: Promise.resolve(),
};

// ---- formatting -------------------------------------------------------------
function money(value) {
  if (value === null || value === undefined) return "Unknown";
  const n = BigInt(value),
    a = n < 0n ? -n : n;
  const whole = (a / 100n).toLocaleString("en-US");
  return `${n < 0n ? "−" : ""}${whole}.${String(a % 100n).padStart(2, "0")}`;
}
function signed(value) {
  if (value === null || value === undefined) return "—";
  return (BigInt(value) > 0n ? "+" : "") + money(value);
}
function sim(value) {
  return value === null || value === undefined ? "—" : `${money(value)} SIM`;
}
const words = (s) => String(s).replaceAll("_", " ");
const capital = (s) => s.charAt(0).toUpperCase() + s.slice(1);
function when(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
function node(tag, text, className) {
  const n = document.createElement(tag);
  if (text !== undefined && text !== null) n.textContent = text;
  if (className) n.className = className;
  return n;
}

const OUTCOMES = {
  proposable: { title: "A correction is ready for review.", status: "Correction ready", tone: "good" },
  no_change: { title: "The invoice is already correct.", status: "No change", tone: "good" },
  review: { title: "This needs a human decision.", status: "Needs review", tone: "warn" },
  request_information: { title: "More information is needed.", status: "Missing terms", tone: "warn" },
  outside_scope: { title: "That request is outside billing scope.", status: "Out of scope", tone: "neutral" },
  deny: { title: "The source or access check failed.", status: "Refused", tone: "bad" },
};
const REASONS = {
  constructed_source_and_stored_facts_agree:
    "The agreement and the independently stored billing facts agree on the expected amount.",
  invoice_already_correct: "The issued amount already matches what the agreement requires.",
  adjustment_above_cap:
    "The difference exceeds the 100.00 SIM per-invoice cap, so no automatic correction can be requested.",
  request_unrelated: "The question isn't about billing, so no agreement terms were checked.",
  request_outside_constructed_vocabulary:
    "The instruction is too open-ended for this deterministic checker, so it routes to a person.",
  independent_stored_facts_disagree: "Stored billing facts disagree with the agreement. A person must decide.",
  model_and_stored_facts_agree: "The live model cited the price and seat count. Both match the registered agreement.",
  model_unavailable: "The live model could not complete the check. Review the agreement before proceeding.",
  model_evidence_disagrees: "The live model’s evidence did not match the registered agreement. Review is required.",
  model_allowance_exhausted: "The live model’s demo allowance is exhausted. No correction can be requested.",
  invalid_constructed_document: "The agreement text could not be parsed into known terms.",
};
const FIELDS = {
  annual_uplift_bps: "Annual uplift",
  conflicting_terms: "Conflicting terms",
  start: "Start date",
  end: "End date",
  seats: "Seats",
  unit_price_minor: "Unit price",
  uplift_anchor: "Uplift anchor",
};
function displayValue(field, raw) {
  // Presentation only; the exact cited span is always shown beneath it.
  if (field.endsWith("_minor") && /^-?\d+$/.test(raw)) return sim(raw);
  if (field.endsWith("_bps") && /^\d+$/.test(raw)) return `${(Number(raw) / 100).toFixed(2)}%`;
  return raw.replace(/^"(.*)"$/, "$1");
}
const reasonText = (r) => REASONS[r] || capital(words(r)) + ".";
const STATUS_TONE = { pending: "warn", approved: "good", applied: "good", rejected: "bad", expired: "bad" };

// ---- notices ----------------------------------------------------------------
let toastTimer = 0;
function notice(message, tone = "good") {
  const t = $("notice");
  clearTimeout(toastTimer);
  t.textContent = message || "";
  t.dataset.tone = tone;
  t.hidden = !message;
  if (message) toastTimer = setTimeout(() => (t.hidden = true), tone === "bad" ? 9000 : 5000);
}
const fail = (error) => notice(error.message, "bad");

// ---- API (unchanged contract) ----------------------------------------------
function csrf() {
  const name = document.querySelector('meta[name="csrf-cookie"]').content;
  const part = document.cookie
    .split(";")
    .map((x) => x.trim())
    .find((x) => x.startsWith(name + "="));
  return part ? decodeURIComponent(part.slice(name.length + 1)) : "";
}
async function api(path, { method = "GET", body } = {}) {
  const controller = new AbortController(),
    timer = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(path, {
      method,
      credentials: "same-origin",
      cache: "no-store",
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(method !== "GET" ? { "x-csrf-token": csrf() } : {}) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    const value = await response.json();
    if (!response.ok) {
      if (response.status === 403 && path !== "/api/login" && state.user) clearSession();
      throw new Error(value.error || "Request refused");
    }
    return value;
  } catch (error) {
    if (error.name === "AbortError")
      throw new Error("Response timed out. Refresh stored state before retrying; the action may have committed.");
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
function authTask(task) {
  const pending = state.authQueue.then(task, task);
  state.authQueue = pending.catch(() => {});
  return pending;
}

// ---- session ----------------------------------------------------------------
function clearAssessment() {
  state.sequence++;
  state.analysis = state.payload = null;
  $("assessment-panel").hidden = true;
  $("propose").hidden = true;
  guide();
}
function clearSession() {
  state.epoch++;
  state.user = null;
  state.cases = [];
  state.workbench = null;
  state.keys.clear();
  clearAssessment();
  if ($("confirm").open) $("confirm").close("cancel");
  $("workspace").hidden = true;
  $("identity").hidden = true;
  $("login-panel").hidden = false;
  for (const id of ["proposals", "ledger", "citations", "timing", "case-list"]) $(id).replaceChildren();
  $("document").value = "";
  $("password").value = "";
}

// ---- guidance + progress ----------------------------------------------------
function guide() {
  const user = state.user,
    wb = state.workbench;
  if (!user) return;
  const proposals = wb ? wb.proposals : [],
    ledger = wb ? wb.ledger : [];
  const has = (s) => proposals.some((p) => p.status === s);
  const a = state.analysis;
  const ready = a && a.action === "proposable";
  let text;
  if (user.role === "reviewer") {
    if (has("pending")) text = "A correction is waiting for you. Review the exact change, then approve or reject it.";
    else if (has("approved")) text = "Approved. Sign out so the operator can apply the correction.";
    else if (ledger.length) text = "Committed. The ledger holds one receipt per operation.";
    else text = "Nothing to review yet. Sign in as the operator to request a correction.";
  } else if (has("approved")) text = "Approved by the reviewer. Apply the correction to commit a ledger receipt.";
  else if (has("pending")) text = "Waiting for review. Sign out and sign in as the reviewer to decide.";
  else if (ready) text = "Request approval. Nothing on the invoice changes until a different person agrees.";
  else if (a) text = "Try another scenario or question to see how the agent routes it.";
  else if (ledger.length)
    text = "Committed. Use “Verify duplicate delivery” to confirm a retry returns the same receipt — or pick another scenario.";
  else text = "Pick a scenario, then check the agreement against the registered invoice.";
  $("guide-text").textContent = text;

  const any = proposals.length > 0,
    decided = proposals.some((p) => p.status !== "pending"),
    committed = ledger.length > 0;
  const steps = {
    check: a || any ? "done" : "current",
    request: any ? "done" : ready ? "current" : "upcoming",
    review: decided ? "done" : has("pending") ? "current" : "upcoming",
    ledger: committed && !has("approved") ? "done" : has("approved") ? "current" : "upcoming",
  };
  if (!Object.values(steps).includes("current")) steps.check = steps.check === "done" ? "done" : "current";
  for (const li of $("steps").children) {
    const s = steps[li.dataset.step];
    li.dataset.state = s;
    li.firstElementChild.setAttribute("aria-current", s === "current" ? "step" : "false");
  }
}

// ---- source -----------------------------------------------------------------
function selectedCase() {
  const checked = document.querySelector('input[name="case"]:checked');
  return checked ? state.cases.find((x) => x.case_id === checked.value) : undefined;
}
function selectedQuestion() {
  const checked = document.querySelector('input[name="question"]:checked');
  return checked ? checked.value : "Check this invoice.";
}
function selectCase() {
  clearAssessment();
  const c = selectedCase();
  if (!c) return;
  $("document").value = c.document;
  $("invoice-title").textContent = c.title;
  $("invoice-amount").textContent = money(c.invoice_minor);
}
function renderCases(catalog) {
  $("case-list").replaceChildren();
  catalog.forEach((c, index) => {
    const label = node("label", undefined, "case");
    const input = node("input");
    input.type = "radio";
    input.name = "case";
    input.value = c.case_id;
    input.checked = index === 0;
    input.addEventListener("change", selectCase);
    label.append(input, node("strong", c.title), node("small", `Issued ${sim(c.invoice_minor)}`));
    $("case-list").append(label);
  });
}

// ---- review dialog ----------------------------------------------------------
function confirmAction({ title, copy, go, danger, rows }) {
  const dialog = $("confirm");
  $("confirm-title").textContent = title;
  $("confirm-copy").textContent = copy;
  $("confirm-go").textContent = go;
  $("confirm-go").classList.toggle("danger", !!danger);
  $("confirm-details").replaceChildren();
  for (const [name, value, mono] of rows) {
    const row = node("div");
    row.append(node("dt", name), node("dd", value, mono ? "mono" : ""));
    $("confirm-details").append(row);
  }
  dialog.returnValue = "";
  dialog.showModal();
  $("confirm-go").focus();
  return new Promise((resolve) =>
    dialog.addEventListener("close", () => resolve(dialog.returnValue === "confirm"), { once: true }),
  );
}

// ---- rendering --------------------------------------------------------------
function button(text, action, cls = "primary small") {
  const b = node("button", text, cls);
  b.type = "button";
  b.onclick = async () => {
    const epoch = state.epoch;
    b.disabled = true;
    try {
      await action();
    } catch (error) {
      if (epoch === state.epoch) fail(error);
    } finally {
      b.disabled = false;
    }
  };
  return b;
}
function meta(parts) {
  const m = node("div", undefined, "row-meta");
  for (const [k, v] of parts) {
    const s = node("span", k + " ");
    s.append(node("b", v));
    m.append(s);
  }
  return m;
}
function proposalRows(workbench) {
  $("proposals").replaceChildren();
  const proposals = workbench.proposals;
  for (const p of [...proposals].reverse()) {
    const row = node("article", undefined, "row"),
      main = node("div", undefined, "row-main");
    const title = node("div", undefined, "row-title");
    const status = node("span", capital(p.status), "status");
    status.dataset.tone = STATUS_TONE[p.status] || "neutral";
    title.append(status, node("span", p.command.resource_id, "rid"));
    const figure = node("div", undefined, "row-figure");
    figure.append(
      document.createTextNode(`${signed(p.adjustment_minor)} SIM`),
      node("span", `  ·  new total ${sim(p.command.invoice_amount_minor)}`, "soft"),
    );
    main.append(
      title,
      figure,
      meta([
        ["Version", String(p.command.expected_version)],
        ["Proposed by", p.proposer_id],
        ["Reviewer", p.reviewer_id || "pending"],
      ]),
    );
    const actions = node("div", undefined, "actions");
    if (state.user.role === "reviewer" && p.status === "pending") {
      for (const decision of ["reject", "approve"]) {
        const approve = decision === "approve";
        actions.append(
          button(
            approve ? "Approve" : "Reject",
            async () => {
              const ok = await confirmAction({
                title: approve ? "Approve this exact change?" : "Reject this change?",
                copy: approve
                  ? "Your approval binds this payload and record version. The operator applies it next; the invoice is unchanged until then."
                  : "No invoice change will be made. The operator would need a fresh request after reassessment.",
                go: approve ? "Approve exact change" : "Reject change",
                danger: !approve,
                rows: [
                  ["Invoice", p.command.resource_id, true],
                  ["Expected version", String(p.command.expected_version)],
                  ["New total", sim(p.command.invoice_amount_minor)],
                  ["Adjustment", `${signed(p.adjustment_minor)} SIM`],
                  ["Proposed by", p.proposer_id],
                  ["Action digest", p.action_digest.slice(0, 16) + "…", true],
                ],
              });
              if (!ok) return;
              const epoch = state.epoch;
              await api(`/api/proposals/${encodeURIComponent(p.operation_id)}/review`, {
                method: "POST",
                body: { decision, action_digest: p.action_digest },
              });
              if (epoch !== state.epoch) return;
              notice(approve ? "Approved. The invoice has not been changed yet." : "Rejected. No invoice change.");
              await refresh();
            },
            approve ? "primary small" : "ghost small",
          ),
        );
      }
    }
    if (state.user.role === "operator" && p.status === "approved") {
      actions.append(
        button("Apply correction", async () => {
          const epoch = state.epoch;
          const result = await api(`/api/proposals/${encodeURIComponent(p.operation_id)}/apply`, {
            method: "POST",
            body: {},
          });
          if (epoch !== state.epoch) return;
          if (result.committed) notice("Committed. The ledger now proves the SIM invoice change.");
          else notice("No committed receipt returned.", "bad");
          clearAssessment();
          await refresh();
          $("step-ledger").scrollIntoView({ block: "start" });
        }),
      );
    }
    if (state.user.role === "operator" && p.status === "applied") {
      actions.append(
        button(
          "Verify duplicate delivery",
          async () => {
            const epoch = state.epoch;
            await api(`/api/proposals/${encodeURIComponent(p.operation_id)}/apply`, { method: "POST", body: {} });
            if (epoch !== state.epoch) return;
            notice("Same receipt returned. The ledger still has one entry for this operation.");
            await refresh();
          },
          "ghost small",
        ),
      );
    }
    row.append(main, actions);
    $("proposals").append(row);
  }
  if (!proposals.length)
    $("proposals").append(node("p", "No approval requests yet. As the operator, check an eligible agreement and request approval.", "empty"));
}
function ledgerRows(workbench) {
  $("ledger").replaceChildren();
  for (const entry of [...workbench.ledger].reverse()) {
    const row = node("article", undefined, "row receipt"),
      left = node("div", undefined, "row-left"),
      main = node("div", undefined, "row-main");
    const title = node("div", undefined, "row-title");
    title.append(node("span", entry.resource_id, "rid"), node("span", capital(words(entry.kind)), "status"));
    main.append(
      title,
      meta([
        ["Version", `${entry.before_version} → ${entry.after_version}`],
        ["Reviewed by", entry.reviewer_id],
        ["Committed", when(entry.committed_at)],
      ]),
    );
    left.append(node("span", "✓", "receipt-icon"), main);
    const delta = BigInt(entry.delta_minor);
    row.append(left, node("div", `${signed(entry.delta_minor)} SIM`, "row-figure " + (delta < 0n ? "amount-neg" : "amount-pos")));
    $("ledger").append(row);
  }
  if (!workbench.ledger.length)
    $("ledger").append(node("p", "No committed adjustments yet. A request or approval is not a receipt.", "empty"));
  const n = workbench.ledger.length;
  $("ledger-count").textContent = `${n} receipt${n === 1 ? "" : "s"}`;
}
function renderAnalysis(result) {
  const outcome = OUTCOMES[result.action] || { title: "No correction proposed.", status: words(result.action), tone: "neutral" };
  const panel = $("assessment-panel");
  panel.hidden = false;
  panel.dataset.tone = outcome.tone;
  $("assessment-state").textContent = outcome.status;
  $("assessment-state").dataset.tone = outcome.tone;
  $("finding-title").textContent = outcome.title;
  $("finding-reason").textContent = reasonText(result.reason);
  $("issued").textContent = sim(result.issued_minor);
  $("expected").textContent = sim(result.expected_minor);
  $("delta").textContent = result.delta_minor === null || result.delta_minor === undefined ? "—" : `${signed(result.delta_minor)} SIM`;
  $("citations").replaceChildren();
  const cited = result.citations.map((citation) => {
    const quote = String(citation.quote);
    const eq = quote.indexOf("=");
    const raw = eq >= 0 ? quote.slice(eq + 1) : quote;
    return { citation, quote, raw, unset: raw === "null" || raw === "[]" };
  });
  cited.sort((x, y) => Number(x.unset) - Number(y.unset));
  for (const { citation, quote, raw, unset } of cited) {
    const item = node("div", undefined, "citation");
    // Wire integers arrive as decimal strings; add offsets as numbers, not by string concatenation.
    const start = Number(citation.start);
    const where = Number.isSafeInteger(start) && start >= 0 ? ` · chars ${start}–${start + quote.length}` : "";
    item.append(
      node("span", FIELDS[citation.field] || capital(words(citation.field)), "field"),
      node("span", unset ? "not set" : displayValue(citation.field, raw), "value" + (unset ? " unset" : "")),
      node("span", `“${quote}”${where}`, "span"),
    );
    $("citations").append(item);
  }
  $("citation-count").textContent = String(result.citations.length);
  if (!result.citations.length)
    $("citations").append(node("p", "No agreement terms were extracted for this request.", "no-evidence"));
  $("propose").hidden = result.action !== "proposable" || state.user.role !== "operator";
  $("proposal-note").textContent =
    result.action === "proposable"
      ? state.user.role === "operator"
        ? "Requesting approval changes no invoice. A different reviewer must approve the exact action, then you apply it."
        : "Only the operator can request this correction."
      : "No executable correction is available for this result.";
  guide();
}

// ---- flows ------------------------------------------------------------------
async function refresh() {
  const epoch = state.epoch,
    sequence = ++state.sequence;
  const workbench = await api("/api/workbench");
  if (epoch !== state.epoch || sequence !== state.sequence || !state.user) return;
  state.workbench = workbench;
  proposalRows(workbench);
  ledgerRows(workbench);
  guide();
  const timing = await api("/walkthrough-api/timing");
  if (epoch !== state.epoch || sequence !== state.sequence || !state.user) return;
  $("timing").replaceChildren();
  for (const [stage, value] of Object.entries(timing.stages)) {
    if (!value.observations) continue;
    const item = node("div");
    item.append(
      node("strong", `${(value.p95_seconds * 1000).toFixed(2)} ms`),
      node("span", `${words(stage)} · p95 · ${value.observations} obs.`),
    );
    $("timing").append(item);
  }
}
async function openSession(user, epoch) {
  if (epoch !== state.epoch) return;
  state.user = user;
  $("signed-as").textContent = user.username;
  $("signed-role").textContent = user.role;
  $("signed-role").className = "role-pill " + user.role;
  $("avatar").textContent = String(user.username).replace(/^demo-/, "").slice(0, 2);
  $("identity").hidden = false;
  $("login-panel").hidden = true;
  $("workspace").hidden = false;
  guide();
  const catalog = await api("/walkthrough-api/cases");
  if (epoch !== state.epoch || !state.user) return;
  state.cases = catalog;
  renderCases(catalog);
  selectCase();
  await refresh();
  // A reviewer's work is the queue, not the source form: bring it into view.
  if (epoch === state.epoch && state.user && state.user.role === "reviewer" && state.workbench &&
      state.workbench.proposals.some((p) => p.status === "pending"))
    $("step-review").scrollIntoView({ block: "start" });
}

$("login").onsubmit = (event) => {
  event.preventDefault();
  const username = $("username").value,
    password = $("password").value;
  const epoch = ++state.epoch;
  $("password").value = "";
  authTask(async () => {
    const user = await api("/api/login", { method: "POST", body: { username, password } });
    if (epoch !== state.epoch) return;
    notice("");
    void openSession(user, epoch).catch((error) => {
      if (epoch === state.epoch) {
        clearSession();
        fail(error);
      }
    });
  }).catch((error) => {
    if (epoch === state.epoch) fail(error);
  });
};
$("logout").onclick = () => {
  clearSession();
  notice("Private view cleared. Confirming server sign-out…");
  authTask(() => api("/api/logout", { method: "POST", body: {} })).then(
    () => notice("Signed out."),
    () => notice("Private view cleared; server sign-out could not be confirmed.", "bad"),
  );
};
for (const radio of document.querySelectorAll('input[name="question"]')) radio.addEventListener("change", clearAssessment);
$("document").oninput = clearAssessment;
$("analyze").onclick = async () => {
  if (!state.user) return;
  const c = selectedCase();
  if (!c) return;
  const epoch = state.epoch;
  const payload = { case_id: c.case_id, document: $("document").value, question: selectedQuestion() };
  $("analyze").disabled = true;
  clearAssessment();
  const fence = state.sequence;
  try {
    const result = await api("/walkthrough-api/analyze", { method: "POST", body: payload });
    if (epoch !== state.epoch || fence !== state.sequence || !state.user) return;
    state.analysis = result;
    state.payload = payload;
    renderAnalysis(result);
    $("assessment-panel").scrollIntoView({ block: "start" });
  } catch (error) {
    if (epoch === state.epoch) fail(error);
  } finally {
    $("analyze").disabled = false;
  }
};
$("propose").onclick = async () => {
  if (!state.user || !state.analysis || !state.payload) return;
  const epoch = state.epoch,
    a = state.analysis,
    payload = state.payload;
  const key = [state.user.tenant_id, state.user.username, a.case_id, a.expected_version, a.analysis_digest].join("|");
  if (!state.keys.has(key)) state.keys.set(key, crypto.randomUUID());
  $("propose").disabled = true;
  try {
    await api("/walkthrough-api/propose", {
      method: "POST",
      body: { analysis: payload, expected_version: version(a.expected_version), analysis_digest: a.analysis_digest, operation_id: state.keys.get(key) },
    });
    if (epoch !== state.epoch) return;
    notice("Approval request stored. Sign in as the reviewer to approve the exact change.");
    await refresh();
    $("step-review").scrollIntoView({ block: "start" });
  } catch (error) {
    if (epoch === state.epoch) fail(error);
  } finally {
    $("propose").disabled = false;
  }
};
function version(value) {
  const n = Number(value);
  if (!Number.isSafeInteger(n) || n < 0) throw new Error("Record version requires operator review.");
  return n;
}
$("refresh").onclick = () => refresh().catch(fail);
const startup = state.epoch;
api("/api/session")
  .then((user) => openSession(user, startup))
  .catch(() => {
    if (startup === state.epoch) clearSession();
  });
