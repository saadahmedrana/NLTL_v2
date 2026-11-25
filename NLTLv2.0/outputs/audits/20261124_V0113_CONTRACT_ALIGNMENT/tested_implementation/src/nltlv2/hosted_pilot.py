"""Small shared-start entry point using the production Runner; evaluation is separate."""
import argparse,copy,hashlib,json,pathlib,sys,time,datetime
from .core import Project,load,write,digest
from .runner import Runner
from .transport import HostedResponsesTransport

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def verify(root,lock):
 for name,h in lock['files'].items():
  if sha(root/name)!=h:raise ValueError('FROZEN_RESOURCE_INTEGRITY_FAILURE '+name)
 # Refuse an interpreter importing a different implementation.
 for p in pathlib.Path(__file__).parent.glob('*.py'):
  if sha(p)!=lock['files'].get('src/nltlv2/'+p.name):raise ValueError('INSTALLED_SOURCE_INTEGRITY_FAILURE '+p.name)

def run_pair(project,config,transport,out,rid):
 single=copy.deepcopy(config);single.update(method='Single-shot',semantic_review=False,maximum_candidate_attempts=1);single.pop('delivery_policy',None)
 so=out/'Single-shot';so.mkdir();sr=Runner(project,single,transport,so);s=sr.run(rid)
 if not s.get('history'):return dict(requirement_id=rid,single=s,nltl=None,shared_start_equal=False)
 response=load(so/'response_001.json');request=load(so/'request_001.json')
 shared=dict(request=request,response=response,response_sha256=digest(json.dumps(response,sort_keys=True)))
 no=out/'NLTL';no.mkdir();nr=Runner(project,config,transport,no);n=nr.run(rid,shared_start=shared)
 equal=(so/'candidate_01.ttl').read_bytes()==(no/'candidate_01.ttl').read_bytes() if (no/'candidate_01.ttl').is_file() else False
 same_raw=response['text']==load(no/'shared_start.json')['response']['text'] if (no/'shared_start.json').is_file() else False
 if not equal or not same_raw:raise ValueError('SHARED_START_CANDIDATE_INTEGRITY_FAILURE')
 result=dict(requirement_id=rid,single=s,nltl=n,shared_start_equal=equal,shared_raw_equal=same_raw,initial_request_equal=request==load(no/'shared_start.json')['request'],physical_initial_generations=1)
 write(out/'pair.json',result);return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--manifest',required=True);p.add_argument('--run-id',required=True);p.add_argument('--allow-model-calls',action='store_true');a=p.parse_args()
 project=Project(a.project);m=load(project.path(a.manifest));lock=load(project.path(m['freeze_lock']));verify(project.root,lock)
 if m.get('dispatch_ready') is not True:raise ValueError('EXPERIMENT_NOT_READY')
 if not a.allow_model_calls:raise ValueError('EXPLICIT_MODEL_AUTHORIZATION_REQUIRED')
 if m['label'] not in ['HOSTED_GPT_OSS_SHARED_START_SMOKE','HOSTED_GPT_OSS_SHARED_START_DEVELOPMENT']:raise ValueError('UNSUPPORTED_EXPERIMENT_LABEL')
 out=project.output('experiments',a.run_id);write(out/'manifest.frozen.json',m);write(out/'freeze_lock.json',lock)
 start=time.monotonic();transport=None;pairs=[];errors=[];inventory=[];workflows={w:{} for w in ['Single-shot','NLTL']};queue=[]
 try:
  transport=HostedResponsesTransport(enabled=True,project_root=project.root,output=out/'provider',max_calls=m['max_physical_calls'],max_seconds=m['max_execution_seconds'],max_output_tokens_total=m['max_reserved_output_tokens'],token_limits=m['token_limits'],timeout=m['request_timeout_seconds'])
  dispatch=transport.dispatch
  def guarded(*args,**kwargs):verify(project.root,lock);return dispatch(*args,**kwargs)
  transport.dispatch=guarded
  for rid in m['requirements']:
   if rid in m.get('readiness_blockers',{}):
    queue.append(dict(requirement_id=rid,status='NOT_RUN',reason=m['readiness_blockers'][rid]));continue
   remaining=m['max_execution_seconds']-(time.monotonic()-start)
   if remaining<m['start_requirement_reserve_seconds']:
    queue.append(dict(requirement_id=rid,status='NOT_RUN',reason='INSUFFICIENT_REMAINING_TIME'));continue
   cfg=copy.deepcopy(m['config']);cfg['admission_file']=m['scope_files'][rid];dest=out/rid;dest.mkdir();write(dest/'config.json',cfg)
   # Save both logical configurations before any physical call.
   pair_start=time.monotonic();pair=run_pair(project,cfg,transport,dest,rid);pairs.append(pair)
   queue.append(dict(requirement_id=rid,status='COMPLETED',elapsed_seconds=time.monotonic()-pair_start))
   write(out/'progress.json',dict(queue=queue,physical_calls=transport.calls,elapsed_seconds=time.monotonic()-start))
   reasons=[x.get('status','') for x in [pair.get('single') or {},pair.get('nltl') or {}]]
   if any(x in ['INFRASTRUCTURE_FAILURE','REQUEST_INTEGRITY_FAILURE','RESOURCE_ATTRIBUTION_UNCERTAIN'] for x in reasons):break
 except Exception as e:
  errors.append(dict(type=type(e).__name__,diagnostic=str(e),no_retry=True));write(out/'failure.json',errors)
 finally:
  if transport:transport.close()
  for rid in m['requirements']:
   for wf in workflows:
    d=out/rid/wf
    result=load(d/'run.json') if (d/'run.json').exists() else {}
    selected=result.get('evaluation_candidate');delivery=result.get('delivery',{})
    entry=dict(shape=None,original_no_verdict=True,version=None,status=delivery.get('status','NOT_RUN' if not result else 'NO_VERDICT'),terminal_reason=result.get('status','NOT_RUN'),final_review=delivery.get('final_review'))
    for f in sorted(d.glob('candidate_*.ttl')):
     v=int(f.stem.split('_')[1]);item=dict(workflow=wf,requirement_id=rid,version=v,shape=str(f.relative_to(project.root)),sha256=sha(f),selected=v==selected)
     inventory.append(item)
     if v==selected:entry.update(shape=item['shape'],original_no_verdict=False,version=v,sha256=item['sha256'],status=delivery.get('status','ORIGINAL_SINGLE_SHOT'))
    workflows[wf][rid]=entry
  done={q['requirement_id'] for q in queue}
  queue.extend(dict(requirement_id=rid,status='NOT_RUN',reason='EARLY_TERMINAL_STOP') for rid in m['requirements'] if rid not in done)
  selection=dict(label=m['label'],workflows=workflows,dispatch_closure=str((out/'dispatch_closed.json').relative_to(project.root)),evaluation_not_consulted=True)
  write(out/'selected_outputs.json',selection);write(out/'candidate_inventory.json',inventory)
  try:verify(project.root,lock)
  except Exception as e:errors.append(dict(type=type(e).__name__,diagnostic=str(e)))
  receipt=dict(dispatch_closed=True,outstanding_provider_processes=0,selection_manifest_sha256=sha(out/'selected_outputs.json'),all_candidate_inventory_sha256=sha(out/'candidate_inventory.json'),candidate_sha256={w:{r:e.get('sha256') for r,e in entries.items()} for w,entries in workflows.items()},all_candidate_sha256={x['shape']:x['sha256'] for x in inventory},physical_calls=transport.calls if transport else 0,elapsed_seconds=time.monotonic()-start,errors=errors,queue=queue,provider_internal_queue_seconds=None,provider_model_load_seconds=None,provider_GPU_inference_seconds=None)
  write(out/'dispatch_closed.json',receipt);print(json.dumps(dict(output=str(out),**receipt)),flush=True)
 if errors:raise SystemExit(2)
if __name__=='__main__':main()
