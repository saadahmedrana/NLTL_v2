# R6 Terra Full-Sweep Offline Failure Audit

## Executive result

This audit diagnoses the immutable 238-requirement R6 Terra development sweep. It made **zero API/LLM calls** and did not modify R6, prompts, contracts, or pipeline logic.

- Accepted baseline: **177/238 (74.4%)**
- Failures audited: **61/61**
- Of 31 `TERM_RESOLUTION_UNRESOLVED` cases, **13 are genuinely impossible to represent in locked R6**: six missing concepts/controlled values and seven missing structural paths. The other **18 are not vocabulary absence**.
- Exclusive root causes: 7 genuine schema gaps; 11 modelling/dependency defects; 2 retrieval failures; 22 ordinary generator failures; 9 validator/control failures; 5 syntax/code-generation failures; 5 evaluator limitations; 0 unsupported.
- Theoretically compiler-preventable failures: **31** (assuming correct semantic extraction).
- Hybrid compiler hypothesis: **MODERATE support**.
- Decision: **R7 is needed**, but only for the 20 source-grounded schema/modelling/retrieval corrections listed below.

## Audit method and evidence boundary

For every failed run, the audit compared the authoritative source excerpt and normalized requirement in its locked context pack, its COMPLETE dependency contract, supplied R6 terms and owners, all recorded generation/validation/matcher/static artifacts, and terminal feedback. Model feedback alone was never treated as source evidence. Representative figure/table-dependent source pages were also rendered and visually checked. No source wording was fabricated.

## Part 1 — all 31 term-resolution failures

