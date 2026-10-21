"use strict";
const $ = (id) => document.getElementById(id);
let user = null,
  data = null,
  chosen = null,
  currentView = "findings";
const money = (n) => {
  if (n === null || n === undefined) return "—";
  const value = BigInt(n),
    mag = value < 0n ? -value : value;
  return (
    (value < 0n ? "-" : "") +
    (mag / 100n).toLocaleString("en-US") +
    "." +
    (mag % 100n).toString().padStart(2, "0")
  );
};
const version = (n) => {
  const value = Number(n);
  if (!Number.isSafeInteger(value) || value < 0)
    throw new Error(
      "This record version requires trusted administrator review.",
    );
  return value;
};
const label = (s) => s.replaceAll("_", " ");
function el(tag, text, cls) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (cls) node.className = cls;
  return node;
}
function notice(message) {
  $("notice").textContent = message;
  $("notice").hidden = !message;
}
function csrf() {
  const name = document.querySelector('meta[name="csrf-cookie"]').content;
  return (
    document.cookie
      .split("; ")
      .find((v) => v.startsWith(name + "="))
      ?.slice(name.length + 1) || ""
  );
}
async function request(path, body) {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    credentials: "same-origin",
    headers:
      body === undefined
        ? {}
        : {
            "Content-Type": "application/json",
            "X-CSRF-Token": decodeURIComponent(csrf()),
          },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let result = {};
  try {
    result = await response.json();
  } catch {
    throw new Error(
      "The service returned an incomplete response. Refresh before retrying.",
    );
  }
  if (!response.ok) {
    const messages = {
      403: "Access or session verification failed. Check your role or sign in again.",
      409: "The state changed or this action requires review. Refresh and reassess before retrying.",
      422: "The action is incomplete or invalid. Check the displayed record and try again.",
      503: "The state service is unavailable. Refresh before retrying; a previous action may already be saved.",
      404: "This record or proposal is unavailable in your scope.",
    };
    throw new Error(
      messages[response.status] ||
        "The request could not complete. Refresh before retrying.",
    );
  }
  return result;
}
function keyFor(kind, record, target = "", original = "") {
  const key = [
    user.tenant_id,
    user.username,
    kind,
    record.resource_id,
    record.version,
    target,
    original,
  ].join(":");
  const old = sessionStorage.getItem(key);
  if (old) return old;
  const value = crypto.randomUUID();
  sessionStorage.setItem(key, value);
  return value;
}
async function action(button, handler) {
  button.disabled = true;
  try {
    await handler();
    await refresh(false);
  } catch (error) {
    notice(error.message);
    try {
      await refresh(false);
    } catch {}
  } finally {
    button.disabled = false;
  }
}
function cell(row, text, cls) {
  const td = el("td", text, cls);
  row.append(td);
  return td;
}
function button(text, handler) {
  const b = el("button", text, "secondary");
  b.type = "button";
  b.addEventListener("click", () => action(b, () => handler(b)));
  return b;
}
function badge(text) {
  return el("span", label(text), "badge " + text);
}
function versionCell(row, id, version) {
  const td = cell(row, undefined, "resource");
  td.append(el("span", id), el("span", "VERSION " + version, "sub"));
}
function showView(name) {
  currentView = name;
  document
    .querySelectorAll(".view")
    .forEach((v) => (v.hidden = v.id !== "view-" + name));
  document.querySelectorAll(".tabs button").forEach((b) => {
    const active = b.dataset.view === name;
    b.classList.toggle("active", active);
    b.setAttribute("aria-current", active ? "page" : "false");
  });
}
function render() {
  $("login-panel").hidden = true;
  $("workspace").hidden = false;
  $("identity").hidden = false;
  $("who").textContent = user.username + " / " + user.role;
  $("updated").textContent = "As of " + new Date(data.at).toLocaleTimeString();
  const d = data.digest;
  $("totals").replaceChildren();
  for (const [name, value] of [
    ["Found", d.found_minor],
    ["Proposed", d.proposed_minor],
    ["Approved", d.approved_minor],
    ["Applied", d.applied_minor],
    ["Rejected", d.rejected_minor],
    ["Compensated", d.compensated_minor],
  ]) {
    const metric = el("div", undefined, "metric");
    metric.append(
      el("div", name + " · SIM", "metric-label"),
      el("div", money(value), "metric-value"),
    );
    $("totals").append(metric);
  }
  $("net").replaceChildren();
  for (const text of [
    "Net ledger movement: " + money(d.net_adjustment_minor) + " SIM",
    d.pending_count + " pending decisions",
    d.expired_count + " expired waits",
    d.ledger_entries + " permanent entries",
  ]) {
    $("net").append(el("span", text));
  }
  $("finding-count").textContent = data.findings.length;
  $("review-count").textContent = data.proposals.filter(
    (p) => p.status === "pending",
  ).length;
  $("ledger-count").textContent = data.ledger.length;
  $("findings").replaceChildren();
  for (const f of data.findings) {
    const tr = el("tr");
    versionCell(tr, f.resource_id, f.expected_version);
    cell(tr, money(f.current_minor), "number");
    cell(tr, money(f.should_be_minor), "number");
    cell(
      tr,
      money(f.delta_minor),
      "number " + (f.delta_minor ? "positive" : ""),
    );
    const status = cell(tr);
    status.append(badge(f.disposition), el("span", label(f.reason), "sub"));
    const td = cell(tr);
    if (user.role === "operator" && f.eligible) {
      td.append(
        button("Propose correction", async () => {
          await request("/api/proposals", {
            operation_id: keyFor("invoice_correct", {
              resource_id: f.resource_id,
              version: f.expected_version,
            }),
            kind: "invoice_correct",
            resource_id: f.resource_id,
            expected_version: version(f.expected_version),
          });
          notice(
            "Correction proposed. A separate reviewer must approve the exact change.",
          );
          showView("reviews");
        }),
      );
    } else
      td.append(
        el(
          "span",
          f.eligible ? "Separate operator" : "Review required",
          "small muted",
        ),
      );
    $("findings").append(tr);
  }
  $("findings-empty").hidden = !!data.findings.length;
  $("proposals").replaceChildren();
  for (const p of data.proposals) {
    const article = el("article", undefined, "proposal");
    const heading = el("div");
    heading.append(
      el("h4", label(p.command.kind)),
      el("span", p.command.resource_id, "resource"),
      el("span", p.operation_id, "sub"),
    );
    const detail = el("div");
    detail.append(
      badge(p.status),
      el("div", "Adjustment " + money(p.adjustment_minor) + " SIM", "small"),
      el(
        "div",
        (p.overdue && p.status !== "applied"
          ? "Deadline passed · refresh / sweep. "
          : "Review deadline · ") + new Date(p.expires_at).toLocaleString(),
        "deadline",
      ),
    );
    const actions = el("div", undefined, "actions");
    if (user.role === "reviewer" && p.status === "pending" && !p.overdue) {
      actions.append(
        button("Review exact action", () => {
          openReview(p);
        }),
      );
    }
    if (user.role === "operator" && p.status === "approved" && !p.overdue) {
      actions.append(
        button("Apply approved change", async () => {
          await request(
            "/api/proposals/" + encodeURIComponent(p.operation_id) + "/apply",
            {},
          );
          notice("Change committed. The permanent receipt is in the ledger.");
        }),
      );
    }
    if (p.status === "rejected" || p.status === "expired")
      actions.append(
        el(
          "span",
          "Create a fresh proposal after reassessment.",
          "small muted",
        ),
      );
    article.append(heading, detail, actions);
    $("proposals").append(article);
  }
  $("proposals-empty").hidden = !!data.proposals.length;
  $("ledger").replaceChildren();
  for (const receipt of [...data.ledger].reverse()) {
    const tr = el("tr");
    const td = cell(
      tr,
      new Date(receipt.committed_at).toLocaleString(),
      "resource",
    );
    td.append(el("span", receipt.operation_id, "sub"));
    cell(tr, label(receipt.kind));
    cell(tr, receipt.resource_id, "resource");
    cell(tr, receipt.before_version + " → " + receipt.after_version, "number");
    cell(tr, money(receipt.delta_minor), "number");
    const actionCell = cell(tr);
    const record = data.records.find(
      (r) => r.resource_id === receipt.resource_id,
    );
    if (user.role === "operator" && record && receipt.kind !== "compensate") {
      actionCell.append(
        button("Propose compensation", async () => {
          await request("/api/proposals", {
            operation_id: keyFor(
              "compensate",
              record,
              "",
              receipt.operation_id,
            ),
            kind: "compensate",
            resource_id: record.resource_id,
            expected_version: version(record.version),
            original_operation_id: receipt.operation_id,
          });
          notice("Compensation proposed. A separate reviewer must approve it.");
          showView("reviews");
        }),
      );
    }
    $("ledger").append(tr);
  }
  $("ledger-empty").hidden = !!data.ledger.length;
  const accounts = data.records.filter((r) => r.kind === "account");
  $("accounts").replaceChildren();
  $("merge-source").replaceChildren();
  $("merge-target").replaceChildren();
  for (const record of accounts) {
    const tr = el("tr");
    versionCell(tr, record.resource_id, record.version);
    cell(tr, record.note, "note");
    cell(tr, record.alias_to || "—", "resource");
    const td = cell(tr);
    if (user.role === "operator" && record.note !== record.note.trim()) {
      td.append(
        button("Trim outer whitespace", async () => {
          await request("/api/trim", {
            operation_id: keyFor("crm_trim", record),
            resource_id: record.resource_id,
            expected_version: version(record.version),
          });
          notice("Only outer whitespace was trimmed. A receipt was recorded.");
        }),
      );
    }
    $("accounts").append(tr);
    if (!record.alias_to) {
      for (const select of [$("merge-source"), $("merge-target")]) {
        const option = el("option", record.resource_id);
        option.value = record.resource_id;
        select.append(option);
      }
    }
  }
  $("merge-form").hidden = user.role !== "operator" || accounts.length < 2;
  if ($("merge-target").options.length > 1) $("merge-target").selectedIndex = 1;
  showView(currentView);
}
async function refresh(clear = true) {
  if (clear) notice("");
  data = await request("/api/workbench");
  render();
}
function openReview(p) {
  chosen = p;
  $("review-details").replaceChildren();
  for (const [name, value] of [
    ["Action", label(p.command.kind)],
    ["Operation", p.operation_id],
    ["Resource", p.command.resource_id],
    ["Expected version", p.command.expected_version],
    [
      "New invoice total",
      p.command.invoice_amount_minor === null
        ? "—"
        : money(p.command.invoice_amount_minor) + " SIM",
    ],
    ["Adjustment", money(p.adjustment_minor) + " SIM"],
    ["Alias target", p.command.target_account_id || "—"],
    ["Target version", p.command.expected_target_version ?? "—"],
    ["Original operation", p.command.original_operation_id || "—"],
    ["Proposed by", p.proposer_id],
    ["Action digest", p.action_digest],
  ]) {
    $("review-details").append(el("dt", name), el("dd", String(value)));
  }
  $("review-dialog").showModal();
}
for (const name of ["approve", "reject"]) {
  $(name).addEventListener("click", () =>
    action($(name), async () => {
      if (!chosen) return;
      const result = await request(
        "/api/proposals/" + encodeURIComponent(chosen.operation_id) + "/review",
        { decision: name, action_digest: chosen.action_digest },
      );
      $("review-dialog").close();
      notice(
        result.event_dispatch === "pending_recovery"
          ? "Decision saved. Event relay is unavailable; explicit apply or a recovery sweep can continue."
          : name === "approve"
            ? "Approved. An operator may now apply this exact change."
            : "Rejected. No billing change was made.",
      );
    }),
  );
}
$("login-form").addEventListener("submit", (event) => {
  event.preventDefault();
  action(event.submitter, async () => {
    user = await request("/api/login", {
      username: $("username").value,
      password: $("password").value,
    });
    $("password").value = "";
    await refresh();
  });
});
$("logout").addEventListener("click", async () => {
  let confirmed = false;
  try {
    await request("/api/logout", {});
    confirmed = true;
  } catch {
  } finally {
    user = null;
    data = null;
    $("workspace").hidden = true;
    $("identity").hidden = true;
    $("login-panel").hidden = false;
    sessionStorage.clear();
    notice(
      confirmed
        ? "Signed out."
        : "Local view cleared. Server sign-out is unconfirmed; close this browser session and retry when the service returns.",
    );
  }
});
$("refresh").addEventListener("click", () =>
  action($("refresh"), () => refresh()),
);
$("sweep").addEventListener("click", () =>
  action($("sweep"), async () => {
    const result = await request("/api/sweep", {});
    notice(result.expired + " overdue waits reconciled.");
  }),
);
document
  .querySelectorAll(".tabs button")
  .forEach((b) => b.addEventListener("click", () => showView(b.dataset.view)));
$("merge-form").addEventListener("submit", (event) => {
  event.preventDefault();
  action(event.submitter, async () => {
    const source = data.records.find(
        (r) =>
          r.resource_id === $("merge-source").value && r.kind === "account",
      ),
      target = data.records.find(
        (r) =>
          r.resource_id === $("merge-target").value && r.kind === "account",
      );
    if (!source || !target || source.resource_id === target.resource_id)
      throw new Error("Choose two different accounts.");
    await request("/api/proposals", {
      operation_id: keyFor(
        "account_merge",
        source,
        target.resource_id + ":" + target.version,
      ),
      kind: "account_merge",
      resource_id: source.resource_id,
      expected_version: version(source.version),
      target_account_id: target.resource_id,
      expected_target_version: version(target.version),
    });
    notice("Account alias proposed for separate review.");
    showView("reviews");
  });
});
(async () => {
  try {
    user = await request("/api/session");
    await refresh();
  } catch {
    $("workspace").hidden = true;
    $("login-panel").hidden = false;
  }
})();
