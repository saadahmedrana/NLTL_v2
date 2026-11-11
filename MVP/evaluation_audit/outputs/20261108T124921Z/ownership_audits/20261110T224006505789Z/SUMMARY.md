# Ownership/path adjudication — retained evaluation evidence

Authoritative baseline `20261108T124921Z`, latest semantic review `20261110T103534113460Z`. The current flags are **59 NLTL_v2 / 56 Single-shot**, rather than the frozen earlier 58/55 CSV. Current per-case causes plus the original-50 cause fallback produce **115 workflow/case flags, 89 unique cases, 20 requirements**, grouped into **32 requirement/property analyses**.

| Finding | NLTL_v2 (59 flags) | Single-shot (56 flags) |
|---|---:|---:|
| SHACL_VIOLATES_CLEAR_SCHEMA | 0 | 0 |
| FIXTURE_VIOLATES_CLEAR_SCHEMA | 29 | 13 |
| BOTH_VIOLATE_CLEAR_SCHEMA | 0 | 0 |
| BOTH_CONFORM_NO_OWNERSHIP_ERROR | 3 | 5 |
| ONTOLOGY_CONTRACT_CONFLICT | 0 | 0 |
| SCHEMA_UNDERSPECIFIED | 27 | 38 |
| INSUFFICIENT_EVIDENCE | 0 | 0 |

Fixture-side counts cover the original negative or its supplied repaired counterfactual, as explicitly recorded by adjudicated_fixture_arm. Five workflow/case flags have no original value; the wrong-owner value exists only in the supplied repair, and is not misdescribed as an original wrong-node assertion. Confirmed placement violations are distinguished from supported no-ownership-error findings and unresolved schema gaps. These counts do not rescore validation or strict intended-failure accuracy. A deliberately invalid negative fixture can violate the representation without being an invalid test.

## Evidence and examples

- **TRF-130:** `/termOwners/TRF-130/totalRelevantEnginePower = ship`. Both source engine-output wording and the explicit contract are consistent with a ship-owned shared quantity. Where present, the flagged negative or supplied repaired fixtures put it on an inlet chest while the shape requires it on ship. This is a fixture placement violation; the broad benchmarkEntity domain is not the ownership proof.
- **TRF-050-F05, both workflows:** the shapes target frameAttachmentRecord. The fixture puts frameShellWeldType on frame instead of the linked frameAttachment object. That assertion infers frameAttachmentRecord on frame via RDFS domain, explaining why record constraints report a missing shellPlateButtCrossing there. The previous shape-owner blame is not supported: this is the intended fixture wrong-owner defect. The existing strict classification is preserved. The property-level record explicitly separates correctly placed shellPlateButtCrossing from the causal misplaced frameShellWeldType; the primary case finding refers to the latter.
- **I2-024, Single-shot:** interpolationPoint and obliquePlatingInterpolationCase are subclasses of calculationCase. Values on the root case and constraints on endpoint calculationCase instances do not establish an incompatible owner. Missing endpoint values and a possibly overbroad universal minCount are separate cardinality/role-scope issues, which the supplied contract does not settle.
- **I2-006:** the shape and every supplied aftSectionDesignBasis value use ship; one negative omits the value rather than placing it elsewhere. The flagged error is an exact-string/literal issue, not ownership.

## Unresolved representation and context

For the SCHEMA_UNDERSPECIFIED groups, the disputed property lacks an explicit requirement-specific termOwners assignment and a modelPath binding that property. Related case/component relationships do not fix the missing property owner. All these domains are benchmarkEntity. requiredOwner=ship in the historical context is retained as prompt evidence, not treated as authoritative schema. This includes the earlier machineryComponentType owner claim for IMO-049.

No exclusive placement rule is inferred from an RDFS domain. Range and subclass relations are recorded separately. No ontology/contract contradiction is declared merely because classes differ; actual explicit inconsistencies, if present, are listed in each schema record.

The actual attempt_01 generator_prompt.txt payload is compared with the initial context pack and the locked ontology/index hashes. `context_counts.csv` separately reports correct/incorrect/contradictory/underspecified ownership context; generic calculationCase role/cardinality scope remains underspecified even where its owner class is correct.

## Files

`cause_ledger_reconciliation.json` identifies the current cause source and semantic-review additions. `current_provisional_cause_ledger.*` preserves the flags before adjudication. `findings.*` gives one primary finding for each of the 115 flags. `confirmed_findings.csv` and `provisional_or_unresolved_findings.csv` are separate. `groups/` contains source excerpts, complete property declarations, class hierarchy, exact contract/termOwners/modelPaths, actual prompt excerpts and shape traversal for each grouped analysis. `cases/` retains every affected case, exact fixture owners/types/paths and both saved validation reports.

No existing file, shape, fixture, verdict, label, exclusion or cause record is changed. All prior authoritative-run artifact hashes are checked. No validation, generation or API call is made. The audit script and read-only tests are retained here.
