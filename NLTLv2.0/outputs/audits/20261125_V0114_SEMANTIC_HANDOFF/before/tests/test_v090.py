"""Software controls only. No real-regulation witness or evaluation data."""
import unittest,json,copy,os,pathlib,hashlib
from unittest.mock import patch
from rdflib import Graph,URIRef,RDF
import test_general_pipeline as base
from nltlv2.admission import validate_declaration,load_admission,validate_data_scope,target_findings,definition_hash
from nltlv2.runner import Runner
from nltlv2.schema import Schema,N
from nltlv2.core import Candidate,offline_network_guard,write
from nltlv2.context_resolution import Resolver
def input_binding(ad,g):
 sha=hashlib.sha256(g.serialize(format='turtle').encode()).hexdigest()
 return dict(format_version=1,scope_id=ad['declaration']['admission_id'],scope_definition_sha256=definition_hash(ad['declaration']),input_sha256=sha,admitted_nodes=['urn:software:ship'],construction_provenance=dict(kind='SYNTHETIC_CONSTRUCTION_REVIEWED',references=['Synthetic software-only graph construction'])),sha
def guarded(g,schema,ad):
 if ad is None:return validate_data_scope(g,schema.graph,None)
 binding,sha=input_binding(ad,g);return validate_data_scope(g,schema.graph,ad,binding,sha)
