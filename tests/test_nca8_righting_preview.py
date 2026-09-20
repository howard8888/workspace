"""H5 source, task, projection and BodyMap proofs with no actuator side effects."""

from __future__ import annotations

import json
import math
import random
from dataclasses import FrozenInstanceError, replace

import pytest

from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1
from nca8_body_targets import nominal_body_capabilities_v1
from nca8_executive import NavigationRuntimeV1
from nca8_maps import MotorSupportConfigurationV1, create_posture_support_map_library_v1
from nca8_prediction import Nca8PredictionRuntimeV1
from nca8_primitives import PrimitiveKindV1, StandUpIPV1
from nca8_righting import RightingActivityV1, RightingApplicationV1, RightingContextV1, RightingIPV1
from nca8_righting_demo import competing_preview_bid_v1
from nca8_runtime import Nca8RightingPreviewSessionV1
from nca8_sensorimotor_contracts import FocalMotorEvidenceV1, SensorimotorTargetKindV1
from nca8_sensory import Nca8BodySensoryModuleV1

STREAM = MotorStreamRefV1("test:h5", 1)


def reading(tick=0, **changes):
    packet = MotorFeedbackV1(STREAM, tick + 1, tick, tick if tick == 0 else tick + 1, 30.0, 0.4, True, 0.5, 0.3)
    return replace(packet, **changes)


def session(**kwargs):
    return Nca8RightingPreviewSessionV1(STREAM, **kwargs)


def application(result):
    value = result.navigation.application
    assert isinstance(value, RightingApplicationV1)
    return value


def paired(previous):
    owner = session()
    first = owner.preview(previous, cutoff_tick=0)
    last = owner.preview(reading(3), cutoff_tick=4)
    return owner, first, last


def test_source_is_one_existing_dynamic_map_with_actual_motor_facet():
    owner = session()
    signature = owner.maps.durable_record_signature()
    result = owner.preview(reading(), cutoff_tick=0)
    assert owner.maps.durable_map_count == owner.maps.current_state_count == 1
    assert result.source is owner.sensory.current_state
    assert owner.navigation.current_wnm.primary_source_state is result.source
    assert result.source.motor_support.evidence.feedback == reading()
    assert result.source.posture.value == "unknown"  # No canonical posture-profile selection.
    assert not result.source.evidence_current       # Old coarse slot is not motor evidence.
    assert owner.maps.durable_record_signature() == signature


def test_first_sample_supports_meaningful_conservative_attempt_without_zero_rates():
    owner = session()
    result = owner.preview(reading(), cutoff_tick=0)
    actual = application(result)
    assert result.source.motor_support.rates == (None, None, None)
    assert actual.strategy == "conservative_unknown_trend"
    assert actual.contribution.desired_tilt_degrees == 25.5
    assert actual.contribution.desired_extension == 0.5
    assert actual.task.applications == 1
    assert result.proposal.bindings
    assert owner.mapper.reservations(at_tick=0) == ()


def test_same_current_measurements_with_opposite_histories_change_real_consumed_targets():
    recovering, _, good = paired(reading(body_tilt_degrees=34, useful_loading=0.4, destabilization=0.4))
    worsening, _, bad = paired(reading(body_tilt_degrees=26, useful_loading=0.6, destabilization=0.2))
    assert good.source.motor_support.feedback == bad.source.motor_support.feedback
    good_app, bad_app = application(good), application(bad)
    assert good_app.strategy == "continue_useful_recovery"
    assert bad_app.strategy == "support_first_deteriorating"
    assert good_app.contribution.desired_tilt_degrees == 21.0
    assert bad_app.contribution.desired_tilt_degrees is None
    assert good_app.contribution.desired_extension == pytest.approx(0.6)
    assert bad_app.contribution.desired_extension == 0.5
    assert len(good.proposal.bindings) == 2 and len(bad.proposal.bindings) == 1
    assert good_app.projection.predicted_loading != bad_app.projection.predicted_loading
    assert good_app.projection.predicted_destabilization != bad_app.projection.predicted_destabilization
    assert recovering.maps.durable_record_signature() == worsening.maps.durable_record_signature()


