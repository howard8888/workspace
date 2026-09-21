#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only L01-L25 coverage inventory from Planning v18, Appendix I.

This is documentation data, not a learner scheduler. The canonical capability
names, intended owners/depths, input/evidence and change contracts, timing,
modulation, phase destinations and promotion tests are retained from I.1-I.25.
Current implementation maturity is separately stated: no durable learner is
promoted by registering a row. Only L12 has the narrow, called source-side
eligibility hook; its actual acquisition rule remains unimplemented. H4's fixed
motor provider and fixed protective bounds do not meet adaptive L10/L25 claims.
The host inspector reads this inventory on demand; the focal core and F do not.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

__version__ = "0.1.1"
__all__ = ["LearningCapabilityV1", "learning_capabilities_v1", "render_learning_ledger_v1", "__version__"]


@dataclass(frozen=True, slots=True)
class LearningCapabilityV1:
    """One immutable planned responsibility with separately reported source maturity.

    Intended owners need not yet exist as runtime objects. input_output_contract
    and timing_evidence preserve the planned change and its information basis;
    promotion_control is a future causal test, not a test already passed here.
    Current test_destination distinguishes real hook tests from future gates.
    """

    capability_id: str
    name: str
    owner: str
    depth: str
    input_output_contract: str
    timing_evidence: str
    modulation_persistence: str
    promotion_control: str
    promotion_phase: str
    c99_minimum: str
    architecture_source: str

    @property
    def maturity(self) -> str:
        """Do not confuse future Working minima with actual durable learning."""
        return "eligibility_only_no_durable_rule" if self.capability_id == "L12" else "documentation_contract_only"

    @property
    def live_consumer(self) -> str:
        """Identify the two domain recipients of one partial capability; do not fabricate learners."""
        return ("Nca8BodySensoryModuleV1.learning_hook -> RightingLearningHookV1.reconcile; "
                "MaternalSourceV1.learning_hook -> MaternalLearningHookV1.reconcile (source-side no-learning seams only)"
                if self.capability_id == "L12" else "none; no runtime learner for this row")

    @property
    def test_destination(self) -> str:
        """Separate current plumbing tests from the future required learning proof."""
        return ("tests/test_nca8_learning.py, tests/test_nca8_learning_demo.py, tests/test_nca8_maternal_learning.py "
                "and tests/test_nca8_maternal_learning_demo.py; future durable proof at " + self.promotion_phase
                if self.capability_id == "L12" else "planned promotion experiment at " + self.promotion_phase)

    def as_dict(self) -> dict[str, object]:
        """Return detached documentation; reading a row calls no learning owner."""
        return {**{field.name: getattr(self, field.name) for field in fields(self)}, "maturity": self.maturity,
                "live_consumer": self.live_consumer, "test_destination": self.test_destination,
                "durable_rule_implemented": False}


