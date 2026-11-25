# Selective recovery

Git revision, working-tree/index patches and all original file hashes precede the refactor. No reset/commit or whole-project backup was made. `recovery_manifest.json` names pre-refactor hashes; originals without an archive field are in `changed_originals.tar.gz`, while explicitly named archives contain later-listed original metadata/documents. Recover only selected members after checking current edits and SHA-256. No historic experiment files were overwritten. `change_manifest.json` records modified/added files; no original source/schema/evaluation data was deleted.
