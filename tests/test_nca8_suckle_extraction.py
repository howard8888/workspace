"""L-C selected applicability, original projection/handoff and preservation contracts.

Changed evidence/competing questions are labelled test fixtures. They do not claim
hidden supply awareness, milk-based task completion or a new learning algorithm.
"""
from __future__ import annotations

from dataclasses import replace
import json
import random

import pytest

from cca8_motor_contracts import MotorStreamRefV1
from cca8_navmap_kernel import NavPointV1
from nca8_body_targets import OralExtractionRequestV1
from nca8_handoff import Nca8MotorEnvelopeV1, Nca8PhaseEDispatchV1, Nca8InternalHandoffV1
from nca8_prediction import SucklePreviewV1, SuckleExtractionPreviewV1
from nca8_sensorimotor_contracts import LocalTargetDispositionV1, TargetOriginV1
from nca8_suckle import SuckleIPV1, SuckleProfileV1, SuckleApplicationV1, SuckleExtractionApplicationV1, SuckleExtractionEpisodeV1
from nca8_suckle_extraction_demo import suckle_extraction_profile_v1, create_suckle_extraction_trial_v1, run_suckle_extraction_v1
from nca8_seek_nipple import SeekNippleIPV1


def new_trial(case="nominal", **changes):
    profile = suckle_extraction_profile_v1(case)
    if changes:
        profile = replace(profile, latch=replace(profile.latch, suckle=replace(profile.latch.suckle, **changes)))
    return create_suckle_extraction_trial_v1(profile)


def advance(trial, count):
    return tuple(trial.advance_lower() for _ in range(count))


@pytest.fixture
def selected():
    trial = new_trial()
    cycle = trial.focal_step()
    return trial, cycle, cycle.calculation.navigation.application


@pytest.mark.parametrize("bad", [None, 0, 1, "true", [], {}])
def test_extraction_flag_is_boolean(bad):
    with pytest.raises(TypeError):
        SuckleProfileV1(extraction_enabled=bad)


@pytest.mark.parametrize("bad", [None, True, False, 0, 3, -1, 1.5, "2"])
def test_repetitions_are_bounded_integer(bad):
    with pytest.raises(ValueError):
        SuckleProfileV1(extraction_enabled=True, extraction_repetitions=bad)


def test_default_export_stays_old_and_construction_has_no_episode():
    assert not SuckleProfileV1().extraction_enabled
    assert "extraction_contribution" not in SuckleProfileV1().as_dict()
    trial = new_trial()
    owner = trial.core.suckle
    assert owner.task is None and owner.extraction_assessment().application is None
    assert owner.authorized_target is None and trial.tick == 0 and trial.controller.installation_count == 0
    assert trial.core.cognition.prediction.current_pnm is None


def test_one_real_selected_Suckle_application_uses_distinct_original_projection(selected):
    trial, cycle, app = selected
    assert isinstance(app, SuckleExtractionApplicationV1)
    assert not isinstance(app, SuckleApplicationV1) and not isinstance(app.projection, SucklePreviewV1)
    assert app.primitive_id == "ip:suckle" and cycle.commitment.task_action == "SUCKLE_EXTRACTION"
    assert app.projection.basis is cycle.feeding_detail_source
    assert cycle.calculation.navigation.wnm.primary_source_state is cycle.feeding_detail_source
    assert trial.core.suckle.task is None and app.task.latch is None
    assert app.task.started_tick == 0 and app.task.started_cycle == 1 and app.task.applications == 1
    assert app.contribution.origin_status == "selected_suckle_extraction"
    assert cycle.receipt.dispatch.motor.projection is app.projection
    assert cycle.receipt.dispatch.pnm is app.projection.pnm
    assert trial.core.cognition.prediction.current_pnm is app.projection.pnm
    assert len(cycle.reservations) == trial.controller.installation_count == 1
    assert trial.tick == 0  # installation has no physical step
    assert cycle.suckle_learning_report.new_participation is None and cycle.suckle_correspondence.registration is None
    assert not trial.core.suckle_outcomes.pending()


