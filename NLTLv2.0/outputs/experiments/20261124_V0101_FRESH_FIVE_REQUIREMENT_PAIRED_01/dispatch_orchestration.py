import pathlib,json,hashlib,os,sys,subprocess,shutil,datetime,re,time
R=pathlib.Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');P=R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL';M=json.loads((P/'pilot_manifest.json').read_text());OUT=R/M['batch_output'];START=time.monotonic()
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def frozen():
 for f,h in load(P/'frozen_resource_hashes.json').items():assert sha(R/f)==h,'FROZEN_RESOURCE_CHANGED '+f
assert 'SUMMARY tests=214 failures=0 errors=0 model_calls=0' in pathlib.Path('/tmp/nltl_fresh_pilot_offline_tests.log').read_text()
assert not OUT.exists();assert sum(j['max_provider_calls'] for j in M['jobs'])==55
frozen();assert os.environ['PYTHONPATH']==str(P/'runtime')
pre=subprocess.run([sys.executable,'-B',str(P/'offline_preflight.py')],capture_output=True,text=True,check=True)
from dotenv import dotenv_values
cred=dotenv_values('/Users/sadisfaction570/Desktop/Journal 1/env/NLTL_v2.env');assert cred.get('AALTO_RESPONSES_BASE_URL','').rstrip('/')==M['destination'],'DESTINATION_MISMATCH';assert cred.get('AALTO_API_KEY'),'MISSING_PROVIDER_KEY';del cred
before={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts}
OUT.mkdir();write(OUT/'protected_before.json',before);shutil.copy2(P/'pilot_manifest.json',OUT/'pilot_manifest.frozen.json');shutil.copy2('/tmp/nltl_fresh_pilot_offline_tests.log',OUT/'offline_tests.log');write(OUT/'offline_preflight.json',dict(returncode=pre.returncode,stdout=pre.stdout,stderr=pre.stderr));write(OUT/'offline_harness_correction.json',dict(initial_command='Original offline test command installed the socket-class guard before ssl import.',initial_result='9 test-module import errors, no tests exercised; zero provider calls.',exact_error="TypeError: function() argument 'code' must be code, not str",correction='Preload ssl and unittest.mock before entering the unchanged existing offline_network_guard.',pipeline_changed=False,corrected_result='214 tests, failures=0, errors=0, model_calls=0'))
write(OUT/'dispatch_authorization.json',dict(user_instruction='u can run them  now',reference='Current conversation user authorization following the exact offline/live commands and configured 55-call limits.',recorded_at=now(),manifest_sha256=sha(P/'pilot_manifest.json'),destination=M['destination'],model=M['model'],maximum_provider_calls=55,no_extra_jobs_or_retries=True))
shutil.copy2('/tmp/nltl_run_authorized_five_pilot.py',OUT/'dispatch_orchestration.py')
env=dict(os.environ,NLTL_ENV_FILE='/Users/sadisfaction570/Desktop/Journal 1/env/NLTL_v2.env',NLTL_ALLOW_MODEL_CALLS='YES',PYTHONDONTWRITEBYTECODE='1');jobs=[];failure=None
try:
 for job in M['jobs']:
  frozen();assert not (R/job['output']).exists();job_start=time.monotonic();print('START '+job['requirement_id']+' '+job['workflow'],flush=True)
  command=[sys.executable,'-B','-m','nltlv2.cli','--project',str(R),'run','--config',job['config'],'--requirement',job['requirement_id'],'--experiment-id',job['experiment_id'],'--allow-model-calls']
  with (OUT/(job['experiment_id']+'.stdout.log')).open('w') as stdout,(OUT/(job['experiment_id']+'.stderr.log')).open('w') as stderr:
   completed=subprocess.run(command,env=env,stdout=stdout,stderr=stderr)
  row=dict(requirement_id=job['requirement_id'],workflow=job['workflow'],output=job['output'],returncode=completed.returncode,elapsed_seconds=time.monotonic()-job_start,closed_at=now())
  resultfile=R/job['output']/'run.json'
  if resultfile.exists():
   result=load(resultfile);row.update(status=result['status'],provider_calls=result['provider_calls'],accepted_version=result['accepted_version'],candidate_attempts=result['candidate_attempts']);assert result['provider_calls']<=job['max_provider_calls']
   initial=R/job['output']/'request_001.json'
   if initial.exists():assert load(initial)==load(R/job['initial_request']),'ACTUAL_INITIAL_REQUEST_DRIFT'
  else:row['status']='CLI_FAILURE_NO_RUN_RESULT'
  jobs.append(row);write(OUT/'dispatch_progress.json',jobs);print('DONE '+json.dumps(row),flush=True)
  assert completed.returncode==0,'CLI_FAILURE_NO_RETRY'
  frozen()
except Exception as e:
 failure=dict(type=type(e).__name__,message=str(e),at=now(),no_retry=True);write(OUT/'dispatch_operational_failure.json',failure)
