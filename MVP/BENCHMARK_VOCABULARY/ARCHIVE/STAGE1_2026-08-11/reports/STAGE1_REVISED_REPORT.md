# Journal 1 NL-to-SHACL Benchmark Vocabulary - Revised Stage 1

Date: 2026-08-11

## Outcome

This revision resolves the source-placement and engineering-policy issues raised during review. It remains a Stage 1 evidence workbook: no RDF/JSON-LD ontology, SHACL vocabulary profile, or benchmark ship graph has been emitted.

- 313 locked requirements remain fully covered.
- The shortlist was cleaned from 904 to **830 distinct concept candidates** by preventing short equation symbols from becoming standalone canonical concepts when their semantics were not established. Symbols remain aliases/evidence.
- All 830 proposed local names pass a strict ASCII lowerCamelCase check and are unique.
- The accepted activation boundary is retained: 240 direct/deterministic candidates, 40 Complex deferred, 17 Dynamic deferred, and 16 Physical Test evidence-only.
- The broken JSON-LD file is excluded from naming, definitions, namespaces, mappings, and compatibility authority.

## Source hierarchy resolved

1. `RELEVANT FILES/MSC.385(94).pdf` is now the current 59-page main Polar Code. It was moved from `OLD FILES/Haitham_Data` with user authorization. SHA-256: `6c6a038bff68ee906dd97c41e95fb4442917c014c8e79228f15e80cc5afa5c1f`.
2. `RELEVANT FILES/POLARCODES.pdf` remains the separate January 2026 supplement/amendment. It is not treated as the main code.
3. `INPUTS/Input_regulations_3Sources.xlsx` is now the current active locked workbook. It is byte-identical to the historical copy. SHA-256: `05eb02b0bce6fb7373329a92841a30171cd5c03c880ac570efbeb10b13700eaa`.
4. `OLD FILES` copies remain historical duplicates or implementation references only.
5. `RELEVANT FILES/BROKENONTOLOGYFROMGITHUB` remains physically present but is explicitly excluded.

“INPUTS had no active workbook” previously meant that the folder was empty except for `.DS_Store`. That issue is resolved by the byte-identical promotion above.

## Adopted engineering decisions

### Vocabulary and names

- One canonical master vocabulary with internal domains.
- Provisional vocabulary base: `https://w3id.org/nltl-benchmark/vocab#`.
- ASCII-only, unit-free lowerCamelCase local names.
- Original regulatory symbols, Haitham names, thesis names, and workbook variables remain aliases with provenance.
- Exact DNV, QUDT, or W3C mappings are accepted only when the complete URI/code is independently verified. Otherwise a consistent benchmark term is coined.
- Short or ambiguous formula symbols are not promoted merely through lexical similarity.

### Canonical RDF value model

The adopted future pattern is:

- engineering entity/component -> canonical property -> `qudt:QuantityValue` for measured quantities;
- engineering entity/component -> canonical property -> explicitly typed literal or controlled enumeration for Boolean, date, count, category, and status values;
- `sosa:Observation` for time-stamped/history-dependent information, with feature of interest, observed property, result, and result time;
- document, certificate, approval, survey, and test evidence represented as nodes with provenance rather than undifferentiated Boolean flags.

Haitham/Rana named singleton variables linked through `ssn:isPropertyOf` and `ssp:hasVariableValue` remain implementation compatibility evidence. They are not adopted as the canonical master pattern.

### Evidence lifecycle

Evidence and approval artifacts use the controlled states:

- Draft
- Submitted
- UnderReview
- Approved
- Rejected
- Expired
- Revoked

They also require, where applicable, issuing/approving authority, issue date, validity interval, scope, evidence target, source document, and provenance.

### Namespace policy

- Do not use `example.com` namespaces in the benchmark.
- Use `http://qudt.org/schema/qudt/` for the QUDT schema prefix and `http://qudt.org/vocab/unit/` for unit IRIs.
- Do not copy Haitham's malformed `http://qudt.org/2.1/schema/qudt` prefix expansion.
- Use the standard W3C RDF, RDFS, XSD, SHACL, SOSA/SSN, PROV, DCTERMS, and SKOS namespaces exactly.

## Remaining non-blocking review queue

Only three review items remain, none requiring an immediate user decision:

1. Register the provisional w3id redirect, or replace it with an institutional publication URI, before public release.
2. ISO 19848 normative definitions remain unavailable and are not claimed.
3. Low-confidence regulatory formula aliases require domain-expert confirmation before final URI emission. They have not been silently guessed.

The workbook's internal `216885...` predecessor hash is retained only as legacy provenance metadata. The directly verified active workbook hash `05eb02...` is used as the current file identity.

## Consistency checks

- Requirements covered: 313/313.
- Proposed local-name duplicates: 0.
- Invalid ASCII/lowerCamelCase proposed names: 0.
- Unit suffixes remaining in proposed local names: 0.
- Confirmed Haitham rule `ssp:` terms absent from confirmed ship graph: 0.
- Broken ontology terms adopted: 0.

Stage 2 should use only the revised workbook and should not use the earlier Stage 1 workbook as naming authority.
