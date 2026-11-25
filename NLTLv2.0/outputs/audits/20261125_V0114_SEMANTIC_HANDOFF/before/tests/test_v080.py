
import unittest,json,pathlib,copy
from unittest.mock import patch
import test_general_pipeline as base
from nltlv2.core import Candidate,GenerationProject,digest
from nltlv2.context_resolution import Resolver
from nltlv2.schema import Schema,N
from nltlv2.source_context import references
from nltlv2.requests import parse_review,ReviewerFormatError
from nltlv2.runner import Runner
INACTIVE=base.GOOD.replace('a sh:NodeShape;','a sh:NodeShape; sh:deactivated true;')
def req(reference,revision=None,section=None):return dict(kind='source',reference=reference,revision=revision,section=section,query='Application scope',reason='Software dependency test')
def evidence_request(request,items):
 o=json.loads(base.review_response(request));o.update(decision='REQUEST_EVIDENCE',issues=[],evidence_requests=items);return json.dumps(o)
def context_issue(request):
 x=base.issue_for(request,'UNRESOLVED_CONTEXT');x.update(issue_id='uncertain-activation',candidate_excerpt='sh:deactivated true',reason='Applicability binding needs source evidence',expected='Explicit source-backed scope',suggestion='Retrieve evidence; do not activate by assumption');return x
