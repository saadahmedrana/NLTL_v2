#!/usr/bin/env python3

import json
import shutil
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, RDFS


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
REGISTRY_PATH = PROJECT / "BENCHMARK_VOCABULARY/STAGE2/registry/term_registry.json"
ONTOLOGY_PATH = PROJECT / "BENCHMARK_VOCABULARY/STAGE2/ontology/nltl_benchmark_vocabulary.ttl"
CASES_ROOT = ROOT / "cases"
NLTL = "https://w3id.org/nltl/vocab#"

PREFIX_IRIS = {
    "dct": "http://purl.org/dc/terms/",
    "fs": "urn:nltl:few-shot:",
    "nltl": NLTL,
    "qudt": "http://qudt.org/schema/qudt/",
    "sh": "http://www.w3.org/ns/shacl#",
    "sosa": "http://www.w3.org/ns/sosa/",
    "unit": "http://qudt.org/vocab/unit/",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}


def turtle(prefixes, body):
    header = "\n".join(f"@prefix {prefix}: <{PREFIX_IRIS[prefix]}> ." for prefix in prefixes)
    return f"{header}\n\n{body.strip()}\n"


def shape(target_class, body):
    return f"""
fs:Shape a sh:NodeShape ;
    sh:targetClass nltl:{target_class} ;
{body.rstrip()}
"""


def scalar_shape(target_class, property_name, datatype, extra):
    return shape(
        target_class,
        f"""    sh:property [
        sh:path nltl:{property_name} ;
        sh:datatype xsd:{datatype} ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        {extra}
    ] .""",
    )


def quantity_shape(target_class, property_name, unit_name, numeric_constraint):
    return shape(
        target_class,
        f"""    sh:property [
        sh:path nltl:{property_name} ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:node [
            sh:class qudt:QuantityValue ;
            sh:property [
                sh:path qudt:numericValue ;
                sh:datatype xsd:decimal ;
                sh:minCount 1 ;
                sh:maxCount 1 ;
                {numeric_constraint}
            ] ;
            sh:property [
                sh:path qudt:unit ;
                sh:hasValue unit:{unit_name} ;
                sh:minCount 1 ;
                sh:maxCount 1
            ]
        ]
    ] .""",
    )


