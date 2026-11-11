"""One authorized development pilot. No evaluation imports or fixtures in this process."""
from pathlib import Path
import json,hashlib,datetime,subprocess,sys,os,shutil,time,traceback,urllib.parse,importlib.metadata
from nltlv2.core import Project,write,stamp,digest
from nltlv2.schema import Schema
from nltlv2.requests import initial_request
from nltlv2.runner import Runner
from nltlv2.transport import LiveTransport
ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');REPO=ROOT.parent
ENV=Path('/Users/sadisfaction570/Desktop/Journal 1/env/NLTL_v2.env');p=Project(ROOT);rid='TRF-010';tag=stamp()+'_TRF010_LIVE_DEV';group=p.output('experiments',tag)
shutil.copyfile(__file__,group/'pilot_driver.py');git='/Library/Developer/CommandLineTools/usr/bin/git'
def command(*args):return subprocess.run([git,'-C',str(REPO),*args],capture_output=True,text=True,check=True).stdout
revision=command('rev-parse','HEAD');(group/'git_revision.txt').write_text(revision);(group/'git_status_before.txt').write_text(command('status','--porcelain=v1','--untracked-files=normal'));(group/'git_diff_stat_before.txt').write_text(command('diff','--stat'));(group/'git_cached_diff_stat_before.txt').write_text(command('diff','--cached','--stat'))
# Exact current generation resources and implementation snapshot, without old outputs or secrets.
snapshot=group/'snapshot';snapshot.mkdir()
for d in ['src','prompts','configs','schema','data/requirements','data/examples','data/contracts']:
 shutil.copytree(ROOT/d,snapshot/d,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.egg-info'))
hashes={str(f.relative_to(snapshot)):hashlib.sha256(f.read_bytes()).hexdigest() for f in snapshot.rglob('*') if f.is_file()};write(group/'snapshot_hashes.json',hashes)
import nltlv2
assert all(f.read_bytes()==(Path(nltlv2.__file__).parent/f.name).read_bytes() for f in (ROOT/'src/nltlv2').glob('*.py'))
schema=Schema(p);context=schema.context(rid);examples=context['examples'];req=context['requirement'];assert all(rid not in json.dumps(x) and x['inputRequirement']!=req['text'] and x['inputRequirement']!=req['normalized'] for x in examples)
configs={m:p.config('configs/'+f+'.json') for m,f in [('Single-shot','single_shot'),('NLTL','nltl')]}
for c in configs.values():c['network_enabled']=True # Explicit authorized live-pilot override only; base configs unchanged.
assert configs['Single-shot']['maximum_candidate_attempts']==1 and not configs['Single-shot']['semantic_review'];assert configs['NLTL']['maximum_candidate_attempts']==6 and not configs['NLTL']['fresh_regeneration']
requests_=[initial_request(p,context,{k:c[k] for k in ['model','generation_max_tokens','review_max_tokens']}) for c in configs.values()];assert requests_[0]==requests_[1]
write(group/'initial_request.json',requests_[0]);write(group/'resolved_configs.json',configs)
from dotenv import dotenv_values
v=dotenv_values(ENV);url=v['AALTO_RESPONSES_BASE_URL'].rstrip('/');u=urllib.parse.urlsplit(url);assert u.scheme=='https' and u.hostname and not any([u.username,u.password,u.query,u.fragment]) and v['AALTO_API_KEY']
old_config=json.loads((REPO/'MVP/SHACL_GENERATION_PIPELINE/experiments/FULL_REPAIR_V2/CONFIGS/pipeline.full-repair-v2-run01.json').read_text());assert all(c['model']==old_config['models']['generator'] for c in configs.values())
write(group/'preflight.json',dict(requirement_id=rid,git_revision=revision.strip(),credential_location=str(ENV),credential_file_exists=True,key_present=True,credentials_logged=False,endpoint_origin=u.scheme+'://'+u.netloc,endpoint_path=u.path,model=configs['NLTL']['model'],model_identifier_matches_FULL_REPAIR_V2_RUN_01=True,availability_probe='None; actual generation request is the availability test',schema_sha256=hashes['schema/Schema_for_NLTL.ttl'],initial_request_sha256=digest(json.dumps(requests_[0],ensure_ascii=False)),initial_requests_identical=True,selected_examples=[dict(id=x['exampleId'],text=x['inputRequirement']) for x in examples],target_absent_from_selected_examples=True,substitution=None,network_override='Explicit authorized pilot only',package_version=importlib.metadata.version('nltlv2-refined'),python=sys.version,dependencies={k:importlib.metadata.version(k) for k in ['rdflib','pyshacl','requests','python-dotenv']},evaluation_firewall='No evaluation modules/fixtures/labels/counterparts accessed by this driver; evaluate only after generation completes',limits=dict(requirements=1,single_shot_generation_calls=1,nltl_maximum_candidate_attempts=6,nltl_reviewer_format_retries=1,fresh_regeneration=False),snapshots='snapshot/',scope='Development pilot, no comparative performance inference'))
del v
os.environ['NLTL_ALLOW_MODEL_CALLS']='YES';os.environ['NLTL_ENV_FILE']=str(ENV)
class AuditedLiveTransport(LiveTransport):
 def __init__(self,dest):super().__init__(enabled=True,project_root=ROOT);self.dest=dest;self.index=0;self.events=[]
 def dispatch(self,request,latest=None,expected_findings=None):
  self.index+=1;i=self.index
  payload=dict(model=request['model'],input=[dict(role='system',content=request['system']),dict(role='user',content=request['user'])],max_output_tokens=request['max_output_tokens'])
  write(self.dest/f'provider_request_{i:03d}.json',dict(endpoint_origin=u.scheme+'://'+u.netloc,endpoint_path=u.path,headers_names=['Ocp-Apim-Subscription-Key'],body=payload))
  start=time.monotonic();event=dict(index=i,route=request['route'],candidate_version=latest.version if latest else None,request_sha256=digest(json.dumps(payload)),status='DISPATCHING');self.events.append(event);write(self.dest/'call_ledger.json',self.events)
  try:
   result=super().dispatch(request,latest,expected_findings);provider=result.get('provider_response',{});event.update(status='RESPONSE',response_status=result.get('status'),finish_reason=result.get('finish_reason'),provider_model=provider.get('model'),provider_id=provider.get('id'),usage=result.get('usage',{}),elapsed_seconds=result.get('elapsed_seconds'));write(self.dest/'call_ledger.json',self.events);return result
  except Exception as e:
   response=getattr(e,'response',None);body=response.text if response is not None else None
   if body:body=body.replace(self.key,'[REDACTED_CREDENTIAL]')
   event.update(status='ERROR',exception_type=type(e).__name__,http_status=response.status_code if response is not None else None,body=body,elapsed_seconds=time.monotonic()-start);write(self.dest/'call_ledger.json',self.events);raise RuntimeError('Provider dispatch failed; see redacted call_ledger.json') from None
outcomes={};start=time.monotonic();print('PILOT_DIRECTORY='+str(group),flush=True)
for method in ['Single-shot','NLTL']:
 dest=group/('single_shot' if method=='Single-shot' else 'nltl');dest.mkdir();write(dest/'resolved_config.json',configs[method]);transport=AuditedLiveTransport(dest)
 print('START '+method,flush=True)
 try:
  result=Runner(p,configs[method],transport,dest).run(rid);outcomes[method]={k:v for k,v in result.items() if k!='history'};print('FINISHED '+method+' '+result['status']+' candidates='+str(result['candidate_attempts']),flush=True)
 except Exception as e:
  outcomes[method]=dict(status='PROVIDER_OR_RUNNER_FAILURE',message=str(e),call_count=transport.index);write(group/'execution_outcomes.json',outcomes);print('STOP '+method+' '+str(e),flush=True);break
 write(group/'execution_outcomes.json',outcomes)
write(group/'execution_outcomes.json',dict(requirement_id=rid,methods=outcomes,elapsed_seconds=time.monotonic()-start,scope='One requirement only; no evaluation has been run or fed back'))
print('COMPLETE '+str(group),flush=True)
