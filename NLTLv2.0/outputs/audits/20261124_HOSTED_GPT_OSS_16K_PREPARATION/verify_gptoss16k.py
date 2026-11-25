import os,sys,unittest,pathlib,ssl,requests,socket,json,io,time,hashlib,copy,tempfile
from unittest.mock import patch,Mock
R=pathlib.Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261124_HOSTED_GPT_OSS_16K_PREPARATION';D=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION';sys.path[:0]=[str(R/'src'),str(R/'tests'),str(D/'tokenizer_runtime')];os.environ['NLTL_TEST_PROJECT']=str(R)
def deny(*a,**kw):raise RuntimeError('NETWORK_BLOCKED_OFFLINE')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=deny
start=time.monotonic();suite=unittest.defaultTestLoader.discover(str(R/'tests'));out=io.StringIO();result=unittest.TextTestRunner(stream=out,verbosity=2).run(suite);(A/'offline_tests.log').write_text(out.getvalue());summary=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful(),elapsed_seconds=time.monotonic()-start,network='BLOCKED',model_calls=0);(A/'offline_tests.json').write_text(json.dumps(summary,indent=2));print(out.getvalue()[-1800:]);print(json.dumps(summary))
if not result.wasSuccessful():sys.exit(1)
from nltlv2.transport import HostedResponsesTransport
from nltlv2.core import load
from nltlv2.review_protocol import normalize_response,ReviewerFormatError
old=R/'outputs/experiments/20261124_V0111_HOSTED_GPT_OSS_SHARED_START_REPLACEMENT_SMOKE_01';replays=[]
for n in [3,4]:
 obj=load(old/'provider'/f'call_{n:03d}_response.json')['provider_response'];body=(old/'provider'/f'call_{n:03d}_response.body').read_bytes()
 with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,{'NLTL_ALLOW_MODEL_CALLS':'YES'}):
  root=pathlib.Path(td);env=root/'external.env';env.write_text('AALTO_AI_API_KEY=FAKE_ONLY\n');transport=HostedResponsesTransport(enabled=True,project_root=R,output=root/'provider',max_calls=1,max_seconds=60,max_output_tokens_total=16000,env_file=env)
  request=dict(route='review',system='Offline software interface control',user='{}',model='gpt-oss-120b',max_output_tokens=16000)
  with patch.object(transport.session,'post',return_value=Mock(status_code=200,content=body)):response=transport.dispatch(request)
  assert response['provider_response']==obj
  try:normalize_response(response);raise AssertionError('Partial review accepted')
  except ReviewerFormatError as e:assert e.details['code']=='TRUNCATED_REVIEW';error=e.details
  replays.append(dict(label='OFFLINE_EXACT_SAVED_RESPONSE_SOFTWARE_CONTROL',source_response_sha256=hashlib.sha256(body).hexdigest(),source_call=n,substantive_text_and_metadata_unchanged=True,status=response['status'],finish_reason=response['finish_reason'],final_output_present=response['final_output_present'],normalizer=error,accepted_issues=0,model_calls=0,not_a_prediction_of_16k_model_behavior=True))
(A/'saved_response_replay.json').write_text(json.dumps(replays,indent=2));print(json.dumps(replays))
