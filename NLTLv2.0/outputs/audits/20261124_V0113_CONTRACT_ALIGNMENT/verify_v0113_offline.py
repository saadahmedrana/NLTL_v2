import os,sys,ssl,socket,requests,pathlib,json,time,io,unittest
R=pathlib.Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261124_V0113_CONTRACT_ALIGNMENT';D=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION';sys.path[:0]=[str(R/'src'),str(R/'tests'),str(D/'tokenizer_runtime')]
from nltlv2.core import Project,write
os.environ['NLTL_TEST_PROJECT']=str(R);os.environ['NLTL_ALIGNMENT_EXAMPLE']=str(A)
def deny(*a,**kw):raise RuntimeError('NETWORK_BLOCKED_OFFLINE')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=deny
start=time.monotonic();stream=io.StringIO();suite=unittest.defaultTestLoader.discover(str(R/'tests'));result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite);(A/'offline_tests.log').write_text(stream.getvalue());summary=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful(),network='BLOCKED',model_calls=0,evaluation_reruns=0,label='SCRIPTED_SOFTWARE_EVIDENCE_ONLY',elapsed_seconds=time.monotonic()-start);write(A/'offline_verification.json',summary);print(stream.getvalue()[-2500:]);print(json.dumps(summary));sys.exit(not result.wasSuccessful())
