"""L-D original-claim, interval and execution tests.

Modified packets below are labelled correspondence fixtures. They are not new
physical runs, action policies or claims that contradictory reports came from
unchanged physics. Live contrasts are in the companion shared-review tests.
"""
from dataclasses import replace
import json
import random

import pytest

from cca8_motor_contracts import MotorStreamRefV1
from cca8_navmap_kernel import NavPointV1
from nca8_sensorimotor_contracts import LocalTargetDispositionV1
from nca8_suckle import SuckleProfileV1, SuckleExtractionApplicationV1, SuckleIPV1
from nca8_suckle_outcomes import SuckleIntervalEvidenceV1
from nca8_suckle_extraction_outcomes import SuckleExtractionClaimV1, SuckleExtractionOutcomeRuntimeV1
from nca8_suckle_extraction_demo import suckle_extraction_profile_v1, create_suckle_extraction_trial_v1


def make_trial(case="nominal", **options):
    profile = suckle_extraction_profile_v1(case)
    options = {"extraction_outcomes_enabled": True, **options}
    profile = replace(profile, latch=replace(profile.latch, suckle=replace(profile.latch.suckle, **options)))
    return create_suckle_extraction_trial_v1(profile)


def snapshot(owner):
    return json.dumps({"claim": owner._claim.as_dict() if owner._claim else None,
                       "evidence": repr(owner._evidence), "history": [r.as_dict() for r in owner.history()],
                       "cutoff": owner._last_cutoff, "interval": owner._last_interval, "command": owner._last_command,
                       "closed": owner._closed}, sort_keys=True)


@pytest.fixture(scope="module")
def material():
    trial = make_trial()
    first = trial.focal_step()
    intervals = []
    for _ in range(16):
        trial.advance_lower()
        intervals.append(trial._suckle_intervals[-1])
        if trial.tick % 4 == 0:
            trial.focal_step()
    return first, tuple(intervals)


def reader(first, *, compare=True, install=True):
    app = first.calculation.navigation.application
    owner = SuckleExtractionOutcomeRuntimeV1(app.contribution.origin.stream, compare_predictions=compare)
    owner.consume_intervals((), cutoff_tick=0)
    claim = owner.register(app, first.calculation.proposal, tuple(r.current for r in first.reservations))
    if install:
        owner.installed(claim, at_tick=0)
    return owner, claim


def consume(owner, intervals):
    return owner.consume_intervals(intervals, cutoff_tick=owner._last_interval + len(intervals) + 1)


@pytest.mark.parametrize("field", ["extraction_outcomes_enabled", "extraction_prediction_comparison_enabled"])
@pytest.mark.parametrize("bad", [None, 0, 1, "true", [], {}])
def test_switches_are_actual_booleans(field, bad):
    with pytest.raises(TypeError):
        SuckleProfileV1(**{field: bad})


def test_independent_route_requires_extraction_not_old_closure_learning():
    with pytest.raises(ValueError):
        SuckleProfileV1(extraction_outcomes_enabled=True)
    with pytest.raises(ValueError):
        SuckleProfileV1(extraction_enabled=True, extraction_prediction_comparison_enabled=False)
    trial = make_trial(outcomes_enabled=False, outcome_attention_enabled=False, learning_hook_enabled=False)
    assert trial.core.suckle_outcomes is None
    trial.focal_step()
    for _ in range(20):
        trial.advance_lower()
        if trial.tick % 4 == 0:
            trial.focal_step()
    outcome, = trial.core.extraction_outcomes.history()
    assert dict(outcome.relations)["finite_reciprocation"] == "matched"
    assert not trial._suckle_intervals


def test_default_disabled_retains_old_export_and_no_reader():
    profile = suckle_extraction_profile_v1()
    assert "extraction_prediction_comparison_enabled" not in profile.latch.suckle.as_dict()
    trial = create_suckle_extraction_trial_v1(profile)
    assert trial.core.extraction_outcomes is None
    assert "extraction_correspondence" not in trial.focal_step().as_dict()


