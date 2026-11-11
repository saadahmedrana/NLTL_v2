"""Checks for reviewed batch coverage, fixture isolation, semantics and reuse."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rdflib import Graph, RDF, Literal, URIRef, Namespace
import audit
from reviewed_oracles import inspect_fixture
BASE=audit.HERE/'outputs/20261108T124921Z'
SPEC=audit.HERE/'reviewed_failure_specs_batch50.json'
E=Namespace('urn:batch-test:')

class Batch50Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.specs=audit.expected_specs(SPEC)
        cls.rows=audit.read(BASE/'retained_rows.json')
        cls.index={(r['condition'],r['case_id']):r for r in cls.rows}
    def test_50_specs_include_original14_and_span_regulations(self):
        self.assertEqual(len(self.specs),50)
        self.assertTrue(set(audit.expected_specs())<=set(self.specs))
        self.assertEqual(len({s['requirement'] for s in self.specs.values()}),19)
        self.assertEqual({s['requirement'].split('-')[0] for s in self.specs.values()},{'I2','TRF','IMO','IMO26'})
        self.assertFalse(set(self.specs)&set(audit.EXCLUSIONS))
    def test_exact_same_case_and_spec_for_both_workflows(self):
        for cid,s in self.specs.items():
            one=self.index['NO_SEMANTIC',cid];two=self.index['SINGLESHOT',cid]
            self.assertEqual(one['expected'],two['expected']);self.assertEqual(one['expected'],'FAIL')
            self.assertEqual(one['rdf_sha256'],two['rdf_sha256'])
            self.assertEqual(set(s['admissible_semantics']),set(audit.WORKFLOWS))
    def test_new_fixture_oracles_exactly_one_defect_then_none(self):
        review=audit.read(audit.HERE/'batch50_fixture_review.json')
        independent={r['case_id']:r for r in review['records']}
        self.assertFalse(review['generated_shapes_read'])
        for cid,s in self.specs.items():
            if not s.get('fixture_oracle'):continue
            with self.subTest(case=cid):
                r=self.index['NO_SEMANTIC',cid];bad=Graph().parse(BASE/'corrected_benchmark'/r['rdf_path']);good=audit.clone(bad)
                self.assertEqual(inspect_fixture(bad,s['requirement'])['defects'],s['fixture_oracle']['expected_negative_defects'])
                for t in audit.load_triples(s['removed_triples']):self.assertIn(t,good);good.remove(t)
                for t in audit.load_triples(s['added_triples']):self.assertNotIn(t,good);good.add(t)
                self.assertEqual(inspect_fixture(good,s['requirement'])['defects'],[])
                self.assertEqual(s['removed_triples'],independent[cid]['removed_triples'])
                self.assertEqual(s['added_triples'],independent[cid]['added_triples'])
    def test_oracle_detects_unrelated_defect_alongside_missing_field(self):
        r=self.index['NO_SEMANTIC','I2-006-F02'];g=Graph().parse(r['fixture_path']);ship=next(g.subjects(RDF.type,audit.N.ship))
        g.set((ship,audit.N.aftSectionDesignBasis,Literal('Stern',datatype=audit.XSD.string)))
        defects=inspect_fixture(g,'I2-006')['defects']
        self.assertIn('presence:'+str(audit.N.hullAreaRequirementSet),defects)
        self.assertIn('value:'+str(audit.N.aftSectionDesignBasis),defects)
        self.assertEqual(len(defects),2)
    def test_oracle_rejects_repaired_graph_with_wrong_unit(self):
        r=self.index['NO_SEMANTIC','IMO-010-F01'];g=Graph().parse(r['fixture_path']);q=next(g.objects(None,audit.N.maximumExpectedRescueTime))
        g.set((q,audit.Q.numericValue,Literal('5',datatype=audit.XSD.decimal)))
        self.assertEqual(inspect_fixture(g,'IMO-010')['defects'],[])
        g.set((q,audit.Q.unit,URIRef('http://qudt.org/vocab/unit/UNITLESS')))
        self.assertEqual(inspect_fixture(g,'IMO-010')['defects'],['unit:'+str(audit.N.maximumExpectedRescueTime)])
    def test_multiple_sparql_queries_are_matched_individually(self):
        query1='SELECT $this WHERE { FILTER NOT EXISTS { $this <urn:batch-test:intended> ?v } }'
        query2='SELECT $this WHERE { FILTER NOT EXISTS { $this <urn:batch-test:unrelated> ?v } }'
        shape=Graph();shape.add((E.Shape,audit.S.targetClass,E.Target))
        for i,q in enumerate([query1,query2]):
            c=URIRef(f'urn:constraint:{i}');shape.add((E.Shape,audit.S.sparql,c));shape.add((c,audit.S.select,Literal(q)))
        data=Graph();data.add((E.subject,RDF.type,E.Target))
        spec=dict(requirement='TEST',admissible_semantics={'NO_SEMANTIC':[dict(paths=[],components=['SPARQLConstraintComponent'],focus=[str(E.subject)],query_sha256=hashlib.sha256(query1.encode()).hexdigest())]})
        with tempfile.TemporaryDirectory() as temp,patch.object(audit,'_ONTO',Graph()):
            result=audit.validate(data,shape,Path(temp),'two_queries')
        expected,unrelated,_=audit.match_semantics(result['violations'],spec,'NO_SEMANTIC')
        self.assertEqual(len(expected),1);self.assertEqual(len(unrelated),1)
        self.assertEqual(audit.classify(True,False,True,True,bool(unrelated)),'MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE')
    def test_unit_component_with_wrong_expected_unit_is_not_intended(self):
        p=str(audit.S.hasValue)
        spec=dict(requirement='TEST',admissible_semantics={'NO_SEMANTIC':[dict(paths=[str(audit.Q.unit)],components=['HasValueConstraintComponent'],focus=[str(E.q)],expected_constraint_parameters={p:['http://qudt.org/vocab/unit/KiloW']})]})
        v=dict(paths=[str(audit.Q.unit)],components=[str(audit.S.HasValueConstraintComponent)],focus=[str(E.q)],constraint_parameters={p:[str(audit.Q.KiloW)]})
        self.assertFalse(audit.match_semantics([v],spec,'NO_SEMANTIC')[0])
    def test_source_excerpts_and_hashes_are_reproducible(self):
        for s in self.specs.values():
            if not s.get('fixture_oracle'):continue
            e=s['source_evidence'];p=Path(e['path'])
            self.assertEqual(audit.sha(p),e['sha256'])
            self.assertEqual('\n'.join(p.read_text().split('\n')[e['line_start']-1:e['line_end']]),e['excerpt'])
            self.assertGreater(len(e['excerpt'].strip()),40)
    def test_baseline_is_unchanged_and_authoritative(self):
        authority=audit.read(audit.HERE/'authoritative_run.json')
        self.assertEqual(Path(authority['run_dir']),BASE)
        self.assertEqual(audit.sha(BASE/'baseline_results.json'),authority['baseline_sha256'])
        self.assertTrue(audit.read(BASE/'run_reconciliation.json')['baseline_validation_inputs_unchanged'])
    def test_saved_pairs_preserve_exact_declared_rdf_changes(self):
        batch=BASE/'review_batches/batch50'
        for r in audit.read(batch/'strict_results.json'):
            folder=batch/'reviewed'/r['arm']/r['condition']/r['case_id']
            bad=Graph().parse(folder/'negative_fixture.ttl');good=Graph().parse(folder/'repaired_fixture.ttl');s=self.specs[r['case_id']]
            self.assertEqual(set(bad)-set(good),audit.load_triples(s['removed_triples']))
            self.assertEqual(set(good)-set(bad),audit.load_triples(s['added_triples']))
    def test_shape_exports_preserve_bytes_and_decimal_terms(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source.ttl';out=Path(temp)/'out.ttl'
            source.write_text('@prefix sh: <http://www.w3.org/ns/shacl#>. @prefix xsd: <http://www.w3.org/2001/XMLSchema#>. <urn:s> sh:minInclusive "7"^^xsd:decimal .')
            original=Graph().parse(source);shape=audit.clone(original)
            audit.save_evaluated_shape(shape,original,source,out)
            self.assertEqual(source.read_bytes(),out.read_bytes())
            shape.set((URIRef('urn:s'),audit.S.minInclusive,Literal('8',datatype=audit.XSD.decimal)))
            audit.save_evaluated_shape(shape,original,source,out)
            self.assertEqual(set(Graph().parse(out)),set(shape))
    def test_changed_export_cases_replay_identical_saved_verdicts(self):
        batch=BASE/'review_batches/batch50'
        selected={'I2-004-G-F02','I2-005-G-F01'}
        with tempfile.TemporaryDirectory() as temp:
            for r in audit.read(batch/'strict_results.json'):
                if r['case_id'] not in selected or r['arm']!='corrected_fixtures':continue
                folder=batch/'reviewed'/r['arm']/r['condition']/r['case_id'];shape=Graph().parse(folder/'evaluated_shape.ttl')
                for label in ['negative','repaired']:
                    data=Graph().parse(folder/f'{label}_fixture.ttl')
                    replay=audit.validate(data,shape,Path(temp)/r['condition']/r['case_id'],label)
                    self.assertEqual(replay['conforms'],r[label]['conforms'])
    def test_original14_results_and_no_verdicts_are_preserved(self):
        previous={(r['condition'],r['case_id'],r['arm']):r for r in audit.read(BASE/'strict_results.json')}
        for r in audit.read(BASE/'review_batches/batch50/strict_results.json'):
            key=r['condition'],r['case_id'],r['arm']
            if key in previous:self.assertEqual(r['status'],previous[key]['status'])
            if not r['original_eligible']:self.assertEqual(r['status'],'NO_VERDICT')
    def test_every_strict_mismatch_has_a_reviewed_cause(self):
        import csv
        from batch_report import CAUSES
        batch=BASE/'review_batches/batch50'
        rs=[r for r in audit.read(batch/'strict_results.json') if r['arm']=='corrected_fixtures' and r['status'] in ['MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE','MISSED_INTENDED_DEFECT','UNRESOLVED_REASON']]
        with (batch/'strict_mismatch_causes.csv').open() as f:causes=list(csv.DictReader(f))
        self.assertEqual({(r['condition'],r['case_id']) for r in rs},{(r['condition'],r['case_id']) for r in causes})
        for r in causes:self.assertIn(r['primary'],CAUSES);self.assertTrue(r['explanation'])

if __name__=='__main__':unittest.main()
