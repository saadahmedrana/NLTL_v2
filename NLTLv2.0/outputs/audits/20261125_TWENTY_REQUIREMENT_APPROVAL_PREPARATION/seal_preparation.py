"""Offline approval/resource seal. Never creates approval or dispatches requests."""
import pathlib,json,sys,hashlib,copy,argparse
R=pathlib.Path(__file__).resolve().parents[3];A=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(R/'src'));sys.path.insert(0,str(R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION/tokenizer_runtime'))
from nltlv2.core import Project,GenerationProject,write,offline_network_guard
from nltlv2.schema import Schema
from nltlv2.admission import validate_declaration,definition_hash
from nltlv2.hosted_pilot import verify
from nltlv2.requests import initial_request
from nltlv2.transport import provider_payload
from nltlv2.token_budget import load_counter,preflight
load=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--check-only',action='store_true');a=p.parse_args();blocked=[];lock=load(A/'pipeline.freeze.json');verify(R,lock);bundle=load(A/'preparation_bundle.freeze.json')
 for n,h in bundle['files'].items():
  if sha(R/n)!=h:raise ValueError('PREPARATION_CHANGED '+n)
 selection=load(A/'selection.frozen.json');s=Schema(GenerationProject(R));defs=load(A/'scope_definition_hashes.json');scopes={}
 with offline_network_guard():
  for rid,file in selection['scope_files'].items():
   if not (R/file).is_file():blocked.append(dict(requirement_id=rid,reason='APPROVED_SCOPE_FILE_MISSING',proposed=file.replace('.approved.','.proposed.')));continue
   declaration=load(R/file);v=validate_declaration(declaration,s,rid)
   if not v['valid'] or definition_hash(declaration)!=defs[rid]:blocked.append(dict(requirement_id=rid,reason='APPROVAL_OR_SCOPE_DEFINITION_MISMATCH',errors=v['errors']));continue
   scopes[rid]=v['context']
  for n,h in load(A/'evaluation_inputs.freeze.json')['files'].items():
   if sha(R/n)!=h:raise ValueError('EVALUATION_INPUT_CHANGED '+n)
  if blocked:print(json.dumps(dict(status='BLOCKED',decisions=blocked,model_calls=0),indent=2));return 2
  master=load(A/'experiment.prepared.json');renderings=[]
  for job in master['jobs']:
   m=load(R/job['manifest']);cfg=m['config'];rid=job['requirement_id'];ctx=s.context(rid);ctx['admission']=scopes[rid];ctx['scope']+=' External population/date eligibility and edition selection are supplied by caller admission, not independently inferred from RDF. Conditions within the represented requirement remain in scope; activation and query correctness are separate obligations.'
   q=initial_request(Project(R),ctx,{k:cfg[k] for k in ['model','generation_max_tokens','review_max_tokens']});q.update(model=cfg['model'],max_output_tokens=cfg['generation_max_tokens']);payload=provider_payload(q);payload['input']=[dict(role='developer' if x['role']=='system' else x['role'],content=[dict(type='input_text',text=x['content'])]) for x in payload['input']];payload.update(truncation='disabled',store=False);budget=preflight(payload,m['token_limits'],load_counter(R,m['token_limits']))
   if budget['exceeds_known_token_limit']:raise ValueError('APPROVED_REQUEST_CAPACITY_EXCEEDED '+rid)
   renderings.append(dict(model=cfg['model'],requirement_id=rid,identical_logical_initial_requests=True,request=q,provider_payload=payload,request_bytes=len(json.dumps(payload,ensure_ascii=False).encode()),budget=budget))
  if a.check_only:
   if (A/'dispatch.freeze.json').exists():
    verify(R,load(A/'dispatch.freeze.json'))
    frozen=load(A/'experiment.dispatch.json')
    for n,h in frozen['dispatch_manifest_sha256'].items():
     if sha(R/n)!=h:raise ValueError('DISPATCH_CONFIGURATION_CHANGED '+n)
   print(json.dumps(dict(status='APPROVED_RESOURCES_MATCH',requirements=20,overlap=10,model_calls=0)));return 0
  if (A/'dispatch.freeze.json').exists():raise ValueError('SEAL_ALREADY_EXISTS_NO_OVERWRITE')
  final=copy.deepcopy(lock);final['files'].update({f:sha(R/f) for f in selection['scope_files'].values()});final['files'].update(bundle['files']);final['snapshot_id']+='__APPROVAL_SEALED'
  ev=load(A/'evaluation_inputs.freeze.json');ev['files'].update({f:sha(R/f) for f in selection['scope_files'].values()});write(A/'evaluation_resources.lock.json',ev)
  write(A/'initial_requests.approved.json',renderings)
  for job in master['jobs']:
   m=load(R/job['manifest']);m['dispatch_ready']=True;m['scopes_pending']=[];m['authorization']='Approved scope files and frozen resources verified; experiment inference requires user launch flag.';write(R/job['dispatch_manifest'],m)
  final['files'].update({j['dispatch_manifest']:sha(R/j['dispatch_manifest']) for j in master['jobs']});final['files'][str((A/'evaluation_resources.lock.json').relative_to(R))]=sha(A/'evaluation_resources.lock.json');write(A/'dispatch.freeze.json',final)
  master['dispatch_ready']=True;master['status']='APPROVAL_SEALED_UNDISPATCHED';master['source_freeze_sha256']=sha(A/'dispatch.freeze.json');master['dispatch_manifest_sha256']={j['dispatch_manifest']:sha(R/j['dispatch_manifest']) for j in master['jobs']};write(A/'experiment.dispatch.json',master)
  print(json.dumps(dict(status='SEALED_UNDISPATCHED',requirements=20,overlap=10,model_calls=0)))
 return 0
if __name__=='__main__':raise SystemExit(main())
