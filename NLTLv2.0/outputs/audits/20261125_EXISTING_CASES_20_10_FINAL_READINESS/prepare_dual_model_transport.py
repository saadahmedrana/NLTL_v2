from pathlib import Path
import json,hashlib,shutil
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261125_EXISTING_CASES_20_10_FINAL_READINESS';A.mkdir(exist_ok=False);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for n in ['src/nltlv2/transport.py','src/nltlv2/hosted_pilot.py']:
 p=A/'before'/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(R/n,p)
protected={str(p.relative_to(R)):sha(p) for dn in ['outputs/experiments','results','data','schema','evaluation','prompts','configs','docs'] for p in (R/dn).rglob('*') if p.is_file() and '__pycache__' not in p.parts};(A/'protected_before.json').write_text(json.dumps(protected))
p=R/'src/nltlv2/transport.py';s=p.read_text().replace("HOSTED_MODEL='gpt-oss-120b'","HOSTED_MODEL='gpt-oss-120b'\nHOSTED_MODELS=(HOSTED_MODEL,'gpt-5.5-2026-04-24')")
s=s.replace('timeout=180,env_file=None,token_limits=None,token_counter=None):','timeout=180,env_file=None,token_limits=None,token_counter=None,model=HOSTED_MODEL):')
s=s.replace("  import dotenv,requests\n  p=pathlib.Path(env_file", "  if model not in HOSTED_MODELS:raise ValueError('UNSUPPORTED_HOSTED_MODEL')\n  self.expected_model=model\n  import dotenv,requests\n  p=pathlib.Path(env_file")
s=s.replace("if request['model']!=HOSTED_MODEL:raise ValueError('PROVIDER_MODEL_INTEGRITY_FAILURE')","if request['model']!=self.expected_model:raise ValueError('PROVIDER_MODEL_INTEGRITY_FAILURE')")
s=s.replace("returned==HOSTED_MODEL else 'MISMATCH'","returned==self.expected_model else 'MISMATCH'")
s=s.replace("returned!=HOSTED_MODEL:raise ValueError('PROVIDER_MODEL_INTEGRITY_FAILURE')","returned!=self.expected_model:raise ValueError('PROVIDER_MODEL_INTEGRITY_FAILURE')")
p.write_text(s)
p=R/'src/nltlv2/hosted_pilot.py';s=p.read_text();needle="max_output_tokens_total=m['max_reserved_output_tokens'],token_limits=m['token_limits'],timeout=m['request_timeout_seconds'])";assert needle in s;s=s.replace(needle,"max_output_tokens_total=m['max_reserved_output_tokens'],token_limits=m['token_limits'],timeout=m['request_timeout_seconds'],model=m['config']['model'])");p.write_text(s)
(R/'tests/test_hosted_model_identity.py').write_text('''"""Generic hosted identity controls; mocked responses only, no model calls."""
import json,os,pathlib,tempfile,unittest
from unittest.mock import patch,Mock
from nltlv2.transport import HostedResponsesTransport,HOSTED_MODEL
class HostedModelIdentity(unittest.TestCase):
 def create(self,root,model):
  env=root/'external.env';env.write_text('AALTO_AI_API_KEY=FAKE_ONLY\\n');return HostedResponsesTransport(enabled=True,project_root=root/'project',output=root/'provider',max_calls=1,max_seconds=60,max_output_tokens_total=64,env_file=env,model=model)
 def request(self,model):return dict(route='generation',system='Generic software check',user='No source or evaluation input',model=model,max_output_tokens=64)
 def response(self,model):return Mock(status_code=200,content=json.dumps(dict(model=model,status='completed',output=[dict(type='message',role='assistant',content=[dict(type='output_text',text='OK')])],usage=dict(input_tokens=7,output_tokens=1,total_tokens=8))).encode())
 @patch.dict(os.environ,{'NLTL_ALLOW_MODEL_CALLS':'YES'})
 def test_explicit_model_preserved_and_not_filled_when_missing(self):
  for returned in ['gpt-5.5-2026-04-24',None]:
   with tempfile.TemporaryDirectory() as td:
    t=self.create(pathlib.Path(td),'gpt-5.5-2026-04-24')
    with patch.object(t.session,'post',return_value=self.response(returned)) as post:r=t.dispatch(self.request('gpt-5.5-2026-04-24'))
    self.assertEqual(json.loads(post.call_args.kwargs['data'])['model'],'gpt-5.5-2026-04-24');self.assertEqual(r['returned_model'],returned);self.assertEqual(r['identity_status'],'UNKNOWN' if returned is None else 'MATCH');t.close()
 @patch.dict(os.environ,{'NLTL_ALLOW_MODEL_CALLS':'YES'})
 def test_different_or_unknown_model_never_falls_back(self):
  with tempfile.TemporaryDirectory() as td:
   t=self.create(pathlib.Path(td),'gpt-5.5-2026-04-24')
   with patch.object(t.session,'post') as post:
    with self.assertRaisesRegex(ValueError,'MODEL_INTEGRITY'):t.dispatch(self.request(HOSTED_MODEL))
    post.assert_not_called()
   with patch.object(t.session,'post',return_value=self.response(HOSTED_MODEL)):
    with self.assertRaisesRegex(ValueError,'MODEL_INTEGRITY'):t.dispatch(self.request('gpt-5.5-2026-04-24'))
   self.assertEqual(t.calls,1);t.close()
  with tempfile.TemporaryDirectory() as td:
   with self.assertRaisesRegex(ValueError,'UNSUPPORTED_HOSTED_MODEL'):self.create(pathlib.Path(td),'unverified-model')
''')
print('MINIMAL_DUAL_MODEL_IDENTITY_ADAPTER; no inference')