finally:
 # Seal selection BEFORE importing any independent evaluator or consulting outcome labels.
 inventory=[];workflows={wf:{} for wf in ['NLTL','Single-shot']};counts={};initial_payloads={};metrics=[]
 from nltlv2.transport import provider_payload
 for job in M['jobs']:
  d=R/job['output'];result=load(d/'run.json') if (d/'run.json').exists() else {};history={h['version']:h for h in result.get('history',[])};accepted=next((h['version'] for h in result.get('history',[]) if h.get('accepted') is True),None)
  selected=accepted if job['workflow']=='NLTL' and result.get('status')=='ACCEPTED' else result.get('evaluation_candidate') if job['workflow']=='Single-shot' else None
  selected_path=d/f'candidate_{selected:02d}.ttl' if selected is not None else None
  if selected_path is not None and not selected_path.is_file():selected=None;selected_path=None
  entry=dict(original_no_verdict=selected is None,selected_version=selected,selection_basis='FIRST_INTERNAL_ACCEPTANCE' if selected is not None and job['workflow']=='NLTL' else 'SOLE_SINGLE_SHOT_DELIVERY' if selected is not None else 'NO_VERDICT',terminal_reason=result.get('status','NOT_DISPATCHED_AFTER_BATCH_STOP'))
  if selected_path is not None:entry.update(shape=str(selected_path.relative_to(R)),sha256=sha(selected_path))
  workflows[job['workflow']][job['requirement_id']]=entry
  counts.setdefault(job['workflow'],{})[job['requirement_id']]=entry.get('sha256')
  for f in sorted(d.glob('candidate_*.ttl')):
   version=int(f.stem.split('_')[-1]);h=history.get(version,{});findings=d/f'findings_{version:02d}.json';inv=dict(requirement_id=job['requirement_id'],workflow=job['workflow'],version=version,shape=str(f.relative_to(R)),sha256=sha(f),selected=version==selected,label='SELECTED_INTERNAL_ACCEPTANCE' if version==selected and job['workflow']=='NLTL' else 'SELECTED_SINGLE_SHOT_DELIVERY' if version==selected else 'REJECTED_CANDIDATE_DIAGNOSTICS',candidate_status=h.get('status','CHECKING_ABORTED_OR_NO_HISTORY'),run_terminal_reason=entry['terminal_reason'],history_row=h,findings_file=str(findings.relative_to(R)) if findings.exists() else None,findings_unavailable_reason=None if findings.exists() else 'Single-shot has no review/check findings by design' if job['workflow']=='Single-shot' else result.get('operational_failure',{'reason':'Checking aborted before findings were saved'}));assert not h.get('sha256') or h['sha256']==inv['sha256'];inventory.append(inv)
  attempt_files=[f for f in d.glob('request_*.json') if re.fullmatch(r'request_\d{3}\.json',f.name)];assert len(attempt_files)<=job['max_provider_calls']
  if attempt_files:
   ad=d/'actual_provider_payloads';ad.mkdir(exist_ok=False)
   for requestfile in sorted(attempt_files):
    request=load(requestfile);write(ad/requestfile.name,provider_payload(request));responsefile=d/requestfile.name.replace('request_','response_');response=load(responsefile) if responsefile.exists() else {};sizes=load(d/(requestfile.stem+'_sizes.json'));metrics.append(dict(requirement_id=job['requirement_id'],workflow=job['workflow'],sequence=requestfile.stem,route=request['route'],rendered_bytes=sizes['rendered_bytes'],usage=response.get('usage',{}),provider_elapsed_seconds=response.get('elapsed_seconds',0),response_received=responsefile.exists(),request_sha256=sha(requestfile),response_sha256=sha(responsefile) if responsefile.exists() else None))
   initial_payloads.setdefault(job['requirement_id'],{})[job['workflow']]=load(d/'request_001.json')
  assert len(metrics)<=55
 for rid,arms in initial_payloads.items():
  if len(arms)==2:assert arms['NLTL']==arms['Single-shot']
 write(OUT/'candidate_inventory.json',inventory);write(OUT/'call_metrics.json',metrics)
 selection=dict(workflows=workflows,dispatch_closure=str((OUT/'dispatch_closed.json').relative_to(R)),research_scopes=M['scope_files'],admissions=M['evaluation']['bindings'],requirements=M['requirements'],excluded_case_ids={'NLTL':[],'Single-shot':[]},deferred=['I2-042'],selection_frozen_before_evaluation=True,first_internal_acceptance_only=True)
 write(OUT/'selected_outputs.json',selection)
 closure=dict(dispatch_closed=True,closed_at=now(),selection_manifest_sha256=sha(OUT/'selected_outputs.json'),candidate_sha256=counts,all_candidate_inventory_sha256=sha(OUT/'candidate_inventory.json'),all_candidate_sha256={x['shape']:x['sha256'] for x in inventory},manifest_sha256=sha(P/'pilot_manifest.json'),jobs=jobs,batch_failure=failure,provider_call_attempts=len(metrics),maximum_provider_calls=55,outstanding_provider_processes=0,no_additional_dispatch=True,elapsed_seconds=time.monotonic()-START)
 write(OUT/'dispatch_closed.json',closure);changed=[k for k,h in before.items() if not (R/k).is_file() or sha(R/k)!=h];write(OUT/'preservation_after_dispatch.json',dict(status='PASS' if not changed else 'FAIL',protected_files=len(before),modified_or_deleted=changed));assert not changed,changed
 print('DISPATCH_CLOSED '+json.dumps(dict(output=str(OUT),calls=len(metrics),candidates=len(inventory),elapsed_seconds=closure['elapsed_seconds'],failure=failure)),flush=True)
