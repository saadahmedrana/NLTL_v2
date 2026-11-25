from pathlib import Path
import sys,json,copy,tempfile,hashlib
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261125_TWENTY_REQUIREMENT_APPROVAL_PREPARATION';D=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION';sys.path[:0]=[str(R/'src'),str(D/'tokenizer_runtime')]
from nltlv2.core import Project,Candidate,write,offline_network_guard
from nltlv2.runner import Runner
from nltlv2.tracking import Tracker
from nltlv2.change_review import manifest
from nltlv2.transport import provider_payload
from nltlv2.token_budget import load_counter,preflight
from nltlv2.schema import N
load=lambda p:json.loads(p.read_text());rows=[];counter=load_counter(R,load(D/'token_limits.verified.json'));p=Project(R)
class CaptureDone(Exception):pass
class Capture:
 is_live=False
 def dispatch(self,q,*a):self.request=copy.deepcopy(q);raise CaptureDone()
with offline_network_guard():
 for job in load(A/'experiment.prepared.json')['jobs']:
  if job['model_tag']!='GPTOSS':continue
  rid=job['requirement_id'];cfg=load(R/job['manifest'])['config'];preview=load(A/'initial_request_previews/GPTOSS'/str(rid+'.json'));context=json.loads(preview['request']['user'])['context'];root=context['admission']['declaration']['focus_set']['owner_class'].removeprefix(str(N));code='@prefix sh:<http://www.w3.org/ns/shacl#>. @prefix n:<'+str(N)+'>. n:SoftwarePreflight a sh:NodeShape;sh:targetClass n:'+root+';sh:nodeKind sh:IRI.\n'
  for kind in ['minimal_generic','output_token_envelope_generic']:
   if kind!='minimal_generic':
    padding=max(0,(16000-counter(code))//counter('# x\n'));code+='# x\n'*padding
    while counter(code)>16000:code=code[:-4]
   dest=A/'review_preflight_software_only'/rid/kind;dest.mkdir(parents=True,exist_ok=True);(dest/'candidate_01.ttl').write_text(code);t=Capture();r=Runner(p,cfg,t,dest);r.admission_context=context['admission'];c=Candidate(1,code,code)
   try:r.review(c,context,None,dict(status='INITIAL_CANDIDATE',changes=[]),Tracker(),[])
   except CaptureDone:pass
   payload=provider_payload(t.request);payload['input']=[dict(role='developer' if x['role']=='system' else x['role'],content=[dict(type='input_text',text=x['content'])]) for x in payload['input']];payload.update(truncation='disabled',store=False);budget=preflight(payload,load(D/'token_limits.verified.json'),counter)
   write(dest/'SOFTWARE_ONLY.json',dict(label='UNDISPATCHED_GENERIC_RENDERING_CONTROL_NOT_A_GENERATED_CANDIDATE',candidate_tokens=counter(code),provider_calls=0));rows.append(dict(requirement_id=rid,kind=kind,candidate_tokens=counter(code),**budget));print(rid,kind,budget['supplied_text_tokens'],budget['status'],flush=True)
write(A/'review_capacity.software_only.json',rows)
