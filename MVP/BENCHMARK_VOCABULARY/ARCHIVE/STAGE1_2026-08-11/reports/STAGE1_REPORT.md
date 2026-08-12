# Journal 1 NL-to-SHACL Benchmark Vocabulary - Stage 1 Report

Date: 2026-08-11  
Project: `/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP`  
Stage boundary: **Stage 0 source audit + Stage 1 review shortlist only. No final ontology, JSON-LD schema, SHACL profile, or ship-design graph is declared.**

## Executive result

- The locked corpus contains **313 requirements**: 122 TRAFICOM, 48 IACS UR I2, 125 main IMO Polar Code, and 18 January 2026 amendments.
- The Stage 1 terminology shortlist contains **904 distinct review candidates**. This intentionally includes explicit operands plus hidden applicability, targeting, calculation, comparison, relationship, time/history, document/approval, and physical-test evidence inputs. It was not pruned to meet a round-number target.
- Every locked requirement is linked to at least one Stage 1 candidate concept.
- **240** Static or Static Calculation requirements are marked as direct/deterministic Stage 2 candidates.
- **40** Complex requirements are deferred pending composite/evidence workflow design; **17** Dynamic requirements are deferred pending observation/history/simulation design; **16** Physical Test requirements are evidence-only and must not be treated as substantively verified by SHACL.
- The confirmed Haitham implementation files both parse as Turtle: `HAITHAMSHIP.ttl` has 1,921 triples and `HAITHAMSRULES.ttl` has 736 triples. All 111 distinct `ssp:` local names referenced by the rules occur in the ship file, but this does not resolve their semantic, datatype, unit, target-node, or structural correctness.

## Live project and Git audit

At the start of this work, the current local branch was `main`, tracking `origin/main`, with remote `https://github.com/saadahmedrana/NLTL_v2.git`. The tree was clean at that moment. No reset, restore, checkout, clean, deletion, move, rename, commit, pull, push, or remote write was performed. All new material was created below `BENCHMARK_VOCABULARY`.

The source precedence used was:

1. `RELEVANT FILES` - current source/reference documents.
2. `INPUTS` - current active benchmark inputs.
3. `OLD FILES` - historical master's-thesis material and fallback/reference only.

`INPUTS` currently contains no active benchmark file other than `.DS_Store`. Consequently, the R2 locked workbook and the main MSC.385(94) PDF had to be used from `OLD FILES` and are explicitly marked as fallback sources.

## Source audit

### Current `RELEVANT FILES`

| File | Verified content and role | Pages / syntax | Status |
|---|---|---:|---|
| `AnchorMap__A_Multi_Agent_Pipeline_for_Variable_Standardisation_in_Maritime_Engineering (1).pdf` | AnchorMap methodology and canonicalisation evidence | 8 | Methodology |
| `BROKENONTOLOGYFROMGITHUB` | JSON-LD reference with ship/hull/propulsion terms | 406 RDF triples after parse | Broken reference only |
| `HAITHAMSHIP.ttl` | Haitham's confirmed final ship/requirement implementation graph | 1,921 triples | Implementation evidence |
| `HAITHAMSOCEANENGINEERINGJOURNAL.pdf` | *Regulatory requirement classification and semantic verification for model-based ship design*, Ocean Engineering 362 (2026) 126356 | 15 | Methodology |
| `HAITHAMSRULES.ttl` | Haitham's confirmed final SHACL shapes | 736 triples | Implementation evidence |
| `POLARCODES.pdf` | *Polar Code, 2016 Edition, Supplement January 2026*, including MSC.538(107) | 7 | Authoritative amendment/supplement, **not** the main code |
| `THESIS_RANA.pdf` | NLTL methodology, 90-case experiment, and variable-node access pattern | 80 | Methodology |
| `TRAFICOM.pdf` | *Ice Class Regulations and the Application Thereof*, TRAFICOM/68863/03.04.01.00/2021 | 65 | Authoritative regulation |
| `ur-i1rev2-1.pdf` | IACS UR I1 Rev.2, Polar Class descriptions and application | 2 | Authoritative companion/reference |
| `ur-i2rev4.pdf` | IACS UR I2 Rev.4, Structural Requirements for Polar Class Ships | 22 | Authoritative regulation |

