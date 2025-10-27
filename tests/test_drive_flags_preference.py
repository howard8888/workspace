# tests/test_drive_flags_preference.py

import pytest

from cca8_controller import Drives  # flags()/predicates() live here
from cca8_run import _drive_tags    # runner helper prefers flags() over predicates()

def test_drives_flags_exists_and_matches_thresholds():
    """
    Drives.flags() should emit the three drive:* flags based on strict thresholds:
      hunger > 0.60, fatigue > 0.70, warmth < 0.30
    predicates() is a deprecated alias and should equal flags().
    """
    d = Drives(hunger=0.61, fatigue=0.71, warmth=0.29)
    expect = {"drive:hunger_high", "drive:fatigue_high", "drive:cold"}
    assert set(d.flags()) == expect
    assert d.predicates() == d.flags()  # alias remains for back-compat

    # Boundary values shouldn't trigger
    d2 = Drives(hunger=0.60, fatigue=0.70, warmth=0.30)
    assert d2.flags() == []
    assert d2.predicates() == []


def test_runner_drive_tags_prefers_flags_over_predicates():
    """
    The runner's _drive_tags(...) must prefer Drives.flags() over predicates()
    when both exist (ensures our rename doesn't regress behavior).
    """
    class FakeDrives:
        # Make both available, but return different signals so preference is visible
        def flags(self):
            return ["drive:from_flags"]
        def predicates(self):
            return ["drive:from_predicates"]
        # Ensure the threshold fallback wouldn't add anything
        hunger = 0.0
        fatigue = 0.0
        warmth = 1.0

    fd = FakeDrives()
    tags = _drive_tags(fd)
    assert tags == ["drive:from_flags"], "runner should prefer flags() over predicates()"
