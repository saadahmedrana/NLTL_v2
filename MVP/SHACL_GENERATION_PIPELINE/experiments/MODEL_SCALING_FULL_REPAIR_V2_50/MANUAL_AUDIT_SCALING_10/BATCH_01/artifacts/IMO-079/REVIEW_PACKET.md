# IMO-079

Family: IMO
Complexity category: DIRECT_CALCULATION
Source: International Code for Ships Operating in Polar Waters (Polar Code)
Edition: Resolution MSC.385(94), adopted 21 Nov 2014; consolidated with MEPC.264(68), adopted 15 May 2015
Section: Part I-A Chapter 8 - Survival
Clause: 8.3.3.4
Page: 25

## Exact natural-language requirement

Adequate emergency rations shall be provided, for the maximum expected time of rescue.

## Relevant ontology context

Full context: rdf_cases/IMO-079/ontology_context.json

- availableEmergencyRationPerson: {"aliases": ["available_emergency_ration_person_days"], "datatype": null, "definition": "NORMALIZED (Stage 1): candidate concept for availableEmergencyRationPerson derived from the linked locked requirements; scope and final semantics require vocabulary approval.", "domains": ["https://w3id.org/nltl/vocab#benchmarkEntity"], "iri": "https://w3id.org/nltl/vocab#availableEmergencyRationPerson", "kind": "QuantityProperty", "label": "Available emergency ration person", "localName": "availableEmergencyRationPerson", "mappingStatus": "No exact current Haitham SSP local-name match", "module": "core", "namingBasis": "Unit-stripped normalized regulatory variable", "quantityKind": "Time", "range": "http://qudt.org/schema/qudt/QuantityValue", "recommendedUnit": "http://qudt.org/vocab/unit/DAY", "requiredOwner": "ship", "selectionReason": "linked by the locked 313-requirement index", "sourceReferences": "IMO-079 | IMO_POLAR_CODE p.25 | 8.3.3.4", "unitSymbol": "day"}
- benchmarkEntity: {"aliases": [], "datatype": null, "definition": "Locked ontology infrastructure term.", "domains": [], "iri": "https://w3id.org/nltl/vocab#benchmarkEntity", "kind": "Class", "label": "Benchmark entity", "localName": "benchmarkEntity", "mappingStatus": "Locked ontology term", "module": "ontology-infrastructure", "namingBasis": "Locked ontology infrastructure", "quantityKind": null, "range": "", "recommendedUnit": null, "requiredOwner": "ship", "selectionReason": "baseline target infrastructure; domain dependency of availableEmergencyRationPerson; domain dependency of maximumExpectedRescueTime; domain dependency of personsOnBoard", "sourceReferences": "Locked Stage 2 ontology", "unitSymbol": null}
- maximumExpectedRescueTime: {"aliases": ["maximum_expected_rescue_time_days"], "datatype": null, "definition": "NORMALIZED (Stage 1): candidate concept for maximumExpectedRescueTime derived from the linked locked requirements; scope and final semantics require vocabulary approval.", "domains": ["https://w3id.org/nltl/vocab#benchmarkEntity"], "iri": "https://w3id.org/nltl/vocab#maximumExpectedRescueTime", "kind": "QuantityProperty", "label": "Maximum expected rescue time", "localName": "maximumExpectedRescueTime", "mappingStatus": "No exact current Haitham SSP local-name match", "module": "tests", "namingBasis": "Unit-stripped normalized regulatory variable", "quantityKind": "Time", "range": "http://qudt.org/schema/qudt/QuantityValue", "recommendedUnit": "http://qudt.org/vocab/unit/DAY", "requiredOwner": "ship", "selectionReason": "linked by the locked 313-requirement index", "sourceReferences": "IMO-010 | IMO_POLAR_CODE p.13 | 1.2.7; IMO-020 | IMO_POLAR_CODE p.15 | 1.4.3; IMO-063 | IMO_POLAR_CODE p.23 | 8.2.2; IMO-065 | IMO_POLAR_CODE p.23-24 | 8.2.3.3; IMO-079 | IMO_POLAR_CODE p.25 | 8.3.3.4; IMO-093 | IMO_POLAR_CODE p.28 | 10.2.2.3; IMO-099 | IMO_POLAR_CODE p.29 | 10.3.2.3", "unitSymbol": "day"}
- personsOnBoard: {"aliases": ["persons_on_board"], "datatype": "xsd:integer", "definition": "NORMALIZED (Stage 1): candidate concept for personsOnBoard derived from the linked locked requirements; scope and final semantics require vocabulary approval.", "domains": ["https://w3id.org/nltl/vocab#benchmarkEntity"], "iri": "https://w3id.org/nltl/vocab#personsOnBoard", "kind": "DatatypeProperty", "label": "Persons on board", "localName": "personsOnBoard", "mappingStatus": "No exact current Haitham SSP local-name match", "module": "core", "namingBasis": "Locked-workbook normalized regulatory term", "quantityKind": null, "range": "http://www.w3.org/2001/XMLSchema#integer", "recommendedUnit": null, "requiredOwner": "ship", "selectionReason": "linked by the locked 313-requirement index", "sourceReferences": "IMO-075 | IMO_POLAR_CODE p.25 | 8.3.3.3.3.2; IMO-079 | IMO_POLAR_CODE p.25 | 8.3.3.4", "unitSymbol": null}
- ship: {"aliases": [], "datatype": null, "definition": "Locked ontology infrastructure term.", "domains": [], "iri": "https://w3id.org/nltl/vocab#ship", "kind": "Class", "label": "Ship", "localName": "ship", "mappingStatus": "Locked ontology term", "module": "ontology-infrastructure", "namingBasis": "Locked ontology infrastructure", "quantityKind": null, "range": "", "recommendedUnit": null, "requiredOwner": "ship", "selectionReason": "authoritative required owner class; authoritative requirement target owner; baseline target infrastructure", "sourceReferences": "Locked Stage 2 ontology", "unitSymbol": null}

