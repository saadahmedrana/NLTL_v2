# Development smoke test

Status: **PASS**

This is development evidence only and is not part of the formal ablation results.

## Selection

Requirement `IMO26-014` was selected because it is COMPLETE and generation-eligible, has an intact formal RUN_01 first-prompt reference, and exercises a conditional SHACL rule without being an unusually expensive advanced-formula case.

## Result

- Run ID: `RUN-IMO26-014-20260831T140053117627Z`
- Generator model: `gpt-5.6-luna-2026-07-09`
- Logical generator calls: **1**
- Physical transport attempts: **1**
- Semantic-validator calls: **0**
- Vocabulary-matcher calls: **0**
- Syntax-repair calls: **0**
- Regeneration calls: **0**
- Extraction: **PASS**
- RDF/Turtle parse: **PASS**
- SHACL deterministic/meta-validation: **PASS**
- Canonical-vocabulary diagnostic: **PASS**
- Deterministic validation errors: **0**
- Deterministic validation warnings: **0**
- API elapsed time: **12,646.899 ms**
- Input tokens: **5,136**
- Output tokens: **842**
- Total tokens: **5,978**
- Estimated cost: **USD 0.010188** using the repository's indicative Luna rates of USD 1/M input and USD 6/M output tokens; this is not an Aalto invoice.

The raw model text was retained before diagnostics. The extracted SHACL and diagnostics were saved separately. No diagnostic result was fed back to any model.

The live smoke-test generator prompt was byte-identical to the stored formal FULL-pipeline first prompt for the same requirement:

`f2a5e27eb8cad09e70830390e9648ff8ff3680fa857690e8222148e3f6e50d08`

Artifacts are under:

`experiments/LUNA_CONTEXTUAL_SINGLESHOT/SMOKE_TEST/runs/RUN-IMO26-014-20260831T140053117627Z/`