def test_registration_precedes_F_and_physical_install(monkeypatch):
    trial = make_trial()
    hook = trial.core.feeding_detail.suckle_learning_hook
    original = hook.reconcile
    seen = []
    def capture(**kwargs):
        claim = trial.core.extraction_outcomes.pending()
        seen.append((claim, trial.controller.installation_count, trial.core.extraction_outcomes._evidence.installed))
        assert kwargs["registration"] is None  # K has no new extraction participant.
        return original(**kwargs)
    monkeypatch.setattr(hook, "reconcile", capture)
    first = trial.focal_step()
    assert len(seen) == 1 and seen[0][0] is first.extraction_correspondence.registration
    assert seen[0][1:] == (0, False)
    assert trial.core.extraction_outcomes._evidence.installed
    assert trial.tick == 0 and first.extraction_correspondence.outcomes == ()
    claim = first.extraction_correspondence.registration
    assert (claim.start_tick, claim.due_tick, claim.last_acceptable_availability_tick) == (0, 8, 16)


def test_live_original_registration_and_final_result_are_single_use(material):
    first, intervals = material
    owner, claim = reader(first)
    assert consume(owner, intervals[:4]) == ()
    assert consume(owner, intervals[4:8]) == ()
    result, = consume(owner, intervals[8:12])
    assert result.claim is claim and owner.pending() is None
    assert result.status == "local_sequence_observed" and result.end_tick == 7
    assert set(dict(result.relations).values()) == {"matched"}
    assert result.command_ticks == (0, 2, 4, 6)
    assert len(result.confirmations) == 4
    assert result.milk_evidence()["exact_observed_total"] == pytest.approx(.2)
    assert consume(owner, intervals[12:]) == ()
    assert owner.history() == (result,)
    with pytest.raises(RuntimeError):
        owner.register(first.calculation.navigation.application, first.calculation.proposal, claim.targets)


@pytest.mark.parametrize("change", ["copy_request", "foreign_request", "copy_binding", "missing_binding", "late", "closure"])
def test_register_rejects_wrong_originals_without_mutation(material, change):
    first, _ = material
    app, proposal = first.calculation.navigation.application, first.calculation.proposal
    targets = tuple(r.current for r in first.reservations)
    owner = SuckleExtractionOutcomeRuntimeV1(app.contribution.origin.stream)
    owner.consume_intervals((), cutoff_tick=0)
    if change == "copy_request":
        copied = replace(proposal.request)
        proposal = replace(proposal, request=copied, extraction_preview=replace(proposal.extraction_preview, request=copied))
    elif change == "foreign_request":
        owner = SuckleExtractionOutcomeRuntimeV1(MotorStreamRefV1("other", 1)); owner.consume_intervals((), cutoff_tick=0)
    elif change == "copy_binding":
        targets = (replace(targets[0], target=replace(targets[0].target)),)
    elif change == "missing_binding":
        targets = ()
    elif change == "late":
        owner.consume_intervals((SuckleIntervalEvidenceV1(0, None, (), (), ()),), cutoff_tick=1)
    else:
        app = object()
    before = snapshot(owner)
    with pytest.raises((ValueError, TypeError)):
        owner.register(app, proposal, targets)
    assert snapshot(owner) == before


@pytest.mark.parametrize("change", ["copy", "time", "replay"])
def test_installation_requires_exact_awaiting_claim(material, change):
    first, _ = material
    owner, claim = reader(first, install=change == "replay")
    before = snapshot(owner)
    with pytest.raises(ValueError):
        owner.installed(replace(claim) if change == "copy" else claim, at_tick=1 if change == "time" else 0)
    assert snapshot(owner) == before


@pytest.mark.parametrize("field,value", [("outward_offset", .11), ("repetitions", 1), ("lease_ticks", 7)])
def test_claim_rejects_modified_target_pattern(material, field, value):
    first, _ = material
    app = first.calculation.navigation.application
    target = first.reservations[0].current
    with pytest.raises(ValueError):
        SuckleExtractionClaimV1(app, (replace(target, target=replace(target.target, **{field: value})),))


