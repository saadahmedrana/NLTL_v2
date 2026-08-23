from __future__ import annotations

import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path

from rdflib import Graph, Namespace, RDF, RDFS
from rdflib.compare import isomorphic

from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.prompts import PromptFactory
from nltl_pipeline.retrieval.context import VocabularyRepository


NLTL = Namespace("https://w3id.org/nltl/vocab#")
EXPECTED = {"Static":190,"Static Calculation":44,"Complex":45,"Dynamic":19,"Physical Test":15}
CHANGED = {"I2-017","IMO-011","TRF-012","TRF-080","TRF-084","TRF-086"}


class R11SourceGroundedCorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline=Path(__file__).resolve().parents[1]; cls.mvp=cls.pipeline.parent
        cls.r11=cls.mvp/"BENCHMARK_VOCABULARY/FINAL_LOCK_R11"; cls.r10=cls.mvp/"BENCHMARK_VOCABULARY/FINAL_LOCK_R10"
        cls.config=PipelineConfig.load(cls.pipeline/"config/pipeline.r11-prelock-offline.json")
        cls.repo=VocabularyRepository(cls.config)
        cls.evidence=json.loads((cls.r11/"evidence/stage1_approved.json").read_text()); cls.by={r["id"]:r for r in cls.evidence["requirements"]}
        cls.before={r["id"]:r for r in json.loads((cls.r10/"evidence/stage1_approved.json").read_text())["requirements"]}
        cls.index=json.loads((cls.r11/"requirement_term_index.json").read_text())

    def test_exact_category_delta_counts_and_eligibility(self):
        self.assertEqual(CHANGED,{rid for rid in self.by if self.by[rid]["category"]!=self.before[rid]["category"]})
        self.assertEqual(EXPECTED,dict(Counter(r["category"] for r in self.evidence["requirements"])))
        self.assertEqual(268,sum(self.repo.is_generation_eligible(r) for r in self.by.values()))
        self.assertEqual("DEFERRED_SCOPE_ONLY",self.index["dependencyContracts"]["I2-002"]["status"])
        self.assertFalse(self.repo.is_generation_eligible(self.by["I2-002"]))

    def test_exact_vocabulary_delta_and_ontology(self):
        before={t["localName"]:t for t in json.loads((self.r10/"registry/term_registry.json").read_text())}
        after={t["localName"]:t for t in json.loads((self.r11/"registry/term_registry.json").read_text())}
        decisions=json.loads((self.r11/"registry/r11_source_grounded_change_decisions.json").read_text())
        self.assertEqual(set(decisions["newCanonicalTerms"]),set(after)-set(before)); self.assertEqual(25,len(set(after)-set(before)))
        self.assertEqual({"frameBoundaryConditionType"},{n for n in before if before[n]!=after[n]})
        ttl=Graph().parse(self.r11/"ontology/nltl_benchmark_vocabulary.ttl",format="turtle")
        rdf=Graph().parse(self.r11/"ontology/nltl_benchmark_vocabulary.rdf",format="xml")
        self.assertTrue(isomorphic(ttl,rdf)); self.assertIn((NLTL.frameBoundaryConditionType,RDFS.domain,NLTL.frame),ttl)
        self.assertNotIn((NLTL.frameBoundaryConditionType,RDFS.domain,NLTL.transverseFrame),ttl)
        for local in decisions["newCanonicalTerms"]: self.assertTrue(any(ttl.triples((NLTL[local],RDF.type,None))),local)

    def test_contract_cleanup_i2_023_i2_035(self):
        self.assertEqual(["averageIcePressure","frameSpacing","frameSpan","framingAngleOmega","loadPatchHeight","peakPressureFactor","selectedHullAreaFactor","yieldStrength"],self.index["dependencyContracts"]["I2-023"]["operandTerms"])
        self.assertEqual(["iceLoadRequiredNetPlateThickness"],self.index["dependencyContracts"]["I2-023"]["resultTerms"])
        self.assertEqual(["averageIcePressure","frameSpacing","frameSpan","peakPressureFactor","selectedHullAreaFactor","yieldStrength","shearArea"],self.index["dependencyContracts"]["I2-035"]["operandTerms"])
        self.assertEqual(["requiredLongitudinalFrameShearArea"],self.index["dependencyContracts"]["I2-035"]["resultTerms"])

    def test_key_paths_and_controlled_values(self):
        c=self.index["dependencyContracts"]
        self.assertIn("steelGradeRequirementCasePlating",c["I2-048"]["relationshipTerms"])
        self.assertIn("thinFirstYearIceWithPossibleOldIceInclusions",c["IMO-002"]["controlledValueTerms"])
        self.assertEqual("COMPLEX_READINESS",c["IMO-011"]["verificationMode"])
        self.assertIn("hasDailyLowTemperatureObservation",c["IMO-011"]["relationshipTerms"])
        self.assertIn("hasApprovalRecord",c["IMO-032"]["relationshipTerms"])
        self.assertEqual(["hasComponent","hasApprovalRecord","scantlingApprovalStatus"],c["IMO-049"]["relationshipTerms"])
        self.assertNotIn("continuousUseSuitabilityStatus",self.index["requirements"]["IMO-072"])
        self.assertIn("searchlightContinuousUseSuitabilityStatus",self.index["requirements"]["IMO-072"])
        self.assertEqual("hasPolarRoutePlan",c["IMO-101"]["modelPaths"][0]["via"])

    def test_remaining_approved_models(self):
        c=self.index["dependencyContracts"]
        for rid in ("IMO-117","IMO-123"):
            self.assertIn("hasDischargeDistanceRecord",c[rid]["relationshipTerms"])
            self.assertIn("distanceToAreaWithIceConcentrationGreaterThanOneTenth",self.index["requirements"][rid])
        self.assertIn("12 nautical miles",c["IMO-123"]["comparisonModel"])
        self.assertIn("no numerical minimum is imposed for the ice-concentration-area distance",c["IMO-117"]["comparisonModel"])
        self.assertEqual("2007-07-01",c["TRF-014"]["literalConstants"]["regulatoryCutoffDate"])
        self.assertEqual(["evidenceStateApproved"],c["TRF-029"]["controlledValueTerms"])
        self.assertIn("terminationAdjacentBoundary",c["TRF-043"]["relationshipTerms"])
        self.assertNotIn("designIceLoadHeight",c["TRF-048"]["applicabilityTerms"])
        self.assertIn("strengtheningEnvelopeBoundary",c["TRF-063"]["relationshipTerms"])
        self.assertEqual(["azimuthing","fixed"],c["TRF-070"]["stringValuePolicies"]["thrusterType"])
        self.assertEqual("sh:xone or equivalent deterministic exclusive choice",c["TRF-075"]["exclusiveChoicePolicies"][0]["encoding"])
        self.assertEqual(0.000747,c["TRF-109"]["tableModel"]["open"]["C1"])
        self.assertIn("aggregateMarkingPolicies",c["TRF-133"])

    def test_complex_readiness_prompt_clarification_is_r11_scoped(self):
        prompts=PromptFactory(self.pipeline/"prompts/r11")
        for text in (prompts.generator_instructions,prompts.validator_instructions):
            self.assertIn("only when",text); self.assertIn("explicitly declared",text)
            self.assertIn("nonlinear formula",text)
        self.assertNotEqual((self.pipeline/"prompts/generator.txt").read_bytes(),(self.pipeline/"prompts/r11/generator.txt").read_bytes())

    def test_direct_calculation_diagnostic_is_report_only(self):
        report=json.loads((self.r11/"validation/r11_direct_calculation_completeness_diagnostic.json").read_text())
        self.assertEqual(23,report["diagnosticCount"]); self.assertEqual(0,report["contractsModified"])
        self.assertEqual(0,report["eligibilityModified"]); self.assertIn("TRF-048",report["requirementIds"])

    def test_all_contexts_resolve_and_r10_is_immutable(self):
        for rid in sorted(self.repo.requirements): self.assertEqual(rid,self.repo.build_context_pack(rid).selection["requirementId"])
        provenance=json.loads((self.r11/"provenance/r10_immutable_source_hashes.json").read_text())
        for relative,expected in provenance["files"].items():
            path=self.mvp/relative; self.assertTrue(path.exists(),relative)
            self.assertEqual(expected,hashlib.sha256(path.read_bytes()).hexdigest(),relative)


if __name__=="__main__": unittest.main()
