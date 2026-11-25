from pathlib import Path
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0')
(R/'tests/test_gptoss_incomplete_16k.py').write_text('''"""Offline software controls using exact saved incomplete GPT-OSS responses."""
import unittest,pathlib,json,tempfile,copy,os,hashlib,shutil,sys,io
from unittest.mock import patch,Mock
from nltlv2.core import load,Candidate
from nltlv2.transport import HostedResponsesTransport,HOSTED_MODEL
from nltlv2.review_protocol import normalize_response,ReviewerFormatError
import nltlv2.hosted_pilot as pilot
import test_general_pipeline as gp
from test_general_pipeline import GOOD,wrap,software_admission
R=pathlib.Path(__file__).resolve().parents[1]
OLD=R/'outputs/experiments/20261124_V0111_HOSTED_GPT_OSS_SHARED_START_REPLACEMENT_SMOKE_01'

class IncompleteControls(unittest.TestCase):
 def check_object(self,obj):
  with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,{'NLTL_ALLOW_MODEL_CALLS':'YES'}):
   root=pathlib.Path(td);env=root/'external.env';env.write_text('AALTO_AI_API_KEY=FAKE_ONLY\\n');transport=HostedResponsesTransport(enabled=True,project_root=R,output=root/'provider',max_calls=1,max_seconds=60,max_output_tokens_total=16000,env_file=env)
   request=dict(route='review',system='Software test only',user='{}',model=HOSTED_MODEL,max_output_tokens=16000)
   with patch.object(transport.session,'post',return_value=Mock(status_code=200,content=json.dumps(obj).encode())):return transport.dispatch(request)
 def test_actual_saved_truncated_responses_reach_existing_validator_unchanged(self):
  for n in [3,4]:
   with self.subTest(call=n):
    original=load(OLD/'provider'/f'call_{n:03d}_response.json');obj=original['provider_response'];response=self.check_object(obj)
    self.assertEqual(response['provider_response'],obj);self.assertEqual(response['text'],original['text']);self.assertEqual(response['status'],'incomplete');self.assertEqual(response['finish_reason'],'max_output_tokens')
    with self.assertRaises(ReviewerFormatError) as e:normalize_response(response)
    self.assertEqual(e.exception.details['code'],'TRUNCATED_REVIEW')
 def test_completed_missing_final_remains_error(self):
  obj=dict(model=HOSTED_MODEL,status='completed',output=[dict(type='reasoning',content=[dict(type='reasoning_text',text='Must not become final')])])
  with self.assertRaisesRegex(RuntimeError,'HOSTED_FINAL_OUTPUT_MISSING'):self.check_object(obj)
 def test_completed_with_conflicting_length_marker_still_missing_final_error(self):
  with self.assertRaisesRegex(RuntimeError,'HOSTED_FINAL_OUTPUT_MISSING'):self.check_object(dict(model=HOSTED_MODEL,status='completed',finish_reason='max_output_tokens',output=[]))
 def test_completed_final_excludes_reasoning(self):
  obj=dict(model=HOSTED_MODEL,status='completed',output=[dict(type='reasoning',content=[dict(type='reasoning_text',text='Hidden analysis')]),dict(type='message',role='assistant',content=[dict(type='output_text',text='{}')])]);self.assertEqual(self.check_object(obj)['text'],'{}')
 def test_partial_review_is_not_accepted(self):
  obj=dict(model=HOSTED_MODEL,status='incomplete',incomplete_details=dict(reason='max_output_tokens'),output=[dict(type='message',role='assistant',content=[dict(type='output_text',text='{"decision":"ACCEPT"}')])]);response=self.check_object(obj)
  with self.assertRaises(ReviewerFormatError) as e:normalize_response(response)
  self.assertEqual(e.exception.details['code'],'TRUNCATED_REVIEW')

class BoundedBatchControls(unittest.TestCase):
 def test_exhausted_incomplete_review_continues_batch_with_same16k_correction(self):
  base=gp.GeneralPipelineTests();base.setUp()
  try:
   software_admission(base);requirements=load(base.root/'data/requirements/requirements.json');requirements['SECOND-RULE']=dict(requirements['NOVEL-RULE'],id='SECOND-RULE');base.write('data/requirements/requirements.json',requirements)
   source=pathlib.Path(pilot.__file__).parent;dest=base.root/'src/nltlv2';dest.mkdir(parents=True)
   files={}
   for p in source.glob('*.py'):
    shutil.copy2(p,dest/p.name);files['src/nltlv2/'+p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
   base.write('lock.json',dict(files=files));cfg=base.p.config('configs/nltl.json');cfg.update(model=HOSTED_MODEL,generation_max_tokens=16000,review_max_tokens=16000,maximum_candidate_attempts=2,delivery_policy='latest_technical')
   manifest=dict(label='HOSTED_GPT_OSS_SHARED_START_SMOKE',dispatch_ready=True,freeze_lock='lock.json',requirements=['NOVEL-RULE','SECOND-RULE'],scope_files={rid:'data/admissions/software.json' for rid in ['NOVEL-RULE','SECOND-RULE']},config=cfg,max_physical_calls=20,max_execution_seconds=7200,max_reserved_output_tokens=320000,token_limits={},request_timeout_seconds=180,start_requirement_reserve_seconds=1920);base.write('manifest.json',manifest)
   class Fake:
    is_live=False
    def __init__(self,**kwargs):self.calls=0;self.requests=[]
    def dispatch(self,request,latest=None,expected_findings=None):
     self.calls+=1;self.requests.append(request)
     if request['route']=='generation':return dict(text=wrap(GOOD),status='completed',usage={},elapsed_seconds=0)
     return copy.deepcopy(load(OLD/'provider'/('call_003_response.json' if request['route']=='review' else 'call_004_response.json')))
    def close(self):pass
   with patch.object(pilot,'HostedResponsesTransport',Fake),patch.object(sys,'argv',['hosted_pilot','--project',str(base.root),'--manifest','manifest.json','--run-id','SOFTWARE_BATCH_ONLY','--allow-model-calls']),patch('sys.stdout',new=io.StringIO()):pilot.main()
   batch=base.root/'outputs/experiments/SOFTWARE_BATCH_ONLY';closure=load(batch/'dispatch_closed.json');self.assertFalse(closure['errors']);self.assertEqual([q['status'] for q in closure['queue']],['COMPLETED','COMPLETED']);self.assertEqual(closure['physical_calls'],6)
   for rid in manifest['requirements']:
    result=load(batch/rid/'NLTL/run.json');self.assertEqual(result['status'],'REVIEWER_FORMAT_FAILURE');self.assertEqual(result['repair_calls'],0);self.assertIsNone(result['accepted_version']);self.assertEqual(result['delivery']['status'],'UNVERIFIED')
    first=load(batch/rid/'NLTL/request_001.json');retry=load(batch/rid/'NLTL/request_002.json');self.assertEqual(first['max_output_tokens'],16000);self.assertEqual(retry['max_output_tokens'],16000);self.assertEqual(result['auxiliary_format_retries'],1)
  finally:base.tearDown()
''')
print('Saved-response and bounded batch continuation controls added; production controller unchanged.')
