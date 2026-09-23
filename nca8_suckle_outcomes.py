#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-2C-I: original Suckle claims, actual permission and later sensed relations.

This bounded operation-local correspondence owner observes the accepted H path.
It cannot select a task, inspect the plant, refresh a source, command closure,
establish H's two-sample latch proof, or assign causal credit. H predicts closure
and conditional seal at an anchored contact, not milk or complete feeding.
Original claims survive subsequent source/PNM replacement without being edited.

The fixed endpoint profile uses H's 0.025 closure tolerance and 0.005-metre
contact bound. Exact endpoint acquisitions may arrive up to eight ticks late.
A changed authorization excludes dependent relations instead of rewriting the
forecast. Missing sensing and unknown execution are not executed failures.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1
from cca8_navmap_kernel import NavPointV1
from nca8_body_targets import BodyTargetProposalV1, OralClosureRequestV1
from nca8_prediction import SucklePreviewV1
from nca8_sensorimotor_contracts import BodyRelativeTargetV1, CommittedBodyTargetV1, LocalTargetReportV1, SensorimotorTargetKindV1
from nca8_suckle import SuckleApplicationV1
from nca8_visual import VisualObservationV1

__version__ = "0.1.0"
__all__ = ["SuckleEndpointV1", "SuckleIntervalEvidenceV1", "SuckleClaimV1", "SuckleOutcomeV1", "SuckleOutcomeFrameV1",
           "SuckleOutcomeRuntimeV1", "__version__"]
_RELATIONS = ("mouth_position", "detail_anchor", "closure", "seal")
_GEOMETRY_TOLERANCE = 0.005
_CLOSURE_TOLERANCE = 0.025
_END_DISPOSITIONS = frozenset({"cancelled", "interrupted", "unavailable", "blocked", "expired"})


def _tick(value: int) -> int:
    """Reject coerced, Boolean and overflowing physical time before state changes."""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**63 - 17:
        raise ValueError("Suckle correspondence tick must be a bounded nonnegative integer")
    return value


def _distance(left: NavPointV1, right: NavPointV1) -> float:
    """Measure two already frame-compatible points without changing either source."""
    return math.hypot(left.x - right.x, left.y - right.y)


@dataclass(frozen=True, slots=True)
class SuckleEndpointV1:
    """Paired products of one acquisition, not a current source or task verdict.

    Missing visual sensing is explicit. Matching sample/event/availability/frame
    identities and measured SELF prevent borrowing a more convenient scene.
    The derived mouth position uses only sensed body position, heading and reach.
    Historical endpoints need not still be fresh enough to authorize movement.
    """

    feedback: MotorFeedbackV1
    observation: VisualObservationV1 | None

    def __post_init__(self) -> None:
        if not isinstance(self.feedback, MotorFeedbackV1):
            raise TypeError("Suckle endpoint needs canonical motor feedback")
        sample, observation = self.feedback, self.observation
        if observation is None:
            return
        if not isinstance(observation, VisualObservationV1) or sample.planar is None:
            raise ValueError("Suckle visual product requires its paired planar acquisition")
        if (observation.stream, observation.sample_id, observation.event_tick, observation.available_tick, observation.frame_id) != (
            sample.stream, sample.sample_id, sample.event_tick, sample.available_tick, sample.planar.frame_id
        ):
            raise ValueError("Suckle endpoint products disagree on identity, time or frame")
        position = None if observation.self_position is None else (observation.self_position.x, observation.self_position.y)
        if position != sample.planar.position:
            raise ValueError("Suckle visual SELF differs from the original body acquisition")

    @property
    def mouth_position(self) -> NavPointV1 | None:
        """Derive the oral tip only from complete admitted body/heading/reach data."""
        planar, oral = self.feedback.planar, self.feedback.oral
        if planar is None or planar.position is None or planar.heading_degrees is None or oral is None or oral.extension_metres is None:
            return None
        angle = math.radians(planar.heading_degrees)
        return NavPointV1(planar.position[0] + oral.extension_metres * math.cos(angle),
                          planar.position[1] + oral.extension_metres * math.sin(angle))

    def as_dict(self) -> dict[str, object]:
        """Export independent closure, contact and seal; none proves a latch task."""
        mouth = self.mouth_position
        return {"feedback": self.feedback.as_dict(), "visual": None if self.observation is None else self.observation.as_dict(),
                "derived_mouth_position": None if mouth is None else mouth.as_dict(), "establishes_latch_or_milk": False}


