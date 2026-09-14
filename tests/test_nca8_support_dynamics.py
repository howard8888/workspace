#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-1E-C owner-local differences and continuity, without action or learning authority."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json

import pytest

from cca8_env import EnvObservation
from nca8_adapters import adapt_env_observation_v1
from nca8_maps import SupportObservationV1, create_posture_support_map_library_v1
from nca8_runtime import Nca8SessionConfigV1
from nca8_sensory import Nca8BodySensoryModuleV1
from nca8_support_dynamics import SupportDynamicsProfileV1, SupportDynamicsTrackerV1, SupportDynamicsV1

_ABSENT = object()


def _packet(cycle: int, **changes):
    """Create a synthetic input at the unchanged admitted schema, not world state."""
    packet = SupportObservationV1(cycle, cycle, "body_ground_v1", 10.0, 0.4, 0.6, True).as_dict()
    packet.update(changes)
    return packet


def _owner():
    return Nca8BodySensoryModuleV1(
        create_posture_support_map_library_v1(), support_observation_enabled=True, support_dynamics_enabled=True,
    )


def _apply(owner, cycle, packet=_ABSENT, *, posture=("posture:fallen",)):
    """Use actual admission, staging and scheduler-authorized application, never direct history injection."""
    raw = {} if packet is _ABSENT else {"posture_support_v1": packet}
    admitted = adapt_env_observation_v1(EnvObservation(raw_sensors=raw, predicates=list(posture)))
    result = owner.poll_observation(admitted, cycle_id=cycle, observation_number=cycle)
    before = owner.support_dynamics
    assert owner.support_dynamics is before
    owner.apply_result(result.mark_applied(cycle), cycle_id=cycle)
    return owner.support_dynamics


@pytest.mark.parametrize("name, upper", (("angle_deadband", 90.0), ("loading_deadband", 1.0), ("destabilization_deadband", 1.0)))
@pytest.mark.parametrize("bad", (True, "0.02", -0.01, float("nan"), float("inf")))
def test_profile_rejects_nonfinite_wrong_type_and_negative_deadbands(name, upper, bad):
    with pytest.raises((TypeError, ValueError)):
        SupportDynamicsProfileV1(**{name: bad})
    with pytest.raises(ValueError):
        SupportDynamicsProfileV1(**{name: upper + 0.1})


@pytest.mark.parametrize("name", ("max_pair_interval", "continuity_cycles"))
@pytest.mark.parametrize("bad", (True, "2", 1.5, -1, 9))
def test_profile_bounds_prevent_unlimited_or_fractional_history(name, bad):
    with pytest.raises(ValueError):
        SupportDynamicsProfileV1(**{name: bad})


def test_zero_continuity_and_named_profile_parameters_are_explicit():
    profile = SupportDynamicsProfileV1(continuity_cycles=0)
    assert profile.profile_id == "support_trend_v1"
    assert profile.as_dict()["max_pair_interval"] == 2
    assert profile.angle_deadband == 1.0
    assert profile.loading_deadband == profile.destabilization_deadband == 0.02
    with pytest.raises(ValueError):
        SupportDynamicsProfileV1(max_pair_interval=0)
    with pytest.raises(FrozenInstanceError):
        profile.continuity_cycles = 20
    with pytest.raises(TypeError):
        SupportDynamicsTrackerV1({})


@pytest.mark.parametrize("bad", (1, "true", None))
def test_dynamics_switch_is_boolean_and_requires_existing_consumer(bad):
    with pytest.raises(TypeError):
        Nca8SessionConfigV1(support_dynamics_enabled=bad)
    with pytest.raises(TypeError):
        Nca8BodySensoryModuleV1(create_posture_support_map_library_v1(), support_dynamics_enabled=bad)
    with pytest.raises(ValueError):
        Nca8SessionConfigV1(support_dynamics_enabled=True)
    with pytest.raises(ValueError):
        Nca8BodySensoryModuleV1(create_posture_support_map_library_v1(), support_dynamics_enabled=True)


