"use strict";
// Exercise the shipped browser asset against controlled response ordering.
const assert = require("node:assert/strict"), fs = require("node:fs"), vm = require("node:vm"), path = require("node:path");
const source = fs.readFileSync(path.join(__dirname,"../projects/cfpb-triage/src/cfpb_triage/web/console.js"),"utf8");
const tick = () => new Promise(resolve=>setImmediate(resolve));
function deferred(){let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};}
function response(value,status=200){return {ok:status>=200&&status<300,status,json:async()=>value};}
function harness(){
  const nodes=new Map(),plans=new Map(),calls=[];
  function node(id){if(!nodes.has(id))nodes.set(id,{hidden:false,disabled:false,value:"",textContent:"",children:[],dataset:{},classList:{toggle(){}},append(...items){this.children.push(...items);},replaceChildren(...items){this.children=[...items];},querySelectorAll(){return [];},get firstChild(){return this.children[0];}});return nodes.get(id);}
  function queue(url){const pending=deferred(),rows=plans.get(url)||[];rows.push(pending);plans.set(url,rows);return pending;}
  const context=vm.createContext({console,Date,Promise,encodeURIComponent,crypto:{randomUUID:()=>"invented-command"},document:{body:{dataset:{csrfCookie:"csrf"}},cookie:"csrf=canary",getElementById:node,createElement:tag=>node(tag+Math.random()),createTextNode:text=>({textContent:text})},fetch:async(url,options)=>{calls.push(url);const planned=plans.get(url)?.shift();if(planned)return planned.promise;if(url==="/api/session")return response({},403);if(url==="/api/login")return response({username:JSON.parse(options.body).username,role:"reviewer"});if(url==="/api/cases")return response({cases:[]});return response({});}});
  vm.runInContext(source,context);
  const api=vm.runInContext("({signIn,signOut,selectCase,loadCases,state:()=>({epoch,user,active})})",context);
  return {node,api,queue,calls};
}
(async()=>{
  const h=harness();await tick();await h.api.signIn("reviewer","invented password");
  assert.equal(h.node("workspace").hidden,false);
  const late=h.queue("/api/cases/private-case"),loading=h.api.selectCase("private-case");await tick();
  await h.api.signOut();
  assert.equal(h.node("workspace").hidden,true);assert.equal(h.node("detail").children.length,0);
  late.resolve(response({case_id:"private-case"}));await loading;
  assert.equal(h.node("detail").children.length,0);assert.equal(h.api.state().user,null);
  const blocked=harness();await tick();const list=blocked.queue("/api/cases");
  const signin=blocked.api.signIn("reviewer","invented password");await tick();await tick();
  await blocked.api.signOut();assert.ok(blocked.calls.includes("/api/logout"));
  list.resolve(response({cases:[{case_id:"late-secret",status:"waiting"}]}));await signin;
  assert.equal(blocked.node("cases").children.length,0);
  const expired=harness();await tick();await expired.api.signIn("reviewer","invented password");
  expired.node("detail").append({textContent:"private evidence"});
  const denied=expired.queue("/api/cases");const refresh=expired.api.loadCases();denied.resolve(response({},403));await refresh;
  assert.equal(expired.node("detail").children.length,0);assert.equal(expired.node("workspace").hidden,true);
  const switched=harness();await tick();await switched.api.signIn("old-reviewer","invented password");
  const oldDenied=switched.queue("/api/cases");const oldLoad=switched.api.loadCases();await tick();
  await switched.api.signIn("new-reviewer","invented password");
  oldDenied.resolve(response({},403));await oldLoad;
  assert.equal(switched.api.state().user.username,"new-reviewer");
  assert.equal(switched.node("workspace").hidden,false);
  console.log("CFPB browser asset: stale case/list responses, logout during stalled load and expired-session private clearing passed; zero network calls");
})().catch(error=>{console.error(error);process.exitCode=1;});
