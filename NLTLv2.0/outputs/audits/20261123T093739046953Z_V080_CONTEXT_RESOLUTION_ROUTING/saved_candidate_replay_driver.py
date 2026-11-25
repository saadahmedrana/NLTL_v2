"""Labelled software replay only. No generation, evaluation fixtures or prior diagnostic solution."""
from pathlib import Path
import json,hashlib,sys,os
from nltlv2.core import Project,Candidate,write,offline_network_guard
from nltlv2.runner import Runner
from nltlv2.checks import check
from nltlv2.tracking import Tracker
from nltlv2.requests import repair_request,assert_integrity
S=json.loads(Path('/private/tmp/v080_state.json').read_text());W=Path(S['work']);A=Path(S['audit']);R=Path(S['root']);H=R/'outputs/experiments/20261123T090918547479Z_V070_I2_004_SOURCE_GROUNDED_OPERATIONAL_CHECK/I2-004/nltl/candidate_01.ttl'
code=H.read_text();assert hashlib.sha256(code.encode()).hexdigest()=='26f4d0bfbbc3d9ad5bc08df3be0ec3db8aee241f2b1a80728b0bd2fac650972a';out=A/'saved_v070_diagnostic';out.mkdir(exist_ok=False);(out/'candidate_01.ttl').write_bytes(H.read_bytes());enabled=[True]
def audit(event,args):
 if enabled[0] and event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
  p=Path(os.fsdecode(args[0])).resolve()
  if p.is_relative_to(R/'evaluation') or p.is_relative_to(R/'outputs') or p.is_relative_to(W/'evaluation') or p.is_relative_to(W/'tests') or p.is_relative_to(W/'data/contracts'):raise PermissionError('REPLAY_EXTERNAL_EVALUATION_HISTORY_DENIED')
sys.addaudithook(audit)
class ScriptedReviewer:
 is_live=False
 def __init__(self):self.calls=[]
 def dispatch(self,request,latest=None,expected_findings=None):
  assert request['route']=='review','No generation, repair or retry in unresolved saved-candidate replay';self.calls.append(request);body=json.loads(request['user']);context=body['context'];assert body['full_candidate']==code;assert 'query_branch_diagnostics' not in request['user'];assert 'FORBIDDEN_EVALUATION' not in request['user']
  source=next(x['text'] for x in context['source_documents'] if x.get('retrieved_reference')=='UR I1')
  issue=dict(issue_id='unresolved-source-binding',category='UNRESOLVED_CONTEXT',source_clause=context['requirement']['clause'],source_excerpt=source,candidate_excerpt='sh:deactivated true',reason='The retrieved source and vocabulary do not establish an approved applicability representation or which cited edition governs this scope. No target is inferred.',expected='Explicit source/representation decision before active enforcement',suggestion='Retain unresolved context; clarify edition and the applicability binding. Review all query logic independently against source.',evidence_excerpt=json.dumps(context['contract']))
  obj=dict(decision='UNRESOLVED',issues=[issue],change_assessments=[],reconciliations=[dict(issue_id=x['issue_id'],state='PERSISTENT',source_excerpt=source,candidate_excerpt=code,reason='Additional evidence does not settle the binding/edition; no code change or correctness is inferred.') for x in body['prior_issues']],unchecked=[dict(scope='Applicability representation and governing cross-document edition',material=True,reason='Vocabulary existence and a retained source edition alone are insufficient')],evidence_requests=[],context_assessments=[])
  return dict(text=json.dumps(obj),status='completed',finish_reason='stop',usage={},elapsed_seconds=0,software_script=True)
try:
 with offline_network_guard():
  p=Project(W);cfg=p.config('configs/v080_bounded_live_check.json');transport=ScriptedReviewer();runner=Runner(p,cfg,transport,out);context=runner.schema.context('I2-004');write(out/'initial_context.json',context);write(out/'source_selection_manifest.json',runner.schema.source_manifests['I2-004']);candidate=Candidate(1,code,'');fs=check(candidate,runner.schema,'I2-004');initial=dict(status='INITIAL_CANDIDATE',changes=[])
  context,findings,review,error,conflicts,status=runner.assess_candidate(candidate,context,None,initial,Tracker(),fs,'I2-004')
  assert code==(out/'candidate_01.ttl').read_text();assert status!='ACCEPTED';assert not error and not conflicts;assert 1<=len(transport.calls)<=3
  write(out/'finding_results.json',[f.asdict() for f in findings]);write(out/'final_review.json',review);write(out/'outcome.json',dict(label='SAVED_V070_CONTEXT_ROUTING_SOFTWARE_DIAGNOSTIC',status=status,source_seed_sha256=candidate.sha256,provider_calls=0,generation_calls=0,repair_calls=0,scripted_review_requests=len(transport.calls),no_shape_edits=True,historical_credit=False,external_data_denied=True,query_diagnostic_solution_supplied=False))
  # A fully rendered, integrity-checked proposed feedback packet; never dispatched.
  packet=repair_request(runner.p,context,candidate,findings);assert_integrity(packet,candidate,findings);write(out/'proposed_feedback_NOT_DISPATCHED.json',packet);(out/'proposed_feedback_NOT_DISPATCHED.rendered.txt').write_text(packet['system']+'\n\n--- USER ---\n'+packet['user'])
finally:enabled[0]=False
print(json.dumps(dict(status=status,states=[x['state'] for x in runner.controller_transitions],scripted_reviews=len(transport.calls),source_file_reads=len(runner.resolver.cache),retrieved_characters=runner.resolver.total_characters,provider_calls=0),indent=2))
