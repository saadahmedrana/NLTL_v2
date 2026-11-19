# Recovery point

The recorded Git revision and binary working/index patches describe the pre-refactor tree; user edits were not reset. `files_before.json` records original file hashes. No commit was made.

`recovery_index.json` records each modified/deleted/relocated original. Restore only selected paths after checking current user edits: `RELOCATED_UNCHANGED` and `EXISTING_IMMUTABLE_EVIDENCE` entries name a preserved byte-identical file; `SELECTIVE_ARCHIVE` entries name a member in the small `selective_originals.tar.gz`. Check its recorded SHA-256 before copying. `REBUILDABLE_CACHE` entries are disposable and were intentionally not archived. Do not extract over the whole tree blindly.

Historical experiments, scores and snapshots were not modified. The active pipeline is a forward v0.6.0 refactor, not an historical score correction.
