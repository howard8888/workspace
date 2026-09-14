#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-1E-C source-to-WNM refresh, authority isolation and pre-edit regressions."""

from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from cca8_env import EnvObservation
from nca8_adapters import adapt_env_observation_v1
from nca8_contracts import CyclePhase
from nca8_maps import SupportObservationV1, create_posture_support_map_library_v1
from nca8_primitives import StandUpIPV1
from nca8_runtime import Nca8CognitiveRuntimeV1, Nca8SessionConfigV1, Nca8SessionV1
from nca8_scheduler import Nca8DeterministicSchedulerV1
from nca8_sensory import Nca8BodySensoryModuleV1
from nca8_trace import Nca8TraceBufferV1, Nca8TraceEventV1, render_explanatory_trace_lines_v1, render_flow_trace_lines_v1
from scripts.run_nca8_support_evidence import main, run_support_case_v1

ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads((ROOT / 'tests/fixtures/nca8_support_dynamics_baseline.json').read_text(encoding='utf-8'))
NEW_CHANNELS = {'support_dynamics', 'wnm_support'}
RECOVERY = 'posture_support_recovery_v1'
DISTURBED = 'posture_support_disturbed_v1'


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _strip_working_facet(result):
    """Remove only the newly advertised working content; every prior behavioral field remains compared."""
    result = deepcopy(result)
    for wnm in (result.get('wnm'), result.get('navigation', {}).get('wnm')):
        if wnm is not None:
            wnm.pop('support_dynamics', None)
    return result


def _session(scenario=RECOVERY, **flags):
    return Nca8SessionV1(Nca8SessionConfigV1(
        scenario_name=scenario, support_observation_enabled=True, support_dynamics_enabled=True, **flags,
    ))


def _core(*, primitives=None):
    """Core-only controlled observations: no injected packet is claimed to be a world simulation."""
    owner = Nca8BodySensoryModuleV1(
        create_posture_support_map_library_v1(), support_observation_enabled=True, support_dynamics_enabled=True,
    )
    trace = Nca8TraceBufferV1()
    runtime = Nca8CognitiveRuntimeV1(
        trace=trace, scheduler=Nca8DeterministicSchedulerV1(), body_sensory=owner, primitives=primitives,
    )
    return runtime, owner, trace


def _core_step(core, cycle, packet=None, *, posture='fallen'):
    raw = {} if packet is None else {'posture_support_v1': packet}
    observation = adapt_env_observation_v1(EnvObservation(raw_sensors=raw, predicates=[f'posture:{posture}']))
    result = core.run_cycle(observation, observation_number=cycle)
    core.handoff.consume(result.handoff_receipt)  # synthetic input test only: not evidence of physical execution
    return result


def _packet(cycle, *, angle=20.0, loading=0.4, destabilization=0.6):
    return SupportObservationV1(cycle, cycle, 'body_ground_v1', angle, loading, destabilization, angle < 15).as_dict()


@pytest.mark.parametrize('name', tuple(BASELINE['cases']))
def test_new_path_disabled_preserves_exact_preedit_results_inputs_measurements_and_canonical_trace(name):
    case = BASELINE['cases'][name]
    session = Nca8SessionV1(Nca8SessionConfigV1(**case['config']))
    results, observations, measured = [], [], []
    for _ in range(6):
        results.append(session.run_cognitive_cycle().as_dict())
        observations.append(session.pending_observation.as_dict())
        measured.append(session.support_configuration.as_dict() if session.support_configuration else None)
        assert session.support_dynamics is None
    assert _digest(results) == case['cycle_results_sha256']
    assert _digest(observations) == case['input_stream_sha256']
    assert _digest(measured) == case['support_configurations_sha256']
    assert hashlib.sha256(session.trace_canonical_bytes()).hexdigest() == case['trace_sha256']
    assert len(session.trace_snapshot()) == case['trace_count']
    assert _digest(session.durable_posture_support_map.as_dict()) == case['durable_sha256']


