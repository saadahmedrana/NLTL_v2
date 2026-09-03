# First-call equivalence

Result: **PASS**

For COMPLETE requirement `IMO26-014`, the following were byte-identical:

- the stored formal FULL RUN_01 first generator prompt;
- a freshly rendered FULL-pipeline first request;
- the no-semantic-validator first request.

SHA256 for all three combined prompts:

`f2a5e27eb8cad09e70830390e9648ff8ff3680fa857690e8222148e3f6e50d08`

Developer instructions, user payload, requirement/source context, dependency contract, vocabulary, node/path/formula/applicability material, few-shots (`FS-BOOL-01`, `FS-BOOL-02`), generated-shape namespace, Luna model and the 16,000-token generator output allowance all matched. `repairFeedback` was `NONE`.

No normalization was required because no run ID, timestamp or output path is embedded in the request. The intervention occurs only after the first generator response.
