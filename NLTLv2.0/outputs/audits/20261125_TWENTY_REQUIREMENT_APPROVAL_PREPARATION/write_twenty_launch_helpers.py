from pathlib import Path
import json
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261125_TWENTY_REQUIREMENT_APPROVAL_PREPARATION'
(A/'seal_preparation.py').write_text('''"""Offline approval/resource seal. Never creates approval or dispatches requests."""
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
  if a.check_only:print(json.dumps(dict(status='APPROVED_RESOURCES_MATCH',requirements=20,overlap=10,model_calls=0)));return 0
  if (A/'dispatch.freeze.json').exists():raise ValueError('SEAL_ALREADY_EXISTS_NO_OVERWRITE')
  final=copy.deepcopy(lock);final['files'].update({f:sha(R/f) for f in selection['scope_files'].values()});final['files'].update(bundle['files']);final['snapshot_id']+='__APPROVAL_SEALED';write(A/'dispatch.freeze.json',final)
  ev=load(A/'evaluation_inputs.freeze.json');ev['files'].update({f:sha(R/f) for f in selection['scope_files'].values()});write(A/'evaluation_resources.lock.json',ev)
  write(A/'initial_requests.approved.json',renderings)
  for job in master['jobs']:
   m=load(R/job['manifest']);m['dispatch_ready']=True;m['scopes_pending']=[];m['authorization']='Approved scope files and frozen resources verified; experiment inference requires user launch flag.';write(R/job['dispatch_manifest'],m)
  master['dispatch_ready']=True;master['status']='APPROVAL_SEALED_UNDISPATCHED';master['source_freeze_sha256']=sha(A/'dispatch.freeze.json');master['dispatch_manifest_sha256']={j['dispatch_manifest']:sha(R/j['dispatch_manifest']) for j in master['jobs']};write(A/'experiment.dispatch.json',master)
  print(json.dumps(dict(status='SEALED_UNDISPATCHED',requirements=20,overlap=10,model_calls=0)))
 return 0
if __name__=='__main__':raise SystemExit(main())
''')
(A/'queue_receipt.py').write_text('''"""Bookkeeping for serial invocations of the existing runner; no model/evaluation route."""
import pathlib,json,sys,time
A=pathlib.Path(__file__).resolve().parent;R=A.parents[2];master=pathlib.Path(sys.argv[1]);cfg=json.loads((A/'experiment.dispatch.json').read_text());rows=[];closed=True;calls=0
for j in cfg['jobs']:
 d=R/'outputs/experiments'/j['run_id'];row=dict(model=j['model'],requirement_id=j['requirement_id'],run_id=j['run_id'],status='NOT_RUN',reason='Not started before frozen terminal/time stop')
 if d.exists():
  f=d/'dispatch_closed.json'
  if f.exists():
   c=json.loads(f.read_text());ok=c.get('dispatch_closed') is True and c.get('outstanding_provider_processes')==0;closed&=ok;row.update(status='CLOSED' if ok else 'INCOMPLETE',physical_calls=c['physical_calls'],errors=c['errors']);calls+=c['physical_calls']
  else:row.update(status='ERROR',reason='Started output has no dispatch-closure receipt');closed=False
 rows.append(row)
receipt=dict(label='FROZEN_20_10_DEVELOPMENT_QUEUE',all_started_dispatches_closed=closed,physical_calls=calls,max_physical_calls=330,queue=rows,not_run=sum(r['status']=='NOT_RUN' for r in rows),closed=sum(r['status']=='CLOSED' for r in rows),planned_pairs=30,generated_performance_consulted=False)
(master/'queue_status.json').write_text(json.dumps(receipt,indent=2)+'\\n');print(json.dumps(dict(done=receipt['closed'],not_run=receipt['not_run'],in_progress=0,physical_calls=calls,all_started_dispatches_closed=closed)),flush=True)
''')
(A/'check_pair_closure.py').write_text('''import pathlib,json,sys
R=pathlib.Path(__file__).resolve().parents[3];d=R/'outputs/experiments'/sys.argv[1];r=json.loads((d/'dispatch_closed.json').read_text());assert r['dispatch_closed'] is True and r['outstanding_provider_processes']==0
bad=bool(r['errors']);states={}
for arm in ['Single-shot','NLTL']:
 p=d/sys.argv[2]/arm/'run.json';v=json.loads(p.read_text()) if p.exists() else {};states[arm]=v.get('status','MISSING_OUTPUT');bad|=states[arm] in ['INFRASTRUCTURE_FAILURE','REQUEST_INTEGRITY_FAILURE','RESOURCE_ATTRIBUTION_UNCERTAIN','MISSING_OUTPUT']
print(json.dumps(dict(run_id=sys.argv[1],calls=r['physical_calls'],terminal_states=states,stop_remaining=bad)),flush=True)
raise SystemExit(2 if bad else 0)
''')
# This is a shell command list, not a replacement controller: each line invokes the same production Runner/evaluator.
(A/'launch_20_10.sh').write_text('''#!/usr/bin/env bash
set -euo pipefail
cd '/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0'
R="$PWD"
A="$R/outputs/audits/20261125_TWENTY_REQUIREMENT_APPROVAL_PREPARATION"
PY='/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2-env/bin/python'
export PYTHONPATH="$R/src:$R/outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION/tokenizer_runtime"
export NLTL_ENV_FILE="${NLTL_ENV_FILE:-/Users/sadisfaction570/Desktop/Journal 1/env/NLTL_v2.env}"
export NLTL_ALLOW_MODEL_CALLS=YES
"$PY" "$A/seal_preparation.py" --check-only
MASTER="$R/outputs/experiments/20261125_20_10_SHARED_START_01"
test ! -e "$MASTER"
test -f "$A/experiment.dispatch.json"
while IFS=$'\\t' read -r model rid manifest runid; do test ! -e "$R/outputs/experiments/$runid"; done < "$A/jobs.tsv"
mkdir -p "$MASTER/logs"
cp "$A/experiment.dispatch.json" "$MASTER/manifest.frozen.json"
finish() { "$PY" "$A/queue_receipt.py" "$MASTER"; }
trap finish EXIT
SECONDS=0
count=0
while IFS=$'\\t' read -r model rid manifest runid; do
  if (( 18000 - SECONDS < 600 )); then echo 'STOP: insufficient remaining dispatch allocation; remaining entries NOT_RUN'; break; fi
  echo "START $((count+1))/30 model=$model requirement=$rid done=$count in_progress=1"
  "$PY" -u -m nltlv2.hosted_pilot --project "$R" --manifest "$manifest" --run-id "$runid" --allow-model-calls 2>&1 | tee "$MASTER/logs/$runid.log"
  "$PY" "$A/check_pair_closure.py" "$runid" "$rid"
  count=$((count+1))
  "$PY" "$A/queue_receipt.py" "$MASTER"
  echo "DONE $count/30 in_progress=0"
done < "$A/jobs.tsv"
''')
(A/'evaluate_after_closure.sh').write_text('''#!/usr/bin/env bash
set -euo pipefail
cd '/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0'
R="$PWD"
A="$R/outputs/audits/20261125_TWENTY_REQUIREMENT_APPROVAL_PREPARATION"
PY='/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2-env/bin/python'
export PYTHONPATH="$R/src"
unset NLTL_ALLOW_MODEL_CALLS
MASTER="$R/outputs/experiments/20261125_20_10_SHARED_START_01"
"$PY" -c 'import json,sys; p=json.load(open(sys.argv[1])); assert p["all_started_dispatches_closed"] is True' "$MASTER/queue_status.json"
while IFS=$'\\t' read -r model rid manifest runid; do
  if test ! -d "$R/outputs/experiments/$runid"; then echo "NOT_RUN $model $rid (planned denominator retained in queue manifest)"; continue; fi
  echo "OFFLINE EVALUATION $model $rid"
  "$PY" "$R/evaluation/evaluate_hosted_shared_start.py" --project "$R" --run-id "$runid"
done < "$A/jobs.tsv"
''')
master=json.loads((A/'experiment.prepared.json').read_text());(A/'jobs.tsv').write_text(''.join('\t'.join([j['model_tag'],j['requirement_id'],j['dispatch_manifest'],j['run_id']])+'\n' for j in master['jobs']))