@pytest.mark.parametrize("load,expected_rotation", [(0.0, False), (0.1, False), (0.29, False), (0.3, True), (0.7, True)])
def test_current_loading_controls_rotation_precondition(load, expected_rotation):
    result = session().preview(reading(useful_loading=load), cutoff_tick=0)
    assert (application(result).contribution.desired_tilt_degrees is not None) is expected_rotation


@pytest.mark.parametrize("tilt", [-80.0, -30.0, 30.0, 80.0])
def test_orientation_contribution_is_signed_and_limited_not_fixed_upright(tilt):
    result = session().preview(reading(body_tilt_degrees=tilt), cutoff_tick=0)
    request = application(result).contribution
    assert request.desired_tilt_degrees != 0.0
    assert abs(request.desired_tilt_degrees) < abs(tilt)
    assert abs(request.desired_tilt_degrees - tilt) <= 6.0
    orientation = next(item.target for item in result.proposal.bindings if item.target.kind is SensorimotorTargetKindV1.ORIENTATION_ADJUST)
    assert math.copysign(1, orientation.offset) == -math.copysign(1, tilt)


@pytest.mark.parametrize("prior_tilt,prior_load,prior_instability", [(25, 0.5, 0.3), (30, 0.7, 0.3), (30, 0.5, 0.1)])
def test_each_supported_deterioration_channel_can_withhold_rotation(prior_tilt, prior_load, prior_instability):
    _, _, result = paired(reading(body_tilt_degrees=prior_tilt, useful_loading=prior_load, destabilization=prior_instability))
    assert application(result).contribution.desired_tilt_degrees is None


def test_zero_rates_only_follow_distinct_equivalent_physical_acquisitions():
    _, _, result = paired(reading())
    assert result.source.motor_support.rates == (0.0, 0.0, 0.0)
    assert application(result).strategy == "bounded_support_adjustment"


def test_rates_use_real_elapsed_time_not_focal_call_count():
    owner = session()
    owner.preview(reading(useful_loading=0.4), cutoff_tick=0)
    result = owner.preview(reading(7, useful_loading=0.54), cutoff_tick=8)
    assert result.source.motor_support.rates[1] == pytest.approx(0.4)


@pytest.mark.parametrize("axis", ["body_tilt_degrees", "support_extension"])
def test_missing_one_coordinate_preserves_other_justified_target(axis):
    result = session().preview(reading(**{axis: None}), cutoff_tick=0)
    request = application(result).contribution
    assert (request.desired_tilt_degrees is None) is (axis == "body_tilt_degrees")
    assert (request.desired_extension is None) is (axis == "support_extension")
    assert len(result.proposal.bindings) == 1


@pytest.mark.parametrize("channel", ["support_contact", "useful_loading", "destabilization"])
def test_missing_essential_support_is_unknown_not_desired_truth(channel):
    owner = session()
    result = owner.preview(reading(**{channel: None}), cutoff_tick=0)
    assert result.navigation.application is None and result.proposal is None
    assert result.source_status == "support_relation_unknown"
    assert owner.prediction.current_pnm is None


def test_no_contact_still_permits_extension_but_not_expected_contact_or_rotation():
    result = session().preview(reading(support_contact=False, useful_loading=0.0), cutoff_tick=0)
    actual = application(result)
    assert actual.contribution.desired_tilt_degrees is None
    assert actual.projection.expected_contact is None
    assert result.source.motor_support.feedback.support_contact is False
    assert result.source.motor_support.feedback.useful_loading == 0.0


@pytest.mark.parametrize("activity,tilt,loading,instability", [
    (RightingActivityV1.REST, 80, 0.03, 0.05),
    (RightingActivityV1.CROUCH, 30, 0.5, 0.1),
    (RightingActivityV1.MOBILITY, 10, 0.8, 0.1),
])
def test_current_activity_adequacy_stops_new_request_without_success_or_dwell(activity, tilt, loading, instability):
    owner = session(context=RightingContextV1("fixture:context", activity))
    result = owner.preview(reading(body_tilt_degrees=tilt, useful_loading=loading, destabilization=instability), cutoff_tick=0)
    assert result.source_status == "currently_adequate_not_dwell"
    assert result.navigation.application is None and result.task is None
    assert owner.prediction.pending_snapshot() == owner.prediction.outcome_history() == ()