@pytest.mark.parametrize("mode", ["missing", "wrong_category", "wrong_parent", "moved_detail", "wrong_frame"])
def test_same_actual_movement_result_does_not_prove_original_scene(material, mode):
    first, intervals = material
    app = first.calculation.navigation.application
    changed = []
    for interval in intervals[:12]:
        observations = []
        for observation in interval.observations:
            if mode == "missing":
                continue
            detections = []
            for detection in observation.detections:
                if detection.region_id == app.projection.region_id:
                    if mode == "wrong_category": detection = replace(detection, descriptor="hazard")
                    if mode == "moved_detail": detection = replace(detection, position=NavPointV1(2.0, 0.0))
                if mode == "wrong_parent" and detection.region_id == app.projection.basis.seed.parent_region_id:
                    detection = replace(detection, descriptor="hazard")
                detections.append(detection)
            observations.append(replace(observation, detections=tuple(detections)))
        if mode == "wrong_frame":
            # An inconsistent paired frame is transport corruption, not uncertain perception.
            if interval.observations:
                with pytest.raises(ValueError):
                    replace(interval, observations=(replace(interval.observations[0], frame_id="wrong_frame"),))
            continue
        changed.append(replace(interval, observations=tuple(observations)))
    if mode == "wrong_frame": return
    owner, _ = reader(first)
    result, = consume(owner, tuple(changed))
    assert result.status == "local_sequence_observed"
    assert dict(result.relations)["finite_reciprocation"] == "matched"
    assert dict(result.relations)["detail_anchor"] == ("unknown" if mode == "missing" else "mismatch")
    assert result.milk_evidence()["exact_observed_total"] == pytest.approx(.2)
    assert result.milk_evidence()["original_detail_associated_event_ticks"] == []


def test_comparison_off_preserves_every_original_execution_and_sensory_record(material):
    first, intervals = material
    on, claim_on = reader(first)
    off, claim_off = reader(first, compare=False)
    a, = consume(on, intervals[:12]); b, = consume(off, intervals[:12])
    assert claim_on == claim_off
    assert a.status == b.status and a.samples == b.samples and a.confirmations == b.confirmations
    assert a.command_ticks == b.command_ticks and a.milk_evidence() == b.milk_evidence()
    assert {value for _, value in b.relations} == {"comparison_disabled"}


def map_samples(intervals, transform):
    """Test-only coherent replacement of every occurrence of one physical acquisition."""
    return tuple(replace(i, deliveries=tuple(transform(s) for s in i.deliveries), reports=tuple(
        replace(r, feedback=transform(r.feedback) if r.feedback else None,
                extraction_confirmations=tuple(transform(s) for s in r.extraction_confirmations)) for r in i.reports)) for i in intervals)


@pytest.mark.parametrize("mode", ["missing_all", "missing_one", "zero", "late", "duplicate"])
def test_milk_interval_coverage_is_not_physical_total_or_repeated_experience(material, mode):
    first, intervals = material
    def change(s):
        facet = s.oral_extraction
        if facet is None or facet.interval_start_tick is None:
            return s
        value = None if mode == "missing_all" or mode == "missing_one" and s.event_tick == 1 else 0.0 if mode == "zero" else facet.milk_transferred_units
        return replace(s, oral_extraction=replace(facet, milk_transferred_units=value))
    data = map_samples(intervals[:12], change)
    if mode == "late":
        # Event 2 is not an endpoint confirmation; delay only this measurement beyond deadline.
        kept = []
        late = None
        for item in data:
            for s in item.deliveries:
                if s.event_tick == 2: late = replace(s, available_tick=17)
            kept.append(replace(item, deliveries=tuple(s for s in item.deliveries if s.event_tick != 2),
                                observations=tuple(o for o in item.observations if o.event_tick != 2),
                                reports=tuple(replace(r, feedback=r.extraction_confirmations[-1])
                                              if r.feedback and r.feedback.event_tick == 2 else r for r in item.reports)))
        data = tuple(kept)
        owner, _ = reader(first)
        assert consume(owner, data) == ()
        extra = tuple(SuckleIntervalEvidenceV1(tick, None, (), (late,) if tick == 16 else (), ()) for tick in range(12, 20))
        result, = consume(owner, extra)
        assert 2 in result.milk_evidence()["missing_event_ticks"]
        assert result.status == "local_sequence_observed"
        return
    if mode == "duplicate":
        duplicate = data[1].deliveries[0]
        data = (*data[:10], replace(data[10], deliveries=(*data[10].deliveries, duplicate)), data[11])
    owner, _ = reader(first)
    result, = consume(owner, data)
    milk = result.milk_evidence()
    assert milk["coverage"] == ("unavailable" if mode == "missing_all" else "partial" if mode == "missing_one" else "complete")
    assert milk["known_interval_sum"] == pytest.approx(0 if mode in {"missing_all", "zero"} else .1 if mode == "missing_one" else .2)
    if mode == "missing_one": assert milk["exact_observed_total"] is None and milk["missing_event_ticks"] == [1]