class ResolutionControls(unittest.TestCase):
 setUp=base.GeneralPipelineTests.setUp;tearDown=base.GeneralPipelineTests.tearDown;write=base.GeneralPipelineTests.write;run_local=base.GeneralPipelineTests.run_local;accepting=base.GeneralPipelineTests.accepting
 def document(self,code='UR B2',text=None,revision=1,authority='SoftwareAuthority',name=None):
  text=text or 'B2.1 Application\nB2.1.1 This software scope applies to every ship record in this test representation.\nB2.2 Unrelated\nB2.2.1 Other words.\n';file='data/requirements/'+(name or code.replace(' ','_'))+'.txt';(self.root/file).write_text(text);catalog=json.loads((self.root/'data/requirements/source_catalog.json').read_text());catalog['sources'][name or code]=dict(file=file,sha256=digest(text),document_id=code,authority=authority,edition='Rev.'+str(revision),revision=revision,provenance={'kind':'Synthetic source for reusable software tests, not a real regulation'});self.write('data/requirements/source_catalog.json',catalog);return file
 def resolver(self,cfg=None):
  self.s=Schema(self.p);return Resolver(self.s,cfg or {}),self.s.context('NOVEL-RULE')
 def add_reference(self,reference='UR B2 Rev.1'):
  f=self.root/'data/requirements/source.txt';f.write_text(base.SOURCE+' Refer to '+reference+'.');rows=json.loads((self.root/'data/requirements/requirements.json').read_text());rows['NOVEL-RULE']['text']=f.read_text();self.write('data/requirements/requirements.json',rows)
 def test_cross_document_and_edition_detection(self):
  rs=references('Apply UR B2 Rev.1 and UR C3.2.1 and (PR) No. 29.');self.assertEqual(rs[0]['revision'],1);self.assertEqual(rs[1]['section'],'C3.2.1');self.assertEqual(rs[2]['document_id'],'PR 29')
 def test_available_source_with_explicit_edition(self):
  self.document();r,c=self.resolver();new,e=r.resolve(c,[req('UR B2',1)],'NOVEL-RULE');self.assertTrue(e['novel']);self.assertEqual(e['entries'][0]['status'],'RETRIEVED');self.assertEqual(e['entries'][0]['edition'],'Rev.1');self.assertTrue(new['source_documents'][-1]['selection']['sha256'])
 def test_unversioned_source_qualified_not_assumed_compatible(self):
  self.document();r,c=self.resolver();new,e=r.resolve(c,[req('UR B2')],'NOVEL-RULE');self.assertEqual(e['entries'][0]['status'],'RETRIEVED_EDITION_UNSPECIFIED');self.assertTrue(new['unresolvedSourceContext'])
 def test_missing_source_is_explicit(self):
  r,c=self.resolver();new,e=r.resolve(c,[req('UR Z9')],'NOVEL-RULE');self.assertEqual(e['entries'][0]['status'],'MISSING_DOCUMENT');self.assertFalse(e['novel'])
 def test_ambiguous_editions_not_silently_latest(self):
  self.document(name='old');self.document(revision=2,name='new');r,c=self.resolver();new,e=r.resolve(c,[req('UR B2')],'NOVEL-RULE');self.assertEqual(e['entries'][0]['status'],'AMBIGUOUS_DOCUMENT');self.assertEqual(len(new['source_documents']),len(c['source_documents']))
 def test_explicit_incompatible_edition(self):
  self.document();r,c=self.resolver();_,e=r.resolve(c,[req('UR B2',9)],'NOVEL-RULE');self.assertEqual(e['entries'][0]['status'],'INCOMPATIBLE_EDITION')
 def test_cyclic_references_bounded(self):
  self.document(text='B2.1 Application\nB2.1.1 Use UR C3 Rev.1.\n');self.document(code='UR C3',text='C3.1 Application\nC3.1.1 Use UR B2 Rev.1.\n');r,c=self.resolver();_,e=r.resolve(c,[req('UR B2',1)],'NOVEL-RULE');self.assertTrue(any(x['status']=='CYCLE_SKIPPED' for x in e['entries']));self.assertEqual(len(r.cache),2)
 def test_provenance_hash_mismatch_rejected(self):
  f=self.document();(self.root/f).write_text('changed');r,c=self.resolver();_,e=r.resolve(c,[req('UR B2',1)],'NOVEL-RULE');self.assertEqual(e['entries'][0]['status'],'SOURCE_HASH_MISMATCH');self.assertFalse(e['novel'])
 def test_missing_provenance_not_authoritative(self):
  self.document();cat=json.loads((self.root/'data/requirements/source_catalog.json').read_text());cat['sources']['UR B2'].pop('provenance');self.write('data/requirements/source_catalog.json',cat);r,c=self.resolver();_,e=r.resolve(c,[req('UR B2',1)],'NOVEL-RULE');self.assertEqual(e['entries'][0]['status'],'PROVENANCE_UNVERIFIED')
 def test_incompatible_authority_dependency(self):
  self.document(text='B2.1 Application\nB2.1.1 Use UR C3 Rev.1.\n');self.document(code='UR C3',authority='OtherAuthority',text='C3.1 Application\nC3.1.1 Other.\n');r,c=self.resolver();_,e=r.resolve(c,[req('UR B2',1)],'NOVEL-RULE');self.assertTrue(any(x['status']=='INCOMPATIBLE_AUTHORITY' for x in e['entries']))
 def test_missing_section_does_not_fall_back_to_whole_source(self):
  self.document();r,c=self.resolver();_,e=r.resolve(c,[req('UR B2',1,'B2.999')],'NOVEL-RULE');self.assertEqual(e['entries'][0]['status'],'MISSING_SECTION');self.assertFalse(e['novel'])
 def test_passage_budget_never_blindly_truncates(self):
  self.document();r,c=self.resolver({'context_resolution':{'max_characters_per_round':10}});new,e=r.resolve(c,[req('UR B2',1)],'NOVEL-RULE');self.assertEqual(e['entries'][0]['status'],'PASSAGE_LIMIT_EXHAUSTED');self.assertFalse(e['novel']);self.assertEqual(len(new['source_documents']),len(c['source_documents']))
 def test_repeated_request_stops_without_repeat_read(self):
  self.document();r,c=self.resolver();new,_=r.resolve(c,[req('UR B2',1)],'NOVEL-RULE');again,e=r.resolve(new,[req('UR B2',1)],'NOVEL-RULE');self.assertEqual(e['status'],'REPEATED_EVIDENCE_REQUEST');self.assertEqual(len(r.cache),1)
 def test_round_limit_is_separate_from_candidate_budget(self):
  self.document();r,c=self.resolver({'context_resolution':{'max_rounds':0}});_,e=r.resolve(c,[req('UR B2',1)],'NOVEL-RULE');self.assertEqual(e['status'],'CONTEXT_LIMIT_EXHAUSTED')
 def test_source_only_path_isolation(self):
  r,c=self.resolver();_,e=r.resolve(c,[req('evaluation/labels.json')],'NOVEL-RULE');self.assertEqual(e['entries'][0]['status'],'MISSING_DOCUMENT');self.assertNotIn('FORBIDDEN_EVALUATION',json.dumps(e))
 def test_schema_evidence_does_not_create_binding(self):
  f=self.root/'schema/Schema_for_NLTL.ttl';f.write_text(f.read_text()+'\n@prefix rdfs:<http://www.w3.org/2000/01/rdf-schema#>. n:exampleApplicability a <http://www.w3.org/2002/07/owl#DatatypeProperty>;rdfs:label "Example applicability";rdfs:domain n:ship.');self.write('schema/representation_bindings.json',{'requirements':{'NOVEL-RULE':{'terms':['bridgeWingsEnclosed']}}});r,c=self.resolver();new,e=r.resolve(c,[dict(kind='schema',query='Example applicability',reason='Evidence only')],'NOVEL-RULE');self.assertIn(str(N.exampleApplicability),[x['iri'] for x in new['schema_terms']]);self.assertEqual(new['termOwners'],{});self.assertEqual(new['contract'],c['contract']);self.assertIn('not evidence of legal eligibility',e['entries'][0]['meaning'])
 def test_request_evidence_protocol_valid_without_regulatory_claim(self):
  self.s=Schema(self.p);c=Candidate(1,base.GOOD,'');fake={'user':json.dumps(dict(context=self.s.context('NOVEL-RULE'),full_candidate=c.code,previous_candidate=None,change_manifest={'changes':[]},prior_issues=[]))};o=json.loads(evidence_request(fake,[dict(kind='source',reference='UR B2',section=None,revision=1,query='Application',reason='Need scope')]));obj,fs=parse_review({'text':json.dumps(o)},c,self.s.context('NOVEL-RULE'));self.assertEqual(obj['decision'],'REQUEST_EVIDENCE');self.assertFalse(fs)
 def test_empty_evidence_request_rejected(self):
  c=Candidate(1,base.GOOD,'');obj=base.bind_review_response({'user':json.dumps(dict(context=self.s.context('NOVEL-RULE'),full_candidate=c.code,previous_candidate=None,change_manifest={'changes':[]},prior_issues=[]))},dict(decision='REQUEST_EVIDENCE',issues=[],change_assessments=[],reconciliations=[],unchecked=[],evidence_requests=[]))
  with self.assertRaisesRegex(ReviewerFormatError,'EMPTY_EVIDENCE_REQUEST'):parse_review({'text':json.dumps(obj)},c,self.s.context('NOVEL-RULE'))
 def repair_review(self,request):
  data=base.request_data(request);ctx=data['context'];source=next(x['text'] for x in ctx['source_documents'] if 'software scope applies' in x['text']);o=json.loads(base.review_response(request));o.update(decision='REJECT',issues=[dict(issue_id='deactivated-control',category='SOURCE_BACKED_LOGIC_ERROR',source_clause=ctx['requirement']['clause'],source_excerpt=source,candidate_excerpt='sh:deactivated true',reason='The software source and explicit current contract establish the scope; the submitted deactivation disables it.',expected='Active enforcement in declared scope',suggestion='Remove only the supported deactivation; preserve all unrelated logic.',evidence_excerpt=json.dumps(ctx['contract'],sort_keys=True,ensure_ascii=False))],context_assessments=[dict(finding_key=f['finding_key'],disposition='REPAIRABLE_CODE',source_excerpt=source,candidate_excerpt='sh:deactivated true',evidence_excerpt=json.dumps(ctx['contract'],sort_keys=True,ensure_ascii=False),reason='Explicit source/contract for this software scope; no inferred eligibility.') for f in data['acceptance_blockers']]);return json.dumps(base.bind_review_response(request,o))
 def configured_scope(self):
  self.document();self.add_reference();self.write('schema/representation_bindings.json',{'requirements':{'NOVEL-RULE':dict(terms=['bridgeWingsEnclosed'],owners={'bridgeWingsEnclosed':'ship'},target_owner='ship')}})
 def test_resolvable_gap_proceeds_review_repair_full_latest(self):
  self.configured_scope()
  def handler(req,i):
   if req['route']=='generation':return base.wrap(INACTIVE)
   if req['route'].endswith('repair'):
    self.assertEqual(req['payload']['previous_candidate'],INACTIVE);self.assertEqual(req['payload']['candidate_sha256'],digest(INACTIVE));self.assertTrue(base.request_data(req)['context']['retrieval_evidence']);return base.wrap(base.GOOD)
   return self.repair_review(req) if base.request_data(req)['candidate_version']==1 else base.review_response(req)
  r,t,out=self.run_local(handler);self.assertEqual(r['accepted_version'],2,json.dumps(r));self.assertEqual(r['repair_calls'],1);states=[x['state'] for x in json.loads((out/'controller_transitions.json').read_text())];self.assertTrue((out/'retrieved_input_hashes.json').is_file());self.assertIn('RETRIEVE_CONTEXT',states);self.assertIn('REPAIR_PROPOSED',states);self.assertEqual(states[-1],'ACCEPTED')
  if __import__('os').environ.get('NLTL_TEST_OUTPUT'):
   __import__('shutil').copytree(out,pathlib.Path(__import__('os').environ['NLTL_TEST_OUTPUT'])/'resolvable_context_control')
 def test_missing_gap_retained_no_automatic_activation(self):
  self.add_reference('UR Z9')
  def handler(req,i):
   if req['route']=='generation':return base.wrap(INACTIVE)
   self.assertFalse(req['route'].endswith('repair'));return base.review_response(req,'UNRESOLVED',context_issue(req))
  r,t,out=self.run_local(handler);self.assertIsNone(r['accepted_version']);self.assertEqual(r['candidate_attempts'],1);self.assertEqual(r['repair_calls'],0);self.assertEqual((out/'candidate_01.ttl').read_text(),INACTIVE)
 def test_reviewer_accept_cannot_erase_deactivation(self):
  r,t,_=self.run_local(lambda req,i:base.wrap(INACTIVE) if req['route']=='generation' else base.review_response(req));self.assertEqual(r['status'],'UNRESOLVED_CONTEXT');self.assertIsNone(r['accepted_version'])
 def test_repeated_request_no_endless_review_loop(self):
  def handler(req,i):return base.wrap(base.GOOD) if req['route']=='generation' else evidence_request(req,[dict(kind='source',reference='UR Z9',query='Application',reason='Needed',section=None,revision=None)])
  r,t,_=self.run_local(handler);self.assertEqual(len(t.calls),2);self.assertIsNone(r['accepted_version']);self.assertEqual(r['repair_calls'],0)
 def test_retrieved_evidence_tampering_stops_dispatch(self):
  self.configured_scope();f=self.root/'data/requirements/UR_B2.txt'
  def handler(req,i):
   if req['route']=='generation':return base.wrap(INACTIVE)
   if req['route']=='review':response=self.repair_review(req);f.write_text('changed after retrieval');return response
   self.fail('No repair may dispatch after source changes')
  r,t,_=self.run_local(handler);self.assertEqual(r['status'],'REQUEST_INTEGRITY_FAILURE');self.assertEqual(len(t.calls),2)
 def test_review_budget_explicit(self):
  self.document();cfg=self.p.config('configs/nltl.json');cfg['context_resolution']={'max_reviews_per_candidate':1}
  def handler(req,i):return base.wrap(base.GOOD) if req['route']=='generation' else evidence_request(req,[dict(kind='source',reference='UR B2',revision=1,section=None,query='Application',reason='Scope')])
  r,t,_=self.run_local(handler,cfg=cfg);self.assertEqual(r['status'],'CONTEXT_LIMIT_EXHAUSTED');self.assertEqual(len(t.calls),2)
 def test_late_schema_or_source_request_runs_review_again_same_code(self):
  self.document()
  def handler(req,i):
   if req['route']=='generation':return base.wrap(base.GOOD)
   self.assertEqual(base.request_data(req)['full_candidate'],base.GOOD)
   return evidence_request(req,[dict(kind='source',reference='UR B2',revision=1,section=None,query='Application',reason='Scope')]) if i==2 else base.review_response(req)
  r,t,out=self.run_local(handler);self.assertEqual(r['accepted_version'],1);self.assertEqual(len(t.calls),3);self.assertEqual(r['repair_calls'],0)
 def test_no_evaluation_or_witness_in_context_resolution(self):
  self.document();self.add_reference()
  def handler(req,i):
   self.assertNotIn('FORBIDDEN_EVALUATION_GOLD',json.dumps(req));self.assertNotIn('FORBIDDEN_WITNESS_GOLD',json.dumps(req));return base.wrap(INACTIVE) if req['route']=='generation' else base.review_response(req,'UNRESOLVED',context_issue(req))
  enabled=[True]
  def audit(event,args):
   if enabled[0] and event=='open' and args and isinstance(args[0],(str,bytes)):
    p=pathlib.Path(__import__('os').fsdecode(args[0])).resolve()
    if any(p.is_relative_to(self.root/x) for x in ['evaluation','tests','data/contracts']):raise PermissionError('FORBIDDEN_EVALUATION_WITNESS_READ')
  __import__('sys').addaudithook(audit)
  try:r,t,_=self.run_local(handler)
  finally:enabled[0]=False
  self.assertIsNone(r['accepted_version']);self.assertFalse(r['behavioral_gold_consulted'])
 def test_invalid_context_limit_rejected(self):
  cfg=self.p.config('configs/nltl.json');cfg['context_resolution']={'max_rounds':-1};self.write('configs/invalid.json',cfg)
  with self.assertRaisesRegex(ValueError,'INVALID_CONTEXT_RESOLUTION_LIMIT'):self.p.config('configs/invalid.json')

 def test_followup_after_unversioned_dependency_handles_pending_reference(self):
  self.document();r,c=self.resolver();new,_=r.resolve(c,[req('UR B2')],'NOVEL-RULE');new,event=r.resolve(new,[dict(kind='schema',query='Application binding',reason='Follow up')],'NOVEL-RULE');self.assertIn(event['status'],['EVIDENCE_ADDED','NO_NEW_EVIDENCE'])

 def test_bare_cross_document_clause_detected_but_headings_not_dependencies(self):
  rs=references('B2.1 Application\nUse the provision in C3.2.1 and UR D4 Rev.2.\n');self.assertEqual({x['document_id'] for x in rs},{'UR C3','UR D4'});self.assertEqual(next(x['section'] for x in rs if x['document_id']=='UR C3'),'C3.2.1')
 def test_request_limit_leaves_deferred_evidence_explicit(self):
  self.document();r,c=self.resolver({'context_resolution':{'max_requests_per_round':1}});_,e=r.resolve(c,[req('UR B2',1),req('UR Z9')],'NOVEL-RULE');self.assertTrue(any(x['status']=='REQUEST_LIMIT_DEFERRED' for x in e['entries']))

 def test_internal_reference_in_retrieved_document_is_followed_not_false_cycle(self):
  self.document(text='B2.1 Application\nB2.1.1 Refer to section B2.2.1.\nB2.2 Supporting\nB2.2.1 Required internal evidence.\n');r,c=self.resolver();new,e=r.resolve(c,[req('UR B2',1,'B2.1')],'NOVEL-RULE');self.assertIn('Required internal evidence',''.join(x['text'] for x in new['source_documents']));self.assertFalse(any(x['status']=='MISSING_SECTION_REFERENCE' for x in e['entries']))

 def test_declared_source_gap_retrieved_before_review_and_not_silently_accepted(self):
  self.add_reference('UR Z9')
  def handler(req,i):
   if req['route']=='generation':return base.wrap(base.GOOD)
   data=base.request_data(req);data=data.get('original_request',data);self.assertTrue(data['context']['retrieval_gaps']);return base.review_response(req)
  r,t,_=self.run_local(handler);self.assertIsNone(r['accepted_version']);self.assertEqual(r['status'],'REVIEWER_FORMAT_FAILURE')

 def test_cyclic_retrieval_metadata_roundtrips_full_repair_payload(self):
  from nltlv2.core import finding
  from nltlv2.requests import repair_request,assert_integrity
  self.document(text='B2.1 Application\nB2.1.1 Refer to UR C3 Rev.1.\n');self.document(code='UR C3',text='C3.1 Application\nC3.1.1 Refer to UR B2 Rev.1.\n');r,ctx=self.resolver();ctx,_=r.resolve(ctx,[req('UR B2',1)],'NOVEL-RULE');candidate=Candidate(1,base.GOOD,'');f=finding(candidate,'ACTIVATION_ERROR','Software packet check',suggestion='Preserve current code');packet=repair_request(GenerationProject(self.root),ctx,candidate,[f]);self.assertTrue(assert_integrity(packet,candidate,[f])['previous_code_full'])

 def test_reference_lookup_cap_is_explicit(self):
  self.document();r,c=self.resolver({'context_resolution':{'max_reference_lookups':0}});_,e=r.resolve(c,[req('UR B2',1)],'NOVEL-RULE');self.assertEqual(e['entries'][0]['status'],'REFERENCE_LIMIT_EXHAUSTED');self.assertFalse(e['novel'])
