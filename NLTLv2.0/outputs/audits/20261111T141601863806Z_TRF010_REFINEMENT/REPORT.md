# TRF-010 refinement — offline verification

Implemented version 0.2.0 with complete section 1.8 source, a six-value obligation, verified canonical mapping supplement and deterministic finite-set coverage before NLTL acceptance. Both workflows receive the same corrected initial context. The ontology, locked registry and locked index remain unchanged; all 130 completed-pilot files remain byte-identical. No historical acceptance decision, score or baseline shape was changed.

Verification: configuration checks passed; all 96 control tests passed; all 37 external source-authored reference controls passed (17 positives, 20 negatives, and 20 passing intended-only counterparts). Reference results do not measure generated repair quality. No model/network calls, live generations, six-requirement batch or study were run.

Both byte-identical diagnostic pilot-shape copies now produce MISSING_ENUMERATION and cannot reach internal acceptance, even when an unused scripted reviewer ACCEPT is queued. Full latest-code packets, version/SHA, precise source locations, six expected IRIs, original JSON diagnostics and source evidence are saved with the diagnostic copies. Single-shot baseline is untouched.

Recognized alternatives include sh:in, sh:node indirection, value-focus OR/AND of finite constraints and value-focus hasValue singletons. Missing/incomplete/extra sets, wrong paths, deactivation and known applicability bypasses are detected. Unsupported equivalence remains unresolved; it is not forced into a preferred syntax or labelled a confirmed defect. Maximum cardinality remains unresolved and is not required. See docs/TRF010_enumeration_gate.md and docs/TRF010_maxCount_review.json for exact limits and evidence.

Representative complete rendered repair packets:

- [test_pilot_shapes_diagnostic_copies_only_nltl_TRF010_pilot_v1](../../../outputs/smoke_tests/20261111T141240853269Z/test_pilot_shapes_diagnostic_copies_only_nltl_TRF010_pilot_v1/repair_request.rendered.txt)
- [test_pilot_shapes_diagnostic_copies_only_single_shot_TRF010_pilot_v1](../../../outputs/smoke_tests/20261111T141240853269Z/test_pilot_shapes_diagnostic_copies_only_single_shot_TRF010_pilot_v1/repair_request.rendered.txt)
