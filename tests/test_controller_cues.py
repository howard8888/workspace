# tests/test_controller_cues.py
from cca8_world_graph import WorldGraph
from cca8_controller import _any_cue_present  # friend import is fine in tests

def test_any_cue_present_flags_cue_tags():
    g = WorldGraph()
    g.set_tag_policy("allow")
    g.ensure_anchor("NOW")
    assert not _any_cue_present(g)
    g.add_cue("vision:silhouette:mom", attach="now")
    assert _any_cue_present(g)
