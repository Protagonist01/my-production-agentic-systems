"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm"),path=require("node:path");
class Element{constructor(){this.value="";this.textContent="";this.hidden=false;this.disabled=false;this.children=[];}append(...children){this.children.push(...children);}replaceChildren(...children){this.children=children;this.textContent="";}}
const elements=new Map(),pending=[];
const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
const response=(body,status=200)=>({ok:status>=200&&status<300,status,json:async()=>body});
const context=vm.createContext({console,BigInt,Number,Map,Object,String,Error,Promise,JSON,encodeURIComponent,decodeURIComponent,AbortController,setTimeout,clearTimeout,
  crypto:{randomUUID:()=>"invented-operation"},window:{confirm:()=>true},
  document:{cookie:"revenue_csrf_test=invented-token",getElementById:get,createElement:()=>new Element(),querySelector:()=>({content:"revenue_csrf_test"})},
  fetch:async(url,options)=>{if(url==="/api/session")return response({error:"not signed in"},403);return new Promise(resolve=>pending.push({url,options,resolve}));}});
vm.runInContext(fs.readFileSync(path.join(__dirname,"..","revenue_demo_web.js"),"utf8"),context);
const run=code=>vm.runInContext(code,context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  await tick();await tick();
  assert.equal(run('money("9223372036854775807")'),"92233720368547758.07");
  assert.equal(run('money("-500")'),"−5.00");
  run('state.user={username:"old-operator",role:"operator",tenant_id:"invented"}; $("workspace").hidden=false;');
  const refreshing=run('refresh()');await tick();
  const workbench=pending.shift();assert.equal(workbench.url,"/api/workbench");
  run('clearSession()');
  assert.equal(get("workspace").hidden,true);
  workbench.resolve(response({proposals:[{command:{resource_id:"PRIVATE_OLD_RECORD"}}],ledger:[]}));
  await refreshing;
  assert.equal(get("proposals").children.length,0,"late response cannot refill private view");
  run('state.user={username:"reviewer",role:"reviewer",tenant_id:"invented"}; $("workspace").hidden=false;');
  const expired=run('api("/walkthrough-api/cases")');await tick();
  pending.shift().resolve(response({error:"access_or_session_denied"},403));
  await assert.rejects(expired);
  assert.equal(run('state.user'),null,"expired session must erase private state");
  assert.equal(get("workspace").hidden,true);
  const mutation=run('api("/walkthrough-api/analyze",{method:"POST",body:{invented:true}})');await tick();
  const request=pending.shift();assert.equal(request.options.headers["x-csrf-token"],"invented-token");
  request.resolve(response({action:"review"}));await mutation;
  run('state.user={username:"operator",role:"operator",tenant_id:"invented"};$("case-select").value="invented";$("document").value="PRIVATE_SOURCE";$("question").value="Check this invoice.";');
  const analyzing=get("analyze").onclick();await tick();
  const old=pending.shift();run('clearAssessment()');
  old.resolve(response({action:"proposable",citations:[],issued_minor:"1",expected_minor:"2",delta_minor:"1"}));await analyzing;
  assert.equal(get("assessment-panel").hidden,true,"changed source invalidates outstanding analysis");
  assert.equal(run('state.analysis'),null);
  console.log("Revenue walkthrough browser asset: exact money, late private response, expiry clearing, CSRF and stale analysis passed; zero network calls");
})().catch(error=>{console.error(error);process.exitCode=1;});