| ID | Primary classification | Source meaning / required representation | R6 result | Confidence | R7 |
|---|---|---|---|---|---|
| I2-009 | TRUE_SCHEMA_GAP | The scantling equations require ice-load parameters to be determined independently of hull shape. Required: A determination-method/provenance assertion that the ice-load parameters were obtained independently of hull shape. | Missing: No canonical R6 term records the required hull-shape-independent determination method. | LOW | Yes |
| I2-019 | SOURCE_REQUIRES_STRUCTURAL_EXTENSION | Where a member spans more than one hull area, the largest applicable hull-area factor must govern. Required: A member-to-spanned-hull-area association with each area's factor, followed by maximum selection. | Missing: R6 has the individual terms but no canonical association that binds each factor to each spanned area/member. | HIGH | Yes |
| I2-024 | DEPENDENCY_CONTEXT_DEFECT | Obtain the design value by linear interpolation between tabulated points. Required: Interpolation points must bind coordinates/inputs to the corresponding result value. | Exists: interpolationPointCoordinate + interpolationPointResult | HIGH | Yes |
| I2-029 | VALIDATOR_REQUESTED_UNSUPPORTED_SEMANTICS | Check the specified member property using the requirement's supplied operands and comparison. Required: A direct member-targeted calculation/comparison; the source does not require a separate calculation-case-to-member link. | Exists: required target owner + supplied operand/result terms | HIGH | No |
| I2-037 | SOURCE_REQUIRES_STRUCTURAL_EXTENSION | Each relevant structural member must withstand the applicable ice-load patch/design load. Required: A member-to-load-patch/design-case association that pairs demand with member capacity. | Missing: R6 lacks a canonical relationship pairing the particular member with its governing ice-load patch/design case. | HIGH | Yes |
| I2-047 | MODEL_TERM_REASONING_FAILURE | Apply the thickness requirement to the relevant hull structure/component. Required: Traverse the existing ship/component or directly target the authoritative structure owner and constrain thickness. | Exists: hasComponent -> hullStructure; existing thickness terms | HIGH | No |
| I2-061 | SOURCE_REQUIRES_STRUCTURAL_EXTENSION | The calculation cases must cover the shell and local-frame requirements in I2.4, I2.6 and I2.7. Required: A calculation-case scope relation or controlled scope identifying the covered rule sections/components. | Missing: No canonical R6 path states which required structural-rule scope a calculation case covers. | HIGH | Yes |
| I2-064 | TRUE_SCHEMA_GAP | The source explicitly requires use of a linear calculation method. Required: A controlled calculation-method value for the linear method. | Missing: The selector property exists, but its required linear-method controlled value is absent. | HIGH | Yes |
| I2-066 | SOURCE_REQUIRES_STRUCTURAL_EXTENSION | The weld requirement applies to welds in ice-strengthened areas. Required: A weld node/path scoped to the ice-strengthened area in which that weld occurs. | Missing: R6 cannot canonically connect an individual weld to the applicable ice-strengthened area. | HIGH | Yes |
| IMO-001 | TRUE_SCHEMA_GAP | The design condition must cover at least medium first-year ice, including old-ice inclusions where stated. Required: Controlled ice-condition/severity values capable of expressing the regulatory minimum. | Missing: R6 lacks the controlled medium-first-year/old-inclusion condition representation. | HIGH | Yes |
| IMO-003 | TRUE_SCHEMA_GAP | Category C is for open water or ice conditions less severe than Categories A and B. Required: Controlled open-water/ice-severity representation with an ordering or explicit less-severe relation. | Missing: R6 has category concepts but no controlled severity ordering sufficient for this branch. | HIGH | Yes |
| IMO-052 | MODEL_TERM_REASONING_FAILURE | Required access items must have an ice/snow removal or prevention means. Required: ship -> hasRequiredAccessItem -> item -> hasIceOrSnowRemovalOrPreventionMeans -> means. | Exists: hasRequiredAccessItem + hasIceOrSnowRemovalOrPreventionMeans | HIGH | No |
| IMO-064 | VALIDATOR_REQUESTED_UNSUPPORTED_SEMANTICS | Thermal protection must be adequate for the relevant environmental and operational conditions. Required: The benchmark's existing assigned-thermal-protection/status evidence abstraction. | Exists: assignedThermalProtection and supplied adequacy/status evidence | MEDIUM | No |
| IMO-097 | MODEL_TERM_REASONING_FAILURE | The required rescue/lifeboat devices and their associated provisions must be represented together. Required: The supplied rescue/lifeboat-to-device relationship paths. | Exists: retrieved rescue/lifeboat classes and device relationships | HIGH | No |
| IMO-118 | VALIDATOR_REQUESTED_UNSUPPORTED_SEMANTICS | The branch applies to Category A/B ships or passenger ships. Required: rdf:type nltl:passengerShip as the authoritative passenger selector, combined with category branches. | Exists: rdf:type passengerShip; shipCategory | HIGH | No |
| TRF-006 | TRUE_SCHEMA_GAP | Application of the alternative engine-output provisions depends on an owner request/election. Required: Evidence that the ship owner requested/elected the applicable rule option/edition. | Missing: No R6 term captures the source-required owner request/election. | HIGH | Yes |
| TRF-013 | EXISTING_TERM_NOT_RETRIEVED | Determine the maximum and minimum ice-class draught limits. Required: The existing upper/lower maximum/minimum ice-class draught quantities. | Exists: maximumIceClassDraught + minimumIceClassDraught (and upper/lower variants already used by TRF-014) | HIGH | Yes |
| TRF-014 | SOURCE_REQUIRES_STRUCTURAL_EXTENSION | The certificate must record the six specified draught values. Required: certificate/document -> recorded draught-value entries, including position and upper/lower distinction. | Missing: R6 has document and draught terms but no canonical content/evidence relationship binding the six values to the certificate. | HIGH | Yes |
| TRF-016 | MODEL_TERM_REASONING_FAILURE | Use displacement at the greatest applicable ice waterline/draught. Required: Select the greatest waterline by the supplied upper-waterline relation and compare its displacement. | Exists: hasUpperIceWaterline + waterlineDisplacement | HIGH | No |
| TRF-020 | VALIDATOR_REQUESTED_UNSUPPORTED_SEMANTICS | Calculate and compare the upper/lower draught-specific ship quantities. Required: Ship-owned upper/lower draught quantities and their supplied formulas/comparisons. | Exists: supplied upper/lower draught operand and result terms | MEDIUM | No |
| TRF-031 | MODEL_TERM_REASONING_FAILURE | Apply the von Mises yield criterion. Required: Use the supplied canonical criterion term as the requirement's criterion representation. | Exists: vonMisesYieldCriterion | HIGH | No |
| TRF-047 | MODEL_TERM_REASONING_FAILURE | The lower end and strengthened part of the main frame must satisfy the support/strength arrangement. Required: The supplied lower-end, strengthened-part, support and strength paths. | Exists: mainFrameBelowIceBeltStrengthened and retrieved support/part relationships | HIGH | No |
| TRF-050 | SOURCE_REQUIRES_STRUCTURAL_EXTENSION | The frame-to-shell attachment itself must satisfy the stated arrangement. Required: A frame-shell attachment node/reified relationship that can own attachment properties. | Missing: R6 has relationship predicates but no attachment entity/class able to own the required attachment evidence. | HIGH | Yes |
| TRF-070 | VALIDATOR_REQUESTED_UNSUPPORTED_SEMANTICS | The thruster body must have adequate local strength for the stated design conditions. Required: Existing design-condition demand/capacity evidence or the supplied local-strength assertion. | Exists: thrusterBodyLocalStrength and supplied design-condition load/capacity terms | MEDIUM | No |
| TRF-076 | MODEL_TERM_REASONING_FAILURE | Represent the required propeller blade load cases, including reversal and propeller-type conditions. Required: propeller -> hasPropellerBladeLoadCase -> case with number/reversal/type selectors. | Exists: hasPropellerBladeLoadCase + loadCaseNumber + reversal + propeller type | HIGH | No |
| TRF-102 | EXISTING_TERM_NOT_RETRIEVED | The source formula uses Z, the number of propeller blades, as an operand. Required: Propeller blade count as the denominator/input Z. | Exists: propellerBladeCount | HIGH | Yes |
| TRF-127 | TRUE_SCHEMA_GAP | Additional-purpose air-receiver demand must be added to the starting-air baseline capacity. Required: The starting-air baseline capacity, separate from total capacity and additional-purpose demand. | Missing: R6 lacks the distinct starting-air baseline capacity needed by the stated sum. | LOW | Yes |
| TRF-128 | VALIDATOR_REQUESTED_UNSUPPORTED_SEMANTICS | The compressor must charge the receivers within the stated time. Required: The directly observed/calculated compressor charge-time outcome. | Exists: compressorChargeTime | HIGH | No |
| TRF-129 | MODEL_TERM_REASONING_FAILURE | Cooling-water supply must be secured while navigating in ice. Required: Boolean implication: navigatingInIce true implies coolingWaterSupplySecured true. | Exists: navigatingInIce + coolingWaterSupplySecured | HIGH | No |
| TRF-130 | SOURCE_REQUIRES_STRUCTURAL_EXTENSION | Provide at least one inlet chest; two smaller chests may be accepted as an alternative, with properties assessed per chest. Required: ship -> hasComponent -> inletChest, per-chest ownership, and one/two-chest cardinality alternative. | Missing: Current chest properties are ship-owned and R6 lacks a complete per-inlet-chest ownership/count model. | HIGH | Yes |
| TRF-131 | MODEL_TERM_REASONING_FAILURE | A ballast arrangement/reserve cannot substitute for the required inlet chest. Required: Use the existing inletChest component and ballast arrangement/status terms to prohibit substitution. | Exists: hasComponent -> inletChest plus ballast arrangement/status terms | HIGH | No |

