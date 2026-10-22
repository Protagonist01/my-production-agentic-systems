"use strict";
// Execute the actual browser asset with a minimal DOM and controlled fetches.
// This checks response ordering, not a copied session-state implementation.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(
  path.join(
    __dirname,
    "../projects/revenue-integrity/src/revenue_integrity/web/console.js",
  ),
  "utf8",
);
const tick = () => new Promise((resolve) => setImmediate(resolve));
function deferred() {
  let resolve, reject;
  const promise = new Promise((a, b) => {
    resolve = a;
    reject = b;
  });
  return { promise, resolve, reject };
}
function response(value, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => value };
}
function workbench(marker) {
  return {
    at: "2026-10-22T00:00:00Z",
    digest: {
      found_minor: 0,
      proposed_minor: 0,
      approved_minor: 0,
      applied_minor: 0,
      rejected_minor: 0,
      compensated_minor: 0,
      net_adjustment_minor: 0,
      pending_count: 0,
      expired_count: 0,
      ledger_entries: 0,
    },
    findings: [],
    proposals: [],
    ledger: [],
    records: [],
    marker,
  };
}
function harness(initialRestore) {
  const nodes = new Map(),
    storage = new Map(),
    plans = new Map(),
    calls = [];
  let serverUser = null;
  function node(id) {
    if (!nodes.has(id))
      nodes.set(id, {
        hidden: false,
        disabled: false,
        open: false,
        value: "",
        textContent: "",
        children: [],
        options: [],
        dataset: {},
        addEventListener() {},
        append(...items) {
          this.children.push(...items);
        },
        replaceChildren(...items) {
          this.children = [...items];
        },
        setAttribute() {},
        close() {
          this.open = false;
        },
        showModal() {
          this.open = true;
        },
      });
    return nodes.get(id);
  }
  function queue(url) {
    const pending = deferred();
    const list = plans.get(url) || [];
    list.push(pending);
    plans.set(url, list);
    return pending;
  }
  if (initialRestore) plans.set("/api/session", [initialRestore]);
  const context = vm.createContext({
    console,
    URL,
    Date,
    BigInt,
    Number,
    Promise,
    encodeURIComponent,
    decodeURIComponent,
    crypto: { randomUUID: () => "invented-operation" },
    sessionStorage: {
      getItem: (k) => storage.get(k) || null,
      setItem: (k, v) => storage.set(k, v),
      clear: () => storage.clear(),
    },
    document: {
      cookie: "test_csrf=invented-csrf",
      getElementById: node,
      createElement: (tag) => node("created-" + Math.random() + tag),
      querySelector: () => ({ content: "test_csrf" }),
      querySelectorAll: () => [],
    },
    fetch: async (url, options) => {
      calls.push(url);
      const plan = plans.get(url)?.shift();
      if (plan) return plan.promise;
      if (url === "/api/session") return response({}, 403);
      if (url === "/api/login") {
        const body = JSON.parse(options.body);
        serverUser = {
          username: body.username,
          tenant_id: "invented",
          role: body.username.includes("reviewer") ? "reviewer" : "operator",
        };
        return response(serverUser);
      }
      if (url === "/api/logout") {
        serverUser = null;
        return response({ signed_out: true });
      }
      if (url === "/api/workbench")
        return response(workbench(serverUser?.username || "signed-out"));
      return response({});
    },
  });
  vm.runInContext(source, context, { filename: "console.js" });
  const api = vm.runInContext(
    "({signIn,signOut,refresh,action,money,state:()=>({user,data,epoch:sessionEpoch})})",
    context,
  );
  return { api, node, queue, calls };
}
(async () => {
  const h = harness();
  await tick();
  await h.api.signIn("operator", "invented password");
  assert.equal(h.node("workspace").hidden, false);
  const delayed = h.queue("/api/workbench");
  const action = h.api.action({ disabled: false }, async () => {});
  await tick();
  const logout = h.queue("/api/logout");
  const signedOut = h.api.signOut();
  assert.equal(
    h.node("workspace").hidden,
    true,
    "private view must hide before logout responds",
  );
  assert.equal(h.node("login-panel").hidden, false);
  assert.equal(h.api.state().data, null);
  const callsBeforeLogin = h.calls.filter((p) => p === "/api/login").length;
  const newLogin = h.api.signIn("reviewer", "invented password");
  await tick();
  assert.equal(
    h.calls.filter((p) => p === "/api/login").length,
    callsBeforeLogin,
    "new login must wait for old logout response/cookie mutation",
  );
  logout.resolve(response({ signed_out: true }));
  await signedOut;
  await newLogin;
  assert.equal(h.api.state().user.username, "reviewer");
  assert.equal(h.api.state().data.marker, "reviewer");
  delayed.resolve(response(workbench("old-private-operator")));
  await action;
  assert.equal(h.api.state().user.username, "reviewer");
  assert.equal(
    h.api.state().data.marker,
    "reviewer",
    "old refresh cannot replace new-session data",
  );
  assert.equal(h.node("who").textContent, "reviewer / reviewer");
  assert.equal(h.node("workspace").hidden, false);
  assert.equal(h.node("login-panel").hidden, true);
  await h.api.signOut();
  const count = h.calls.length;
  await h.api.refresh();
  await h.api.action({ disabled: false }, async () => {
    throw new Error("must not execute while signed out");
  });
  assert.equal(h.calls.length, count);
  assert.equal(h.node("workspace").hidden, true);
  const restore = deferred();
  const newer = harness(restore);
  await newer.api.signIn("reviewer", "invented password");
  restore.resolve(
    response({
      username: "old-operator",
      role: "operator",
      tenant_id: "invented",
    }),
  );
  await tick();
  assert.equal(
    newer.api.state().user.username,
    "reviewer",
    "startup session response must not overwrite explicit login",
  );
  const failed = newer.queue("/api/logout");
  const result = newer.api.signOut();
  assert.equal(newer.node("workspace").hidden, true);
  failed.reject(new Error("invented transport failure"));
  await result;
  assert.match(newer.node("notice").textContent, /unconfirmed/);
  assert.equal(newer.api.state().user, null);
  assert.equal(h.api.money("9223372036854775807"), "92,233,720,368,547,758.07");
  const blocked = harness();
  await tick();
  const initialWorkbench = blocked.queue("/api/workbench");
  const initialLogin = blocked.api
    .signIn("operator", "invented password")
    .catch((error) => error);
  await tick();
  assert.ok(blocked.calls.includes("/api/workbench"));
  const cancelLogin = blocked.api.signOut();
  await tick();
  assert.ok(
    blocked.calls.includes("/api/logout"),
    "a stalled login workbench must not block server logout",
  );
  await cancelLogin;
  initialWorkbench.resolve(response(workbench("stale-initial-operator")));
  await initialLogin;
  assert.equal(blocked.api.state().user, null);
  assert.equal(blocked.node("workspace").hidden, true);
  console.log(
    JSON.stringify({
      delayed_refresh_after_logout_and_new_login: "passed",
      auth_cookie_mutations_serialized: "passed",
      late_startup_response: "passed",
      signed_out_actions_do_not_fetch: "passed",
      failed_logout_truthful: "passed",
      exact_signed64_formatter: "passed",
      stalled_initial_workbench_does_not_block_logout: "passed",
      network_calls: 0,
    }),
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