def test_same_body_has_different_activity_adequacy_without_rewriting_measurement():
    current = reading(destabilization=0.1)
    mobility = session().preview(current, cutoff_tick=0)
    crouch = session(context=RightingContextV1("fixture:crouch", RightingActivityV1.CROUCH)).preview(current, cutoff_tick=0)
    assert mobility.source.as_dict() == crouch.source.as_dict()
    assert mobility.navigation.application is not None and crouch.navigation.application is None


@pytest.mark.parametrize("contact,instability", [(False, 0.05), (True, 0.7)])
def test_rest_context_does_not_announce_safety_without_contact_and_stability(contact, instability):
    owner = session(context=RightingContextV1("fixture:rest", RightingActivityV1.REST))
    result = owner.preview(reading(body_tilt_degrees=80, useful_loading=0.1, support_contact=contact, destabilization=instability), cutoff_tick=0)
    assert result.source_status == "support_needed"
    assert result.source.motor_support.feedback.destabilization == instability
    assert application(result).contribution.desired_tilt_degrees is None
    assert application(result).contribution.desired_extension == 0.5


def test_context_change_releases_task_and_preview_without_relabeling_old_claim():
    owner = session()
    first = owner.preview(reading(), cutoff_tick=0)
    saved = first.as_dict()
    result = owner.preview(reading(3, body_tilt_degrees=80, useful_loading=0.03, destabilization=0.05), cutoff_tick=4,
                           context=RightingContextV1("new:rest", RightingActivityV1.REST))
    assert result.task is None and owner.prediction.current_pnm is None
    assert first.as_dict() == saved
    assert owner.prediction.preview_history()[0] == application(first).projection
    assert owner.prediction.outcome_history() == ()


def test_same_context_id_cannot_change_criterion_in_place():
    owner = session()
    first = owner.preview(reading(), cutoff_tick=0)
    with pytest.raises(ValueError, match="context ID"):
        owner.preview(reading(3), cutoff_tick=4, context=RightingContextV1(owner.context.context_id, RightingActivityV1.REST))
    assert owner.last_result is first and owner.maps.current_state() is first.source


def test_task_persists_across_changed_samples_without_constant_proposals():
    owner, first, later = paired(reading(useful_loading=0.2))
    assert application(first).task.task_id == application(later).task.task_id
    assert application(later).task.started_cycle == 1 and application(later).task.applications == 2
    assert application(first).contribution != application(later).contribution
    assert first.source.source_map_ref == later.source.source_map_ref
    assert owner.maps.current_state_count == owner.maps.durable_map_count == 1


def test_missing_input_breaks_history_but_does_not_restart_the_task():
    owner = session()
    first = owner.preview(reading(), cutoff_tick=0)
    missing = owner.preview(None, cutoff_tick=4)
    assert missing.task.task_id == first.task.task_id
    assert missing.task.applications == 1 and owner.prediction.current_pnm is None
    returned = owner.preview(reading(7), cutoff_tick=8)
    assert returned.task.task_id == first.task.task_id
    assert returned.source.motor_support.rates == (None, None, None)


def test_duplicate_current_acquisition_retains_time_and_has_no_new_rate():
    owner = session()
    first = owner.preview(reading(), cutoff_tick=0)
    duplicate = owner.preview(reading(), cutoff_tick=1)
    assert duplicate.source.motor_support.evidence.feedback is not None
    assert duplicate.source.motor_support.feedback.event_tick == 0
    assert duplicate.source.motor_support.rates == (None, None, None)
    assert first.source.motor_support.feedback == duplicate.source.motor_support.feedback


@pytest.mark.parametrize("cutoff", [3, 4, 9])
def test_stale_source_never_gains_freshness_from_reading_or_task_influence(cutoff):
    owner = session()
    owner.preview(reading(), cutoff_tick=0)
    result = owner.preview(reading(), cutoff_tick=cutoff)
    assert not result.source.motor_support.current
    assert result.persistence_rank == 0 and result.navigation.application is None
    assert result.source.motor_support.feedback.event_tick == 0


