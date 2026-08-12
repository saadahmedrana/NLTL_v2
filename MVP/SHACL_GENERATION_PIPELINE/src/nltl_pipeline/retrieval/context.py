from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from rdflib import Graph, RDF, RDFS, URIRef
from rdflib.namespace import OWL, SKOS

from ..config import PipelineConfig
from ..errors import ConfigurationError
from ..models import ContextPack


NLTL = "https://w3id.org/nltl-benchmark/vocab#"
INFRASTRUCTURE_DEPENDENCIES = ("benchmarkEntity", "ship")


class VocabularyRepository:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.lock_info = config.verify_locked_inputs()
        self.registry = self._read_json(config.path("term_registry"))
        self.evidence = self._read_json(config.path("requirement_evidence"))
        self.index_payload = self._read_json(config.path("requirement_term_index"))
        self.requirements = {item["id"]: item for item in self.evidence["requirements"]}
        self.registry_by_local = {item["localName"]: dict(item) for item in self.registry}
        self.ontology_graph = Graph().parse(config.path("ontology"), format="turtle")
        self.ontology_terms = self._ontology_term_records()
        # Registry metadata is richer, while ontology records carry authoritative
        # rdfs:domain statements. Merge rather than overwrite either source.
        self.all_terms = dict(self.ontology_terms)
        for local_name, registry_term in self.registry_by_local.items():
            merged = dict(self.ontology_terms.get(local_name, {}))
            merged.update(registry_term)
            merged["domains"] = list(self.ontology_terms.get(local_name, {}).get("domains", []))
            self.all_terms[local_name] = merged
        self.requirement_index = dict(self.index_payload["requirements"])
        self.requirement_target_owner = dict(self.index_payload.get("requirementTargetOwner", {}))
        self.term_owners = dict(self.index_payload.get("termOwners", {}))
        self.semantic_obligations = dict(self.index_payload.get("semanticObligations", {}))
        if int(self.index_payload.get("requirementCount", -1)) != len(self.requirements):
            raise ConfigurationError("Requirement evidence and requirement-term index counts differ")

    @staticmethod
    def _read_json(path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"Cannot read JSON source: {path}") from exc

    def _ontology_term_records(self) -> dict[str, dict[str, Any]]:
        records: dict[str, dict[str, Any]] = {}
        type_to_kind = {
            OWL.Class: "Class",
            OWL.ObjectProperty: "ObjectProperty",
            OWL.DatatypeProperty: "DatatypeProperty",
        }
        for rdf_type, kind in type_to_kind.items():
            for subject in self.ontology_graph.subjects(RDF.type, rdf_type):
                iri = str(subject)
                if not iri.startswith(NLTL):
                    continue
                local = iri[len(NLTL):]
                labels = [str(item) for item in self.ontology_graph.objects(subject, RDFS.label)]
                ranges = [str(item) for item in self.ontology_graph.objects(subject, RDFS.range)]
                domains = [str(item) for item in self.ontology_graph.objects(subject, RDFS.domain)]
                records[local] = {
                    "localName": local,
                    "iri": iri,
                    "label": labels[0] if labels else local,
                    "kind": kind,
                    "module": "ontology-infrastructure",
                    "parentOrRange": ranges[0] if ranges else "",
                    "datatype": "",
                    "unitIri": "",
                    "unitSymbol": "",
                    "quantityKindLabel": "",
                    "aliases": [],
                    "normalizedDefinition": "Locked ontology infrastructure term.",
                    "sourceConceptIds": [],
                    "sourceRefs": "Locked Stage 2 ontology",
                    "namingBasis": "Locked ontology infrastructure",
                    "namingRule": "Infrastructure term preserved exactly",
                    "roleDecision": "Ontology infrastructure",
                    "unitDecisionStatus": "Not specified",
                    "mappingStatus": "Locked ontology term",
                    "haithamUri": "",
                    "requirements": [],
                    "domains": domains,
                }
        controlled_value_types = (
            URIRef(f"{NLTL}evidenceState"),
            URIRef(f"{NLTL}complianceState"),
            URIRef(f"{NLTL}iceClassValue"),
            URIRef(f"{NLTL}polarClassValue"),
            URIRef(f"{NLTL}polarShipCategoryValue"),
        )
        controlled_subjects: dict[URIRef, URIRef] = {}
        for value_type in controlled_value_types:
            for subject in self.ontology_graph.subjects(RDF.type, value_type):
                controlled_subjects[subject] = value_type
        # Development revisions may add new regulation-defined value classes.
        # Any explicitly declared owl:NamedIndividual is safe to expose using
        # its non-OWL rdf:type as the controlled-value range.
        for subject in self.ontology_graph.subjects(RDF.type, OWL.NamedIndividual):
            value_types = [
                item for item in self.ontology_graph.objects(subject, RDF.type)
                if item != OWL.NamedIndividual
            ]
            if value_types:
                controlled_subjects[subject] = value_types[0]
        for subject, value_type in controlled_subjects.items():
            iri = str(subject)
            if not iri.startswith(NLTL):
                continue
            local = iri[len(NLTL):]
            labels = [str(item) for item in self.ontology_graph.objects(subject, SKOS.prefLabel)]
            records[local] = {
                "localName": local,
                "iri": iri,
                "label": labels[0] if labels else local,
                "kind": "NamedIndividual",
                "module": "ontology-controlled-value",
                "parentOrRange": str(value_type),
                "datatype": "",
                "unitIri": "",
                "unitSymbol": "",
                "quantityKindLabel": "",
                "aliases": [],
                "normalizedDefinition": "Locked controlled value from the Stage 2 ontology.",
                "sourceConceptIds": [],
                "sourceRefs": "Locked Stage 2 ontology",
                "namingBasis": "Locked ontology controlled value",
                "namingRule": "Controlled-value IRI preserved exactly",
                "roleDecision": "Named controlled value",
                "unitDecisionStatus": "Not applicable",
                "mappingStatus": "Locked ontology term",
                "haithamUri": "",
                "requirements": [],
                "domains": [],
            }
        return records

    @staticmethod
    def _compact(term: dict[str, Any], selection_reason: str) -> dict[str, Any]:
        return {
            "localName": term["localName"],
            "iri": term["iri"],
            "label": term.get("label", term["localName"]),
            "kind": term.get("kind", ""),
            "module": term.get("module", ""),
            "range": term.get("parentOrRange", ""),
            "domains": list(term.get("domains") or []),
            "datatype": term.get("datatype") or None,
            "recommendedUnit": term.get("unitIri") or None,
            "unitSymbol": term.get("unitSymbol") or None,
            "quantityKind": term.get("quantityKindLabel") or None,
            "aliases": list(term.get("aliases") or []),
            "definition": term.get("normalizedDefinition", ""),
            "sourceReferences": term.get("sourceRefs", ""),
            "namingBasis": term.get("namingBasis", ""),
            "mappingStatus": term.get("mappingStatus", ""),
            "selectionReason": selection_reason,
        }

    def requirement(self, requirement_id: str) -> dict[str, Any]:
        try:
            return dict(self.requirements[requirement_id])
        except KeyError as exc:
            raise ConfigurationError(f"Unknown requirement ID: {requirement_id}") from exc

    def is_generation_eligible(self, requirement: dict[str, Any]) -> bool:
        return (
            requirement.get("activeStatus") == "Stage 2 candidate - direct/deterministic"
            and str(requirement.get("figureDependent", "No")).lower() != "yes"
        )

    def build_context_pack(
        self,
        requirement_id: str,
        additional_local_names: Iterable[str] = (),
    ) -> ContextPack:
        requirement = self.requirement(requirement_id)
        indexed = list(self.requirement_index.get(requirement_id, []))
        if not indexed:
            raise ConfigurationError(f"Requirement has no indexed vocabulary terms: {requirement_id}")
        reasons: defaultdict[str, list[str]] = defaultdict(list)
        for name in indexed:
            reasons[name].append("linked by the locked 313-requirement index")
        for name in INFRASTRUCTURE_DEPENDENCIES:
            reasons[name].append("baseline target infrastructure")

        indexed_terms = [self.all_terms[name] for name in indexed if name in self.all_terms]
        if any(item.get("module") in {"hull", "machinery"} for item in indexed_terms):
            for name in ("hasComponent", "shipComponent"):
                reasons[name].append("component-path dependency inferred from the linked term module")
        if any(item.get("kind") == "QuantityProperty" for item in indexed_terms):
            # QUDT itself is standard infrastructure; no extra benchmark term is invented.
            pass
        if requirement.get("category") == "Physical Test" or "evidence" in str(requirement.get("encodingPattern", "")).lower():
            for name in ("hasEvidence", "evidenceArtifact"):
                reasons[name].append("evidence-node dependency from verification category")
        text = " ".join(
            str(requirement.get(key, ""))
            for key in ("sourceText", "normalizedRequirement", "encodingPattern")
        ).lower()
        if any(token in text for token in ("observation", "history", "time-dependent", "time dependent")):
            reasons["hasObservation"].append("observation/history dependency from verified requirement metadata")

        for term in indexed_terms:
            range_iri = str(term.get("parentOrRange") or "")
            if range_iri.startswith(NLTL):
                reasons[range_iri[len(NLTL):]].append(f"range dependency of {term['localName']}")
                for local_name, candidate in self.all_terms.items():
                    if (
                        candidate.get("kind") == "NamedIndividual"
                        and candidate.get("parentOrRange") == range_iri
                    ):
                        reasons[local_name].append(
                            f"controlled value permitted by the range of {term['localName']}"
                        )
            for domain_iri in term.get("domains", []):
                if str(domain_iri).startswith(NLTL):
                    reasons[str(domain_iri)[len(NLTL):]].append(f"domain dependency of {term['localName']}")

        for name in additional_local_names:
            reasons[str(name)].append("verified vocabulary-matcher addition")

        unknown = sorted(set(reasons) - set(self.all_terms))
        if unknown:
            raise ConfigurationError(f"Context dependency is absent from locked ontology: {unknown}")
        terms = [
            self._compact(self.all_terms[name], "; ".join(sorted(set(reasons[name]))))
            for name in sorted(reasons)
        ]
        target_owner = self.requirement_target_owner.get(requirement_id, "ship")
        ownership = self.term_owners.get(requirement_id, {})
        for term in terms:
            term["requiredOwner"] = ownership.get(term["localName"], target_owner)
        kinds = {item["kind"] for item in terms}
        patterns: list[dict[str, Any]] = []
        if "Class" in kinds:
            patterns.append({"id": "rdfType", "pattern": "node rdf:type canonicalClassIri"})
        if "DatatypeProperty" in kinds:
            patterns.append({"id": "typedLiteral", "pattern": "subject canonicalProperty typedLiteral"})
        if "ObjectProperty" in kinds:
            patterns.append({"id": "objectIri", "pattern": "subject canonicalProperty objectIri"})
        if "QuantityProperty" in kinds:
            patterns.append({
                "id": "qudtQuantityValue",
                "pattern": "subject canonicalProperty quantityNode; quantityNode qudt:numericValue xsd:decimal; qudt:unit recommendedUnit",
            })
        patterns.insert(0, {
            "id": "requirementTargetOwner",
            "pattern": f"Target {NLTL}{target_owner}; each allowed vocabulary term carries its authoritative requiredOwner for this requirement.",
        })
        return ContextPack(
            requirement=requirement,
            terms=terms,
            node_patterns=patterns,
            source_lock=self.lock_info,
            selection={
                "requirementId": requirement_id,
                "indexedTermCount": len(indexed),
                "expandedTermCount": len(terms),
                "eligibleForGeneration": self.is_generation_eligible(requirement),
                "requiredTargetOwner": target_owner,
                "semanticObligations": list(self.semantic_obligations.get(requirement_id, [])),
            },
            usage_policy={
                "useOnlyAllowedCanonicalTerms": True,
                "useExactCanonicalIris": True,
                "reportVocabularyGapInsteadOfInventingATerm": True,
                "containsRegulatoryAnswerLogic": False,
            },
        )

    def full_compact_index(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for local_name in sorted(self.all_terms):
            term = self.all_terms[local_name]
            result.append({
                "localName": local_name,
                "iri": term["iri"],
                "label": term.get("label", local_name),
                "kind": term.get("kind", ""),
                "range": term.get("parentOrRange", ""),
                "datatype": term.get("datatype") or None,
                "recommendedUnit": term.get("unitIri") or None,
                "aliases": list(term.get("aliases") or []),
            })
        return result

    def compact_terms_for_iris(self, iris: Iterable[str]) -> list[dict[str, Any]]:
        """Return compact records only for verified canonical IRIs used by a candidate."""
        requested = set(iris)
        return [
            item
            for item in self.full_compact_index()
            if item["iri"] in requested
        ]

    def regulation_queue(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in sorted(self.requirements.values(), key=lambda value: value["id"]):
            rows.append({
                "requirement_id": item["id"],
                "source": item.get("source", ""),
                "edition": item.get("edition", ""),
                "page": item.get("page", ""),
                "clause": item.get("clause", ""),
                "category": item.get("category", ""),
                "active_status": item.get("activeStatus", ""),
                "codability": item.get("codability", ""),
                "figure_dependent": item.get("figureDependent", ""),
                "queue_eligibility": "ELIGIBLE" if self.is_generation_eligible(item) else "DEFERRED",
            })
        return rows
