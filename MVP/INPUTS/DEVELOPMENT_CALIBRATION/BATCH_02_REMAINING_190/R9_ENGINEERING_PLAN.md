# R9 engineering plan

## Objective

Create a development vocabulary and context model in which every generation-eligible requirement can be expressed using verified canonical terms, owners, node paths, datatypes, units, controlled values, and semantic metadata. R9 is a development revision, not a final experimental lock.

R8.1 remains preserved. No prior accepted shape will be relabelled as an R9 result.

## Evidence baseline

- Batch 02 queue: 190/190 completed.
- Accepted: 96.
- Term resolution unresolved: 79.
- Maximum attempts reached: 15.
- Failed cases requiring classification: 94.
- Saved event logs, prompts, responses, validation records, and accepted shapes are the evidence source. Terminal output is not required.

## Work packages

### 1. Failure reconstruction and classification

For every unsuccessful requirement, record:

- final status and attempt count;
- indexed terms and expanded context terms;
- generator and validator feedback by iteration;
- matcher activation, candidates, and decision;
- deterministic validation errors;
- missing concept or structural capability;
- whether the root cause is vocabulary, retrieval/indexing, modelling, metadata, generator logic, or benchmark suitability.

Multi-label root-cause categories:

1. missing explicit formula operand;
2. missing formula result property;
3. missing applicability or branch selector;
4. string used where a controlled value is required;
5. string used where a numeric quantity is required;
6. missing object relationship or inventory path;
7. missing case, assignment, observation, calculation, table-lookup, document, approval, or physical-evidence node;
8. incorrect owner/domain/range;
9. missing or incompatible datatype, unit, or quantity kind;
10. incomplete requirement-term index;
11. missing semantic obligation, exclusivity, comparison, boundary, or table rule metadata;
12. generator-only SHACL/SPARQL logic error;
13. requirement too compound, ambiguous, non-deterministic, or unsuitable as one active benchmark case.

### 2. Global 313-requirement dependency audit

The same dependency template will be applied to all 313 requirements, not only the 94 failures. Each requirement must explicitly record, where applicable:

- target class and applicability owner;
- applicability inputs and non-applicable branch evidence;
- all formula operands, constants, table inputs, table outputs, and reported result;
- comparison direction and inclusive/exclusive boundary;
- calculation or tolerance semantics;
- component/case membership and target-to-owner paths;
- time, history, assignment, and aggregation inputs;
- document, certificate, approval, alternative-compliance, and test evidence;
- controlled values and regulatory ordering;
- datatype, quantity kind, unit, cardinality, and closed-world expectation;
- whether the requirement is directly SHACL-verifiable.

An active requirement fails readiness if a required dependency is absent. A term merely mentioned in prose is not automatically an active operand.

### 3. Canonical modelling decisions

Use reusable node patterns instead of creating isolated properties for every sentence:

- `calculationCase` for formula inputs/results tied to one case;
- `loadCase` and `designCondition` for directional or operating cases;
- `tableLookupCase` for table selector inputs and attributed outputs;
- `assignment` for per-person/per-item/per-craft obligations;
- component inventory relationships for universal per-component constraints;
- `evidenceArtifact`, `approval`, `certificate`, and `documentRecord` for verifiable evidence;
- controlled-value classes/individuals where lexical strings cannot safely encode regulatory categories or ordering;
- quantity properties with one defensible quantity kind and unit policy;
- explicit result properties when a regulation requires comparison against a calculated value.

New terms must be ASCII-safe lowerCamelCase, have a normalized definition, naming rationale, source requirement/clause, owner, range, datatype/unit decision, aliases, and provenance. Formula symbols remain aliases, not canonical names.

### 4. Vocabulary and index change set

For each proposed change, record one of:

- add a verified new canonical term;
- reuse an existing exact term;
- alias/map semantically equivalent terms;
- split an overloaded term;
- change an incorrect datatype or quantity representation;
- add a controlled-value set;
- add or correct domain/range/owner metadata;
- add a missing relationship path;
- update only the requirement index/context metadata;
- defer or deactivate the requirement with an engineering reason.

No term will be added only because a generator requested it. The regulatory requirement and engineering model must support the term.

### 5. Retrieval and pipeline safeguards

Strengthen local, non-LLM checks so future readiness audits detect deep gaps before API calls:

- dependency completeness schema per encoding pattern;
- formula requirements must identify operands, result, units, and comparison metadata;
- conditional requirements must identify a branch selector;
- table requirements must identify selector and result terms or a lookup case;
- universal per-item requirements must expose an inventory path and item-owned properties;
- controlled categories must not rely on unrestricted strings when ordering/enumeration matters;
- context owner paths must be validated beyond simple one-hop existence;
- validator feedback requesting absent canonical terms must be distinguished from generator logic repair;
- matcher must not substitute semantically adjacent terms merely to avoid a vocabulary-gap status.

Recurring SHACL-generation safeguards will also be added for:

- pre-bound `$this` aggregation and grouping;
- no accidental passes from missing selectors or operands;
- all-values constraints instead of existence-only qualified counts;
- correct alternatives rather than conjunctive requirements;
- expected-result-scaled numeric tolerance;
- bounded SPARQL queries and supported math functions;
- removal of unrelated constraints added by the generator.

### 6. R9 construction

Create a new, non-overwriting development directory containing:

- ontology Turtle/RDF;
- term registry JSON/CSV;
- requirement evidence;
- requirement-term index;
- ownership, semantic-obligation, exclusivity, and node-pattern metadata;
- machine-readable change ledger;
- validation report and hashes;
- an explicit R9 development binding.

### 7. Validation gates before any API rerun

R9 proceeds only if all gates pass:

1. Turtle, RDF/XML, JSON, and JSON-LD parse successfully.
2. Every canonical local name is unique, ASCII-safe lowerCamelCase, and stable.
3. Every mapped IRI exists and matches exact URI identity.
4. Every indexed term exists.
5. Every owner, domain, range, controlled value, and relationship path resolves.
6. All active formula/conditional/table/per-item dependencies pass the stronger readiness rules.
7. All 313 contexts build.
8. No datatype/unit contradictions are detected.
9. Existing pipeline tests pass, plus new regression tests for the recurring failure patterns.
10. The R9 queue vocabulary ID matches the active R9 binding.

### 8. Targeted rerun and evaluation

- Create a queue containing only cases affected by R9 vocabulary, context, or pipeline changes.
- Do not rerun unaffected accepted shapes during development.
- Compare R8.1 and R9 outcomes per requirement.
- Any remaining term-resolution failure must be classified as a real new gap, retrieval failure, unsuitable benchmark case, or unsupported source ambiguity.
- Once generation stabilizes, create pass/fail RDF fixtures and evaluate accepted shapes independently of the LLM.
- Before the real experiment, freeze the vocabulary, discard development outputs from the experimental sample, and rerun clean simulations under the final lock.

## Completion criteria

R9 development is complete when:

- all 94 failures have a reviewed root-cause decision;
- the same latent patterns have been checked across all 313 requirements;
- every accepted active case has complete vocabulary/model dependencies;
- no unresolved failure is hidden by inventing or loosely substituting a term;
- all local validation gates pass;
- the affected-case rerun queue and change ledger are ready for review.
