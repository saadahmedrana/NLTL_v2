from __future__ import annotations
import difflib,json,time
from .core import Candidate,finding,normalize,WrapperError,write,digest
from .schema import Schema
from .checks import check,regression,transitions,runtime_probe
from .requests import initial_request,repair_request,assert_integrity,parse_review,ReviewerFormatError,review_conflicts
class Runner:
 def __init__(self,project,config,transport,output):
  self.p=project;self.cfg=config;self.transport=transport;self.output=output;self.schema=Schema(project);self.sequence=0;self.latest_findings=();self.calls=[];self.response_metrics=[]
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
 def review(self,c,context):
  request=dict(route='review',system=self.p.path('prompts/reviewer.txt').read_text(),user=json.dumps(dict(context=context,candidate_version=c.version,candidate_sha256=c.sha256,full_candidate=c.code,max_issues=self.cfg['review_max_issues']),ensure_ascii=False))
  for retry in range(self.cfg['review_format_retries']+1):
   response=self.dispatch(request,c)
   try:
    obj,fs=parse_review(response,c,context,self.cfg['review_max_issues']);return obj,fs,None
   except ReviewerFormatError as e:
    write(self.output/f'reviewer_format_failure_{self.sequence:03d}.json',dict(error=str(e),raw_response=response,candidate_version=c.version,sha256=c.sha256,not_regulatory_rejection=True))
    if retry==self.cfg['review_format_retries']:return None,[],str(e)
    request=dict(request,route='review_format_retry',user=json.dumps(dict(original_request=json.loads(request['user']),format_error=str(e),raw_previous_response=response['text'],instruction='Return complete bounded JSON. No code generation or repair.')))
 def run(self,rid):
  context=self.schema.context(rid);write(self.output/'context.json',context)
  settings={k:self.cfg[k] for k in ['model','generation_max_tokens','review_max_tokens']};request=initial_request(self.p,context,settings)
  method=self.cfg['method'];maximum=1 if method=='Single-shot' else self.cfg['maximum_candidate_attempts'];history=[];old=None;oldfindings=[];authorization=[];start=time.monotonic()
  for attempt in range(1,maximum+1):
   call_start=self.sequence
   response=self.dispatch(request,old)
   raw=response['text'];normalization=None
   try:code,normalization=normalize(raw);format_error=None
   except WrapperError as e:code=raw;format_error=str(e)
   c=Candidate(attempt,code,raw);self.output.joinpath(f'candidate_{attempt:02d}.ttl').write_text(code)
   write(self.output/f'candidate_{attempt:02d}.json',dict(version=attempt,sha256=c.sha256,normalization=normalization,attempt_includes_initial=True))
   if method=='Single-shot':
    history.append(dict(attempt=attempt,version=c.version,sha256=c.sha256,status='FORMAT_ERROR' if format_error else 'ORIGINAL_RESPONSE',accepted=None,findings=[],response_format_error=format_error));status='SINGLE_SHOT_COMPLETE';write(self.output/'history.json',history);break
   fs=[finding(c,'RESPONSE_FORMAT_ERROR','Missing or ambiguous response wrapper',raw,expected='<BEGIN_SHACL>\\ncomplete Turtle\\n<END_SHACL>',evidence='prompts/generator.txt wrapper contract',suggestion='Return exactly one full SHACL block with expected markers.',diagnostic=format_error)] if format_error else check(c,self.schema,rid)
   if old:
    self.output.joinpath(f'diff_{attempt-1:02d}_{attempt:02d}.patch').write_text(''.join(difflib.unified_diff(old.code.splitlines(True),c.code.splitlines(True),fromfile=f'v{old.version}',tofile=f'v{c.version}')))
    if not format_error:fs+=regression(old,c,authorization)
   obj=None;review_error=None;conflict=[]
   if not fs:
    runtime_findings,probe=runtime_probe(c,self.schema);fs+=runtime_findings;write(self.output/f'runtime_probe_{attempt:02d}.json',probe)
   if not fs:
    obj,semantic,review_error=self.review(c,context);fs+=semantic
    if obj:conflict=review_conflicts(obj,self.schema,rid)
   accepted=not fs and not review_error and not conflict
   state='ACCEPTED' if accepted else ('REVIEWER_FORMAT_FAILURE' if review_error else 'CONFLICT' if conflict else 'UNRESOLVED_CONTEXT' if any(not f.confirmed for f in fs) else 'REJECTED')
   row=dict(request_metrics=self.response_metrics[call_start:],candidate_response_usage=response.get('usage',{}),candidate_response_seconds=response.get('elapsed_seconds',0),attempt=attempt,version=c.version,sha256=c.sha256,status=state,accepted=accepted,findings=[f.asdict() for f in fs],changes=transitions(oldfindings,fs),review=obj,reviewer_format_failure=review_error,conflicts=conflict)
   history.append(row);write(self.output/'history.json',history);write(self.output/f'findings_{attempt:02d}.json',[f.asdict() for f in fs]);self.latest_findings=tuple(fs)
   if accepted or review_error or conflict or any(not f.confirmed for f in fs):status=state;break
   old=c;oldfindings=fs;authorization=fs
   if attempt<maximum:request=repair_request(self.p,context,c,fs)
   status='ATTEMPT_LIMIT_EXHAUSTED'
  result=dict(method=method,requirement_id=rid,status=status,candidate_attempts=len(history),auxiliary_format_retries=sum(r['route']=='review_format_retry' for r in self.calls),generation_calls=sum(r['route']=='generation' for r in self.calls),accepted_version=next((h['version'] for h in history if h['accepted']),None),evaluation_candidate=next((h['version'] for h in history if h['accepted']),1 if method=='Single-shot' else None),exhaustion_policy='Unaccepted NLTL candidates have NO_VERDICT; last candidate diagnostic only.',request_count_by_route={route:sum(q['route']==route for q in self.calls) for route in {q['route'] for q in self.calls}},elapsed_seconds=time.monotonic()-start,history=history)
  write(self.output/'run.json',result);return result
