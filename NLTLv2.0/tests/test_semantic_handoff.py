"""Current small-contract controls: generic synthetic software evidence only."""
import copy,json,os,pathlib,shutil,unittest
import test_general_pipeline as base
from nltlv2.core import Candidate,digest
from nltlv2.requests import parse_review,assert_integrity,review_base
from nltlv2.review_protocol import reviewer_schema
from nltlv2.review_validation import validate_review
from nltlv2.evidence import evidence_catalog
from nltlv2.change_review import manifest

def answer(request,assessment='APPROVE',issues=None,questions=None):
 w=json.loads(request['user']);source=next(e for e in w['evidence_catalog']['entries'] if e['kind']=='SOURCE')
 obj=dict(assessment=assessment,issues=issues or [],questions=questions or [])
 if w['change_manifest']['changes']:obj['change_review']=[dict(id=c['id'],disposition='SUPPORTED',reason='Compared the generic source, previous code, current code and reachable obligations',evidence=[source['evidence_id']]) for c in w['change_manifest']['changes']]
 if w.get('retrieval_gaps'):obj['gap_review']=[dict(id=g['id'],material=False,why='Outside the represented synthetic obligation') for g in w['retrieval_gaps']]
 return json.dumps(obj)
def issue(request):
 w=json.loads(request['user']);source=next(e for e in w['evidence_catalog']['entries'] if e['kind']=='SOURCE');code=w['full_candidate'];start=code.index('sh:maxCount 1')
 return dict(description='The synthetic source explicitly imposes no maximum count; this maximum is unsupported.',evidence=[source['evidence_id']],location=dict(start=start,end=start+len('sh:maxCount 1'),unit='characters'),suggestion='Remove only this maximum; preserve the required boolean recording obligation and other constraints.')
