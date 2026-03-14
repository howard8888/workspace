from __future__ import annotations

import cca8_env
import cca8_navpatch
import cca8_run


def _set_cell(cells: list[int], grid_w: int, x: int, y: int, value: int) -> None:
    """Small local helper for writing one cell into a flat grid list."""
    cells[(y * grid_w) + x] = int(value)


def _build_navsummary_test_grid() -> cca8_navpatch.SurfaceGridV1:
    """Build a tiny deterministic SurfaceGrid for direct NavSummary tests.

    Layout intent
    -------------
    SELF is at the center (3,3) of a 7x7 grid.

    We create:
      - one connected safe corridor from SELF to an eastward goal,
      - one disconnected safe island inside the local radius,
      - two nearby hazard cells north of SELF.

    This gives us a testbed where:
      - hazard_near should be True,
      - goal_dir should be E,
      - shortest_safe_path_cost should be 2,
      - corridor_count should be 2.
    """
    w = 7
    h = 7
    cells = [cca8_navpatch.CELL_UNKNOWN] * (w * h)

    cx = 3
    cy = 3

    # Connected safe path from SELF to an eastward goal.
    _set_cell(cells, w, cx, cy, cca8_navpatch.CELL_TRAVERSABLE)
    _set_cell(cells, w, 4, 3, cca8_navpatch.CELL_TRAVERSABLE)
    _set_cell(cells, w, 5, 3, cca8_navpatch.CELL_GOAL)

    # A second disconnected safe island within the local radius.
    _set_cell(cells, w, 1, 3, cca8_navpatch.CELL_TRAVERSABLE)

    # Nearby hazard cells.
    _set_cell(cells, w, 3, 2, cca8_navpatch.CELL_HAZARD)
    _set_cell(cells, w, 4, 2, cca8_navpatch.CELL_HAZARD)

    return cca8_navpatch.SurfaceGridV1(grid_w=w, grid_h=h, grid_cells=cells)


def _make_safe_navsummary_observation() -> cca8_env.EnvObservation:
    """Create one safe/sheltered EnvObservation for integration testing.

    This mirrors the later phase of the newborn-goat storyboard:
      - mom near/touching,
      - shelter near,
      - cliff far,
      - nipple latched,
      - position in shelter_area.

    The goal here is not to test the environment itself, but to make sure the
    runner computes and caches a NavSummary from a realistic observation packet.
    """
    state = cca8_env.EnvState(
        kid_posture="resting",
        mom_distance="touching",
        shelter_distance="near",
        cliff_distance="far",
        nipple_state="latched",
        scenario_stage="rest",
        position="shelter_area",
        kid_position=(1.6, 0.0),
        mom_position=(1.6, 0.0),
    )
    state.update_zone_from_position()

    adapter = cca8_env.PerceptionAdapter()
    return adapter.observe(state)


def test_compute_navsummary_v1_direct_grid_metrics() -> None:
    """NavSummary should compute the expected local topology metrics from a direct grid.

    This is the most important pure-function test because it exercises the small
    topology scan without depending on the full env/controller pipeline.
    """
    sg = _build_navsummary_test_grid()

    summary = cca8_run.compute_navsummary_v1(
        sg,
        slots=None,
        self_xy=(3, 3),
        local_radius=2,
    )

    assert summary["schema"] == "wm_navsummary_v1"
    assert summary["grid_w"] == 7
    assert summary["grid_h"] == 7
    assert summary["self_xy"] == [3, 3]
    assert summary["local_radius"] == 2

    assert summary["hazard_near"] is True
    assert summary["goal_present"] is True
    assert summary["goal_dir"] == "E"
    assert summary["goal_distance_l1"] == 2
    assert summary["shortest_safe_path_cost"] == 2
    assert summary["corridor_count"] == 2

    assert 0.0 < summary["hazard_density"] < 1.0
    assert 0.0 < summary["traversable_density"] < 1.0

    counts = summary["local_counts"]
    assert counts["hazard"] == 2
    assert counts["goal"] == 1
    assert counts["traversable"] == 3
    assert counts["known"] == 6
    assert counts["unknown"] >= 0


def test_compute_navsummary_v1_prefers_slot_family_overrides() -> None:
    """When slot-family hints are supplied, the boolean/dir summaries should prefer them.

    This keeps NavSummary aligned with the Step-13 slot-family layer when that
    layer already has a stable symbolic interpretation.
    """
    sg = _build_navsummary_test_grid()

    summary = cca8_run.compute_navsummary_v1(
        sg,
        slots={
            "hazard:near": False,
            "terrain:traversable_near": False,
            "goal:dir": "NW",
        },
        self_xy=(3, 3),
        local_radius=2,
    )

    # These three should follow the slot-family overrides, not the raw grid.
    assert summary["hazard_near"] is False
    assert summary["traversable_near"] is False
    assert summary["goal_dir"] == "NW"

    # The rest of the numeric summary should still be computed from the grid.
    assert summary["goal_present"] is True
    assert summary["goal_distance_l1"] == 2
    assert summary["shortest_safe_path_cost"] == 2
    assert summary["corridor_count"] == 2
    assert summary["hazard_density"] > 0.0


def test_format_navsummary_line_v1_renders_compact_readable_summary() -> None:
    """The terminal formatter should emit the expected compact fields."""
    sg = _build_navsummary_test_grid()
    summary = cca8_run.compute_navsummary_v1(
        sg,
        slots=None,
        self_xy=(3, 3),
        local_radius=2,
    )

    line = cca8_run.format_navsummary_line_v1(summary)

    assert "hazard_near=1" in line
    assert "traversable_near=1" in line
    assert "corridors=2" in line
    assert "goal_dir=E" in line
    assert "goal_l1=2" in line
    assert "safe_cost=2" in line

    assert cca8_run.format_navsummary_line_v1({}) == "(none)"


def test_inject_obs_into_working_world_populates_ctx_wm_navsummary() -> None:
    """The live WorkingMap injection path should populate ctx.wm_navsummary.

    This is the integration-level test that proves NavSummary is not just a pure
    helper function: it is actually computed and cached during the real env_obs →
    WorkingMap pipeline.
    """
    ctx = cca8_run.Ctx()
    ctx.body_world, ctx.body_ids = cca8_run.init_body_world()
    ctx.working_world = cca8_run.init_working_world()

    obs = _make_safe_navsummary_observation()

    cca8_run.update_body_world_from_obs(ctx, obs)
    out = cca8_run.inject_obs_into_working_world(ctx, obs)

    assert isinstance(out, dict)
    assert ctx.wm_surfacegrid is not None
    assert isinstance(ctx.wm_navsummary, dict)
    assert ctx.wm_navsummary["schema"] == "wm_navsummary_v1"

    summary = ctx.wm_navsummary
    assert summary["grid_sig16"] == ctx.wm_surfacegrid_sig16
    assert summary["hazard_near"] is False
    assert summary["traversable_near"] is True
    assert summary["goal_present"] is True
    assert isinstance(summary["goal_dir"], str) and summary["goal_dir"]
    assert isinstance(summary["goal_distance_l1"], int) and summary["goal_distance_l1"] >= 1
    assert isinstance(summary["shortest_safe_path_cost"], int) and summary["shortest_safe_path_cost"] >= 1

    line = cca8_run.format_navsummary_line_v1(summary)
    assert "hazard_near=0" in line
    assert "traversable_near=1" in line
    assert "goal_dir=" in line
    assert "safe_cost=" in line
