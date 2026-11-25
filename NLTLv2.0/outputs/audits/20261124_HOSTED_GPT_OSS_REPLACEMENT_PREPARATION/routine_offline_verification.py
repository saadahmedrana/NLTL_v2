import os,sys,unittest,pathlib,ssl,requests,socket,json,io,time,hashlib,tempfile
from unittest.mock import patch,Mock
R=pathlib.Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION';sys.path[:0]=[str(R/'src'),str(R/'tests'),str(A/'tokenizer_runtime')];os.environ['NLTL_TEST_PROJECT']=str(R)
def denied(*a,**kw):raise RuntimeError('NETWORK_BLOCKED_OFFLINE')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=denied
from nltlv2.core import Project,stamp
for name,h in json.loads((A/'freeze_lock.json').read_text())['files'].items():assert hashlib.sha256((R/name).read_bytes()).hexdigest()==h,('FROZEN_SOURCE_CHANGED',name)
O=Project(R).output('audits','OFFLINE_HOSTED_V0111_'+stamp());print('NEW_OFFLINE_OUTPUT '+str(O),flush=True)
start=time.monotonic();suite=unittest.defaultTestLoader.discover(str(R/'tests'));stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite);(O/'offline_tests.log').write_text(stream.getvalue());summary=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful(),elapsed_seconds=time.monotonic()-start,network='BLOCKED',model_calls=0);(O/'offline_tests.json').write_text(json.dumps(summary,indent=2));print(stream.getvalue()[-2000:]);print(json.dumps(summary))
if not result.wasSuccessful():sys.exit(1)
