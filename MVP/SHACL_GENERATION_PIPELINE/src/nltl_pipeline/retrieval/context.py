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


NLTL = "https://w3id.org/nltl/vocab#"
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
        self.exclusive_property_groups = dict(self.index_payload.get("exclusivePropertyGroups", {}))
        self.dependency_contracts = dict(self.index_payload.get("dependencyContracts", {}))
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
        if str(requirement.get("figureDependent", "No")).lower() == "yes":
            return False
        requirement_id = str(requirement.get("id", ""))
        contract = self.dependency_contracts.get(requirement_id, {})
        category = requirement.get("category")
        mode = contract.get("verificationMode")
        if contract.get("status") == "COMPLETE":
            if category == "Static" and mode == "DIRECT_STATIC":
                return True
            if category == "Static Calculation" and mode == "DIRECT_CALCULATION":
                return True
            if category == "Complex" and mode == "COMPLEX_READINESS":
                return True
        # Compatibility for immutable pre-R9 locks whose direct requirements
        # predate explicit verification-mode routing.
        if requirement.get("activeStatus") == "Stage 2 candidate - direct/deterministic":
            return True
        return False

    @staticmethod
    def retrieval_tags(requirement: dict[str, Any], contract: dict[str, Any]) -> list[str]:
        if contract.get("verificationMode") == "COMPLEX_READINESS" or requirement.get("category") == "Complex":
            return [
                "complex", "readiness", "external-calculation", "calculation-inputs",
                "calculation-results", "engineering-evidence",
            ]
        if requirement.get("category") == "Static Calculation":
            return ["static-calculation", "direct-calculation", "basic-arithmetic"]
        if requirement.get("category") == "Static":
            return ["static", "direct-static"]
        if requirement.get("category") == "Dynamic":
            return ["dynamic", "runtime", "history"]
        if requirement.get("category") == "Physical Test":
            return ["physical-test", "test-evidence"]
        return []

    def build_context_pack(
        self,
        requirement_id: str,
        additional_local_names: Iterable[str] = (),
    ) -> ContextPack:
        requirement = self.requirement(requirement_id)
        self.validate_dependency_contract(requirement_id)
        indexed = list(self.requirement_index.get(requirement_id, []))
        if not indexed:
            raise ConfigurationError(f"Requirement has no indexed vocabulary terms: {requirement_id}")
        reasons: defaultdict[str, list[str]] = defaultdict(list)
        for name in indexed:
            reasons[name].append("linked by the locked 313-requirement index")
        for name in INFRASTRUCTURE_DEPENDENCIES:
            reasons[name].append("baseline target infrastructure")

        target_owner = self.requirement_target_owner.get(requirement_id, "ship")
        reasons[target_owner].append("authoritative requirement target owner")
        ownership = self.term_owners.get(requirement_id, {})
        required_owners = {target_owner, *ownership.values()}
        for owner in required_owners:
            reasons[owner].append("authoritative required owner class")

        # When a required operand belongs to another node, expose the canonical
        # object-property path from the target to that owner. This is a general
        # graph-model expansion and does not encode requirement answer logic.
        target_iri = NLTL + target_owner
        for owner in sorted(required_owners - {target_owner}):
            owner_iri = NLTL + owner
            for local_name, candidate in self.all_terms.items():
                if candidate.get("kind") != "ObjectProperty":
                    continue
                if str(candidate.get("parentOrRange") or "") != owner_iri:
                    continue
                candidate_domains = {str(item) for item in candidate.get("domains", [])}
                if target_iri in candidate_domains:
                    reasons[local_name].append(
                        f"canonical path from target owner {target_owner} to required owner {owner}"
                    )

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
        for term in terms:
            explicit_owner = ownership.get(term["localName"])
            domain_owners = [
                str(value)[len(NLTL):]
                for value in term.get("domains", [])
                if str(value).startswith(NLTL)
                and str(value) != NLTL + "benchmarkEntity"
            ]
            # A unique canonical rdfs:domain is safer than silently defaulting
            # every older term to the requirement target (normally ship).
            # Explicit per-requirement ownership still has highest precedence.
            inferred_owner = domain_owners[0] if len(set(domain_owners)) == 1 else target_owner
            term["requiredOwner"] = explicit_owner or inferred_owner
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
                "exclusivePropertyGroups": list(self.exclusive_property_groups.get(requirement_id, [])),
                "dependencyContract": dict(self.dependency_contracts.get(requirement_id, {})),
                "retrievalTags": self.retrieval_tags(
                    requirement, self.dependency_contracts.get(requirement_id, {})
                ),
            },
            usage_policy={
                "useOnlyAllowedCanonicalTerms": True,
                "useExactCanonicalIris": True,
                "reportVocabularyGapInsteadOfInventingATerm": True,
                "containsRegulatoryAnswerLogic": False,
            },
        )

    def validate_dependency_contract(self, requirement_id: str) -> None:
        """Reject an explicitly complete R9 contract if its declared model is inconsistent.

        Older locks and draft contracts remain usable. This gate becomes strict only
        after engineering review marks a requirement contract COMPLETE.
        """
        contract = self.dependency_contracts.get(requirement_id)
        if not contract or contract.get("status") != "COMPLETE":
            return
        declared: set[str] = set()
        for key in (
            "applicabilityTerms", "operandTerms", "resultTerms", "comparisonTerms",
            "relationshipTerms", "evidenceTerms", "controlledValueTerms", "timeTerms",
            "directConstraintTerms",
        ):
            declared.update(str(item) for item in contract.get(key, []))
        for direct_check in contract.get("directCheckSubconstraints", []):
            declared.update(str(item) for item in direct_check.get("requiredTerms", []))
        declared.update(str(item) for item in contract.get("ownerClasses", []))
        missing = sorted(declared - set(self.all_terms))
        if missing:
            raise ConfigurationError(
                f"Complete dependency contract contains absent canonical terms for {requirement_id}: {missing}"
            )
        indexed = set(self.requirement_index.get(requirement_id, []))
        not_indexed = sorted(
            name for name in declared - set(contract.get("ownerClasses", []))
            if name not in indexed
        )
        if not_indexed:
            raise ConfigurationError(
                f"Complete dependency contract terms are not in the requirement index for {requirement_id}: {not_indexed}"
            )
        missing_fields = [
            field for field in contract.get("requiredModelFields", [])
            if not contract.get(field)
        ]
        if missing_fields:
            raise ConfigurationError(
                f"Complete dependency contract lacks required model fields for {requirement_id}: {missing_fields}"
            )
        if contract.get("verificationMode") == "COMPLEX_READINESS":
            requirement = self.requirement(requirement_id)
            if requirement.get("category") != "Complex":
                raise ConfigurationError(
                    f"COMPLEX_READINESS contract is not classified Complex: {requirement_id}"
                )
            if not contract.get("operandTerms") and not contract.get("inputsSatisfiedByEvidenceOnly"):
                raise ConfigurationError(
                    f"COMPLEX_READINESS contract lacks required inputs: {requirement_id}"
                )
            if not contract.get("resultTerms"):
                raise ConfigurationError(
                    f"COMPLEX_READINESS contract lacks required outputs: {requirement_id}"
                )
            for direct_check in contract.get("directCheckSubconstraints", []):
                if not direct_check.get("id") or not direct_check.get("requiredTerms"):
                    raise ConfigurationError(
                        f"COMPLEX_READINESS DIRECT_CHECK is incomplete for {requirement_id}"
                    )
        if contract.get("verificationMode") in {"DIRECT_STATIC", "DIRECT_CALCULATION"}:
            requirement = self.requirement(requirement_id)
            expected_category = (
                "Static" if contract.get("verificationMode") == "DIRECT_STATIC"
                else "Static Calculation"
            )
            if requirement.get("category") != expected_category:
                raise ConfigurationError(
                    f"{contract.get('verificationMode')} contract has category mismatch: {requirement_id}"
                )
            direct_terms = set(str(item) for item in contract.get("directConstraintTerms", []))
            missing_direct = sorted(direct_terms - set(self.all_terms))
            if missing_direct:
                raise ConfigurationError(
                    f"Direct contract contains absent canonical terms for {requirement_id}: {missing_direct}"
                )
        if int(contract.get("schemaVersion", 1)) >= 2:
            def class_is_compatible(actual_iri: str, expected_iri: str) -> bool:
                """Return true when actual is expected or one of its subclasses."""
                actual = URIRef(actual_iri)
                expected = URIRef(expected_iri)
                if actual == expected:
                    return True
                visited: set[URIRef] = set()
                frontier = [actual]
                while frontier:
                    current = frontier.pop()
                    if current in visited:
                        continue
                    visited.add(current)
                    for parent in self.ontology_graph.objects(current, RDFS.subClassOf):
                        if parent == expected:
                            return True
                        if isinstance(parent, URIRef):
                            frontier.append(parent)
                return False

            owner_classes = set(str(item) for item in contract.get("ownerClasses", []))
            relationship_terms = set(str(item) for item in contract.get("relationshipTerms", []))
            paths = list(contract.get("modelPaths", []))
            path_relationships = {str(item.get("via", "")) for item in paths}
            undeclared_paths = sorted(path_relationships - relationship_terms)
            if undeclared_paths:
                raise ConfigurationError(
                    f"Complete dependency contract model paths use undeclared relationships for "
                    f"{requirement_id}: {undeclared_paths}"
                )
            for item in paths:
                via = str(item.get("via", ""))
                source_owner = str(item.get("fromOwner", ""))
                target_owner = str(item.get("toOwner", ""))
                term = self.all_terms.get(via, {})
                if term.get("kind") != "ObjectProperty":
                    raise ConfigurationError(
                        f"Complete dependency contract path for {requirement_id} does not use an "
                        f"object property: {via}"
                    )
                expected_range = NLTL + target_owner
                if str(term.get("parentOrRange") or "") != expected_range:
                    raise ConfigurationError(
                        f"Complete dependency contract path range mismatch for {requirement_id}: "
                        f"{via} -> {target_owner}"
                    )
                domains = {str(value) for value in term.get("domains", [])}
                if domains and not any(
                    class_is_compatible(NLTL + source_owner, domain) for domain in domains
                ):
                    raise ConfigurationError(
                        f"Complete dependency contract path domain mismatch for {requirement_id}: "
                        f"{source_owner} -{via}-> {target_owner}"
                    )
            declared_terms = declared - owner_classes
            ownership = self.term_owners.get(requirement_id, {})
            for name in sorted(declared_terms):
                if name not in ownership:
                    continue
                owner = str(ownership[name])
                term = self.all_terms[name]
                domains = {str(value) for value in term.get("domains", [])}
                if term.get("kind") in {"ObjectProperty", "DatatypeProperty", "QuantityProperty"} and domains:
                    if not any(class_is_compatible(NLTL + owner, domain) for domain in domains):
                        raise ConfigurationError(
                            f"Complete dependency contract ownership/domain mismatch for {requirement_id}: "
                            f"{name} owner={owner} domains={sorted(domains)}"
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