The exact terminal feedback, full source excerpt, clause/page, existing/missing canonical representation, and recommended action are preserved in the CSV and JSON.

## Part 2 — all 19 max-attempt failures

| ID | Primary cause | Could final repair be implemented in R6? | Finding |
|---|---|---|---|
| I2-001 | OWNER_PATH_REASONING | Yes | The final target was not restricted to nltl:ship even though the target owner and date comparison were supplied. |
| I2-011 | BRANCH_APPLICABILITY_REASONING | Yes | Terra failed to preserve the exact applicability branch/selector semantics after three repairs. |
| I2-018 | FORMULA_REASONING | Yes | All operands and comparison policy were supplied; the generated arithmetic/direction remained wrong. |
| I2-030 | FORMULA_REASONING | Yes | The derived attached-plate-flange applicability expression and operands were present in R6, but Terra did not encode the final formula correctly. |
| I2-031 | BRANCH_APPLICABILITY_REASONING | Yes | The corrected per-member plasticStrength path existed; Terra failed to keep the branch and comparison owner aligned. |
| I2-041 | EVALUATOR_FUNCTION_LIMITATION | Yes | The requirement needs a fractional-power/square-root calculation that the current deterministic expression support cannot compile/validate reliably. |
| I2-050 | EVALUATOR_FUNCTION_LIMITATION | Yes | The supplied formula is representable in R6, but evaluator-supported math is insufficient for its exponent/root form. |
| I2-054 | EVALUATOR_FUNCTION_LIMITATION | Yes | The direct expected-result math needs unsupported root/fractional-exponent capability rather than new vocabulary. |
| IMO-002 | CARDINALITY/DATATYPE_REASONING | Yes | Terra inserted or retained a cardinality/datatype restriction not justified by the contract. |
| IMO26-012 | CARDINALITY/DATATYPE_REASONING | Yes | The final candidate narrowed cardinality/datatype beyond the explicit policy despite supplied terms. |
| TRF-009 | CARDINALITY/DATATYPE_REASONING | Yes | The candidate added unsupported occurrence/datatype restrictions rather than only the source requirement. |
| TRF-049 | OWNER_PATH_REASONING | Yes | The authoritative component/member path existed, but the candidate constrained the wrong owner/path. |
| TRF-051 | EVALUATOR_FUNCTION_LIMITATION | Yes | The source formula is semantically modelled, but its math form exceeds deterministic evaluator support. |
| TRF-060 | EVALUATOR_FUNCTION_LIMITATION | Yes | The lookup formula/relationship terms are present; unsupported math/expression handling prevented stable completion. |
| TRF-078 | TABLE_LOOKUP_REASONING | Yes | The complete table model existed, but Terra failed to encode lookup selectors/result linkage after three attempts. |
| TRF-083 | CARDINALITY/DATATYPE_REASONING | Yes | The candidate retained unsupported cardinality or datatype narrowing despite explicit contract policy. |
| TRF-085 | TABLE_LOOKUP_REASONING | Yes | The supplied lookup structure was not faithfully preserved in the final candidate. |
| TRF-088 | CARDINALITY/DATATYPE_REASONING | Yes | The source-grounded value constraint was encumbered by unsupported cardinality/datatype restrictions. |
| TRF-133 | TRUE_SCHEMA_GAP | No | The source figure requires the warning-triangle upper edge to be vertically above the ICE mark and includes a timber-reference applicability alternative; neither relation/selector is represented in R6. |

