# First-generator-call equivalence

Result: **PASS**

The representative COMPLETE requirement was `IMO26-014`. It was selected because it occurs in the frozen 268-item queue and has an intact first-attempt generator-prompt artifact in formal `FINAL_LUNA_MAIN/RUN_01`.

Three requests were compared offline:

1. the exact stored first generator prompt from formal RUN_01;
2. a freshly rendered request through the normal full `PipelineRunner` components;
3. a freshly rendered request through `ContextualSingleShotRunner`.

All three combined prompts were byte-identical with SHA256:

`f2a5e27eb8cad09e70830390e9648ff8ff3680fa857690e8222148e3f6e50d08`

The following checks all passed:

- developer/system instructions matched;
- user payload matched;
- requirement and structured dependency/context matched;
- scoped vocabulary and node/path material matched;
- selected few-shots matched (`FS-BOOL-01`, `FS-BOOL-02`);
- table/source material embedded by the context renderer matched;
- `repairFeedback` was `NONE`;
- generator model matched: `gpt-5.6-luna-2026-07-09`;
- generator output limit matched: 16,000 tokens;
- few-shot count and generated-shape namespace matched.

No timestamp, run ID or output path is embedded in the generator prompt, so no normalization was required. Machine-readable details are in `first_call_equivalence.json`.