def test_one_current_sample_is_not_a_trend_and_polling_does_not_apply_it():
    owner = _owner()
    observation = adapt_env_observation_v1(EnvObservation(raw_sensors={"posture_support_v1": _packet(1)}))
    result = owner.poll_observation(observation, cycle_id=1, observation_number=1)
    assert owner.support_dynamics is None
    owner.apply_result(result.mark_applied(1), cycle_id=1)
    facet = owner.support_dynamics
    assert facet.continuity == "current" and facet.evidence_age == 0
    assert facet.previous is None and facet.pair_interval is None
    assert facet.trends == ("unknown", "unknown", "unknown")
    assert facet.angle_rate is facet.loading_rate is facet.destabilization_rate is None
    assert not facet.behavioral_authority


@pytest.mark.parametrize("sign", (-1, 1))
def test_opposite_distinct_samples_produce_opposite_rates_with_same_coarse_pose(sign):
    owner = _owner()
    _apply(owner, 1, _packet(1, body_ground_angle_degrees=30.0, useful_loading=0.5, destabilization=0.5))
    facet = _apply(owner, 2, _packet(2, body_ground_angle_degrees=30.0 + sign * 10, useful_loading=0.5 + sign * 0.2,
                                   destabilization=0.5 - sign * 0.1))
    assert owner.current_state.posture.value == "fallen"
    assert facet.angle_rate == pytest.approx(sign * 10.0)
    assert facet.loading_rate == pytest.approx(sign * 0.2)
    assert facet.destabilization_rate == pytest.approx(-sign * 0.1)
    assert facet.trends == (("increasing", "increasing", "decreasing") if sign > 0 else ("decreasing", "decreasing", "increasing"))
    assert facet.previous.sample_id == 1 and facet.reference.sample_id == 2
    assert facet.lateral_contact_change == "unchanged"


@pytest.mark.parametrize("difference, expected", ((-0.021, "decreasing"), (-0.02, "approximately_stable"),
    (-0.019, "approximately_stable"), (0.0, "approximately_stable"), (0.019, "approximately_stable"),
    (0.02, "approximately_stable"), (0.021, "increasing")))
def test_signed_deadband_includes_the_boundary_without_zeroing_measured_rate(difference, expected):
    owner = _owner()
    _apply(owner, 1, _packet(1, body_ground_angle_degrees=30.0, useful_loading=0.5, destabilization=0.5))
    facet = _apply(owner, 2, _packet(2, body_ground_angle_degrees=30.0 + difference * 50,
                                   useful_loading=0.5 + difference, destabilization=0.5 + difference))
    assert facet.trends == (expected, expected, expected)
    assert facet.loading_rate == pytest.approx(difference)


def test_pair_uses_event_interval_not_sample_id_delta_or_application_count():
    owner = _owner()
    _apply(owner, 1, _packet(1, sample_id=10, body_ground_angle_degrees=20.0, useful_loading=0.2))
    held = _apply(owner, 2)
    assert held.continuity == "bounded_continuity" and held.pair_interval is None
    facet = _apply(owner, 3, _packet(3, sample_id=100, body_ground_angle_degrees=30.0, useful_loading=0.6))
    assert facet.pair_interval == 2
    assert facet.angle_rate == 5.0 and facet.loading_rate == pytest.approx(0.2)
    assert facet.previous.sample_id == 10


def test_missing_then_duplicate_cannot_refresh_evidence_or_generate_repeated_progress():
    owner = _owner()
    packet = _packet(1)
    _apply(owner, 1, packet)
    held = _apply(owner, 2)
    assert held.evidence_age == 1 and held.reference.event_cycle == 1
    held_again = _apply(owner, 3, packet)
    assert held_again.configuration.disposition == "duplicate" and held_again.evidence_age == 2
    assert held_again.configuration.last_supported_event_cycle == 1
    assert held_again.trends == ("unknown",) * 3 and held_again.previous is None
    expired = _apply(owner, 4, packet)
    assert expired.continuity == "insufficient_evidence" and expired.reference is None
    assert expired.configuration.last_supported_event_cycle == 1
    fresh = _apply(owner, 5, _packet(5))
    assert fresh.previous is None and fresh.trends == ("unknown",) * 3
    assert held.reference.event_cycle == 1 and held.evidence_age == 1  # immutable old snapshot


