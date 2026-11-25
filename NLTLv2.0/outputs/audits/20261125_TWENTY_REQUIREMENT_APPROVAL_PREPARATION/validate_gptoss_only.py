"""User-run offline resume command; invokes the existing frozen evaluator unchanged."""
import pathlib,json,subprocess,sys,os,time,datetime,fcntl,hashlib
A=pathlib.Path(__file__).resolve().parent;R=A.parents[2]
load=lambda p:json.loads(p.read_text())
def stamp():return datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
def main():
 lock=(A/'gptoss_validation_only.lock').open('a')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise SystemExit('Another GPT-OSS validation command is already running; no duplicate launched.')
 receipt=load(R/'outputs/experiments/20261125_20_10_SHARED_START_01/queue_status.json')
 assert receipt['all_started_dispatches_closed'] is True,'Provider dispatch closure required'
 jobs=[j for j in load(A/'experiment.dispatch.json')['jobs'] if j['model_tag']=='GPTOSS'];assert len(jobs)==20
 status={j['requirement_id']:'PENDING' for j in jobs};logs=A/'gptoss_validation_logs';logs.mkdir(exist_ok=True)
 def update(current=None):
  for j in jobs:
   if (R/'outputs/experiments'/j['run_id']/'evaluation/evaluation_complete.json').exists():status[j['requirement_id']]='COMPLETE'
  s=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),model='gpt-oss-120b',completed=sum(v=='COMPLETE' for v in status.values()),total=20,current=current,requirements=status,model_calls=0,GPT55_untouched=True)
  p=A/'gptoss_validation_status.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(s,indent=2)+'\n');tmp.replace(p);return s
 def existing(runid):
  result=subprocess.run(['ps','-A','-o','pid=,args='],capture_output=True,text=True,check=True)
  return [line.split(None,1)[0] for line in result.stdout.splitlines() if 'evaluate_hosted_shared_start.py' in line and '--run-id '+runid in line and str(R) in line]
 before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for j in jobs for p in (R/'outputs/experiments'/j['run_id']/'evaluation').glob('*.json') if (p.parent/'evaluation_complete.json').exists()}
 errors=[];update()
 for j in jobs:
  rid=j['requirement_id'];runid=j['run_id'];directory=R/'outputs/experiments'/runid;done=directory/'evaluation/evaluation_complete.json'
  if done.exists():print(f'SKIP {rid}: completed results preserved',flush=True);continue
  while existing(runid):
   status[rid]='WAITING_FOR_EXISTING_EVALUATOR';s=update(rid);print(f'[{s["completed"]}/20 complete] WAIT {rid}: existing evaluator still running; no duplicate',flush=True);time.sleep(15)
  if done.exists():update();print(f'COMPLETE {rid}: existing evaluator finished',flush=True);continue
  e=directory/'evaluation'
  if e.exists():
   archive=directory/('evaluation.unfinished_preserved.'+stamp());e.rename(archive);print(f'PRESERVED unfinished evaluation at {archive}',flush=True)
  status[rid]='RUNNING';s=update(rid);log=logs/(runid+'.'+stamp()+'.log');print(f'[{s["completed"]}/20 complete] RUN {rid}; log={log}',flush=True)
  env=os.environ.copy();env.pop('NLTL_ALLOW_MODEL_CALLS',None);env['PYTHONPATH']=str(R/'src')
  with log.open('x') as out:result=subprocess.run([sys.executable,str(R/'evaluation/evaluate_hosted_shared_start.py'),'--project',str(R),'--run-id',runid],cwd=R,env=env,stdout=out,stderr=subprocess.STDOUT)
  if result.returncode or not done.exists():status[rid]='EVALUATION_FAILED_OR_INCOMPLETE';errors.append(dict(requirement_id=rid,exit_code=result.returncode,log=str(log)));print(f'ERROR {rid}: evaluation incomplete; preserved log={log}',flush=True)
  else:status[rid]='COMPLETE';print(f'COMPLETE {rid}',flush=True)
  update()
 for name,h in before.items():assert hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()==h,'Completed evaluation modified: '+name
 final=update();final['errors']=errors;final['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();(A/'gptoss_validation_command_result.json').write_text(json.dumps(final,indent=2)+'\n');print(json.dumps(final,indent=2),flush=True)
 return 2 if errors else 0
if __name__=='__main__':raise SystemExit(main())