def test_excessive_pair_gap_starts_a_new_rate_baseline():
    owner = session()
    owner.preview(reading(), cutoff_tick=0)
    result = owner.preview(reading(11), cutoff_tick=12)
    assert result.source.motor_support.current and result.source.motor_support.previous is None
    assert result.source.motor_support.rates == (None, None, None)


def test_source_influence_changes_actual_attention_with_all_sensing_fixed():
    results = []
    for enabled in (True, False):
        owner = session(influence_enabled=enabled)
        owner.preview(reading(), cutoff_tick=0)
        result = owner.preview(reading(), cutoff_tick=1, competing_bids=(competing_preview_bid_v1(2),))
        results.append((owner, result))
    (on_owner, on), (off_owner, off) = results
    assert on.source.as_dict() == off.source.as_dict()
    assert on.persistence_rank == 20 and off.persistence_rank == 0
    assert on.attention.selected_source_state.source_map_ref.map_id == "posture_support"
    assert off.attention.selected_source_state.source_map_ref.map_id == "fixture_competing_source"
    assert on.navigation.selected_primitive_id == "ip:righting"
    assert off.navigation.selected_primitive_id is None
    assert off.task.task_id == on.task.task_id and off.task.applications == 1
    assert off_owner.prediction.current_pnm is None
    assert on_owner.mapper.reservations(at_tick=1) == off_owner.mapper.reservations(at_tick=1) == ()


def test_source_influence_cannot_defeat_higher_protected_priority():
    owner = session()
    owner.preview(reading(), cutoff_tick=0)
    competitor = replace(competing_preview_bid_v1(2), protected_safety_rank=1, safety_escalation=True)
    result = owner.preview(reading(), cutoff_tick=1, competing_bids=(competitor,))
    assert result.persistence_rank == 20
    assert result.attention.selected_source_state.source_map_ref.map_id == "fixture_competing_source"
    assert result.navigation.application is None


def test_righting_off_preserves_source_and_attention_but_no_task_contribution():
    owner = session(righting_enabled=False)
    result = owner.preview(reading(), cutoff_tick=0)
    assert result.attention.selected_source_state is result.source
    assert result.navigation.wnm is not None
    assert result.navigation.application is None and result.task is None
    assert result.navigation.applicability_records[0].vetoes == ("righting_disabled",)


def test_default_navigation_still_withholds_enhanced_source_from_a0_arguments():
    owner = session()
    result = owner.preview(reading(), cutoff_tick=0)
    record = []

    class Probe(StandUpIPV1):
        def evaluate_applicability(self, wnm, *, cycle_id):
            record.append(wnm.primary_source_state.motor_support)
            return super().evaluate_applicability(wnm, cycle_id=cycle_id)

    NavigationRuntimeV1().commit(result.navigation.wnm, (Probe(),), cycle_id=1)
    assert record == [None]
    assert result.navigation.wnm.primary_source_state.motor_support is not None


def test_retained_standup_is_not_changed_or_used_as_hidden_fallback():
    old = StandUpIPV1()
    result = session(additional_primitives=(old,)).preview(reading(), cutoff_tick=0)
    assert result.navigation.selected_primitive_id == "ip:righting"
    assert old.application_count == 0
    assert {item.primitive_id for item in result.navigation.applicability_records} == {"ip:righting", "ip:stand_up"}


def test_supplied_lp_kind_can_win_the_common_selector_without_starting_righting():
    class SuppliedLP(StandUpIPV1):
        primitive_id = "fixture:learned_candidate"
        primitive_kind = PrimitiveKindV1.LEARNED

        def evaluate_applicability(self, wnm, *, cycle_id):
            base = super().evaluate_applicability(wnm, cycle_id=cycle_id)
            return replace(base, eligible=True, safety_rank=0, fit_rank=200, vetoes=())

        def apply(self, wnm, applicability, *, cycle_id):
            # An explicitly supplied fixture, not an acquired LP or a motor route.
            from nca8_primitives import PrimitiveApplicationV1, TaskActionV1, TaskActionKindV1
            return PrimitiveApplicationV1("fixture:application", self.primitive_id, self.primitive_kind, cycle_id,
                                          wnm.working_id, (), ("fixture:expected",), "fixture_only",
                                          TaskActionV1("fixture:action", cycle_id, TaskActionKindV1.NO_ACTION, "fixture:application", ()), None)

    owner = session(additional_primitives=(SuppliedLP(),))
    result = owner.preview(reading(), cutoff_tick=0)
    assert result.navigation.selected_primitive_id == "fixture:learned_candidate"
    assert owner.righting.task is None and owner.righting.history() == ()
    assert owner.prediction.current_pnm is None and result.proposal is None