EXAMPLES = [
    {
        "id": "FS-BOOL-01",
        "case_number": "01",
        "case_id": "boolean_state",
        "slug": "polar_manual_required",
        "title": "Required Boolean state: polar manual",
        "requirement": "Synthetic rule: Every ship in this example shall record that a Polar Water Operational Manual is present.",
        "tags": ["boolean", "required-value", "cardinality"],
        "vocab": ["ship", "polarWaterOperationalManualPresent"],
        "negative_vocab": [],
        "shape": turtle(
            ["fs", "nltl", "sh", "xsd"],
            scalar_shape("ship", "polarWaterOperationalManualPresent", "boolean", "sh:hasValue true"),
        ),
        "pass": turtle(
            ["fs", "nltl", "xsd"],
            'fs:shipPass a nltl:ship ;\n    nltl:polarWaterOperationalManualPresent "true"^^xsd:boolean .',
        ),
        "fail": turtle(
            ["fs", "nltl", "xsd"],
            'fs:shipFail a nltl:ship ;\n    nltl:polarWaterOperationalManualPresent "false"^^xsd:boolean .',
        ),
    },
    {
        "id": "FS-BOOL-02",
        "case_number": "01",
        "case_id": "boolean_state",
        "slug": "bridge_wings_enclosed",
        "title": "Required Boolean state: enclosed bridge wings",
        "requirement": "Synthetic rule: Every ship in this example shall record that its bridge wings are enclosed.",
        "tags": ["boolean", "required-value", "cardinality"],
        "vocab": ["ship", "bridgeWingsEnclosed"],
        "negative_vocab": [],
        "shape": turtle(
            ["fs", "nltl", "sh", "xsd"],
            scalar_shape("ship", "bridgeWingsEnclosed", "boolean", "sh:hasValue true"),
        ),
        "pass": turtle(
            ["fs", "nltl", "xsd"],
            'fs:shipPass a nltl:ship ;\n    nltl:bridgeWingsEnclosed "true"^^xsd:boolean .',
        ),
        "fail": turtle(
            ["fs", "nltl", "xsd"],
            'fs:shipFail a nltl:ship ;\n    nltl:bridgeWingsEnclosed "false"^^xsd:boolean .',
        ),
    },
    {
        "id": "FS-SCALAR-01",
        "case_number": "02",
        "case_id": "typed_scalar",
        "slug": "echo_sounder_count",
        "title": "Typed integer with a minimum",
        "requirement": "Synthetic rule: Every ship in this example shall have at least two echo-sounding devices.",
        "tags": ["integer", "minimum", "cardinality"],
        "vocab": ["ship", "echoSoundingDeviceCount"],
        "negative_vocab": [],
        "shape": turtle(
            ["fs", "nltl", "sh", "xsd"],
            scalar_shape("ship", "echoSoundingDeviceCount", "integer", "sh:minInclusive 2"),
        ),
        "pass": turtle(
            ["fs", "nltl", "xsd"],
            'fs:shipPass a nltl:ship ;\n    nltl:echoSoundingDeviceCount "2"^^xsd:integer .',
        ),
        "fail": turtle(
            ["fs", "nltl", "xsd"],
            'fs:shipFail a nltl:ship ;\n    nltl:echoSoundingDeviceCount "1"^^xsd:integer .',
        ),
    },
    {
        "id": "FS-SCALAR-02",
        "case_number": "02",
        "case_id": "typed_scalar",
        "slug": "construction_date_type",
        "title": "Required date datatype",
        "requirement": "Synthetic rule: Every ship in this example shall have exactly one construction date encoded as xsd:date.",
        "tags": ["date", "datatype", "cardinality"],
        "vocab": ["ship", "constructionDate"],
        "negative_vocab": [],
        "shape": turtle(
            ["fs", "nltl", "sh", "xsd"],
            scalar_shape("ship", "constructionDate", "date", 'sh:message "constructionDate must be one xsd:date value"'),
        ),
        "pass": turtle(
            ["fs", "nltl", "xsd"],
            'fs:shipPass a nltl:ship ;\n    nltl:constructionDate "2022-04-18"^^xsd:date .',
        ),
        "fail": turtle(
            ["fs", "nltl", "xsd"],
            'fs:shipFail a nltl:ship ;\n    nltl:constructionDate "2022-04-18"^^xsd:string .',
        ),
    },
    {
        "id": "FS-QTY-01",
        "case_number": "03",
        "case_id": "qudt_quantity",
        "slug": "length_overall_threshold",
        "title": "QUDT length quantity with threshold",
        "requirement": "Synthetic rule: Every ship in this example shall have a length overall of at least 70 metres.",
        "tags": ["quantity", "qudt", "unit", "threshold"],
        "vocab": ["ship", "lengthOverall"],
        "negative_vocab": [],
        "shape": turtle(
            ["fs", "nltl", "qudt", "sh", "unit", "xsd"],
            quantity_shape("ship", "lengthOverall", "M", 'sh:minInclusive "70"^^xsd:decimal'),
        ),
        "pass": turtle(
            ["fs", "nltl", "qudt", "unit", "xsd"],
            'fs:shipPass a nltl:ship ;\n    nltl:lengthOverall [\n        a qudt:QuantityValue ;\n        qudt:numericValue "75"^^xsd:decimal ;\n        qudt:unit unit:M\n    ] .',
        ),
        "fail": turtle(
            ["fs", "nltl", "qudt", "unit", "xsd"],
            'fs:shipFail a nltl:ship ;\n    nltl:lengthOverall [\n        a qudt:QuantityValue ;\n        qudt:numericValue "55"^^xsd:decimal ;\n        qudt:unit unit:M\n    ] .',
        ),
    },
    {
        "id": "FS-QTY-02",
        "case_number": "03",
        "case_id": "qudt_quantity",
        "slug": "mcr_power_unit",
        "title": "QUDT power quantity with canonical unit",
        "requirement": "Synthetic rule: Every ship in this example shall record at least 1,200 kilowatts of maximum continuous rating power, using the canonical kilowatt unit.",
        "tags": ["quantity", "qudt", "unit", "threshold"],
        "vocab": ["ship", "maximumContinuousRatingPower"],
        "negative_vocab": [],
        "shape": turtle(
            ["fs", "nltl", "qudt", "sh", "unit", "xsd"],
            quantity_shape("ship", "maximumContinuousRatingPower", "KiloW", 'sh:minInclusive "1200"^^xsd:decimal'),
        ),
        "pass": turtle(
            ["fs", "nltl", "qudt", "unit", "xsd"],
            'fs:shipPass a nltl:ship ;\n    nltl:maximumContinuousRatingPower [\n        a qudt:QuantityValue ;\n        qudt:numericValue "1500"^^xsd:decimal ;\n        qudt:unit unit:KiloW\n    ] .',
        ),
        "fail": turtle(
            ["fs", "nltl", "qudt", "unit", "xsd"],
            'fs:shipFail a nltl:ship ;\n    nltl:maximumContinuousRatingPower [\n        a qudt:QuantityValue ;\n        qudt:numericValue "1500"^^xsd:decimal ;\n        qudt:unit unit:W\n    ] .',
        ),
    },
    {
        "id": "FS-REL-01",
        "case_number": "04",
        "case_id": "entity_relation",
        "slug": "emergency_power_relation",
        "title": "Required relation to an emergency-power entity",
        "requirement": "Synthetic rule: Every ship component in this example shall link to exactly one benchmark entity through connectedToEmergencyPower.",
        "tags": ["object-property", "relation", "iri", "class"],
        "vocab": ["shipComponent", "benchmarkEntity", "connectedToEmergencyPower"],
        "negative_vocab": [],
        "shape": turtle(
            ["fs", "nltl", "sh"],
            shape(
                "shipComponent",
                '''    sh:property [
        sh:path nltl:connectedToEmergencyPower ;
        sh:nodeKind sh:IRI ;
        sh:class nltl:benchmarkEntity ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] .''',
            ),
        ),
        "pass": turtle(
            ["fs", "nltl"],
            "fs:componentPass a nltl:shipComponent ;\n    nltl:connectedToEmergencyPower fs:emergencyBus .\n\nfs:emergencyBus a nltl:benchmarkEntity .",
        ),
        "fail": turtle(
            ["fs", "nltl"],
            "fs:componentFail a nltl:shipComponent .",
        ),
    },
    {
        "id": "FS-REL-02",
        "case_number": "04",
        "case_id": "entity_relation",
        "slug": "structural_connection_relation",
        "title": "Hull structural connection as an IRI relation",
        "requirement": "Synthetic rule: Every hull structure in this example shall identify at least one structural connection as an IRI referring to a benchmark entity.",
        "tags": ["object-property", "relation", "iri", "class"],
        "vocab": ["hullStructure", "benchmarkEntity", "structuralConnection"],
        "negative_vocab": [],
        "shape": turtle(
            ["fs", "nltl", "sh"],
            shape(
                "hullStructure",
                """    sh:property [
        sh:path nltl:structuralConnection ;
        sh:nodeKind sh:IRI ;
        sh:class nltl:benchmarkEntity ;
        sh:minCount 1
    ] .""",
            ),
        ),
        "pass": turtle(
            ["fs", "nltl"],
            "fs:hullPass a nltl:hullStructure ;\n    nltl:structuralConnection fs:jointOne .\n\nfs:jointOne a nltl:benchmarkEntity .",
        ),
        "fail": turtle(
            ["fs", "nltl"],
            'fs:hullFail a nltl:hullStructure ;\n    nltl:structuralConnection "joint one" .',
        ),
    },
    {
        "id": "FS-CTRL-01",
        "case_number": "05",
        "case_id": "controlled_value",
        "slug": "polar_ship_category",
        "title": "Controlled IMO polar ship category",
        "requirement": "Synthetic rule: A ship in this example shall use Category A or Category B as its controlled polar ship category.",
        "tags": ["controlled-value", "iri", "enumeration"],
        "vocab": ["ship", "shipCategory", "polarShipCategoryA", "polarShipCategoryB"],
        "negative_vocab": ["polarShipCategoryC"],
        "shape": turtle(
            ["fs", "nltl", "sh"],
            shape(
                "ship",
                """    sh:property [
        sh:path nltl:shipCategory ;
        sh:nodeKind sh:IRI ;
        sh:in ( nltl:polarShipCategoryA nltl:polarShipCategoryB ) ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] .""",
            ),
        ),
        "pass": turtle(
            ["fs", "nltl"],
            "fs:shipPass a nltl:ship ;\n    nltl:shipCategory nltl:polarShipCategoryA .",
        ),
        "fail": turtle(
            ["fs", "nltl"],
            "fs:shipFail a nltl:ship ;\n    nltl:shipCategory nltl:polarShipCategoryC .",
        ),
    },
    {
        "id": "FS-CTRL-02",
        "case_number": "05",
        "case_id": "controlled_value",
        "slug": "finnish_swedish_ice_class",
        "title": "Controlled Finnish-Swedish ice class",
        "requirement": "Synthetic rule: A ship in this example shall use IA Super, IA, or IB as its controlled Finnish-Swedish ice class.",
        "tags": ["controlled-value", "iri", "enumeration"],
        "vocab": ["ship", "iceClass", "iceClassIaSuper", "iceClassIa", "iceClassIb"],
        "negative_vocab": ["iceClassIii"],
        "shape": turtle(
            ["fs", "nltl", "sh"],
            shape(
                "ship",
                """    sh:property [
        sh:path nltl:iceClass ;
        sh:nodeKind sh:IRI ;
        sh:in ( nltl:iceClassIaSuper nltl:iceClassIa nltl:iceClassIb ) ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] .""",
            ),
        ),
        "pass": turtle(
            ["fs", "nltl"],
            "fs:shipPass a nltl:ship ;\n    nltl:iceClass nltl:iceClassIa .",
        ),
        "fail": turtle(
            ["fs", "nltl"],
            "fs:shipFail a nltl:ship ;\n    nltl:iceClass nltl:iceClassIii .",
        ),
    },
    {
        "id": "FS-DOC-01",
        "case_number": "06",
        "case_id": "document_approval_evidence",
        "slug": "material_approval_state",
        "title": "Approval state as a controlled IRI",
        "requirement": "Synthetic rule: Each ship component in this example shall have an approved material approval status.",
        "tags": ["approval", "evidence-state", "controlled-value"],
        "vocab": ["shipComponent", "materialApprovalStatus", "evidenceStateApproved"],
        "negative_vocab": ["evidenceStateUnderReview"],
        "shape": turtle(
            ["fs", "nltl", "sh"],
            shape(
                "shipComponent",
                """    sh:property [
        sh:path nltl:materialApprovalStatus ;
        sh:nodeKind sh:IRI ;
        sh:hasValue nltl:evidenceStateApproved ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] .""",
            ),
        ),
        "pass": turtle(
            ["fs", "nltl"],
            "fs:componentPass a nltl:shipComponent ;\n    nltl:materialApprovalStatus nltl:evidenceStateApproved .",
        ),
        "fail": turtle(
            ["fs", "nltl"],
            "fs:componentFail a nltl:shipComponent ;\n    nltl:materialApprovalStatus nltl:evidenceStateUnderReview .",
        ),
    },
    {
        "id": "FS-DOC-02",
        "case_number": "06",
        "case_id": "document_approval_evidence",
        "slug": "approved_certificate_evidence",
        "title": "Approved certificate evidence node",
        "requirement": "Synthetic rule: Every ship in this example shall link to one Polar Ship Certificate Form evidence node with a source and Approved lifecycle state.",
        "tags": ["document", "certificate", "evidence-node", "provenance", "approval"],
        "vocab": ["ship", "hasEvidence", "polarShipCertificateForm", "hasEvidenceState", "evidenceStateApproved"],
        "negative_vocab": ["evidenceStateDraft"],
        "shape": turtle(
            ["dct", "fs", "nltl", "sh"],
            shape(
                "ship",
                """    sh:property [
        sh:path nltl:hasEvidence ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:node [
            sh:class nltl:polarShipCertificateForm ;
            sh:property [
                sh:path dct:source ;
                sh:nodeKind sh:IRI ;
                sh:minCount 1 ;
                sh:maxCount 1
            ] ;
            sh:property [
                sh:path nltl:hasEvidenceState ;
                sh:hasValue nltl:evidenceStateApproved ;
                sh:minCount 1 ;
                sh:maxCount 1
            ]
        ]
    ] .""",
            ),
        ),
        "pass": turtle(
            ["dct", "fs", "nltl"],
            "fs:shipPass a nltl:ship ;\n    nltl:hasEvidence fs:certificateEvidence .\n\nfs:certificateEvidence a nltl:polarShipCertificateForm ;\n    dct:source fs:certificateRecord ;\n    nltl:hasEvidenceState nltl:evidenceStateApproved .",
        ),
        "fail": turtle(
            ["dct", "fs", "nltl"],
            "fs:shipFail a nltl:ship ;\n    nltl:hasEvidence fs:certificateEvidence .\n\nfs:certificateEvidence a nltl:polarShipCertificateForm ;\n    dct:source fs:certificateRecord ;\n    nltl:hasEvidenceState nltl:evidenceStateDraft .",
        ),
    },
    {
        "id": "FS-OBS-01",
        "case_number": "07",
        "case_id": "sosa_observation_history",
        "slug": "working_liquid_observation",
        "title": "Single SOSA observation with a simple result",
        "requirement": "Synthetic rule: Every ship in this example shall have one timestamped SOSA observation of its working liquid, with a string result.",
        "tags": ["sosa", "observation", "time", "simple-result"],
        "vocab": ["ship", "hasObservation", "workingLiquid"],
        "negative_vocab": [],
        "shape": turtle(
            ["fs", "nltl", "sh", "sosa", "xsd"],
            shape(
                "ship",
                """    sh:property [
        sh:path nltl:hasObservation ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:node [
            sh:class sosa:Observation ;
            sh:property [
                sh:path sosa:hasFeatureOfInterest ;
                sh:nodeKind sh:IRI ;
                sh:minCount 1 ;
                sh:maxCount 1
            ] ;
            sh:property [
                sh:path sosa:observedProperty ;
                sh:hasValue nltl:workingLiquid ;
                sh:minCount 1 ;
                sh:maxCount 1
            ] ;
            sh:property [
                sh:path sosa:resultTime ;
                sh:datatype xsd:dateTime ;
                sh:minCount 1 ;
                sh:maxCount 1
            ] ;
            sh:property [
                sh:path sosa:hasSimpleResult ;
                sh:datatype xsd:string ;
                sh:minCount 1 ;
                sh:maxCount 1
            ]
        ]
    ] .""",
            ),
        ),
        "pass": turtle(
            ["fs", "nltl", "sosa", "xsd"],
            'fs:shipPass a nltl:ship ;\n    nltl:hasObservation fs:observationOne .\n\nfs:observationOne a sosa:Observation ;\n    sosa:hasFeatureOfInterest fs:shipPass ;\n    sosa:observedProperty nltl:workingLiquid ;\n    sosa:resultTime "2026-02-12T08:30:00Z"^^xsd:dateTime ;\n    sosa:hasSimpleResult "hydraulic oil"^^xsd:string .',
        ),
        "fail": turtle(
            ["fs", "nltl", "sosa", "xsd"],
            'fs:shipFail a nltl:ship ;\n    nltl:hasObservation fs:observationOne .\n\nfs:observationOne a sosa:Observation ;\n    sosa:hasFeatureOfInterest fs:shipFail ;\n    sosa:observedProperty nltl:workingLiquid ;\n    sosa:resultTime "2026-02-12 08:30"^^xsd:string ;\n    sosa:hasSimpleResult "hydraulic oil"^^xsd:string .',
        ),
    },
    {
        "id": "FS-OBS-02",
        "case_number": "07",
        "case_id": "sosa_observation_history",
        "slug": "temperature_history",
        "title": "SOSA observation history with QUDT results",
        "requirement": "Synthetic rule: Every ship in this example shall provide at least two timestamped daily-low-temperature observations, each recorded as a QUDT degree-Celsius quantity.",
        "tags": ["sosa", "history", "time", "quantity", "qudt"],
        "vocab": ["ship", "hasObservation", "dailyLowTemperature"],
        "negative_vocab": [],
        "shape": turtle(
            ["fs", "nltl", "qudt", "sh", "sosa", "unit", "xsd"],
            shape(
                "ship",
                """    sh:property [
        sh:path nltl:hasObservation ;
        sh:minCount 2 ;
        sh:node [
            sh:class sosa:Observation ;
            sh:property [
                sh:path sosa:hasFeatureOfInterest ;
                sh:nodeKind sh:IRI ;
                sh:minCount 1 ;
                sh:maxCount 1
            ] ;
            sh:property [
                sh:path sosa:observedProperty ;
                sh:hasValue nltl:dailyLowTemperature ;
                sh:minCount 1 ;
                sh:maxCount 1
            ] ;
            sh:property [
                sh:path sosa:resultTime ;
                sh:datatype xsd:dateTime ;
                sh:minCount 1 ;
                sh:maxCount 1
            ] ;
            sh:property [
                sh:path sosa:hasResult ;
                sh:minCount 1 ;
                sh:maxCount 1 ;
                sh:node [
                    sh:class qudt:QuantityValue ;
                    sh:property [
                        sh:path qudt:numericValue ;
                        sh:datatype xsd:decimal ;
                        sh:minCount 1 ;
                        sh:maxCount 1
                    ] ;
                    sh:property [
                        sh:path qudt:unit ;
                        sh:hasValue unit:DEG_C ;
                        sh:minCount 1 ;
                        sh:maxCount 1
                    ]
                ]
            ]
        ]
    ] .""",
            ),
        ),
        "pass": turtle(
            ["fs", "nltl", "qudt", "sosa", "unit", "xsd"],
            'fs:shipPass a nltl:ship ;\n    nltl:hasObservation fs:observationOne, fs:observationTwo .\n\nfs:observationOne a sosa:Observation ;\n    sosa:hasFeatureOfInterest fs:shipPass ;\n    sosa:observedProperty nltl:dailyLowTemperature ;\n    sosa:resultTime "2026-01-10T00:00:00Z"^^xsd:dateTime ;\n    sosa:hasResult [ a qudt:QuantityValue ; qudt:numericValue "-18"^^xsd:decimal ; qudt:unit unit:DEG_C ] .\n\nfs:observationTwo a sosa:Observation ;\n    sosa:hasFeatureOfInterest fs:shipPass ;\n    sosa:observedProperty nltl:dailyLowTemperature ;\n    sosa:resultTime "2026-01-11T00:00:00Z"^^xsd:dateTime ;\n    sosa:hasResult [ a qudt:QuantityValue ; qudt:numericValue "-21"^^xsd:decimal ; qudt:unit unit:DEG_C ] .',
        ),
        "fail": turtle(
            ["fs", "nltl", "qudt", "sosa", "unit", "xsd"],
            'fs:shipFail a nltl:ship ;\n    nltl:hasObservation fs:observationOne .\n\nfs:observationOne a sosa:Observation ;\n    sosa:hasFeatureOfInterest fs:shipFail ;\n    sosa:observedProperty nltl:dailyLowTemperature ;\n    sosa:resultTime "2026-01-10T00:00:00Z"^^xsd:dateTime ;\n    sosa:hasResult [ a qudt:QuantityValue ; qudt:numericValue "-18"^^xsd:decimal ; qudt:unit unit:DEG_C ] .',
        ),
    },
    {
        "id": "FS-TEST-01",
        "case_number": "08",
        "case_id": "physical_test_evidence",
        "slug": "winter_clothing_operability_test",
        "title": "Required physical-test result state",
        "requirement": "Synthetic rule: Every watertight or weathertight closing device in this example shall have a successful winter-clothing operability test status.",
        "tags": ["physical-test", "boolean", "target-class"],
        "vocab": ["watertightOrWeathertightClosingDevice", "winterClothingOperabilityTestStatus"],
        "negative_vocab": [],
        "shape": turtle(
            ["fs", "nltl", "sh", "xsd"],
            scalar_shape("watertightOrWeathertightClosingDevice", "winterClothingOperabilityTestStatus", "boolean", "sh:hasValue true"),
        ),
        "pass": turtle(
            ["fs", "nltl", "xsd"],
            'fs:devicePass a nltl:watertightOrWeathertightClosingDevice ;\n    nltl:winterClothingOperabilityTestStatus "true"^^xsd:boolean .',
        ),
        "fail": turtle(
            ["fs", "nltl", "xsd"],
            'fs:deviceFail a nltl:watertightOrWeathertightClosingDevice ;\n    nltl:winterClothingOperabilityTestStatus "false"^^xsd:boolean .',
        ),
    },
    {
        "id": "FS-TEST-02",
        "case_number": "08",
        "case_id": "physical_test_evidence",
        "slug": "approved_model_test_evidence",
        "title": "Physical-test evidence node with provenance",
        "requirement": "Synthetic rule: Every ship in this example shall link to one approved model-test evidence node that identifies its source record.",
        "tags": ["physical-test", "evidence-node", "provenance", "approval"],
        "vocab": ["ship", "hasEvidence", "modelTestEvidence", "hasEvidenceState", "evidenceStateApproved"],
        "negative_vocab": [],
        "shape": turtle(
            ["dct", "fs", "nltl", "sh"],
            shape(
                "ship",
                """    sh:property [
        sh:path nltl:hasEvidence ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:node [
            sh:class nltl:modelTestEvidence ;
            sh:property [
                sh:path dct:source ;
                sh:nodeKind sh:IRI ;
                sh:minCount 1 ;
                sh:maxCount 1
            ] ;
            sh:property [
                sh:path nltl:hasEvidenceState ;
                sh:hasValue nltl:evidenceStateApproved ;
                sh:minCount 1 ;
                sh:maxCount 1
            ]
        ]
    ] .""",
            ),
        ),
        "pass": turtle(
            ["dct", "fs", "nltl"],
            "fs:shipPass a nltl:ship ;\n    nltl:hasEvidence fs:modelTestEvidence .\n\nfs:modelTestEvidence a nltl:modelTestEvidence ;\n    dct:source fs:modelTestRecord ;\n    nltl:hasEvidenceState nltl:evidenceStateApproved .",
        ),
        "fail": turtle(
            ["fs", "nltl"],
            "fs:shipFail a nltl:ship ;\n    nltl:hasEvidence fs:modelTestEvidence .\n\nfs:modelTestEvidence a nltl:modelTestEvidence ;\n    nltl:hasEvidenceState nltl:evidenceStateApproved .",
        ),
    },
    {
        "id": "FS-CALC-01",
        "case_number": "09",
        "case_id": "comparison_calculation",
        "slug": "capacity_comparison",
        "title": "Cross-property numeric comparison",
        "requirement": "Synthetic rule: For each ship in this example, persons on board shall not exceed the available survival-equipment capacity.",
        "tags": ["comparison", "cross-property", "integer"],
        "vocab": ["ship", "personsOnBoard", "availableSurvivalEquipmentCapacity"],
        "negative_vocab": [],
        "shape": turtle(
            ["fs", "nltl", "sh", "xsd"],
            shape(
                "ship",
                """    sh:property [
        sh:path nltl:personsOnBoard ;
        sh:datatype xsd:integer ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:lessThanOrEquals nltl:availableSurvivalEquipmentCapacity
    ] ;
    sh:property [
        sh:path nltl:availableSurvivalEquipmentCapacity ;
        sh:datatype xsd:integer ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] .""",
            ),
        ),
        "pass": turtle(
            ["fs", "nltl", "xsd"],
            'fs:shipPass a nltl:ship ;\n    nltl:personsOnBoard "40"^^xsd:integer ;\n    nltl:availableSurvivalEquipmentCapacity "44"^^xsd:integer .',
        ),
        "fail": turtle(
            ["fs", "nltl", "xsd"],
            'fs:shipFail a nltl:ship ;\n    nltl:personsOnBoard "60"^^xsd:integer ;\n    nltl:availableSurvivalEquipmentCapacity "50"^^xsd:integer .',
        ),
    },
    {
        "id": "FS-CALC-02",
        "case_number": "09",
        "case_id": "comparison_calculation",
        "slug": "capacity_sum_formula",
        "title": "Derived integer sum using SHACL-SPARQL",
        "requirement": "Synthetic rule: For each ship in this example, personsCapacityRequirement shall equal personsOnBoard plus additionalEquipmentCapacityRequirement.",
        "tags": ["calculation", "formula", "sparql", "integer"],
        "vocab": ["ship", "personsOnBoard", "additionalEquipmentCapacityRequirement", "personsCapacityRequirement"],
        "negative_vocab": [],
        "shape": turtle(
            ["fs", "nltl", "sh", "xsd"],
            shape(
                "ship",
                '''    sh:property [
        sh:path nltl:personsOnBoard ;
        sh:datatype xsd:integer ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] ;
    sh:property [
        sh:path nltl:additionalEquipmentCapacityRequirement ;
        sh:datatype xsd:integer ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] ;
    sh:property [
        sh:path nltl:personsCapacityRequirement ;
        sh:datatype xsd:integer ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] ;
    sh:sparql [
        sh:message "personsCapacityRequirement must equal personsOnBoard plus additionalEquipmentCapacityRequirement" ;
        sh:select """
            SELECT $this
            WHERE {
                $this <https://w3id.org/nltl/vocab#personsOnBoard> ?persons ;
                      <https://w3id.org/nltl/vocab#additionalEquipmentCapacityRequirement> ?additional ;
                      <https://w3id.org/nltl/vocab#personsCapacityRequirement> ?required .
                FILTER (?required != (?persons + ?additional))
            }
        """
    ] .''',
            ),
        ),
        "pass": turtle(
            ["fs", "nltl", "xsd"],
            'fs:shipPass a nltl:ship ;\n    nltl:personsOnBoard "30"^^xsd:integer ;\n    nltl:additionalEquipmentCapacityRequirement "5"^^xsd:integer ;\n    nltl:personsCapacityRequirement "35"^^xsd:integer .',
        ),
        "fail": turtle(
            ["fs", "nltl", "xsd"],
            'fs:shipFail a nltl:ship ;\n    nltl:personsOnBoard "30"^^xsd:integer ;\n    nltl:additionalEquipmentCapacityRequirement "5"^^xsd:integer ;\n    nltl:personsCapacityRequirement "34"^^xsd:integer .',
        ),
    },
    {
        "id": "FS-INT-01",
        "case_number": "10",
        "case_id": "conditional_integrated",
        "slug": "polar_operation_conditional",
        "title": "Conditional applicability with a required dependency",
        "requirement": "Synthetic rule: Each ship shall declare whether it operates in polar waters. If it does, the ship shall record that a Polar Water Operational Manual is present.",
        "tags": ["conditional", "applicability", "dependency", "boolean"],
        "vocab": ["ship", "shipOperatesInPolarWaters", "polarWaterOperationalManualPresent"],
        "negative_vocab": [],
        "shape": turtle(
            ["fs", "nltl", "sh", "xsd"],
            shape(
                "ship",
                """    sh:property [
        sh:path nltl:shipOperatesInPolarWaters ;
        sh:datatype xsd:boolean ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] ;
    sh:or (
        [
            sh:not [
                sh:property [
                    sh:path nltl:shipOperatesInPolarWaters ;
                    sh:hasValue true
                ]
            ]
        ]
        [
            sh:property [
                sh:path nltl:shipOperatesInPolarWaters ;
                sh:hasValue true
            ] ;
            sh:property [
                sh:path nltl:polarWaterOperationalManualPresent ;
                sh:datatype xsd:boolean ;
                sh:hasValue true ;
                sh:minCount 1 ;
                sh:maxCount 1
            ]
        ]
    ) .""",
            ),
        ),
        "pass": turtle(
            ["fs", "nltl", "xsd"],
            'fs:shipPass a nltl:ship ;\n    nltl:shipOperatesInPolarWaters "true"^^xsd:boolean ;\n    nltl:polarWaterOperationalManualPresent "true"^^xsd:boolean .',
        ),
        "fail": turtle(
            ["fs", "nltl", "xsd"],
            'fs:shipFail a nltl:ship ;\n    nltl:shipOperatesInPolarWaters "true"^^xsd:boolean .',
        ),
    },
    {
        "id": "FS-INT-02",
        "case_number": "10",
        "case_id": "conditional_integrated",
        "slug": "multi_condition_ship",
        "title": "Integrated controlled, date, Boolean, and quantity constraints",
        "requirement": "Synthetic rule: Each ship in this example shall be Category A or B, have a construction date on or after 1 January 2020, have enclosed bridge wings, and have a length overall of at least 60 metres.",
        "tags": ["integrated", "controlled-value", "date", "boolean", "quantity"],
        "vocab": ["ship", "shipCategory", "polarShipCategoryA", "polarShipCategoryB", "constructionDate", "bridgeWingsEnclosed", "lengthOverall"],
        "negative_vocab": ["polarShipCategoryC"],
        "shape": turtle(
            ["fs", "nltl", "qudt", "sh", "unit", "xsd"],
            shape(
                "ship",
                """    sh:property [
        sh:path nltl:shipCategory ;
        sh:nodeKind sh:IRI ;
        sh:in ( nltl:polarShipCategoryA nltl:polarShipCategoryB ) ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] ;
    sh:property [
        sh:path nltl:constructionDate ;
        sh:datatype xsd:date ;
        sh:minInclusive "2020-01-01"^^xsd:date ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] ;
    sh:property [
        sh:path nltl:bridgeWingsEnclosed ;
        sh:datatype xsd:boolean ;
        sh:hasValue true ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] ;
    sh:property [
        sh:path nltl:lengthOverall ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:node [
            sh:class qudt:QuantityValue ;
            sh:property [
                sh:path qudt:numericValue ;
                sh:datatype xsd:decimal ;
                sh:minInclusive "60"^^xsd:decimal ;
                sh:minCount 1 ;
                sh:maxCount 1
            ] ;
            sh:property [
                sh:path qudt:unit ;
                sh:hasValue unit:M ;
                sh:minCount 1 ;
                sh:maxCount 1
            ]
        ]
    ] .""",
            ),
        ),
        "pass": turtle(
            ["fs", "nltl", "qudt", "unit", "xsd"],
            'fs:shipPass a nltl:ship ;\n    nltl:shipCategory nltl:polarShipCategoryA ;\n    nltl:constructionDate "2022-05-01"^^xsd:date ;\n    nltl:bridgeWingsEnclosed "true"^^xsd:boolean ;\n    nltl:lengthOverall [ a qudt:QuantityValue ; qudt:numericValue "80"^^xsd:decimal ; qudt:unit unit:M ] .',
        ),
        "fail": turtle(
            ["fs", "nltl", "qudt", "unit", "xsd"],
            'fs:shipFail a nltl:ship ;\n    nltl:shipCategory nltl:polarShipCategoryC ;\n    nltl:constructionDate "2018-05-01"^^xsd:date ;\n    nltl:bridgeWingsEnclosed "false"^^xsd:boolean ;\n    nltl:lengthOverall [ a qudt:QuantityValue ; qudt:numericValue "50"^^xsd:decimal ; qudt:unit unit:M ] .',
        ),
    },
]


