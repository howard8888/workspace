from cca8_controller import reset_skills, update_skill, skills_to_dict, skills_from_dict, skill_readout
from cca8_reporting import skills_hud_text

def test_skills_roundtrip_and_readout():
    reset_skills()
    update_skill("policy:rest", reward=0.2, ok=True)
    update_skill("policy:rest", reward=0.0, ok=False, execution=False)

    snap = skills_to_dict()
    assert "policy:rest" in snap
    assert snap["policy:rest"]["execution_count"] == 1
    assert snap["policy:rest"]["learning_update_count"] == 2

    reset_skills()
    skills_from_dict(snap)
    txt = skill_readout()
    assert "policy:rest" in txt
    assert "exec=1" in txt
    assert "updates=2" in txt
    assert "q=" in txt

    hud = skills_hud_text()
    assert "exec=  1" in hud
    assert "updates=  2" in hud
    assert "rate=1.00" in hud
    assert "last_exec=+0.20" in hud
    assert "last_update=+0.00" in hud


def test_legacy_skill_snapshot_loads_with_explicitly_inferred_execution_count():
    """Pre-split save files should remain readable without pretending the inference is exact."""
    reset_skills()
    skills_from_dict(
        {
            "policy:legacy": {
                "n": 5,
                "succ": 4,
                "q": 0.6,
                "last_reward": 1.0,
            }
        }
    )

    row = skills_to_dict()["policy:legacy"]
    assert row["learning_update_count"] == 5
    assert row["execution_count"] == 5
    assert row["execution_count_inferred"] is True
    assert "inferred_exec" in skill_readout()
