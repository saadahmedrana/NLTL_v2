"""Offline-only routing audit and undispatched preparation, never a live executor."""
from pathlib import Path
import argparse,ast,copy,hashlib,io,json,os,shutil,sys,unittest
from nltlv2.core import Project,Candidate,offline_network_guard,write
from nltlv2.runner import Runner
from nltlv2.schema import Schema
from nltlv2.admission import load_admission
from nltlv2.tracking import Tracker
from nltlv2.checks import check,runtime_probe
from nltlv2.evidence import probe_summary
from nltlv2.requests import review_conflicts,review_proposal_routing,review_base

SAVED='outputs/experiments/20261124T095744944101Z_V0100_I2_004_DEVELOPMENT_CONTINUATION'
SEED='d8986fa2c5186ae5d619696650e5f56328480bc5c3430465c4fdbc1ef9d94f9a'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text())
def function_source(path,name):
 text=path.read_text();node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name);return ast.get_source_segment(text,node)
class CaptureBoundary(Exception):pass
class NoDispatch:
 is_live=False
 def dispatch(self,request,*args):self.packet=copy.deepcopy(request);raise CaptureBoundary('PREPARED_UNDISPATCHED: no provider transport')
class UnchangedSavedResponse:
 is_live=False
 def __init__(self,response):self.response=response;self.requests=[]
 def dispatch(self,request,*args):
  self.requests.append(copy.deepcopy(request));assert len(self.requests)<=2
  if len(self.requests)==2:assert review_base(json.loads(request['user']))==json.loads(self.requests[0]['user'])
  return copy.deepcopy(self.response)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--project',required=True);parser.add_argument('--history-root');parser.add_argument('--output',required=True);args=parser.parse_args();root=Path(args.project).resolve();history=Path(args.history_root).resolve() if args.history_root else root;out=root/args.output;out.mkdir(parents=True,exist_ok=False)
 with offline_network_guard():
  sys.path.insert(0,str(root/'tests'));os.environ['NLTL_TEST_PROJECT']=str(root);os.environ['NLTL_TEST_OUTPUT']=str(out/'software_packets');(out/'software_packets').mkdir();suite=unittest.defaultTestLoader.discover(str(root/'tests'));log=io.StringIO();result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite);(out/'software_tests.txt').write_text(log.getvalue());assert result.wasSuccessful(),log.getvalue()
  old=history/SAVED/'I2-004/nltl';raw_file=old/'response_001.json';raw=load(raw_file);old_body=load(old/'review_state_001.json');seed=(old/'candidate_01.ttl').read_bytes();assert hashlib.sha256(seed).hexdigest()==SEED;c=Candidate(1,seed.decode(),'');config=Project(root).config('configs/nltl.json');config['continuation']={'max_provider_calls':9}
  unchanged_guard=function_source(root/'src/nltlv2/requests.py','review_conflicts')==function_source(history/SAVED/'runtime/nltlv2/requests.py','review_conflicts');assert unchanged_guard,'PROPERTY_PATH_VALIDATOR_MUST_REMAIN_UNCHANGED'
  replay=out/'UNCHANGED_SAVED_RESPONSE_REPLAY';replay.mkdir();shutil.copyfile(raw_file,replay/'original_response_001.json');(replay/'candidate_01.ttl').write_bytes(seed);transport=UnchangedSavedResponse(raw);runner=Runner(Project(root),config,transport,replay);runner.admission_context=copy.deepcopy(old_body['context']['admission']);runner.execution_summaries[1]=copy.deepcopy(old_body['execution_probe']);tracker=Tracker()
  obj,findings,error=runner.review(c,copy.deepcopy(old_body['context']),None,copy.deepcopy(old_body['change_manifest']),tracker,[])
  assert obj is None and findings==[] and error and runner.review_failure_outcome=='REVIEWER_PROPOSAL_CORRECTION_EXHAUSTED';assert len(transport.requests)==2 and tracker.prior_semantic_issues()==[] and sha(raw_file)==sha(replay/'original_response_001.json')
  first_packet=json.loads(transport.requests[0]['user']);original_response=json.loads(raw['text']);assert first_packet['review_request_id']==original_response['review_request_id'],'Saved binding was not adapted'
  first=load(replay/'reviewer_proposal_validation_001.json');second=load(replay/'reviewer_proposal_validation_002.json');assert first['correctable']==second['correctable'];assert first['route']=='CORRECT_RESPONSE';assert first['correctable'][0]['code']=='INCONSISTENT_REVIEWER_PROPERTY_PATH_PAIRING'
  replay_receipt=dict(label='UNCHANGED_HISTORICAL_RESPONSE_REPLAY_SOFTWARE_ONLY',saved_response=str(raw_file),saved_response_sha256=sha(raw_file),seed_sha256=SEED,no_response_metadata_adaptations=True,no_claim_or_path_changes=True,property_path_validator_byte_identical=unchanged_guard,initial_prior_issues=[],returned_findings=[],repair_authorized=False,outcome=runner.review_failure_outcome,scripted_response_deliveries=2,real_model_calls=0,shared_correction_calls=1,first_error=first['correctable'][0]);write(replay/'receipt.json',replay_receipt)
  # Separate new preparation: fresh current production source/schema, no saved reviewer issues.
  prep=out/'prepared_continuation';prep.mkdir();(prep/'candidate_01.ttl').write_bytes(seed);schema=Schema(Project(root));context=schema.context('I2-004');admission=load_admission(Project(root),dict(config,admission_file='data/admissions/i2_004_research_scope.approved.json'),schema,'I2-004');assert admission['valid'];context['admission']=copy.deepcopy(admission['context']);context['scope']+=' External population/date eligibility and edition selection are supplied by caller admission, not independently inferred from RDF. Conditions within the represented requirement remain in scope; activation and query correctness are separate obligations.';write(prep/'initial_source_schema_context.json',context)
  cfg=copy.deepcopy(config);cfg.update(method='offline',maximum_candidate_attempts=2,semantic_review=True,network_enabled=False,proposal_only=True,admission_file='data/admissions/i2_004_research_scope.approved.json');cfg['context_resolution']=dict(cfg.get('context_resolution',{}),max_rounds=2,max_reviews_per_run=4,max_reviews_per_candidate=3);cfg['continuation']=dict(label='DEVELOPMENT_CONTINUATION',requirement_id='I2-004',seed_sha256=SEED,seed_file=str((prep/'candidate_01.ttl').relative_to(root)),source_context=str((prep/'initial_source_schema_context.json').relative_to(root)),initial_generation_calls=0,max_repair_calls=1,max_total_candidates_including_seed=2,max_provider_calls=9,prior_issue_ids=[],dispatch_prepared_only=True,requires_separate_model_authorization=True,main_run_cli_must_reject=True,failed_historical_reviews_are_not_prior_state=True);write(prep/'continuation_config.json',cfg)
  prepared_cfg=copy.deepcopy(cfg);prepared_cfg['method']='NLTL';capture=NoDispatch();r=Runner(Project(root),prepared_cfg,capture,prep);r.admission_context=context['admission'];fs=check(c,r.schema,'I2-004',admission=context['admission']);execution,probe=runtime_probe(c,r.schema);fs+=execution;write(prep/'deterministic_findings.json',[f.asdict() for f in fs]);write(prep/'execution_only_probe.json',probe);r.execution_summaries[1]=probe_summary(c,probe)
  try:r.assess_candidate(c,context,None,{'status':'EXACT_SEED_UNCHANGED','changes':[]},Tracker(),fs,'I2-004')
  except CaptureBoundary:pass
  else:raise AssertionError('Expected a prepared review, no provider call')
  write(prep/'review_request.json',capture.packet);write(prep/'PREPARED_UNDISPATCHED.json',dict(seed_sha256=SEED,version='0.10.1',generations=0,max_repairs=1,max_candidates=2,max_primary_reviews=4,max_reviews_per_candidate=3,max_shared_response_corrections_per_review=1,max_retrieval_rounds=2,max_provider_calls=9,early_acceptance=True,regeneration=False,provider_transport='NONE',initial_prior_issues=[],historical_review_issues_loaded=False,no_known_diagnosis_or_solution_injected=True))
  for file in (root/'configs').glob('*.json'):Project(root).config(str(file.relative_to(root)))
  schema_audit=schema.audit();summary=dict(version='0.10.1',software_tests=result.testsRun,software_failures=len(result.failures),software_errors=len(result.errors),network='BLOCKED',model_calls=0,evaluation_reruns=0,property_path_validator_unchanged=unchanged_guard,replay=replay_receipt,config_schema_check='PASS',schema=schema_audit,representative_correction='software_packets/SCRIPTED_valid_response_correction_and_repair/request_003.json',prepared_continuation='prepared_continuation/continuation_config.json',ledger='Previous 17-item ledger retained unchanged; routing addendum only');write(out/'verification.json',summary)
  text=f'''Focused reviewer-error routing — v0.10.1 — offline software evidence

Exact change
requests.py::review_proposal_routing classifies proposal errors around the unchanged
review_conflicts validator. A path/property mismatch is correctable only when the
supplied current-requirement representation contract and quantity encoding match
current declarations, and the SAME path/role/unit/datatype passes the unchanged
validator for another declared property. No property, path or role is rewritten.
Unknown/unsupported paths, missing mappings, datatype/unit conflicts, UNRESOLVED_CONTEXT
and explicit UNRESOLVED_CONTRADICTION remain blocking CONFLICTs. Mixed failures
cannot hide a real contradiction behind an otherwise correctable pairing.

runner.py::Runner.review now validates proposal consistency before returning findings.
A proven inconsistent pairing raises a structured REVIEWER_PROPOSAL_ERROR inside
the EXISTING response-correction loop. The unchanged packet is resent once with
format_feedback: exact field, original property/path/role, original guard reason,
supplied matching declarations, and a correction-or-withdrawal instruction. The
candidate, evidence and original prior state stay identical. No new loop, route,
primary review, allowance or overall budget is added. review_format_retry remains
the transport label and consumes the same review_format_retries setting.

A failed correction returns REVIEWER_PROPOSAL_CORRECTION_EXHAUSTED with no accepted
issues and no repair authorization. Stale candidate/code/request binding is terminal
REQUEST_INTEGRITY_FAILURE. Integrity/infrastructure exceptions are not retried.
Blocking representation proposals are saved as audit evidence but excluded from
accepted issue/tracker state. The declared continuation max_provider_calls is enforced
before dispatch, so response correction cannot exceed the existing nine-call cap.

Multi-operand interface
issues[].operands[] may contain up to eight unique operand_id entries, each with
property, proposed_path and explicit PROPERTY/NUMERIC_OPERAND role, plus optional
unit/datatype. Each pair is separately passed to the same validator. Legacy scalar
proposals are still checked; a valid operands list cannot hide an invalid scalar
pair. Parent source/schema evidence applies. Only validated corrected operands are
delivered in targeted-repair feedback, as unverified model interpretations.

Offline verification
{result.testsRun} software controls passed with sockets blocked; configuration/schema checks passed.
Controls cover mismatched/unknown paths, valid multi-operand pairs, genuine and mixed
contradictions, stale state, infrastructure failure, zero/exhausted/shared correction
allowance, total call cap, immutable nonempty prior issues and full repair delivery.
The scripted valid correction -> targeted repair -> recheck control is SOFTWARE
EVIDENCE ONLY; no claim about real-model or regulatory correctness follows.

Saved-response replay
The actual v0.10.0 response was delivered unchanged: no binding, property, path,
role, quotation, diagnosis or metadata fix was made. It again passes citations/code
locations, and the original mismatched pairing is detected. Repeating that same
unchanged response as a SCRIPTED correction consumes the shared allowance and stops
at REVIEWER_PROPOSAL_CORRECTION_EXHAUSTED. No findings or repair permission escape.
The original response and candidate remain byte-identical. A separate generic
scripted correction supplies valid explicit pairs and alone permits repair; no
manually corrected I2-004 response or solution was created.

Artifacts
software_packets/SCRIPTED_valid_response_correction_and_repair/: complete original
review, correction request/response, repair/recheck and integrity/transition logs.
UNCHANGED_SAVED_RESPONSE_REPLAY/: exact saved response/seed, complete correction
packet, exact routing errors, exhaustion outcome and no-authorization receipt.
prepared_continuation/: exact unchanged seed, fresh current source/schema/approved
scope and diagnostics, complete initial review packet and offline-only config.
Bounds: zero generations; <=1 repair; <=2 candidates; <=4 primary reviews (<=3 per
candidate); one SHARED response correction/review; two retrieval rounds; <=9 calls;
early acceptance; no regeneration. No transport or dispatch is enabled.

Historical runs/scores/fixtures/ontology/approved scope, tracker and 17-item retention
ledger are unchanged. No model call, candidate edit, evaluation rerun or framework
rewrite occurred. The code/citation interpreter remains unverified; a real source/
schema contradiction cannot be fixed by correction of response metadata. Future
live execution requires separate authorization and must honor new explicit terminal
outcomes; older frozen continuation drivers are preserved, not repurposed silently.
''';(out/'REPORT.txt').write_text(text)
 print(json.dumps(dict(output=str(out),tests=result.testsRun,replayed_without_adaptation=True,model_calls=0,prepared_only=True)))
if __name__=='__main__':main()