def test_F_is_before_outer_install_and_extraction_adds_no_learning_participant(monkeypatch):
    trial = new_trial()
    hook = trial.core.feeding_detail.suckle_learning_hook
    original = hook.reconcile
    observed = []
    def capture(**kwargs):
        observed.append((trial.tick, trial.controller.installation_count, kwargs))
        return original(**kwargs)
    monkeypatch.setattr(hook, "reconcile", capture)
    cycle = trial.focal_step()
    assert len(observed) == 1
    tick, installations, kwargs = observed[0]
    assert tick == installations == 0
    assert kwargs["registration"] is None and kwargs["task"] is None and kwargs["outcomes"] == ()
    assert cycle.suckle_learning_report.as_dict()["durable_learning_updates"] == 0


@pytest.mark.parametrize("field,value", [
    ("primitive_id", "ip:seek_nipple"), ("application_id", "another"), ("source_wnm_id", "other_wnm"),
    ("cycle_id", 2), ("expected_relations", ("fake",)),
])
def test_application_links_reject_substitution(selected, field, value):
    with pytest.raises((ValueError, TypeError)):
        replace(selected[2], **{field: value})


@pytest.mark.parametrize("field,value", [
    ("task_id", "different"), ("region_id", "different"), ("scene_target", NavPointV1(1, 1)),
    ("outward_extent", 0.2), ("outward_extent", float("nan")), ("outward_extent", True),
    ("repetitions", 0), ("repetitions", 3), ("repetitions", True),
    ("horizon_ticks", 0), ("horizon_ticks", 9), ("horizon_ticks", True),
])
def test_preview_is_original_finite_typed_and_not_supply_or_local_outcome(selected, field, value):
    with pytest.raises((ValueError, TypeError)):
        replace(selected[2], projection=replace(selected[2].projection, **{field: value}))


@pytest.mark.parametrize("field,value", [
    ("task_id", ""), ("region_id", ""), ("started_cycle", 0), ("started_tick", -1),
    ("applications", 0), ("applications", 13), ("applications", 2),
])
def test_sealed_start_episode_rejects_unfounded_history(field, value):
    kwargs = dict(task_id="task", region_id="region", started_cycle=1, started_tick=0, applications=1)
    kwargs[field] = value
    with pytest.raises((ValueError, TypeError)):
        SuckleExtractionEpisodeV1(**kwargs)


def test_old_fixture_provenance_remains_default_but_cannot_masquerade_as_selected(selected):
    app = selected[2]
    fixture = replace(app.contribution, origin_status="supplied_requirement_fixture")
    assert fixture.as_dict()["origin_status"] == "supplied_requirement_fixture"
    with pytest.raises(ValueError):
        replace(app, contribution=fixture)
    with pytest.raises(ValueError):
        replace(fixture, origin_status="some_permission")


@pytest.mark.parametrize("field,value", [
    ("repetitions", 1), ("outward_offset", 0.11), ("lease_ticks", 7),
])
def test_motor_payload_requires_the_extraction_projection_not_merely_any_oral_target(selected, field, value):
    _trial, cycle, app = selected
    committed = cycle.reservations[0].current
    if field == "lease_ticks":
        # A wider original projection/episode mismatch is rejected by the application.
        with pytest.raises(ValueError):
            replace(app, contribution=replace(app.contribution, lease_ticks=value))
        return
    changed = replace(committed, target=replace(committed.target, **{field: value}))
    with pytest.raises(ValueError):
        replace(cycle.receipt.dispatch.motor, targets=(changed,))


def test_old_closure_projection_cannot_authorize_extraction_target(selected):
    from nca8_suckle_demo import create_suckle_trial_v1
    closure = create_suckle_trial_v1().focal_step().calculation.navigation.application
    with pytest.raises(ValueError):
        replace(selected[1].receipt.dispatch.motor, projection=closure.projection)


