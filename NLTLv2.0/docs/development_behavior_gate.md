# Source-authored finite behavioral checks — v0.3.1

No model calls. This release adds reusable `max_equal`, `constant_equal`, `quantity_equal`, and `conditional_value` operators driven by `data/contracts/development_witness_contracts.json`. There are no requirement-ID branches or generated SHACL answers in the checker. Arithmetic expectations use Python Decimal and explicit canonical paths/units, independently of candidate code. Source quotations/hashes, the exact locked dependency contracts, termOwners and property unit metadata are verified before use. Synthetic control shapes exist only in tests; the checker executes candidates, it does not replace them.

The witness configurations originate in source and locked representation metadata. They are development inputs, not held-out fixtures, benchmark labels, repaired counterfactuals or lessons inferred from workflow scores. Missing calculation inputs are a readiness failure in the declared local computation scope, not a new fleet-level existence rule. No maximum cardinality or numeric tolerance is invented.

| Requirement | New finite checks | Remaining limits |
|---|---|---|
| I2-004 | Single/multiple cases, maximum in both orders, ties, fractional maximum; selected result below/above maximum; missing result/cases/case operand/numeric/unit. | Finite decimals and represented cases, not proof for all graph multiplicities, literals, malformed data or physical waterlines. |
| I2-005 | Exactly 7°, values immediately below/above, mixed sampled points; missing sampled points/angle/numeric/unit. | No geometry reconstruction, complete spatial sampling or tolerance interpretation. |
| IMO-001 | Applicable A, wrong/missing applicable category; known nonapplicable branch with/without category; missing selector readiness. | Unknown/multiple selectors, category multiplicity, converse and engineering capability are not certified. R7 selector readiness is separate from regulatory truth. |
| TRF-035 | Equal integer/fractional quantities, either inequality direction; missing result/input/both/numeric/unit. | Stored inputs only; no society-rule derivation or universal literal/graph equivalence proof. |

Each mismatch saves source evidence, synthetic RDF, independently computed expectation, observed full-shape result, original pySHACL log and RDF report. Feedback includes the complete latest candidate/version/hash via the existing integrity-checked targeted repair route, an exact embedded query when unique (otherwise the full candidate with scope explicitly identified), and a source-backed correction instruction. A full-shape behavioral counterexample does not claim a unique root-cause constraint when several queries/branches exist. Execution failures are UNRESOLVED_EXECUTION/unconfirmed context, never conformance failures.

The checks run before semantic review and after each revision. `development_coverage_<attempt>.json`, history and run.json retain coverage/unchecked limits and `complete_verification: false`; reviewer ACCEPT cannot overwrite these fields. Internal acceptance is still bounded evidence. Single-shot does not execute these checks or repair; its original response is evaluated independently afterward.

`GenerationProject` denies evaluation/, outputs/ and results/ resource access in source building, checking, review and repair; the runner uses this restricted resource view. Tests run checks with the evaluation directory physically absent. This is a resource/API firewall, not an OS sandbox for arbitrary Python plugins; no untrusted execution plugins are introduced. External controls run separately after unit tests. Never pass their graphs or labels to this gate.

I2-042 remains blocked; see I2-042_applicability_decision.md. Keep the frozen six-requirement manifest unchanged. It is now stale relative to v0.3.1 and validation reports that explicitly, rather than silently refreshing its hashes. The separate five-requirement manifest freezes current inputs and exact evaluation IDs. Both workflows receive identical initial contexts/settings. TRF-010 initial context and shared prompts remain unchanged; the four new contexts describe the bounded verification scope. Tag v0.3.1 separately from completed v0.2.0/v0.3.0 artifacts.

Offline commands, from NLTLv2.0 with declared dependencies installed:

```sh
python -m nltlv2 --project . check
python -m nltlv2 --project . smoke
```

The five-requirement manifest is preparation only. Model calls still require separate authorization and a fresh frozen experiment destination. No dispatch command is executed by this release. The 50-requirement study remains pending review of the other 44 requirements.