The workbook `SOURCE_MANIFEST` sheet records exact paths, SHA-256 hashes, page counts, roles, and notes for all current sources and the material fallback sources.

### Fallbacks, duplicates, and missing companions

- `RELEVANT FILES/POLARCODES.pdf` is byte-identical to `OLD FILES/Haitham_Data/2Q191E_Supplement_January2026_EBK.pdf` (SHA-256 `9ff7f380...f9cf8fc`). The current copy is authoritative by precedence; the `OLD FILES` copy is only a historical duplicate.
- The main Polar Code is `OLD FILES/Haitham_Data/MSC.385(94).pdf`, 59 pages, SHA-256 `6c6a038b...afa5c1f`. It is not present in `RELEVANT FILES` or `INPUTS`, even though 125 locked requirements depend on it.
- `OLD FILES/Haitham_Data/ship.ttl` is byte-identical to current `HAITHAMSHIP.ttl`.
- `OLD FILES/Haitham_Data/rulesV2.ttl` is byte-identical to current `HAITHAMSRULES.ttl`.
- `OLD FILES/Haitham_Data/1-s2.0-S0029801826021906-main.pdf` has the same Ocean Engineering article identity as the current Haitham paper but is byte-different, consistent with a different PDF copy/metadata package.
- The historical Rana fixture set was validated read-only: 90/90 input JSON cases parse, 5/5 few-shot JSON files parse, and 10/10 ship-design Turtle files parse (2,889 triples total).
- The locked workbook is `OLD FILES/data/INPUTS/Input_regulations_3Sources.xlsx`, lock ID `LOCK-2026-08-11-R2`, current file SHA-256 `05eb02b0...700eaa`. Its `TRACEABILITY_LOCK` sheet also contains a separate “Reverified input SHA-256” beginning `216885...`; the object represented by that precursor hash needs clarification before publication.

## Locked requirement audit

| Source | Requirements |
|---|---:|
| TRAFICOM | 122 |
| IACS UR I2 Rev.4 | 48 |
| IMO Polar Code MSC.385(94) | 125 |
| IMO January 2026 supplement/amendment | 18 |
| **Total** | **313** |

| Verification category | Count | Stage 1 activation boundary |
|---|---:|---|
| Static | 151 | Direct/deterministic candidate |
| Static Calculation | 89 | Direct/deterministic candidate |
| Dynamic | 17 | Deferred for observation/history/simulation model |
| Complex | 40 | Deferred for composite/evidence workflow |
| Physical Test | 16 | Evidence/status only; no inferred physical compliance |

All included rows retain `Figure_Dependent = No`. This does not mean every row is directly SHACL-verifiable; the activation boundary above prevents simulation-, approval-, document-, or physical-test-dependent clauses from being misrepresented as simple graph-value checks.

## Terminology shortlist method

The shortlist was derived from all 313 rows, not the 15-rule or 90-rule pilots. Inputs included:

- locked canonical variables and required-input/artifact fields;
- exact verified source passages and normalized requirements;
- implicit operands needed for applicability, target selection, formulas, comparisons, topology, time/history, evidence, approval, certificates, and tests;
- Haitham's final ship and shapes files;
- Rana's thesis access pattern and historical fixtures;
- AnchorMap's rules for context-aware canonicalisation and separating units from identifiers;
- verified QUDT unit IRIs and W3C datatypes where available;
- the public DNV Vista/GMOD model and tooling description, without claiming unverified term-level codes.

The proposed local-name form is ASCII-only `lowerCamelCase`. Unit suffixes such as `_kW`, `_MPa`, `_m`, and `_degC` are retained as aliases but removed from proposed identifiers when detected; units are stored separately. Short formula symbols remain as aliases/evidence and are low-confidence review items when a readable semantic name is not yet securely established.

