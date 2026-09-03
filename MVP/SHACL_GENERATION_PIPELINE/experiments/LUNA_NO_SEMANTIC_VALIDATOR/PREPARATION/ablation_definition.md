# LUNA_NO_SEMANTIC_VALIDATOR definition

## Intervention

This condition is the frozen FULL Luna R13 pipeline with the semantic-validator component removed. Every operation before the first generator response is unchanged. After that response, the existing syntax-only recovery route remains active, followed by read-only deterministic validation and an ablation-specific terminal classification.

## Active components

- R13 lock, 268-item queue and COMPLETE-contract gate;
- source, normalized requirement and structured dependency context;
- scoped canonical vocabulary and owner/path/formula/applicability context;
- identical few-shot retrieval;
- identical generator developer/user prompt;
- Luna generator model and generator output allowance;
- response-marker extraction;
- Turtle/RDF and embedded SPARQL parsing;
- syntax-repair LLM, only while the existing syntax-failure predicate is true;
- immediate revalidation after each syntax repair;
- SHACL/meta-SHACL, vocabulary, datatype/unit, target/path and deterministic contract diagnostics;
- raw response, candidate, event, token, timing and cost telemetry.

## Inactive components

- semantic-validator LLM;
- validator ACCEPT/REVISE judgement;
- validator feedback and validator-response reconciliation;
- vocabulary-matcher LLM, because the real architecture has no independent activation path;
- context expansion from matcher decisions;
- semantic generator regeneration/attempts 2–4;
- `GENERATION_ACCEPTED`, because that full-pipeline status requires semantic-validator acceptance.

## Execution model

1. Make one normal generator call.
2. Save its exact output text.
3. Run deterministic extraction and validation.
4. If and only if the existing syntax-failure predicate is true, invoke syntax repair within the existing configured syntax budget. Save every repair response and revalidate immediately.
5. Do not send diagnostics to the generator, matcher or any semantic substitute.
6. Finish as:
   - `SYNTAX_REPAIR_EXHAUSTED` if syntax remains unusable;
   - `NO_SEMANTIC_VALIDATOR_DETERMINISTIC_PASS` if all deterministic checks pass;
   - `NO_SEMANTIC_VALIDATOR_DETERMINISTIC_FAIL` if syntax is usable but another deterministic check fails.

`maximum_semantic_attempts` remains present and identical in the formal configs for first-call equivalence, but it has no operational role in this ablation. No blind generator retry is introduced.

## Scientific distinction from contextual single-shot

Contextual single-shot performs no downstream LLM call. This ablation retains the FULL pipeline's independent syntax-repair LLM. Therefore malformed generator output may be recovered mechanically here, whereas it remains a legitimate extraction/parse failure in contextual single-shot.

The terminal deterministic-pass status is not semantic correctness and not hidden-RDF accuracy.
