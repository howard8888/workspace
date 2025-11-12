from cca8_controller import reset_skills, update_skill, skills_to_dict, skills_from_dict, skill_readout

def test_skills_roundtrip_and_readout():
    reset_skills()
    update_skill("policy:rest", reward=0.2, ok=True)
    update_skill("policy:rest", reward=0.0, ok=False)

    snap = skills_to_dict()
    assert "policy:rest" in snap

    reset_skills()
    skills_from_dict(snap)
    txt = skill_readout()
    assert "policy:rest" in txt and "n=" in txt and "q=" in txt
