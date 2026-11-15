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
};
