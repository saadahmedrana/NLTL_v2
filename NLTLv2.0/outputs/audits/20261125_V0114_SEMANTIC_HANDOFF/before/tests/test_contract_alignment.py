"""Generic software evidence, never a regulatory compliance oracle or model call."""
import copy,json,os,pathlib,shutil,unittest
import test_general_pipeline as base
from nltlv2.core import Candidate,digest
from nltlv2.evidence import evidence_catalog,code_location,wire_catalog
from nltlv2.review_protocol import reviewer_schema,contract_instructions
from nltlv2.review_validation import validate_review
from nltlv2.requests import parse_review,review_base
from nltlv2.context_resolution import Resolver
from nltlv2.source_context import select_document

class AlignmentControls(unittest.TestCase):
 setUp=base.GeneralPipelineTests.setUp;tearDown=base.GeneralPipelineTests.tearDown;write=base.GeneralPipelineTests.write;run_local=base.GeneralPipelineTests.run_local;accepting=base.GeneralPipelineTests.accepting
 def response(self,decision='ACCEPT',context=None):
  ctx=context or self.s.context('NOVEL-RULE');c=Candidate(1,base.GOOD,'');r={'user':json.dumps(dict(context=ctx,full_candidate=c.code,previous_candidate=None,change_manifest={'changes':[]},prior_issues=[]))};obj=json.loads(base.review_response(r));obj['decision']=decision;return c,ctx,r,obj
 def errors(self,c,ctx,obj):return validate_review({'text':json.dumps(obj)},c,ctx)[2]
 def test_optional_source_reference_omitted_or_null_not_blank(self):
  c,ctx,r,obj=self.response('REQUEST_EVIDENCE');obj['evidence_requests']=[dict(kind='source',query='Application',reason='Missing source scope')]
  self.assertFalse(self.errors(c,ctx,obj));obj['evidence_requests'][0]['reference']=None;self.assertFalse(self.errors(c,ctx,obj));obj['evidence_requests'][0]['reference']='';self.assertIn('INVALID_SOURCE_REFERENCE',[e['code'] for e in self.errors(c,ctx,obj)])
 def test_optional_reference_search_stays_with_supplied_documents(self):
  base.software_admission(self);self.s=base.Schema(self.p);ctx=self.s.context('NOVEL-RULE');res=Resolver(self.s,{})
  new,event=res.resolve(ctx,[dict(kind='source',query=base.SOURCE,reason='Need context')],'NOVEL-RULE');self.assertTrue(all(e.get('reference') in [None,'SOFTWARE SOURCE'] for e in event['entries']));self.assertLessEqual(len(res.cache),res.policy['max_source_documents'])
 def test_context_only_issue_has_no_invented_code_anchor(self):
  c,ctx,r,obj=self.response('UNRESOLVED');issue=base.issue_for(r,'UNRESOLVED_CONTEXT');
  for key in ['source_clause','source_evidence_id','source_excerpt','candidate_excerpt','candidate_location','insertion_context']:issue.pop(key,None)
  issue.update(reason='Missing declared input context',expected='Supply context',suggestion='Retrieve source without editing code',candidate_location=None);obj['issues']=[issue]
  self.assertFalse(self.errors(c,ctx,obj));review,findings=parse_review({'text':json.dumps(obj)},c,ctx);self.assertEqual(findings[0].excerpt,'');self.assertEqual(findings[0].category,'UNRESOLVED_CONTEXT');self.assertNotIn('line',findings[0].location)
  issue['candidate_location']=code_location(Candidate(2,c.code,''),0,2);self.assertTrue(any(e['code']=='STALE_CODE_LOCATION' for e in self.errors(c,ctx,obj)))
 def test_technical_issue_uses_supplied_scope_not_law(self):
  base.software_admission(self);ctx=self.s.context('NOVEL-RULE');ctx['admission']={'approved':'Synthetic software scope'};c,ctx,r,obj=self.response('REJECT',ctx);issue=base.issue_for(r)
  for key in ['source_clause','source_evidence_id','source_excerpt']:issue.pop(key,None)
  fact=next(e for e in evidence_catalog(ctx)['entries'] if e['kind']=='CALLER_DECLARATION');issue.update(category='TECHNICAL_REPRESENTATION_ERROR',evidence_id=fact['evidence_id'],evidence_excerpt=fact['text'],reason='An asserted global target exceeds the supplied focus population',expected='Only declared root population',suggestion='Correct the evidenced target and preserve reachable constraints')
  obj['issues']=[issue];self.assertFalse(self.errors(c,ctx,obj));self.assertEqual(parse_review({'text':json.dumps(obj)},c,ctx)[1][0].category,'TECHNICAL_REPRESENTATION_ERROR');issue['evidence_id']='UNKNOWN';self.assertTrue(self.errors(c,ctx,obj))
 def test_optional_asserted_source_is_still_checked(self):
  c,ctx,r,obj=self.response('UNRESOLVED');issue=base.issue_for(r,'UNRESOLVED_CONTEXT');issue['source_excerpt']='INVENTED';obj['issues']=[issue];self.assertIn('INVALID_SOURCE_QUOTATION',[e['code'] for e in self.errors(c,ctx,obj)])
 def test_context_only_state_not_a_repairable_reject_or_approval(self):
  c,ctx,r,obj=self.response('UNRESOLVED');obj['unchecked']=[dict(scope='Missing owner context',material=True,reason='Not supplied')];self.assertFalse(self.errors(c,ctx,obj))
  for decision in ['ACCEPT','REJECT']:
   obj['decision']=decision;self.assertIn('DECISION_ISSUE_CONTRADICTION',[e['code'] for e in self.errors(c,ctx,obj)])
  obj.update(decision='UNRESOLVED',unchecked=[]);self.assertTrue(self.errors(c,ctx,obj))
 def test_gap_assessment_explicit_for_accept_including_nonmaterial(self):
  ctx=self.s.context('NOVEL-RULE');ctx['retrieval_gaps']=[dict(gap_id='gap-1',evidence='Missing cited document')];c,ctx,r,obj=self.response(context=ctx);self.assertIn('UNASSESSED_RETRIEVAL_GAP',[e['code'] for e in self.errors(c,ctx,obj)])
  obj['unchecked']=[dict(scope='gap-1',material=False,reason='Outside supplied represented task')];self.assertFalse(self.errors(c,ctx,obj))
  obj['unchecked'][0]['material']=True;self.assertTrue(self.errors(c,ctx,obj));obj['decision']='UNRESOLVED';self.assertFalse(self.errors(c,ctx,obj))
 def test_schema_and_runtime_share_authority_and_decision_contract(self):
  s=reviewer_schema(primary_clause='A.1');self.assertEqual(s['description'],contract_instructions());i=s['properties']['issues']['items'];self.assertEqual(i['properties']['source_clause']['anyOf'][0],{'const':'A.1'});self.assertNotIn('candidate_location',i['required']);self.assertNotIn('reference',s['properties']['evidence_requests']['items']['required']);self.assertIn('candidate_location',i['allOf'][0]['then']['required'])
 def test_retry_keeps_rejected_text_once_and_original_state(self):
  first=[];bad=[]
  def handler(r,n):
   if r['route']=='generation':return base.wrap(base.BAD_EXTRA)
   if r['route'].endswith('repair'):return base.wrap(base.GOOD)
   if json.loads(r['user'])['candidate_version']==2:return base.review_response(r)
   wire=json.loads(r['user']);obj=json.loads(base.review_response(r,'REJECT',base.issue_for(r)))
   if r['route']=='review':first.append(copy.deepcopy(wire));obj['issues'][0]['evidence_id']='UNKNOWN';bad.append(json.dumps(obj));return bad[-1]
   self.assertEqual(review_base(wire),first[0]);self.assertEqual(wire['format_feedback']['rejected_response'],bad[0]);self.assertEqual(wire['prior_issues'],[]);return json.dumps(obj)
  result,t,out=self.run_local(handler);self.assertEqual(result['accepted_version'],2);self.assertEqual(result['auxiliary_format_retries'],1)
 def test_only_duplicate_retrieval_triples_removed(self):
  ctx=self.s.context('NOVEL-RULE');triples=copy.deepcopy(ctx['ontology_evidence']);ctx['retrieval_evidence']=[dict(kind='schema',ontology_triples=triples,status='RETRIEVED',representation_mappings=[{'owner':'supplied'}])];cat=evidence_catalog(ctx);entry=next(e for e in cat['entries'] if e['origin'].get('context_field')=='retrieval_evidence');self.assertNotIn('ontology_triples',entry['text']);self.assertIn('representation_mappings',entry['text']);self.assertEqual(ctx['ontology_evidence'],triples);self.assertTrue(any(e['kind']=='RDF_FACT' for e in cat['entries']))
 def test_definition_table_does_not_pull_unrelated_section_but_explicit_reference_does(self):
  text='1 Application\n1.1 Scope for all supplied records.\n2 Definitions\n2.1 A record is a supplied claim.\nTable 9-1: Definition of loads\nRefer to section 9.1.\n3.1 Primary obligation.\n9.1 Other mechanics.\n';doc=dict(file='source.txt',sha256=digest(text),text=text);record={'text':'3.1 Primary obligation.'};docs,manifest=select_document(doc,record);joined=''.join(d['text'] for d in docs);self.assertIn(record['text'],joined);self.assertIn('A record is',joined);self.assertNotIn('Other mechanics',joined)
  record={'text':'3.1 Primary obligation. Refer to section 9.1.'};changed=text.replace('3.1 Primary obligation.',record['text']);docs,_=select_document(dict(doc,text=changed,sha256=digest(changed)),record);self.assertIn('Other mechanics',''.join(d['text'] for d in docs))
 def test_one_technical_then_one_semantic_full_delivery_example(self):
  bad=base.GOOD.replace('a sh:NodeShape;','a ;')
  def handler(r,n):
   if r['route']=='generation':return base.wrap(bad)
   if r['route'].endswith('repair'):return base.wrap(base.BAD_EXTRA if r['repair_type']=='technical' else base.GOOD)
   wire=json.loads(r['user']);return base.review_response(r,'REJECT',base.issue_for(r)) if wire['candidate_version']==2 else base.review_response(r)
  cfg=self.p.config('configs/nltl.json');cfg['delivery_policy']='latest_technical';result,t,out=self.run_local(handler,cfg=cfg);self.assertEqual(result['repair_counts'],{'technical':1,'semantic':1});self.assertEqual(result['accepted_version'],3);self.assertEqual(result['delivery']['status'],'ACCEPTED');self.assertEqual([q['repair_type'] for q in t.calls if q['route'].endswith('repair')],['technical','semantic'])
  if os.environ.get('NLTL_ALIGNMENT_EXAMPLE'):shutil.copytree(out,pathlib.Path(os.environ['NLTL_ALIGNMENT_EXAMPLE'])/'scripted_technical_semantic_example',dirs_exist_ok=True)
 def test_semantic_error_after_spent_technical_slot_gets_no_hidden_revision(self):
  bad=base.GOOD.replace('a sh:NodeShape;','a ;')
  def handler(r,n):
   if r['route']=='generation':return base.wrap(bad)
   if r['route'].endswith('repair'):return base.wrap(base.BAD_EXTRA if r['repair_type']=='technical' else bad)
   return base.review_response(r,'REJECT',base.issue_for(r))
  cfg=self.p.config('configs/nltl.json');cfg['delivery_policy']='latest_technical';result,t,out=self.run_local(handler,cfg=cfg);self.assertEqual(result['repair_calls'],2);self.assertEqual(result['candidate_attempts'],3);self.assertEqual(result['repair_counts'],{'technical':1,'semantic':1});self.assertTrue(any(f['category']=='PARSE_ERROR' for f in result['history'][-1]['findings']));self.assertEqual(result['delivery']['version'],2);self.assertEqual(result['delivery']['status'],'UNVERIFIED')
 def test_repeated_technical_failure_stops_with_unused_semantic_slot(self):
  bad=base.GOOD.replace('a sh:NodeShape;','a ;');result,t,out=self.run_local(lambda r,n:base.wrap(bad));self.assertEqual(result['repair_counts'],{'technical':1,'semantic':0});self.assertEqual(result['repair_calls'],1);self.assertEqual(result['status'],'REPAIR_TYPE_LIMIT_EXHAUSTED')
 def test_early_acceptance_does_not_force_repairs(self):
  result,t,out=self.run_local(self.accepting);self.assertEqual(result['repair_counts'],{'technical':0,'semantic':0});self.assertEqual(len(t.calls),2);self.assertEqual(result['effective_review_limits'],dict(primary_total=4,primary_per_candidate=3,shared_corrections_per_review=1,retrieval_rounds=2))

 def test_technical_change_assessment_needs_schema_or_scope_not_source(self):
  from nltlv2.change_review import manifest
  old=Candidate(1,base.BAD_EXTRA,'');c=Candidate(2,base.GOOD,'');ctx=self.s.context('NOVEL-RULE');ctx['admission']={'scope':'Supplied synthetic root population'};changes=manifest(old,c)
  r={'user':json.dumps(dict(context=ctx,full_candidate=c.code,candidate_version=2,previous_candidate=dict(version=1,full_code=old.code),change_manifest=changes,prior_issues=[]))};obj=json.loads(base.review_response(r));entry=next(e for e in evidence_catalog(ctx)['entries'] if e['kind']=='CALLER_DECLARATION')
  for change in obj['change_assessments']:
   change.pop('source_excerpt');change.pop('source_evidence_id');change.pop('removal_assessments',None);change.update(claim_basis='TECHNICAL',evidence_id=entry['evidence_id'],evidence_excerpt=entry['text'],removal_disposition='SUPPORTED_REMOVAL')
  self.assertFalse(validate_review({'text':json.dumps(obj)},c,ctx,previous=old,changes=changes)[2])
  obj['change_assessments'][0]['source_evidence_id']=entry['evidence_id'];obj['change_assessments'][0]['source_excerpt']=entry['text'];self.assertIn('SOURCE_ID_KIND_MISMATCH',[e['code'] for e in validate_review({'text':json.dumps(obj)},c,ctx,previous=old,changes=changes)[2]])
 def test_pending_unresolved_change_does_not_require_invented_code_issue(self):
  from nltlv2.change_review import manifest
  old=Candidate(1,base.BAD_EXTRA,'');c=Candidate(2,base.GOOD,'');ctx=self.s.context('NOVEL-RULE');changes=manifest(old,c);r={'user':json.dumps(dict(context=ctx,full_candidate=c.code,candidate_version=2,previous_candidate=dict(version=1,full_code=old.code),change_manifest=changes,prior_issues=[]))};obj=json.loads(base.review_response(r,change_state='UNRESOLVED'));obj.update(decision='REQUEST_EVIDENCE',evidence_requests=[dict(kind='source',query='Missing supporting context',reason='Cannot assess change yet')]);self.assertFalse(validate_review({'text':json.dumps(obj)},c,ctx,previous=old,changes=changes)[2]);self.assertEqual(obj['issues'],[])
 def test_unrepresented_retrieval_facts_are_not_discarded(self):
  ctx=self.s.context('NOVEL-RULE');extra=['<urn:new>','<urn:predicate>','<urn:object>'];ctx['retrieval_evidence']=[dict(ontology_triples=[extra])];entry=next(e for e in evidence_catalog(ctx)['entries'] if e['origin'].get('context_field')=='retrieval_evidence');self.assertIn('urn:new',entry['text'])

 def test_missing_information_assessment_needs_evidence_but_no_offending_location(self):
  c,ctx,r,obj=self.response('UNRESOLVED');entry=next(e for e in evidence_catalog(ctx)['entries'] if e['kind']=='SCHEMA_TEXT');obj['unchecked']=[dict(scope='Missing context',material=True,reason='No supplied ownership decision')];assessment=dict(finding_key='missing-context',disposition='MISSING_INFORMATION',evidence_id=entry['evidence_id'],evidence_excerpt=entry['text'],reason='The supplied metadata does not establish the missing context');obj['context_assessments']=[assessment];self.assertFalse(self.errors(c,ctx,obj));assessment.update(disposition='REPAIRABLE_CODE',claim_basis='CONTEXT');self.assertIn('CONTEXT_CANNOT_AUTHORIZE_REPAIR',[e['code'] for e in self.errors(c,ctx,obj)])