## Frozen RDF cases

- IMO-079-H-F01: expected FAIL; `IMO-079-H-F01.ttl`
- IMO-079-H-F02: expected FAIL; `IMO-079-H-F02.ttl`
- IMO-079-H-F03: expected FAIL; `IMO-079-H-F03.ttl`
- IMO-079-H-F04: expected FAIL; `IMO-079-H-F04.ttl`
- IMO-079-H-F05: expected FAIL; `IMO-079-H-F05.ttl`
- IMO-079-H-P01: expected PASS; `IMO-079-H-P01.ttl`
- IMO-079-H-P02: expected PASS; `IMO-079-H-P02.ttl`
- IMO-079-H-P03: expected PASS; `IMO-079-H-P03.ttl`

## Blinded artifact slots

- A01: AVAILABLE; candidate SHA-256 a6fd7d64c195088814365a6ceab5ed763493267e68102643ba6112c8d94830f5
- A02: AVAILABLE; candidate SHA-256 4e9af331a580a0961d1f7eae47c418c0629acc5f2d95ece0754067c27fd72f72
- A03: AVAILABLE; candidate SHA-256 a6fd7d64c195088814365a6ceab5ed763493267e68102643ba6112c8d94830f5
- A04: AVAILABLE; candidate SHA-256 eeb814923fbeb2f2e8532430924493a4a554c2af1fb5c180ae24f32818473d1e
- A05: AVAILABLE; candidate SHA-256 eeb814923fbeb2f2e8532430924493a4a554c2af1fb5c180ae24f32818473d1e
- A06: AVAILABLE; candidate SHA-256 4e9af331a580a0961d1f7eae47c418c0629acc5f2d95ece0754067c27fd72f72
- A07: AVAILABLE; candidate SHA-256 2f61d760a1f65d5be110229dc6ed9a9b4ca32eabcd9af3de47be364559871673
- A08: AVAILABLE; candidate SHA-256 2f61d760a1f65d5be110229dc6ed9a9b4ca32eabcd9af3de47be364559871673

Score every slot in scoring_template.xlsx. Do not attempt to identify the system or processing stage.
