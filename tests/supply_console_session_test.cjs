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
    "../projects/supply-chain-disruption/src/supply_chain/web/console.js",
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
  return {as_of:"2026-10-23T00:00:00Z",label:marker,budget:{cap_minor:"50000",spent_minor:"0",remaining_minor:"50000",replans_used:"0"},shipments:[],notices:[],context:null};
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
      if (url === "/api/incidents") return response({incidents:[{event_id:"incident",label:"Invented"}]});
      if (url === "/api/workbench/incident")
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
  const h = harness(); await tick();
  await h.api.signIn("operator", "invented password");
  assert.equal(h.node("workspace").hidden, false);
  const delayed = h.queue("/api/workbench/incident");
  const refreshing = h.api.refresh(); await tick();
  await h.api.signOut();
  assert.equal(h.node("workspace").hidden, true);
  assert.equal(h.node("shipments").children.length, 0);
  delayed.resolve(response(workbench("private late response")));
  await refreshing.catch(() => {});
  assert.equal(h.api.state().data, null);
  const blocked = harness(); await tick();
  const board = blocked.queue("/api/workbench/incident");
  const signing = blocked.api.signIn("operator", "invented password"); await tick(); await tick();
  await blocked.api.signOut();
  assert.ok(blocked.calls.includes("/api/logout"));
  board.resolve(response(workbench("stale"))); await signing;
  assert.equal(blocked.api.state().user, null);
  assert.equal(h.api.money("9223372036854775807"), "92,233,720,368,547,758.07");
  console.log("Supply browser asset: late responses, private clearing, stalled login logout, exact money passed; zero network calls");
})().catch((error)=>{console.error(error);process.exitCode=1;});