def test_a_large_pair_gap_does_not_reuse_a_held_sample_for_a_rate():
    owner = _owner()
    _apply(owner, 1, _packet(1))
    _apply(owner, 2)
    _apply(owner, 3)
    facet = _apply(owner, 4, _packet(4, useful_loading=0.8))
    assert facet.continuity == "current" and facet.reference.sample_id == 4
    assert facet.previous is None and facet.reason == "pair_interval_exceeded_new_baseline"


@pytest.mark.parametrize("field", ("body_ground_angle_degrees", "useful_loading", "destabilization"))
@pytest.mark.parametrize("side", ("first", "second"))
def test_missing_quantity_is_not_backfilled_or_assigned_a_zero_rate(field, side):
    owner = _owner()
    _apply(owner, 1, _packet(1, **({field: None} if side == "first" else {})))
    next_packet = _packet(2, useful_loading=0.7)
    if side == "second":
        next_packet[field] = None
    facet = _apply(owner, 2, next_packet)
    rates = {"body_ground_angle_degrees": facet.angle_rate, "useful_loading": facet.loading_rate,
             "destabilization": facet.destabilization_rate}
    assert rates[field] is None
    if side == "second":
        assert getattr(facet.reference, field) is None


def test_contact_only_partial_measurement_is_not_a_complete_body_package():
    owner = _owner()
    _apply(owner, 1, _packet(1))
    facet = _apply(owner, 2, _packet(2, body_ground_angle_degrees=None, useful_loading=None, destabilization=None, lateral_contact=False))
    assert facet.continuity == "current" and facet.trends == ("unknown",) * 3
    assert facet.lateral_contact_change == "disappeared"
    held = _apply(owner, 3)
    assert held.reference.useful_loading is None and held.configuration.last_supported_event_cycle == 2
    assert held.previous is None


@pytest.mark.parametrize("before, after, expected", ((True, False, "disappeared"), (False, True, "appeared"),
                                                   (False, False, "unchanged"), (None, False, "unknown")))
def test_boolean_contact_is_a_change_not_a_fraction_or_derivative(before, after, expected):
    owner = _owner()
    _apply(owner, 1, _packet(1, lateral_contact=before))
    facet = _apply(owner, 2, _packet(2, lateral_contact=after))
    assert facet.lateral_contact_change == expected


@pytest.mark.parametrize("bad", (None, {}, {"frame_id": "other"}, {"useful_loading": float("nan")},
    {"destabilization": float("inf")}, {"sample_id": True}, {"owner": "foreign"}))
def test_invalid_or_changed_frame_breaks_history_and_next_current_sample_restarts(bad):
    owner = _owner()
    _apply(owner, 1, _packet(1))
    packet = None if bad is None else ({} if not bad else _packet(2, **bad))
    facet = _apply(owner, 2, packet)
    assert facet.configuration.disposition == "invalid"
    assert facet.continuity == "insufficient_evidence" and facet.reference is None
    assert facet.configuration.last_supported_event_cycle == 1
    resumed = _apply(owner, 3, _packet(3))
    assert resumed.previous is None and resumed.trends == ("unknown",) * 3
    assert _apply(owner, 4, _packet(4, useful_loading=0.8)).loading_rate == pytest.approx(0.4)


@pytest.mark.parametrize("changes, expected", (({"sample_id": 1, "useful_loading": 0.9}, "invalid"),
    ({"sample_id": 2, "event_cycle": 1}, "out_of_order"), ({"event_cycle": 9}, "future")))
def test_order_identity_and_future_failures_cannot_enter_a_fresh_pair(changes, expected):
    owner = _owner()
    _apply(owner, 1, _packet(1))
    changes = dict(changes)
    if changes.get("sample_id") == 1:
        changes["event_cycle"] = 1
    facet = _apply(owner, 2, _packet(2, **changes))
    assert facet.configuration.disposition == expected
    assert facet.reference is None and facet.previous is None
    assert _apply(owner, 3, _packet(3)).previous is None


def test_historical_sample_can_be_inspected_without_replacing_the_current_reference():
    owner = _owner()
    _apply(owner, 1, _packet(1))
    _apply(owner, 2)
    facet = _apply(owner, 3, _packet(2, useful_loading=0.95))
    assert facet.configuration.disposition == "delayed"
    assert facet.configuration.observation.sample_id == 2
    assert facet.reference.sample_id == 1 and facet.evidence_age == 2
    assert facet.loading_rate is None and facet.configuration.last_supported_event_cycle == 1
    assert _apply(owner, 4, _packet(4)).previous is None


