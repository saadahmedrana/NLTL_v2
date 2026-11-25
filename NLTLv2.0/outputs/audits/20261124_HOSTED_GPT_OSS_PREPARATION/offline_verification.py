import os,sys,unittest,pathlib,ssl,requests,socket,json,io,time
R=pathlib.Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');sys.path[:0]=[str(R/'src'),str(R/'tests')];os.environ['NLTL_TEST_PROJECT']=str(R)
from nltlv2.core import Project,stamp
lock=json.loads((R/'outputs/audits/20261124_HOSTED_GPT_OSS_PREPARATION/freeze_lock.json').read_text())
import hashlib
for name,h in lock['files'].items():assert hashlib.sha256((R/name).read_bytes()).hexdigest()==h,('FROZEN_SOURCE_CHANGED',name)
A=Project(R).output('audits','OFFLINE_HOSTED_CHECK_'+stamp())
print('NEW_OFFLINE_OUTPUT '+str(A),flush=True)
def denied(*a,**kw):raise RuntimeError('NETWORK_BLOCKED_OFFLINE')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=denied
start=time.monotonic();suite=unittest.defaultTestLoader.discover(str(R/'tests'));stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite);(A/'offline_tests.log').write_text(stream.getvalue());(A/'offline_tests.json').write_text(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful(),elapsed_seconds=time.monotonic()-start,network='BLOCKED',model_calls=0),indent=2));print(stream.getvalue()[-4000:]);print((A/'offline_tests.json').read_text());sys.exit(not result.wasSuccessful())
