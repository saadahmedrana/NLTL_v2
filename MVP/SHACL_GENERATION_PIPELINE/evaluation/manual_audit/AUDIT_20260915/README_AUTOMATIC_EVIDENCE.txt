NLTL MethodV2 automatic-evidence enrichment

Purpose
=======
scripts/enrich_automatic_evidence.py enriches the three MethodV2 architecture
sheets using the authoritative audit_selection.json and existing RUN_01
behavioural ledgers. It creates a new workbook and never overwrites
NLTL_Manual_Audit_ready_v2.xlsx.

The script does not call a model API, generation pipeline, repair agent,
candidate evaluator, or behavioural experiment. It does not fill manual
semantic-fidelity, code-quality, oracle-validity, reviewer, or corrected-label
fields.

Inputs and artifact policy
==========================
The only selected artifact for an architecture-requirement identity is the path
and SHA-256 in audit_selection.json. Every artifact, evidence file, ledger, and
selected RDF case is checked against its recorded SHA-256. A missing or
mismatched artifact remains missing/error; the script never searches for or
substitutes another candidate. Only RUN_01 is accepted.

Imported or reconciled evidence
===============================
The script imports rather than recomputes:

* Turtle parsing status.
* Pipeline deterministic/static validation and acceptance status.
* Selected RDF case expected outcome, actual conformance, execution status,
  behavioural match, and outcome class.
* Existing conditional and end-to-end behavioural metrics.

Existing workbook values are preserved. A mismatch with the authoritative
selection or ledger is written to automatic_evidence_discrepancies.csv.

New automatic evidence
======================
Operational SHACL validity:

The pipeline's recorded meta_shacl_valid field is composite rather than a pure
replication of W3C SHACL-SHACL or NL2SHACL-Bench Spec-VR. The implementation
first performs meta-SHACL validation, then activates declared targets on a
synthetic graph and requires successful SHACL runtime execution. Consequently,
embedded SHACL-SPARQL parser and runtime failures can make the field false. The
workbook and r2 summary therefore call this Operational SHACL validity.

1. RECORDED: uses this existing composite meta_shacl_valid value only when its
   evidence hash and artifact-metadata iteration match the selected artifact
   SHA-256.
2. DERIVED: when the exact selected artifact parsed and at least one exact-hash
   ledger row completed execution with pyshacl_options.meta_shacl=true.
3. RECHECKED: only if recorded and derived evidence are unresolved, the same
   local meta-SHACL plus activated synthetic runtime-smoke checks are performed.
   This does not evaluate an RDF benchmark case.
4. NOT_TESTED, MISSING_ARTIFACT, and ERROR remain explicit.

The workbook displays PASS, FAIL, NOT_EVALUATED, UNAVAILABLE, or ERROR for this
field. The JSONL retains VALID/INVALID and full provenance.

SHACL vocabulary validity:

Every URI in http://www.w3.org/ns/shacl# used anywhere in the selected graph is
checked against the SHACL vocabulary terms present in the installed pySHACL
version's shacl.ttl and shacl-shacl.ttl assets. IRIs in project-specific and
other namespaces are outside this check. Every unknown SHACL IRI is retained in
automatic_evidence_r2.jsonl.

Recorded versus selected-artifact Turtle parsing:

The workbook's Recorded Turtle parse status remains unchanged historical
pipeline evidence. Each r2 JSONL record separately contains
selected_artifact_turtle_parse_validity, which records the result of parsing the
hash-verified retained artifact during enrichment. A retained diagnostic may be
pipeline-rejected yet still be an available, Turtle-parseable audit artifact.

The r2 summary keeps four denominators separate:

* pipeline_approved_output_rate: OFFICIAL_ELIGIBLE_OUTPUT / 268 requirements.
* retained_audit_artifact_availability: hash-verified retained artifacts / 268.
* selected_artifact_turtle_parse_rate: enrichment parse-valid artifacts /
  hash-verified retained artifacts.
* operational_shacl_validity_rate: operational-valid artifacts / parseable
  artifacts for which the composite operational check was evaluated.

Selected-case target activation:

