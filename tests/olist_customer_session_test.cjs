"use strict";
// Drive the shipped asset with adversarial response ordering; never use a network.
const assert = require("node:assert/strict"), fs = require("node:fs"), vm = require("node:vm"), path = require("node:path");
const source = fs.readFileSync(path.join(__dirname, "../projects/olist-support/src/olist_support/web/customer.js"), "utf8");
const tick = () => new Promise(resolve => setImmediate(resolve));
function deferred() { let resolve; const promise = new Promise(r => { resolve = r; }); return {promise, resolve}; }
const response = (value, status=200) => ({ok:status<400, status, json:async()=>value});
const offer = {case_id:"case-one", order_id:"order-one", action:"refund", amount_minor:5000, unit:"SIM", challenge:"invented-unique-challenge-123456789", request_text:"What options do I have?"};
function harness() {
  const nodes = new Map(), plans = new Map(), calls = [];
  function node(id) {
    if (!nodes.has(id)) nodes.set(id, {hidden:false, disabled:false, value:"", textContent:"", children:[], listeners:{},
      addEventListener(kind, callback) { this.listeners[kind] = callback; },
      append(...items) { this.children.push(...items); }, replaceChildren(...items) { this.children = items; }});
    return nodes.get(id);
  }
  function queue(url) { const pending = deferred(), rows = plans.get(url) || []; rows.push(pending); plans.set(url, rows); return pending; }
  const context = vm.createContext({console, Date, Promise, encodeURIComponent, AbortController, setTimeout, clearTimeout,
    document:{cookie:"csrf=invented", getElementById:node, createElement:tag=>node(tag+Math.random())},
    fetch:async(url, options)=>{
      calls.push({url, body:options.body && JSON.parse(options.body)});
      const planned = plans.get(url)?.shift(); if (planned) return planned.promise;
      if (url === "/api/session") return response({},403);
      if (url === "/api/login") return response({csrf_cookie:"csrf",principal:{role:"customer",username:JSON.parse(options.body).username}});
      if (url === "/api/customer/cases") return response([{case_id:offer.case_id,order_id:offer.order_id,committed:false}]);
      if (url.endsWith("/challenge")) return response(offer);
      if (url.endsWith("/confirm")) return response({confirmed:true,committed:false});
      if (url.endsWith("/execute")) return response({committed:true,message:"Full refund committed in SIM."});
      return response({});
    }});
  vm.runInContext(source, context);
  return {node, queue, calls, click:id=>node(id).listeners.click(),
    state:()=>vm.runInContext("({identity,selection,busy})",context),
    login:async(username="customer")=>{node("username").value=username;node("password").value="invented password";await node("customer-login").listeners.submit({preventDefault(){}});},
    open:()=>node("customer-list").children[0].children[1].listeners.click()};
}
(async()=>{
  const h = harness(); await tick(); await h.login();
  assert.equal(h.node("password").value, ""); await h.open();
  assert.match(h.node("customer-confirm").textContent,/50\.00 SIM/);
  await h.click("customer-cancel");
  assert.equal(h.state().selection,null); assert.equal(h.calls.some(c=>c.url.endsWith("/confirm")),false);
  await h.open(); await h.click("customer-confirm");
  const writes = h.calls.filter(c=>/\/(confirm|execute)$/.test(c.url));
  assert.equal(writes.length,2); assert.deepEqual(writes[0].body,{challenge:offer.challenge,action:"refund",amount_minor:5000,unit:"SIM"});
  assert.deepEqual(writes[1].body,writes[0].body);

  const late = harness(); await tick(); await late.login();
  const challenge = late.queue("/api/customer/cases/case-one/challenge"), opening = late.open(); await tick();
  await late.click("customer-logout"); challenge.resolve(response(offer)); await opening;
  assert.equal(late.state().identity,null); assert.equal(late.state().selection,null);
  assert.equal(late.node("customer-proposal").hidden,true); assert.equal(late.node("customer-request").textContent,"");
  assert.equal(late.node("customer-confirm").textContent,"Confirm full refund");

  const switched = harness(); await tick(); await switched.login("first"); await switched.open();
  const confirmed = switched.queue("/api/customer/cases/case-one/confirm"), sending = switched.click("customer-confirm"); await tick();
  await switched.click("customer-logout"); await switched.login("second");
  confirmed.resolve(response({confirmed:true,committed:false})); await sending;
  assert.equal(switched.state().identity.username,"second");
  assert.equal(switched.calls.some(c=>c.url.endsWith("/execute")),false);

  const failed = harness(); await tick(); await failed.login(); await failed.open();
  const denied = failed.queue("/api/customer/cases/case-one/execute"); denied.resolve(response({},503));
  await failed.click("customer-confirm");
  assert.equal(failed.calls.filter(c=>c.url.endsWith("/execute")).length,1);
  assert.equal(failed.state().selection,null); assert.match(failed.node("customer-notice").textContent,/Refresh/);
  const expired = harness(); await tick(); await expired.login(); await expired.open();
  const deniedSession = expired.queue("/api/customer/cases/case-one/confirm"); deniedSession.resolve(response({},403));
  await expired.click("customer-confirm");
  assert.equal(expired.state().identity,null); assert.equal(expired.node("customer-request").textContent,"");
  assert.equal(expired.node("customer-confirm").textContent,"Confirm full refund");
  assert.equal(expired.node("customer-login").hidden,false);

  const staleDenied = harness(); await tick(); await staleDenied.login("first");
  const old = staleDenied.queue("/api/customer/cases/case-one/challenge"), loading = staleDenied.open(); await tick();
  await staleDenied.click("customer-logout"); await staleDenied.login("second");
  old.resolve(response({},403)); await loading;
  assert.equal(staleDenied.state().identity.username,"second");
  console.log("Olist customer asset: exact amount, cancel, stale challenge, account switch and no automatic retry passed; zero network calls");
})().catch(error=>{console.error(error);process.exitCode=1;});
