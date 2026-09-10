# Integrity repair: Batch E/F vs Pilot 02

Date: 2026-09-10

A file-namespace collision was detected after Batch E/F construction: Batch E reused the frozen Pilot-02 I2-014 and I2-015 RDF/specification paths, and Batch F reused the frozen Pilot-02 I2-021 paths. This was a benchmark infrastructure error, not a model-performance finding.

Repair performed:

1. Batch E collision artifacts were migrated to Batch-E-specific case IDs and specification filenames.
2. Batch F collision artifacts were migrated to Batch-F-specific case IDs and specification filename.
3. The exact original Pilot-02 bytes were restored and verified against the unchanged pilot_02_fixture_lock.json hashes.
4. Batch E/F locks were recomputed over their migrated artifacts.
5. No generated SHACL output was inspected and no source oracle or PASS/FAIL behavior was changed because of model performance.

Original pre-repair Batch E/F manifests and locks are retained in this reports directory for auditability.