def test_applicability_queries_do_not_create_task_preview_or_budget_use():
    owner = session(righting_enabled=False)
    result = owner.preview(reading(), cutoff_tick=0)
    primitive = RightingIPV1()
    primitive.prepare_opportunity(cycle_id=1, at_tick=0, context=RightingContextV1())
    for _ in range(5):
        assert primitive.evaluate_applicability(result.navigation.wnm, cycle_id=1).eligible
    assert primitive.task is None and primitive.history() == ()


def test_selected_application_can_only_apply_once_to_current_opportunity():
    owner = session()
    result = owner.preview(reading(), cutoff_tick=0)
    record = result.navigation.applicability_records[0]
    with pytest.raises(ValueError):
        owner.righting.apply(result.navigation.wnm, record, cycle_id=1)
    assert owner.righting.task.applications == 1


def test_bodymap_consumes_contribution_and_can_narrow_without_mutating_pnm():
    capabilities = tuple(replace(item, maximum_step=4.0) if item.kind is SensorimotorTargetKindV1.ORIENTATION_ADJUST else item
                         for item in nominal_body_capabilities_v1())
    result = session(capabilities=capabilities).preview(reading(), cutoff_tick=0)
    app = application(result)
    assert app.contribution.desired_tilt_degrees == app.projection.predicted_tilt == 25.5
    target = next(item.target for item in result.proposal.bindings if item.target.kind is SensorimotorTargetKindV1.ORIENTATION_ADJUST)
    assert target.endpoint == 26.0
    assert app.projection.as_dict()["executed_obligation"] is False


def test_unavailable_capability_withholds_only_that_axis():
    capabilities = tuple(item for item in nominal_body_capabilities_v1() if item.kind is SensorimotorTargetKindV1.SUPPORT_EXTENSION)
    result = session(capabilities=capabilities).preview(reading(), cutoff_tick=0)
    assert len(result.proposal.bindings) == 1
    assert result.proposal.withheld == ((SensorimotorTargetKindV1.ORIENTATION_ADJUST, "capability_unavailable"),)


def test_old_source_target_and_pnm_anchors_never_drift_with_new_measurements():
    owner = session()
    first = owner.preview(reading(), cutoff_tick=0)
    original = first.as_dict()
    later = owner.preview(reading(3, body_tilt_degrees=24.0, useful_loading=0.6), cutoff_tick=4)
    assert first.as_dict() == original
    assert application(first).projection.basis.feedback.body_tilt_degrees == 30.0
    assert later.source.motor_support.feedback.body_tilt_degrees == 24.0
    assert first.proposal.bindings[0].target.basis.body_tilt_degrees == 30.0


def test_previews_are_not_armed_as_executed_claims_or_scored_on_new_sensing():
    owner = session()
    first = owner.preview(reading(), cutoff_tick=0)
    second = owner.preview(reading(3, body_tilt_degrees=5, useful_loading=0.9, destabilization=0.01), cutoff_tick=4)
    assert owner.prediction.pending_snapshot() == owner.prediction.outcome_history() == ()
    assert owner.prediction.current_pnm is None
    assert owner.prediction.preview_history() == (application(first).projection,)
    assert second.source_status == "currently_adequate_not_dwell"
    assert not second.task.as_dict()["task_success_established"]


def test_preview_and_executed_pending_prediction_modes_cannot_overlap():
    owner = session()
    app = application(owner.preview(reading(), cutoff_tick=0))
    with pytest.raises(ValueError, match="release"):
        owner.prediction.create_current(app)
    pending = Nca8PredictionRuntimeV1()
    pending.create_current(app)
    with pytest.raises(ValueError, match="mix"):
        pending.adopt_support_preview(app.projection)


