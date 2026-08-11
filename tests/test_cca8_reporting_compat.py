"""Compatibility checks for the runner-reporting extraction."""

from __future__ import annotations

import cca8_reporting
import cca8_run


def test_runner_reporting_compatibility_surface() -> None:
    """Historical runner names should resolve to the extracted reporting module."""
    direct_aliases = (
        "TeeTextIO",
        "install_terminal_tee",
        "print_startup_notices",
        "print_working_map_snapshot",
        "print_working_map_layers",
        "print_working_map_entity_table",
        "_hamming_hex64",
        "_snapshot_temporal_legend",
        "timekeeping_line",
        "print_timekeeping_line",
        "_python_loc_counts_for_file",
        "_compute_loc_by_dir",
        "_render_loc_by_dir_table",
        "_parse_vector",
        "snapshot_text",
        "export_snapshot",
        "recent_bindings_text",
        "print_env_loop_tag_legend_once",
        "_quiet_solved_rest_tail_v1",
        "_print_cog_cycle_footer",
        "mini_snapshot_text",
        "print_mini_snapshot",
        "drives_and_tags_text",
        "skill_ledger_text",
        "skills_hud_text",
        "_io_banner",
    )

    for name in direct_aliases:
        assert getattr(cca8_run, name) is getattr(cca8_reporting, name)

    # These small graph/drive helpers remain runner-owned because they also
    # participate in non-reporting runtime paths. Reporting keeps private,
    # read-only equivalents for its own formatting work.
    assert cca8_run._drive_tags is not cca8_reporting._drive_tags  # pylint: disable=protected-access
    assert cca8_run._anchor_id is not cca8_reporting._anchor_id  # pylint: disable=protected-access
    assert cca8_run._sorted_bids is not cca8_reporting._sorted_bids  # pylint: disable=protected-access

    # The SurfaceGrid wrapper intentionally remains runner-owned so existing
    # monkeypatches of runner formatting hooks continue to work at call time.
    assert cca8_run._surfacegrid_ascii_terminal_block_v1 is not (  # pylint: disable=protected-access
        cca8_reporting._surfacegrid_ascii_terminal_block_v1  # pylint: disable=protected-access
    )

    registry = dict(cca8_run._CCA8_COMPONENT_REGISTRY)  # pylint: disable=protected-access
    assert registry["reporting"] == "cca8_reporting"
    assert "cca8_run" not in cca8_reporting.__dict__
