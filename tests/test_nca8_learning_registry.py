"""Every planned learning capability has one honest immutable inventory row."""

from dataclasses import FrozenInstanceError
from collections import Counter
import json

import pytest

from nca8_learning_registry import learning_capabilities_v1, render_learning_ledger_v1


EXPECTED_NAMES = (
    'Sensory discrimination and recognition', 'Recruitment of new sensory representations',
    'Local sensory sequence and motion learning', 'Cross-modal correspondence learning',
    'ANM formation, refinement and differentiation', 'Relational and direct-association learning',
    'Body calibration', 'Task-to-body and support learning', 'SEC sequence, timing and error adaptation',
    'Detailed motor-skill and automatic-execution learning', 'IP calibration and learned coupling',
    'Operation-conditioned consequence learning', 'Learned operation applicability and preference', 'LP acquisition and refinement',
    'Learned attentional relevance and accessibility', 'Habituation and sensitization', 'Learned emotional significance',
    'Experience–internal-consequence learning', 'Extinction, safety learning and reversal', 'Rapid event and episode binding',
    'Local stabilization', 'Replay-supported and systems-level consolidation', 'Retrieval-dependent updating and reconsolidation',
    'Forgetting and selective weakening', 'Regulation of plasticity',
)


def test_exactly_25_unique_canonical_capabilities_with_unchanged_c99_minima():
    rows = learning_capabilities_v1()
    assert tuple(row.capability_id for row in rows) == tuple(f'L{number:02}' for number in range(1, 26))
    assert tuple(row.name for row in rows) == EXPECTED_NAMES
    assert Counter(row.c99_minimum for row in rows) == {'Working': 18, 'Contract permitted': 5, 'Lower contract': 2}
    assert {row.capability_id for row in rows if row.c99_minimum == 'Contract permitted'} == {'L03', 'L16', 'L18', 'L22', 'L23'}


@pytest.mark.parametrize('number', range(25))
def test_each_row_has_owner_depth_evidence_timing_promotion_and_real_maturity(number):
    row = learning_capabilities_v1()[number]
    assert row.owner and row.depth and row.input_output_contract and row.timing_evidence
    assert row.modulation_persistence and row.promotion_control and row.promotion_phase and row.test_destination
    assert row.architecture_source == f'A101 §103.{number + 4}'
    assert row.maturity in {'documentation_contract_only', 'eligibility_only_no_durable_rule'}
    assert row.as_dict()['durable_rule_implemented'] is False
    assert ('RightingLearningHookV1' in row.live_consumer) == (row.capability_id == 'L12')


def test_inventory_is_immutable_detached_and_no_learner_is_constructed(monkeypatch):
    from nca8_learning import RightingLearningHookV1
    monkeypatch.setattr(RightingLearningHookV1, '__init__', lambda *_args, **_kwargs: pytest.fail('ledger created a learner'))
    rows = learning_capabilities_v1()
    with pytest.raises(FrozenInstanceError):
        rows[0].name = 'changed'
    data = rows[0].as_dict()
    data['owner'] = 'fake'
    assert rows[0].owner != 'fake'
    text = render_learning_ledger_v1(detail=True)
    assert 'L01' in text and 'L25' in text and 'no durable learner' in text
    json.dumps([row.as_dict() for row in rows], allow_nan=False)


def test_l12_partial_hook_does_not_promote_l11_l13_or_lp():
    by_id = {row.capability_id: row for row in learning_capabilities_v1()}
    assert by_id['L12'].maturity == 'eligibility_only_no_durable_rule'
    assert all(by_id[key].maturity == 'documentation_contract_only' for key in ('L11', 'L13', 'L14'))
    assert 'GO-LP-DESIGN' in by_id['L14'].promotion_phase
    assert by_id['L12'].promotion_phase == 'P16-3F-B2'
