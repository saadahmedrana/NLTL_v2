"""Generic scripted routing controls, never regulatory correctness or live-model evidence."""
import copy,json,unittest,pathlib,os
import test_general_pipeline as base
from nltlv2.core import Candidate,digest
from nltlv2.schema import Schema,N
from nltlv2.requests import review_conflicts,review_proposal_routing,review_base,parse_review,ReviewerFormatError
from nltlv2.review_validation import validate_review

class ReviewerRoutingControls(unittest.TestCase):
 tearDown=base.GeneralPipelineTests.tearDown;write=base.GeneralPipelineTests.write;run_local=base.GeneralPipelineTests.run_local;accepting=base.GeneralPipelineTests.accepting
 def setUp(self):
  base.GeneralPipelineTests.setUp(self)
  self.write('schema/representation_bindings.json',{'requirements':{'NOVEL-RULE':{'terms':['bridgeWingsEnclosed','componentValue'],'owners':{'bridgeWingsEnclosed':'ship','componentValue':'component'},'model_paths':[dict(fromOwner='ship',via='hasComponent',toOwner='component')],'target_owner':'ship'}}});self.s=Schema(self.p)
 def paired(self):return dict(property=str(N.bridgeWingsEnclosed),proposed_path=[str(N.hasComponent),str(N.componentValue)],proposed_path_role='PROPERTY')
 def route(self,issue,context=None):return review_proposal_routing({'issues':[dict(issue_id='generic-issue',category='SOURCE_BACKED_LOGIC_ERROR',**issue)]},self.s,'NOVEL-RULE',context or self.s.context('NOVEL-RULE'))
 def proposal(self,request,**extra):
  issue=base.issue_for(request);issue.update(self.paired());issue.update(extra);return issue
 def reject(self,r,**extra):return base.review_response(r,'REJECT',self.proposal(r,**extra))
 def test_mismatch_detected_without_mutating_validator_or_issue(self):
  issue=dict(issue_id='generic-issue',category='SOURCE_BACKED_LOGIC_ERROR',**self.paired());original=copy.deepcopy(issue);before=review_conflicts({'issues':[issue]},self.s,'NOVEL-RULE');routing=review_proposal_routing({'issues':[issue]},self.s,'NOVEL-RULE',self.s.context('NOVEL-RULE'))
  self.assertEqual(issue,original);self.assertEqual(before,review_conflicts({'issues':[issue]},self.s,'NOVEL-RULE'));self.assertEqual(routing['route'],'CORRECT_RESPONSE');self.assertEqual(routing['correctable'][0]['code'],'INCONSISTENT_REVIEWER_PROPERTY_PATH_PAIRING');self.assertEqual(routing['correctable'][0]['matching_declared_properties'],[str(N.componentValue)])
 def test_unknown_path_stays_blocking(self):
  route=self.route(dict(property=str(N.bridgeWingsEnclosed),proposed_path=['urn:unknown-path'],proposed_path_role='PROPERTY'));self.assertEqual(route['route'],'CONFLICT');self.assertFalse(route['correctable'])
 def test_unknown_property_is_not_silently_relabelled(self):
  route=self.route(dict(self.paired(),property='urn:unknown-property'));self.assertEqual(route['route'],'CONFLICT');self.assertEqual(route['blocking'][0]['code'],'UNRESOLVED_PROPOSAL_MAPPING')
 def test_genuine_representation_contradiction_stays_blocking(self):
  for fields in [dict(self.paired(),representation_disposition='UNRESOLVED_CONTRADICTION'),dict(self.paired(),proposed_datatype='http://www.w3.org/2001/XMLSchema#decimal')]:
   route=self.route(fields);self.assertEqual(route['route'],'CONFLICT')
 def test_unresolved_context_is_not_reclassified_as_format(self):
  issue=dict(issue_id='uncertain',category='UNRESOLVED_CONTEXT',**self.paired());route=review_proposal_routing({'issues':[issue]},self.s,'NOVEL-RULE',self.s.context('NOVEL-RULE'));self.assertEqual(route['route'],'CONFLICT');self.assertFalse(route['correctable'])
 def test_missing_supplied_mapping_cannot_grant_correction(self):
  ctx=self.s.context('NOVEL-RULE');ctx['contract']['owners']={};self.assertEqual(self.route(self.paired(),ctx)['route'],'CONFLICT')
 def operands(self):return [dict(operand_id='record',property=str(N.bridgeWingsEnclosed),proposed_path=[str(N.bridgeWingsEnclosed)],proposed_path_role='PROPERTY'),dict(operand_id='component',property=str(N.componentValue),proposed_path=[str(N.hasComponent),str(N.componentValue)],proposed_path_role='PROPERTY')]
 def test_valid_multi_operand_finding_each_pair_checked(self):
  route=self.route(dict(operands=self.operands()));self.assertEqual(route['route'],'VALID')
  operands=self.operands();operands[1]['proposed_path']=['urn:unknown'];self.assertEqual(self.route(dict(operands=operands))['route'],'CONFLICT')
 def test_valid_operands_do_not_hide_invalid_legacy_scalar_pair(self):
  self.assertEqual(self.route(dict(self.paired(),operands=self.operands()))['route'],'CORRECT_RESPONSE')
 def test_invalid_operands_are_rejected_before_proposal_routing(self):
  context=self.s.context('NOVEL-RULE');c=Candidate(1,base.BAD_EXTRA,'');r={'user':json.dumps(dict(context=context,full_candidate=c.code,candidate_version=1,previous_candidate=None,change_manifest={'changes':[]},prior_issues=[]))};issue=base.issue_for(r);issue['operands']=self.operands();issue['operands'][1]['operand_id']='record';obj=json.loads(base.review_response(r,'REJECT',issue));errors=validate_review({'text':json.dumps(obj)},c,context)[2];self.assertTrue(any(e['code']=='DUPLICATE_OPERAND_ID' for e in errors))
 def test_shared_correction_budget_then_valid_repair(self):
  initial=[];valid_response=[]
  def handler(r,i):
   if r['route']=='generation':return base.wrap(base.BAD_EXTRA)
   if r['route'].endswith('repair'):
    self.assertEqual(r['payload']['previous_candidate'],base.BAD_EXTRA);self.assertTrue(valid_response);support=r['payload']['current_findings'][-1]['evidence'];self.assertEqual(support['reviewer_proposal']['operands'],self.operands());return base.wrap(base.GOOD)
   packet=json.loads(r['user'])
   if packet['candidate_version']==2:return base.review_response(r)
   if r['route']=='review':initial.append(copy.deepcopy(packet));return self.reject(r)
   self.assertEqual(review_base(packet),initial[0]);self.assertEqual(packet['prior_issues'],[]);feedback=packet['format_feedback'];self.assertEqual(feedback['correction_kind'],'PROPOSAL');self.assertTrue(feedback['shared_response_correction_allowance']);self.assertEqual(feedback['validation_errors'][0]['observed'],self.paired());self.assertEqual(feedback['validation_errors'][0]['path'],'$.issues[0].proposed_path')
   issue=base.issue_for(r);issue['operands']=self.operands();response=base.review_response(r,'REJECT',issue);valid_response.append(response);return response
  cfg=self.p.config('configs/nltl.json');cfg['continuation']={'max_provider_calls':5};result,t,out=self.run_local(handler,cfg=cfg);self.assertEqual(result['accepted_version'],2,result);self.assertEqual(result['auxiliary_format_retries'],1);self.assertEqual(result['repair_calls'],1);self.assertEqual(len(t.calls),5);self.assertEqual(result['history'][0]['findings'][-1]['diagnostic'],valid_response[0]);self.assertEqual(result['history'][0]['review']['issues'][0]['operands'],self.operands())
  if os.environ.get('NLTL_TEST_OUTPUT'):
   import shutil;shutil.copytree(out,pathlib.Path(os.environ['NLTL_TEST_OUTPUT'])/'SCRIPTED_valid_response_correction_and_repair')
 def test_exhausted_pairing_correction_never_authorizes_repair(self):
  def handler(r,i):return base.wrap(base.BAD_EXTRA) if r['route']=='generation' else self.reject(r)
  result,t,out=self.run_local(handler);self.assertEqual(result['status'],'REVIEWER_PROPOSAL_CORRECTION_EXHAUSTED');self.assertEqual(result['repair_calls'],0);self.assertEqual(result['auxiliary_format_retries'],1);self.assertIsNone(result['history'][0]['review']);self.assertFalse(any(f['assessment']=='MODEL_INTERPRETATION' for f in result['history'][0]['findings']))
 def test_format_and_proposal_corrections_share_one_allowance(self):
  def handler(r,i):return base.wrap(base.BAD_EXTRA) if r['route']=='generation' else '{invalid' if r['route']=='review' else self.reject(r)
  result,t,_=self.run_local(handler);self.assertEqual(result['status'],'REVIEWER_PROPOSAL_CORRECTION_EXHAUSTED');self.assertEqual(len(t.calls),3);self.assertEqual(result['repair_calls'],0)
 def test_zero_allowance_stops_explicitly(self):
  cfg=self.p.config('configs/nltl.json');cfg['review_format_retries']=0
  result,t,_=self.run_local(lambda r,i:base.wrap(base.BAD_EXTRA) if r['route']=='generation' else self.reject(r),cfg=cfg);self.assertEqual(result['status'],'REVIEWER_PROPOSAL_CORRECTION_EXHAUSTED');self.assertEqual(len(t.calls),2)
 def test_unknown_path_and_contradiction_do_not_consume_correction(self):
  for fields in [dict(proposed_path=['urn:unknown-path']),dict(representation_disposition='UNRESOLVED_CONTRADICTION')]:
   result,t,_=self.run_local(lambda r,i:base.wrap(base.BAD_EXTRA) if r['route']=='generation' else self.reject(r,**fields));self.assertEqual(result['status'],'CONFLICT');self.assertEqual(result['auxiliary_format_retries'],0);self.assertEqual(result['repair_calls'],0);self.assertIsNone(result['history'][0]['review'])
 def test_stale_candidate_or_code_location_is_terminal(self):
  for target in ['root','location']:
   def handler(r,i):
    if r['route']=='generation':return base.wrap(base.BAD_EXTRA)
    obj=json.loads(self.reject(r))
    if target=='root':obj['candidate_sha256']='0'*64
    else:obj['issues'][0]['candidate_location']['candidate_sha256']='0'*64
    return json.dumps(obj)
   result,t,_=self.run_local(handler);self.assertEqual(result['status'],'REQUEST_INTEGRITY_FAILURE');self.assertEqual(len(t.calls),2);self.assertEqual(result['repair_calls'],0);self.assertIsNone(result['history'][0]['review'])
 def test_infrastructure_failure_never_enters_response_correction(self):
  def handler(r,i):
   if r['route']=='generation':return base.wrap(base.GOOD)
   raise TimeoutError('Synthetic infrastructure timeout')
  result,t,_=self.run_local(handler);self.assertEqual(result['status'],'RESOURCE_ATTRIBUTION_UNCERTAIN');self.assertEqual(result['auxiliary_format_retries'],0);self.assertEqual(len(t.calls),2)
 def test_overall_call_cap_blocks_correction_without_dispatch(self):
  cfg=self.p.config('configs/nltl.json');cfg['continuation']={'max_provider_calls':2}
  result,t,_=self.run_local(lambda r,i:base.wrap(base.BAD_EXTRA) if r['route']=='generation' else self.reject(r),cfg=cfg);self.assertEqual(result['status'],'PROVIDER_CALL_LIMIT_EXHAUSTED');self.assertEqual(len(t.calls),2);self.assertEqual(result['repair_calls'],0)
 def test_nonempty_original_prior_state_survives_proposal_correction(self):
  seen=[]
  def handler(r,i):
   if r['route']=='generation':return base.wrap(base.BAD_EXTRA)
   if r['route'].endswith('repair'):return base.wrap(base.GOOD)
   wire=json.loads(r['user'])
   if wire['candidate_version']==1:return base.review_response(r,'REJECT',base.issue_for(r))
   if r['route']=='review':seen.append(copy.deepcopy(wire));self.assertTrue(wire['prior_issues']);return self.reject(r)
   self.assertEqual(review_base(wire),seen[0]);self.assertEqual(wire['prior_issues'],seen[0]['prior_issues']);self.assertEqual(wire['prior_issues'][0]['last_seen_version'],1);return base.review_response(r)
  result,t,_=self.run_local(handler);self.assertEqual(result['accepted_version'],2,result);self.assertEqual(result['auxiliary_format_retries'],1);self.assertEqual(result['repair_calls'],1)
 def test_multi_operand_numeric_role_uses_unchanged_quantity_validator(self):
  bindings=self.s.bindings['NOVEL-RULE'];bindings['owners']['probeLength']='ship';self.write('schema/representation_bindings.json',{'requirements':{'NOVEL-RULE':bindings}});self.s=Schema(self.p)
  operands=[self.operands()[0],dict(operand_id='length',property=str(N.probeLength),proposed_path=[str(N.probeLength),self.s.quantity_profile['numeric_predicate']],proposed_path_role='NUMERIC_OPERAND',proposed_unit='http://qudt.org/vocab/unit/M')]
  self.assertEqual(self.route(dict(operands=operands))['route'],'VALID');operands[1]['proposed_unit']='http://qudt.org/vocab/unit/MilliM';self.assertEqual(self.route(dict(operands=operands))['route'],'CONFLICT')
 def test_mixed_conflict_prevents_correctable_pair_from_hiding_contradiction(self):
  issues=[dict(issue_id='pairing',category='SOURCE_BACKED_LOGIC_ERROR',**self.paired()),dict(issue_id='contradiction',category='UNRESOLVED_CONTEXT',representation_disposition='UNRESOLVED_CONTRADICTION')]
  routing=review_proposal_routing({'issues':issues},self.s,'NOVEL-RULE',self.s.context('NOVEL-RULE'));self.assertEqual(routing['route'],'CONFLICT');self.assertTrue(routing['correctable']);self.assertTrue(routing['blocking'])