@pytest.mark.parametrize('name', tuple(name for name, case in BASELINE['cases'].items() if case['config'].get('support_observation_enabled')))
def test_enabled_path_changes_only_readonly_working_content_and_two_named_trace_channels(name):
    case = BASELINE['cases'][name]
    session = Nca8SessionV1(Nca8SessionConfigV1(**case['config'], support_dynamics_enabled=True))
    results, observations, measured = [], [], []
    for _ in range(6):
        results.append(_strip_working_facet(session.run_cognitive_cycle().as_dict()))
        observations.append(session.pending_observation.as_dict())
        measured.append(session.support_configuration.as_dict())
    assert _digest(results) == case['cycle_results_sha256']
    assert _digest(observations) == case['input_stream_sha256']
    assert _digest(measured) == case['support_configurations_sha256']
    old_events = [event for event in session.trace_snapshot() if event.channel not in NEW_CHANNELS]
    # Remove only added reports, then renumber their former interleaving. No old field or message is normalized away.
    normalized = [replace(event, sequence=index).as_dict() for index, event in enumerate(old_events, 1)]
    assert _digest(normalized) == case['trace_sha256']
    assert _digest(session.durable_posture_support_map.as_dict()) == case['durable_sha256']


@pytest.mark.parametrize('scenario', (RECOVERY, DISTURBED))
def test_maintained_wnm_really_refreshes_same_source_content_before_future_world_input(scenario):
    session = _session(scenario)
    first = session.run_cognitive_cycle()
    frozen_first = first.wnm.as_dict()
    assert first.wnm.support_dynamics.reference.sample_id == 1
    assert first.wnm.support_dynamics.previous is None
    assert session.pending_observation.support_observation.sample_id == 2
    second = session.run_cognitive_cycle()
    facet = second.wnm.support_dynamics
    assert second.attention_selection.disposition.value == 'maintain'
    assert second.wnm.working_id == first.wnm.working_id == 'wnm:current'
    assert second.wnm.created_cycle == first.wnm.created_cycle == 1
    assert second.wnm.refreshed_cycle == 2 and second.wnm.focus_age == 2
    assert facet == session.support_dynamics and facet is not session.support_dynamics
    assert facet.configuration.source_map_ref == second.wnm.primary_source_state.source_map_ref
    assert facet.reference.sample_id == 2 and facet.previous.sample_id == 1
    assert first.wnm.as_dict() == frozen_first
    assert session.pending_observation.support_observation.sample_id == 3
    assert {x.split(':', 1)[0] for x in second.wnm.working_relations} == {'posture', 'support', 'contact'}
    assert session.status().current_map_state_count == 1 and session.status().posture_support_map_revision == 1


def test_routine_recovery_event_produces_expected_measured_difference_in_source_and_wnm():
    session = _session()
    session.run_cognitive_cycle()
    result = session.run_cognitive_cycle()
    facet = result.wnm.support_dynamics
    assert facet.angle_rate == pytest.approx(24.4865888, abs=1e-5)
    assert facet.loading_rate == pytest.approx(0.285)
    assert facet.destabilization_rate == pytest.approx(-0.140375)
    assert facet.trends == ('increasing', 'increasing', 'decreasing')
    assert result.posture_support_state.posture.value == 'fallen'


def test_source_keeps_updating_without_a_wnm_then_return_uses_its_current_content():
    core, owner, _ = _core()
    first = _core_step(core, 1, _packet(1))
    assert first.wnm is not None
    release = _core_step(core, 2, _packet(2, angle=90.0, loading=0.8), posture='standing')
    assert release.wnm is None and core.navigation.current_wnm is None
    assert owner.support_dynamics.reference.sample_id == 2
    returned = _core_step(core, 3, _packet(3, angle=20.0, loading=0.2))
    assert returned.wnm.created_cycle == 3 and returned.wnm.focus_age == 1
    assert returned.wnm.support_dynamics.reference.sample_id == 3
    assert returned.wnm.support_dynamics.previous.sample_id == 2
    assert returned.wnm.support_dynamics.loading_rate == pytest.approx(-0.6)
    assert first.wnm.support_dynamics.reference.sample_id == 1