@pytest.mark.parametrize("mode", ["gap", "repeat_interval", "wrong_stream", "command_replay", "conflicting_sample", "copy_target", "bad_prefix"])
def test_entire_invalid_batch_is_atomic(material, mode):
    first, intervals = material
    owner, _ = reader(first)
    data = list(intervals[:12])
    if mode == "gap": data.pop(5)
    elif mode == "repeat_interval": data[5] = data[4]
    elif mode == "wrong_stream":
        item = data[8]; sample = item.deliveries[0]
        data[8] = replace(item, deliveries=(replace(sample, stream=MotorStreamRefV1("foreign", 1)),), observations=())
    elif mode == "command_replay": data[6] = replace(data[6], command=replace(data[6].command, command_id=data[4].command.command_id))
    elif mode == "conflicting_sample":
        sample = intervals[1].deliveries[0]
        data[10] = replace(data[10], deliveries=(replace(sample, oral_extraction=replace(sample.oral_extraction, milk_transferred_units=.9)),), observations=())
    elif mode == "copy_target":
        report = data[9].reports[0]
        data[9] = replace(data[9], reports=(replace(report, committed_target=replace(report.committed_target)),))
    else:
        report = data[8].reports[0]
        # Deliberately corrupted frozen report; replay its validator at the consumer boundary.
        forged = replace(report)
        object.__setattr__(forged, "extraction_confirmations", ())
        data[8] = replace(data[8], reports=(forged,))
    before = snapshot(owner)
    with pytest.raises((ValueError, TypeError)):
        owner.consume_intervals(tuple(data), cutoff_tick=12)
    assert snapshot(owner) == before
    assert consume(owner, intervals[:12])[0].status == "local_sequence_observed"


@pytest.mark.parametrize("bad", [True, -1, 2**63, 1.5, "12"])
def test_bad_cutoff_cannot_consume(material, bad):
    owner, _ = reader(material[0])
    before = snapshot(owner)
    with pytest.raises(ValueError): owner.consume_intervals((), cutoff_tick=bad)
    assert snapshot(owner) == before


def test_no_installation_or_command_cannot_score_movement(material):
    first, intervals = material
    uninstalled, _ = reader(first, install=False)
    data = tuple(replace(i, command=None, reports=()) for i in intervals)
    assert consume(uninstalled, data) == ()
    result, = consume(uninstalled, tuple(SuckleIntervalEvidenceV1(t, None, (), (), ()) for t in range(16, 20)))
    assert result.status == "uninstalled_unresolved" and not result.installed
    assert set(dict(result.relations).values()) == {"unresolved_execution"}
    # The measurement is retained, but not claimed to be caused by the unapplied action.
    assert result.milk_evidence()["known_interval_sum"] == pytest.approx(.2)
    no_command, _ = reader(first)
    observed, = consume(no_command, tuple(replace(i, command=None) for i in intervals[:12]))
    assert observed.status == "observed_without_command"
    assert observed.command_ticks == () and dict(observed.relations)["finite_reciprocation"] == "unresolved_execution"


def test_late_timely_batch_is_accounted_before_expiry_and_result_never_revised(material):
    first, intervals = material
    owner, _ = reader(first)
    assert consume(owner, intervals[:4]) == ()
    # All original sample availability is timely; later focal polling is not a new event.
    batch = (*intervals[4:], *(SuckleIntervalEvidenceV1(t, None, (), (), ()) for t in range(16, 20)))
    result, = consume(owner, batch)
    assert result.evaluated_tick == 20 and result.claim.last_acceptable_availability_tick == 16
    assert set(dict(result.relations).values()) == {"matched"}
    before = result.as_dict()
    assert consume(owner, (SuckleIntervalEvidenceV1(20, None, (), (), ()),)) == ()
    owner.close(reason="later_fault")
    assert owner.history()[0] is result and result.as_dict() == before


