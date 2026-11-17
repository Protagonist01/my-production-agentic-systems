"""Frozen authored pack through actual SQL intake, durable worker and citation cards."""

import json
import uuid
from decimal import Decimal

import pytest
from agent_harness.contracts import ModelMessage, ModelResponse, Usage
from prior_auth.candidate import QuoteClaim
from test_prior_auth_review import actor
from test_prior_auth_review_state import app as app

from prior_auth_demo_fixtures import fake_scope
from prior_auth_demo_regression import EXPECTED, QUOTES, imported, source, witnesses
from prior_auth_demo_runtime import DemoWorker, provision_scope, setup
from prior_auth_evidence_cards import EvidenceReader
from prior_auth_pipeline import prepare
from prior_auth_profiling import Profiler
from prior_auth_store import IntakeStore
from prior_auth_store import setup as setup_intake


@pytest.mark.parametrize("witness", witnesses(), ids=lambda w: w.case_id)
def test_declared_pack_through_scoped_sql_and_source_readback(app, witness):
    server, trial, store, _ = app
    with server.connect(trial.name) as admin:
        setup_intake(admin, trial.name)
        setup(admin, trial.name)
    raw = source(witness)
    prepared = prepare(raw, imported(witness, raw), Profiler())
    user = actor(witness.case_id)
    version = IntakeStore(store.connect, clock=store.clock).accept(user, prepared, Profiler())
    intake, route, differences = EXPECTED[witness.case_id]
    assert prepared.decision.outcome == intake
    if prepared.note is None:
        assert version is None
        with store.transaction() as c:
            assert not c.execute(
                "SELECT 1 FROM prior_auth_app.cases WHERE tenant_id=%s AND case_id=%s",
                (user.tenant_id, witness.case_id),
            ).fetchone()
        return

    scope = fake_scope(
        "pack-" + uuid.uuid4().hex, (prepared.note,), prepared.policy, now=store.now()
    )
    with server.connect(trial.name) as admin:
        provision_scope(admin, scope)

    class PositiveProposal:
        def generate(self, context, request):
            assert context.mode == "offline_fake"
            payload = json.loads(request.messages[1].content)
            key, text = payload["criterion"]["criterion_id"], payload["full_note"]
            quote = (
                witness.quote
                if witness.quote_key == key
                else QUOTES[key]
                if QUOTES[key] in text
                else text
            )
            return ModelResponse(
                provider=request.provider,
                model=request.model,
                output=ModelMessage(
                    role="assistant",
                    content=QuoteClaim(
                        criterion_id=key,
                        state="met",
                        quotes=(quote,),
                        rationale="Authored SQL regression proposal; no provider used.",
                    ).canonical_json(),
                ),
                usage=Usage(
                    model_calls=1,
                    input_tokens=0,
                    output_tokens=0,
                    cost=Decimal(0),
                    cost_currency="USD",
                ),
            )

    worker = DemoWorker(store, scope, PositiveProposal())
    assert worker.step()["published"]
    snapshot = store.snapshot(user, witness.case_id)
    assert snapshot["status"] == route
    cards = EvidenceReader(store).cards(user, witness.case_id, expected_version=1)
    assert len(cards) == 7
    for card in cards:
        assert card.state == differences.get(card.criterion, "met")
        if card.state == "met":
            assert card.source_mapping == "mapped"
    assert worker.step()["claimed"] is False