Eighteen of nineteen final repairs were implementable without ontology change. `TRF-133` is the exception and needs a source-grounded structural/applicability addition.

## Part 3 — validator-response failures

| ID | Terminal detector | Genuine reversal in history | Root cause |
|---|---|---|---|
| I2-017 | False-positive | No | False-positive contradiction: polarity/term overlap made compatible formula-preservation instructions appear reversed. |
| IMO-037 | False-positive | No | The residual stability factor is modelled as ship-owned, but the source requires s_i = 1 for each loading condition; the case-to-factor path is absent. |
| TRF-012 | False-positive | No | False-positive contradiction: the control layer treated a compatible refinement as a reversal. |
| TRF-025 | False-positive | No | False-positive contradiction caused by lexical polarity across preserved and prohibited clauses. |
| TRF-112 | False-positive | Yes, explicit | The validator explicitly reversed itself, but the deeper issue is a contract that invents an unstated formula; the source only requires combined-load no-yield evidence and safety factors >= 1. |
| TRF-123 | False-positive | Yes, explicit | The validator explicitly reversed itself; the COMPLETE contract incorrectly narrows the population through hasPropellerShaftLineComponent although the source covers all occasional-force-transmitting components except the blade. |

Counts: **0 true terminal contradiction detections**, **6 false-positive detections**, **2 genuine explicit reversals in the recorded history**, and **2 validator-instability cases**. The remaining control defect is global: superseded pre-reversal instructions remain in the comparison set, and lexical polarity can make a compatible refinement look contradictory.

