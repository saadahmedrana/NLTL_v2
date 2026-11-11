"""Behavioral regression checks for strict credit and fair denominators."""
import unittest
from unittest.mock import patch
from rdflib import Graph, Namespace, RDF, Literal, BNode
import pyshacl
import audit
E=Namespace('urn:test:')
S=audit.S

class StrictCreditTests(unittest.TestCase):
    def fixture_and_shape(self, intended=True, unrelated=False):
        data=Graph(); data.add((E.subject,RDF.type,E.Target))
        shape=Graph();shape.add((E.Shape,S.targetClass,E.Target))
        for path in ([E.intended] if intended else [])+([E.unrelated] if unrelated else []):
            prop=BNode();shape.add((E.Shape,S.property,prop));shape.add((prop,S.path,path));shape.add((prop,S.minCount,Literal(1)))
        return data,shape
    def verdict(self,data,shape):
        c,g,_=pyshacl.validate(data,shacl_graph=shape)
        paths=set(g.objects(None,S.resultPath));return bool(c),paths
    def test_unrelated_rejection_has_no_credit(self):
        data,shape=self.fixture_and_shape(intended=False,unrelated=True)
        bad,paths=self.verdict(data,shape)
        data.add((E.subject,E.intended,Literal(True)))
        good,_=self.verdict(data,shape)
        self.assertEqual(audit.classify(True,bad,good,E.intended in paths,bool(paths-{E.intended})),'MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE')
    def test_missed_defect_has_no_credit(self):
        data,shape=self.fixture_and_shape(intended=False)
        bad,paths=self.verdict(data,shape)
        self.assertEqual(audit.classify(True,bad,True,False,False),'MISSED_INTENDED_DEFECT')
    def test_intended_and_unrelated_repair_still_fails(self):
        data,shape=self.fixture_and_shape(unrelated=True)
        bad,paths=self.verdict(data,shape)
        data.add((E.subject,E.intended,Literal(True)))
        good,_=self.verdict(data,shape)
        self.assertFalse(good)
        self.assertEqual(audit.classify(True,bad,good,True,True),'MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE')
        self.assertEqual(audit.classify(True,bad,good,True,False),'MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE')
    def test_intended_only_receives_credit(self):
        data,shape=self.fixture_and_shape()
        bad,paths=self.verdict(data,shape);data.add((E.subject,E.intended,Literal(True)));good,_=self.verdict(data,shape)
        self.assertEqual(audit.classify(True,bad,good,True,False),'STRICT_INTENDED_MATCH')
    def test_no_verdict_never_gets_offline_credit(self):
        self.assertEqual(audit.classify(False,False,True,True,False),'NO_VERDICT')
    def test_unknown_report_meaning_is_unresolved(self):
        self.assertEqual(audit.classify(True,False,True,False,False),'UNRESOLVED_REASON')
    def test_matching_uses_focus_and_logic_not_message(self):
        spec=dict(requirement='I2-001',admissible_semantics={'NO_SEMANTIC':[dict(paths=[],components=['SPARQLConstraintComponent'],focus=[str(E.subject)],logic_fingerprint='reviewed')]})
        v=dict(paths=[],components=[str(S.SPARQLConstraintComponent)],focus=[str(E.subject)],logic_fingerprint='unrelated',messages=['intended-looking'])
        expected,unexpected,_=audit.match_semantics([v],spec,'NO_SEMANTIC')
        self.assertFalse(expected);self.assertTrue(unexpected)
        v['logic_fingerprint']='reviewed';v['messages']=['anything']
        self.assertTrue(audit.match_semantics([v],spec,'NO_SEMANTIC')[0])
        v['focus']=[str(E.other)];self.assertFalse(audit.match_semantics([v],spec,'NO_SEMANTIC')[0])
    def test_blank_node_and_message_changes_do_not_change_logic(self):
        one=Graph().parse(data='@prefix sh: <http://www.w3.org/ns/shacl#>. <urn:s> sh:or ([sh:property [sh:path <urn:p>; sh:minCount 1; sh:message "one"]]).',format='turtle')
        two=Graph().parse(data='@prefix sh: <http://www.w3.org/ns/shacl#>. <urn:s> sh:or ([sh:property [sh:path <urn:p>; sh:minCount 1; sh:message "two"]]).',format='turtle')
        from rdflib import URIRef
        self.assertEqual(audit.logic_fingerprint(one,URIRef('urn:s'),'OrConstraintComponent'),audit.logic_fingerprint(two,URIRef('urn:s'),'OrConstraintComponent'))
    def test_exclusions_and_macro_denominators_identical(self):
        rows=[];results=[]
        for w in audit.WORKFLOWS:
            for cid,req in [('TRF-002-F02','TRF-002'),('keep1','TRF-002'),('keep2','OTHER')]:
                rows.append(dict(condition=w,case_id=cid,requirement_id=req,expected='FAIL'))
                results.append(dict(condition=w,case_id=cid,original_conforms=None if cid=='keep1' else False))
        summaries,fig,per=audit.metrics(rows,results,'original_conforms',True)
        self.assertEqual([r['cases'] for r in summaries],[2,2]);self.assertEqual([r['correct'] for r in summaries],[1,1])
        self.assertEqual([r['requirement_averaged_accuracy'] for r in summaries],[.5,.5])
        self.assertEqual([{r['requirement_id'] for r in per if r['condition']==w} for w in audit.WORKFLOWS],[{'TRF-002','OTHER'}]*2)
    def test_reviewed_specs_never_guessed(self):
        with patch.object(audit,'read',return_value=[dict(case='reviewed',review_status='REVIEWED'),dict(case='not_reviewed'),dict(case='pending',review_status='PENDING')]):
            self.assertEqual(set(audit.expected_specs()),{'reviewed'})
    def test_all_reviewed_repairs_satisfy_independent_fixture_oracle(self):
        import json
        cases={}
        for p in (audit.BENCH/'manifests').glob('*_batch_*_manifest.jsonl'):
            for line in p.read_text().splitlines():
                r=json.loads(line);cases[r['case_id']]=r
        for cid,spec in audit.expected_specs().items():
            with self.subTest(case=cid):
                data=Graph().parse(audit.BENCH/cases[cid]['rdf_path'])
                if spec['requirement']=='TRF-001':
                    ship=next(data.subjects(RDF.type,audit.N.ship))
                    for value in [audit.N.iceClassSection1Point8Provision2021,audit.N.iceClassDraughtChapter2Provision2021]:data.add((ship,audit.N.applicableIceClassRegulatoryProvision,value))
                self.assertFalse(audit.reviewed_fixture_oracle(data,spec['requirement']))
                for triple in audit.load_triples(spec['removed_triples']):
                    self.assertIn(triple,data);data.remove(triple)
                for triple in audit.load_triples(spec['added_triples']):data.add(triple)
                self.assertTrue(audit.reviewed_fixture_oracle(data,spec['requirement']))

if __name__=='__main__': unittest.main()
