"use strict";
const $ = id => document.getElementById(id);
let current = null;
const csrfName = document.currentScript.dataset.csrf;
async function api(path, body) {
  const token = document.cookie.split("; ").find(x => x.startsWith(csrfName + "="));
  const response = await fetch(path, {method: body ? "POST" : "GET", headers: {
    "Content-Type": "application/json", "X-CSRF-Token": token ? token.slice(csrfName.length + 1) : ""
  }, body: body ? JSON.stringify(body) : undefined});
  if (!response.ok) throw new Error("Request failed (" + response.status + "). Refresh before retrying.");
  return response.json();
}
async function safely(action) {
  try { await action(); $("message").textContent = "Saved / refreshed."; }
  catch (error) { $("message").textContent = error.message; }
}
$("login").onsubmit = event => { event.preventDefault(); safely(async () => {
  const fields = new FormData(event.target);
  await api("/api/login", Object.fromEntries(fields)); event.target.reset(); await load();
}); };
async function load() {
  const rows = await api("/api/v2/evaluation"); $("assignments").replaceChildren();
  for (const row of rows.cases) {
    const button = document.createElement("button"); button.textContent = row.case_id;
    button.onclick = () => safely(() => show(row.case_id)); $("assignments").append(button);
  }
}
async function show(id) {
  const changed = current?.case_id !== id;
  current = await api("/api/v2/evaluation/" + encodeURIComponent(id));
  $("case").hidden = false; $("case-title").textContent = id;
  $("arm").textContent = current.arm + (current.accepted_at ? " — final triage accepted" : "");
  $("basis").textContent = "Measurement basis: " + (current.measurement_basis || "unknown").replaceAll("_", " ") +
    ". Active seconds recorded: " + current.active_seconds;
  $("narrative").textContent = current.complaint.narrative;
  const result = current.result;
  const prediction = result && result.prediction;
  $("candidate").textContent = current.arm === "manual" ? "Blinded manual assignment" :
    (result ? ["Suggested disposition: " + result.action.replaceAll("_", " "),
      "Scope: " + (result.scope || "not established").replaceAll("_", " "),
      "Product: " + (prediction?.product || "not established"),
      "Issue: " + (prediction?.issue || "not established"),
      "Priority: " + (prediction?.priority || "not established"),
      "Context: " + (prediction?.ambiguity || "not established"),
      ...(prediction?.evidence || []).map(e => "Supporting quote: “" + e.text + "”")
    ].join("\n") : "Waiting for candidate");
  $("product").replaceChildren();
  for (const product of Object.keys(current.taxonomy.pairs)) {
    const option = document.createElement("option"); option.textContent = product; $("product").append(option);
  }
  issues(); $("seconds").value = "0";
  if (changed) {
    $("scope").value = "in_scope"; $("priority").value = "uncertain";
    $("ambiguity").value = "ambiguous"; $("quote").value = ""; $("work-kind").value = "review";
  }
  if (current.final_result) {
    const final = current.final_result;
    $("scope").value = final.scope; $("quote").value = final.quotes[0] || "";
    if (final.classification) {
      $("product").value = final.classification.product; issues();
      $("issue").value = final.classification.issue;
      $("priority").value = final.classification.priority;
      $("ambiguity").value = final.classification.ambiguity;
    }
  }
  for (const control of $("judgment").elements) control.disabled = !!current.accepted_at;
  $("start").disabled = !!current.accepted_at || !!current.work_started;
  $("pause").disabled = !!current.accepted_at || !current.work_started;
  $("work-kind").disabled = !!current.accepted_at || !!current.work_started;
  $("seconds").disabled = !!current.accepted_at;
  if (current.work_started && current.work_kind) $("work-kind").value = current.work_kind;
  $("correct").disabled = !!current.accepted_at || !current.work_started;
  $("judgment").querySelector('button[type="submit"]').disabled = !!current.accepted_at || !current.work_started;
  // A browser acknowledgement follows rendering. Server wall time is separate from
  // model/process monotonic timing and must not be described as paint precision.
  if (!current.accepted_at) {
    await new Promise(resolve => requestAnimationFrame(resolve));
    const receipt = await api("/api/v2/evaluation/" + encodeURIComponent(id) + "/work", {
      command_id: crypto.randomUUID(), expected_version: current.version, operation: "visible"
    });
    current.version = receipt.version;
  }
}
function issues() {
  $("issue").replaceChildren();
  for (const issue of current.taxonomy.pairs[$("product").value] || []) {
    const option = document.createElement("option"); option.textContent = issue; $("issue").append(option);
  }
}
$("product").onchange = issues;
function judgment() {
  const quote = $("quote").value;
  return {scope: $("scope").value, confidence: 0.0, quotes: quote ? [quote] : [], classification:
    $("scope").value === "in_scope" ? {schema_version: 1, product: $("product").value,
      issue: $("issue").value, priority: $("priority").value, ambiguity: $("ambiguity").value,
      confidence: 0.0, quotes: quote ? [quote] : []} : null};
}
async function work(operation) {
  if (!current) throw new Error("Choose an assignment first.");
  await api("/api/v2/evaluation/" + encodeURIComponent(current.case_id) + "/work", {
    command_id: crypto.randomUUID(), expected_version: current.version, operation,
    work_kind: $("work-kind").value,
    active_seconds: ["start", "visible"].includes(operation) ? 0.0 : Number($("seconds").value),
    final: ["accept", "correct"].includes(operation) ? judgment() : null
  });
  await show(current.case_id);
}
for (const operation of ["start", "pause", "correct"]) $(operation).onclick = () => safely(() => work(operation));
$("judgment").onsubmit = event => { event.preventDefault(); safely(() => work("accept")); };
$("load").onclick = () => safely(load);
$("logout").onclick = () => safely(async () => {
  await api("/api/logout", {}); current = null; $("case").hidden = true; $("assignments").replaceChildren();
  $("narrative").textContent = ""; $("candidate").textContent = ""; $("case-title").textContent = "";
  $("basis").textContent = ""; $("arm").textContent = "";
  $("quote").value = ""; $("seconds").value = "0"; $("judgment").reset();
  $("product").replaceChildren(); $("issue").replaceChildren();
});
