"""Run the operating exercise through the protected HTTP and PostgreSQL paths."""

from test_cfpb_desk_state import app as app

from cfpb_operations_exercise import Scenario, run_exercise


def test_scripted_reviewer_resolves_authored_cases_and_keeps_unknowns_in_queue(app):
    server, trial, *_ = app
    report = run_exercise(
        server,
        trial.workspace_key,
        (Scenario("archive", "Invented archive fixture.", None),),
        ("a" * 64,),
    )
    assert report["provider_calls"] == 0 and report["qualification"] is False
    for outcome in report["arms"].values():
        assert (outcome["scheduled"], outcome["accepted"], outcome["unresolved"]) == (8, 5, 3)
        assert outcome["observed_human_savings_seconds"] is None
    assert report["arms"]["assisted"]["candidate_missed_escalations_in_authored_cases"] == 1
    assert report["arms"]["assisted"]["scripted_correction_seconds"] == 35
