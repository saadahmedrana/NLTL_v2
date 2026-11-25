"""Generic replacement-smoke integration controls. All responses are software evidence."""
import unittest,pathlib,tempfile,json,copy,hashlib,types,importlib.util,os
from unittest.mock import patch,Mock
from nltlv2.token_budget import preflight,load_counter
from nltlv2.hosted_pilot import run_pair
from nltlv2.core import digest
import test_general_pipeline as gp
from test_general_pipeline import software_admission,wrap,GOOD

class TokenControls(unittest.TestCase):
 def payload(self):return dict(input=[dict(role='developer',content=[dict(type='input_text',text='abcdefghij')])],max_output_tokens=5)
 def test_exact_known_token_boundary(self):
  self.assertFalse(preflight(self.payload(),dict(model_context_tokens=15),len)['exceeds_known_token_limit'])
  self.assertTrue(preflight(self.payload(),dict(model_context_tokens=14),len)['exceeds_known_token_limit'])
 def test_provider_limit_takes_precedence_and_output_reserved(self):
  b=preflight(self.payload(),dict(model_context_tokens=131072,provider_context_tokens=14),len);self.assertTrue(b['exceeds_known_token_limit']);self.assertEqual(b['input_plus_output_lower_bound'],15)
 def test_unknown_framing_does_not_claim_full_count_or_trigger_arbitrary_block(self):
  b=preflight(self.payload(),dict(model_context_tokens=131072),len);self.assertFalse(b['exceeds_known_token_limit']);self.assertFalse(b['complete_provider_input_count_verified']);self.assertIsNone(b['provider_context_tokens'])
  self.assertIsNone(preflight(self.payload(),{},None)['supplied_text_tokens'])
 def test_missing_or_tampered_token_cache_is_integrity_failure(self):
  with tempfile.TemporaryDirectory() as td:
   root=pathlib.Path(td);(root/'cache').mkdir();p=root/'cache/ranks';p.write_text('wrong')
   with self.assertRaisesRegex(ValueError,'TOKENIZER_CACHE_INTEGRITY_FAILURE'):load_counter(root,dict(tiktoken_version='0.12.0',tokenizer_cache='cache',cache_files={'cache/ranks':'0'*64}))
 def test_cached_real_harmony_encoding_is_lossless_offline(self):
  R=pathlib.Path(__file__).resolve().parents[1];profile=json.loads((R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION/token_limits.verified.json').read_text());count=load_counter(R,profile)
  self.assertEqual(count('hello world'),2);self.assertGreater(count('λ = 7.00; qudt:numericValue'),0)

class InterruptedAccounting(unittest.TestCase):
 def test_scripted_preflight_failure_preserves_candidate_and_counts_only_HTTP_attempts(self):
  base=gp.GeneralPipelineTests();base.setUp()
  try:
   software_admission(base);cfg=base.p.config('configs/nltl.json');cfg.update(review_contract_version=4,maximum_candidate_attempts=2,delivery_policy='latest_technical',admission_file='data/admissions/software.json')
   class Physical:
    is_live=True
    def __init__(self):self.calls=0
    def dispatch(self,request,latest=None,expected_findings=None):
     if request['route'].startswith('review'):raise RuntimeError('SCRIPTED_LOCAL_PREFLIGHT_FAILURE')
     self.calls+=1
     return dict(text=wrap(GOOD.replace('n:bridgeWingsEnclosed','n:undeclaredBoolean')) if request['route']=='generation' else wrap(GOOD),status='completed',usage={},elapsed_seconds=0)
   t=Physical();out=base.root/'pair';out.mkdir();r=run_pair(base.p,cfg,t,out,'NOVEL-RULE')
   self.assertEqual(t.calls,2);self.assertEqual(r['single']['provider_calls']+r['nltl']['provider_calls'],2);self.assertEqual(r['nltl']['dispatch_attempts'],2);self.assertEqual(r['nltl']['candidate_attempts'],2);self.assertEqual(len(r['nltl']['history']),2);self.assertTrue(r['nltl']['history'][-1]['interrupted']);self.assertEqual(r['nltl']['delivery']['version'],2);self.assertEqual(r['nltl']['delivery']['status'],'UNVERIFIED');self.assertTrue((out/'NLTL/findings_02.json').is_file());self.assertFalse(r['nltl']['history'][-1]['accepted'])
  finally:base.tearDown()

class SymmetricEvaluation(unittest.TestCase):
 def test_scope_failure_preserves_raw_behavior_for_both_unchanged_arms(self):
  from rdflib import Graph
  R=pathlib.Path(__file__).resolve().parents[1]
  def module(name,file):
   spec=importlib.util.spec_from_file_location(name,R/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
  ev=module('independent_test','evaluation/independent.py');driver=module('hosted_eval_test','evaluation/evaluate_hosted_shared_start.py')
  shape=Graph().parse(data='@prefix sh:<http://www.w3.org/ns/shacl#>. @prefix n:<urn:software:>. n:S a sh:NodeShape;sh:targetClass n:Ship,n:Other;sh:property [sh:path n:flag;sh:hasValue true].',format='turtle')
  data=Graph().parse(data='@prefix n:<urn:software:>. n:a a n:Ship;n:flag true. n:b a n:Other;n:flag false.',format='turtle');original=set(shape);results=[]
  for wf in ['Single-shot','NLTL']:
   result,_=driver.execute_unchanged(data,shape,types.SimpleNamespace(graph=Graph()),ev,[dict(category='ADMISSION_SCOPE_ERROR',diagnostic='Extra global target')]);results.append(result)
   self.assertFalse(result['behavior']['conforms']);self.assertIsNone(result['admitted']['conforms']);self.assertFalse(result['scope_qualified']);self.assertTrue(result['scope_findings']);self.assertEqual(set(shape),original)
  self.assertEqual(results[0]['behavior']['conforms'],results[1]['behavior']['conforms'])
 def test_parse_failure_is_visible_and_not_scope_qualified(self):
  R=pathlib.Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('hosted_parse_test',R/'evaluation/evaluate_hosted_shared_start.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  x,_=m.execute_unchanged(None,None,None,None,[],parse_error='Exact original syntax error');self.assertIsNone(x['behavior']['conforms']);self.assertFalse(x['scope_qualified']);self.assertEqual(x['behavior']['error'],'Exact original syntax error')