def test_held_working_content_ages_then_clears_instead_of_reusing_stale_focal_values():
    core, owner, _ = _core()
    _core_step(core, 1, _packet(1))
    held = _core_step(core, 2)
    assert held.wnm.support_dynamics.continuity == 'bounded_continuity'
    assert held.wnm.support_dynamics.reference.event_cycle == 1
    assert held.wnm.refreshed_cycle == 2 and held.wnm.support_dynamics.evidence_age == 1
    _core_step(core, 3)
    expired = _core_step(core, 4)
    assert expired.wnm.support_dynamics.continuity == 'insufficient_evidence'
    assert expired.wnm.support_dynamics.reference is None and owner.support_dynamics.reference is None
    assert expired.wnm.support_dynamics.loading_rate is None
    # A0's coarse scaffold still selects the same action; no measured authority was enabled here.
    assert expired.output == held.output == 'STAND_UP'


def test_no_facet_argument_clears_prior_working_content_not_freshness_of_the_source():
    core, owner, _ = _core()
    _core_step(core, 1, _packet(1))
    result = _core_step(core, 2, _packet(2, loading=0.6))
    before = owner.support_dynamics
    wnm = core.navigation.update_wnm(result.attention_selection)
    assert wnm.support_dynamics is None
    assert owner.support_dynamics is before


@pytest.mark.parametrize('change', ('revision', 'application', 'owner'))
def test_wnm_rejects_wrong_source_timing_or_owner_without_replacing_valid_working_content(change):
    core, owner, _ = _core()
    result = _core_step(core, 1, _packet(1))
    actual = core.navigation.current_wnm
    facet = owner.support_dynamics
    if change == 'revision':
        foreign = replace(facet.configuration.source_map_ref, revision=2)
        facet = replace(facet, configuration=replace(facet.configuration, source_map_ref=foreign))
        with pytest.raises(ValueError):
            core.navigation.update_wnm(result.attention_selection, support_dynamics=facet)
    elif change == 'application':
        _core_step(core, 2, _packet(2))
        actual = core.navigation.current_wnm
        with pytest.raises(ValueError):
            core.navigation.update_wnm(result.attention_selection, support_dynamics=owner.support_dynamics)
    else:
        with pytest.raises(ValueError):
            replace(actual, primary_source_state=replace(actual.primary_source_state, owner_circuit='foreign_owner'))
    assert core.navigation.current_wnm is actual


def test_primitive_cannot_read_measured_facet_in_either_applicability_or_application():
    seen = []
    class InspectingStandUp(StandUpIPV1):
        """A test primitive attempts to observe the field, proving an actual argument boundary."""
        def evaluate_applicability(self, wnm, *, cycle_id):
            seen.append(('query', wnm.support_dynamics))
            assert wnm.support_dynamics is None
            return super().evaluate_applicability(wnm, cycle_id=cycle_id)
        def apply(self, wnm, applicability, *, cycle_id):
            seen.append(('apply', wnm.support_dynamics))
            assert wnm.support_dynamics is None
            return super().apply(wnm, applicability, cycle_id=cycle_id)
    core, _, _ = _core(primitives=(InspectingStandUp(),))
    result = _core_step(core, 1, _packet(1))
    assert result.wnm.support_dynamics is not None
    assert result.navigation.wnm is result.wnm
    assert seen == [('query', None), ('apply', None)]