def test_close_preserves_partial_exposure_and_reports_uncertainty(material):
    owner, claim = reader(material[0])
    consume(owner, material[1][:2])
    owner.close(reason="unknown_effect_after_physical_call")
    outcome, = owner.history()
    assert outcome.claim is claim and outcome.command_ticks == (0,)
    assert outcome.status == "execution_unknown_after_fault"
    assert dict(outcome.relations)["finite_reciprocation"] == "unresolved_execution"
    with pytest.raises(ValueError): consume(owner, material[1][2:4])
    owner.close(reason="duplicate_close")
    assert owner.history() == (outcome,)


def test_end_does_not_discard_delayed_measurements_or_renew_lease(material):
    first, intervals = material
    owner, claim = reader(first)
    consume(owner, intervals[:2])
    owner.end_execution(at_tick=2)
    assert owner.pending() is claim and claim.due_tick == 8 and claim.last_acceptable_availability_tick == 16
    # No actual commands after cancellation; delayed original event 2 still arrives.
    data = tuple(replace(i, command=None, reports=()) for i in intervals[2:8])
    outcome, = consume(owner, data)
    assert outcome.status == "interrupted" and outcome.end_tick == 2
    assert outcome.milk_evidence()["exact_observed_total"] == pytest.approx(.1)
    assert claim.targets[0].expires_at_tick == 8


def test_duplicate_consume_and_oversized_batch_are_rejected(material):
    owner, _ = reader(material[0])
    consume(owner, material[1][:4])
    before = snapshot(owner)
    with pytest.raises(ValueError): owner.consume_intervals(material[1][:4], cutoff_tick=4)
    with pytest.raises(ValueError): owner.consume_intervals(tuple(SuckleIntervalEvidenceV1(t, None, (), (), ()) for t in range(4, 21)), cutoff_tick=21)
    assert snapshot(owner) == before


def test_observer_reads_are_detached_and_cannot_call_an_IP(material, monkeypatch):
    owner, _ = reader(material[0]); result, = consume(owner, material[1][:12])
    rng = random.getstate(); before = snapshot(owner)
    def forbidden(*args, **kwargs): raise AssertionError("evidence reader attempted a new IP application")
    monkeypatch.setattr(SuckleIPV1, "apply", forbidden)
    for _ in range(3):
        result.as_dict()["samples"].clear()
        owner.retained_counts(); owner.pending(); owner.history()
    assert snapshot(owner) == before and random.getstate() == rng


def test_reset_replaces_owner_and_does_not_recover_old_permissions():
    trial = make_trial(); old = trial.core.extraction_outcomes
    trial.focal_step(); trial.advance_lower(); trial.reset()
    assert trial.core.extraction_outcomes is not old
    assert trial.core.extraction_outcomes.history() == () and trial.core.extraction_outcomes.pending() is None
    assert trial.controller.installation_count == 0 and trial.tick == 0


def test_conflicting_known_sample_id_cannot_hide_outside_original_window(material):
    owner, _ = reader(material[0]); consume(owner, material[1][:12])
    original = material[1][1].deliveries[0]
    forged = replace(original, event_tick=20, available_tick=20,
                     oral_extraction=replace(original.oral_extraction, interval_start_tick=19))
    batch = tuple(SuckleIntervalEvidenceV1(t, None, (), (forged,) if t == 19 else (), ()) for t in range(12, 20))
    before = snapshot(owner)
    with pytest.raises(ValueError, match="conflicting"):
        consume(owner, batch)
    assert snapshot(owner) == before


