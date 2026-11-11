# TRF-010 source context and deterministic enumeration gate

This refinement is offline. The completed live pilot, both baseline shapes, raw responses, acceptance decisions and scores remain unchanged. Replays use byte-identical, explicitly labelled diagnostic copies under smoke_tests/diagnostic_inputs, never edits to the pilot.

## Source and bindings

The complete enumeration in TRAFICOM/68863/03.04.01.00/2021 section 1.8 is recovered from data/requirements/TRAFICOM_full.txt. The source hash, exact excerpt and line range are in data/contracts/enumeration_obligations.json and docs/TRF010_context_change_manifest.json. Active TRF-010 source text now includes all six numbered classes and descriptions. The represented verification scope remains category assignment; it does not certify engineering qualification from those descriptive paragraphs.

Each source label is uniquely matched to an existing ontology individual by rdf:type iceClassValue and skos:prefLabel:

| Source label | Existing canonical local name |
|---|---|
| IA Super | iceClassIaSuper |
| IA | iceClassIa |
| IB | iceClassIb |
| IC | iceClassIc |
| II | iceClassIi |
| III | iceClassIii |

All IRIs use https://w3id.org/nltl/vocab#. All six are absent as individual entries from the locked term registry. That absence is explicit; it was not reported as a successful registry match. schema/controlled_value_registry.json supplies verified source/schema-backed supplemental entries, including the original registry hash and absence check. The locked registry, locked term index and ontology RDF are unchanged. No ontology triples, IRIs or meanings were altered. Schema construction/configuration verification rejects stale source hashes, wrong owner/path, invented labels/IRIs, duplicate bindings or inconsistent registry assertions.

Both generation methods receive the same corrected initial source, explicit finite-set obligation, mapping, ontology types/labels and examples. The source-derived contract contains no evaluation fixture paths or labels. The explicit termOwners binding requires ship/iceClass; the broad benchmarkEntity domain is not an ownership rule.

## What the gate proves

For every applicable ship, the analyzed membership restriction at iceClass must admit exactly the verified six IRI terms. Cardinality/presence and other obligations remain separate. The gate runs before reviewer acceptance and after every code repair in NLTL. Single-shot generation remains one call with shared extraction only.

Recognized finite-set encodings:

- sh:in at the required property value focus, including single-step RDF sequence paths.
- sh:node indirection to a NodeShape with that restriction.
- Value-focus sh:or unions and sh:and intersections of recognized finite restrictions. Value-focus sh:hasValue NodeShapes are singleton sets, so ORs of six singleton value shapes are supported.
- Owner-focus conjunction of property restrictions; owner-focus OR only where one proven branch set contains all other branch sets and no unresolved applicability guard is involved.

The proof follows actual RDF constraint structure, complete path, targets, deactivation and logical branches; it does not search messages for enum text. Unreferenced or wrong-path lists do not count. Type/range membership, sh:nodeKind sh:IRI and cardinality do not establish a closed set. Missing restrictions, missing/extra members, inactive/wrong-scope restrictions and a known logical bypass cannot receive coverage credit.

Owner-level OR of disjoint partial property sets is **not** assumed equivalent to a value-level OR. With multiple values, `(all values in A) OR (all values in B)` differs from `all values in (A union B)`. The checker does not invent maxCount 1 to make that equivalence hold.

Unsupported SPARQL equivalence, xone/not, custom constraint components, qualified constraints, nonstandard target strategies, recursive/malformed structure, complex paths and unproven applicability guards yield UNRESOLVED_CONTEXT, confirmed=false. They block acceptance without being presented as confirmed regulatory defects. An equivalent encoding outside the supported subset needs an additional evidence-backed equivalence implementation; it is not declared wrong merely for using different syntax.

This is a proof of the declared membership obligation, not a whole-shape equivalence or regulatory correctness proof. Other checks and source review remain necessary. In particular a covering superclass target can prove membership coverage for ships while broader target effects remain for the existing target/path checker to adjudicate. Ordinary execution success is not proof of correctness.

## Feedback and regressions

coverage_findings emits the current candidate version/hash, status, expected six IRIs, effective members and differences, target/path/applicability evidence, source clause/excerpt/hash, exact offending block with line/offset location, original JSON diagnostic and concrete suggested correction. Existing request-integrity guards require the full latest candidate and the identical latest findings at dispatch. Rendered diagnostic replay packets are saved in the current smoke output.

Changing a list no longer disappears behind a generic STRUCTURE regression signature: list members are fingerprinted. A diagnosed wrong set may be corrected to the exact evidenced set; deleting unrelated constraints still triggers the regression guard. Declared SHACL shape identifiers are distinguished from regulatory operands, preventing an artifact name from being misreported as an unknown vocabulary term during pilot replay.

## Maximum cardinality

Section 1.8 supplies the category list, but no explicit maximum-cardinality assertion was established. The locked representation contract has no maxCount policy, and iceClass is not declared owl:FunctionalProperty. docs/TRF010_maxCount_review.json records this evidence. maxCount 1 remains an unresolved possible overconstraint, not a confirmed defect. Neither generator guidance, reviewer guidance nor the deterministic enum gate requires it. Its presence/absence does not by itself establish or invalidate membership coverage. No cardinality repair is applied to either pilot shape.

## Verification boundaries

Internal execution checks use only source/schema-derived synthetic ships and an explicitly synthetic unlisted value. External cases and repaired counterparts remain confined to the independent evaluation module. A generation-only file-access test rejects evaluation/ paths. Diagnostic replays stop before reviewer acceptance if the enum is absent; scripted local correction tests exercise feedback integrity but do not establish model repair quality. The complete external 37-case source-authored reference-control regression remains development evidence, not generated-shape performance.

No new model requests, six-requirement batch or scaling study is authorized or run by this refinement.