@pytest.mark.parametrize('flags', ({'attention_enabled': False}, {'navigation_enabled': False}, {'body_action_handoff_enabled': False}))
def test_existing_ablations_and_veto_remain_effective_with_dynamics(flags):
    session = _session(**flags)
    result = session.run_cognitive_cycle()
    assert result.output == 'NO_ACTION' and result.environment_step == 1
    assert session.support_dynamics.reference.sample_id == 1
    assert session.pending_observation.support_observation.sample_id == 2
    if flags.get('attention_enabled') is False:
        assert result.wnm is None
        assert not any(event.channel == 'wnm_support' for event in session.trace_snapshot())


def test_enabling_working_content_cannot_change_the_body_or_prediction_on_opposite_trends():
    core_up, _, _ = _core()
    core_down, _, _ = _core()
    _core_step(core_up, 1, _packet(1, loading=0.4))
    _core_step(core_down, 1, _packet(1, loading=0.8))
    up = _core_step(core_up, 2, _packet(2, loading=0.8))
    down = _core_step(core_down, 2, _packet(2, loading=0.4))
    assert up.wnm.support_dynamics.loading_rate > 0 > down.wnm.support_dynamics.loading_rate
    assert _strip_working_facet(up.as_dict()) == _strip_working_facet(down.as_dict())


def test_history_resets_with_session_and_no_other_session_supplies_a_predecessor():
    first, other = _session(), _session()
    first.run_cognitive_cycle()
    first.run_cognitive_cycle()
    assert first.support_dynamics.previous is not None and other.support_dynamics is None
    initial = other.run_cognitive_cycle()
    assert initial.wnm.support_dynamics.previous is None
    first.reset()
    assert first.support_dynamics is None and first.support_configuration is None
    assert first.run_cognitive_cycle().wnm.support_dynamics.previous is None
    assert first.status().lifecycle_generation == 2


def test_diagnostics_and_ring_eviction_cannot_change_source_working_content_or_actions():
    small = _session(trace_capacity=5)
    large = _session(trace_capacity=256)
    for _ in range(8):
        a, b = small.run_cognitive_cycle(), large.run_cognitive_cycle()
        assert a.as_dict() == b.as_dict() and small.pending_observation == large.pending_observation
        assert small.support_dynamics == large.support_dynamics
        before = small.support_dynamics.as_dict()
        render_flow_trace_lines_v1(small.trace_snapshot())
        render_explanatory_trace_lines_v1(small.trace_snapshot())
        assert small.support_dynamics.as_dict() == before
    assert len(small.trace_snapshot()) == 5
    assert all(dict(event.details)['durable_updates'] == 0 for event in large.trace_snapshot() if event.channel == 'learning')


def test_new_trace_events_have_true_C1_D_placement_bounded_details_and_no_future_reference():
    session = _session()
    for cycle in (1, 2):
        result = session.run_cognitive_cycle()
        events = [event for event in session.trace_snapshot() if event.cycle_id == cycle]
        source = next(event for event in events if event.channel == 'support_dynamics')
        working = next(event for event in events if event.channel == 'wnm_support')
        external = next(event for event in events if event.channel == 'dispatch')
        assert source.phase == CyclePhase.UPDATE_OUTCOMES.name
        assert working.phase == CyclePhase.FOCAL_COMMITMENT.name
        assert source.sequence < working.sequence < external.sequence
        for event in (source, working):
            details = dict(event.details)
            assert len(details) == 16 and details['reference_sample'] == cycle
            assert details['behavioral_authority'] is False
        assert dict(working.details)['loading_rate'] == result.wnm.support_dynamics.loading_rate
    before = session.trace_canonical_bytes()
    text = '\n'.join(render_flow_trace_lines_v1(session.trace_snapshot()))
    assert 'Body-sensory local support dynamics' in text
    assert 'Same WNM - read-only measured support facet' in text
    assert 'excluded from primitive queries and application' in ' '.join(line.strip(' :|') for line in text.splitlines())
    assert 'finite-difference/continuity approximation' in text
    assert 'UNCLASSIFIED' not in text
    assert session.trace_canonical_bytes() == before


