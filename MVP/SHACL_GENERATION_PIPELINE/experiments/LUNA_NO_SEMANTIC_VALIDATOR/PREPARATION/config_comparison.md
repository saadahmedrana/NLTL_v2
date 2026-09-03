# Formal configuration comparison

The five formal configurations were derived from the same frozen FULL Luna configuration. After normalizing only `pipeline_version` and `paths.outputs`, their JSON objects are identical.

| Config | Pipeline version | Output directory | SHA256 |
|---|---|---|---|
| run01 | luna-no-semantic-validator-run01-v1 | RUN_01 | `0d276f13dd1810d0d4237d856d1b0f3d40eb8fad7a846bb167d79c57f00247da` |
| run02 | luna-no-semantic-validator-run02-v1 | RUN_02 | `96a4e58e80d739a6a4aabada0fd1f4d3d795bafac49dd58fba7f7157e7415d03` |
| run03 | luna-no-semantic-validator-run03-v1 | RUN_03 | `bb6483ba893abda069c1a8c6bb1f6caf95a5ef3497ba66c81a97958715dc7ccd` |
| run04 | luna-no-semantic-validator-run04-v1 | RUN_04 | `a6faa351b84435661d7f31b66b6b92b5a0fcc6ddb1ecbb80aa8229fbd03d9e58` |
| run05 | luna-no-semantic-validator-run05-v1 | RUN_05 | `97d101b11470db98326d7ced3ccff4764463507e4463857778a37edf90f9ac29` |

Common scientific settings include R13, the frozen 268 queue, one repetition, Luna for all configured roles, identical prompts/retrieval/generation parameters, semantic validator disabled, independent syntax repair enabled, matcher disabled, semantic regeneration disabled, and deterministic diagnostics not used as a regeneration signal.
