# v0.9.1 scope decision — proposed, not approved

## Exact proposed declaration

The complete machine-readable proposal is `data/admissions/i2_004_research_scope.proposed.json`. Its exact substantive declaration is:

> Synthetic ship-design records are assumed externally eligible for the represented UR I2.1.2.2 calculation. Use UR I2 Rev.4 (December 2019) for the represented calculation and UR I1 Rev.2 (April 2016) as contextual scope evidence for this experiment. These are explicit experimental edition choices, not a finding that those editions legally govern any vessel or construction date. The generated constraints check the represented requirement within this population. They do not independently certify Polar Class qualification, real-vessel compliance, or construction-date eligibility. Regulatory applicability text remains visible. Conditions within the represented requirement, query correctness and effective activation remain separate obligations.

The record class is `https://w3id.org/nltl/vocab#ship`. The common boundary is `COMPLETE_CLASS_POPULATION_PER_INPUT`: each independent validation invocation must bind its entire class population unambiguously to separately reviewed input nodes/hash, including RDFS-inferred instances. RDF membership identifies the population; it does not prove regulatory eligibility.

`approval.status` is PROPOSED; approved_by/reference and caller declarant/reference are null. No user provenance or approval was manufactured. The only outstanding substantive decision is approval (or correction) of this experimental assumption and its two selected editions. Actual approval-message provenance can be recorded only after approval. No separate claim about real-vessel dates/qualifications is requested. Approval of scope alone is not permission to dispatch models.

## Leakage finding and minimal correction

v0.9.0 required `focus_set.nodes` and copied the full declaration into generation, review/retry and repair. It did not read evaluation files automatically, but satisfying that interface with evaluation admission records would expose fixture identities and couple generic generation to external cases. This was a design leak risk, not evidence of a dispatched v0.9 model leak (no v0.9 model run occurred).

v0.9.1 removes the nodes field from the common interface and rejects legacy node-bearing declarations and evaluation bindings there. Only the common source/schema/research-scope declaration reaches models. It is identical for Single-shot and NLTL. Full latest candidate/hash integrity remains enforced; review/repair carries the same common declaration. No fixture/case IDs, labels or counterpart records are loaded by this route. Individual targetNode scopes are unsupported in this reusable interface; a scoped class target is allowed only behind the separate input guard. No shape is automatically activated or edited.

Independent evaluation uses separate `evaluation/specifications/admission_scope_i2_004/*.admission.json` bindings: exact input byte SHA-256, complete admitted node list, shared scope ID/definition hash, and reviewed construction provenance. These files are denied by GenerationProject and absent from all production configs/resources. The independent evaluator takes the common declaration as `research_scope` and case bindings under `admissions`; it never sends them back to review/repair. Missing/ambiguous binding, unapproved scope, mismatched bytes/scope or additional inferred nodes remains unresolved/NO_VERDICT. The definition hash excludes approval attribution, so the same reviewed bindings remain valid after a real approval is recorded without changing scope/editions. Scope meaning changes invalidate them.

This is a narrow correction to the existing admission module and evaluator, not another framework. No new compliance witnesses, regulatory solution profile, per-requirement gate, permission mechanism or tracker change was added. Generic synthetic software controls exercise interfaces only.

## I2-004 construction-provenance review

See `evaluation/provenance/v091/i2_004_scope_review.json` for every input and evidence hash. The original six files match the frozen Batch G fixture lock and retained RDF bytes. Their original manifest declares D_REGULATION_SYNTHETIC, source SRC-IACS-I2-R4 and clause I2.1.2.2; the retained constructor explicitly creates design-record graphs. Each of the three counterparts matches its retained derivation hash and keeps the same synthetic record identity; no counterpart outcome was used for admission. Every input has one unambiguous complete class-population node, including RDFS inference. No source constructor or compliance oracle was executed for this review.

All nine are **supported conditional on scope approval**, not yet admitted by an approved declaration. This relies on synthetic construction and the proposed external experimental eligibility assumption, not expected labels, values, generated shapes, scores or a claim of actual vessel eligibility. No input currently has an additional unsupported construction/admission blocker; any unmatched or undocumented input would stay unresolved. Historical 37-case and other selections, labels, scores and exclusions are untouched. The prior broad v0.9 inventory remains historical; it did not have this construction-lineage review.

Exact retained originals: I2-004-G-P01, I2-004-G-P02, I2-004-G-P03, I2-004-G-F01, I2-004-G-F02, I2-004-G-F03. Exact existing counterparts: I2-004-G-F01.repaired.ttl, I2-004-G-F02.repaired.ttl, I2-004-G-F03.repaired.ttl. These identifiers occur only in evaluation/audit materials, never the common declaration or model requests.

UR I2.1.1 explicitly references UR I1; retained I2/I1 editions are proposed above. I1's references to UR I3 concern qualification and PR29 concerns construction-date interpretation. This experimental declaration does not independently establish either eligibility claim. No unavailable transitive text was invented or globally waived: if full-code source review identifies a missing provision material to the represented calculation, it remains unresolved under existing retrieval limits. Resolving admission cannot establish query correctness or accept an inactive shape.

## Prepared bounded operational check

`configs/v091_bounded_live_check.json` preserves the existing two-candidate I2-004 check, bounded reviews/retrieval, one reviewer-format retry per review, early acceptance, no seed/regeneration or capability probe. It references the proposed common scope, so preflight blocks today without reading credentials. After actual approval and provenance recording, the admission/input readiness blocker is resolved and this check is operationally prepared, subject to normal frozen-input/provider preflight and a separate dispatch instruction. No model run, pilot rerun or evaluation-score recalculation has been performed. Context/version changes mean later results must be labelled v0.9.1.

```sh
PYTHONDONTWRITEBYTECODE=1 ../NLTLv2-env/bin/python -m nltlv2 --project . check
PYTHONDONTWRITEBYTECODE=1 ../NLTLv2-env/bin/python -m nltlv2 --project . smoke
# Expected exit 2 until actual approval/provenance is recorded:
PYTHONDONTWRITEBYTECODE=1 ../NLTLv2-env/bin/python -m nltlv2 --project . check --requirement I2-004 --admission data/admissions/i2_004_research_scope.proposed.json
```

Limits: assertions/approval provenance are recorded, not cryptographically authenticated or legally certified. Only the generic declared-class boundary is supported. Complete-population guards and input hashes verify identity, not regulatory truth. Review/probes do not prove all arithmetic or logic. The trusted application path capability is not a hostile-code OS sandbox.
