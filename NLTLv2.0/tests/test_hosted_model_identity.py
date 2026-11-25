"""Generic hosted identity controls; mocked responses only, no model calls."""
import json,os,pathlib,tempfile,unittest
from unittest.mock import patch,Mock
from nltlv2.transport import HostedResponsesTransport,HOSTED_MODEL
class HostedModelIdentity(unittest.TestCase):
 def create(self,root,model):
  env=root/'external.env';env.write_text('AALTO_AI_API_KEY=FAKE_ONLY\n');return HostedResponsesTransport(enabled=True,project_root=root/'project',output=root/'provider',max_calls=1,max_seconds=60,max_output_tokens_total=64,env_file=env,model=model)
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