## Part 4 — syntax-repair failures

| ID | Exact construct/failure mechanism |
|---|---|
| I2-015 | Bare SQRT and fractional-exponent expressions remained unsupported; repairs moved BIND/FILTER placement but retained the unsupported math. |
| I2-022 | Repairs moved the expression from BIND to FILTER and varied SQRT spelling, but the parser/evaluator still does not support the root construct. |
| I2-023 | Nested IF branches retained unsupported square-root expressions; moving BIND to FILTER did not address the root cause. |
| TRF-026 | The C2 expression retained SQRT/fractional-power syntax across repairs; punctuation changes did not replace it with a supported construct. |
| TRF-041 | Repairs tried SQRT, '** 0.5', and '^ 0.5'; none is accepted by the current SPARQL/parser capability. |

All five routes received the correct numbered parser excerpt and used the separate three-retry syntax budget. All five cluster around unsupported square-root/fractional-power expressions. BIND/FILTER placement was a parser symptom; there was no nested-SELECT, aggregation, or unbounded-join cluster in this group.

## Part 5 — formal-pattern scalability

Pattern assignment is a reproducible heuristic over locked `encodingPattern`, normalized/source text, and dependency-contract fields; it does not replace human semantic classification.

| Formal pattern | Eligible | Accepted | Rate | TERM | MAX | Validator | Syntax | Compiler-preventable failures |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| aggregation/max/min | 3 | 2 | 66.67% | 0 | 1 | 0 | 0 | 1 |
| boolean implication | 1 | 1 | 100.0% | 0 | 0 | 0 | 0 | 0 |
| cardinality | 10 | 8 | 80.0% | 1 | 1 | 0 | 0 | 2 |
| complex multi-branch formula | 6 | 5 | 83.33% | 1 | 0 | 0 | 0 | 0 |
| conditional applicability | 56 | 43 | 76.79% | 10 | 3 | 0 | 0 | 3 |
| controlled-value membership | 9 | 6 | 66.67% | 2 | 1 | 0 | 0 | 1 |
| cross-owner path | 6 | 4 | 66.67% | 1 | 1 | 0 | 0 | 1 |
| direct comparison | 17 | 17 | 100.0% | 0 | 0 | 0 | 0 | 0 |
| direct presence | 15 | 11 | 73.33% | 3 | 0 | 1 | 0 | 2 |
| document/evidence requirement | 18 | 18 | 100.0% | 0 | 0 | 0 | 0 | 0 |
| existential relationship constraint | 6 | 5 | 83.33% | 1 | 0 | 0 | 0 | 1 |
| interpolation | 4 | 1 | 25.0% | 1 | 2 | 0 | 0 | 2 |
| numeric threshold | 10 | 10 | 100.0% | 0 | 0 | 0 | 0 | 0 |
| piecewise formula | 1 | 1 | 100.0% | 0 | 0 | 0 | 0 | 0 |
| simple arithmetic formula | 53 | 32 | 60.38% | 8 | 4 | 4 | 5 | 11 |
| table lookup | 19 | 11 | 57.89% | 2 | 6 | 0 | 0 | 7 |
| universal per-component constraint | 4 | 2 | 50.0% | 1 | 0 | 1 | 0 | 0 |

