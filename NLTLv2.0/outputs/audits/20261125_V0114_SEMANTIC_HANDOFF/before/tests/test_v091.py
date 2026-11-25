"""Admission leakage/interface controls, not regulatory compliance witnesses."""
import unittest,json,copy,pathlib,os,sys
from unittest.mock import patch
import test_general_pipeline as base
from test_v090 import input_binding
from nltlv2.admission import validate_declaration,validate_data_scope,target_findings
from nltlv2.schema import Schema,N
from nltlv2.core import Candidate
from rdflib import Graph,URIRef,RDF
class ScopeIsolationControls(unittest.TestCase):
 setUp=base.GeneralPipelineTests.setUp;tearDown=base.GeneralPipelineTests.tearDown;write=base.GeneralPipelineTests.write;run_local=base.GeneralPipelineTests.run_local;accepting=base.GeneralPipelineTests.accepting
 def test_no_input_id_or_counterpart_access_any_route(self):
  (self.root/'evaluation/input_binding.json').write_text(json.dumps(dict(case_id='CASE_CANARY_8f1',admitted_nodes=['urn:FIXTURE_CANARY_8f1'],label='LABEL_CANARY_8f1',counterpart='COUNTERPART_CANARY_8f1')))
  enabled=[True];forbidden=self.root/'evaluation'
  def audit(event,args):
   if enabled[0] and event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
    p=pathlib.Path(os.fsdecode(args[0])).resolve()
    if p==forbidden or p.is_relative_to(forbidden):raise AssertionError('PRODUCTION_OPENED_EVALUATION')
  sys.addaudithook(audit)
  def handler(r,i):
   if r['route']=='generation':return base.wrap(base.BAD_EXTRA)
   if r['route'].endswith('repair'):return base.wrap(base.GOOD)
   if i==2:return '{invalid'
   body=base.request_data(r);body=body.get('original_request',body)
   return base.review_response(r,'REJECT',base.issue_for(r)) if body['candidate_version']==1 else base.review_response(r)
  try:result,t,out=self.run_local(handler)
  finally:enabled[0]=False
  self.assertEqual(result['accepted_version'],2,result);routes=[r['route'] for r in t.calls];self.assertIn('review_format_retry',routes);self.assertIn('targeted_repair',routes)
  for r in t.calls:
   text=json.dumps(r)
   for canary in ['CASE_CANARY_8f1','FIXTURE_CANARY_8f1','LABEL_CANARY_8f1','COUNTERPART_CANARY_8f1']:self.assertNotIn(canary,text)
   body=base.request_data(r);body=body.get('original_request',body);ad=body.get('context',{}).get('admission') if r['route'] in ['generation','review','review_format_retry'] else body['admission'];self.assertEqual(set(ad['declaration']['focus_set']),{'mode','owner_class'})
  if os.environ.get('NLTL_TEST_OUTPUT'):
   import shutil;shutil.copytree(out,pathlib.Path(os.environ['NLTL_TEST_OUTPUT'])/'scope_isolation_complete_packets')
 def test_input_binding_or_legacy_identity_declaration_cannot_generate(self):
  value=base.software_admission(self);self.s=Schema(self.p)
  old=copy.deepcopy(value);old['format_version']=1;old['focus_set']['nodes']=['urn:EXTERNAL_CASE_NODE']
  g=Graph();g.add((URIRef('urn:software:ship'),RDF.type,N.ship));ad=validate_declaration(value,self.s,'NOVEL-RULE')['context'];binding,_=input_binding(ad,g)
  for obj in [old,binding]:
   self.write('data/admissions/wrong.json',obj)
   result,t,_=self.run_local(self.accepting,cfg=dict(self.p.config('configs/nltl.json'),admission_file='data/admissions/wrong.json'));self.assertEqual(result['status'],'UNRESOLVED_ADMISSION');self.assertEqual(len(t.calls),0)
 def test_proposed_or_unattributed_scope_not_approved(self):
  value=base.software_admission(self);self.s=Schema(self.p)
  for status in ['PROPOSED','PENDING_APPROVAL','REJECTED',None]:
   v=copy.deepcopy(value);v['approval']['status']=status;self.assertFalse(validate_declaration(v,self.s,'NOVEL-RULE')['valid'])
  v=copy.deepcopy(value);v['approval']['approved_by']=None;self.assertFalse(validate_declaration(v,self.s,'NOVEL-RULE')['valid'])
 def test_evaluation_binding_required_hash_bound_and_scope_bound(self):
  value=base.software_admission(self);self.s=Schema(self.p);ad=validate_declaration(value,self.s,'NOVEL-RULE')['context'];g=Graph();g.add((URIRef('urn:software:ship'),RDF.type,N.ship));binding,sha=input_binding(ad,g)
  self.assertFalse(validate_data_scope(g,self.s.graph,ad)['valid']);self.assertTrue(validate_data_scope(g,self.s.graph,ad,binding,sha)['valid'])
  for key,val in [('input_sha256','0'*64),('scope_id','wrong'),('scope_definition_sha256','0'*64),('admitted_nodes',[]),('construction_provenance',{})]:
   b=copy.deepcopy(binding);b[key]=val;self.assertFalse(validate_data_scope(g,self.s.graph,ad,b,sha)['valid'])
 def test_external_identity_cannot_be_required_as_shape_target(self):
  value=base.software_admission(self);self.s=Schema(self.p);ad=validate_declaration(value,self.s,'NOVEL-RULE')['context'];code=base.GOOD.replace('sh:targetClass n:ship','sh:targetNode <urn:external:fixture>');fs=target_findings(Candidate(1,code,code),ad);self.assertTrue(fs);self.assertIn('declared owner_class',fs[0].expected)
