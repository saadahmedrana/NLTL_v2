import os,sys,ssl,socket,requests,pathlib,json,unittest,io,time
R=pathlib.Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261125_V0115_CONTEXT_QUESTIONS/interface_clarity';D=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION';sys.path[:0]=[str(R/'src'),str(R/'tests'),str(D/'tokenizer_runtime')]
from nltlv2.core import write
for key in ['NLTL_TEST_OUTPUT','NLTL_ALIGNMENT_EXAMPLE','NLTL_HANDOFF_EXAMPLE']:os.environ.pop(key,None)
os.environ['NLTL_TEST_PROJECT']=str(R)
def deny(*a,**kw):raise RuntimeError('NETWORK_BLOCKED_OFFLINE')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=deny
stream=io.StringIO();start=time.monotonic();suite=unittest.defaultTestLoader.discover(str(R/'tests'));result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite);(A/'offline_tests.log').write_text(stream.getvalue());summary=dict(tests=result.testsRun,new_prompt_clarity_controls=7,failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful(),network='BLOCKED',model_calls=0,benchmark_evaluation_reruns=0,elapsed_seconds=time.monotonic()-start,label='SOFTWARE_EVIDENCE_ONLY_NOT_WORKFLOW_ACCURACY');write(A/'verification.json',summary);print(json.dumps(summary));print(stream.getvalue()[-1600:]);sys.exit(not result.wasSuccessful())