The data give **MODERATE**, not strong, support for a hybrid compiler. Deterministic templates could prevent malformed syntax, unsupported cardinality/datatype insertion, standard boolean implication/comparison/path mistakes, and supported formula-template errors. They cannot repair wrong source interpretation, wrong applicability or branch meaning, wrong term selection, genuinely absent concepts, or unusual formula semantics.

## Part 6 — regulatory category

| Category | Eligible | Accepted | Rate | Attempts 1/2/3 | TERM | MAX | Validator | Syntax |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Static | 151 | 123 | 81.46% | 82/42/27 | 19 | 8 | 1 | 0 |
| Static Calculation | 87 | 54 | 62.07% | 35/24/25 | 12 | 11 | 5 | 5 |

Only `Static` and `Static Calculation` requirements are generation-eligible in this 238-case sweep. Dynamic, Complex and Physical Test requirements therefore have no eligible denominator here.

## Part 7 — smallest justified R7 corrections

| Requirement | Correction type | Smallest source-grounded correction |
|---|---|---|
| I2-009 | vocabulary addition | Add hull-shape-independent load-parameter determination method/provenance evidence. |
| I2-019 | relationship/path addition | Associate a member with every spanned hull area and its factor so the governing maximum can be selected. |
| I2-024 | dependency-contract correction | Retrieve the existing interpolationPointCoordinate/interpolationPointResult structure. |
| I2-037 | relationship/path addition | Pair each member with its governing ice-load patch/design case and capacity check. |
| I2-061 | relationship/path addition | Represent calculation-case coverage of the required shell/local-frame rule scopes. |
| I2-064 | controlled-value addition | Add the linear calculation method value under calculationMethod. |
| I2-066 | relationship/path addition | Scope each weld to its ice-strengthened area. |
| IMO-001 | controlled-value addition | Add the required medium first-year/old-inclusion ice-condition values. |
| IMO-003 | controlled-value addition | Add open-water/less-severe ice-condition representation and ordering. |
| IMO-037 | owner/domain correction | Bind residualStabilityFactorSI to each loading condition through a canonical case path. |
| TRF-006 | vocabulary addition | Add ship-owner request/election evidence for the applicable rule option. |
| TRF-013 | dependency-contract correction | Retrieve existing maximum/minimum ice-class draught terms. |
| TRF-014 | relationship/path addition | Bind the six draught entries to the certificate/document content. |
| TRF-050 | relationship/path addition | Add a reified frame-shell attachment structure able to own attachment evidence. |
| TRF-102 | dependency-contract correction | Retrieve existing propellerBladeCount as formula operand Z. |
| TRF-112 | dependency-contract correction | Remove the unstated formula obligation; keep no-yield and safety-factor evidence. |
| TRF-123 | dependency-contract correction | Use occasionalForceCaseAssessedComponent; remove the unrelated shaft-line narrowing. |
| TRF-127 | vocabulary addition | Add the starting-air baseline capacity or an approved semantically equivalent evidence representation. |
| TRF-130 | owner/domain correction | Model ship-to-inlet-chest cardinality and make chest properties per-chest owned. |
| TRF-133 | relationship/path addition | Add vertical-above ICE-mark relation and timber-reference applicability selector. |

No new term is proposed where an existing term/path suffices. `I2-009` and `TRF-127` remain LOW-confidence representation choices and require human review before R7 implementation.

## Exact active artifacts that a later R7 would touch

- `BENCHMARK_VOCABULARY/FINAL_LOCK_R6/registry/term_registry.json` and `.csv` only for confirmed vocabulary/owner/value additions.
- `BENCHMARK_VOCABULARY/FINAL_LOCK_R6/ontology/nltl_benchmark_vocabulary.ttl` and `.rdf` only for confirmed ontology/path/domain changes.
- `BENCHMARK_VOCABULARY/FINAL_LOCK_R6/requirement_term_index.json` for the confirmed dependency/retrieval corrections.
- The R6 workbook and lock/hash manifests would be copied/promoted to a new R7 identity, never overwritten.

This report is diagnostic only. No R7 artifacts were created.