@dataclass(frozen=True, slots=True)
class SuckleIntervalEvidenceV1:
    """One returned physical interval, its pre-call reports and sensory deliveries.

    A returned command is exposure, not attainment. Missing products are not
    negative observations. The outer driver creates this detached record; the
    correspondence owner never calls physics. Batches retain original objects.
    """

    tick: int
    command: MotorCommandV1 | None
    reports: tuple[LocalTargetReportV1, ...]
    deliveries: tuple[MotorFeedbackV1, ...]
    observations: tuple[VisualObservationV1, ...]

    def __post_init__(self) -> None:
        _tick(self.tick)
        if self.command is not None and (not isinstance(self.command, MotorCommandV1) or self.command.issued_tick != self.tick):
            raise ValueError("Suckle interval must retain its original command and tick")
        if not isinstance(self.reports, tuple) or len(self.reports) > 2 or any(
            not isinstance(item, LocalTargetReportV1) or item.reported_tick > self.tick for item in self.reports
        ):
            raise ValueError("Suckle interval accepts at most two already available local reports")
        if not isinstance(self.deliveries, tuple) or len(self.deliveries) > 16 or any(
            not isinstance(item, MotorFeedbackV1) or item.available_tick > self.tick + 1 for item in self.deliveries
        ):
            raise ValueError("Suckle interval has invalid or future sensory deliveries")
        if len({item.sample_id for item in self.deliveries}) != len(self.deliveries):
            raise ValueError("Suckle interval cannot repeat one acquisition")
        if not isinstance(self.observations, tuple) or len(self.observations) > 16 or any(
            not isinstance(item, VisualObservationV1) for item in self.observations
        ):
            raise ValueError("Suckle interval requires a bounded immutable visual batch")
        if len({item.sample_id for item in self.observations}) != len(self.observations):
            raise ValueError("Suckle interval cannot repeat a visual product")
        for observation in self.observations:
            sample = next((item for item in self.deliveries if item.sample_id == observation.sample_id), None)
            if sample is None:
                raise ValueError("Suckle visual product lacks its original body acquisition")
            SuckleEndpointV1(sample, observation)

    def endpoints(self) -> tuple[SuckleEndpointV1, ...]:
        """Pair by acquisition identity, never list position or later current state."""
        return tuple(SuckleEndpointV1(sample, next((v for v in self.observations if v.sample_id == sample.sample_id), None))
                     for sample in self.deliveries)


