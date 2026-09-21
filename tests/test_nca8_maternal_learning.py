"""Maternal eligibility integrity, atomic rejection and original-recipient timing.

Canonical positive records come from the real hierarchy. Mutated records below
are explicit hostile publisher/dependency fixtures, not claimed physical events.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json

import pytest

from cca8_motor_contracts import MotorStreamRefV1
from nca8_followmom import FollowMomProfileV1
from nca8_maternal import MaternalSeedV1, MaternalSourceV1
from nca8_maternal_learning import MaternalLearningHookV1
from nca8_maternal_learning_demo import run_maternal_learning_v1


@pytest.fixture(scope="module")
def records():
    return {name: run_maternal_learning_v1(name) for name in ("nominal_on", "competing_on", "unresolved_current", "narrowed")}


def disposition(result, status):
    return next(item for focal in result.cycles for item in focal.maternal_learning_report.dispositions if item.status == status)


def participant(result, cycle=1):
    return next(focal.maternal_learning_report.new_participation for focal in result.cycles
                if focal.commitment.cycle_id == cycle)


def new_hook(part, *, capacity=32):
    hook = MaternalLearningHookV1(part.claim.preview.basis.stream, part.claim.preview.basis.seed, diagnostic_capacity=capacity)
    hook.reconcile(cycle_id=part.created_cycle, cutoff_tick=part.claim.preview.basis.cutoff_tick, registration=part.claim, task=part.task)
    return hook


def snapshot(hook):
    return json.dumps({"pending": [item.as_dict() for item in hook.pending()], "history": [item.as_dict() for item in hook.history()],
                       "counts": hook.retained_counts(), "cycle": hook._last_cycle, "tick": hook._last_tick,
                       "outcome": hook._last_outcome, "closed": hook._closed}, sort_keys=True)


@pytest.mark.parametrize("bad", [None, 0, 1, "true", (), []])
def test_enablement_requires_boolean(bad):
    with pytest.raises(TypeError):
        FollowMomProfileV1(outcomes_enabled=True, learning_hook_enabled=bad)


def test_hook_is_explicit_and_requires_original_correspondence():
    assert not FollowMomProfileV1().learning_hook_enabled
    with pytest.raises(ValueError):
        FollowMomProfileV1(learning_hook_enabled=True)


def test_maternal_source_owns_one_hook_without_modifying_organization():
    source = MaternalSourceV1(MotorStreamRefV1("owner", 1), MaternalSeedV1())
    before = source.durable_map.as_dict()
    assert source.learning_hook is None
    source.configure_learning_hook()
    assert isinstance(source.learning_hook, MaternalLearningHookV1)
    assert source.learning_hook.source_ref.map_id == "maternal_target"
    assert source.durable_map.as_dict() == before
    with pytest.raises(RuntimeError):
        source.configure_learning_hook()


@pytest.mark.parametrize("bad", [True, False, None, -1, 0, 33, 1.5, "8"])
def test_diagnostic_capacity_cannot_be_unbounded_or_coerced(bad):
    with pytest.raises(ValueError):
        MaternalLearningHookV1(MotorStreamRefV1("a", 1), MaternalSeedV1(), diagnostic_capacity=bad)


@pytest.mark.parametrize("stream,seed", [(None, MaternalSeedV1()), (MotorStreamRefV1("a", 1), None)])
def test_owner_identity_must_be_typed(stream, seed):
    with pytest.raises(TypeError):
        MaternalLearningHookV1(stream, seed)


def test_participation_keeps_original_task_source_and_target_not_current_wnm(records):
    part = participant(records["nominal_on"])
    hook = new_hook(part)
    held, = hook.pending()
    assert held.claim is part.claim and held.task is part.task
    assert held.created_cycle == 1 and held.expires_before_cycle == 5
    assert held.claim.due_tick == 8 and held.claim.expires_at_tick == 16
    assert held.as_dict()["grants_motor_authority"] is False
    assert held.as_dict()["source_map_ref"] == {"map_id": "maternal_target", "revision": 1}
    assert held.claim.targets[0].target.origin == held.claim.request.origin


def test_matched_outcome_consumed_once_with_no_causal_credit(records):
    part = participant(records["nominal_on"])
    outcome = disposition(records["nominal_on"], "accepted_no_update").outcome
    hook = new_hook(part)
    report = hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=(outcome,))
    accepted, = report.dispositions
    assert accepted.status == "accepted_no_update" and accepted.outcome is outcome
    assert len(accepted.accepted_relations) == 3 and not hook.pending()
    assert accepted.as_dict()["action_causation"] == "uncertain"
    repeat = hook.reconcile(cycle_id=5, cutoff_tick=16, outcomes=(outcome,))
    assert [item.status for item in repeat.dispositions] == ["duplicate_ignored"]
    assert report.as_dict()["durable_learning_updates"] == report.as_dict()["ledger_rows_executed"] == 0


@pytest.mark.parametrize("cycle,tick", [(True, 4), (0, 4), (2.0, 4), ("2", 4), (2, True), (2, -1), (2, 4.0), (2, 2**63)])
def test_invalid_reconciliation_time_has_no_partial_effect(records, cycle, tick):
    hook = new_hook(participant(records["nominal_on"]))
    before = snapshot(hook)
    with pytest.raises(ValueError):
        hook.reconcile(cycle_id=cycle, cutoff_tick=tick)
    assert snapshot(hook) == before


@pytest.mark.parametrize("flag", ["comparison_enabled", "attention_enabled"])
@pytest.mark.parametrize("bad", [None, 0, 1, "false"])
def test_route_flags_are_boolean_and_atomic(records, flag, bad):
    hook = new_hook(participant(records["nominal_on"]))
    before = snapshot(hook)
    with pytest.raises(TypeError):
        hook.reconcile(cycle_id=2, cutoff_tick=4, **{flag: bad})
    assert snapshot(hook) == before


@pytest.mark.parametrize("change", [
    {"number": True}, {"number": 0}, {"command_intervals": True}, {"command_intervals": -1}, {"command_intervals": 9},
    {"command_intervals": 0}, {"status": "success"}, {"status": "mismatch"}, {"status": "unknown"}, {"evaluated_tick": 13},
    {"evaluated_tick": 8}, {"evaluated_tick": True}, {"relations": ()}, {"relations": (("self_position", "matched"),)},
    {"relations": (("self_position", "matched"),) * 3}, {"relations": (("wrong", "matched"),)},
    {"relations": (("self_position", "success"),)}, {"relations": [["self_position", "matched"]]},
    {"residuals": (("self_position", float("nan")),)}, {"residuals": (("self_position", True),)},
    {"residuals": (("self_position", -0.1),)}, {"residuals": (("self_position", 0.1),)},
    {"residuals": (("self_position", 0.0),) * 2}, {"residuals": []}, {"evidence": None}, {"evidence": "observed"},
])
def test_malformed_canonical_result_cannot_change_eligibility(records, change):
    part = participant(records["nominal_on"])
    outcome = disposition(records["nominal_on"], "accepted_no_update").outcome
    hook = new_hook(part)
    before = snapshot(hook)
    with pytest.raises((TypeError, ValueError)):
        hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=(replace(outcome, **change),))
    assert snapshot(hook) == before


@pytest.mark.parametrize("field,value", [("event_tick", 7), ("available_tick", 17), ("sample_id", 1), ("frame_id", "scene_xy:other"),
                                         ("stream", MotorStreamRefV1("other", 1))])
def test_wrong_endpoint_or_frame_is_not_teaching(records, field, value):
    part = participant(records["nominal_on"])
    outcome = disposition(records["nominal_on"], "accepted_no_update").outcome
    hook = new_hook(part)
    before = snapshot(hook)
    bad = replace(outcome, evidence=replace(outcome.evidence, **{field: value}))
    with pytest.raises(ValueError):
        hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=(bad,))
    assert snapshot(hook) == before


def test_copy_of_equal_claim_is_not_original_participation(records):
    part = participant(records["nominal_on"])
    outcome = disposition(records["nominal_on"], "accepted_no_update").outcome
    hook = new_hook(part)
    before = snapshot(hook)
    with pytest.raises(ValueError, match="copied|changed"):
        hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=(replace(outcome, claim=replace(outcome.claim)),))
    assert snapshot(hook) == before


@pytest.mark.parametrize("status", ["not_applied", "cancelled", "interrupted", "expired_unresolved", "unresolved_stopped", "comparison_disabled"])
def test_adverse_or_unexecuted_evidence_does_not_become_positive_teaching(records, status):
    part = participant(records["nominal_on"])
    outcome = disposition(records["nominal_on"], "accepted_no_update").outcome
    hook = new_hook(part)
    adverse = replace(outcome, status=status, evidence=None, command_intervals=0, relations=(), residuals=())
    report = hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=(adverse,))
    assert report.dispositions[0].status == "rejected_" + status
    assert not report.dispositions[0].accepted_relations and not hook.pending()


def test_observed_without_commands_preserves_uncertain_credit(records):
    part = participant(records["nominal_on"])
    outcome = disposition(records["nominal_on"], "accepted_no_update").outcome
    report = new_hook(part).reconcile(cycle_id=4, cutoff_tick=12,
                                    outcomes=(replace(outcome, status="observed_without_command", command_intervals=0),))
    assert report.dispositions[0].status == "rejected_observed_without_command"
    assert not report.dispositions[0].accepted_relations


def test_partial_unknown_is_preserved_without_invented_failure(records):
    part = participant(records["nominal_on"])
    outcome = disposition(records["nominal_on"], "accepted_no_update").outcome
    unknown = replace(outcome, status="unknown", relations=(("self_position", "unknown"), ("maternal_anchor", "matched"),
                                                           ("separation", "unknown")), residuals=(("maternal_anchor", 0.0),),
                      evidence=replace(outcome.evidence, self_position=None))
    report = new_hook(part).reconcile(cycle_id=4, cutoff_tick=12, outcomes=(unknown,))
    assert report.dispositions[0].status == "rejected_unknown" and not report.dispositions[0].accepted_relations


def test_narrowed_permission_teaches_only_still_compatible_relation(records):
    result = records["narrowed"]
    accepted = disposition(result, "accepted_no_update")
    assert accepted.accepted_relations == (("maternal_anchor", "matched"),)
    assert set(accepted.outcome.claim.unevaluable_relations) == {"self_position", "separation"}
    assert accepted.outcome.status == "partly_matched"


@pytest.mark.parametrize("batch", ["list", "oversized", "duplicate", "bad_second"])
def test_bad_outcome_batches_are_atomic(records, batch):
    part = participant(records["nominal_on"])
    outcome = disposition(records["nominal_on"], "accepted_no_update").outcome
    payload = {"list": [outcome], "oversized": (outcome,) * 9, "duplicate": (outcome, outcome), "bad_second": (outcome, None)}[batch]
    hook = new_hook(part)
    before = snapshot(hook)
    with pytest.raises((TypeError, ValueError)):
        hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=payload)
    assert snapshot(hook) == before


def test_unregistered_but_well_formed_operation_is_not_sent_to_current_focus(records):
    outcome = disposition(records["nominal_on"], "accepted_no_update").outcome
    hook = MaternalLearningHookV1(outcome.claim.preview.basis.stream, outcome.claim.preview.basis.seed)
    report = hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=(outcome,))
    assert report.dispositions[0].status == "rejected_unregistered_operation"


def test_close_revokes_pending_and_rejects_same_generation_reuse(records):
    hook = new_hook(participant(records["nominal_on"]))
    hook.close()
    assert not hook.pending()
    with pytest.raises(RuntimeError):
        hook.reconcile(cycle_id=2, cutoff_tick=4)


def test_wrong_owner_stream_or_seed_cannot_register_old_claim(records):
    part = participant(records["nominal_on"])
    for stream, seed in ((MotorStreamRefV1("other", 1), part.claim.preview.basis.seed),
                         (replace(part.claim.preview.basis.stream, generation=2), part.claim.preview.basis.seed),
                         (part.claim.preview.basis.stream, MaternalSeedV1(region_id="region_2"))):
        hook = MaternalLearningHookV1(stream, seed)
        with pytest.raises(ValueError):
            hook.reconcile(cycle_id=1, cutoff_tick=0, registration=part.claim, task=part.task)
        assert not hook.pending()


def test_just_issued_claim_and_relabelled_participation_cannot_supply_future_evidence(records):
    part = participant(records["nominal_on"])
    outcome = disposition(records["nominal_on"], "accepted_no_update").outcome
    hook = MaternalLearningHookV1(part.claim.preview.basis.stream, part.claim.preview.basis.seed)
    with pytest.raises(ValueError):
        hook.reconcile(cycle_id=1, cutoff_tick=0, registration=part.claim, task=part.task, outcomes=(outcome,))
    with pytest.raises(ValueError):
        hook.reconcile(cycle_id=2, cutoff_tick=4, registration=part.claim, task=part.task)
    assert not hook.pending()


def test_second_f_call_and_reversed_clock_cannot_repeat_work(records):
    hook = new_hook(participant(records["nominal_on"]))
    before = snapshot(hook)
    for cycle, tick in ((1, 0), (1, 4), (2, 0)):
        with pytest.raises(RuntimeError):
            hook.reconcile(cycle_id=cycle, cutoff_tick=tick)
        assert snapshot(hook) == before


def test_interpretation_waits_for_actual_existing_allocation(records):
    part = participant(records["competing_on"], cycle=3)
    focal = records["competing_on"].cycles[5]
    request, = focal.maternal_attention.created
    hook = new_hook(part)
    report = hook.reconcile(cycle_id=6, cutoff_tick=20, outcomes=(request.outcome,), requests=(request,))
    assert [item.status for item in report.dispositions] == ["pending_interpretation"]
    assert hook.pending()[0].request is request
    later = hook.reconcile(cycle_id=7, cutoff_tick=24)
    assert [item.status for item in later.dispositions] == ["eligibility_expired"]
    assert not hook.pending() and request.expires_at_tick == 28


def test_actual_resolved_interpretation_permits_same_f_admission_but_no_update(records):
    part = participant(records["competing_on"], cycle=3)
    focal = records["competing_on"].cycles[5]
    request, = focal.maternal_attention.created
    interpreted = focal.maternal_attention.allocation.interpretation
    report = new_hook(part).reconcile(cycle_id=6, cutoff_tick=20, outcomes=(request.outcome,),
                                     requests=(request,), interpretation=interpreted)
    accepted = report.dispositions[-1]
    assert accepted.status == "accepted_no_update" and accepted.interpretation is interpreted
    assert not report.pending and report.as_dict()["durable_learning_updates"] == 0


def test_unresolved_interpretation_keeps_original_expiry(records):
    result = records["unresolved_current"]
    focal = result.cycles[5]
    request, = focal.maternal_attention.created
    hook = new_hook(participant(result, cycle=3))
    report = hook.reconcile(cycle_id=6, cutoff_tick=20, outcomes=(request.outcome,), requests=(request,),
                            interpretation=focal.maternal_attention.allocation.interpretation)
    assert report.dispositions[-1].status == "pending_unresolved_interpretation"
    assert report.pending[0].expires_before_cycle == 7
    assert hook.reconcile(cycle_id=7, cutoff_tick=24).dispositions[0].status == "eligibility_expired"


@pytest.mark.parametrize("mutation", ["copy_request", "wrong_cycle", "wrong_tick", "status", "relations", "foreign_source"])
def test_bad_interpretation_is_atomically_rejected(records, mutation):
    result = records["competing_on"]
    focal = result.cycles[5]
    request, = focal.maternal_attention.created
    original = focal.maternal_attention.allocation.interpretation
    changed = {
        "copy_request": replace(original, request=replace(request)), "wrong_cycle": replace(original, cycle_id=5),
        "wrong_tick": replace(original, cutoff_tick=16), "status": replace(original, status="historical_resolved"),
        "relations": replace(original, relation_relevance=()),
        "foreign_source": replace(original, current_source=replace(original.current_source, visual=replace(original.current_source.visual, stream=MotorStreamRefV1("foreign", 1)))),
    }[mutation]
    hook = new_hook(participant(result, cycle=3))
    before = snapshot(hook)
    with pytest.raises(ValueError):
        hook.reconcile(cycle_id=6, cutoff_tick=20, outcomes=(request.outcome,), requests=(request,), interpretation=changed)
    assert snapshot(hook) == before


@pytest.mark.parametrize("mutation", ["copy_outcome", "wrong_time", "duplicate", "nonsignificant", "mutable"])
def test_bad_dependency_batch_never_partially_activates_recipient(records, mutation):
    result = records["competing_on"]
    focal = result.cycles[5]
    request, = focal.maternal_attention.created
    payload = {
        "copy_outcome": (replace(request, outcome=replace(request.outcome)),),
        "wrong_time": (replace(request, admitted_tick=16),), "duplicate": (request, request),
        "nonsignificant": (replace(request, relations=("maternal_anchor",)),), "mutable": [request],
    }[mutation]
    hook = new_hook(participant(result, cycle=3))
    before = snapshot(hook)
    with pytest.raises(ValueError):
        hook.reconcile(cycle_id=6, cutoff_tick=20, outcomes=(request.outcome,), requests=payload)
    assert snapshot(hook) == before


def test_disabled_attention_does_not_supply_free_interpretation(records):
    result = records["competing_on"]
    focal = result.cycles[5]
    request, = focal.maternal_attention.created
    hook = new_hook(participant(result, cycle=3))
    report = hook.reconcile(cycle_id=6, cutoff_tick=20, outcomes=(request.outcome,), attention_enabled=False)
    assert report.pending[0].awaiting_interpretation and report.pending[0].request is None
    assert all(item.status != "accepted_no_update" for item in report.dispositions)
    assert hook.reconcile(cycle_id=7, cutoff_tick=24, attention_enabled=False).dispositions[0].status == "eligibility_expired"


def test_disabled_attention_rejects_claimed_focal_result(records):
    focal = records["competing_on"].cycles[5]
    hook = new_hook(participant(records["competing_on"], cycle=3))
    with pytest.raises(ValueError):
        hook.reconcile(cycle_id=6, cutoff_tick=20, interpretation=focal.maternal_attention.allocation.interpretation,
                       attention_enabled=False)


def test_saturated_participant_buffer_refuses_new_work_atomically(records):
    # Deliberately saturate internal storage to exercise a future/broken producer;
    # normal one-application/four-cycle scheduling does not fill eight slots.
    part = participant(records["nominal_on"])
    next_part = participant(records["nominal_on"], cycle=3)
    hook = new_hook(part)
    hook._pending = {"saturated:" + str(index): part for index in range(8)}
    before = snapshot(hook)
    with pytest.raises(OverflowError):
        hook.reconcile(cycle_id=3, cutoff_tick=8, registration=next_part.claim, task=next_part.task)
    assert snapshot(hook) == before


def test_exports_are_detached_frozen_and_do_not_extend_eligibility(records):
    part = participant(records["nominal_on"])
    hook = new_hook(part)
    before = snapshot(hook)
    exported = hook.pending()[0].as_dict()
    exported["compatible_relations"].clear()
    exported["origin"]["task_id"] = "other"
    with pytest.raises(FrozenInstanceError):
        hook.pending()[0].created_cycle = 100
    assert snapshot(hook) == before
    assert hook.reconcile(cycle_id=5, cutoff_tick=4).dispositions[0].status == "eligibility_expired"


def test_diagnostic_truncation_and_rereads_do_not_control_acceptance(records):
    part = participant(records["nominal_on"])
    outcome = disposition(records["nominal_on"], "accepted_no_update").outcome
    tiny, full = new_hook(part, capacity=1), new_hook(part)
    assert tiny.reconcile(cycle_id=4, cutoff_tick=12, outcomes=(outcome,)) == full.reconcile(cycle_id=4, cutoff_tick=12, outcomes=(outcome,))
    for cycle in range(5, 20):
        tiny.history(); tiny.pending()
        assert tiny.reconcile(cycle_id=cycle, cutoff_tick=cycle * 4, outcomes=(outcome,)) == full.reconcile(
            cycle_id=cycle, cutoff_tick=cycle * 4, outcomes=(outcome,))
    assert len(tiny.history()) == 1 and len(full.history()) == 16


def test_renumbered_outcome_cannot_replace_pending_interpretation_evidence(records):
    result = records["competing_on"]
    focal = result.cycles[5]
    request, = focal.maternal_attention.created
    hook = new_hook(participant(result, cycle=3))
    hook.reconcile(cycle_id=6, cutoff_tick=20, outcomes=(request.outcome,), requests=(request,))
    before = snapshot(hook)
    changed = replace(request.outcome, number=request.outcome.number + 1, evaluated_tick=21)
    with pytest.raises(ValueError, match="second outcome"):
        hook.reconcile(cycle_id=7, cutoff_tick=21, outcomes=(changed,))
    assert snapshot(hook) == before
    assert hook.pending()[0].outcome is request.outcome
    assert hook.pending()[0].request is request


def test_distinct_numbers_do_not_allow_two_results_for_the_same_original_claim(records):
    part = participant(records["nominal_on"])
    outcome = disposition(records["nominal_on"], "accepted_no_update").outcome
    hook = new_hook(part)
    before = snapshot(hook)
    with pytest.raises(ValueError, match="two publisher outcomes"):
        hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=(outcome, replace(outcome, number=outcome.number + 1)))
    assert snapshot(hook) == before
