"use strict";
const $ = (id) => document.getElementById(id);
let user = null, data = null, incident = null, sessionEpoch = 0, viewVersion = 0;
let authQueue = Promise.resolve();
class StaleSession extends Error {}
const label = (value) => value.replaceAll("_", " ");
function el(tag, text, cls) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (cls) node.className = cls;
  return node;
}
function money(value) {
  const n = BigInt(value), mag = n < 0n ? -n : n;
  return (n < 0n ? "-" : "") + (mag / 100n).toLocaleString("en-US") + "." + (mag % 100n).toString().padStart(2, "0");
}
function notice(text) { $("notice").textContent = text; $("notice").hidden = !text; }
function clearLocalSession() {
  user = data = incident = null;
  viewVersion += 1;
  $("workspace").hidden = $("identity").hidden = true;
  $("login-panel").hidden = false;
  $("who").textContent = $("title").textContent = $("updated").textContent = "";
  $("password").value = "";
  for (const id of ["incidents", "budget", "shipments", "context", "notices", "details", "decisions"]) $(id).replaceChildren();
  if ($("detail").open) $("detail").close();
}
function serializeAuth(handler) {
  const next = authQueue.catch(() => {}).then(handler);
  authQueue = next.catch(() => {});
  return next;
}
function csrf() {
  const name = document.querySelector('meta[name="csrf-cookie"]').content;
  return decodeURIComponent(document.cookie.split("; ").find((v) => v.startsWith(name + "="))?.slice(name.length + 1) || "");
}
async function request(path, body, token) {
  const epoch = sessionEpoch;
  const response = await fetch(path, {method: body === undefined ? "GET" : "POST", credentials: "same-origin",
    headers: body === undefined ? {} : {"Content-Type": "application/json", "X-CSRF-Token": token === undefined ? csrf() : token},
    body: body === undefined ? undefined : JSON.stringify(body)});
  let result;
  try { result = await response.json(); }
  catch { throw new Error("Incomplete response. Refresh before retrying; an action may already be saved."); }
  if (epoch !== sessionEpoch) throw new StaleSession();
  if (!response.ok) throw new Error(({403: "Access or session verification failed. Check your role or sign in again.",
    409: "State changed or review is required. Refresh and reassess the exact proposal.",
    422: "Invalid action. Check the displayed proposal.", 404: "Record unavailable in your scope.",
    503: "State service unavailable. Refresh before retrying; an action may already be saved."})[response.status] || "Request failed. Refresh before retrying.");
  return result;
}
async function action(button, handler) {
  const epoch = sessionEpoch, principal = user, event = incident;
  if (!principal) return;
  button.disabled = true;
  try {
    await handler();
    if (epoch === sessionEpoch && user === principal && incident === event) await refresh();
  } catch (error) {
    if (epoch !== sessionEpoch || user !== principal || incident !== event || error instanceof StaleSession) return;
    notice(error.message);
    try { await refresh(); } catch {}
  } finally { button.disabled = false; }
}
function button(text, handler, cls = "secondary") {
  const b = el("button", text, cls); b.type = "button";
  b.addEventListener("click", () => action(b, handler)); return b;
}
function showDetail(row) {
  const event = incident, snapshot = row.snapshot;
  $("details").replaceChildren(); $("decisions").replaceChildren();
  if (!snapshot) {
    $("details").append(el("p", "No SIM proposal exists. " + label(row.freshness) + "."));
  } else {
    const p = snapshot.proposal, r = snapshot.receipt, dl = el("dl");
    for (const [name, value] of [["Shipment", row.fact.shipment_id], ["State", label(row.state)], ["Proposer", p.proposer_id],
      ["Reviewer", p.reviewer_id || "No separate review recorded"], ["Action", p.command.action], ["Cost", money(p.option.cost_minor) + " SIM"],
      ["Proposal expires", p.expires_at], ["Committed", r?.committed_at || "No receipt"], ["Confirmation due", r?.confirmation_deadline || "No receipt"],
      ["Fingerprint", p.payload_sha256]]) dl.append(el("dt", name), el("dd", value));
    $("details").append(dl, el("h3", "Stored command"), el("pre", JSON.stringify(p.command, null, 2)),
      el("p", "Estimates are planning inputs. SIM confirmation records acceptance of a simulated action; it does not confirm shipment delivery.", "small"));
    const selection = {event_id: event, shipment_id: row.fact.shipment_id, payload_sha256: p.payload_sha256};
    const decide = async (path, extra = {}) => { await request(path, {...selection, ...extra}); if ($("detail").open) $("detail").close(); };
    if (user.role === "reviewer" && row.state === "pending") {
      $("decisions").append(button("Approve exact SIM proposal", () => decide("/api/review", {approve: true}), ""),
        button("Reject proposal", () => decide("/api/review", {approve: false})));
    }
    if (user.role === "operator" && row.state === "approved") $("decisions").append(button("Commit approved SIM action", () => decide("/api/apply"), ""));
    if (user.role === "confirmer" && row.state === "awaiting_confirmation") {
      $("decisions").append(button("Record SIM confirmation", () => decide("/api/confirm", {success: true}), ""),
        button("Record SIM failure", () => decide("/api/confirm", {success: false})));
    }
  }
  $("detail").showModal();
}
function render() {
  if (!user || !data) return;
  $("login-panel").hidden = true; $("workspace").hidden = $("identity").hidden = false;
  $("who").textContent = user.username + " / " + user.role + " / " + user.tenant_id;
  $("title").textContent = data.label;
  $("updated").textContent = "Facts checked at " + new Date(data.as_of).toLocaleString();
  $("assess").hidden = user.role !== "operator";
  $("budget").replaceChildren();
  for (const [name, value, unit] of [["Incident budget", money(data.budget.cap_minor), "SIM cap"], ["Committed", money(data.budget.spent_minor), "SIM debited"],
    ["Remaining", money(data.budget.remaining_minor), "SIM available"], ["Replans used", data.budget.replans_used + " / 2", "Incident-wide limit"]]) {
    const metric = el("div"); metric.append(el("div", name, "metric-label"), el("div", value, "metric-value"), el("div", unit, "metric-unit")); $("budget").append(metric);
  }
  $("shipments").replaceChildren();
  for (const row of data.shipments) {
    const tr = el("tr"), fact = row.fact, p = row.snapshot?.proposal;
    const td = el("td", fact.shipment_id); td.append(el("span", fact.region + " · " + fact.provenance, "small"), el("span", label(row.freshness), "small"));
    tr.append(td, el("td", fact.estimated_delay_hours + " h (estimate)"), el("td", p ? p.command.action + " / " + money(p.option.cost_minor) + " SIM" : "No proposal"));
    const state = el("td"); state.append(el("span", label(row.state), "badge " + row.state));
    const detail = el("td"); detail.append(button("View", () => showDetail(row)));
    tr.append(state, detail); $("shipments").append(tr);
  }
  $("context").replaceChildren();
  const c = data.context;
  $("context").append(el("p", c?.alert ? (c.source_kind === "invented" ? "Invented" : "Independent recorded") + " alert context: " + c.alert.event + " · " + label(data.alert_state) + ". No weather-to-shipment causal relationship has been verified." : "No alert context attached. Shipment observations determine action eligibility."));
  $("notices").replaceChildren();
  for (const n of data.notices) {
    const card = el("article", undefined, "notice-card" + (n.read ? " read" : "")), copy = el("div");
    copy.append(el("p", n.body), el("p", new Date(n.created_at).toLocaleString() + " · " + label(n.state), "small")); card.append(copy);
    if (!n.read) card.append(button("Mark read", () => request("/api/notices/" + encodeURIComponent(n.notice_id) + "/read", {})));
    else card.append(el("span", "Read", "small"));
    $("notices").append(card);
  }
}
async function refresh() {
  if (!user || !incident) return;
  const epoch = sessionEpoch, principal = user, event = incident, version = ++viewVersion;
  const result = await request("/api/workbench/" + encodeURIComponent(event));
  if (epoch !== sessionEpoch || principal !== user || version !== viewVersion || event !== incident) return;
  data = result; render();
}
async function loadIncidents() {
  const epoch = sessionEpoch, principal = user;
  const result = await request("/api/incidents");
  if (epoch !== sessionEpoch || principal !== user) return;
  $("incidents").replaceChildren();
  for (const item of result.incidents) {
    const b = button(item.label, async () => {
      incident = item.event_id; data = null; viewVersion += 1;
      for (const id of ["budget", "shipments", "context", "notices", "details", "decisions"]) $(id).replaceChildren();
      if ($("detail").open) $("detail").close();
      document.querySelectorAll("#incidents button").forEach((node) => node.setAttribute("aria-current", node === b ? "page" : "false"));
      await refresh();
    });
    b.setAttribute("aria-current", item === result.incidents[0] ? "page" : "false"); $("incidents").append(b);
  }
  incident = result.incidents[0]?.event_id || null; await refresh();
}
async function signIn(username, password) {
  const epoch = ++sessionEpoch;
  clearLocalSession(); notice("");
  try {
    const result = await serializeAuth(async () => {
      if (epoch !== sessionEpoch) throw new StaleSession();
      return request("/api/login", {username, password});
    });
    if (epoch !== sessionEpoch) return;
    user = result;
    await loadIncidents();
  } catch (error) {
    if (epoch === sessionEpoch && !(error instanceof StaleSession)) notice(error.message);
  }
}
async function signOut() {
  const token = csrf(), epoch = ++sessionEpoch;
  clearLocalSession(); notice("");
  try {
    await serializeAuth(() => request("/api/logout", {}, token));
    if (epoch === sessionEpoch) notice("Signed out.");
  } catch {
    if (epoch === sessionEpoch) notice("Private view cleared. Server sign-out could not be confirmed; retry signing out or close this browser session.");
  }
}
$("login").addEventListener("submit", (event) => {
  event.preventDefault();
  signIn($("username").value, $("password").value);
});
$("logout").addEventListener("click", signOut);
$("refresh").addEventListener("click", () => action($("refresh"), async () => {}));
$("assess").addEventListener("click", () => action($("assess"), () => request("/api/assess", {event_id: incident})));
$("close-detail").addEventListener("click", () => $("detail").close());
const startupEpoch = sessionEpoch;
request("/api/session").then(async (result) => {
  if (startupEpoch !== sessionEpoch) return;
  user = result; await loadIncidents();
}).catch((error) => { if (!(error instanceof StaleSession) && startupEpoch === sessionEpoch) clearLocalSession(); });