def test_motor_commitment_must_name_the_selected_extraction_branch(selected):
    _trial, cycle, _app = selected
    dispatch = cycle.receipt.dispatch
    owner = Nca8InternalHandoffV1(generation=cycle.receipt.generation)
    with pytest.raises(ValueError):
        owner.accept(replace(dispatch, commitment=replace(cycle.commitment, task_action="SUCKLE_INITIAL_LATCH")))


def test_real_executor_refuses_fixture_install_and_repeated_authorized_install(selected):
    trial, cycle, _app = selected
    with pytest.raises((RuntimeError, ValueError)):
        trial.controller.install(cycle.reservations, at_tick=0)
    assert trial.controller.installation_count == 1
    # A separate fresh trial isolates the failed installation side effects.
    other = new_trial()
    current = other.focal_step()
    with pytest.raises((RuntimeError, ValueError)):
        other.controller.install_authorized(current.reservations, at_tick=0)
    assert other.controller.installation_count == 1 and other.tick == 0


def test_core_requires_real_handoff_and_no_physics_occurs_on_refused_install(monkeypatch):
    trial = new_trial()
    def refuse(*_args, **_kwargs):
        raise ValueError("test-only handoff refusal")
    monkeypatch.setattr(trial.core.handoff, "consume_motor", refuse)
    with pytest.raises(ValueError):
        trial.focal_step()
    assert trial.stopped and trial.tick == 0 and trial.controller.installation_count == 0
    assert trial.observer_oral_extraction_body.transferred_milk_units == 0


def test_Navigation_disabled_or_competing_source_cannot_be_replaced_by_a_fixture():
    trial = new_trial()
    from nca8_executive import NavigationRuntimeV1
    trial.core.cognition.navigation = NavigationRuntimeV1(enabled=False, motor_preview_enabled=True)
    cycle = trial.focal_step()
    assert cycle.calculation.navigation.application is None and not cycle.reservations
    assert trial.core.suckle.extraction_assessment().application is None
    other = new_trial()
    cycle = other.focal_step(visual_bid_priority=(10, 70))
    assert not isinstance(cycle.calculation.navigation.application, SuckleExtractionApplicationV1)
    assert other.core.suckle.extraction_assessment().application is None


@pytest.mark.parametrize("case", ["extraction_off", "suckle_off", "no_need", "source_off", "attention_off",
                                  "missing_stroke", "missing_seal", "nonsealable", "competing_initial"])
def test_current_applicability_controls_never_install_extraction(case):
    result = run_suckle_extraction_v1(case)
    assert result.metrics()["extraction_installations"] == result.metrics()["extraction_commands"] == 0


def test_body_capability_refusal_consumes_only_one_selected_attempt():
    result = run_suckle_extraction_v1("no_capability")
    assert result.metrics()["selected_extraction_applications"] == 1
    assert result.metrics()["extraction_installations"] == result.metrics()["extraction_commands"] == 0
    assert result.metrics()["local_status"] == "not_applied"


@pytest.mark.parametrize("cadence", [1, 4, 8])
def test_final_endpoint_retirement_preserves_evidence_not_pursuit(cadence):
    trial = new_trial()
    first = trial.focal_step()
    target = first.reservations[0].current
    observed = []
    for tick in range(12):
        if tick and tick % cadence == 0:
            trial.focal_step()
        step = trial.advance_lower()
        if step.command is not None:
            assert step.command.issued_tick < target.expires_at_tick
        observed.extend(r for r in step.reports if r.disposition is LocalTargetDispositionV1.ACHIEVED)
    final = trial.focal_step()
    assert target.expires_at_tick == 8 and observed
    assert len(observed[0].extraction_confirmations) == 4
    assert observed[0].feedback.event_tick <= 8 and observed[0].reported_tick == 8
    assert final.suckle_extraction.status == "local_achieved"
    assert trial.controller.installation_count == 1 and not trial.core.cognition.mapper.reservations(at_tick=12)
    assert not trial.core.suckle.awaiting_final_extraction_evidence(at_tick=12)