class AdmissionControls(unittest.TestCase):
 setUp=base.GeneralPipelineTests.setUp;tearDown=base.GeneralPipelineTests.tearDown;write=base.GeneralPipelineTests.write;run_local=base.GeneralPipelineTests.run_local;accepting=base.GeneralPipelineTests.accepting
 def valid(self):
  value=base.software_admission(self);self.s=Schema(self.p);result=validate_declaration(value,self.s,'NOVEL-RULE');self.assertTrue(result['valid'],result);return value,result['context']
 def test_same_shared_initial_information(self):
  a,ta,_=self.run_local(self.accepting);b,tb,_=self.run_local(self.accepting,'Single-shot');self.assertEqual(ta.calls[0],tb.calls[0]);self.assertEqual(len(tb.calls),1);self.assertIn('admission',json.loads(ta.calls[0]['user'])['context'])
 def test_admission_full_latest_candidate_reaches_review_retry_and_repair(self):
  bad=base.GOOD.replace('sh:hasValue true','sh:hasValue true; sh:maxCount 1');seen=[]
  def handler(r,i):
   if r['route']=='generation':seen.append(base.request_data(r)['context']['admission']);return base.wrap(bad)
   body=base.request_data(r);body=body.get('original_request',body);ad=body.get('context',{}).get('admission') if r['route'].startswith('review') else body['admission'];self.assertEqual(ad,seen[0]);seen.append(ad)
   if r['route'].endswith('repair'):self.assertEqual(body['previous_candidate'],bad);self.assertEqual(body['candidate_sha256'],hashlib.sha256(bad.encode()).hexdigest());return base.wrap(base.GOOD)
   if i==2:return '{broken'
   return base.review_response(r,'REJECT',base.issue_for(r)) if body['candidate_version']==1 else base.review_response(r)
  result,t,out=self.run_local(handler);self.assertEqual(result['accepted_version'],2,result);self.assertEqual(result['auxiliary_format_retries'],1);self.assertEqual(result['repair_calls'],1)
  if os.environ.get('NLTL_TEST_OUTPUT'):
   import shutil;shutil.copytree(out,pathlib.Path(os.environ['NLTL_TEST_OUTPUT'])/'admission_complete_packets')
 def test_missing_admission_both_workflows_zero_calls(self):
  for method in ['NLTL','Single-shot']:
   result,t,_=self.run_local(self.accepting,method,cfg=dict(self.p.config('configs/'+('nltl' if method=='NLTL' else 'single_shot')+'.json'),admission_file=None));self.assertEqual(result['status'],'UNRESOLVED_ADMISSION');self.assertEqual(len(t.calls),0);self.assertIsNone(result['evaluation_candidate'])
 def test_ambiguous_and_incomplete_admission_rejected(self):
  value,_=self.valid();variants=[]
  for key,val in [('nodes',[]),('nodes',['urn:a','urn:a']),('nodes',['relative']),('owner_class',str(N.unknown)),('mode','UNRESTRICTED_FLEET')]:
   v=copy.deepcopy(value);v['focus_set'][key]=val;variants.append(v)
  for key,val in [('eligibility_assertion',None),('provenance',{}),('source_editions',[])]:v=copy.deepcopy(value);v[key]=val;variants.append(v)
  for key,val in [('edition','invented'),('sha256','0'*64),('selection_provenance','')]:v=copy.deepcopy(value);v['source_editions'][0][key]=val;variants.append(v)
  for v in variants:self.assertFalse(validate_declaration(v,self.s,'NOVEL-RULE')['valid'])
 def test_source_and_manifest_mutation_stop_before_next_call(self):
  def handler(r,i):
   (self.root/'data/admissions/software.json').write_text('{}');return base.wrap(base.GOOD)
  result,t,_=self.run_local(handler);self.assertEqual(result['status'],'REQUEST_INTEGRITY_FAILURE');self.assertEqual(len(t.calls),1)
 def test_request_admission_tampering_rejected(self):
  from nltlv2.requests import repair_request
  original=repair_request
  def tamper(*a,**k):
   r=original(*a,**k);r['payload']['admission_sha256']='tampered';r['user']=json.dumps(r['payload']);return r
  def handler(r,i):return base.wrap(base.BAD_EXTRA) if r['route']=='generation' else base.review_response(r,'REJECT',base.issue_for(r))
  with patch('nltlv2.runner.repair_request',side_effect=tamper):result,t,_=self.run_local(handler)
  self.assertEqual(result['status'],'REQUEST_INTEGRITY_FAILURE');self.assertEqual(len(t.calls),2)
 def test_data_guard_including_rdfs_inferred_unadmitted_population(self):
  _,ad=self.valid();g=Graph();g.add((URIRef('urn:software:ship'),RDF.type,N.ship));self.assertTrue(guarded(g,self.s,ad)['valid'])
  # Domain assertion types another ship; typing is not admission.
  g.add((URIRef('urn:outside'),N.bridgeWingsEnclosed,__import__('rdflib').Literal(True)));r=guarded(g,self.s,ad);self.assertFalse(r['valid']);self.assertIn('urn:outside',r['unadmitted_nodes'])
  self.assertFalse(guarded(Graph(),self.s,ad)['valid']);self.assertFalse(guarded(g,self.s,None)['valid'])
 def test_target_boundaries_and_nested_shapes(self):
  _,ad=self.valid();self.assertFalse(target_findings(Candidate(1,base.GOOD,base.GOOD),ad))
  for code in [base.GOOD.replace('n:ship','n:component'),base.GOOD.replace('sh:targetClass n:ship','sh:targetNode <urn:outside>'),base.GOOD.replace('sh:targetClass n:ship;','')]:self.assertTrue(target_findings(Candidate(1,code,code),ad))
  nested=base.GOOD+'<urn:nested> a sh:NodeShape; sh:property [sh:path n:bridgeWingsEnclosed; sh:minCount 1].';self.assertFalse(target_findings(Candidate(1,nested,nested),ad))
 def test_admission_does_not_activate_or_certify_query(self):
  from nltlv2.checks import check
  _,ad=self.valid();c=Candidate(1,base.GOOD.replace('a sh:NodeShape;','a sh:NodeShape; sh:deactivated true;'),'software raw');fs=check(c,self.s,'NOVEL-RULE',admission=ad);self.assertTrue(any(f.category=='ACTIVATION_ERROR' and f.blocking for f in fs));self.assertEqual(c.code.count('sh:deactivated true'),1)
 def test_caller_selected_edition_qualified_retrieval(self):
  v,ad=self.valid();source='data/requirements/dependency.txt';text='B1.1 Application\nB1.1.1 Synthetic population scope only.\n';(self.root/source).write_text(text);catalog=json.loads((self.root/'data/requirements/source_catalog.json').read_text());entry=dict(document_id='SOFTWARE DEPENDENCY',edition='Software edition 2',file=source,sha256=hashlib.sha256(text.encode()).hexdigest(),authority='Software test author',provenance={'kind':'Synthetic source only'});catalog['sources']['SOFTWARE DEPENDENCY']=entry;self.write('data/requirements/source_catalog.json',catalog);v['source_editions'].append({k:entry[k] for k in ['document_id','edition','file','sha256']});v['source_editions'][-1]['selection_provenance']='Explicit software test caller choice';self.s=Schema(self.p);ad=validate_declaration(v,self.s,'NOVEL-RULE')['context'];ctx=self.s.context('NOVEL-RULE');ctx['admission']=ad;r=Resolver(self.s,{})
  ctx,event=r.resolve(ctx,[dict(kind='source',reference='SOFTWARE DEPENDENCY',query='population scope',section=None,revision=None,reason='Software context request')],'NOVEL-RULE');self.assertEqual(event['entries'][0]['status'],'RETRIEVED_CALLER_SELECTED_EDITION');self.assertIn('not a finding',event['entries'][0]['edition_compatibility'])
 def test_pending_live_template_never_dispatches(self):
  self.write('data/admissions/pending.json',{}) if (self.root/'data/admissions').exists() else None
  result,t,_=self.run_local(self.accepting,cfg=dict(self.p.config('configs/nltl.json'),admission_file='data/admissions/pending.json'));self.assertEqual(result['status'],'UNRESOLVED_ADMISSION');self.assertEqual(len(t.calls),0)

 def test_target_node_data_identifiers_and_owner_checks(self):
  from nltlv2.checks import check
  v,ad=self.valid();node=str(N)+'callerSpecificRecord';code=base.GOOD.replace('sh:targetClass n:ship','sh:targetNode <'+node+'>');fs=check(Candidate(1,code,code),self.s,'NOVEL-RULE',admission=ad);self.assertFalse(any(f.category=='CANONICAL_IDENTIFIER_ERROR' for f in fs));self.assertTrue(target_findings(Candidate(1,code,code),ad))
 def test_unknown_editions_and_missing_authority_not_invented(self):
  v,_=self.valid();catalog=json.loads((self.root/'data/requirements/source_catalog.json').read_text());catalog['sources']['Synthetic source document for software testing'].pop('authority');self.write('data/requirements/source_catalog.json',catalog);self.s=Schema(self.p);self.assertFalse(validate_declaration(v,self.s,'NOVEL-RULE')['valid'])
 def test_input_declaration_does_not_contain_regulatory_answer(self):
  v,ad=self.valid();self.assertNotIn('expected',json.dumps(ad));self.assertNotIn('hasValue',json.dumps(ad));self.assertEqual(ad['policy']['interpretation'],'A');self.assertTrue(ad['policy']['caller_attestation_is_not_independent_certification'])
 def test_evaluation_guard_is_separate_and_refuses_unadmitted_data(self):
  import importlib.util
  project=pathlib.Path(os.environ.get('NLTL_TEST_PROJECT',str(pathlib.Path(__file__).resolve().parents[1])))
  spec=importlib.util.spec_from_file_location('admission_independent_control',project/'evaluation/independent.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  from rdflib import Literal
  v,ad=self.valid();g=Graph();g.add((URIRef('urn:software:ship'),RDF.type,N.ship));g.add((URIRef('urn:software:ship'),N.bridgeWingsEnclosed,Literal(True)));shape=Graph().parse(data=base.GOOD,format='turtle')
  binding,sha=input_binding(ad,g)
  result,report=module.validate_admitted_graph(g,shape,self.s,'NOVEL-RULE',v,binding,sha);self.assertTrue(result['conforms']);self.assertIsNotNone(report)
  result,report=module.validate_admitted_graph(g,shape,self.s,'NOVEL-RULE',{});self.assertIsNone(result['conforms']);self.assertIsNone(report)
  g.add((URIRef('urn:outside'),RDF.type,N.ship));binding,sha=input_binding(ad,g);result,report=module.validate_admitted_graph(g,shape,self.s,'NOVEL-RULE',v,binding,sha);self.assertIsNone(result['conforms']);self.assertIsNone(report)

 def test_missing_admission_does_not_construct_live_transport_or_read_credentials(self):
  import sys,io,contextlib
  from nltlv2.cli import main
  args=['nltl','--project',str(self.root),'run','--config','configs/nltl.json','--requirement','NOVEL-RULE','--experiment-id','missing_admission','--allow-model-calls']
  with patch.object(sys,'argv',args),patch('nltlv2.transport.LiveTransport',side_effect=AssertionError('credentials must not be read')),contextlib.redirect_stdout(io.StringIO()):main()
  result=json.loads((self.root/'outputs/experiments/missing_admission/run.json').read_text());self.assertEqual(result['status'],'UNRESOLVED_ADMISSION');self.assertEqual(result['provider_calls'],0)
 def test_caller_admission_supports_reviewed_activation_repair_without_selector(self):
  inactive=base.GOOD.replace('a sh:NodeShape;','a sh:NodeShape; sh:deactivated true;')
  def handler(r,i):
   if r['route']=='generation':return base.wrap(inactive)
   if r['route'].endswith('repair'):
    self.assertEqual(r['payload']['previous_candidate'],inactive);self.assertEqual(base.request_data(r)['admission']['declaration']['eligibility_assertion'],'ASSUMED_EXTERNAL_RESEARCH_ELIGIBILITY');return base.wrap(base.GOOD)
   body=base.request_data(r)
   if body['candidate_version']==1:
    issue=base.issue_for(r);issue.update(issue_id='inactive-root',candidate_excerpt='sh:deactivated true',reason='The represented source obligation is disabled despite explicit caller population admission',expected='Active constraint inside the supplied population',suggestion='Remove deactivation only after source-grounded review; preserve full query obligations',evidence_excerpt='ASSUMED_EXTERNAL_RESEARCH_ELIGIBILITY');issue.pop('evidence_id',None)
    obj=json.loads(base.review_response(r,'REJECT',issue));obj['context_assessments']=[dict(finding_key=f['finding_key'],disposition='REPAIRABLE_CODE',source_excerpt=body['context']['source_documents'][0]['text'],candidate_excerpt='sh:deactivated true',evidence_excerpt='ASSUMED_EXTERNAL_RESEARCH_ELIGIBILITY',reason='Caller has supplied external eligibility; declared class supplies representation identity, not legal qualification') for f in body['acceptance_blockers']];return json.dumps(base.bind_review_response(r,obj))
   return base.review_response(r)
  result,t,out=self.run_local(handler);self.assertEqual(result['accepted_version'],2,result);self.assertEqual(result['repair_calls'],1);self.assertNotIn('polarClass',json.dumps(t.calls));self.assertEqual((out/'candidate_01.ttl').read_text(),inactive)
 def test_explicit_reference_conflicting_with_caller_edition_is_unresolved(self):
  v,ad=self.valid();catalog=json.loads((self.root/'data/requirements/source_catalog.json').read_text());catalog['sources']['Synthetic source document for software testing']['revision']=1;self.write('data/requirements/source_catalog.json',catalog);self.s=Schema(self.p);ctx=self.s.context('NOVEL-RULE');ctx['admission']=ad;resolver=Resolver(self.s,{})
  _,event=resolver.resolve(ctx,[dict(kind='source',reference='SOFTWARE SOURCE',revision=2,section=None,query='Application scope',reason='Software reference conflict')],'NOVEL-RULE');self.assertEqual(event['entries'][0]['status'],'CALLER_EDITION_REFERENCE_CONFLICT')
