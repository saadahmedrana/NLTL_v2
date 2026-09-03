# Full-pipeline semantic-validator dependency audit

## Audited code path

The current full route is implemented by `src/nltl_pipeline/orchestration/runner.py::PipelineRunner.run_requirement` and called from `src/nltl_pipeline/cli.py::main`.

1. `VocabularyRepository.build_context_pack` builds the locked R13 context.
2. `FewShotSelector.select` chooses the configured examples.
3. `PromptFactory.generator_user` renders the first request with `repairFeedback` equal to `NONE`.
4. `client.call("generator", ...)` produces the first response.
5. `ShaclStaticValidator.validate_raw` extracts the marked SHACL and runs Turtle, SHACL/meta-SHACL, SPARQL, vocabulary, datatype/unit, target/path and deterministic contract checks.
6. When `ShaclStaticValidator.is_syntax_failure` is true, the independent syntax-only loop invokes `client.call("syntax_repair", ...)`, revalidates immediately, and may repeat up to `maximum_syntax_repairs_per_semantic_attempt`.
7. Once syntax is usable, `PromptFactory.validator_user` embeds the candidate and deterministic report. `_call_and_parse` invokes `client.call("validator", ...)` and parses the semantic ACCEPT/REVISE decision.
8. The candidate is accepted only when `validation.valid and validator_decision.accept`.
9. The vocabulary matcher is reached only when `validator_decision.activate_variable_matcher` is true. Deterministic search supplies candidate terms, but there is no independent matcher-control branch.
10. Validator feedback, optionally appended with a matcher result, becomes `repair_feedback`. The outer semantic-attempt loop then calls the generator again.
11. `generation.maximum_semantic_attempts` limits that outer generator/validator repair loop.

## Answers to the dependency questions

1. **What invokes the semantic validator?** `PipelineRunner.run_requirement` always invokes `_call_and_parse` with role `validator` after syntax is usable. The request is built by `PromptFactory.validator_user`.
2. **What depends specifically on validator feedback?** Semantic ACCEPT/REVISE, activation of the vocabulary matcher, construction of repair feedback, context expansion through a verified matcher term, and every semantic generator revision.
3. **Can generator attempts 2–4 occur without validator feedback?** Not through the implemented full route. The next generator attempt is controlled by the post-validator branch. Syntax repair is a separate role and does not count as another generator attempt.
4. **Can the vocabulary matcher run independently?** No. It is gated by `validator_decision.activate_variable_matcher`. Suspicious deterministic IRIs alone only prepare possible candidates for validator context; they do not invoke the matcher.
5. **Is syntax repair independent?** Yes. It runs before semantic validation, receives parser/extraction diagnostics, has its own retry budget, and can complete without a semantic-validator call.
6. **Can deterministic validation independently request generator regeneration?** No. It can block full acceptance and its errors are appended to feedback, but the control decision and next semantic attempt still pass through the validator branch. Reusing deterministic diagnostics as a new regeneration controller would create a new architecture rather than remove one component.
7. **What terminal states remain coherent without the semantic validator?** `SYNTAX_REPAIR_EXHAUSTED` remains unchanged for unrepaired syntax. For syntax-usable outputs, new explicit ablation statuses are needed: `NO_SEMANTIC_VALIDATOR_DETERMINISTIC_PASS` and `NO_SEMANTIC_VALIDATOR_DETERMINISTIC_FAIL`. They avoid claiming semantic acceptance.
8. **Does `GENERATION_ACCEPTED` require validator acceptance?** Yes. In the full runner it is assigned only inside the `validation.valid and validator_decision.accept` branch. The ablation must not emit `GENERATION_ACCEPTED`.

## Audit conclusion

Removing only the semantic validator necessarily removes the vocabulary-matcher invocation and semantic generator attempts 2–4 because both are downstream of the validator decision. Syntax-only repair remains scientifically coherent and operationally independent. Deterministic validation remains an observational/terminal gate, not a replacement semantic validator and not a new repair signal.
