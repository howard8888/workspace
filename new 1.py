




    # Always keep BodyMap current (policies are BodyMap-first now).


    try:
        update_body_world_from_obs(ctx, env_obs)
    except Exception:
        # BodyMap update should never be allowed to break env stepping.
        pass
    # Mirror into WorkingMap (raw per-tick trace) when enabled.
    try:
        if getattr(ctx, "working_enabled", False):
            inject_obs_into_working_world(ctx, env_obs)
    except Exception:
        pass

    # Allow turning off long-term injection entirely (BodyMap still updates).
    if not getattr(ctx, "longterm_obs_enabled", True):
        return {"predicates": created_preds, "cues": created_cues, "token_to_bid": token_to_bid}

    mode = (getattr(ctx, "longterm_obs_mode", "snapshot") or "snapshot").strip().lower()
    do_changes = mode in ("changes", "dedup", "delta", "state_changes")

    # Normalize (defensive: some probes may include prefixes already)
    pred_tokens = [
        str(p).replace("pred:", "")
        for p in (getattr(env_obs, "predicates", []) or [])
        if p is not None
    ]
    cue_tokens = [
        str(c).replace("cue:", "")
        for c in (getattr(env_obs, "cues", []) or [])
        if c is not None
    ]

    # Pull a couple of env meta fields for keyframes (if present)
    env_meta = getattr(env_obs, "env_meta", None) or {}

    # Partial observability (Phase VIII): optionally drop some observation facts before they enter memory.
    #
    # Notes:
    # - This is a PERCEPTION knob (what crosses the env→agent boundary), not a change to EnvState truth.
    # - A small set of safety-critical predicate families is protected so zone classification remains stable.
    mask_p = float(getattr(ctx, "obs_mask_prob", 0.0) or 0.0)
    if mask_p > 0.0:
        mask_p = max(0.0, min(1.0, mask_p))

        protect_pred_prefixes = ("posture:", "hazard:cliff:", "proximity:shelter:")

        preds_in = getattr(env_obs, "predicates", None)
        cues_in = getattr(env_obs, "cues", None)

        preds = [t for t in preds_in if isinstance(t, str) and t] if isinstance(preds_in, list) else []
        cues = [t for t in cues_in if isinstance(t, str) and t] if isinstance(cues_in, list) else []

        dropped_preds = 0
        dropped_cues = 0

        preds_out: list[str] = []
        for tok in preds:
            if any(tok.startswith(pfx) for pfx in protect_pred_prefixes):
                preds_out.append(tok)
                continue
            if random.random() < mask_p:
                dropped_preds += 1
                continue
            preds_out.append(tok)

        # Defensive: keep at least one predicate if we had any (avoid “empty observation block” surprises).
        if (not preds_out) and preds:
            preds_out = [preds[0]]
            dropped_preds = max(0, len(preds) - 1)

        cues_out: list[str] = []
        for tok in cues:
            if random.random() < mask_p:
                dropped_cues += 1
                continue
            cues_out.append(tok)

        # Apply the masked lists back onto the observation packet.
        try:
            setattr(env_obs, "predicates", preds_out)
            setattr(env_obs, "cues", cues_out)
        except Exception:
            pass

        if (dropped_preds or dropped_cues) and bool(getattr(ctx, "obs_mask_verbose", True)):
            print(
                f"[obs-mask] dropped preds={dropped_preds}/{len(preds)} cues={dropped_cues}/{len(cues)} "
                f"p={mask_p:.2f} protected={len(protect_pred_prefixes)}"
            )

    stage = env_meta.get("scenario_stage")
    time_since_birth = env_meta.get("time_since_birth")