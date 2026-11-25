import os,sys,unittest,pathlib,ssl,requests,socket,json,io,time,hashlib,tempfile
from unittest.mock import patch,Mock
R=pathlib.Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION';sys.path[:0]=[str(R/'src'),str(R/'tests'),str(A/'tokenizer_runtime')];os.environ['NLTL_TEST_PROJECT']=str(R)
def denied(*a,**kw):raise RuntimeError('NETWORK_BLOCKED_OFFLINE')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=denied
start=time.monotonic();suite=unittest.defaultTestLoader.discover(str(R/'tests'));stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite);(A/'offline_tests.log').write_text(stream.getvalue());summary=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful(),elapsed_seconds=time.monotonic()-start,network='BLOCKED',model_calls=0);(A/'offline_tests.json').write_text(json.dumps(summary,indent=2));print(stream.getvalue()[-2000:]);print(json.dumps(summary))
if not result.wasSuccessful():sys.exit(1)
# Interface-only replay: deliver the exact previously blocked request through a fake HTTP session.
from nltlv2.transport import HostedResponsesTransport
from nltlv2.core import Candidate,load
P=R/'outputs/experiments/20261124_V0110_HOSTED_GPT_OSS_SHARED_START_SMOKE_01/I2-005/NLTL';request=load(P/'request_002.json');code=(P/'candidate_02.ttl').read_text();candidate=Candidate(2,code,code);profile=load(A/'token_limits.verified.json')
with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,{'NLTL_ALLOW_MODEL_CALLS':'YES'}):
 root=pathlib.Path(td);env=root/'external.env';env.write_text('AALTO_AI_API_KEY=FAKE_ONLY\n');dest=root/'provider'
 t=HostedResponsesTransport(enabled=True,project_root=R,output=dest,max_calls=1,max_seconds=60,max_output_tokens_total=4000,env_file=env,token_limits=profile)
 fake=dict(model='gpt-oss-120b',status='completed',output=[dict(type='message',role='assistant',content=[dict(type='output_text',text='SOFTWARE_INTERFACE_ACK_NOT_A_REVIEW')])],usage={})
 with patch.object(t.session,'post',return_value=Mock(status_code=200,content=json.dumps(fake).encode())) as post:
  response=t.dispatch(request,candidate);sent=post.call_args.kwargs['data'];obj=json.loads(sent);assert json.loads(obj['input'][1]['content'][0]['text'])['full_candidate']==candidate.code;assert len(sent)==140705
 record=dict(label='OFFLINE_SOFTWARE_INTERFACE_ONLY_NO_MODEL_REVIEW',saved_request_sha256=hashlib.sha256((P/'request_002.json').read_bytes()).hexdigest(),exact_payload_bytes=len(sent),payload_sha256=hashlib.sha256(sent).hexdigest(),complete_saved_candidate_delivered=True,candidate_sha256=candidate.sha256,token_budget=response['token_budget'],fake_HTTP_attempts=1,actual_provider_calls=0,substantive_review_validated=False,source_truncated=False)
 (A/'previous_blocked_packet_delivery_control.json').write_text(json.dumps(record,indent=2));(A/'previous_blocked_packet.complete_request.body').write_bytes(sent)
 print(json.dumps(record))
