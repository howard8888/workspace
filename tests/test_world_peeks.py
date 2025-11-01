# tests/test_world_peeks.py
import ast
import pathlib

# Files where peeking is allowed (trusted-friend seam + world internals + run script + example)
ALLOW_FILES = {
    "cca8_controller.py",
    "cca8_world_graph.py",
    "cca8_run.py",          # TEMP allow
    "example_test.py",      # TEMP allow
}

# Directories we don't scan
SKIP_DIRS = {
    "tests", "archive", ".git", ".venv", "venv", "build", "dist", "__pycache__", "examples", "scripts"
}

def _offenders_in_file(path: pathlib.Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(text, filename=str(path))
    except Exception:
        return []
    hits = []
    class V(ast.NodeVisitor):
        def visit_Attribute(self, node: ast.Attribute):
            # match: world._bindings
            if isinstance(node.value, ast.Name) and node.value.id == "world" and node.attr == "_bindings":
                hits.append(f"{path}:{node.lineno}")
            self.generic_visit(node)
    V().visit(tree)
    return hits

def test_world_bindings_peek_is_quarantined():
    root = pathlib.Path(__file__).resolve().parents[1]
    offenders: list[str] = []
    for p in root.rglob("*.py"):
        if any(seg in SKIP_DIRS for seg in p.parts):
            continue
        if p.name in ALLOW_FILES:
            continue
        offenders.extend(_offenders_in_file(p))
    offenders.sort()
    assert not offenders, "Don't peek world._bindings outside controller: " + ", ".join(offenders)
