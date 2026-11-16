# Source/context preflight for the six-requirement development pilot

Version 0.3.0 is an offline readiness refinement. No model call or pilot dispatch is performed. The paired manifest contains all six requirements but is **not dispatchable** because I2-042 has unresolved welded-profile applicability.

Generation obligations and context patches are defined in data/contracts/development_preflight_profiles.json from authoritative source quotations, the locked index's explicit termOwners/modelPaths, and existing ontology/registry declarations. No fixture values, expected labels, repaired examples, workflow results or generated solution shapes define those patches. This adds no hard-coded requirement solution to the deterministic checker. The obligation descriptions are source-backed metadata, not executable regulatory answers.

Corrections:

- I2-004: complete I2.1.2.2 and scoped max-selection obligations; restore ship → hasUpperIceWaterlineCase → upperIceWaterlineCase using explicit ship ownership plus the exact relationship range. The broad domain is not used as exclusive ownership. Quarantine the unused, unbound upperIceWaterline string field without assigning it a guessed owner. Expose operand/result roles, both canonical kilotonne quantities and the scalar encoding profile.
- I2-005: verbatim I2.2.5, including 7°, and the explicit sampled-boundary-point graph model. Verify DEG units and the complete linked-point path. This does not reconstruct the whole hull's geometry or justify a one-point maximum.
- I2-042: include the I2.9.4 welded-profile qualification and limit scope to subclause (i), not the adjacent flange-outstand rule. Preserve the lower bound (not less than five times net web thickness) and millimetre units; quarantine generic metre-valued thickness. The generic structuralMember/hasStructuralMember model does not encode welding fabrication. No available structuralSectionType mapping establishes welded applicability. An explicit selector, class or scoped-inventory representation decision is required. Missing scope evidence is not false applicability, and no selector is invented. Both workflows are blocked before any generation request for this unresolved requirement.
- IMO-001: complete Introduction 2.1; the locked mediumFirstYearIceWithPossibleOldIceInclusions definition already denotes **at least** medium first-year ice. Preserve only the declared conditional implication and selector-readiness policy, not a new converse, universal Category A mandate or engineering-capability test. Verify the existing Category A IRI/type/prefLabel and add its missing registry row in the source-backed supplement. Correct the active medium-condition source reference from 1.2.1 to Introduction 2.1 while retaining the original reference as provenance; do not edit the locked registry.
- TRF-035: retain the complete L-definition sentence in 4.1.1, clarify equality of stored ruleLength and classificationSocietyRuleLength in metres, and expose their operand/result roles. Adjacent hull-region definitions and a classification-society-name string are not mandatory inputs of this represented equality; their locked metadata remains available but is quarantined from the active context. No society-specific length calculation or hull-region geometry is invented.

The source population (e.g. UR I2's Polar Class scope) and eligible design-record scope are explicit pilot preconditions. These local checks do not establish fleet eligibility from absent RDF assertions. The case review remains representation-scoped, not a whole-ship regulatory certification.

## Units and scalar literals

The locked R13 JSON-LD context was missing from the self-contained generation bundle. It is now copied byte-for-byte as schema/locked_representation_context.jsonld, with source/lock/hash provenance in docs/representation_context_provenance.json. Its numericValue coercion is xsd:decimal. It is a canonical serialization profile, **not** a new global RDFS numericValue range or a claim that other numeric RDF literal types are illegal in all applications.

Contexts with quantity operands now include that encoding evidence, exact quantity/property/unit IRIs and range metadata. A direct exclusive sh:datatype constraint on qudt:numericValue that rejects the canonical decimal encoding is detected generically. The checker does not alter numeric values, convert units by renaming, infer arbitrary SPARQL numeric equivalence, or silently add decimal ranges to the ontology.

## What is and is not checked

Synthetic, incomplete structural probes verify exact-IRI, object/literal term-kind, direct canonical literal compatibility, supported quantity-unit and explicit owner/path defects. The I2-004 path gap previously prevented reliable checking of case-owned displacements; that route now resolves from explicit evidence.

These probes deliberately omit regulatory arithmetic and existence constraints. The ordinary structural checker still does not prove displacement maximum selection, exact 7° equality, the flange/web inequality, IMO conditional/selector branches, or rule-length equality. The report marks those obligations **UNCHECKED**, rather than treating successful structural checks as verified implementation coverage. Source-backed semantic review and independent evaluation remain needed. TRF-010's explicit finite-set gate is separate and remains in effect. No new requirement-specific checker answers or hard-coded generated SHACL solutions were added.

## Cases, examples and evaluation separation

The retained core remains 37 cases across six requirements: 17 positives, 20 intended negatives and 20 certified intended-only counterparts. Readiness audit rechecks fixture/counterfactual hashes, represented-source oracles and retained intended-only operation certificates. For I2-042, historical certificates and labels are preserved, while current source-domain applicability is explicitly unresolved. Nothing is relabelled or excluded to improve a workflow result.

The two actual supplied examples remain FS-BOOL-01 and FS-BOOL-02 for both methods; none of the six requirements occurs in them. Related generic category/quantity/conditional examples in the unused corpus are reported separately, not mistaken for supplied target examples. The generation builder and repair loop never read evaluation fixtures, labels or counterparts. External case review is performed only by the offline preflight/evaluation module.

## Prepared manifest and comparability

configs/paired_development_pilot.json declares one-call Single-shot with no revision, maximum six-candidate NLTL with early internal acceptance and no fresh regeneration, independent post-workflow evaluation, identical initial-request hashes, frozen source/code/config hashes, shared exclusions and stop rules. It has dispatch=false and no executor is invoked. Structural validation may pass while readiness is blocked; --require-ready fails on the unresolved I2-042 binding.

```sh
../NLTLv2-env/bin/python -m nltlv2 preflight
../NLTLv2-env/bin/python -m nltlv2 preflight --require-ready
# The second command is expected to refuse readiness until the blocker is resolved.
```

Five initial contexts and generic checker/eligibility implementation change in v0.3.0. The TRF-010 initial context and shared prompts remain identical to the completed v0.2.0 fresh paired pilot; a regression test pins that equality. Nevertheless implementation versions must be recorded separately and historical scores must not be pooled or rewritten. All historical artifacts remain byte-identical. The 50-requirement study still requires review of the other 44 requirements; the new core applicability blocker is additional, not a manufactured change to that count.
