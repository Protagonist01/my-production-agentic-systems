"""Provider preflight uses invented policy/credentials, never invokes an SDK client."""

from dataclasses import replace

import pytest
from agent_harness.admission import GeminiFreeAdmission
from agent_harness.provider_capture import GeminiCaptureControls
from agent_harness.release_contracts import pin
from domain_recording_fixtures import composition
from revenue_integrity.provider_recording import RevenueProviderFactory
from test_provider_budget_accounting import inputs, tariff


def test_revenue_provider_requires_exact_budget_tariff_source_and_explicit_control_pin(tmp_path):
    loaded, _, old = composition("revenue")
    ledger, _, route = inputs(tmp_path)
    policy = tariff()
    controls = GeminiCaptureControls("invented-placeholder", ledger, policy, pin(policy), "a" * 64)
    adapter = replace(old.adapter, route=route)
    spec = old.candidate.model_copy(
        update={
            "model_config_sha256": adapter.configuration_sha256,
            "prompt_sha256": old.candidate.source_files[adapter.source_prefix + "extraction.py"],
            "provider_control_sha256": controls.sha256,
        }
    )
    factory = RevenueProviderFactory(spec, loaded, adapter, controls, tmp_path / "unused")
    factory.validate()
    for field in ("prompt_sha256", "provider_control_sha256"):
        with pytest.raises(ValueError):
            replace(factory, candidate=spec.model_copy(update={field: "0" * 64})).validate()
    bad = replace(controls, project_sha256="d" * 64)
    with pytest.raises(ValueError):
        replace(factory, controls=bad).validate()
    assert ledger.summary()["consumed"] == 0


def test_olist_provider_preflight_is_explicit_and_mock_cannot_carry_controls(tmp_path):
    from olist_h10_fixtures import composition as olist_inputs
    from olist_support.h10_config import fingerprints

    _, _, _, old = olist_inputs()
    ledger, _, route = inputs(tmp_path)
    policy = tariff()
    controls = GeminiCaptureControls("invented-placeholder", ledger, policy, pin(policy), "a" * 64)
    with pytest.raises(ValueError, match="mock capture"):
        replace(old, controls=controls).validate()
    spec = old.candidate.model_copy(
        update={
            **fingerprints(route, old.candidate.source_files),
            "provider_control_sha256": controls.sha256,
        }
    )
    factory = replace(
        old,
        candidate=spec,
        route=route,
        origin="provider",
        controls=controls,
        admission=GeminiFreeAdmission(free_tier_confirmed=True, flash_comparison=True),
    )
    factory.validate()
    with pytest.raises(ValueError):
        replace(factory, controls=None).validate()
    assert ledger.summary()["consumed"] == 0
