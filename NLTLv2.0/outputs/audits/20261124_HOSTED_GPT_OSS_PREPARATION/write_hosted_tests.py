from pathlib import Path
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0')
(R/'tests/test_hosted_shared_start.py').write_text('''"""Generic offline software controls; no regulatory candidates or model calls."""
import unittest,tempfile,pathlib,json,copy,os,hashlib
from unittest.mock import patch,Mock
from nltlv2.transport import HostedResponsesTransport,HOSTED_MODEL,final_assistant_text
from nltlv2.delivery import finalize
from nltlv2.hosted_pilot import run_pair
from nltlv2.core import digest,write
from test_general_pipeline import GeneralPipelineTests,software_admission,LocalTransport,wrap,GOOD,BAD_EXTRA,review_response,issue_for

class HostedControls(unittest.TestCase):
 def response(self,**kw):
  obj=dict(model=HOSTED_MODEL,status='completed',output=[dict(type='reasoning',content=[dict(type='output_text',text='PRIVATE REASONING')]),dict(type='message',role='assistant',content=[dict(type='output_text',text='FINAL')])],usage=dict(input_tokens=17,output_tokens=5));obj.update(kw);return obj
 def transport(self,root,max_calls=2):
  env=root/'external.env';env.write_text('AALTO_AI_API_KEY=FAKE_ONLY\\nAALTO_AI_RESPONSES_URL=https://ai-api-v2.aalto.fi/v1/responses\\n')
  return HostedResponsesTransport(enabled=True,project_root=root/'project',output=root/'provider',max_calls=max_calls,max_seconds=100,max_output_tokens_total=200,max_request_bytes=110000,env_file=env)
 def request(self):return dict(route='generation',system='system',user='source only',model=HOSTED_MODEL,max_output_tokens=50)
 def test_typed_final_excludes_reasoning_and_nonfinal(self):
  obj=self.response();obj['output'].append(dict(type='message',role='assistant',channel='analysis',content=[dict(type='output_text',text='BAD')]))
  self.assertEqual(final_assistant_text(obj),'FINAL');self.assertEqual(final_assistant_text(dict(output_text='AMBIGUOUS')),'')
 @patch.dict(os.environ,{'NLTL_ALLOW_MODEL_CALLS':'YES'})
 def test_protocol_raw_usage_unknown_identity_no_fallback(self):
  with tempfile.TemporaryDirectory() as td:
   root=pathlib.Path(td);t=self.transport(root);obj=self.response(model=None);raw=json.dumps(obj).encode();http=Mock(status_code=200,content=raw)
   with patch.object(t.session,'post',return_value=http) as post:r=t.dispatch(self.request())
   self.assertEqual(r['text'],'FINAL');self.assertIsNone(r['returned_model']);self.assertEqual(r['identity_status'],'UNKNOWN');self.assertEqual(r['usage'],obj['usage']);self.assertEqual((root/'provider/call_001_response.body').read_bytes(),raw)
   kw=post.call_args.kwargs;self.assertFalse(kw['allow_redirects']);payload=json.loads(kw['data']);self.assertEqual(payload['input'][0]['role'],'developer');self.assertEqual(payload['truncation'],'disabled');self.assertNotIn('FAKE_ONLY',(root/'provider/call_001_request.json').read_text())
 @patch.dict(os.environ,{'NLTL_ALLOW_MODEL_CALLS':'YES'})
 def test_mismatched_model_terminal_and_preserved(self):
  with tempfile.TemporaryDirectory() as td:
   root=pathlib.Path(td);t=self.transport(root);obj=self.response(model='different')
   with patch.object(t.session,'post',return_value=Mock(status_code=200,content=json.dumps(obj).encode())):
    with self.assertRaisesRegex(ValueError,'MODEL_INTEGRITY'):t.dispatch(self.request())
   self.assertTrue((root/'provider/call_001_response.json').exists());self.assertEqual(t.calls,1)
 @patch.dict(os.environ,{'NLTL_ALLOW_MODEL_CALLS':'YES'})
 def test_physical_call_cap_no_retry_and_closed_boundary(self):
  with tempfile.TemporaryDirectory() as td:
   root=pathlib.Path(td);t=self.transport(root,max_calls=1)
   with patch.object(t.session,'post',return_value=Mock(status_code=503,content=b'Unavailable')) as post:
    with self.assertRaisesRegex(RuntimeError,'HTTP_503'):t.dispatch(self.request())
    with self.assertRaisesRegex(RuntimeError,'CALL_LIMIT'):t.dispatch(self.request())
    self.assertEqual(post.call_count,1)
   t.close()
   with self.assertRaisesRegex(RuntimeError,'DISPATCH_CLOSED'):t.dispatch(self.request())
 @patch.dict(os.environ,{'NLTL_ALLOW_MODEL_CALLS':'YES'})
 def test_context_limit_no_silent_truncation(self):
  with tempfile.TemporaryDirectory() as td:
   t=self.transport(pathlib.Path(td));q=self.request();q['user']='x'*110001
   with patch.object(t.session,'post') as post:
    with self.assertRaisesRegex(RuntimeError,'NO_TRUNCATION'):t.dispatch(q)
    post.assert_not_called();self.assertEqual(t.calls,0)
 @patch.dict(os.environ,{'NLTL_ALLOW_MODEL_CALLS':'YES'})
 def test_refusal_or_reasoning_only_never_candidate(self):
  with tempfile.TemporaryDirectory() as td:
   root=pathlib.Path(td);t=self.transport(root);obj=self.response(output=[dict(type='reasoning',content=[dict(type='output_text',text='not final')])])
   with patch.object(t.session,'post',return_value=Mock(status_code=200,content=json.dumps(obj).encode())):
    with self.assertRaisesRegex(RuntimeError,'FINAL_OUTPUT_MISSING'):t.dispatch(self.request())
   self.assertTrue((root/'provider/call_001_response.body').exists())

class DeliveryControls(unittest.TestCase):
 def rows(self,root):
  rows=[]
  for v,code in [(1,'original'),(2,'revision')]:
   (root/f'candidate_{v:02d}.ttl').write_text(code);rows.append(dict(version=v,sha256=digest(code),accepted=False,review=dict(decision='REJECT'),findings=[dict(message='unresolved')],technical=dict(qualifies=True)))
  return rows
 def test_latest_qualifying_is_unverified_rejected_not_approved(self):
  with tempfile.TemporaryDirectory() as td:
   root=pathlib.Path(td);rows=self.rows(root);d=finalize(root,rows,'ATTEMPT_LIMIT_EXHAUSTED');self.assertEqual((d['version'],d['status'],d['final_review']),(2,'UNVERIFIED','REJECT'));self.assertEqual(d['findings'],rows[1]['findings'])
 def test_bad_last_revision_falls_back_without_acceptance_relaxation(self):
  with tempfile.TemporaryDirectory() as td:
   root=pathlib.Path(td);rows=self.rows(root);rows[1]['technical']['qualifies']=False;rows[0]['review']=None;d=finalize(root,rows,'REVIEWER_FORMAT_FAILURE');self.assertEqual((d['version'],d['status'],d['final_review']),(1,'UNVERIFIED','HUMAN_REVIEW_REQUIRED'))
 def test_no_qualifier_and_integrity_never_deliver(self):
  with tempfile.TemporaryDirectory() as td:
   root=pathlib.Path(td);rows=self.rows(root)
   for h in rows:h['technical']['qualifies']=False
   self.assertEqual(finalize(root,rows,'REJECTED')['status'],'NO_VERDICT');rows[0]['technical']['qualifies']=True;self.assertIsNone(finalize(root,rows,'REQUEST_INTEGRITY_FAILURE')['version'])
 def test_stale_candidate_detected(self):
  with tempfile.TemporaryDirectory() as td:
   root=pathlib.Path(td);rows=self.rows(root);(root/'candidate_02.ttl').write_text('manual edit')
   with self.assertRaisesRegex(ValueError,'INTEGRITY'):finalize(root,rows,'REJECTED')
 def test_accepted_handoff_and_infrastructure_distinct(self):
  with tempfile.TemporaryDirectory() as td:
   root=pathlib.Path(td);rows=self.rows(root);rows[1]['accepted']=True;rows[1]['review']['decision']='ACCEPT';self.assertEqual(finalize(root,rows,'ACCEPTED')['final_review'],'APPROVE');rows[1]['accepted']=False;rows[1]['review']=None;d=finalize(root,rows,'INFRASTRUCTURE_FAILURE');self.assertEqual(d['status'],'UNVERIFIED');self.assertEqual(d['terminal_reason'],'INFRASTRUCTURE_FAILURE')

class PairControls(unittest.TestCase):
 def setUp(self):
  self.base=GeneralPipelineTests();self.base.setUp();software_admission(self.base);self.root=self.base.root
 def tearDown(self):self.base.tearDown()
 def config(self):
  cfg=self.base.p.config('configs/nltl.json');cfg.update(maximum_candidate_attempts=2,delivery_policy='latest_technical',admission_file='data/admissions/software.json');return cfg
 def test_shared_start_exact_bytes_with_actual_scripted_repair(self):
  def handler(q,n):
   if q['route']=='generation':return wrap(BAD_EXTRA)
   if q['route'].endswith('repair'):return wrap(GOOD)
   return review_response(q,'REJECT',issue_for(q)) if 'sh:maxCount' in json.loads(q['user'])['full_candidate'] else review_response(q)
  t=LocalTransport(handler);out=self.root/'pair';out.mkdir();r=run_pair(self.base.p,self.config(),t,out,'NOVEL-RULE')
  self.assertTrue(r['shared_start_equal']);self.assertTrue(r['initial_request_equal']);self.assertEqual(sum(q['route']=='generation' for q in t.calls),1);self.assertEqual(r['nltl']['repair_calls'],1);self.assertEqual(r['nltl']['delivery']['status'],'ACCEPTED');self.assertEqual((out/'Single-shot/candidate_01.ttl').read_bytes(),(out/'NLTL/candidate_01.ttl').read_bytes());self.assertEqual((out/'Single-shot/candidate_01.ttl').read_text(),BAD_EXTRA)
 def test_failed_review_no_repair_and_unverified_delivery(self):
  def handler(q,n):return wrap(GOOD) if q['route']=='generation' else 'invalid JSON'
  t=LocalTransport(handler);out=self.root/'pair';out.mkdir();r=run_pair(self.base.p,self.config(),t,out,'NOVEL-RULE')
  self.assertEqual(r['nltl']['repair_calls'],0);self.assertEqual(r['nltl']['delivery']['status'],'UNVERIFIED');self.assertEqual(r['nltl']['delivery']['final_review'],'HUMAN_REVIEW_REQUIRED');self.assertEqual(len(t.calls),3)
''')
print('Generic hosted/shared-start/delivery controls written.')
