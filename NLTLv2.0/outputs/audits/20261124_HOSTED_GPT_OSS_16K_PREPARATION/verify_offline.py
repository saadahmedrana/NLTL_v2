import os,sys,ssl,socket,requests,pathlib,json,hashlib,time,io,unittest
R=pathlib.Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261124_HOSTED_GPT_OSS_16K_PREPARATION';D=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION';sys.path[:0]=[str(A/'runtime/src'),str(R/'tests'),str(D/'tokenizer_runtime')]
from nltlv2.core import Project,stamp,write
for name,h in json.loads((A/'freeze_lock.json').read_text())['files'].items():assert hashlib.sha256((R/name).read_bytes()).hexdigest()==h,('FROZEN_SOURCE_CHANGED',name)
O=Project(R).output('audits','OFFLINE_GPTOSS16K_'+stamp());os.environ['NLTL_TEST_PROJECT']=str(R)
def deny(*a,**kw):raise RuntimeError('NETWORK_BLOCKED_OFFLINE')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=deny
start=time.monotonic();stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.discover(str(R/'tests')));(O/'offline_tests.log').write_text(stream.getvalue());summary=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful(),network='BLOCKED',model_calls=0,elapsed_seconds=time.monotonic()-start,output=str(O));write(O/'summary.json',summary);print(stream.getvalue()[-1800:]);print(json.dumps(summary));sys.exit(not result.wasSuccessful())
