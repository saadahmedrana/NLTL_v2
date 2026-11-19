from __future__ import annotations
import difflib,json,time
from .core import GenerationProject,Candidate,finding,normalize,WrapperError,write,digest
from .schema import Schema
from .enumerations import coverage_findings
from .development_checks import assess
from .tracking import Tracker
from .checks import check,regression,transitions,runtime_probe
from .requests import initial_request,repair_request,assert_integrity,parse_review,ReviewerFormatError,review_conflicts
class Runner:
 def __init__(self,project,config,transport,output):
  self.p=GenerationProject(project.root);self.cfg=config;self.transport=transport;self.output=output;self.schema=Schema(self.p);self.sequence=0;self.latest_findings=();self.calls=[];self.response_metrics=[]
 def dispatch(self,request,latest=None):
  self.sequence+=1;request=dict(request,model=self.cfg['model'],max_output_tokens=self.cfg['review_max_tokens'] if request['route'].startswith('review') else self.cfg['generation_max_tokens'])
  if latest is not None and request['route'].endswith('repair'):
   saved=self.output/f'candidate_{latest.version:02d}.ttl'
   if saved.read_text()!=latest.code:raise ValueError('PRECEDING_CANDIDATE_ARTIFACT_STALE')
   write(self.output/f'request_{self.sequence:03d}_integrity.json',assert_integrity(request,latest,self.latest_findings))
  write(self.output/f'request_{self.sequence:03d}.json',request)
  self.output.joinpath(f'request_{self.sequence:03d}.rendered.txt').write_text(request['system']+'\n\n--- USER ---\n'+request['user'])
  self.calls.append(request)
  response=self.transport.dispatch(request,latest,self.latest_findings)
  write(self.output/f'response_{self.sequence:03d}.json',response)
  self.response_metrics.append(dict(sequence=self.sequence,route=request['route'],usage=response.get('usage',{}),elapsed_seconds=response.get('elapsed_seconds',0)))
  return response
 def review(self,c,context,warnings=()):
  request=dict(route='review',system=self.p.path('prompts/reviewer.txt').read_text(),user=json.dumps(dict(context=context,candidate_version=c.version,candidate_sha256=c.sha256,full_candidate=c.code,static_warnings=[f.asdict() for f in warnings],warning_policy='Static warnings are not confirmed regulatory defects. Establish source-backed need before recommending a change.',max_issues=self.cfg['review_max_issues']),ensure_ascii=False))
  for retry in range(self.cfg['review_format_retries']+1):
   response=self.dispatch(request,c)
   try:
    obj,fs=parse_review(response,c,context,self.cfg['review_max_issues']);return obj,fs,None
   except ReviewerFormatError as e:
    write(self.output/f'reviewer_format_failure_{self.sequence:03d}.json',dict(error=str(e),raw_response=response,candidate_version=c.version,sha256=c.sha256,not_regulatory_rejection=True))
    if retry==self.cfg['review_format_retries']:return None,[],str(e)
    request=dict(request,route='review_format_retry',user=json.dumps(dict(original_request=json.loads(request['user']),format_error=str(e),raw_previous_response=response['text'],instruction='Return complete bounded JSON. No code generation or repair.')))
 def run(self,rid):
  if self.cfg.get('seed_candidate') and self.cfg.get('requirement_id')!=rid:raise ValueError('SEED_SCOPE_MISMATCH')
  context=self.schema.context(rid);write(self.output/'context.json',context)
  blockers=[issue for issue in context.get('unresolvedSourceContext',[]) if issue.get('blocking_before_generation')]
  if blockers:
   result=dict(method=self.cfg['method'],requirement_id=rid,status='BLOCKED_PREFLIGHT_CONTEXT',candidate_attempts=0,generation_calls=0,auxiliary_format_retries=0,accepted_version=None,evaluation_candidate=None,request_count_by_route={},elapsed_seconds=0,history=[],blockers=blockers)
   write(self.output/'run.json',result);return result
  settings={k:self.cfg[k] for k in ['model','generation_max_tokens','review_max_tokens']}
  request=initial_request(self.p,context,settings);method=self.cfg['method'];maximum=1 if method=='Single-shot' else self.cfg['maximum_candidate_attempts']
  history=[];old=None;oldfindings=[];authorization=[];tracker=Tracker();start=time.monotonic();status='ATTEMPT_LIMIT_EXHAUSTED'
  seed=self.cfg.get('seed_candidate');operational_failure=None
  if seed and (method!='NLTL' or self.cfg.get('run_label')!='TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC'):raise ValueError('Seed mode is diagnostic NLTL only')
  for attempt in range(1,maximum+1):
   call_start=len(self.response_metrics);response={};format_error=None;normalization=None
   try:
    if seed and attempt==1:
     code=self.p.path(seed['path']).read_text();raw=self.p.path(seed['raw_response']).read_text()
     if digest(code)!=seed['sha256'] or normalize(raw)[0]!=code:raise ValueError('SEED_CANDIDATE_INTEGRITY_FAILURE')
     normalization=dict(origin='BYTE_IDENTICAL_DIAGNOSTIC_SEED',historical_candidate_version=seed['historical_version'],sha256=seed['sha256'])
    else:
     response=self.dispatch(request,old);raw=response['text']
     try:code,normalization=normalize(raw)
     except WrapperError as e:code=raw;format_error=str(e)
    c=Candidate(attempt,code,raw);self.output.joinpath(f'candidate_{attempt:02d}.ttl').write_text(code)
    write(self.output/f'candidate_{attempt:02d}.json',dict(version=attempt,sha256=c.sha256,normalization=normalization,attempt_includes_initial=True,origin='DIAGNOSTIC_SEED' if seed and attempt==1 else 'RESPONSE'))
    if method=='Single-shot':
     history.append(dict(attempt=attempt,version=c.version,sha256=c.sha256,status='FORMAT_ERROR' if format_error else 'ORIGINAL_RESPONSE',accepted=None,findings=[],response_format_error=format_error));status='SINGLE_SHOT_COMPLETE';write(self.output/'history.json',history);break
    fs=[finding(c,'RESPONSE_FORMAT_ERROR','Missing or ambiguous response wrapper',raw,expected='<BEGIN_SHACL>\\ncomplete Turtle\\n<END_SHACL>',evidence='prompts/generator.txt wrapper contract',suggestion='Return exactly one full SHACL block with expected markers.',diagnostic=format_error)] if format_error else check(c,self.schema,rid)
    parsed=not format_error and not any(f.category=='PARSE_ERROR' for f in fs)
    behavioral=dict(status='UNASSESSED_FORMAT_OR_PARSE',complete_verification=False,unchecked=['Format/parse must be repaired before behavioral checks.'])
    if parsed:
     _,coverage=coverage_findings(c,self.schema,rid);write(self.output/f'enumeration_coverage_{attempt:02d}.json',coverage)
     behavioral_findings,behavioral=assess(c,self.schema,rid);fs+=behavioral_findings
    write(self.output/f'development_coverage_{attempt:02d}.json',behavioral)
    if old:
     self.output.joinpath(f'diff_{attempt-1:02d}_{attempt:02d}.patch').write_text(''.join(difflib.unified_diff(old.code.splitlines(True),c.code.splitlines(True),fromfile=f'v{old.version}',tofile=f'v{c.version}')))
     if not format_error:fs+=regression(old,c,authorization,schema=self.schema,rid=rid)
    fs+=tracker.carry_unrestored_guards(c,fs)
    from .constraint_changes import preservation_conflicts
    fs+=preservation_conflicts(c,fs,authorization)
    def blocking():return [f for f in fs if f.blocking]
    obj=None;review_error=None;conflict=[f.asdict() for f in fs if f.category=='PRESERVATION_CONFLICT'];runtime_complete=False
    if not blocking():
     runtime_findings,probe=runtime_probe(c,self.schema);fs+=runtime_findings;runtime_complete=not runtime_findings;write(self.output/f'runtime_probe_{attempt:02d}.json',probe)
    if not blocking():
     obj,semantic,review_error=self.review(c,context,warnings=[f for f in fs if not f.blocking]);fs+=semantic
     if obj:conflict=review_conflicts(obj,self.schema,rid)
    changes,persistent=tracker.observe(c,fs,behavioral,static_complete=parsed,review_complete=obj is not None,runtime_complete=runtime_complete)
    accepted=not blocking() and not review_error and not conflict
    resource=any(f.assessment=='RESOURCE_UNCERTAIN' for f in blocking());infra=any(f.assessment=='INFRASTRUCTURE_OR_UNKNOWN' for f in blocking())
    state='ACCEPTED' if accepted else 'RESOURCE_ATTRIBUTION_UNCERTAIN' if resource else 'INFRASTRUCTURE_FAILURE' if infra else 'REVIEWER_FORMAT_FAILURE' if review_error else 'CONFLICT' if conflict else 'UNRESOLVED_CONTEXT' if any(not f.confirmed for f in blocking()) else 'REJECTED'
    stagnation=tracker.stagnation_stop(self.cfg.get('stagnation',{})) if not accepted else None
    if stagnation and state=='REJECTED':state='STAGNATION_STOP'
    row=dict(development_coverage={k:v for k,v in behavioral.items() if k!='witnesses'},acceptance_scope='Internal acceptance only; finite witnesses, static warnings and semantic review do not establish complete correctness.',request_metrics=self.response_metrics[call_start:],candidate_response_usage=response.get('usage',{}),candidate_response_seconds=response.get('elapsed_seconds',0),attempt=attempt,version=c.version,sha256=c.sha256,status=state,accepted=accepted,findings=[f.asdict() for f in fs],changes=changes,persistent_failure_summary=persistent,stagnation_reason=stagnation,review=obj,reviewer_format_failure=review_error,conflicts=conflict,static_warnings=[f.asdict() for f in fs if not f.blocking])
    history.append(row);write(self.output/'history.json',history);write(self.output/f'findings_{attempt:02d}.json',[f.asdict() for f in fs]);write(self.output/f'reconciliation_{attempt:02d}.json',changes);write(self.output/f'persistent_failure_summary_{attempt:02d}.json',persistent);self.latest_findings=tuple(fs)
    status=state
    if accepted or state in ['RESOURCE_ATTRIBUTION_UNCERTAIN','INFRASTRUCTURE_FAILURE','REVIEWER_FORMAT_FAILURE','CONFLICT','UNRESOLVED_CONTEXT','STAGNATION_STOP']:break
    old=c;oldfindings=fs;authorization=fs
    if attempt<maximum:request=repair_request(self.p,context,c,fs,persistent_summary=persistent)
    status='ATTEMPT_LIMIT_EXHAUSTED'
   except Exception as e:
    text=str(e);integrity=any(x in text for x in ['STALE','INTEGRITY','ABSENT','FEEDBACK','TRUNCATED_PREVIOUS','RENDERED_REQUEST'])
    status='REQUEST_INTEGRITY_FAILURE' if integrity else 'RESOURCE_ATTRIBUTION_UNCERTAIN' if isinstance(e,(TimeoutError,MemoryError,RecursionError)) or 'timeout' in type(e).__name__.lower() else 'INFRASTRUCTURE_FAILURE'
    operational_failure=dict(status=status,type=type(e).__name__,diagnostic=text,attempt=attempt,no_automatic_retry=True)
    write(self.output/'operational_failure.json',operational_failure);break
  coverage=history[-1].get('development_coverage',{'status':'INDEPENDENT_EVALUATION_ONLY_FOR_SINGLE_SHOT'}) if history else {'status':'UNASSESSED_OPERATIONAL_FAILURE'}
  result=dict(complete_verification=False,verification_coverage=coverage,method=method,requirement_id=rid,status=status,candidate_attempts=len(history),dispatch_attempts=len(self.calls),successful_response_count=len(self.response_metrics),auxiliary_format_retries=sum(r['route']=='review_format_retry' for r in self.calls),generation_calls=sum(r['route']=='generation' for r in self.calls),accepted_version=next((h['version'] for h in history if h['accepted']),None),evaluation_candidate=next((h['version'] for h in history if h['accepted']),1 if method=='Single-shot' and history else None),exhaustion_policy='Unaccepted NLTL candidates have NO_VERDICT; last candidate diagnostic only.',request_count_by_route={route:sum(q['route']==route for q in self.calls) for route in {q['route'] for q in self.calls}},elapsed_seconds=time.monotonic()-start,history=history,operational_failure=operational_failure,run_label=self.cfg.get('run_label','FRESH_PIPELINE'),seed_origin=seed,stagnation_policy=self.cfg.get('stagnation',{'enabled':False}),failure_policy='Attributable bounded candidate query errors are repairable; infrastructure/integrity/conflict stop dispatch; uncertain time/resource failures stop without code blame.')
  write(self.output/'run.json',result);return result
