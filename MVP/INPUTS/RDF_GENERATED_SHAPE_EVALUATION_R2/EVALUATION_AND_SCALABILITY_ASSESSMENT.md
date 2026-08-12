# R2 generated-shape evaluation and scalability assessment

Date: 2026-08-12  
Vocabulary lock: `VOCAB-LOCK-2026-08-12-R2`  
Evaluation ID: `GENERATED-SHAPES-R2-IMO-057-IMO-088`

## Outcome

The frozen generated SHACL for IMO-057 and IMO-088 was executed against ten
hash-bound, requirement-level RDF variants. All ten executions completed and
all ten actual conformity outcomes matched the independently declared expected
outcomes. There were no expected-outcome mismatches.

| Requirement | Passing variants | Failing variants | Expected matches |
|---|---:|---:|---:|
| IMO-057 | 1 | 3 | 4/4 |
| IMO-088 | 3 | 3 | 6/6 |
| Total | 4 | 6 | 10/10 |

The evaluation covers the following high-value boundaries:

- IMO-057: every explicit pump target in one conforming graph, `0 degC` as a
  strict failure, a non-canonical temperature unit as a failure, and missing
  pump-to-compartment evidence as a failure.
- IMO-088: the 24-hour-daylight exception, the exact two-searchlight and
  360-degree passing thresholds, the approved-alternative branch, and failures
  at one searchlight, 359 degrees, and an unapproved alternative.

## Repairs that proved effective

### IMO-057 relationship model

The R1 string-valued `containingCompartment` model could not express the
required path from a pump to a compartment and then to the compartment's
maintained temperature. R2 replaced that active modelling route with a
`hasContainingCompartment` object property, a `compartment` class, and explicit
classes for emergency fire, water-mist, and water-spray pumps. The generated
shape now checks the relationship, node type, quantity value, strict `> 0`
comparison, decimal datatype, and Celsius unit.

This is a scalable repair pattern: cross-component regulations should use
object-property paths and typed nodes rather than encoding related entities as
strings. The discovery of each missing relationship is not automatically
scalable, so dependency preflight remains necessary before official runs.

### IMO-088 controlled-value retrieval

The pipeline now retrieves controlled ontology individuals through the range of
the supplied property. This allowed the generator to use the locked
`evidenceStateApproved` individual without invoking the optional vocabulary
matcher or inventing a status URI.

This fix is generic and scalable to other document, certificate, approval, and
evidence-state properties that use the same controlled range.

## Evaluator hardening completed

- Every case now binds the exact generated shape and RDF input by SHA-256.
- A mismatched hash blocks SHACL execution rather than silently evaluating a
  changed file.
- The evaluator verifies the locked R2 vocabulary artifacts and supplies the
  locked ontology to pySHACL for RDFS inference.
- Complete reports remain in JSONL and CSV; the workbook uses concise messages
  so a nested SHACL report cannot produce unreadably tall rows.
- The workbook summary was corrected to count text-normalized boolean results.
- The evaluator remains completely separate from generation and makes no LLM or
  API calls.

With the locked ontology enabled, the ten tests averaged approximately 248 ms
per RDF/shape pair on this machine. Evaluation itself is therefore not the
current scaling bottleneck.

## Remaining limitations and risks

### Calibration evidence, not final benchmark performance

These RDF fixtures were authored after inspecting the generated shapes. That is
appropriate for calibration and regression testing, but it is not a blind or
independent estimate of model generalization. Official benchmark fixtures
should be frozen before the evaluated generations and kept unavailable to the
generator and semantic validator.

### Small and non-representative sample

Two successful requirements do not establish performance across all 240
generation-eligible requirements. The next calibration sample should be
stratified across direct cardinalities, calculations, temporal/history rules,
cross-component relations, document/certificate evidence, physical-test
evidence, exceptions, and SPARQL-dependent constraints.

### Correlated LLM review

The generator and semantic validator currently use the same GPT-5.6 Sol model.
This maximizes capability but can produce correlated interpretation errors.
Deterministic gates and hidden RDF tests reduce this risk but do not eliminate
it. Multiple independent runs and blinded executable tests remain essential.

### Regulatory operationalizations must remain explicit

- IMO-057's exact text says compartments must be maintained above freezing.
  The benchmark operationalizes this as a static recorded quantity greater
  than `0 degC`. This is a defensible benchmark convention, but a static RDF
  value does not prove operational temperature history.
- IMO-088's exact text permits “other means to visually detect ice.” The
  benchmark's normalized requirement represents that branch with an approved
  evidence state. Approval is an engineering evidence convention, not wording
  explicitly present in the quoted sentence, and must be documented as such.

### Target-population assumption

The IMO-088 shape targets `nltl:ship`. This is correct only when the evaluated
dataset is already scoped to ships to which the Polar Code requirement applies.
Mixed-fleet graphs would need an explicit applicability profile or preselected
focus nodes to avoid applying the rule too broadly.

### Human-readable SHACL messages

Nested SHACL constraints can report a broad outer message before the precise
inner violation. The raw report remains technically correct, and the tracker
now presents the most specific message. Future generation prompts should still
ask for distinct messages at nested levels to improve diagnostics.

### Generation remains the costly stage

The five accepted pilot requirements used six semantic attempts, twelve LLM
calls, 53,489 input tokens, 9,966 output tokens, and about 138 seconds of total
API-call time. Sequential generation is acceptable for calibration, but a full
multi-run experiment needs an explicit run budget, resumable queues, and a
central rate limiter before introducing parallel workers.

## Scale decision

The architecture is ready for a larger **calibration batch**, not yet for the
final 240-requirement experiment.

Proceed with a stratified calibration batch of roughly 20-30 requirements. For
each requirement, freeze a small hidden suite containing at least one valid
graph, one missing-evidence graph, and boundary or alternative-branch graphs
appropriate to the rule. Record vocabulary gaps during calibration, revise and
relock once, rerun the whole calibration set, and only then freeze the
vocabulary, prompts, model configuration, fixtures, and seeds/run policy for the
official multi-run experiment.

