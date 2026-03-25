from __future__ import annotations

from cca8_run import ExperimentProtocolConfig, experiment_normalize_protocol_v1


def test_experiment_normalize_protocol_v1_sanitizes_invalid_inputs() -> None:
    """Normalize one deliberately messy experiment config and verify the stable contract.

    This is the first experiment-protocol test because later execution patches will depend on
    this helper behaving predictably. I keep the assertions explicit so the intended protocol
    defaults are obvious when the test fails.
    """
    raw = ExperimentProtocolConfig(
        benchmark_id="not_a_real_benchmark",
        condition_ids=["b", "a", "x", "C", "b", "e"],
        seed_list=[11, 23, 11, 41],
        episodes_per_seed=0,
        max_cycles=-7,
        obs_mask_prob=2.5,
        llm_model="  gpt-5.4  ",
        run_label="  goat/ctx:run 01  ",
        output_dir="   ",
    )

    norm = experiment_normalize_protocol_v1(raw)

    assert norm is not raw

    assert norm.benchmark_id == "goat04_context"
    assert norm.condition_ids == ["B", "A", "C", "E"]
    assert norm.seed_list == [11, 23, 41]

    assert norm.episodes_per_seed == 1
    assert norm.max_cycles == 1
    assert norm.obs_mask_prob == 1.0

    assert norm.llm_model == "gpt-5.4"
    assert norm.run_label == "goat_ctx_run_01"
    assert norm.output_dir == "experiment_jsonl"

    defaulted = experiment_normalize_protocol_v1(None)
    assert defaulted.benchmark_id == "goat04_context"
    assert defaulted.condition_ids == ["A", "B", "C", "D", "E"]
    assert defaulted.seed_list == [11, 23, 37, 41, 53]