import os
import pytest

W = pytest.importorskip("cca8_world_graph", reason="world graph not found")

@pytest.mark.viz
def test_to_pyvis_html_writes_file(tmp_path):
    w = W.WorldGraph()
    if hasattr(w, "set_tag_policy"): w.set_tag_policy("allow")
    now = w.ensure_anchor("NOW")
    goal = w.add_predicate("goal", attach="now")

    out = w.to_pyvis_html(path_html=str(tmp_path / "graph.html"), physics=False)
    assert os.path.exists(out)
    # quick sanity on file content
    text = (tmp_path / "graph.html").read_text(encoding="utf-8")
    assert "pyvis" in text.lower() or "network" in text.lower()
