from pathlib import Path
import json,hashlib,datetime
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0')
A=R/'outputs/audits/20261124_HOSTED_GPT_OSS_PREPARATION'
A.mkdir(exist_ok=False)
files={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts and not p.is_relative_to(A)}
(A/'protected_before.json').write_text(json.dumps(files,indent=2))
for f in ['src/nltlv2/runner.py','src/nltlv2/transport.py','src/nltlv2/__init__.py','pyproject.toml']:
 p=A/'original'/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((R/f).read_bytes())
p=R/'src/nltlv2/runner.py';s=p.read_text()
s=s.replace('def run(self,rid):','def run(self,rid,*,shared_start=None):')
s=s.replace("response=self.dispatch(request,old);raw=response['text'];fmt=None;normalization=None",'''if attempt==1 and shared_start is not None:
     expected=dict(request,model=self.cfg['model'],max_output_tokens=self.cfg['generation_max_tokens'])
     if shared_start['request']!=expected:raise ValueError('SHARED_START_REQUEST_INTEGRITY_FAILURE')
     response=copy.deepcopy(shared_start['response'])
     if hashlib.sha256(json.dumps(response,sort_keys=True).encode()).hexdigest()!=shared_start['response_sha256']:raise ValueError('SHARED_START_RESPONSE_INTEGRITY_FAILURE')
     write(self.output/'shared_start.json',dict(request=expected,response=response,response_sha256=shared_start['response_sha256'],physical_call=False))
    else:response=self.dispatch(request,old)
    raw=response['text'];fmt=None;normalization=None
    if response.get('status')=='incomplete' or response.get('finish_reason') in ['length','max_tokens','max_output_tokens']:fmt='Provider output incomplete'
'''.rstrip())
# Preserve incomplete status even if syntactically complete wrapper.
s=s.replace("try:code,normalization=normalize(raw)","try:code,normalization=normalize(raw)")
s=s.replace("check_seconds=time.monotonic()-check_start", """technical=dict(candidate_version=c.version,candidate_sha256=c.sha256,qualifies=not fmt and runtime_complete and not any(f.blocking and f.category!='UNRESOLVED_CONTEXT' for f in fs),runtime_complete=runtime_complete,findings=[f.asdict() for f in fs],check_seconds=time.monotonic()-check_start)
    write(self.output/f'technical_{attempt:02d}.json',technical)
    check_seconds=time.monotonic()-check_start""")
s=s.replace("row=dict(attempt=attempt,version=attempt", "row=dict(technical=technical,attempt=attempt,version=attempt")
s=s.replace("result=dict(version='0.10.1'", "result=dict(version='0.11.0'")
s=s.replace("write(self.output/'run.json',result);return result\n", """if self.cfg.get('delivery_policy')=='latest_technical':
   from .delivery import finalize
   result['delivery']=finalize(self.output,history,status)
   result['accepted_only_evaluation_candidate']=result['evaluation_candidate']
   result['evaluation_candidate']=result['delivery']['version']
   result['exhaustion_policy']='Latest technically qualifying candidate; ACCEPTED requires unchanged grounded acceptance. UNVERIFIED is not correctness approval.'
  result['shared_start']=shared_start is not None
  write(self.output/'run.json',result);return result
""")
p.write_text(s)
for f in ['src/nltlv2/__init__.py','pyproject.toml']:
 p=R/f;p.write_text(p.read_text().replace('0.10.1','0.11.0'))
print('Preparation baseline saved; Runner shared-start and technical evidence added.')
