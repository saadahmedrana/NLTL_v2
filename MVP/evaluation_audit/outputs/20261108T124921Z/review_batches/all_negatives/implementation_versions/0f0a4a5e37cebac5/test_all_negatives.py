"""Evidence gates and end-to-end receipts for the all-negative extension."""
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rdflib import Graph,URIRef,Literal,RDF,XSD

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'full_audit'))
import evidence
import prepare
import evaluate
import report_all
from common import audit,BASE,OUT,OLD

class EvidenceGates(unittest.TestCase):
    def test_original_entrypoint_and_writes_never_run(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'unwanted';script=Path(d)/'source.py'
            script.write_text('from pathlib import Path\nfrom rdflib import Graph\n'+f'Path({str(target)!r}).write_text("wrong")\n'+ 'def build_case(cid, missing=False):\n return Graph()\nCASES=[dict(case_id="EX-1", graph=build_case("EX-1",missing=True))]\n'+f'if __name__ == "__main__":\n Path({str(target)!r}).write_text("wrong")\n')
            loaded=evidence.load_script(script)
            self.assertFalse(target.exists());self.assertFalse(loaded['errors'])
            trace=evidence.trace_for(loaded,'EX-1');self.assertIsNotNone(trace)
            proposals=evidence.default_proposals(trace)
            self.assertEqual([(p['parameter'],p['after']) for p in proposals],[('missing','False')])
    def test_manual_source_reconciliations_are_exact_saved_excerpts(self):
        for req,review in audit.read(HERE/'full_audit/source_reviews.json').items():
            path=Path(review['source_path'])
            self.assertEqual(audit.sha(path),review['source_sha256'],req)
            # Source PDF extracts retain page-break form feeds; line numbers
            # count LF delimiters, as the source-review authoring record does.
            lines=path.read_text().split('\n')
            self.assertEqual('\n'.join(lines[review['line_start']-1:review['line_end']]),review['excerpt'],req)
            self.assertTrue(review['review_note'])
    def test_decimal_replay_preserves_retained_terms_without_changing_values(self):
        s,p=URIRef('urn:s'),URIRef('urn:p');a,b=Graph(),Graph()
        a.add((s,p,Literal('12',datatype=XSD.decimal)));b.add((s,p,Literal('12.0',datatype=XSD.decimal)))
        self.assertEqual(set(prepare.align_numeric_lexicals(a,b)),set(b))
        a.set((s,p,Literal('13',datatype=XSD.decimal)))
        self.assertEqual(str(prepare.align_numeric_lexicals(a,b).value(s,p)),'13')
    def test_multiple_semantic_fields_not_an_intended_only_repair(self):
        s=URIRef('urn:s');a,b=Graph(),Graph()
        for p in [audit.N.shipCategory,audit.N.voyagePlanPresent]:a.add((s,p,Literal(False)));b.add((s,p,Literal(True)))
        self.assertEqual(len({p for s,p in prepare.semantic_roots(a,b)}),2)
    def test_object_range_is_independently_checked(self):
        g=Graph();s,o=URIRef('urn:ship'),URIRef('urn:craft')
        g.add((s,RDF.type,audit.N.ship));g.add((s,audit.N.hasRequiredRescueBoatOrLifeboat,o));g.add((o,RDF.type,audit.N.rescueBoat))
        self.assertTrue(any(x['kind']=='OBJECT_RANGE' for x in prepare.schema_issues(g)))
    def test_repair_pass_alone_is_not_reason_credit(self):
        rec=json.loads((OUT/'records/I2-048-H-F002.json').read_text())
        bad=Graph().parse(rec['negative_fixture']);good=Graph().parse(rec['repaired_fixture'])
        unknown=dict(component='SPARQLConstraintComponent',path=None,focus='urn:focus',source_shape='urn:unknown',parameters={},nested_details=0,query=None,query_sha256=None)
        meaning=evaluate.match_reason(dict(rec,_workflow='NO_SEMANTIC'),bad,good,Graph(),[unknown])
        self.assertFalse(meaning['intended']);self.assertEqual(meaning['unresolved'],[unknown])
    def test_missing_unrelated_property_does_not_match(self):
        rec=json.loads((OUT/'records/I2-048-H-F002.json').read_text())
        bad=Graph().parse(rec['negative_fixture']);good=Graph().parse(rec['repaired_fixture'])
        unrelated=dict(component='MinCountConstraintComponent',path=str(audit.N.voyagePlanPresent),focus='urn:other',source_shape='urn:x',parameters={str(audit.S.minCount):[Literal(1).n3()]},nested_details=0)
        meaning=evaluate.match_reason(dict(rec,_workflow='NO_SEMANTIC'),bad,good,Graph(),[unrelated])
        self.assertFalse(meaning['intended'])

class CompletedCohort(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.records=report_all.records()
    def test_all_1154_additional_cases_are_terminal_and_accounted(self):
        self.assertEqual(len(self.records),1205)
        self.assertEqual(sum(r['state']=='COMPLETED_PRIOR50' for r in self.records),50)
        self.assertEqual(sum(r['state']=='EXCLUDED' for r in self.records),1)
        self.assertEqual(sum(r['state'] in ['COMPLETED','BLOCKED'] for r in self.records),1154)
        self.assertTrue(all(r['state'] in report_all.TERMINAL for r in self.records))
    def test_fairness_no_verdict_and_strict_credit_guards(self):
        report_all.checks(self.records)
    def test_unresolved_is_never_silently_strict(self):
        for r in self.records:
            for v in r.get('workflows',{}).values():
                if v.get('blocker'):self.assertEqual(v['status'],'UNRESOLVED_REASON')
    def test_guard_rejects_ineligible_offline_credit(self):
        rs=copy.deepcopy(self.records)
        victim=next(v for r in rs for v in r.get('workflows',{}).values() if not v['original_eligible'])
        victim['status']='STRICT_INTENDED_MATCH'
        with self.assertRaises(AssertionError):report_all.checks(rs)
    def test_guard_rejects_repaired_failure_credit(self):
        rs=copy.deepcopy(self.records)
        victim=next(v for r in rs for v in r.get('workflows',{}).values() if v['status']=='STRICT_INTENDED_MATCH')
        victim['repaired']['conforms']=False
        with self.assertRaises(AssertionError):report_all.checks(rs)
    def test_guard_rejects_unrelated_credit(self):
        rs=copy.deepcopy(self.records)
        victim=next(v for r in rs if r['state']=='COMPLETED' for v in r['workflows'].values() if v['status']=='STRICT_INTENDED_MATCH')
        victim['violation_reason_review']['unrelated']=[{'component':'WrongField'}]
        with self.assertRaises(AssertionError):report_all.checks(rs)
    def test_guard_rejects_missed_defect_credit(self):
        rs=copy.deepcopy(self.records)
        victim=next(v for r in rs for v in r.get('workflows',{}).values() if v['status']=='STRICT_INTENDED_MATCH')
        victim['negative']['conforms']=True
        with self.assertRaises(AssertionError):report_all.checks(rs)
    def test_prior50_results_and_baseline_preserved_byte_for_byte(self):
        for path,expected in audit.read(OUT/'immutable_inputs.json').items():self.assertEqual(audit.sha(path),expected)
        original={(r['case_id'],r['condition']):r for r in audit.read(OLD/'strict_results.json') if r['arm']=='corrected_fixtures'}
        for r in self.records:
            if r['state']=='COMPLETED_PRIOR50':
                for w,v in r['workflows'].items():self.assertEqual(v,original[r['case_id'],w])
    def test_every_blocker_has_case_evidence(self):
        for r in self.records:
            if r['state']!='BLOCKED':continue
            self.assertTrue(r['blockers']);self.assertTrue(r['source_clause']);self.assertTrue(r['intended_rationale']);self.assertTrue(r.get('source_evidence'))
            for b in r['blockers']:self.assertTrue(b['code']);self.assertTrue(b['detail'])
    def test_negative_pairs_exactly_reuse_baseline_rdf(self):
        rows={r['case_id']:r for r in audit.read(BASE/'retained_rows.json') if r['condition']=='NO_SEMANTIC'}
        for r in self.records:
            if not r.get('negative_fixture'):continue
            source=BASE/'corrected_benchmark'/rows[r['case_id']]['rdf_path']
            self.assertEqual(set(Graph().parse(source)),set(Graph().parse(r['negative_fixture'])),r['case_id'])
    def test_unchanged_shape_snapshots_and_report_caches(self):
        for r in self.records:
            if r['state']=='COMPLETED_PRIOR50':continue
            for w,v in r.get('workflows',{}).items():
                folder=OUT/'cases'/r['case_id']/w
                if not v['original_eligible']:
                    self.assertIsNone(v['negative']);self.assertIsNone(v['repaired']);continue
                self.assertEqual(audit.sha(folder/'evaluated_shape.ttl'),v['shape_sha256'])
                self.assertEqual(audit.sha(v['negative']['report_path']),v['negative']['report_sha256'])
                self.assertEqual(v['negative']['report_sha256'],audit.sha(v['negative']['reused_from']))
    def test_atomic_record_history_exists_for_resume(self):
        self.assertTrue(any((OUT/'record_history').glob('*/*.json')))
    def test_every_admitted_pair_passes_independent_oracle_and_exact_delta(self):
        for r in self.records:
            if r['state']=='COMPLETED_PRIOR50' or not r.get('workflows'):continue
            bad=Graph().parse(r['negative_fixture']);good=Graph().parse(r['repaired_fixture'])
            oracle=evaluate.oracle_callable(r)
            self.assertTrue(oracle(good),r['case_id'])
            self.assertFalse(prepare.schema_issues(good),r['case_id'])
            self.assertTrue(not oracle(bad) or prepare.schema_issues(bad),r['case_id'])
            self.assertEqual(audit.triples(set(bad)-set(good)),r['selected_repair']['removed_triples'])
            self.assertEqual(audit.triples(set(good)-set(bad)),r['selected_repair']['added_triples'])
            self.assertEqual(len({p for s,p in prepare.semantic_roots(bad,good)}),1,r['case_id'])
            self.assertFalse(prepare.coupled_quantity_changes(bad,good),r['case_id'])
    def test_report_uses_common_case_ids_and_keeps_all_ordinary_tests(self):
        report=audit.read(OUT/'report.json')
        for scope in ['all_source_verified_pairs_including_semantic_blockers','fully_classified_common_subset']:
            counts=[r for r in report['strict_summary'] if r['scope']==scope]
            denominators={r['denominator'] for r in counts};self.assertEqual(len(denominators),1)
            for workflow in audit.WORKFLOWS.values():
                self.assertEqual(sum(r['count'] for r in counts if r['workflow']==workflow),next(iter(denominators)))
        for name in ['original_figure6.csv','corrected_after_exclusions_figure6.csv','corrected_after_exclusions_ordinary_verdicts.csv']:
            self.assertEqual(audit.sha(OUT/name),audit.sha(BASE/name))

if __name__=='__main__':unittest.main()