def test_released_old_preview_cannot_be_reinstated_as_new_current_future():
    owner = session()
    app = application(owner.preview(reading(), cutoff_tick=0))
    owner.prediction.adopt_support_preview(None)
    with pytest.raises(ValueError, match="follow"):
        owner.prediction.adopt_support_preview(app.projection)


def test_focal_budget_includes_nonselected_opportunities_and_is_sticky():
    owner = session()
    first = owner.preview(reading(), cutoff_tick=0)
    for tick in range(1, 21):
        result = owner.preview(reading(tick, available_tick=tick), cutoff_tick=tick,
                               competing_bids=(competing_preview_bid_v1(tick + 1, persistence_rank=30),))
    assert result.task.task_id == first.task.task_id and result.task.applications == 1
    assert result.task.status == "budget_exhausted"
    next_result = owner.preview(reading(21, available_tick=21), cutoff_tick=21)
    assert next_result.navigation.application is None and next_result.task.task_id == first.task.task_id


def test_physical_task_budget_is_independent_of_number_of_focal_calls():
    owner = session()
    first = owner.preview(reading(), cutoff_tick=0)
    ended = owner.preview(reading(79), cutoff_tick=80)
    assert ended.task.task_id == first.task.task_id and ended.task.applications == 1
    assert ended.task.status == "budget_exhausted" and ended.navigation.application is None


def test_near_task_expiry_cannot_issue_target_or_projection_beyond_original_budget():
    owner = session()
    owner.preview(reading(), cutoff_tick=0)
    result = owner.preview(reading(78), cutoff_tick=79)
    app = application(result)
    assert app.contribution.lease_ticks == app.projection.horizon_ticks == 1
    assert all(item.target.lease_ticks == 1 for item in result.proposal.bindings)


def test_application_and_preview_histories_are_bounded_without_resetting_task_budget():
    owner = session()
    for tick in range(20):
        result = owner.preview(reading(tick, available_tick=tick), cutoff_tick=tick)
    assert result.task.applications == 20 and len(owner.righting.history()) == 8
    assert len(owner.prediction.preview_history()) == 8
    assert owner.prediction.pending_snapshot() == ()
    assert owner.maps.durable_map_count == owner.maps.current_state_count == 1
    assert owner.mapper.reservations(at_tick=19) == ()


def test_insufficient_coordinate_opportunity_reports_no_contribution_not_fake_hold():
    owner = session()
    result = owner.preview(reading(body_tilt_degrees=0, support_extension=1, useful_loading=0.1), cutoff_tick=0)
    assert result.navigation.application is None
    assert result.navigation.applicability_records[0].vetoes == ("no_supported_contribution",)


def test_new_generation_needs_new_session_and_never_reuses_old_task():
    owner = session()
    old = owner.preview(reading(), cutoff_tick=0)
    other_stream = MotorStreamRefV1(STREAM.stream_id, 2)
    with pytest.raises(ValueError):
        owner.preview(replace(reading(3), stream=other_stream), cutoff_tick=4)
    new_owner = Nca8RightingPreviewSessionV1(other_stream)
    new = new_owner.preview(replace(reading(), stream=other_stream), cutoff_tick=0)
    assert new.task.task_id != old.task.task_id
    assert new.task.applications == 1 and owner.last_result is old


@pytest.mark.parametrize("bad", [True, -1, 0.5, "4", float("inf")])
def test_invalid_cutoffs_fail_before_source_or_task_changes(bad):
    owner = session()
    first = owner.preview(reading(), cutoff_tick=0)
    with pytest.raises((ValueError, TypeError)):
        owner.preview(reading(), cutoff_tick=bad)
    assert owner.last_result is first and owner.maps.current_state() is first.source