def test_valid_empty_packet_and_complete_absence_are_different_but_neither_refreshes():
    owner = _owner()
    assert _apply(owner, 1).reference is None
    first = _apply(owner, 2, _packet(2))
    empty = _apply(owner, 3, _packet(3, body_ground_angle_degrees=None, useful_loading=None, destabilization=None, lateral_contact=None))
    assert empty.configuration.disposition == "empty"
    assert empty.reference == first.reference and empty.evidence_age == 1
    assert empty.trends == ("unknown",) * 3


@pytest.mark.parametrize("posture", (("posture:standing",), ("posture:standing", "posture:fallen")))
def test_contradictory_pose_invalidates_measured_history(posture):
    owner = _owner()
    _apply(owner, 1, _packet(1))
    facet = _apply(owner, 2, _packet(2), posture=posture)
    assert facet.configuration.disposition == "conflict"
    assert facet.continuity == "contradicted" and facet.reference is None
    assert _apply(owner, 3, _packet(3)).previous is None


def test_new_coarse_posture_without_new_measurement_does_not_hold_obsolete_geometry():
    owner = _owner()
    _apply(owner, 1, _packet(1))
    facet = _apply(owner, 2, posture=("posture:standing",))
    assert facet.continuity == "contradicted" and facet.reference is None
    assert facet.configuration.last_supported_event_cycle == 1


def test_revision_change_and_duplicate_application_cannot_reuse_a_prior_source():
    owner = _owner()
    _apply(owner, 1, _packet(1))
    first = owner.support_configuration
    _apply(owner, 2, _packet(2, useful_loading=0.8))
    second = owner.support_configuration
    tracker = SupportDynamicsTrackerV1()
    tracker.update(first)
    with pytest.raises(ValueError):
        tracker.update(first)
    assert tracker.current.configuration is first
    changed = replace(second, source_map_ref=replace(second.source_map_ref, revision=2))
    facet = tracker.update(changed)
    assert facet.reason == "source_changed_new_baseline" and facet.previous is None
    with pytest.raises(TypeError):
        tracker.update({})


def test_zero_continuity_profile_rejects_held_data_at_first_missing_event():
    owner = _owner()
    _apply(owner, 1, _packet(1))
    first = owner.support_configuration
    _apply(owner, 2)
    tracker = SupportDynamicsTrackerV1(SupportDynamicsProfileV1(continuity_cycles=0))
    tracker.update(first)
    assert tracker.update(owner.support_configuration).reference is None


def test_snapshots_are_immutable_detached_and_do_not_revive_expired_history():
    owner = _owner()
    first = _apply(owner, 1, _packet(1))
    encoded = json.dumps(first.as_dict(), sort_keys=True, allow_nan=False)
    exported = first.as_dict()
    exported["reference"]["useful_loading"] = 0.99
    exported["profile"]["continuity_cycles"] = 8
    with pytest.raises(FrozenInstanceError):
        first.reference.useful_loading = 0.99
    with pytest.raises(FrozenInstanceError):
        first.continuity = "current"
    for cycle in range(2, 30):
        _apply(owner, cycle)
    assert json.dumps(first.as_dict(), sort_keys=True, allow_nan=False) == encoded
    assert owner.support_dynamics.reference is None
    assert owner.pending_sample_count == 0
    assert owner.map_library.durable_map_count == owner.map_library.current_state_count == 1
    assert owner.map_library.posture_support_ref.revision == 1
    assert owner._support_dynamics._last_good is None  # bounded owner storage, not diagnostic history


@pytest.mark.parametrize("field, value", (("continuity", "made_up"), ("reference", None), ("profile", {}),
                                         ("configuration", {}), ("reason", ""), ("previous", "bad")))
def test_snapshot_rejects_incoherent_contracts(field, value):
    owner = _owner()
    facet = _apply(owner, 1, _packet(1))
    with pytest.raises((TypeError, ValueError)):
        replace(facet, **{field: value})