def test_missing_final_confirmation_does_not_retain_ownership_indefinitely():
    trial = new_trial()
    trial.focal_step()
    advance(trial, 8)
    trial.focal_step()
    assert trial.core.suckle.awaiting_final_extraction_evidence(at_tick=8)
    # Read-only guard cannot lengthen the original two-tick evidence horizon,
    # even if no further local result is made available.
    assert trial.core.suckle.awaiting_final_extraction_evidence(at_tick=10)
    assert not trial.core.suckle.awaiting_final_extraction_evidence(at_tick=11)
    assert not trial.core.cognition.mapper.reservations(at_tick=8)


def test_cancellation_never_receives_new_permission_from_late_final_evidence():
    trial = new_trial()
    trial.focal_step()
    advance(trial, 7)
    trial.cancel()
    advance(trial, 5)
    cycle = trial.focal_step()
    assert cycle.suckle_extraction.status == "cancelled"
    assert not trial.core.suckle.awaiting_final_extraction_evidence(at_tick=8)
    assert not trial.core.cognition.mapper.reservations(at_tick=12)


@pytest.mark.parametrize("case", ["latch_then_extract", "seek_then_latch", "stand_follow"])
def test_latch_transition_retains_old_I_J_K_task_and_budget(case):
    result = run_suckle_extraction_v1(case)
    extracted = next(c for c in result.run.cycles if isinstance(c.calculation.navigation.application, SuckleExtractionApplicationV1))
    app = extracted.calculation.navigation.application
    assert app.task.latch.status == "latch_established"
    assert app.task.started_tick == app.task.latch.started_tick and app.task.started_cycle == app.task.latch.started_cycle
    assert app.task.applications == app.task.latch.applications + 1
    assert extracted.suckle_task.task is app.task.latch
    prior_latch = [c for c in result.run.cycles if isinstance(c.calculation.navigation.application, SuckleApplicationV1)]
    claims = [c.suckle_correspondence.registration for c in prior_latch if c.suckle_correspondence.registration is not None]
    assert claims and all(claim.preview.task_id == app.task.task_id for claim in claims)
    assert all(c.suckle_task.task is app.task.latch for c in result.run.cycles if c.calculation.cutoff_tick >= extracted.calculation.cutoff_tick)
    assert extracted.suckle_correspondence.registration is None and extracted.suckle_learning_report.new_participation is None
    assert all(r.current.target.origin.task_id == app.task.task_id for r in extracted.reservations)
    assert result.metrics()["local_status"] == "local_achieved"


def test_pending_J_interpretation_blocks_new_extraction_and_keeps_original_question(monkeypatch):
    # A real selected closure application; only its historical event8 measurement
    # is altered as a labelled correspondence fixture. Current event11 remains
    # supported/sealed, so current latch evidence cannot secretly choose the IP.
    trial = new_trial("latch_then_extract")
    first = trial.focal_step()
    original_claim = first.suckle_correspondence.registration
    for _ in range(2):
        advance(trial,4)
        trial.focal_step()
    advance(trial,4)
    altered=[]
    for interval in trial._suckle_intervals:
        samples=tuple(replace(sample,oral_seal=replace(sample.oral_seal,sealed=False))
                      if sample.event_tick==8 else sample for sample in interval.deliveries)
        altered.append(replace(interval,deliveries=samples))
    trial._suckle_intervals[:]=altered
    original_apply=SuckleIPV1.apply
    def forbidden(*_args, **_kwargs):
        raise AssertionError("interpretation must not call either task IP")
    monkeypatch.setattr(SuckleIPV1,"apply",forbidden)
    monkeypatch.setattr(SeekNippleIPV1,"apply",forbidden)
    interpreted=trial.focal_step()
    allocation=interpreted.suckle_attention.allocation
    assert allocation.kind=="interpretation" and interpreted.calculation.navigation.application is None
    request=allocation.interpretation.request
    assert request.outcome.claim is original_claim and request.outcome.status=="mismatch"
    assert request.expires_at_tick==20
    original_task=trial.core.suckle.task
    assert original_task.status=="latch_established"
    monkeypatch.setattr(SuckleIPV1,"apply",original_apply)
    advance(trial,4)
    extracted=trial.focal_step()
    app=extracted.calculation.navigation.application
    assert isinstance(app,SuckleExtractionApplicationV1)
    assert trial.core.suckle.task is original_task and app.task.latch is original_task
    assert request.outcome.status=="mismatch" and request.expires_at_tick==20
    assert not any(reason=="task_invalidated" for _request_id,reason,_tick in trial.core.feeding_detail.suckle_outcome_attention.dispositions())
    assert extracted.suckle_learning_report.new_participation is None