The 904 candidates are a deliberately broad evidence shortlist. They include 864 datatype-property candidates, 38 evidence/entity candidates, and 2 initial object-property candidates under the current automated classification. These role assignments are drafts; the low object-property count is itself evidence that the relation model needs deliberate human decomposition before Stage 2.

## Compatibility findings

### Critical

1. **Canonical node model is undecided.** Haitham/Rana commonly use a named variable node linked with `ssn:isPropertyOf` and read using `ssp:hasVariableValue`. A direct component-property-literal or QUDT quantity-value pattern would produce different SHACL paths, targets, cardinalities, and fixtures.
2. **The `ice:` namespace differs exactly.** Haitham's final rules use `http://example.com/iceregulations#`; Rana thesis listings also show `https://w3id.org/mtl-requirements/ice#`. Identical local names are therefore different IRIs.
3. **The Haitham QUDT schema prefix is malformed for prefixed-name expansion.** `@prefix qudt: <http://qudt.org/2.1/schema/qudt>` makes `qudt:unit` expand to `http://qudt.org/2.1/schema/qudtunit`; 94 such predicates occur. The standard QUDT schema namespace uses a delimiter.
4. **The broken JSON-LD has a malformed RDFS namespace.** It defines `rdfs` as `http://www.w3.org/2000/01/rdf-schem a#`, with an embedded space. Parsing succeeds with warnings and creates non-standard predicates; parse success is not ontology validity.

### High

5. **Identifier style conflicts.** The locked workbook includes unit-bearing names (`mcrPower_kW`, `yieldStrength_MPa`) and acronym/symbol names (`UIWL`, `Qmax_kNm`), while AnchorMap separates units from identifiers and the benchmark request requires readable ASCII lowerCamelCase names.
6. **Datatype and enumeration inconsistency.** Haitham's graph mixes decimals, integers, booleans, dates, and untyped strings. At least three value literals are untyped; categorical and version values require controlled datatype/enumeration decisions.
7. **Target and cardinality patterns vary.** Shapes target ship nodes, components, systems, and named variable nodes. A local-name match alone does not guarantee a structurally compatible shape.
8. **Evidence booleans may overstate compliance.** Approval, certificate, document, survey, and test concepts require provenance, issuing authority, dates, scope, and status lifecycles rather than undifferentiated true/false shortcuts.

### Medium / limitations

9. All 111 `ssp:` terms referenced in the confirmed rules occur in the confirmed ship file, but many are singleton resources rather than reusable properties; this is syntactic/structural coverage, not a semantic endorsement.
10. Public DNV Vista confirms a versioned GMOD with codes/paths and metadata tags, but no exact GMOD code/path was assigned to shortlist rows without a reproducible VIS export/version decision.
11. ISO 19848 normative content was unavailable. No normative ISO definition or identifier is claimed.

## Decisions required before Stage 2

1. Confirm whether the locked R2 workbook in `OLD FILES` remains authoritative, or place an approved current copy in `INPUTS`.
2. Confirm whether the fallback `MSC.385(94).pdf` may remain the authoritative main-code source for the benchmark.
3. Choose the canonical RDF access pattern: named variable nodes, direct datatype/quantity properties, or a precisely documented hybrid.
4. Approve a persistent benchmark base URI and reject the current `example.com` namespaces for final use.
5. Approve ASCII lowerCamelCase, unit-free identifiers with symbols and original notation retained as aliases.
6. Approve or adjust the activation boundary: 240 direct/deterministic candidates, 40 Complex deferred, 17 Dynamic deferred, and 16 Physical Test evidence-only.
7. Approve a provenance and status model for documents, certificates, approvals, surveys, and physical tests.
8. Select a DNV VIS/GMOD version and reproducible export/query workflow before accepting any exact GMOD mapping.
9. Clarify what the workbook's `216885...` “Reverified input SHA-256” identifies.
10. Review low-confidence shortlist rows, especially short formula symbols and candidate relation/entity roles, before any final URI assignment.

## Stage boundary

Work stops here for user review. Stage 2 must not begin until the naming, URI, node-model, evidence-model, source-precedence, and activation decisions above are approved.