class SmallHandoffControls(unittest.TestCase):
 setUp=base.GeneralPipelineTests.setUp;tearDown=base.GeneralPipelineTests.tearDown;write=base.GeneralPipelineTests.write
 def run4(self,handler,**overrides):
  cfg=self.p.config('configs/nltl.json');cfg.update(review_contract_version=4,delivery_policy='latest_technical',**overrides);return base.GeneralPipelineTests.run_local(self,handler,cfg=cfg)
 def control(self,assessment='REJECT'):
  c=Candidate(1,base.BAD_EXTRA,'');ctx=self.s.context('NOVEL-RULE');cat=evidence_catalog(ctx);source=next(e for e in cat['entries'] if e['kind']=='SOURCE');a=c.code.index('sh:maxCount 1');obj=dict(assessment=assessment,issues=[dict(description='Unsupported synthetic maximum',evidence=[source['evidence_id']],location=dict(start=a,end=a+len('sh:maxCount 1'),unit='characters'),suggestion='Remove only the maximum; keep the other represented obligation')],questions=[]);return c,ctx,obj
 def errors(self,c,ctx,obj,**kw):return validate_review(dict(text=json.dumps(obj)),c,ctx,**kw)[2]
 def test_schema_has_three_initial_response_fields_not_software_metadata(self):
  s=reviewer_schema();self.assertEqual(s['required'],['assessment','issues','questions']);self.assertLess(len(json.dumps(s)),4500);self.assertNotIn('candidate_sha256',json.dumps(s));self.assertNotIn('reconciliations',s['properties'])
 def test_software_extracts_exact_evidence_code_and_binds_findings(self):
  c,ctx,o=self.control();review,fs=parse_review(dict(text=json.dumps(o)),c,ctx);self.assertEqual(fs[0].candidate_sha256,c.sha256);self.assertEqual(fs[0].excerpt,'sh:maxCount 1');self.assertEqual(fs[0].diagnostic,json.dumps(o));refs=json.loads(fs[0].evidence)['resolved_evidence'];self.assertEqual(refs[0]['text'],base.SOURCE);self.assertEqual(refs[0]['text_sha256'],digest(base.SOURCE));self.assertTrue(review['software_owned_metadata'])
 def test_context_question_requires_no_code_issue_or_quote(self):
  c,ctx,o=self.control();o.update(assessment='HUMAN_REVIEW_REQUIRED',issues=[],questions=[dict(missing='Declared ownership mapping',why='Need it to locate the represented value',kind='schema')]);review,fs=parse_review(dict(text=json.dumps(o)),c,ctx);self.assertEqual(review['issues'],[]);self.assertTrue(all(f.category=='UNRESOLVED_CONTEXT' for f in fs));self.assertTrue(all(not f.excerpt for f in fs))
 def test_unknown_reference_invalid_location_and_optional_false_quote_fail(self):
  c,ctx,o=self.control();o['issues'][0]['evidence']=['UNKNOWN'];self.assertTrue(self.errors(c,ctx,o));c,ctx,o=self.control();o['issues'][0]['location']['end']=999999;self.assertTrue(self.errors(c,ctx,o));c,ctx,o=self.control();o['issues'][0]['evidence']=[dict(id=o['issues'][0]['evidence'][0],quote='Invented quotation')];self.assertIn('INVALID_SOURCE_QUOTATION',[e['code'] for e in self.errors(c,ctx,o)])
 def test_partial_and_unknown_metadata_are_not_accepted(self):
  c,ctx,o=self.control();o.pop('questions');self.assertTrue(self.errors(c,ctx,o));c,ctx,o=self.control();o['candidate_sha256']=c.sha256;self.assertIn('UNKNOWN_REVIEW_FIELD',[e['code'] for e in self.errors(c,ctx,o)])
 def test_decision_consistency_is_not_relaxed(self):
  for assessment,issues,questions in [('APPROVE',True,False),('REJECT',False,False),('HUMAN_REVIEW_REQUIRED',True,False)]:
   c,ctx,o=self.control();o['assessment']=assessment
   if not issues:o['issues']=[]
   self.assertIn('DECISION_ISSUE_CONTRADICTION',[e['code'] for e in self.errors(c,ctx,o)])
 def test_context_status_alone_cannot_authorize_code_repair(self):
  c,ctx,o=self.control();ctx['retrieval_gaps']=[dict(gap_id='gap',evidence='Missing document')];e=next(e for e in evidence_catalog(ctx)['entries'] if e['kind']=='CONTEXT_STATUS');o['issues'][0]['evidence']=[e['evidence_id']];o['gap_review']=[];self.assertIn('UNSUPPORTED_CODE_ASSERTION',[e['code'] for e in self.errors(c,ctx,o)])
 def test_empty_or_unreviewed_change_does_not_approve_removal(self):
  old=Candidate(1,base.BAD_EXTRA,'');c=Candidate(2,base.GOOD,'');ctx=self.s.context('NOVEL-RULE');o=dict(assessment='APPROVE',issues=[],questions=[]);self.assertTrue(self.errors(c,ctx,o,previous=old,changes=manifest(old,c)))
 def test_material_gap_requires_question_and_blocks_approval(self):
  c,ctx,o=self.control();ctx['retrieval_gaps']=[dict(gap_id='gap',evidence='Missing source')];o.update(assessment='APPROVE',issues=[]);self.assertTrue(self.errors(c,ctx,o));o['gap_review']=[dict(id='G1',material=True,why='Matters')];self.assertTrue(self.errors(c,ctx,o));o.update(assessment='HUMAN_REVIEW_REQUIRED',questions=[dict(missing='Missing source',why='Matters',kind='source')]);self.assertFalse(self.errors(c,ctx,o))
 def test_valid_feedback_reaches_same_generator_and_rechecks(self):
  seen=[]
  def handler(q,n):
   if q['route']=='generation':return base.wrap(base.BAD_EXTRA)
   if q['route'].endswith('repair'):
    p=q['payload'];self.assertEqual(q['model'],'SCRIPTED-OFFLINE');self.assertEqual(p['previous_candidate'],base.BAD_EXTRA);self.assertEqual(q['repair_type'],'semantic');self.assertIn('"assessment": "REJECT"',p['current_findings'][-1]['diagnostic']);assert_integrity(q,Candidate(1,base.BAD_EXTRA,''),None);self.assertTrue(p['current_findings'][-1]['evidence']['resolved_evidence']);seen.append(q);return base.wrap(base.GOOD)
   return answer(q,'REJECT',[issue(q)]) if json.loads(q['user'])['candidate_version']==1 else answer(q)
  r,t,out=self.run4(handler);self.assertEqual(r['accepted_version'],2);self.assertEqual(r['repair_counts'],dict(technical=0,semantic=1));self.assertEqual(len(seen),1);self.assertEqual(r['history'][1]['changes']['resolved']!=[],True)
  if os.environ.get('NLTL_HANDOFF_EXAMPLE'):shutil.copytree(out,pathlib.Path(os.environ['NLTL_HANDOFF_EXAMPLE'])/'complete_current_handoff',dirs_exist_ok=True)
 def test_unknown_reference_uses_one_correction_not_a_repair(self):
  saved=[]
  def handler(q,n):
   if q['route']=='generation':return base.wrap(base.BAD_EXTRA)
   if q['route'].endswith('repair'):return base.wrap(base.GOOD)
   w=json.loads(q['user'])
   if w['candidate_version']==2:return answer(q)
   x=issue(q)
   if q['route']=='review':saved.append(copy.deepcopy(w));x['evidence']=['UNKNOWN']
   else:self.assertEqual(review_base(w),saved[0]);self.assertEqual(w['prior_issues'],[]);self.assertTrue(w['format_feedback']['rejected_response_is_not_prior_state'])
   return answer(q,'REJECT',[x])
  r,t,out=self.run4(handler);self.assertEqual(r['repair_calls'],1);self.assertEqual(r['auxiliary_format_retries'],1)
 def test_failed_reviews_never_authorize_repair(self):
  r,t,out=self.run4(lambda q,n:base.wrap(base.GOOD) if q['route']=='generation' else '{}');self.assertEqual(r['status'],'REVIEWER_FORMAT_FAILURE');self.assertEqual(r['repair_calls'],0);self.assertEqual(r['delivery']['status'],'UNVERIFIED')
 def test_prior_material_question_survives_later_bad_review(self):
  import test_v080 as old
  old.ResolutionControls.document(self);self.s=base.Schema(self.p)
  def handler(q,n):
   if q['route']=='generation':return base.wrap(base.GOOD)
   if n==2:return answer(q,'HUMAN_REVIEW_REQUIRED',questions=[dict(missing='Application scope',why='Need source applicability context',kind='source',reference='UR B2')])
   return '{}'
  r,t,out=self.run4(handler);self.assertEqual(r['status'],'REVIEWER_FORMAT_FAILURE');self.assertTrue(r['delivery']['context_pending']);self.assertTrue(r['delivery']['findings']);self.assertEqual(r['delivery']['final_review'],'HUMAN_REVIEW_REQUIRED');self.assertEqual(r['repair_calls'],0)
 def test_technical_then_semantic_two_slots_no_regeneration(self):
  bad=base.GOOD.replace('a sh:NodeShape;','a ;')
  def handler(q,n):
   if q['route']=='generation':return base.wrap(bad)
   if q['route'].endswith('repair'):return base.wrap(base.BAD_EXTRA if q['repair_type']=='technical' else base.GOOD)
   return answer(q,'REJECT',[issue(q)]) if json.loads(q['user'])['candidate_version']==2 else answer(q)
  r,t,out=self.run4(handler);self.assertEqual(r['repair_counts'],dict(technical=1,semantic=1));self.assertEqual(r['accepted_version'],3);self.assertEqual(r['effective_max_provider_calls'],11)
 def test_semantic_revision_error_after_spent_technical_slot_is_retained(self):
  bad=base.GOOD.replace('a sh:NodeShape;','a ;')
  def handler(q,n):
   if q['route']=='generation':return base.wrap(bad)
   if q['route'].endswith('repair'):return base.wrap(base.BAD_EXTRA if q['repair_type']=='technical' else bad)
   return answer(q,'REJECT',[issue(q)])
  r,t,out=self.run4(handler);self.assertEqual(r['repair_calls'],2);self.assertEqual(r['candidate_attempts'],3);self.assertTrue(any(f['category']=='PARSE_ERROR' for f in r['history'][-1]['findings']));self.assertEqual(r['delivery']['version'],2);self.assertFalse(r['accepted_version'])
 def test_early_approval_does_not_force_repair(self):
  r,t,out=self.run4(lambda q,n:base.wrap(base.GOOD) if q['route']=='generation' else answer(q));self.assertEqual(r['accepted_version'],1);self.assertEqual(r['repair_calls'],0)
 def test_legacy_contract_cannot_be_used_with_live_transport(self):
  from nltlv2.runner import Runner
  class Live:is_live=True
  cfg=self.p.config('configs/nltl.json');cfg['review_contract_version']=3
  with self.assertRaisesRegex(ValueError,'OFFLINE_ONLY'):Runner(self.p,cfg,Live(),self.root)
 def test_stable_issue_identity_does_not_depend_on_model_hash_echo_or_lines(self):
  c,ctx,o=self.control();a=parse_review(dict(text=json.dumps(o)),c,ctx)[0]['issues'][0]['issue_id'];c2=Candidate(2,c.code+'\n','');b=parse_review(dict(text=json.dumps(o)),c2,ctx)[0]['issues'][0]['issue_id'];self.assertEqual(a,b)

 def test_asserted_rdf_numeric_lexical_change_is_still_rejected(self):
  c,ctx,o=self.control();ctx['ontology_evidence']+=[['<urn:a>','<urn:p>','"7"^^<http://www.w3.org/2001/XMLSchema#decimal>']];e=next(e for e in evidence_catalog(ctx)['entries'] if e['kind']=='RDF_FACT' and '<urn:a>' in e['text']);o['issues'][0]['evidence']=[dict(id=e['evidence_id'],quote=e['text'].replace('"7"','"7.0"'))];self.assertIn('ALTERED_OR_UNSUPPORTED_RDF_FACT',[e['code'] for e in self.errors(c,ctx,o)])
 def test_current_operand_role_routing_preserves_mapping_conflicts(self):
  from nltlv2.schema import Schema,N
  from nltlv2.requests import review_proposal_routing
  self.write('schema/representation_bindings.json',{'requirements':{'NOVEL-RULE':{'terms':['probeLength'],'owners':{'probeLength':'ship'},'target_owner':'ship','model_paths':[]}}});self.s=Schema(self.p);c,ctx,o=self.control();prop=str(N.probeLength);operand=dict(property=prop,path=[prop,self.s.quantity_profile['numeric_predicate']],role='NUMERIC_OPERAND');o['issues'][0]['operands']=[operand];review,fs=parse_review(dict(text=json.dumps(o)),c,ctx);self.assertEqual(review_proposal_routing(review,self.s,'NOVEL-RULE',ctx)['route'],'VALID');operand['path'].append('urn:unknown');review,fs=parse_review(dict(text=json.dumps(o)),c,ctx);self.assertTrue(review_proposal_routing(review,self.s,'NOVEL-RULE',ctx)['blocking'])

 def test_rdf_reference_cannot_turn_a_partial_literal_into_a_fact(self):
  c,ctx,o=self.control();entry=next(e for e in evidence_catalog(ctx)['entries'] if e['kind']=='RDF_FACT');o['issues'][0]['evidence']=[dict(id=entry['evidence_id'],start=0,end=2)];self.assertIn('RDF_FACT_REFERENCE_MUST_BE_WHOLE_FACT',[e['code'] for e in self.errors(c,ctx,o)])
