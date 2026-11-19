# I2-042: unresolved applicability decision

Decision: retain the pre-dispatch blocker. No interpretation or schema extension is implemented. Use the separate five-requirement development pilot until a representation decision is approved.

Authoritative evidence: `data/requirements/IACS_I2_full.txt`, I2.9.4(i), SHA-256 `7ad8d57459782b70809da479380584a57cf259c66d9ff286811c0248b02732d2`:

> To prevent local flange buckling of welded profiles, the following are to be satisfied:
> (i) The flange width, bf [mm], is not to be less than five times the net thickness of the web, twn.

Inspected bindings: `schema/Schema_for_NLTL.ttl`, `schema/term_registry.json`, `schema/locked_representation_context.jsonld`, and `data/contracts/requirement_term_index.json` (I2-042 dependency contract, termOwners, target owner and modelPaths). Also searched the original FINAL_LOCK_R13 machine-readable metadata for weldedProfile, welded_profile, fabricationMethod and profileFabrication. No explicit welded-profile selector/class/scoped-inventory binding was found. `structuralMember` is generic; `structuralSectionType` describes section geometry, not fabrication. `hasWeld` links ship weld records for I2.18.2, not structuralMember fabrication. Neither a broad domain nor those adjacent concepts establishes eligibility.

Proposed option, NOT IMPLEMENTED: a restricted welded-profile development scope. Explicitly declare that, for this requirement only, the supplied `hasStructuralMember` inventory contains exclusively source-applicable welded profiles, supported by an independent design/fabrication record. Eligibility must be checked outside the arithmetic rule, recorded with provenance for each input and fail closed when absent. This does not require a new ontology IRI, but DOES change the representation contract and data-admission policy. It must not be assumed merely because dimensions satisfy the formula or a section has a particular type.

Approval/migration decision still needed: accept that inventory-level restriction and define who certifies it, the authoritative fabrication record and its representation; or approve a versioned class/selector extension with owner/path, datatype/value semantics and missing/unknown policy. A mixed member inventory cannot use the restriction without a separate explicitly justified projection. Re-review all seven retained cases and four counterpart eligibility records against external provenance, rather than infer eligibility from their RDF dimensions. Until then, do not dispatch I2-042 or silently exclude/relabel its cases.

The six-requirement v0.3.0 manifest and all 37 historical core cases remain byte-identical. The new five-requirement selection has 30 cases (14 positive, 16 negative) plus 16 intended-only counterparts; I2-042 retains 7 deferred cases (3 positive, 4 negative) plus 4 counterparts. No fixture or ontology change is made.
