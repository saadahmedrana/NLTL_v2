# IMO26-014

Family: IMO26
Complexity category: DIRECT_STATIC
Source: Polar Code January 2026 Supplement - Resolution MSC.538(107)
Edition: January 2026 Supplement; effective 1 Jan 2026
Section: Resolution MSC.538(107) - Chapter 9-1 regulations
Clause: 9-1.3.3
Page: 4

## Exact natural-language requirement

Ships, with the exception of those solely operating in areas with 24 hours daylight, shall be equipped with two means of illumination to aid visual detection of ice.

## Relevant ontology context

Full context: rdf_cases/IMO26-014/ontology_context.json

- benchmarkEntity: {"aliases": [], "datatype": null, "definition": "Locked ontology infrastructure term.", "domains": [], "iri": "https://w3id.org/nltl/vocab#benchmarkEntity", "kind": "Class", "label": "Benchmark entity", "localName": "benchmarkEntity", "mappingStatus": "Locked ontology term", "module": "ontology-infrastructure", "namingBasis": "Locked ontology infrastructure", "quantityKind": null, "range": "", "recommendedUnit": null, "requiredOwner": "ship", "selectionReason": "baseline target infrastructure; domain dependency of operatesOnlyInContinuousDaylight; domain dependency of visualIceDetectionIlluminationMeansCount", "sourceReferences": "Locked Stage 2 ontology", "unitSymbol": null}
- operatesOnlyInContinuousDaylight: {"aliases": ["solely_24_hour_daylight_operation"], "datatype": "xsd:boolean", "definition": "NORMALIZED (Stage 1): candidate concept for solely24HourDaylightOperation derived from the linked locked requirements; scope and final semantics require vocabulary approval.", "domains": ["https://w3id.org/nltl/vocab#benchmarkEntity"], "iri": "https://w3id.org/nltl/vocab#operatesOnlyInContinuousDaylight", "kind": "DatatypeProperty", "label": "Operates only in continuous daylight", "localName": "operatesOnlyInContinuousDaylight", "mappingStatus": "No exact current Haitham SSP local-name match", "module": "core", "namingBasis": "Locked-workbook normalized regulatory term", "quantityKind": null, "range": "http://www.w3.org/2001/XMLSchema#boolean", "recommendedUnit": null, "requiredOwner": "ship", "selectionReason": "linked by the locked 313-requirement index", "sourceReferences": "IMO-088 | IMO_POLAR_CODE p.27 | 9.3.3.1; IMO26-014 | IMO_AMEND_2026 p.4 | 9-1.3.3", "unitSymbol": null}
- ship: {"aliases": [], "datatype": null, "definition": "Locked ontology infrastructure term.", "domains": [], "iri": "https://w3id.org/nltl/vocab#ship", "kind": "Class", "label": "Ship", "localName": "ship", "mappingStatus": "Locked ontology term", "module": "ontology-infrastructure", "namingBasis": "Locked ontology infrastructure", "quantityKind": null, "range": "", "recommendedUnit": null, "requiredOwner": "ship", "selectionReason": "authoritative required owner class; authoritative requirement target owner; baseline target infrastructure", "sourceReferences": "Locked Stage 2 ontology", "unitSymbol": null}
- visualIceDetectionIlluminationMeansCount: {"aliases": ["visual_ice_detection_illumination_means_count"], "datatype": "xsd:integer", "definition": "NORMALIZED (Stage 1): candidate concept for visualIceDetectionIlluminationMeansCount derived from the linked locked requirements; scope and final semantics require vocabulary approval.", "domains": ["https://w3id.org/nltl/vocab#benchmarkEntity"], "iri": "https://w3id.org/nltl/vocab#visualIceDetectionIlluminationMeansCount", "kind": "DatatypeProperty", "label": "Visual ice detection illumination means count", "localName": "visualIceDetectionIlluminationMeansCount", "mappingStatus": "No exact current Haitham SSP local-name match", "module": "core", "namingBasis": "Locked-workbook normalized regulatory term", "quantityKind": null, "range": "http://www.w3.org/2001/XMLSchema#integer", "recommendedUnit": null, "requiredOwner": "ship", "selectionReason": "linked by the locked 313-requirement index", "sourceReferences": "IMO26-014 | IMO_AMEND_2026 p.4 | 9-1.3.3", "unitSymbol": null}

## Frozen RDF cases

- IMO26-014-A-F01: expected FAIL; `IMO26-014-A-F01.ttl`
- IMO26-014-A-F02: expected FAIL; `IMO26-014-A-F02.ttl`
- IMO26-014-A-F03: expected FAIL; `IMO26-014-A-F03.ttl`
- IMO26-014-A-F04: expected FAIL; `IMO26-014-A-F04.ttl`
- IMO26-014-A-P01: expected PASS; `IMO26-014-A-P01.ttl`
- IMO26-014-A-P02: expected PASS; `IMO26-014-A-P02.ttl`
- IMO26-014-A-P03: expected PASS; `IMO26-014-A-P03.ttl`

## Blinded artifact slots

- A01: AVAILABLE; candidate SHA-256 397bad0baad62e9f9b958f881aa3c1f983b8159d08540f310380338879717e9d
- A02: AVAILABLE; candidate SHA-256 397bad0baad62e9f9b958f881aa3c1f983b8159d08540f310380338879717e9d
- A03: AVAILABLE; candidate SHA-256 fdd925638941bb50d0c6322508b34358be11a7f0a64d36d6ff048ff037c9314b
- A04: UNPARSEABLE; candidate SHA-256 8268fcb7c53db91e2a3d1f77bb176348b754875904593efbab41c477e4148dd7
- A05: MISSING
- A06: MISSING
- A07: AVAILABLE; candidate SHA-256 4985df1e432ae43b3f393fbef7d4d0d142122ccaa987bcad0ed32edbe8dd2201
- A08: AVAILABLE; candidate SHA-256 4985df1e432ae43b3f393fbef7d4d0d142122ccaa987bcad0ed32edbe8dd2201

Score every slot in scoring_template.xlsx. Do not attempt to identify the system or processing stage.
