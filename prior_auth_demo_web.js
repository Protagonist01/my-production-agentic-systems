"use strict";
// Append to the original desk so its session epoch/selection fences remain in charge.
const renderOriginalEvidenceDesk = render;
render = function renderDemoEvidence(row) {
  renderOriginalEvidenceDesk(row);
  const root = $("detail");
  const section = el("section", undefined, "demo-citations");
  section.append(el("h3", "Policy and case sources"));
  if (row.current_attempt_modes?.length === 1 && row.current_attempt_modes[0] === "offline_fake") {
    section.append(el("p", "Scripted workflow demonstration. These current attempts made no live model calls.", "notice"));
  }
  section.append(el("p", "Synthetic records · Source mapping verifies locations, not clinical validity.", "fine"));
  for (const card of row.evidence_cards || []) {
    const body = el("div");
    body.append(el("p", "Policy requirement", "eyebrow"), el("blockquote", card.policy_requirement.quote));
    const cms = "https://www.cms.gov/medicare-coverage-database/view/ncd.aspx?ncdid=226&ncdver=3";
    if (card.policy_url === cms) {
      const link = el("a", "Open the CMS national policy ↗");
      link.href = cms;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      body.append(link);
    } else {
      body.append(el("p", "Fixture policy source. This passage is not verified CMS policy text.", "notice"));
    }
    body.append(el("p", "Policy review status: " + human(card.policy_review_status), "fine"));
    body.append(el("p", "Case-document evidence", "eyebrow"));
    if (!card.document_citations.length) body.append(el("p", "No supporting document citation is available.", "reason"));
    for (const citation of card.document_citations) {
      body.append(el("blockquote", citation.evidence.quote));
      if (!citation.locations.length) body.append(el("p", "Source location is unresolved. Inspect the current document.", "notice"));
      for (const location of citation.locations) {
        const pages = [...new Set(location.regions.map(r => r.source_region.page))];
        body.append(el("p", "Document: " + location.document_id + " · " + human(location.format) +
          " · page " + pages.join(", "), "reason"));
        body.append(el("p", "Source digest: " + location.source_sha256, "reason"));
      }
    }
    const status = card.source_mapping === "mapped" ? "sources located" :
      card.source_mapping === "incomplete" ? "source mapping incomplete" : "no case evidence";
    section.append(disclosure(labels[card.criterion] + " · " + status, body));
  }
  if (!row.evidence_cards?.length) section.append(el("p", "Citations will appear after the current assessment is published.", "fine"));
  root.append(section);
  if (row.payer?.configured) renderPayerExchange(row, root);
};

function renderPayerExchange(row, root) {
  const box = el("section");
  box.append(el("h3", "Reference payer exchange"));
  box.append(el("p", "Invented packet sent to the owned HL7 reference payer. Case-note text is not exported. Processing status is not clinical approval.", "notice"));
  const receipt = row.payer.submission;
  box.append(el("p", receipt ? "Submission: " + human(receipt.state) : "Not submitted", "reason"));
  for (const [label, value] of [["Submission", receipt], ["Latest inquiry", row.payer.inquiry]]) {
    if (!value) continue;
    box.append(el("p", label + ": " + human(value.state) +
      (value.processing ? " · processing " + human(value.processing) : "") +
      (value.review_codes?.length ? " · review code " + value.review_codes.join(", ") : ""), "reason"));
    if (value.review_codes?.includes("A3")) box.append(el("p", "A3: this reference service reports authorization is not required for the invented service. It does not approve treatment.", "fine"));
  }
  if (receipt?.state === "reserved" || receipt?.state === "unknown") {
    box.append(el("p", "Submission outcome is uncertain. Use inquiry; do not create another submission to bypass it.", "notice"));
  }
  if (row.payer.blocked_prior_unknown) box.append(el("p", "An earlier case packet has an unresolved submission. Reconcile that packet before submitting this revision.", "notice"));
  box.append(el("p", "Packet digest: " + row.payer.request_sha256, "fine"));
  const controls = [];
  for (const [action, label, disabled] of [["submit", "Submit synthetic packet", !!receipt || row.payer.blocked_prior_unknown], ["inquire", "Check payer status", !receipt]]) {
    const button = el("button", label);
    button.type = "button";
    button.disabled = disabled || user?.role !== "reviewer";
    button.onclick = async () => {
      const mine = epoch, seq = selection;
      if (active !== row.case_id || user?.role !== "reviewer") return;
      for (const b of controls) b.disabled = true;
      try {
        await api("/api/cases/" + encodeURIComponent(row.case_id) + "/payer/" + action,
          {expected_version: row.version, confirm_synthetic_exchange: true});
        if (mine !== epoch || seq !== selection) return;
        await selectCase(row.case_id);
      } catch (error) {
        if (mine === epoch && seq === selection) tell(error.message);
      }
    };
    controls.push(button);
    box.append(button);
  }
  root.append(box);
}