def test_late_final_confirmation_has_no_authority_but_can_complete_historical_evidence(material):
    first, intervals = material
    owner, _ = reader(first)
    actual = intervals[8].reports[0]
    final_sample = actual.extraction_confirmations[-1]
    delayed = replace(final_sample, available_tick=16)
    first_batch = tuple(replace(i, deliveries=tuple(s for s in i.deliveries if s.sample_id != final_sample.sample_id),
                                observations=tuple(o for o in i.observations if o.sample_id != final_sample.sample_id)) for i in intervals[:8])
    assert consume(owner, first_batch) == ()
    prefix = intervals[7].reports[0]
    expired = replace(prefix, disposition=LocalTargetDispositionV1.EXPIRED, reported_tick=8, reason="lease_expired")
    later = tuple(SuckleIntervalEvidenceV1(t, None, (expired,) if t == 8 else (), (delayed,) if t == 15 else (), ())
                  for t in range(8, 16))
    assert consume(owner, later) == ()
    final = replace(actual, reported_tick=16, feedback=delayed,
                    extraction_confirmations=(*actual.extraction_confirmations[:-1], delayed))
    result, = consume(owner, (SuckleIntervalEvidenceV1(16, None, (final,), (), ()),))
    assert result.status == "local_sequence_observed" and result.evaluated_tick == 17
    assert result.end_tick == 7 and result.claim.targets[0].expires_at_tick == 8
    assert max(result.command_ticks) == 6
    assert dict(result.relations)["finite_reciprocation"] == "matched"
    assert dict(result.relations)["detail_anchor"] == "unknown"  # final delayed body lacks paired scene
    assert result.milk_evidence()["exact_observed_total"] == pytest.approx(.2)


def test_expired_report_cannot_create_missing_earlier_legs(material):
    first, intervals = material
    owner, _ = reader(first)
    first_eight = tuple(replace(i, reports=tuple(replace(r, extraction_confirmations=()) for r in i.reports)) for i in intervals[:8])
    consume(owner, first_eight)
    expired = replace(intervals[7].reports[0], disposition=LocalTargetDispositionV1.EXPIRED,
                      reported_tick=8, reason="expired", extraction_confirmations=())
    consume(owner, (SuckleIntervalEvidenceV1(8, None, (expired,), (), ()),))
    partial = replace(intervals[2].reports[0], reported_tick=9)
    before = snapshot(owner)
    with pytest.raises(ValueError, match="terminated"):
        consume(owner, (SuckleIntervalEvidenceV1(9, None, (partial,), (), ()),))
    assert snapshot(owner) == before


def test_new_milk_after_completed_contribution_is_not_added(material):
    first, intervals = material
    def change(sample):
        if sample.event_tick == 8:
            return replace(sample, oral_extraction=replace(sample.oral_extraction, milk_transferred_units=.9))
        return sample
    owner, _ = reader(first)
    result, = consume(owner, map_samples(intervals[:12], change))
    assert result.end_tick == 7 and result.milk_evidence()["known_interval_sum"] == pytest.approx(.2)
    assert 8 not in result.milk_evidence()["known_event_ticks"]


def test_known_contact_loss_at_nonendpoint_mismatches_without_rewriting_the_original(material):
    first, intervals = material
    before = first.calculation.navigation.application.as_dict()
    def change(sample):
        if sample.event_tick == 2:
            return replace(sample, oral_seal=replace(sample.oral_seal, sealed=False))
        return sample
    owner, claim = reader(first)
    result, = consume(owner, map_samples(intervals[:12], change))
    assert dict(result.relations)["sealed_contact"] == "mismatch"
    assert dict(result.relations)["finite_reciprocation"] == "matched"
    assert claim.application.as_dict() == before
    assert claim.application.projection.as_dict()["milk_prediction"] == "not_supplied_supply_unverified"


def test_claim_and_result_reading_has_no_current_source_or_physics_dependency(material):
    import ast
    from pathlib import Path
    import nca8_suckle_extraction_outcomes as outcomes
    tree = ast.parse(Path(outcomes.__file__).read_text())
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert "cca8_support_world" not in imports and "nca8_executive" not in imports
    owner, _ = reader(material[0])
    result, = consume(owner, material[1][:12])
    assert result.claim.application.projection.basis.source_map_ref is not None
    assert not hasattr(owner, "world") and not hasattr(owner, "current_source")


def test_actual_ingress_overflow_stops_before_an_extra_physical_step():
    trial = make_trial(outcomes_enabled=False, outcome_attention_enabled=False, learning_hook_enabled=False)
    trial.focal_step()
    for _ in range(16): trial.advance_lower()
    tick, physical = trial.tick, trial.observer_oral_extraction_body
    assert len(trial._suckle_intervals) == 16
    with pytest.raises(OverflowError): trial.advance_lower()
    assert trial.tick == tick and trial.observer_oral_extraction_body == physical
    assert trial.core.extraction_outcomes.history()[0].status == "execution_unknown_after_fault"