_CAPABILITIES = (
    LearningCapabilityV1(
        'L01',
        'Sensory discrimination and recognition',
        'Local Sensory NavMap circuitry',
        'Functional abstraction',
        (
            'Improve discrimination, matching and useful invariance of candidate sensory configurations. Learn which '
            'variations matter at the represented relational scale; do not reconstruct retinal or V1 feature-detector '
            'learning.'
        ),
        (
            'During informative sensory processing and across exposures. Adequate candidate evidence, recurrence or a '
            'relevant teaching contribution can support change without any selected IP, reward or completed task.'
        ),
        (
            'Local competition, uncertainty and saturation constrain learning. Emotion/modulatory gain may change sensitivity '
            'where a connection exists, but is not obligatory. Later exposure can strengthen or differentiate the acquired '
            'representation.'
        ),
        (
            'Learn a relational sensory discrimination with a fixed provider; test a held-out variation and learning-off '
            'control.'
        ),
        'P16-3F-A1',
        'Working',
        'A101 §103.4',
    ),
    LearningCapabilityV1(
        'L02',
        'Recruitment of new sensory representations',
        'Local Sensory NavMap circuitry',
        'Functional abstraction',
        (
            'Recruit a weak bounded LSNM for coherent useful novelty that existing organization cannot represent adequately. '
            'A new sensory sample alone does not warrant a new durable NM.'
        ),
        (
            'During the encounter with sufficiently supported novelty. The initial candidate may be usable before it is '
            'strongly stabilized; no fixed repetition count or end-of-task commit is required.'
        ),
        (
            'Repetition, useful discrimination, significance and appropriate reactivation may stabilize the candidate. '
            'Incoherent/noisy input does not receive automatic recruitment; unsupported candidates may weaken.'
        ),
        'Recruit and reuse a weak coherent candidate; noise and duplicate samples must not create one map per exposure.',
        'P16-3F-A1',
        'Working',
        'A101 §103.5',
    ),
    LearningCapabilityV1(
        'L03',
        'Local sensory sequence and motion learning',
        'Relevant sensory circuitry; SEC contributions remain separately owned',
        'Functional abstraction',
        (
            'Learn local order, timing and transitions in represented sensory configurations, including motion, '
            'approach/recession, contact change and provisional continuation.'
        ),
        (
            'As informative sequence elements and their consequences become available. A nonfocal sensory source can learn; a '
            'task-level PNM and completed action are not prerequisites.'
        ),
        (
            'Use bounded histories, competition and later contradictory sequences. Modulation may affect rate or persistence. '
            'The source’s local predictor and SEC must not both count one physical update as separate learning.'
        ),
        (
            'Specify a sensory-owned short-sequence rule and omission/order test. Promote only after a separate '
            'local-sequence experiment; no hidden SEC substitution.'
        ),
        'P16-3F-A4',
        'Contract permitted',
        'A101 §103.6',
    ),
    LearningCapabilityV1(
        'L04',
        'Cross-modal correspondence learning',
        'Participating sensory/ANM association and connection owners',
        'Cognitive mechanism with functional alignment',
        (
            'Learn useful links and alignment constraints among contributions representing the same entity/event or another '
            'declared relationship. Preserve each source’s timing and precision.'
        ),
        (
            'During supported spatial/temporal/identity correspondence, including appropriately delayed contributions. '
            'Learning may follow local coherence; it need not await a focal motor result.'
        ),
        (
            'Compatible repeated or highly informative experience can strengthen links; contradictory geometry or identity '
            'can weaken or differentiate them. Significance may modulate learning, not turn mere simultaneity into truth.'
        ),
        (
            'Learn a cross-modal link from supported encounters; preserve unimodal precision and reject a later geometric '
            'contradiction.'
        ),
        'P16-3F-A3',
        'Working',
        'A101 §103.7',
    ),
    LearningCapabilityV1(
        'L05',
        'ANM formation, refinement and differentiation',
        'ANM Association Modules',
        'Cognitive mechanism',
        (
            'Acquire or refine bounded object, individual, scene, situation, conceptual or procedural organization. Reuse a '
            'suitable ANM and separate similar contexts where the distinction changes behavior.'
        ),
        (
            'During informative encounters and recurrent association; later evidence can enrich, stabilize or split a weak '
            'candidate. Updating its present location is not by itself this learning.'
        ),
        (
            'Local evidence, competition, useful repetition and significance influence persistence. Particular maternal '
            'identity is learned or explicitly scaffolded, not genetically installed by naming an ANM MOM.'
        ),
        (
            'Acquire/refine a bounded association rather than preload its learned content; test reuse, ambiguity and useful '
            'differentiation.'
        ),
        'P16-3F-A2',
        'Working',
        'A101 §103.8',
    ),
    LearningCapabilityV1(
        'L06',
        'Relational and direct-association learning',
        'Participating cortical representation and directional-link owners',
        'Cognitive mechanism',
        (
            'Change relationships and directional access among maps: entity–sound, surface–support, place–shelter, observed '
            'operation–consequence, or another useful bounded relation.'
        ),
        (
            'During informative coactivity and when supporting or contradictory later evidence is available. The goat can '
            'learn from observed events or other agents without executing the same operation.'
        ),
        (
            'Preserve context, uncertainty, saturation and selective weakening. Co-occurrence is not infallible causal proof; '
            'broad significance can create imperfect associations rather than an omniscient credit map.'
        ),
        'Change a directional link separately from map content, and show a later access or relational-prediction effect.',
        'P16-3F-A2',
        'Working',
        'A101 §103.9',
    ),
    LearningCapabilityV1(
        'L07',
        'Body calibration',
        'BodyMap and participating body-sensory circuitry',
        'Functional abstraction',
        (
            'Refine relationships among body/effector configuration, sensed movement, reach, orientation and usable '
            'capability. Do not simulate individual motor units or every proprioceptor.'
        ),
        (
            'During informative self-movement and multisensory discrepancy, including exploratory movement and adaptation '
            'after persistent bodily change. Temporary fatigue is not automatically permanent recalibration.'
        ),
        (
            'Repeated supported calibration can stabilize; changed capability can require recalibration. Relevant '
            'internal/modulatory influences may affect rate. Body growth and learned use of that body remain separate.'
        ),
        (
            'Calibrate represented reach/body capability after persistent change; distinguish learning from current fatigue '
            'or body growth.'
        ),
        'P16-3F-B1',
        'Working',
        'A101 §103.10',
    ),
    LearningCapabilityV1(
        'L08',
        'Task-to-body and support learning',
        'BodyMap with participating task/source and connection circuitry',
        'Cognitive/interface mechanism',
        (
            'Learn how a represented object/world transformation can be realized through body-relative effectors, targets, '
            'contact, loading and support arrangements.'
        ),
        (
            'During attempts and informative intermediate reach/contact/load/slip evidence. Some adjustments can influence '
            'the next movement before the entire righting or following task finishes.'
        ),
        (
            'Context-specific useful mappings can strengthen and unreliable mappings can revise or differentiate. Emotion may '
            'add significance; it cannot override current protected bodily evidence.'
        ),
        'Learn a task-to-body/support mapping with intermediate feedback while Navigation’s task stays controlled.',
        'P16-3F-B1',
        'Working',
        'A101 §103.11',
    ),
    LearningCapabilityV1(
        'L09',
        'SEC sequence, timing and error adaptation',
        'Sequential/Error Correcting Module',
        'Functional abstraction',
        (
            'Improve short-sequence expectations, timing, calibration and learned corrective assistance in its participating '
            'sensory, cognitive, body or motor domain.'
        ),
        (
            'When relevant local transition evidence or prediction error arrives, including while lower execution continues. '
            'An immediate correction is not automatically a lasting learned adjustment.'
        ),
        (
            'Use mechanism-specific histories and learning conditions; later practice can stabilize or revise calibration. No '
            'molecular cerebellar simulation or universal reward dependence is required.'
        ),
        'Adapt a useful SEC timing/transition relation; compare correction-off separately from SEC-learning-off.',
        'P16-3E',
        'Working',
        'A101 §103.12',
    ),
    LearningCapabilityV1(
        'L10',
        'Detailed motor-skill and automatic-execution learning',
        'Declared lower motor/robotic control provider',
        'Lower-system contract',
        (
            'Represent the externally supplied improvement in detailed coordination or automatic execution inside an '
            'authorized task. These motor programs are not automatically CCA LPs.'
        ),
        (
            'According to the provider’s practice, feedback and reinforcement mechanisms. CCA records relevant competence and '
            'execution consequences rather than imposing its own global F clock on the provider.'
        ),
        (
            'The provider declares retention and changing competence at the interface. Biological motor-unit, spinal or '
            'synaptic adaptation is deferred unless a specific cognitive experiment needs it.'
        ),
        (
            'Specify fixed/adaptive lower competence, timing, feedback and failure behavior. Do not build motor physiology or '
            'call it an LP.'
        ),
        'P16-3E / lower provider',
        'Lower contract',
        'A101 §103.13',
    ),
    LearningCapabilityV1(
        'L11',
        'IP calibration and learned coupling',
        'IP-related participating circuitry and its actual connection owners',
        'Cognitive mechanism',
        (
            'Tune applicability sensitivity, gain, inhibition, persistence, stopping, expected effects and coupling to '
            'learned representations while retaining the inherited organizing core.'
        ),
        (
            'During informative intermediate events and later corresponding consequences. Selected IP participation is one '
            'learning influence, not the exclusive gate for all cortical learning.'
        ),
        (
            'Context-specific calibration and links remain plastic; ordinary forgetting must not erase the inherited core by '
            'accident. Avoid duplicate attribution of one BodyMap/SEC change to a fictional independent IP weight.'
        ),
        (
            'Tune an identifiable IP-related coupling/calibration without erasing the inherited core or double-counting a '
            'BodyMap change.'
        ),
        'P16-3F-B2',
        'Working',
        'A101 §103.14',
    ),
    LearningCapabilityV1(
        'L12',
        'Operation-conditioned consequence learning',
        'Source/operation circuitry producing the PNM, with declared body/SEC contributors',
        'Cognitive mechanism',
        (
            'Improve expected relational unfolding, observation conditions and uncertainty for a selected IP/LP in context. '
            'The PNM representation itself is not a separate durable learner.'
        ),
        (
            'When corresponding intermediate or completion evidence becomes observable and any required focal interpretation '
            'has occurred. Creating, rereading or revising a prediction is not independent confirmation.'
        ),
        (
            'Retain the earlier tested claim while learning changes future predictions. Distinguish actual from imagined '
            'experience, prediction accuracy from desirability, and changed execution from failed prediction.'
        ),
        (
            'Use corresponding evidence to improve a future operation-conditioned projection; preserve the old tested claim '
            'and separate value from accuracy.'
        ),
        'P16-3F-B2',
        'Working',
        'A101 §103.15',
    ),
    LearningCapabilityV1(
        'L13',
        'Learned operation applicability and preference',
        'Primitive access/selection circuitry and relevant learned connections',
        'Cognitive mechanism',
        (
            'Learn which available operation fits a context, how useful its effects are, and when persistence or repetition '
            'is inappropriate. Do not collapse all usefulness into one global reward scalar.'
        ),
        (
            'When informative consequences, reinforcement or task-relevant evidence reach the appropriate participants. Some '
            'signals can arrive before broader task completion; unavailable final outcomes cannot be borrowed.'
        ),
        (
            'Refine contextual preference, cost and limits; uncertainty can justify no change. Emotion/drive influences '
            'modulate use but do not replace Navigation’s focal selection or BodyMap’s constraints.'
        ),
        (
            'Learn context-sensitive preference among genuine applicable competitors; list order and protected veto remain '
            'separate.'
        ),
        'P16-3F-C1',
        'Working',
        'A101 §103.16',
    ),
    LearningCapabilityV1(
        'L14',
        'LP acquisition and refinement',
        'Relevant sensory/association strategy circuitry',
        'Cognitive mechanism; separate design gate',
        (
            'Acquire a new bounded selectable transformation/strategy with applicability, organizing relations and necessary '
            'execution links. An episode, parameter adjustment or memorized action list is not automatically an LP.'
        ),
        (
            'Useful organization can originate during self-generated behavior, observation or permitted composition; '
            'subsequent use/reactivation can refine and stabilize it. No universal training count is specified.'
        ),
        (
            'Validate generalization, context limits, differentiation, forgetting and useful reuse. WI/SEC may assist but are '
            'not a compulsory serial pipeline. The general induction algorithm remains open.'
        ),
        (
            'Acquire a bounded task transformation absent before experience; test held-out applicability, induction-off and '
            'removal of the acquired operation.'
        ),
        'P16-3G after GO-LP-DESIGN',
        'Working',
        'A101 §103.17',
    ),
    LearningCapabilityV1(
        'L15',
        'Learned attentional relevance and accessibility',
        'Source-association and Attention-related relevance circuitry',
        'Cognitive mechanism',
        (
            'Learn which cues/sources deserve rapid access in a context and which repetitive irrelevant sources can receive '
            'less priority. Recognition strength remains different from focal relevance.'
        ),
        (
            'Across informative encounters and their consequences, including outcome-related contributions. A transient '
            'high-priority request is not itself durable attentional learning.'
        ),
        (
            'Learned bias can stabilize or reverse with context and evidence. Emotion supplies significance where connected; '
            'it does not directly choose WNM or scan the entire library.'
        ),
        (
            'Change learned source relevance with recognition fixed; test access/priority among real competitors without '
            'granting direct WNM authority.'
        ),
        'P16-3F-C2',
        'Working',
        'A101 §103.18',
    ),
    LearningCapabilityV1(
        'L16',
        'Habituation and sensitization',
        'Relevant sensory, emotional and response circuitry',
        'Functional abstraction',
        (
            'Learn reduced response to repeatedly inconsequential input or increased sensitivity after significant experience '
            'where those effects alter cognition or behavior.'
        ),
        (
            'Across repeated presentations and after appropriately salient events, with mechanism-specific recovery and '
            'persistence. Do not infer learning from receptor fatigue, transient adaptation or depletion alone.'
        ),
        (
            'Context, interval and changed significance can alter persistence. No universal decay rate is imposed; the same '
            'signal can be familiar yet remain important for safety.'
        ),
        (
            'Specify learned habituation/sensitization with intact detection and interval/context controls. A current sensor '
            'adaptation is not sufficient.'
        ),
        'P16-3I-D1',
        'Contract permitted',
        'A101 §103.19',
    ),
    LearningCapabilityV1(
        'L17',
        'Learned emotional significance',
        'Emotion Module and its actual participating association connections',
        'Cognitive mechanism',
        (
            'Acquire context-sensitive associations with danger, safety, reward, reassurance or other biological '
            'significance. Current emotional response and learned association are distinct.'
        ),
        (
            'When relevant cue/context activity and consequence/teaching evidence meet the local learning conditions, '
            'directly or through a declared delayed pathway. Task completion and a global memory commit are not required.'
        ),
        (
            'Significance can stabilize, generalize, reverse or extinguish contextually. It can be mistaken; affect does not '
            'acquire factual authority. Molecular amygdala circuitry is not simulated.'
        ),
        (
            'Learn cue/context significance and isolate its expression, Attention effect, readiness bias and selective '
            'learning modulation.'
        ),
        'P16-3I-B/C',
        'Working',
        'A101 §103.20',
    ),
    LearningCapabilityV1(
        'L18',
        'Experience–internal-consequence learning',
        'Sensory/ANM, interoceptive/drive and Emotion-related owners',
        'Cognitive mechanism with interoceptive interface',
        (
            'Learn that particular foods, places, contacts or actions predict nourishment, warmth, relief, pain or malaise. '
            'Distinguish individual identity, maternal significance and current location.'
        ),
        (
            'When the relevant internal consequence becomes available. Short-delay eligibility and longer-delay reactivation '
            'are different candidate mechanisms; no one universal timeout handles all such learning.'
        ),
        (
            'Retain context and uncertainty; supported reactivation may permit later updating after immediate traces decay. '
            'Do not use simulator reward or hidden health state as undeclared sensory evidence.'
        ),
        (
            'Specify an admitted internal consequence and delay/context test; promote only with evidence-sensitive recipient '
            'routing and no benchmark reward leakage.'
        ),
        'P16-3I-D2; longer delay via 3J',
        'Contract permitted',
        'A101 §103.21',
    ),
    LearningCapabilityV1(
        'L19',
        'Extinction, safety learning and reversal',
        'Relevant association, Emotion and operation-learning circuitry',
        'Cognitive mechanism',
        (
            'Learn that an expected consequence is absent under supported conditions, differs by context, or has changed. Do '
            'not default to erasing the original association.'
        ),
        (
            'After the expected event’s appropriate observation window or when informative contradictory experience occurs. '
            'Failure to observe because of blackout is not evidence of genuine nonoccurrence.'
        ),
        (
            'New context-dependent learning can compete with earlier organization; selective weakening may also occur. '
            'Reversal and return of an old response need explicit context and access conditions.'
        ),
        'Learn supported contextual omission/reversal; compare missing-data and simple-memory-deletion controls.',
        'P16-3I-D3',
        'Working',
        'A101 §103.22',
    ),
    LearningCapabilityV1(
        'L20',
        'Rapid event and episode binding',
        'WorldIndex with participating cortical references',
        'Cognitive mechanism',
        (
            'Create or strengthen sparse bindings among relevant active configurations/loci, context and short order '
            'relationships. Keep rich content in its owners.'
        ),
        (
            'During significant or useful novel experience, before a final action outcome may be known. Later outcome '
            'information can be associated without pretending the original binding already contained it.'
        ),
        (
            'Recency, significance, competition, reuse and reactivation affect binding strength and accessibility. Emotion '
            'can influence priority without making every arousing event a full-world copy.'
        ),
        (
            'Bind a sparse meaningful conjunction during experience before final outcome; later partial recall must differ '
            'from a strong preseeded direct route.'
        ),
        'P16-3D',
        'Working',
        'A101 §103.23',
    ),
    LearningCapabilityV1(
        'L21',
        'Local stabilization',
        'Each local learning owner',
        'Functional abstraction',
        (
            'Alter the persistence of an already acquired change, preserving useful organization and allowing unsupported '
            'changes to weaken. Early functional change need not wait for stabilization.'
        ),
        (
            'After induction and through subsequent local activity or modulation; it may overlap the originating experience '
            'and continue later. F can schedule due maintenance without defining the biological timescale.'
        ),
        (
            'Use a declared retention/stability rule, not molecular proteins. Stabilization is not guaranteed permanence and '
            'need not be identical across every map/link/calibration.'
        ),
        (
            'Separate an early effective change from its later persistence with matched experience and stabilization-off '
            'controls.'
        ),
        'P16-3J-A',
        'Working',
        'A101 §103.24',
    ),
    LearningCapabilityV1(
        'L22',
        'Replay-supported and systems-level consolidation',
        'WorldIndex and relevant cortical/other participating circuits',
        'Cognitive/memory mechanism with functional state model',
        (
            'Reactivate selected experience to integrate or strengthen useful organization and, where appropriate, improve '
            'direct cortical access relative to rapid indexing.'
        ),
        (
            'During suitable quiet waking or sleep-related processing under a declared state/availability policy. It is not a '
            'mandatory operation at every F boundary or a global lifetime retraining batch.'
        ),
        (
            'Select limited relevant content; distinguish replay from new sensory evidence and from deliberate deep '
            'hypothetical planning. No universal time makes every memory WI-independent.'
        ),
        (
            'Specify a limited quiet/rest reactivation policy and direct-access/retention test; a replay log is not '
            'consolidation.'
        ),
        'P16-3J-B after design review',
        'Contract permitted',
        'A101 §103.25',
    ),
    LearningCapabilityV1(
        'L23',
        'Retrieval-dependent updating and reconsolidation',
        'Reactivated representation and association owners',
        'Cognitive/memory mechanism with functional persistence',
        (
            'Permit retrieved content to be revised by appropriate new information and restabilized when the modeled '
            'conditions make updating relevant. Not every read is a rewrite.'
        ),
        (
            'During and after suitable reactivation with new evidence or discrepancy. Mere retrieval does not automatically '
            'destabilize all memories or restore exact past physiological eligibility.'
        ),
        (
            'Preserve what the new evidence supports, context, uncertainty and later persistence. Internal rehearsal must not '
            'repeatedly become independent external confirmation.'
        ),
        (
            'Specify retrieval-dependent updating with retrieval-only and new-evidence-only controls; no automatic rewrite on '
            'every read.'
        ),
        'P16-3J-C after design review',
        'Contract permitted',
        'A101 §103.26',
    ),
    LearningCapabilityV1(
        'L24',
        'Forgetting and selective weakening',
        'Local representation, connection and accessibility owners',
        'Cognitive/functional mechanism',
        (
            'Reduce unsupported or competing influences and weak candidates; distinguish a less accessible representation '
            'from erased content. Preserve inherited organizing cores appropriately.'
        ),
        (
            'Across relevant experience and elapsed time under owner-specific interference, competition or decay rules. '
            'Scheduler expiry of a diagnostic record is not cognitive forgetting.'
        ),
        (
            'Different strengths and histories can produce different persistence. New evidence may restore access or require '
            'relearning; do not apply one indiscriminate deletion rate to all organization.'
        ),
        (
            'Weaken unsupported organization and distinguish inaccessible from erased content; diagnostic expiry must not '
            'alter memory.'
        ),
        'P16-3F basics; 3J-A',
        'Working',
        'A101 §103.27',
    ),
    LearningCapabilityV1(
        'L25',
        'Regulation of plasticity',
        'Local circuits with declared developmental/modulatory influences',
        'Lower-system contract plus bounded functional modulation',
        (
            'Represent cognitively relevant changes in learning sensitivity, competition and stability from activity history. '
            'Detailed homeostatic plasticity/metaplasticity physiology remains below scope.'
        ),
        (
            'On the local mechanism’s relevant timescale, often using histories longer than one event. It does not require a '
            'favorable task verdict or a universal F commit.'
        ),
        (
            'Declare limits and persistence of the learning-rate/gain or stability effect. This is local regulation, not a '
            'global organism-level homeostasis objective or an additional executive.'
        ),
        (
            'Expose bounded history-sensitive gain/stability and its effect where modeled; keep molecular regulation below '
            'scope and no global homeostasis objective.'
        ),
        'P16-3F / 3I / 3J local limits',
        'Lower contract',
        'A101 §103.28',
    ),
)