def _authorization_relations(
    preview: SucklePreviewV1, request: OralClosureRequestV1, targets: tuple[CommittedBodyTargetV1, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Classify original relations under the actual finite closure permission.

    An endpoint, lease or rate that cannot supply the original contribution
    makes closure and seal unevaluable under that authorization. This checks
    permitted scope, not a physics prediction or proof of successful execution.
    Compare the target endpoint with the original request, not the task forecast:
    a short-horizon forecast may correctly predict partial closure toward an
    unchanged farther target. Stable scene anchors remain testable. Empty means veto.
    """
    if not targets:
        return (), _RELATIONS
    local = targets[0].target
    if not isinstance(local, BodyRelativeTargetV1) or local.basis.oral_seal is None or local.basis.oral_seal.closure is None:
        raise ValueError("Suckle permission lacks its measured scalar closure basis")
    permitted_closure = min(local.endpoint, local.basis.oral_seal.closure + local.max_rate * 0.05 * local.lease_ticks)
    narrowed = (abs(local.endpoint - request.desired_closure) > 1e-12 or local.lease_ticks != preview.horizon_ticks
                or permitted_closure + 1e-12 < preview.predicted_closure)
    return (("mouth_position", "detail_anchor"), ("closure", "seal")) if narrowed else (_RELATIONS, ())


@dataclass(frozen=True, slots=True)
class SuckleClaimV1:
    """Original selected preview/request and exact authorized target, never a grant.

    Retention does not prolong an actuator lease or keep a second focal PNM
    alive. Proposed meaning and material narrowing stay visible independently.
    No constructor can restore installation from an exported description.
    """

    preview: SucklePreviewV1
    request: OralClosureRequestV1
    targets: tuple[CommittedBodyTargetV1, ...]
    compatible_relations: tuple[str, ...]
    unevaluable_relations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.preview, SucklePreviewV1) or not isinstance(self.request, OralClosureRequestV1):
            raise TypeError("Suckle claim needs its original typed preview and request")
        preview, request = self.preview, self.request
        if (request.origin.stream != preview.basis.stream or request.origin.task_id != preview.task_id
                or request.origin.application_id != preview.pnm.application_id or request.source_map_ref != preview.basis.source_map_ref
                or request.region_id != preview.region_id or request.origin_status != "selected_suckle"
                or request.lease_ticks != preview.horizon_ticks or request.desired_closure != 0.6):
            raise ValueError("Suckle claim changed its original source, task, application or request")
        if not isinstance(self.targets, tuple) or len(self.targets) > 1:
            raise ValueError("Suckle claim must retain the sole closure target or veto")
        for target in self.targets:
            if (not isinstance(target, CommittedBodyTargetV1) or not isinstance(target.target, BodyRelativeTargetV1)
                    or target.target.kind is not SensorimotorTargetKindV1.ORAL_CLOSURE or target.target.origin != request.origin
                    or target.target.basis is not preview.basis.oral_feedback or target.committed_tick != preview.basis.cutoff_tick
                    or target.expires_at_tick > self.due_tick):
                raise ValueError("Suckle permission changed its original body basis, origin or horizon")
        if (self.compatible_relations, self.unevaluable_relations) != _authorization_relations(preview, request, self.targets):
            raise ValueError("Suckle relation subsets disagree with original BodyMap permission")

    @property
    def due_tick(self) -> int:
        """Return the original endpoint event, not the time a later source reads it."""
        return self.preview.basis.cutoff_tick + self.preview.horizon_ticks

    @property
    def expires_at_tick(self) -> int:
        """Allow eight ticks of delivery delay without renewing motor permission."""
        return self.due_tick + 8

    @property
    def authorization_status(self) -> str:
        """Keep pre-execution veto, material narrowing and compatible permission distinct."""
        return "not_applied" if not self.targets else "materially_narrowed" if self.unevaluable_relations else "authorized"

    def as_dict(self) -> dict[str, object]:
        """Describe what was predicted and permitted, without manufacturing evidence."""
        return {"original_preview": self.preview.as_dict(), "proposed_request": self.request.as_dict(),
                "authorized_targets": [item.as_dict() for item in self.targets], "authorization_status": self.authorization_status,
                "compatible_relations": list(self.compatible_relations), "unevaluable_relations": list(self.unevaluable_relations),
                "endpoint_event_tick": self.due_tick, "last_acceptable_availability_tick": self.expires_at_tick,
                "closure_tolerance": _CLOSURE_TOLERANCE, "geometry_tolerance_metres": _GEOMETRY_TOLERANCE,
                "consumer": "suckle_correspondence_v1", "grants_motor_authority": False, "predicts_latch_dwell_or_milk": False}


@dataclass(frozen=True, slots=True)
class SuckleOutcomeV1:
    """One consumed claim with original evidence, not a latch proof or causal reward."""

    number: int
    claim: SuckleClaimV1
    status: str
    evaluated_tick: int
    evidence: SuckleEndpointV1 | None
    relations: tuple[tuple[str, str], ...]
    residuals: tuple[tuple[str, float], ...]
    command_intervals: int
    installed: bool
    reason: str

    def as_dict(self) -> dict[str, object]:
        """Expose actual exposure separately from predicted and observed attainment."""
        return {"number": self.number, "claim": self.claim.as_dict(), "status": self.status,
                "evaluated_tick": self.evaluated_tick, "evidence": None if self.evidence is None else self.evidence.as_dict(),
                "relations": dict(self.relations), "residuals": dict(self.residuals), "command_intervals": self.command_intervals,
                "installed": self.installed, "installation_reported": self.installed, "reason": self.reason,
                "execution_certainty": "unknown_after_fault" if self.status == "unresolved_stopped" else "returned_intervals_only",
                "causal_credit": "not_established",
                "latch_task": "separate_H_two_sample_proof", "milk": "not_supplied", "durable_updates": 0}


@dataclass(frozen=True, slots=True)
class SuckleOutcomeFrameV1:
    """One read-only focal-cycle view of registration, pending claims and outcomes."""

    cutoff_tick: int
    outcomes: tuple[SuckleOutcomeV1, ...]
    registration: SuckleClaimV1 | None
    pending: tuple[SuckleClaimV1, ...]
    comparison_enabled: bool

    def as_dict(self) -> dict[str, object]:
        """Report only I's implemented consumer; Attention and learning remain absent."""
        return {"profile": "suckle_correspondence_v1", "cutoff_tick": self.cutoff_tick,
                "outcomes": [item.as_dict() for item in self.outcomes], "pending": [item.as_dict() for item in self.pending],
                "registration": None if self.registration is None else self.registration.as_dict(),
                "comparison_enabled": self.comparison_enabled, "attention_route": "deferred_suckle_attention",
                "learning_route": "unimplemented_no_participation", "durable_updates": 0}


@dataclass(slots=True)
class _Pending:
    """Finite claim/exposure accounting, not a second task or current source."""

    claim: SuckleClaimV1
    installed: bool = False
    command_intervals: int = 0
    ended_tick: int | None = None
    end_reason: str | None = None


class SuckleOutcomeRuntimeV1:
    """Reconcile selected H forecasts with protected execution and eligible sensing.

    consume_intervals runs at C2; register runs before handoff at E. installed
    is called only after the outer owner successfully installs the identical
    target. Incoming batches validate completely before mutation. Eight pending
    claims, 32 outcomes, sixteen recent acquisitions and one installation
    reference bound this owner. A fault closes it; reset constructs a new owner.

    Comparison-off disables scoring, not task behavior, registration, evidence,
    authority or exposure accounting. No method here supplies an Attention bid,
    participation record, Phase-F learning signal, motor action or current fact.
    """

    def __init__(self, stream: MotorStreamRefV1, *, compare_predictions: bool = True) -> None:
        if not isinstance(stream, MotorStreamRefV1) or not isinstance(compare_predictions, bool):
            raise TypeError("Suckle correspondence needs a stream and Boolean comparison switch")
        self.stream, self.compare_predictions = stream, compare_predictions
        self._pending: dict[str, _Pending] = {}
        self._history: deque[SuckleOutcomeV1] = deque(maxlen=32)
        self._recent: deque[SuckleEndpointV1] = deque(maxlen=16)
        self._awaiting: SuckleClaimV1 | None = None
        self._installed_target: CommittedBodyTargetV1 | None = None
        self._execution_end_tick: int | None = None
        self._last_interval, self._last_cutoff = -1, -1
        self._last_command_id = self._last_registration_cycle = self._number = 0
        self._closed = False

    def pending(self) -> tuple[SuckleClaimV1, ...]:
        """Read original obligations without changing evidence lifetime or authority."""
        return tuple(item.claim for item in self._pending.values())

    def history(self) -> tuple[SuckleOutcomeV1, ...]:
        """Read retained terminal evidence without consuming or replaying experience."""
        return tuple(self._history)

    def retained_counts(self) -> dict[str, int]:
        """Measure actual live storage independently of external review retention."""
        return {"suckle_pending_claims": len(self._pending), "suckle_outcome_history": len(self._history),
                "suckle_recent_acquisitions": len(self._recent), "suckle_awaiting_installation": int(self._awaiting is not None),
                "suckle_execution_reference": int(self._installed_target is not None)}

    def register(
        self, application: SuckleApplicationV1, proposal: BodyTargetProposalV1, targets: tuple[CommittedBodyTargetV1, ...],
    ) -> SuckleClaimV1:
        """Preserve the original selected claim and actual BodyMap subset before handoff.

        A veto finishes as not_applied; narrowing never changes the preview. The
        exact request and bound target objects must survive transport. Overflow
        stops registration before a ninth unanswered obligation can be created.
        """
        if self._closed or self._awaiting is not None:
            raise RuntimeError("Suckle correspondence is closed or awaits installation disposition")
        if not isinstance(application, SuckleApplicationV1) or not isinstance(proposal, BodyTargetProposalV1):
            raise TypeError("register the selected Suckle application and its actual BodyMap proposal")
        preview, request = application.projection, application.contribution
        if proposal.request is not request or request.origin.stream != self.stream or preview.basis.stream != self.stream:
            raise ValueError("Suckle proposal changed its original request or stream")
        if (preview.pnm.created_cycle <= self._last_registration_cycle or preview.basis.cutoff_tick != self._last_cutoff
                or proposal.created_tick != self._last_cutoff):
            raise ValueError("Suckle registration must follow this new frozen opportunity")
        if not isinstance(targets, tuple) or len(targets) > 1 or len(targets) != len(proposal.bindings):
            raise ValueError("Suckle permission must preserve the original sole binding or veto")
        for target, binding in zip(targets, proposal.bindings):
            if not isinstance(target, CommittedBodyTargetV1) or target.target is not binding.target:
                raise ValueError("Suckle permission must retain the identical BodyMap binding")
        compatible, unevaluable = _authorization_relations(preview, request, targets)
        claim = SuckleClaimV1(preview, request, targets, compatible, unevaluable)
        claim_id = preview.pnm.pnm_id
        if claim_id in self._pending or any(item.claim.preview.pnm.pnm_id == claim_id for item in self._history):
            raise ValueError("Suckle claim has already been registered")
        if len(self._pending) >= 8:
            raise OverflowError("eight unanswered Suckle claims; no silent eviction or additional dispatch")
        self._pending[claim_id] = _Pending(claim)
        self._last_registration_cycle = preview.pnm.created_cycle
        if targets:
            self._awaiting = claim
        else:
            self._finish(claim_id, "not_applied", self._last_cutoff, reason="BodyMap vetoed the original closure contribution")
        return claim

    def installed(self, claim: SuckleClaimV1, *, at_tick: int) -> None:
        """Record successful outer installation once; this is not physical attainment."""
        tick = _tick(at_tick)
        if self._closed or not isinstance(claim, SuckleClaimV1) or claim is not self._awaiting or tick != self._last_cutoff:
            raise ValueError("Suckle installation must answer its identical awaiting claim")
        self.end_execution(at_tick=tick, reason="replacement")
        self._pending[claim.preview.pnm.pnm_id].installed = True
        self._installed_target, self._execution_end_tick, self._awaiting = claim.targets[0], None, None

    def end_execution(self, *, at_tick: int, reason: str = "cancelled") -> None:
        """Stop pursuit, retaining prior exposure and already realized endpoint claims.

        A cancellation before the endpoint makes the forecast unscored after
        earlier intervals have been consumed. At or after the endpoint it cannot
        erase a corresponding buffered acquisition. No lease is extended here.
        """
        tick = _tick(at_tick)
        if reason not in {"cancelled", "replacement"} or tick < self._last_cutoff:
            raise ValueError("Suckle execution end has a historical time or invalid reason")
        if self._installed_target is not None and self._execution_end_tick is None:
            self._execution_end_tick = tick
        for item in self._pending.values():
            if item.installed and item.ended_tick is None and tick < item.claim.due_tick:
                item.ended_tick, item.end_reason = tick, reason

    def close(self, *, reason: str) -> None:
        """Close pending obligations unresolved after a fault with possible effects.

        Buffered exposure may be incomplete. This is never recoded as a veto or
        no action, even when installation reporting itself was interrupted.
        """
        if not isinstance(reason, str) or not reason or len(reason) > 100:
            raise ValueError("Suckle closure needs a bounded nonempty reason")
        if self._closed:
            return
        for claim_id in tuple(self._pending):
            self._finish(claim_id, "unresolved_stopped", max(0, self._last_cutoff), reason=reason)
        self._awaiting, self._installed_target, self._closed = None, None, True

    def _validate_batch(self, intervals: tuple[SuckleIntervalEvidenceV1, ...], cutoff: int) -> None:
        """Validate a whole contiguous frozen batch without changing any owner state."""
        if not isinstance(intervals, tuple) or len(intervals) > 16:
            raise ValueError("at most sixteen frozen Suckle intervals are permitted")
        if self._last_interval + len(intervals) + 1 != cutoff:
            raise ValueError("Suckle intervals must account for every elapsed physical interval")
        previous_command, ended_at = self._last_command_id, self._execution_end_tick
        known = {item.feedback.sample_id: item for item in self._recent}
        for index, interval in enumerate(intervals):
            if not isinstance(interval, SuckleIntervalEvidenceV1) or interval.tick != self._last_interval + index + 1:
                raise ValueError("Suckle intervals must be contiguous and consumed once")
            command = interval.command
            if command is not None:
                command.validate_for_update(stream=self.stream, now_tick=interval.tick, previous_command_id=previous_command)
                previous_command = command.command_id
            closure_reports = tuple(r for r in interval.reports if r.committed_target.target.kind is SensorimotorTargetKindV1.ORAL_CLOSURE)
            if len(closure_reports) > 1:
                raise ValueError("Suckle interval cannot repeat the closure resource")
            if any(r.committed_target.target.origin.stream != self.stream for r in interval.reports):
                raise ValueError("Suckle execution report belongs to a foreign generation")
            if any(r.committed_target is not self._installed_target for r in closure_reports):
                raise ValueError("closure report does not describe the original installed target")
            if command is not None and command.oral_closure_drive not in (None, 0.0):
                if not closure_reports:
                    raise ValueError("closure command lacks its original authorized report")
                report = closure_reports[0]
                if (not report.committed_target.committed_tick <= interval.tick < report.committed_target.expires_at_tick
                        or report.reported_tick != interval.tick or report.disposition.value not in {"active", "partial"}):
                    raise ValueError("closure command lacks current live permission within its lease")
                if ended_at is not None and interval.tick >= ended_at:
                    raise ValueError("closure command follows revoked execution")
            for report in closure_reports:
                if report.disposition.value in _END_DISPOSITIONS:
                    ended_at = report.reported_tick if ended_at is None else min(ended_at, report.reported_tick)
            for endpoint in interval.endpoints():
                sample = endpoint.feedback
                sample.validate_available(stream=self.stream, at_tick=cutoff)
                if sample.sample_id in known and known[sample.sample_id] != endpoint:
                    raise ValueError("one Suckle acquisition cannot contain conflicting paired products")
                known[sample.sample_id] = endpoint
                for item in self._pending.values():
                    basis = item.claim.preview.basis.oral_feedback
                    if sample.event_tick == item.claim.due_tick and (basis is None or sample.sample_id <= basis.sample_id):
                        raise ValueError("Suckle endpoint must be a distinct post-prediction acquisition")

    def consume_intervals(
        self, intervals: tuple[SuckleIntervalEvidenceV1, ...], *, cutoff_tick: int,
    ) -> tuple[SuckleOutcomeV1, ...]:
        """Consume returned exposure/evidence at C2, then expire missing endpoints.

        There is no current-source argument: a newer configuration cannot rewrite
        an old claim. Comparison-disabled still records original endpoint identity
        and exposure. It removes only the scoring contribution, not motor behavior.
        """
        cutoff = _tick(cutoff_tick)
        if self._closed or cutoff <= self._last_cutoff:
            raise ValueError("Suckle consumption requires an open owner and a new cutoff")
        self._validate_batch(intervals, cutoff)
        before = self._number
        for interval in intervals:
            command = interval.command
            if command is not None:
                self._last_command_id = command.command_id
            if command is not None and command.oral_closure_drive not in (None, 0.0):
                for item in self._pending.values():
                    if (item.installed and interval.tick < item.claim.due_tick
                            and (item.ended_tick is None or interval.tick < item.ended_tick)
                            and any(r.committed_target is item.claim.targets[0] for r in interval.reports)):
                        item.command_intervals += 1
            for report in interval.reports:
                if report.disposition.value not in _END_DISPOSITIONS:
                    continue
                if report.committed_target is self._installed_target and self._execution_end_tick is None:
                    self._execution_end_tick = report.reported_tick
                for item in self._pending.values():
                    if (item.installed and report.committed_target is item.claim.targets[0]
                            and item.ended_tick is None and report.reported_tick < item.claim.due_tick):
                        item.ended_tick, item.end_reason = report.reported_tick, report.reason
            for endpoint in interval.endpoints():
                self._consume_endpoint(endpoint, cutoff)
            self._last_interval = interval.tick
        for claim_id, item in tuple(self._pending.items()):
            if item.ended_tick is not None and self._last_interval + 1 >= item.ended_tick:
                self._finish(claim_id, "interrupted" if item.command_intervals else "cancelled", cutoff,
                             reason=f"{item.end_reason} before the original endpoint")
            elif cutoff > item.claim.expires_at_tick:
                self._finish(claim_id, "expired_unresolved", cutoff, reason="no exact endpoint inside the original arrival window")
        self._last_cutoff = cutoff
        return tuple(item for item in self._history if item.number > before)

    def _consume_endpoint(self, endpoint: SuckleEndpointV1, cutoff: int) -> None:
        """Consume an original event once, never substituting the latest success."""
        sample = endpoint.feedback
        if any(item.feedback.sample_id == sample.sample_id for item in self._recent):
            return
        self._recent.append(endpoint)
        for claim_id, item in tuple(self._pending.items()):
            claim = item.claim
            if (not item.installed or item.ended_tick is not None or sample.event_tick != claim.due_tick
                    or sample.available_tick > claim.expires_at_tick):
                continue
            if not self.compare_predictions:
                self._finish(claim_id, "comparison_disabled", cutoff, evidence=endpoint,
                             reason="only scoring disabled; original registration, exposure and evidence retained")
                continue
            relations, residuals, identity = _compare(claim, endpoint)
            values = {value for _, value in relations}
            status = "mismatch" if "mismatch" in values else "unknown" if "unknown" in values else "matched"
            if status == "matched" and claim.unevaluable_relations:
                status = "partly_matched"
            if identity == "contradicted":
                status = "identity_contradicted"
            if item.command_intervals == 0:
                status = "observed_without_command"
            self._finish(claim_id, status, cutoff, evidence=endpoint, relations=relations, residuals=residuals,
                         reason="original closure/conditional-seal claim; latch dwell and causal credit remain separate")

    def _finish(
        self, claim_id: str, status: str, tick: int, *, reason: str, evidence: SuckleEndpointV1 | None = None,
        relations: tuple[tuple[str, str], ...] = (), residuals: tuple[tuple[str, float], ...] = (),
    ) -> None:
        """Publish one immutable terminal result and remove its pending obligation."""
        item = self._pending.pop(claim_id)
        self._number += 1
        self._history.append(SuckleOutcomeV1(self._number, item.claim, status, tick, evidence, relations, residuals,
                                              item.command_intervals, item.installed, reason))
        if self._awaiting is item.claim:
            self._awaiting = None


def _compare(
    claim: SuckleClaimV1, endpoint: SuckleEndpointV1,
) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[str, float], ...], str]:
    """Compare H's original relations using only a paired historical acquisition.

    A missing product is unknown. Closure never substitutes for a seal sensor.
    True seal must be localizable to the supported original detail with touch;
    inconsistent no-touch/true-seal remains unknown. A known absent seal tests
    the conditional forecast, not private surface properties or milk transfer.
    """
    preview, sample, observation = claim.preview, endpoint.feedback, endpoint.observation
    detail = None if observation is None else next((d for d in observation.detections if d.region_id == preview.region_id), None)
    parent = None if observation is None else next((d for d in observation.detections
                                                    if d.region_id == preview.basis.seed.parent_region_id), None)
    identity = "unknown"
    if detail is not None and detail.descriptor is not None:
        if detail.descriptor != "feeding":
            identity = "contradicted"
        elif parent is not None and parent.descriptor is not None:
            if parent.descriptor != preview.basis.maternal.seed.descriptor:
                identity = "contradicted"
            elif parent.position is not None and detail.position is not None:
                identity = ("supported" if _distance(parent.position, detail.position) <= preview.basis.seed.maximum_parent_distance + 1e-12
                            else "contradicted")
    same_frame = sample.planar is not None and sample.planar.frame_id == preview.basis.frame_id
    mouth, original_mouth = endpoint.mouth_position, preview.basis.mouth_position
    residuals: dict[str, float] = {}
    if same_frame and mouth is not None and original_mouth is not None:
        residuals["mouth_position"] = _distance(mouth, original_mouth)
    if same_frame and identity == "supported" and detail is not None and detail.position is not None:
        residuals["detail_anchor"] = _distance(detail.position, preview.scene_target)
    seal = sample.oral_seal
    if seal is not None and seal.closure is not None:
        residuals["closure"] = abs(seal.closure - preview.predicted_closure)
    values = {name: "unknown" if name not in residuals else
              "matched" if residuals[name] <= (_CLOSURE_TOLERANCE if name == "closure" else _GEOMETRY_TOLERANCE) + 1e-12 else "mismatch"
              for name in _RELATIONS[:-1]}
    values["seal"] = "unknown"
    if preview.predicted_closure < 0.6 - 1e-12:
        values["seal"] = "not_predicted"
    elif same_frame and identity == "supported" and seal is not None and seal.sealed is not None:
        if not seal.sealed:
            values["seal"] = "mismatch"
        elif (sample.oral is not None and sample.oral.contact is True and mouth is not None
              and detail is not None and detail.position is not None and _distance(mouth, detail.position) <= _GEOMETRY_TOLERANCE + 1e-12):
            values["seal"] = "matched"
    relations = tuple((name, "unevaluable_authorization" if name in claim.unevaluable_relations else values[name]) for name in _RELATIONS)
    return relations, tuple(residuals.items()), identity
