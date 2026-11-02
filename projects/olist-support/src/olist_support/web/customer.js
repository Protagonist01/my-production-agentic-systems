"use strict";
const $ = (id) => document.getElementById(id);
let csrfName = null, identity = null, selection = null, generation = 0, busy = false, sessionEpoch = 0;
let authQueue = Promise.resolve();
function authWork(work) {
  const result = authQueue.then(work, work);
  authQueue = result.catch(() => {});
  return result;
}
const money = (n) => `${Math.floor(n / 100)}.${String(n % 100).padStart(2, "0")} SIM`;
function clearProposal() {
  selection = null;
  $("customer-proposal").hidden = true;
  $("customer-confirm").textContent = "Confirm full refund";
  for (const id of ["customer-order", "customer-request", "customer-amount", "customer-expiry"]) $(id).textContent = "";
}
function clearSessionView() {
  clearProposal(); $("customer-list").replaceChildren();
  $("customer-orders").hidden = true; notice("");
}
function notice(text) { $("customer-notice").textContent = text; }
function cookie(name) {
  const entry = document.cookie.split("; ").find((x) => x.startsWith(name + "="));
  return entry ? decodeURIComponent(entry.slice(name.length + 1)) : "";
}
async function api(path, body) {
  const epoch = sessionEpoch;
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 120000);
  try {
    const headers = body === undefined ? {} : {"Content-Type":"application/json", "X-CSRF-Token":cookie(csrfName)};
    const response = await fetch(path, {method:body === undefined ? "GET" : "POST", credentials:"same-origin", headers,
      body:body === undefined ? undefined : JSON.stringify(body), signal:controller.signal});
    const value = await response.json();
    if (response.status === 403 && identity && epoch === sessionEpoch) {
      ++generation; identity = null; csrfName = null; clearSessionView();
      $("customer-login").hidden = false;
      notice("Your session or order access changed. Sign in again.");
    }
    if (!response.ok) throw new Error(response.status === 403 ? "Your session or order access does not allow this action. Sign in again."
      : response.status === 409 ? "This confirmation changed, expired or needs review. Refresh the request before continuing."
      : "The request could not be completed. Refresh before trying again.");
    return value;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The response timed out. Refresh the request; a refund may already have committed.");
    throw error;
  } finally { clearTimeout(timer); }
}
async function refresh() {
  const ticket = ++generation; clearProposal();
  const rows = await api("/api/customer/cases");
  if (!identity || ticket !== generation) return;
  const list = $("customer-list"); list.replaceChildren();
  if (!rows.length) { notice("There are no requests for your orders."); return; }
  for (const row of rows) {
    const card = document.createElement("section"), label = document.createElement("p"), button = document.createElement("button");
    label.textContent = `Order ${row.order_id}: ${row.committed ? "Refund committed" : "No refund confirmed"}`;
    button.textContent = row.committed ? "View result" : "Review refund details";
    button.className = "text-button";
    button.addEventListener("click", async () => {
      if (busy) return;
      const current = ++generation; clearProposal();
      try {
        if (row.committed) {
          const result = await api(`/api/customer/cases/${encodeURIComponent(row.case_id)}`);
          if (current === generation && identity) notice(result.message);
          return;
        }
        const offer = await api(`/api/customer/cases/${encodeURIComponent(row.case_id)}/challenge`, {});
        if (current !== generation || !identity) return;
        if (offer.case_id !== row.case_id || offer.order_id !== row.order_id || offer.action !== "refund" || offer.unit !== "SIM"
          || !Number.isInteger(offer.amount_minor) || offer.amount_minor < 1 || offer.amount_minor > 10000
          || typeof offer.challenge !== "string" || offer.challenge.length < 32) throw new Error("Refund details could not be verified.");
        selection = Object.freeze({...offer});
        $("customer-order").textContent = `Order: ${offer.order_id}`;
        $("customer-request").textContent = `Request: ${offer.request_text}`;
        $("customer-amount").textContent = `Full refund: ${money(offer.amount_minor)}`;
        $("customer-expiry").textContent = "This confirmation expires in five minutes. Changed order details require a new confirmation.";
        $("customer-confirm").textContent = `Confirm full refund of ${money(offer.amount_minor)}`;
        $("customer-proposal").hidden = false; notice("");
      } catch (error) { if (current === generation) notice(error.message); }
    });
    card.append(label, button); list.append(card);
  }
}
$("customer-confirm").addEventListener("click", async () => {
  if (!selection || busy) return;
  busy = true; const offer = selection, ticket = generation;
  $("customer-confirm").disabled = true;
  const body = {challenge:offer.challenge,action:"refund",amount_minor:offer.amount_minor,unit:"SIM"};
  try {
    await api(`/api/customer/cases/${encodeURIComponent(offer.case_id)}/confirm`, body);
    if (!identity || ticket !== generation) return;
    notice("Your confirmation is saved. Waiting for the refund result.");
    const result = await api(`/api/customer/cases/${encodeURIComponent(offer.case_id)}/execute`, body);
    if (identity && ticket === generation) { clearProposal(); notice(result.message); await refresh(); }
  } catch (error) { if (ticket === generation) { clearProposal(); notice(error.message); } }
  finally { busy = false; $("customer-confirm").disabled = false; }
});
$("customer-cancel").addEventListener("click", () => { if (!busy) { ++generation; clearProposal(); notice("No refund was confirmed."); } });
$("customer-refresh").addEventListener("click", () => { if (!busy) refresh().catch((error) => notice(error.message)); });
$("customer-logout").addEventListener("click", async () => {
  const epoch = ++sessionEpoch; ++generation; identity = null; clearSessionView();
  try { await authWork(() => api("/api/logout", {})); }
  catch { if (epoch === sessionEpoch) notice("Sign-out could not be confirmed. Close this page and sign in again."); }
  if (epoch === sessionEpoch) {
    csrfName = null; $("customer-orders").hidden = true; $("customer-login").hidden = false;
  }
});
async function establish(value, epoch) {
  if (epoch !== sessionEpoch) return;
  if (value.principal.role !== "customer") throw new Error("Use a customer account here. Staff use the support desk.");
  identity = value.principal; csrfName = value.csrf_cookie;
  $("customer-login").hidden = true; $("customer-orders").hidden = false; await refresh();
}
$("customer-login").addEventListener("submit", async (event) => {
  event.preventDefault();
  const epoch = ++sessionEpoch, body = {username:$("username").value,password:$("password").value};
  ++generation; identity = null; clearSessionView(); $("password").value = "";
  try {
    const value = await authWork(async () => {
      const response = await api("/api/login", body);
      csrfName = response.csrf_cookie;
      return response;
    });
    await establish(value, epoch);
  } catch (error) { if (epoch === sessionEpoch) notice(error.message); }
});
const initialEpoch = sessionEpoch;
authWork(async () => {
  const value = await api("/api/session"); csrfName = value.csrf_cookie; return value;
}).then((value) => establish(value, initialEpoch)).catch(() => {
  if (initialEpoch === sessionEpoch) notice("Sign in to review your orders. No refund is confirmed by signing in.");
});
