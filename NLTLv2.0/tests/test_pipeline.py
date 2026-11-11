import unittest,os,json,copy,pathlib,socket
from rdflib import Graph
from nltlv2.core import Project,Candidate,finding,normalize,WrapperError,load,digest
from nltlv2.schema import Schema,N,U,Q
from nltlv2.checks import check,sparql_checks,regression
from nltlv2.runner import Runner
from nltlv2.transport import ScriptedTransport,LiveTransport
from nltlv2.requests import repair_request,assert_integrity,parse_review,ReviewerFormatError,review_conflicts,initial_request
from nltlv2.evaluation import strict_status,oracle,check_exclusions,validate_pair_graph,reference_shape,evaluate
from nltlv2.mappings import verify
from nltlv2.study import prepare_selection,budget_analysis
PREFIX='@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix n: <https://w3id.org/nltl/vocab#> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> . @prefix q: <http://qudt.org/schema/qudt/> . @prefix u: <http://qudt.org/vocab/unit/> .\n'
GOOD=PREFIX+'<urn:test:shape> a sh:NodeShape ; sh:targetClass n:ship ; sh:property [ sh:path n:iceClass ; sh:minCount 1 ; sh:in (n:iceClassIaSuper n:iceClassIa n:iceClassIb n:iceClassIc n:iceClassIi n:iceClassIii) ] .\n'
ACCEPT=json.dumps(dict(decision='ACCEPT',issues=[]))
def wrap(code,alt=False):return '<BEGIN_SHACL>\n'+code+('</END_SHACL>' if alt else '<END_SHACL>')+'\n'
class PipelineTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.p=Project(os.environ['NLTL_TEST_PROJECT']);cls.s=Schema(cls.p);cls.out=pathlib.Path(os.environ['NLTL_TEST_OUTPUT'])
 def run_script(self,responses,rid='TRF-010',single=False,limit=6,review_retries=1):
  cfg=self.p.config('configs/single_shot.json' if single else 'configs/nltl.json');cfg['maximum_candidate_attempts']=limit;cfg['review_format_retries']=review_retries
  path=self.out/self._testMethodName;path.mkdir(exist_ok=False);t=ScriptedTransport(responses);r=Runner(self.p,cfg,t,path).run(rid);return r,t,path
 def c(self,code):return Candidate(1,code,wrap(code))
 def categories(self,code,rid='TRF-010'):return {f.category for f in check(self.c(code),self.s,rid)}
 def test_valid_first_candidate(self):
  r,t,_=self.run_script([wrap(GOOD),ACCEPT]);self.assertEqual(r['status'],'ACCEPTED');self.assertEqual(len(t.calls),2)
 def test_exact_syntax_and_latest_repair(self):
  r,t,p=self.run_script([wrap(GOOD.replace('sh:targetClass','sh:targetClass ;')),wrap(GOOD),ACCEPT]);self.assertEqual(r['status'],'ACCEPTED');q=t.calls[1];self.assertEqual(q['route'],'syntax_repair');self.assertEqual(q['payload']['previous_candidate'],GOOD.replace('sh:targetClass','sh:targetClass ;'));self.assertTrue(q['payload']['current_findings'][0]['diagnostic']);self.assertTrue((p/'request_002_integrity.json').is_file())
 def test_alternate_marker_preserves_body(self):
  code='\n'+GOOD+'\n';body,meta=normalize(wrap(code,True));self.assertEqual(body,code);self.assertTrue(meta['alternate_closing_marker'])
 def test_reject_multiple_blocks(self):
  with self.assertRaises(WrapperError):normalize(wrap(GOOD)+wrap(GOOD))
 def test_marker_feedback_locations(self):
  r,t,_=self.run_script(['<BEGIN_SHACL>\n'+GOOD,wrap(GOOD),ACCEPT]);self.assertEqual(r['status'],'ACCEPTED');f=t.calls[1]['payload']['current_findings'][0];self.assertIn('observed',f['diagnostic']);self.assertIn('offset',f['diagnostic'])
 def test_canonical_unit_identifier(self):
  s=GOOD.replace('sh:in (','sh:hasValue q:KiloW ; sh:in (');self.assertIn('CANONICAL_IDENTIFIER_ERROR',self.categories(s));f=next(f for f in check(self.c(s),self.s,'TRF-010') if f.category=='CANONICAL_IDENTIFIER_ERROR');self.assertEqual(f.expected,str(U.KiloW))
 def test_term_kind(self):self.assertIn('TERM_KIND_ERROR',self.categories(GOOD.replace('sh:minCount 1','sh:datatype xsd:string ; sh:minCount 1')))
 def test_unit_scale(self):
  code=PREFIX+'<urn:s> a sh:NodeShape ; sh:targetClass n:ship ; sh:property [ sh:path n:hasStructuralMember ; sh:node [ sh:property [ sh:path n:flangeWidth ; sh:node [ sh:property [ sh:path q:unit ; sh:hasValue u:M ] ] ] ] ] .'
  self.assertIn('UNIT_CONSISTENCY_ERROR',self.categories(code,'I2-042'))
 def test_explicit_wrong_path(self):
  code=PREFIX+'<urn:s> a sh:NodeShape ; sh:targetClass n:ship ; sh:property [ sh:path n:shellInclinationAngle ; sh:minCount 1 ] .'
  self.assertIn('PATH_CONTRACT_ERROR',self.categories(code,'I2-005'))
 def test_correct_complete_path(self):
  code=PREFIX+'<urn:s> a sh:NodeShape ; sh:targetClass n:ship ; sh:property [ sh:path (n:hasBottomRegionLowerRegionBoundaryPoint n:shellInclinationAngle) ; sh:minCount 1 ] .'
  self.assertNotIn('PATH_CONTRACT_ERROR',self.categories(code,'I2-005'))
 def test_unknown_ownership_explicit(self):
  code=PREFIX+'<urn:s> a sh:NodeShape ; sh:targetClass n:ship ; sh:property [ sh:path n:upperIceWaterline ; sh:minCount 1 ] .'
  fs=check(self.c(code),self.s,'I2-004');self.assertTrue(any(f.category=='UNRESOLVED_CONTEXT' and not f.confirmed for f in fs));self.assertIn('upperIceWaterline',self.s.context('I2-004')['unresolvedOwnership'])
 def test_contradictory_reviewer_stops(self):
  ctx=self.s.context('TRF-010');issue=dict(category='SOURCE_BACKED_LOGIC_ERROR',source_clause=ctx['requirement']['clause'],source_excerpt=ctx['requirement']['text'],candidate_excerpt='n:iceClass',reason='Scripted conflicting ownership claim',expected='ship-independent ice class',suggestion='Move to another owner',evidence_excerpt=ctx['requirement']['text'],property=str(N.iceClass),proposed_path=[str(N.hasStructuralMember),str(N.iceClass)])
  r,t,p=self.run_script([wrap(GOOD),json.dumps(dict(decision='REJECT',issues=[issue]))]);self.assertEqual(r['status'],'CONFLICT');self.assertEqual(len(t.calls),2);self.assertTrue(r['history'][0]['conflicts'])
 def test_invalid_reviewer_json_retry(self):
  r,t,_=self.run_script([wrap(GOOD),'{bad',ACCEPT]);self.assertEqual(r['status'],'ACCEPTED');self.assertEqual(t.calls[-1]['route'],'review_format_retry');self.assertEqual(r['candidate_attempts'],1)
 def test_truncated_reviewer_failure_distinct(self):
  r,t,_=self.run_script([wrap(GOOD),dict(text=ACCEPT,finish_reason='length')],review_retries=0);self.assertEqual(r['status'],'REVIEWER_FORMAT_FAILURE');self.assertIsNone(r['accepted_version']);self.assertEqual(r['history'][0]['findings'],[])
 def test_bounded_reviewer_issues(self):
  with self.assertRaises(ReviewerFormatError):parse_review(dict(text=json.dumps(dict(decision='REJECT',issues=[{}]*13)),finish_reason='stop'),self.c(GOOD),self.s.context('TRF-010'))
 def test_unbound_sparql(self):
  query='SELECT $this WHERE { $this <urn:p> ?x . FILTER(?unknown > ?x) }';self.assertTrue(any('Unbound' in f.message for f in sparql_checks(self.c(GOOD),query)))
 def test_sparql_projection(self):self.assertTrue(sparql_checks(self.c(GOOD),'SELECT ?x WHERE { ?x <urn:p> ?v }'))
 def test_sparql_parser_log(self):self.assertTrue(sparql_checks(self.c(GOOD),'SELECT WHERE {')[0].diagnostic)
 def test_deleted_obligation_not_accepted(self):
  bad=GOOD.replace('sh:minCount 1','sh:datatype xsd:string ; sh:minCount 1');deleted=PREFIX+'<urn:test:shape> a sh:NodeShape ; sh:targetClass n:ship .\n'
  r,t,_=self.run_script([wrap(bad),wrap(deleted)],limit=2);self.assertEqual(r['status'],'ATTEMPT_LIMIT_EXHAUSTED');self.assertTrue(any(f['location']=='repair regression guard' for f in r['history'][-1]['findings']))
 def test_chained_latest_full_candidate(self):
  a=GOOD.replace('sh:targetClass','sh:targetClass ;');b=GOOD.replace('sh:minCount 1','sh:datatype xsd:string ; sh:minCount 1');r,t,_=self.run_script([wrap(a),wrap(b),wrap(GOOD),ACCEPT]);self.assertEqual(r['status'],'ACCEPTED');repairs=[q for q in t.calls if q['route'].endswith('repair')];self.assertEqual([q['payload']['previous_candidate'] for q in repairs],[a,b]);self.assertEqual([q['payload']['candidate_version'] for q in repairs],[1,2])
 def test_attempt_exhaustion(self):
  r,t,_=self.run_script([wrap(GOOD.replace('sh:targetClass','sh:targetClass ;'))]*3,limit=3);self.assertEqual(r['candidate_attempts'],3);self.assertEqual(len(t.calls),3);self.assertIsNone(r['evaluation_candidate'])
 def test_single_shot_exactly_one_call(self):
  r,t,_=self.run_script(['malformed response'],single=True);self.assertEqual(len(t.calls),1);self.assertEqual(r['status'],'SINGLE_SHOT_COMPLETE');self.assertEqual(r['history'][0]['findings'],[])
 def test_initial_request_identical_across_methods(self):
  context=self.s.context('TRF-010');configs=[self.p.config('configs/'+k+'.json') for k in ['nltl','single_shot']];reqs=[initial_request(self.p,context,{k:c[k] for k in ['model','generation_max_tokens','review_max_tokens']}) for c in configs];self.assertEqual(reqs[0],reqs[1])
 def test_integrity_negative_controls(self):
  c=self.c(GOOD);f=finding(c,'PARSE_ERROR','error',GOOD,evidence='parser',suggestion='correct syntax');req=repair_request(self.p,self.s.context('TRF-010'),c,[f]);assert_integrity(req,c)
  for change in ['absent','truncated','version','feedback','rendered']:
   r=copy.deepcopy(req)
   if change=='absent':r['payload'].pop('previous_candidate')
   if change=='truncated':r['payload']['previous_candidate']=GOOD[:20]
   if change=='version':r['payload']['candidate_version']=0
   if change=='feedback':r['payload']['current_findings'][0]['candidate_sha256']='bad'
   if change=='rendered':r['user']='{}'
   else:r['user']=json.dumps(r['payload'])
   with self.assertRaises(ValueError,msg=change):assert_integrity(r,c)
 def test_dispatch_boundary_rejects_stale(self):
  c=self.c(GOOD);f=finding(c,'PARSE_ERROR','error',suggestion='fix');r=repair_request(self.p,self.s.context('TRF-010'),c,[f]);t=ScriptedTransport([])
  with self.assertRaises(ValueError):t.dispatch(r,Candidate(2,GOOD,wrap(GOOD)))
 def test_intended_and_unrelated_attribution(self):
  self.assertEqual(strict_status(False,True,True,False),'VERIFIED_INTENDED_DETECTION');self.assertEqual(strict_status(False,True,False,True),'UNRELATED_OR_ADDITIONAL_FAILURE');self.assertEqual(strict_status(True,True,False,False),'MISSED_INTENDED_DEFECT');self.assertEqual(strict_status(False,False,True,False),'UNRELATED_OR_ADDITIONAL_FAILURE');self.assertEqual(strict_status(False,True,True,False,original_no_verdict=True),'NO_VERDICT');self.assertEqual(strict_status(False,True,True,False,certified=False),'UNRESOLVED_ATTRIBUTION')
 def test_identical_exclusions(self):
  self.assertEqual(check_exclusions({'NLTL':['invalid-a'],'Single-shot':['invalid-a']}),['invalid-a'])
  with self.assertRaises(ValueError):check_exclusions({'NLTL':['valid-test'],'Single-shot':[]})
 def test_project_paths_mapping_configs(self):
  result=verify(self.p);self.assertEqual(result['core'],37)
  for bad in ['../schema/a','/tmp/test']:
   with self.assertRaises(ValueError):self.p.path(bad)
  self.assertEqual(len(list(self.p.path('configs').glob('*.json'))),5)
 def test_output_no_overwrite(self):
  name='collision_'+self._testMethodName;p=self.p.output('audits',name)
  try:
   with self.assertRaises(FileExistsError):self.p.output('audits',name)
  finally:p.rmdir()
 def test_performance_blind_selection_gate(self):
  x=prepare_selection(self.p);self.assertEqual(x['gap_to_50'],44);self.assertEqual(len(set(x['review_queue_50'])),50);self.assertIn('PREPARED_NOT_RUN',x['status'])
 def test_prefix_selection_first_accepted(self):
  run=dict(requirement_id='TRF-010',history=[dict(attempt=i,version=i,accepted=i in [3,4]) for i in range(1,7)]);a=budget_analysis([run]);self.assertIsNone(a[0]['selected_version']);self.assertEqual([r['selected_version'] for r in a[1:]],[3]*4)
 def test_network_and_live_disabled(self):
  with self.assertRaises(RuntimeError):socket.create_connection(('example.invalid',443))
  with self.assertRaises(RuntimeError):LiveTransport()
 def test_schema_hash_unchanged(self):
  import hashlib
  manifest=load(self.p.path('schema/schema_changes.json'));self.assertEqual(hashlib.sha256(self.p.path('schema/Schema_for_NLTL.ttl').read_bytes()).hexdigest(),manifest['sha256']);self.assertEqual(manifest['rdf_changes'],[])

 def test_semantic_findings_reach_targeted_route(self):
  ctx=self.s.context('TRF-010');empty=PREFIX+'<urn:test:shape> a sh:NodeShape ; sh:targetClass n:ship .\n'
  issue=dict(category='SOURCE_BACKED_LOGIC_ERROR',source_clause=ctx['requirement']['clause'],source_excerpt=ctx['requirement']['text'],candidate_excerpt='sh:targetClass n:ship',reason='Missing required ice-class enumeration',expected='Required source-backed six-value ice-class constraint',suggestion='Add required iceClass constraint and six source classes; preserve target.',evidence_excerpt='iceClass')
  raw=json.dumps(dict(decision='REJECT',issues=[issue]));r,t,_=self.run_script([wrap(empty),raw,wrap(GOOD),ACCEPT]);self.assertEqual(r['status'],'ACCEPTED');q=next(q for q in t.calls if q['route']=='targeted_repair');self.assertEqual(q['payload']['current_findings'][0]['diagnostic'],raw);self.assertEqual(q['payload']['previous_candidate'],empty)
 def test_real_unrelated_rejection_and_counterfactual(self):
  core=load(self.p.path('evaluation/selections/regression_core.json'));case=next(c for c in core['cases'] if c['case_id']=='TRF-010-F01');g=Graph().parse(self.p.path(case['fixture']));repaired=Graph().parse(self.p.path(case['counterfactual']));shape,_=reference_shape('TRF-010')
  extra=Graph().parse(data=PREFIX+'<urn:unrelated> a sh:NodeShape ; sh:targetClass n:ship ; sh:property [ sh:path n:shipCategory ; sh:minCount 1 ] .',format='turtle');shape+=extra
  a,ar=validate_pair_graph(g,shape,self.s);b,br=validate_pair_graph(repaired,shape,self.s);self.assertFalse(a['conforms']);self.assertFalse(b['conforms']);self.assertEqual(strict_status(a['conforms'],b['conforms'],True,True),'UNRELATED_OR_ADDITIONAL_FAILURE')
  dest=self.out/self._testMethodName;dest.mkdir();ar.serialize(dest/'negative_report.ttl',format='turtle');br.serialize(dest/'repaired_report.ttl',format='turtle')
 def test_invalid_datatype_and_sparql_term_kind(self):
  self.assertIn('TERM_KIND_ERROR',self.categories(GOOD.replace('sh:minCount 1','sh:datatype xsd:invented ; sh:minCount 1')))
  code=PREFIX+'<urn:test> a sh:NodeShape ; sh:targetClass n:ship ; sh:sparql [ sh:select """PREFIX n: <https://w3id.org/nltl/vocab#> SELECT $this WHERE { $this n:iceClass "IA" }""" ] .'
  self.assertIn('TERM_KIND_ERROR',self.categories(code))

 def test_common_evaluation_preserves_original_no_verdict(self):
  dest=self.out/self._testMethodName;dest.mkdir();shape,_=reference_shape('TRF-010');shape.serialize(dest/'reference.ttl',format='turtle');relative=str(dest.relative_to(self.p.root));manifest=dict(workflows={'NLTL':{'TRF-010':dict(shape=relative+'/reference.ttl')},'Single-shot':{'TRF-010':dict(shape=relative+'/reference.ttl',original_no_verdict=True)}},excluded_case_ids={'NLTL':[],'Single-shot':[]})
  (dest/'manifest.json').write_text(json.dumps(manifest));out=dest/'evaluation';out.mkdir();r=evaluate(self.p,relative+'/manifest.json',out)
  self.assertEqual(r['summaries']['NLTL']['strict_counts']['VERIFIED_INTENDED_DETECTION'],2);self.assertEqual(r['summaries']['Single-shot']['no_verdict'],37);self.assertEqual(r['summaries']['Single-shot']['ordinary_agreement'],0)
 def test_feedback_cannot_be_relabelled_as_current(self):
  c=self.c(GOOD);f=finding(c,'PARSE_ERROR','original exact error',suggestion='fix original');request=repair_request(self.p,self.s.context('TRF-010'),c,[f]);request['payload']['current_findings'][0]['diagnostic']='different error';request['user']=json.dumps(request['payload'])
  with self.assertRaises(ValueError):assert_integrity(request,c,[f])
 def test_workbook_and_bundle_integrity(self):
  import zipfile,hashlib
  with zipfile.ZipFile(self.p.path('mappings/requirement_mapping.xlsx')) as z:
   self.assertIsNone(z.testzip());xml=z.read('xl/workbook.xml').decode();self.assertIn('Requirements',xml);self.assertIn('Cases',xml);self.assertIn('Dictionary',xml)
  lock=load(self.p.path('schema/schema_lock.json'))
  for name,sha in lock['files'].items():self.assertEqual(hashlib.sha256(self.p.path(name).read_bytes()).hexdigest(),sha)
 def test_shared_runtime_failure_is_not_conformance(self):
  from nltlv2.checks import runtime_probe
  code=PREFIX+'<urn:s> a sh:NodeShape ; sh:targetClass n:ship ; sh:sparql [ sh:select """SELECT ?wrong WHERE { $this <urn:p> ?wrong }""" ] .'
  self.assertIn('SPARQL_ERROR',self.categories(code))

 def test_runtime_exception_is_not_a_regulatory_verdict(self):
  from nltlv2.checks import runtime_probe
  code=PREFIX+'<urn:s> a sh:NodeShape ; sh:targetClass n:ship ; sh:property [ sh:path n:iceClass ; sh:minCount "invalid" ] .'
  fs,probe=runtime_probe(self.c(code),self.s);self.assertTrue(fs);self.assertTrue(probe['not_conformance']);self.assertIn('Local SHACL execution failed',fs[0].message)
 def test_known_source_exception_blocks_repairs(self):
  fs=check(self.c(GOOD),self.s,'TRF-002');self.assertTrue(any(f.category=='UNRESOLVED_CONTEXT' and 'Source context' in f.message for f in fs));self.assertTrue(self.s.context('TRF-002')['unresolvedSourceContext'])
 def test_single_shot_does_not_run_checkers(self):
  bad=GOOD.replace('sh:minCount 1','sh:datatype xsd:string ; sh:minCount 1');r,t,_=self.run_script([wrap(bad)],single=True);self.assertEqual(len(t.calls),1);self.assertEqual(r['history'][0]['findings'],[]);self.assertEqual(r['history'][0]['status'],'ORIGINAL_RESPONSE')