@pytest.mark.parametrize("mode", ["wrong_stream", "future", "changed_duplicate", "reversed_sample", "reversed_event"])
def test_invalid_motor_feedback_is_rejected_before_current_source_changes(mode):
    owner = session()
    first = owner.preview(reading(3), cutoff_tick=4)
    packet = reading(4)
    if mode == "wrong_stream":
        packet = replace(packet, stream=MotorStreamRefV1("other", 1))
    elif mode == "future":
        packet = replace(packet, available_tick=7)
    elif mode == "changed_duplicate":
        packet = replace(reading(3), useful_loading=0.9)
    elif mode == "reversed_sample":
        packet = replace(packet, sample_id=1)
    else:
        packet = replace(packet, event_tick=1)
    with pytest.raises(ValueError):
        owner.preview(packet, cutoff_tick=5)
    assert owner.last_result is first and owner.maps.current_state() is first.source


@pytest.mark.parametrize("ticks", [float("nan"), float("inf"), 0.0, -0.01, True, "0.05"])
def test_source_refuses_invalid_timebase(ticks):
    maps = create_posture_support_map_library_v1()
    with pytest.raises((TypeError, ValueError)):
        MotorSupportConfigurationV1(maps.posture_support_ref, STREAM, FocalMotorEvidenceV1(reading(), 1, 0), None, 1, 0, ticks)


def test_source_timebase_cannot_change_mid_generation():
    source = Nca8BodySensoryModuleV1(create_posture_support_map_library_v1())
    first = source.apply_motor_evidence(FocalMotorEvidenceV1(reading(), 1, 0), stream=STREAM, cycle_id=1, cutoff_tick=0)
    with pytest.raises(ValueError, match="timebase"):
        source.apply_motor_evidence(FocalMotorEvidenceV1(reading(3), 2, 4), stream=STREAM, cycle_id=2, cutoff_tick=4, tick_seconds=0.04)
    assert source.current_state is first


@pytest.mark.parametrize("bad", [True, 0, 9, -1, 1.5])
def test_sparse_preview_horizon_validation(bad):
    app = application(session().preview(reading(), cutoff_tick=0))
    with pytest.raises(ValueError):
        replace(app.projection, horizon_ticks=bad)


@pytest.mark.parametrize("field,value", [("predicted_tilt", 91), ("predicted_loading", -0.1), ("predicted_extension", 1.1),
                                          ("predicted_destabilization", float("nan")), ("predicted_tilt", True)])
def test_sparse_preview_rejects_invalid_predicted_values(field, value):
    app = application(session().preview(reading(), cutoff_tick=0))
    with pytest.raises((TypeError, ValueError)):
        replace(app.projection, **{field: value})


def test_sparse_preview_cannot_assert_contact_on_an_absent_surface():
    app = application(session().preview(reading(support_contact=False, useful_loading=0.0), cutoff_tick=0))
    with pytest.raises(ValueError, match="surface"):
        replace(app.projection, expected_contact=True)


def test_exports_and_old_records_are_detached_finite_and_immutable():
    owner = session()
    result = owner.preview(reading(), cutoff_tick=0)
    before = result.as_dict()
    payload = result.as_dict()
    payload["navigation"]["application"]["projection"]["predicted_loading"] = -100
    assert result.as_dict() == before
    assert json.loads(json.dumps(before, allow_nan=False))["motor_dispatches"] == 0
    with pytest.raises(FrozenInstanceError):
        application(result).projection.predicted_loading = 1.0


def test_preview_uses_no_rng_and_does_not_install_or_authorize_motor_work(monkeypatch):
    from nca8_body import Nca8BodyRuntimeV1
    from nca8_sensorimotor import SensorimotorExecutorV1
    from cca8_support_world import MotorWorldV1

    def prohibited(*_args, **_kwargs):
        raise AssertionError("H5 crossed into actuation")

    monkeypatch.setattr(Nca8BodyRuntimeV1, "authorize_application", prohibited)
    monkeypatch.setattr(SensorimotorExecutorV1, "__init__", prohibited)
    monkeypatch.setattr(MotorWorldV1, "__init__", prohibited)
    old_rng = random.getstate()
    owner = session()
    result = owner.preview(reading(), cutoff_tick=0)
    assert result.navigation.selected_primitive_id == "ip:righting"
    assert random.getstate() == old_rng
    assert owner.body.current_envelope is None
    assert owner.mapper.reservations(at_tick=0) == ()