def test_unknown_dynamic_event_does_not_inherit_fabricated_mechanism():
    event = Nca8TraceEventV1(1, 'support_dynamics', 'future unrecognized computation', cycle_id=1, phase='UPDATE_OUTCOMES')
    text = '\n'.join(render_flow_trace_lines_v1((event,)))
    assert 'UNCLASSIFIED' in text and 'future unrecognized computation' in text
    assert 'Body-sensory local support dynamics' not in text


def test_partial_new_trace_retains_missing_context_and_never_reconstructs_a_predecessor():
    session = _session()
    session.run_cognitive_cycle()
    event = next(event for event in session.trace_snapshot() if event.channel == 'support_dynamics')
    text = '\n'.join(render_flow_trace_lines_v1((event,)))
    assert 'previous sample=none' in text and 'angle=none' in text
    assert 'sample=2' not in text


def test_profile_is_local_not_a_new_external_oracle_or_reused_SEC_learner():
    tree = ast.parse((ROOT / 'nca8_support_dynamics.py').read_text(encoding='utf-8'))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imports.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
    assert imports == {'__future__', 'math', 'dataclasses', 'nca8_maps'}
    # Neither behavior owner is changed to read the new facet.
    for name in ('nca8_primitives.py', 'nca8_body.py', 'nca8_prediction.py'):
        assert 'support_dynamics' not in (ROOT / name).read_text(encoding='utf-8')


def test_review_command_has_explicit_optin_and_same_commands_with_or_without_trends(capsys):
    previous = run_support_case_v1('recovery', cycles=3)
    capsys.readouterr()
    current = run_support_case_v1('recovery', cycles=3, dynamics=True)
    text = capsys.readouterr().out
    assert 'P16-1E-C' in text and 'rate per event:' in text and 'WNM (read-only)' in text
    assert previous.pending_observation == current.pending_observation
    assert previous.support_dynamics is None and current.support_dynamics is not None
    assert main(['--dynamics', '--case', 'disturbed', '--cycles', '2', '--trace']) == 0
    text = capsys.readouterr().out
    assert 'loading=-0.097500 (decreasing)' in text and 'NCA8 GUIDED FLOW TRACE' in text


def test_review_continuity_demo_identifies_synthetic_scope_expiry_and_frame_rejection(capsys):
    assert main(['--continuity-demo']) == 0
    text = capsys.readouterr().out
    assert 'owner-only; no environment execution or action' in text
    assert 'Cycle 4: missing; input_disposition=missing; continuity=insufficient_evidence' in text
    assert 'Cycle 6: bad-frame; input_disposition=invalid' in text
    assert 'Cycle 7: fresh;' in text and 'reason=first_current_sample' in text
    assert 'angle=+1.000000 (approximately_stable)' in text


def test_review_script_new_optin_works_outside_the_repository(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / 'scripts/run_nca8_support_evidence.py'), '--dynamics', '--case', 'recovery', '--cycles', '2'],
        cwd=tmp_path, text=True, encoding='utf-8', capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert 'loading=+0.285000 (increasing)' in result.stdout


def test_menu_status_reports_new_optin_without_advertising_enhanced_righting(monkeypatch, capsys):
    import builtins
    from nca8_menu import run_nca8_experimental_menu_v1
    session = _session()
    responses = iter(('1', ''))
    monkeypatch.setattr(builtins, 'input', lambda _prompt='': next(responses))
    before = session.trace_canonical_bytes()
    assert run_nca8_experimental_menu_v1(session) is session
    text = capsys.readouterr().out
    assert 'Read-only source dynamics / WNM facet: enabled (no action authority)' in text
    assert session.trace_canonical_bytes() == before and session.support_dynamics is None


def test_review_rejects_non_boolean_dynamics_flag_before_running(capsys):
    with pytest.raises(TypeError):
        run_support_case_v1('recovery', dynamics='true')
    assert not capsys.readouterr().out
