"use strict";
const $ = id => document.getElementById(id);
let user = null, csrfName = null, selected = null, draftKey = crypto.randomUUID();
const labels = {processing:"Processing",review_required:"Needs review",approved:"Approved · not executed",rejected:"Rejected",stale:"Reevaluation required",committed:"Committed",status:"Status recorded",needs_recovery:"Needs recovery"};
const money = amount => `${Math.floor(amount / 100)}.${String(amount % 100).padStart(2,"0")} SIM`;
function element(tag, text, className) { const n=document.createElement(tag); if(text!==undefined)n.textContent=text; if(className)n.className=className; return n; }
function cookie(name) { const entry=document.cookie.split("; ").find(x=>x.startsWith(name+"=")); return entry ? decodeURIComponent(entry.slice(name.length+1)) : ""; }
async function api(path, body) {
  const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),120000);
  const headers={}; if(body!==undefined){headers["Content-Type"]="application/json";if(csrfName)headers["X-CSRF-Token"]=cookie(csrfName);}
  try { const r=await fetch(path,{method:body===undefined?"GET":"POST",credentials:"same-origin",headers,body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal});
    const value=await r.json(); if(!r.ok){const error=new Error(r.status===401?"Sign-in failed. Check your details or try again later.":r.status===403?"Your session or access does not allow this action. Sign in again if needed.":r.status===409?"The record changed or this action is ineligible. Refresh and review the evidence again.":r.status===503?"Storage is unavailable. Refresh the case before retrying; no outcome is confirmed.":"The request could not be completed. Check the details and refresh.");error.status=r.status;throw error;} return value;
  } catch(error){if(error.name==="AbortError")throw new Error("The response timed out. Refresh the case before retrying; the operation may already have committed.");throw error;} finally{clearTimeout(timer);}
}
function notice(message,error=false){$("notice").hidden=!message;$("notice").textContent=message;$("notice").className=error?"error":"";}
async function busy(button,fn){const contents=[...button.childNodes];button.disabled=true;button.textContent="Working…";try{return await fn();}finally{button.disabled=false;button.replaceChildren(...contents);}}
function screen(name){for(const id of ["empty","compose","detail"])$(id).hidden=id!==name;}
async function signedIn(session){user=session.principal;csrfName=session.csrf_cookie;$("password").value="";$("login-screen").hidden=true;$("desk").hidden=false;$("identity").textContent=`${user.username} · ${user.role}`;$("tenant").textContent=user.tenant_id;$("new-case").hidden=user.role!=="operator";screen("empty");await refresh();}
async function refresh(){
  $("queue-state").hidden=false;$("queue-state").textContent="Loading cases…";
  try{const rows=await api("/api/cases");$("case-list").replaceChildren();$("queue-count").textContent=rows.length;$("queue-state").hidden=rows.length>0;$("queue-state").textContent="No cases yet. New requests will appear here.";
    for(const c of rows){const b=element("button",undefined,"case-item"+(c.case_id===selected?" selected":""));b.dataset.caseId=c.case_id;const top=element("span",undefined,"item-top");top.append(element("span",c.intent.charAt(0).toUpperCase()+c.intent.slice(1)),element("span",labels[c.status]||c.status,"pill "+c.status));b.append(top,element("span",c.order_id,"item-order"));b.addEventListener("click",()=>openCase(c.case_id));$("case-list").append(b);}
    if(selected)await openCase(selected,false);
  }catch(e){$("queue-state").textContent="Cases are unavailable. Use Refresh to try again.";notice(e.message,true);}
  try{const h=await api("/health");$("health").textContent=h.status==="ready"?"Storage connected":"Storage unavailable";}catch{$("health").textContent="Storage unavailable";}
}
async function openCase(id,reloadList=true){try{const value=await api("/api/cases/"+encodeURIComponent(id));selected=id;render(value);if(reloadList){for(const b of $("case-list").children)b.classList.toggle("selected",b.dataset.caseId===id);}}catch(e){notice(e.message,true);}}
function row(target,label,value){target.append(element("dt",label),element("dd",value??"Unknown"));}
function render({case:c,events}){
  screen("detail");$("case-ref").textContent="CASE / "+c.case_id.slice(0,12).toUpperCase();$("case-title").textContent=c.request.intent==="status"?"Order status":c.request.intent==="reship"?"Reship request":"Refund request";$("case-order").textContent=`${c.order_id} · ${new Date(c.created_at).toLocaleString()}`;$("case-status").textContent=labels[c.status]||c.status;$("case-status").className="pill "+c.status;$("customer-message").textContent=c.request.text;
  const evidence=$("evidence"),scenario=$("scenario");evidence.replaceChildren();scenario.replaceChildren();
  if(c.evidence){row(evidence,"Recorded order status",c.evidence.final_source_status);row(evidence,"Source-local case clock",c.evidence.as_of_source_local);row(evidence,"Original currency","Unverified");row(evidence,"Reviewed order version",c.command?String(c.command.expected_version):"No eligible command");}
  else row(evidence,"Evidence","No review snapshot attached");
  const facts=c.confirmation;row(scenario,"Scenario unit",facts?.unit||"Unknown");row(scenario,"Payment confirmed",facts?.payment_confirmed===true?"Yes":facts?.payment_confirmed===false?"No":"Unknown");row(scenario,"Non-delivery confirmed",facts?.undelivered_confirmed===true?"Yes":facts?.undelivered_confirmed===false?"No":"Unknown");
  $("outcome-title").textContent=labels[c.status]||c.status;$("outcome-message").textContent=c.status==="approved"?"Consent is recorded for this exact action. The refund has not been executed yet.":c.status==="rejected"?"The reviewer rejected this request. No refund was executed by this decision.":c.status==="stale"?"The approved action could not be applied under current state or limits. Reevaluate and obtain a new decision.":c.status==="needs_recovery"?"Execution was interrupted. Retry safely to recover the saved outcome.":c.result?.message||"Execution is in progress. Refresh to check its outcome.";
  const receipt=$("receipt");receipt.replaceChildren();receipt.hidden=!c.result?.receipt;if(c.result?.receipt){receipt.className="receipt";receipt.append(element("strong",money(c.result.receipt.amount_minor)),element("span","Verified ledger receipt · "+c.result.receipt.ledger_id.slice(0,16)));}
  const actions=$("actions");actions.replaceChildren();
  const act=(label,endpoint,payload,kind="primary")=>{const b=element("button",label,kind);b.addEventListener("click",()=>busy(b,async()=>{try{await api(`/api/cases/${encodeURIComponent(c.case_id)}/${endpoint}`,typeof payload==="function"?payload():payload);notice("Case updated.");await refresh();}catch(e){notice(e.message,true);}}));actions.append(b);};
  if(user.role==="reviewer"&&["review_required","stale"].includes(c.status)){
    const label=element("label","Decision rationale");label.htmlFor="rationale";const rationale=element("textarea");rationale.id="rationale";rationale.rows=3;rationale.maxLength=2000;actions.append(label,rationale);
    const payload=decision=>()=>{if(!rationale.value.trim())throw new Error("Add a rationale before recording a decision.");return {decision,expected_version:c.version,action_digest:c.action_digest,rationale:rationale.value};};
    if(c.command&&c.status==="review_required")act("Approve "+money(c.command.amount_minor),"decision",payload("approve"));
    else actions.append(element("p",c.proposal?.reason?c.proposal.reason.replaceAll("_"," "):"No eligible refund is available. Resolve the facts before approval.","small muted"));
    act("Reject request","decision",payload("reject"),"danger");
  }
  if(user.role==="reviewer"&&c.status==="approved"&&c.approved_by===user.actor_id)act("Execute approved "+money(c.command.amount_minor),"resume",{action_digest:c.action_digest});
  if(["review_required","stale","approved"].includes(c.status))act("Reevaluate current evidence","reevaluate",{},"secondary");
  if(user.role==="operator"&&["processing","needs_recovery"].includes(c.status))act("Retry safely","resume",{action_digest:null});
  $("history").replaceChildren();for(const e of events){const li=element("li");li.append(element("strong",e.kind.replaceAll("_"," ")),element("p",`${e.actor_id} · ${new Date(e.at).toLocaleString()}`));if(e.detail?.rationale)li.append(element("p",e.detail.rationale));$("history").append(li);}
}
$("login-form").addEventListener("submit",e=>{e.preventDefault();busy(e.submitter,async()=>{try{$("login-error").textContent="";await signedIn(await api("/api/login",{username:$("username").value,password:$("password").value}));}catch(error){$("login-error").textContent=error.message;}finally{$("password").value="";}});});
$("logout").addEventListener("click",()=>busy($("logout"),async()=>{try{await api("/api/logout",{});user=null;csrfName=null;selected=null;$("desk").hidden=true;$("login-screen").hidden=false;$("case-list").replaceChildren();$("detail").hidden=true;notice("");}catch(e){notice(e.message,true);}}));
$("refresh").addEventListener("click",()=>refresh());
$("new-case").addEventListener("click",async()=>{screen("compose");notice("");draftKey=crypto.randomUUID();$("order").replaceChildren(element("option","Loading assigned orders…"));try{const orders=await api("/api/orders");$("order").replaceChildren();for(const order of orders){const option=element("option",`${order.order_id} · ${order.recorded_status||"unknown"}`);option.value=order.order_id;$("order").append(option);}if(!orders.length){$("order").append(element("option","No enrolled orders assigned. Contact your administrator."));$("request-form").querySelector("button").disabled=true;}else $("request-form").querySelector("button").disabled=false;}catch(e){notice(e.message,true);}});
$("request-form").addEventListener("submit",e=>{e.preventDefault();busy(e.submitter,async()=>{try{const c=await api("/api/cases",{event_key:draftKey,order_id:$("order").value,text:$("request-text").value,intent:$("intent").value,require_review:$("manual-review").checked});selected=c.case_id;notice("Request saved.");await refresh();}catch(error){notice(error.message,true);}});});
if(document.cookie.split("; ").some(x=>x.startsWith("olist_csrf_")))api("/api/session").then(signedIn).catch(()=>{});
