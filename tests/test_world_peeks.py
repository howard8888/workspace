"""Guard current CCA8 production modules from direct world._bindings access."""

from __future__ import annotations

import ast
from pathlib import Path


# These modules currently have deliberate access to WorldGraph internals.
# The TEMPORARY exceptions should eventually be replaced with public methods.
ALLOW_FILES = {
    "cca8_world_graph.py",
    "cca8_controller.py",  # TEMPORARY
    "cca8_run.py",         # TEMPORARY
}


def _offenders_in_file(path: Path) -> list[str]:
    """Return locations containing direct world._bindings access."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(text, filename=str(path))
    except (OSError, SyntaxError):
        # Syntax validation is outside this architectural test's purpose.
        return []

    hits: list[str] = []

    class BindingVisitor(ast.NodeVisitor):
        def visit_Attribute(self, node: ast.Attribute) -> None:
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "world"
                and node.attr == "_bindings"
            ):
                hits.append(
                    f"{path.name}:{node.lineno}:{node.col_offset + 1}"
                )

            self.generic_visit(node)

    BindingVisitor().visit(tree)
    return hits


def test_world_bindings_peek_is_quarantined() -> None:
    """CCA8 production modules should use the public WorldGraph interface."""
    root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []

    # Deliberately inspect only current root-level CCA8 production modules.
    for path in sorted(root.glob("cca8_*.py")):
        if path.name in ALLOW_FILES:
            continue

        offenders.extend(_offenders_in_file(path))

    offenders.sort()

    assert not offenders, (
        "Direct world._bindings access found outside the approved modules. "
        "Use a public WorldGraph method or deliberately update ALLOW_FILES:\n"
        + "\n".join(offenders)
    )