def test_remaining_original_episode_time_can_refuse_the_only_extraction_attempt():
    trial=new_trial("latch_then_extract")
    trial.focal_step()
    for t in (4,8,12):
        advance(trial,t-trial.tick)
        trial.focal_step(visual_bid_priority=(10,70) if t == 12 else None)
    latch=trial.core.suckle.task
    assert latch.status=="latch_established"
    for t in (24,32,40):
        advance(trial,t-trial.tick); trial.focal_step(visual_bid_priority=(10,70))
    advance(trial,47-trial.tick)
    cycle=trial.focal_step()
    app=cycle.calculation.navigation.application
    assert isinstance(app,SuckleExtractionApplicationV1)
    assert app.task.started_tick==latch.started_tick==0
    assert app.contribution.lease_ticks==1 and not cycle.reservations
    assert cycle.suckle_extraction.status=="not_applied"
    advance(trial,1)
    assert trial.focal_step().calculation.navigation.application is None


@pytest.mark.parametrize("case", ["nominal","dry","depleted","milk_sensor_off","latch_then_extract"])
def test_diagnostics_rng_and_durable_sources_are_observers_only(case):
    state=random.getstate()
    result=run_suckle_extraction_v1(case)
    payload=json.dumps(result.as_dict(),sort_keys=True,allow_nan=False)
    assert payload==json.dumps(result.as_dict(),sort_keys=True,allow_nan=False)
    assert random.getstate()==state and result.run.durable_before==result.run.durable_after
    assert result.metrics()["task_pnm_fulfilment"]=="unimplemented_unscored"
    assert not result.metrics()["full_suckle_complete"]


def test_reset_constructs_fresh_owners_not_old_permissions(selected):
    trial,cycle,app=selected
    old=trial.core.suckle
    trial.reset()
    assert trial.core.suckle is not old and trial.core.suckle.extraction_assessment().application is None
    assert trial.core.suckle.task is None and trial.controller.installation_count==0
    with pytest.raises((ValueError,RuntimeError)):
        trial.core.handoff.consume_motor(cycle.receipt)


def test_completed_latch_cannot_clear_the_new_selected_extraction_influence():
    trial = new_trial("latch_then_extract")
    trial.focal_step()
    for cutoff in (4, 8, 12):
        advance(trial, cutoff - trial.tick)
        trial.focal_step()
    app = trial.core.suckle.extraction_assessment().application
    assert isinstance(app, SuckleExtractionApplicationV1)
    source = trial.core.feeding_detail
    assert source._influence == (app.task.task_id, 20)
    advance(trial, 4)
    trial.focal_step()
    assert trial.core.suckle.task is app.task.latch
    assert source._influence == (app.task.task_id, 20)
    assert source.candidate().current_task_persistence_rank == 20
    advance(trial, 4)
    trial.focal_step()
    assert source._influence is None
