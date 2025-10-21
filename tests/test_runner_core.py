import types
import io, sys
import pytest
RUN = pytest.importorskip("cca8_run", reason="missing runner")

def test_versions_dict_reports_core_components():
    d = RUN.versions_dict()
    for key in ("runner", "platform", "python", "world_graph", "controller", "column", "features", "temporal"):
        assert key in d

def test_io_banner_variants(capsys):
    args = types.SimpleNamespace(autosave="", load=None)
    RUN._io_banner(args, loaded_path=None, loaded_ok=False)
    out = capsys.readouterr().out
    assert "Autosave OFF" in out

    args = types.SimpleNamespace(autosave="session.json", load=None)
    RUN._io_banner(args, loaded_path=None, loaded_ok=False)
    out = capsys.readouterr().out
    assert "Autosave ON" in out
