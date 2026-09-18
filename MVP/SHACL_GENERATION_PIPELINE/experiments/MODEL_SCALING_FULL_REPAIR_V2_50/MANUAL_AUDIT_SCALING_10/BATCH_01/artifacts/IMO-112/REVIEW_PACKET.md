# IMO-112

Family: IMO
Complexity category: DIRECT_STATIC
Source: International Code for Ships Operating in Polar Waters (Polar Code)
Edition: Resolution MSC.385(94), adopted 21 Nov 2014; consolidated with MEPC.264(68), adopted 15 May 2015
Section: Part II-A Chapter 2 - Noxious liquid substances
Clause: 2.1.1
Page: 42

## Exact natural-language requirement

In Arctic waters any discharge into the sea of noxious liquid substances (NLS), or mixtures containing such substances, shall be prohibited.

## Relevant ontology context

Full context: rdf_cases/IMO-112/ontology_context.json

- arcticWaters: {"aliases": ["Arctic_waters"], "datatype": "xsd:string", "definition": "NORMALIZED (Stage 1): candidate concept for arcticWaters derived from the linked locked requirements; scope and final semantics require vocabulary approval.", "domains": ["https://w3id.org/nltl/vocab#benchmarkEntity"], "iri": "https://w3id.org/nltl/vocab#arcticWaters", "kind": "DatatypeProperty", "label": "Arctic waters", "localName": "arcticWaters", "mappingStatus": "No exact current Haitham SSP local-name match", "module": "core", "namingBasis": "Benchmark-coined descriptive engineering term", "quantityKind": null, "range": "http://www.w3.org/2001/XMLSchema#string", "recommendedUnit": null, "requiredOwner": "ship", "selectionReason": "linked by the locked 313-requirement index", "sourceReferences": "IMO-105 | IMO_POLAR_CODE p.41 | 1.1.1; IMO-112 | IMO_POLAR_CODE p.42 | 2.1.1; IMO-120 | IMO_POLAR_CODE p.43 | 5.2.1.1", "unitSymbol": null}
- benchmarkEntity: {"aliases": [], "datatype": null, "definition": "Locked ontology infrastructure term.", "domains": [], "iri": "https://w3id.org/nltl/vocab#benchmarkEntity", "kind": "Class", "label": "Benchmark entity", "localName": "benchmarkEntity", "mappingStatus": "Locked ontology term", "module": "ontology-infrastructure", "namingBasis": "Locked ontology infrastructure", "quantityKind": null, "range": "", "recommendedUnit": null, "requiredOwner": "ship", "selectionReason": "baseline target infrastructure; domain dependency of arcticWaters; domain dependency of noxiousLiquidSubstanceOrNoxiousLiquidSubstanceMixtureDischargeToSea; domain dependency of operatingArea", "sourceReferences": "Locked Stage 2 ontology", "unitSymbol": null}
- noxiousLiquidSubstanceOrNoxiousLiquidSubstanceMixtureDischargeToSea: {"aliases": ["NLS_or_NLS_mixture_discharge_to_sea"], "datatype": "xsd:boolean", "definition": "NORMALIZED (Stage 1): candidate concept for noxiousLiquidSubstanceOrNoxiousLiquidSubstanceMixtureDischargeToSea derived from the linked locked requirements; scope and final semantics require vocabulary approval.", "domains": ["https://w3id.org/nltl/vocab#benchmarkEntity"], "iri": "https://w3id.org/nltl/vocab#noxiousLiquidSubstanceOrNoxiousLiquidSubstanceMixtureDischargeToSea", "kind": "DatatypeProperty", "label": "Noxious liquid substance or noxious liquid substance mixture discharge to sea", "localName": "noxiousLiquidSubstanceOrNoxiousLiquidSubstanceMixtureDischargeToSea", "mappingStatus": "No exact current Haitham SSP local-name match", "module": "core", "namingBasis": "Locked-workbook normalized regulatory term", "quantityKind": null, "range": "http://www.w3.org/2001/XMLSchema#boolean", "recommendedUnit": null, "requiredOwner": "ship", "selectionReason": "linked by the locked 313-requirement index", "sourceReferences": "IMO-112 | IMO_POLAR_CODE p.42 | 2.1.1", "unitSymbol": null}
- operatingArea: {"aliases": ["operating_area"], "datatype": "xsd:string", "definition": "NORMALIZED (Stage 1): candidate concept for operatingArea derived from the linked locked requirements; scope and final semantics require vocabulary approval.", "domains": ["https://w3id.org/nltl/vocab#benchmarkEntity"], "iri": "https://w3id.org/nltl/vocab#operatingArea", "kind": "DatatypeProperty", "label": "Operating area", "localName": "operatingArea", "mappingStatus": "No exact current Haitham SSP local-name match", "module": "operations", "namingBasis": "Locked-workbook normalized regulatory term", "quantityKind": null, "range": "http://www.w3.org/2001/XMLSchema#string", "recommendedUnit": null, "requiredOwner": "ship", "selectionReason": "linked by the locked 313-requirement index", "sourceReferences": "IMO-080 | IMO_POLAR_CODE p.26 | 9.3.1; IMO-105 | IMO_POLAR_CODE p.41 | 1.1.1; IMO-112 | IMO_POLAR_CODE p.42 | 2.1.1; IMO-120 | IMO_POLAR_CODE p.43 | 5.2.1.1; IMO-124 | IMO_POLAR_CODE p.44 | 5.2.2.1-.2; IMO26-006 | IMO_AMEND_2026 p.3 | 9-1.3.1", "unitSymbol": null}
- ship: {"aliases": [], "datatype": null, "definition": "Locked ontology infrastructure term.", "domains": [], "iri": "https://w3id.org/nltl/vocab#ship", "kind": "Class", "label": "Ship", "localName": "ship", "mappingStatus": "Locked ontology term", "module": "ontology-infrastructure", "namingBasis": "Locked ontology infrastructure", "quantityKind": null, "range": "", "recommendedUnit": null, "requiredOwner": "ship", "selectionReason": "authoritative required owner class; authoritative requirement target owner; baseline target infrastructure", "sourceReferences": "Locked Stage 2 ontology", "unitSymbol": null}

## Frozen RDF cases

- IMO-112-M-F01: expected FAIL; `IMO-112-M-F01.ttl`
- IMO-112-M-F02: expected FAIL; `IMO-112-M-F02.ttl`
- IMO-112-M-F03: expected FAIL; `IMO-112-M-F03.ttl`
- IMO-112-M-P01: expected PASS; `IMO-112-M-P01.ttl`
- IMO-112-M-P02: expected PASS; `IMO-112-M-P02.ttl`

## Blinded artifact slots

- A01: AVAILABLE; candidate SHA-256 62256f65b580cfffbcb70f26939faab5bb493e1d95795f232ffae61721fe34b5
- A02: AVAILABLE; candidate SHA-256 75712f7ef328284be881fd774b54ccc4b4fb0ff60eaf6dfb6eb91c8def44ee24
- A03: MISSING
- A04: AVAILABLE; candidate SHA-256 75712f7ef328284be881fd774b54ccc4b4fb0ff60eaf6dfb6eb91c8def44ee24
- A05: MISSING
- A06: AVAILABLE; candidate SHA-256 ec1291de58cbfea6ceabe2023262915f43ca824c62e942e6319d89fa091c3235
- A07: MISSING
- A08: AVAILABLE; candidate SHA-256 bb1324f47058bae4ff426c381b5ca93a7866377e6dde2e929be6c9da2b548151

Score every slot in scoring_template.xlsx. Do not attempt to identify the system or processing stage.