def test_one_attention_and_one_navigation_call_create_one_wnm_and_one_application(monkeypatch):
    owner = session()
    calls = []
    select, commit, map_target = owner.attention.select, owner.navigation.commit, owner.mapper.propose

    def select_once(*args, **kwargs):
        calls.append("attention")
        return select(*args, **kwargs)

    def commit_once(*args, **kwargs):
        calls.append("navigation")
        return commit(*args, **kwargs)

    def map_once(*args, **kwargs):
        calls.append("body_mapping")
        return map_target(*args, **kwargs)

    monkeypatch.setattr(owner.attention, "select", select_once)
    monkeypatch.setattr(owner.navigation, "commit", commit_once)
    monkeypatch.setattr(owner.mapper, "propose", map_once)
    result = owner.preview(reading(), cutoff_tick=0)
    assert calls == ["attention", "navigation", "body_mapping"]
    assert result.navigation.wnm is owner.navigation.current_wnm
    assert owner.prediction.current_pnm == application(result).projection.pnm


@pytest.mark.parametrize("expiry", [0, 9, True, "8"])
def test_source_continuation_request_cannot_extend_its_eight_tick_permission(expiry):
    owner = session()
    first = owner.preview(reading(), cutoff_tick=0)
    with pytest.raises((ValueError, TypeError)):
        owner.sensory.retain_motor_context(first.task.task_id, owner.context.context_id, cycle_id=1, expires_at_tick=expiry)
    assert owner.sensory.current_state is first.source


def test_source_request_cannot_claim_a_different_application_cycle_or_rewrite_facts():
    owner = session()
    first = owner.preview(reading(), cutoff_tick=0)
    with pytest.raises(ValueError):
        owner.sensory.retain_motor_context(first.task.task_id, owner.context.context_id, cycle_id=2, expires_at_tick=8)
    assert owner.sensory.current_state is first.source
    assert owner.sensory.motor_context_rank("wrong_task", owner.context.context_id) == 0
    assert owner.sensory.motor_context_rank(first.task.task_id, "wrong_context") == 0


@pytest.mark.parametrize("bad_change", [
    {"task_id": ""}, {"started_cycle": 0}, {"applications": 21}, {"started_tick": True},
    {"last_cycle": 0}, {"status": "successful"}, {"context": None}, {"stream": None}, {"source_map_ref": None},
])
def test_task_context_rejects_malformed_or_fabricated_success_states(bad_change):
    task = session().preview(reading(), cutoff_tick=0).task
    with pytest.raises((ValueError, TypeError)):
        replace(task, **bad_change)


def test_unknown_source_coordinate_cannot_be_installed_in_the_preview_as_known():
    app = application(session().preview(reading(body_tilt_degrees=None), cutoff_tick=0))
    with pytest.raises(ValueError, match="absent source"):
        replace(app.projection, predicted_tilt=0.0)


def test_valid_extreme_tick_does_not_overflow_a_future_task_target_lease():
    at_tick = 2**63 - 2
    owner = session()
    packet = reading(at_tick, available_tick=at_tick)
    result = owner.preview(packet, cutoff_tick=at_tick)
    assert result.source_status == "time_budget_unrepresentable"
    assert result.navigation.application is None


def test_new_valid_reading_after_bad_packet_can_still_update_the_unmutated_session():
    owner = session()
    first = owner.preview(reading(), cutoff_tick=0)
    with pytest.raises(ValueError):
        owner.preview(replace(reading(3), stream=MotorStreamRefV1("wrong", 1)), cutoff_tick=4)
    valid = owner.preview(reading(3), cutoff_tick=4)
    assert valid.cycle_id == 2 and valid.task.task_id == first.task.task_id


def test_inadequate_stability_can_request_support_without_forcing_further_orientation():
    result = session().preview(reading(body_tilt_degrees=10, useful_loading=0.8, destabilization=0.3), cutoff_tick=0)
    assert result.source_status == "support_needed"
    assert application(result).contribution.desired_tilt_degrees is None
    assert application(result).contribution.desired_extension == 0.5