def learning_capabilities_v1() -> tuple[LearningCapabilityV1, ...]:
    """Read all 25 immutable contracts; never construct or invoke runtime learners."""
    return _CAPABILITIES


def render_learning_ledger_v1(*, detail: bool = False) -> str:
    """Render actual maturity and retained promotion obligations without simulation."""
    if not isinstance(detail, bool):
        raise TypeError("detail must be Boolean")
    lines = ["P16-1G-C | L01-L25 COVERAGE / MATURITY INVENTORY",
             "Basis: adopted Planning v18 Appendix I; no durable learner is implemented in this profile.",
             "C99 still requires 18 Working demonstrations, 5 Contract permitted rows, and 2 Lower contracts."]
    for card in _CAPABILITIES:
        lines.append(f"{card.capability_id} {card.name} | {card.maturity} | C99: {card.c99_minimum}")
        lines.append(f"  owner: {card.owner}; depth: {card.depth}; promotion: {card.promotion_phase}")
        if detail:
            lines.extend((f"  planned input/change: {card.input_output_contract}", f"  timing/evidence: {card.timing_evidence}",
                          f"  modulation/persistence: {card.modulation_persistence}", f"  future control: {card.promotion_control}",
                          f"  live consumer: {card.live_consumer}", f"  tests: {card.test_destination}"))
    lines.append("Registry inspection is not a Phase-F loop, acquired competence or a new biological module.")
    return "\n".join(lines)