def term_record(local_name, registry, ontology):
    iri = URIRef(NLTL + local_name)
    if local_name in registry:
        item = registry[local_name]
        return {
            "localName": local_name,
            "iri": item["iri"],
            "source": "locked-term-registry",
            "conceptId": item["conceptId"],
            "kind": item["kind"],
            "datatypeOrRange": item["datatype"] or item["parentOrRange"],
            "unitIri": item["unitIri"],
        }
    if not any(ontology.triples((iri, None, None))):
        raise ValueError(f"Vocabulary term is not declared in the locked ontology: {iri}")
    labels = [str(value) for value in ontology.objects(iri, RDFS.label)]
    types = [str(value) for value in ontology.objects(iri, RDF.type)]
    return {
        "localName": local_name,
        "iri": str(iri),
        "source": "locked-ontology-infrastructure-or-controlled-value",
        "label": labels[0] if labels else local_name,
        "rdfTypes": sorted(types),
    }


def main():
    registry_items = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    registry = {item["localName"]: item for item in registry_items}
    ontology = Graph().parse(ONTOLOGY_PATH, format="turtle")

    if CASES_ROOT.exists():
        shutil.rmtree(CASES_ROOT)
    CASES_ROOT.mkdir(parents=True)

    catalog_examples = []
    prompt_pairs = []
    case_summary = {}

    for example in EXAMPLES:
        case_dir = CASES_ROOT / f'{example["case_number"]}_{example["case_id"]}'
        example_dir = case_dir / f'{example["id"]}_{example["slug"]}'
        example_dir.mkdir(parents=True)

        files = {
            "requirement": "input_requirement.txt",
            "shape": "expected_shape.ttl",
            "passData": "example_data_pass.ttl",
            "failData": "example_data_fail.ttl",
            "metadata": "metadata.json",
        }
        (example_dir / files["requirement"]).write_text(example["requirement"] + "\n", encoding="utf-8")
        (example_dir / files["shape"]).write_text(example["shape"], encoding="utf-8")
        (example_dir / files["passData"]).write_text(example["pass"], encoding="utf-8")
        (example_dir / files["failData"]).write_text(example["fail"], encoding="utf-8")

        generator_terms = [term_record(name, registry, ontology) for name in example["vocab"]]
        negative_terms = [term_record(name, registry, ontology) for name in example["negative_vocab"]]
        metadata = {
            "exampleId": example["id"],
            "caseId": example["case_id"],
            "title": example["title"],
            "status": "synthetic-few-shot-not-benchmark-ground-truth",
            "syntheticRequirement": example["requirement"],
            "retrievalTags": example["tags"],
            "exampleDataNamespace": PREFIX_IRIS["fs"],
            "canonicalVocabularyNamespace": NLTL,
            "generatorVocabulary": generator_terms,
            "negativeExampleOnlyVocabulary": negative_terms,
            "standardNamespacesUsed": sorted(
                {
                    PREFIX_IRIS[prefix]
                    for prefix in PREFIX_IRIS
                    if prefix not in {"fs", "nltl"}
                    and any(f"@prefix {prefix}:" in text for text in [example["shape"], example["pass"], example["fail"]])
                }
            ),
            "files": files,
            "expectedValidation": {"passDataConforms": True, "failDataConforms": False},
        }
        (example_dir / files["metadata"]).write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        relative_dir = example_dir.relative_to(ROOT).as_posix()
        catalog_examples.append(
            {
                "exampleId": example["id"],
                "caseId": example["case_id"],
                "title": example["title"],
                "retrievalTags": example["tags"],
                "directory": relative_dir,
                "files": {key: f"{relative_dir}/{value}" for key, value in files.items()},
            }
        )
        prompt_pairs.append(
            {
                "exampleId": example["id"],
                "caseId": example["case_id"],
                "retrievalTags": example["tags"],
                "status": "synthetic-few-shot-not-benchmark-ground-truth",
                "inputRequirement": example["requirement"],
                "generatorVocabulary": generator_terms,
                "expectedShapeTurtle": example["shape"],
            }
        )
        case_summary.setdefault(example["case_id"], []).append(example["id"])

    catalog = {
        "libraryId": "NLTL-SHACL-FEW-SHOT-2026-08-12-R1",
        "status": "generator-input-draft-validated-locally",
        "canonicalVocabularyNamespace": NLTL,
        "exampleDataNamespace": PREFIX_IRIS["fs"],
        "promptReadyJsonl": "few_shot_pairs.jsonl",
        "exampleCount": len(catalog_examples),
        "caseCount": len(case_summary),
        "examplesPerCase": {key: len(value) for key, value in sorted(case_summary.items())},
        "caseMembers": {key: value for key, value in sorted(case_summary.items())},
        "examples": catalog_examples,
    }
    (ROOT / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    (ROOT / "few_shot_pairs.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in prompt_pairs),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
