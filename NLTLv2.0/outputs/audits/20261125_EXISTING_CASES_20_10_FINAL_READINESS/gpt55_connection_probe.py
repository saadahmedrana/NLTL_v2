from pathlib import Path
import sys,json,os,hashlib,time
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261125_EXISTING_CASES_20_10_FINAL_READINESS';D=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION';sys.path[:0]=[str(R/'src'),str(D/'tokenizer_runtime')]
from nltlv2.transport import HostedResponsesTransport
from nltlv2.hosted_pilot import verify
from nltlv2.token_budget import load_counter
from nltlv2.core import write
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();load=lambda p:json.loads(p.read_text())
v=load(A/'verification.json');assert v['success'] and v['tests']==313
old=load(R/'outputs/audits/20261125_IDENTIFIER_ROUTING_AND_20_10_READINESS/pipeline.freeze.json');names=set(old['files'])|{str(p.relative_to(R)) for p in (R/'src/nltlv2').glob('*.py')}|{'tests/test_hosted_model_identity.py'};lock=dict(snapshot_id='V0115_HOSTED_MODEL_IDENTITY_20261125_TESTED_313',version='0.11.5',tests=313,files={n:sha(R/n) for n in sorted(names)});write(A/'pipeline.freeze.json',lock);verify(R,lock)
limits=load(R/'outputs/audits/20261125_V0115_CONTEXT_QUESTIONS/diagnostic.prepared.json')['token_limits'];limits.update(encoding='o200k_base',model_context_tokens=1050000,model_context_reference='https://developers.openai.com/api/docs/models/gpt-5.5',provider_limit_evidence='Provider catalog advertises deployment; deployed limits and framing unknown',count_contract='Pinned public o200k_base text count; deployed provider tokenizer/framing are unverified. No truncation.')
write(A/'gpt55_token_capacity.prepared.json',limits);counter=load_counter(R,limits)
req=dict(route='generation',model='gpt-5.5-2026-04-24',system='Connection check only. Return the requested short text.',user='Reply exactly CONNECTION_OK.',max_output_tokens=512)
write(A/'connection_probe.request.frozen.json',req);assert not (A/'gpt55_connection_probe').exists(),'No repeat connection probe'
os.environ['NLTL_ALLOW_MODEL_CALLS']='YES';os.environ.setdefault('NLTL_ENV_FILE','/Users/sadisfaction570/Desktop/Journal 1/env/NLTL_v2.env');started=time.monotonic();t=None;result=None
try:
 t=HostedResponsesTransport(enabled=True,project_root=R,output=A/'gpt55_connection_probe',max_calls=1,max_seconds=45,max_output_tokens_total=512,timeout=30,token_limits=limits,token_counter=counter,model=req['model']);response=t.dispatch(req);result=dict(status='CONNECTION_VERIFIED' if response.get('status')=='completed' and response['text'].strip()=='CONNECTION_OK' and response.get('identity_status')=='MATCH' else 'CONNECTION_OR_IDENTITY_NOT_FULLY_VERIFIED',endpoint='https://ai-api-v2.aalto.fi/v1/responses',requested_model=req['model'],returned_model=response.get('returned_model'),identity_status=response.get('identity_status'),provider_status=response.get('status'),final_text=response['text'],usage=response.get('usage'),elapsed_seconds=response['elapsed_seconds'])
except Exception as e:result=dict(status='CONNECTION_FAILED_NO_RETRY',error_type=type(e).__name__,diagnostic=str(e))
finally:
 if t:t.close()
 result.update(label='TRANSPORT_ONLY_NO_REQUIREMENT_OR_EVALUATION_INPUT_NOT_EXPERIMENT_INFERENCE',provider_calls=0 if t is None else t.calls,max_calls=1,elapsed_total_seconds=time.monotonic()-started,requirements_sent=[],candidates_sent=False,evaluation_sent=False,main_experiment_dispatched=False,no_retry=True);write(A/'connection_probe.result.json',result);verify(R,lock)
print(json.dumps(result,indent=2))
