# R9 engineering vocabulary foundation

## Outcome

R9 is a development foundation, not a final experiment lock. It preserves the R8.1 development package and adds a fail-closed modelling layer intended to prevent vocabulary/model omissions from being misclassified as LLM generation errors.

- 313 requirements audited.
- 239 requirements remain generation-eligible.
- 1,418 canonical registry terms, including 346 R9 additions.
- 239/239 active requirements have `COMPLETE` dependency contracts.
- 93/94 observed failed requirements are repaired and queued for confirmation.
- 1 observed case (`I2-053`) is intentionally deferred because its calculation is delegated to UR S11.5.4.2 and that companion source is not present.
- 19 previously accepted requirements with proactive model changes are also queued.
- The confirmation queue therefore contains 112 requirements.
- No live API calls were made during this engineering revision.

## What changed

1. Added reusable engineering node patterns for calculation cases, load cases, table lookups, assignments, documents, approvals, equipment, and protected items.
2. Added requirement-grounded operands, results, controlled values, evidence paths, and cross-component relationships exposed by the Batch 02 failures.
3. Added a dependency contract for every requirement. A contract separates applicability inputs, operands, results, relationships, evidence, controlled values, and the comparison/table model.
4. Changed the pipeline to include the contract in generator, validator, and matcher context.
5. Added a fail-closed preflight gate: when the R9 configuration is used, no LLM call is made unless the requirement contract is `COMPLETE` and every declared term exists and is indexed.
6. Added a proactive all-313 model-depth audit so formula, table, conditional, per-item, evidence, and relationship risks are checked beyond the requirements that already failed.
7. Verified all new external unit identifiers against the official QUDT units vocabulary. A plausible but unpublished `MegaN-PER-M` identifier was replaced by QUDT's published dimensional equivalent `MegaN-M-PER-M2` for MN/m.
8. Added an offline regression test proving that the blocked I2 requirement stops before output creation or an LLM call.

## Failure reconstruction

The 190-case R8.1 development batch completed with 96 accepted and 94 failed requirements:

- 79 `TERM_RESOLUTION_UNRESOLVED`.
- 15 `MAX_ATTEMPTS_REACHED`.

The causes are multi-label. The dominant engineering findings were 79 vocabulary/model gaps, 62 incomplete context/model-depth cases, 39 missing evidence models, and 27 missing relationship paths. The registry-link audit found no case where a requirement-linked registry term was simply absent from retrieval; the dominant problem was that the required modelling dependency had not yet been represented or requirement-linked.

## Source boundary

`I2-053` cites UR I2.13.3.2, which directs the calculation to UR S11.5.4.2. The current verified source package contains UR I1 and UR I2 but not UR S11. Engineering action: keep this requirement outside generation until the cited method is obtained, audited, and modelled. Do not infer its hidden operands from general knowledge.

## Validation

- Turtle ontology parsed successfully.
- RDF/XML ontology parsed successfully.
- Registry local names and IRIs are unique.
- All canonical local names pass ASCII lowerCamelCase validation.
- All requirement-index terms resolve to the registry/ontology.
- All new external unit IRIs are in the verification ledger.
- All 313 context packs build successfully; all 239 active contracts are complete.
- Pipeline doctor passes with the R9 configuration without reading the environment file.
- 39/39 offline tests pass.
- The R9 tracker contains nine sheets, has no spreadsheet formula errors, and every sheet was rendered for visual review.

## Confirmation-run interpretation

The 112-case run is a development confirmation, not thesis data. If it reveals another true vocabulary/model omission, revise R9 and repeat the affected cases. Once the vocabulary is complete, create a new immutable evaluation lock and discard development-generation outputs before starting fresh multi-run experiments.

Do not run `I2-053` with an override. The pipeline will reject it even with `--allow-deferred` while its dependency contract is blocked.