Only the fixed selected expected-PASS and expected-FAIL graphs are inspected.
The checker evaluates standard sh:targetNode, sh:targetClass,
sh:targetSubjectsOf, and sh:targetObjectsOf targets. targetNode,
targetSubjectsOf, and targetObjectsOf are checked directly in the selected RDF
case graph. For targetClass, the script reconstructs the original evaluator's
environment: it verifies the RUN_01 run manifests, loads the frozen ontology at
MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R13/ontology/
nltl_benchmark_vocabulary.ttl, verifies its SHA-256 against the manifests,
inoculates a copy of the selected data graph with that ontology using pySHACL,
and applies the installed pySHACL CustomRDFSSemantics RDFS closure. The selected
case is not revalidated against SHACL.

If the ontology path/hash, manifest settings, or inference environment cannot
be reconstructed unambiguously, an otherwise unproved targetClass result is
NOT_EVALUATED with reason ONTOLOGY_OR_INFERENCE_CONTEXT_UNRESOLVED. It is never
reported NOT_ACTIVATED from local case-graph subclass statements alone. The
checker also never infers non-activation from an empty validation-report
focus-node list. A graph using sh:target/custom or SPARQL targets, or
owl:imports, is NOT_EVALUATED. The workbook stores both case IDs and their
activation statuses in one cell; detailed focus nodes, context provenance, and
limitations are kept in the JSONL.

Reproducibility metadata:

automatic_summary_r2.json records the Python, RDFLib, and pySHACL versions; the
paths and SHA-256 identities of installed pySHACL SHACL-vocabulary resources;
the activation ontology path and SHA-256; the inference mode; whether the
activation context was resolved; and the manifests/code paths used to establish
that context.

Structural-profile counting rules
=================================
* Node-shape count: unique resources explicitly typed sh:NodeShape.
* Property-shape count: the union of resources explicitly typed
  sh:PropertyShape, objects of sh:property, and subjects having sh:path.
* SHACL Core component occurrence count: one count for each triple whose
  predicate is a SHACL Core constraint parameter. It includes value, cardinality,
  string, property-pair, logical, shape-based, qualified-value, closed-shape,
  has-value, in-list, and property parameters. It excludes labels, names,
  descriptions, messages, severity, targets, prefixes, deactivation, ordering,
  paths themselves, and sh:sparql.
* Core components used: sorted unique sh: parameter names counted by the rule
  above.
* SHACL-SPARQL constraint count: number of sh:sparql triples.
* Maximum property-path depth: a direct predicate has depth 1. A sequence or
  alternative path adds one level above its deepest member. Inverse and the
  zero/one-or-more path operators add one level above their operand. No path is
  depth 0. Cycles stop at depth 0 rather than looping.
* Maximum logical nesting depth: a top-level sh:and, sh:or, sh:xone, or sh:not
  is depth 1; nested logical operators in their member shapes add one per level.
  No logical constraint is depth 0. Cycles stop at depth 0.

These measurements are descriptive. They are not quality scores and do not
establish complete semantic equivalence to a regulation.

Outputs created by a production run
===================================
* NLTL_Manual_Audit_ready_v2_enriched_r2.xlsx
* automatic_evidence_r2.jsonl
* automatic_summary_r2.json
* automatic_evidence_discrepancies_r2.csv

The pre-r2 enriched workbook and evidence files are left byte-for-byte
unchanged. Their SHA-256 identities are recorded in automatic_summary_r2.json
when they are present, and the verifier checks those archived identities.

The JSONL has one row per architecture-requirement artifact (804 rows for the
full package). Summary rates always include named numerators and denominators.

Run from the repository root
============================
MVP/.venv/bin/python3 MVP/SHACL_GENERATION_PIPELINE/evaluation/manual_audit/AUDIT_20260915/scripts/enrich_automatic_evidence.py

The command fails if any r2 output already exists. To leave unresolved
operational SHACL evidence NOT_TESTED instead of doing the permitted targeted
standalone composite check, add --no-recheck-unresolved-operational-shacl.

Verify after production
=======================
MVP/.venv/bin/python3 MVP/SHACL_GENERATION_PIPELINE/evaluation/manual_audit/AUDIT_20260915/scripts/enrich_automatic_evidence.py --verify-only

The verifier checks one unique JSONL record per architecture-requirement,
artifact identities against audit_selection.json, workbook hash against the
summary, discrepancy counts, and OOXML preservation. All workbook ZIP parts
outside the three architecture worksheets must be byte-identical. Within those
worksheets, only the ten automatic evidence columns may change; formulas and
all other cells and worksheet features must remain unchanged.
