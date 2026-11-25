"""General software controls only. No regulatory compliance witnesses or model calls."""
import copy,hashlib,importlib.util,json,pathlib,unittest,os
import test_general_pipeline as base
from nltlv2.core import Candidate,digest,offline_network_guard
from nltlv2.evidence import evidence_catalog,code_location,extract_location,assert_review_packet
from nltlv2.requests import parse_review,review_conflicts,assert_integrity,review_base
from nltlv2.review_validation import validate_review
from nltlv2.checks import check,sparql_checks
from nltlv2.schema import Schema,N,Q
from nltlv2.tracking import Tracker
from rdflib import Graph

class FocusedControls(unittest.TestCase):
 setUp=base.GeneralPipelineTests.setUp;tearDown=base.GeneralPipelineTests.tearDown;write=base.GeneralPipelineTests.write;run_local=base.GeneralPipelineTests.run_local;accepting=base.GeneralPipelineTests.accepting
 def test_local_ids_bind_immutable_provenance(self):
  ctx=self.s.context('NOVEL-RULE');catalog=evidence_catalog(ctx)
  self.assertEqual([e['evidence_id'] for e in catalog['entries']],['E'+str(i) for i in range(1,len(catalog['entries'])+1)])
  for e in catalog['entries']:
   self.assertEqual(e['text_sha256'],digest(e['text']));self.assertEqual(len(e['evidence_sha256']),64);self.assertEqual(len(e['provenance_sha256']),64)
  changed=copy.deepcopy(ctx);changed['source_documents'][0]['sha256']='different';self.assertNotEqual(catalog['catalog_sha256'],evidence_catalog(changed)['catalog_sha256'])
 def test_ranges_extract_indented_unicode_literal_exactly(self):
  c=Candidate(3,'α\n    "7.0"^^<urn:decimal>\n','');loc=code_location(c,2,2,unit='lines');self.assertEqual(extract_location(loc,c),'    "7.0"^^<urn:decimal>\n');self.assertEqual(extract_location(code_location(c,2,len(c.code)),c),c.code[2:])
 def test_stale_bool_out_of_bounds_and_changed_code_rejected(self):
  c=Candidate(1,base.GOOD,'');loc=code_location(c,1,2)
  for key,val in [('candidate_version',2),('candidate_version',True),('candidate_sha256','0'*64),('start',-1),('end',len(c.code)+1),('start',True),('unit','bytes')]:
   bad=dict(loc,**{key:val})
   with self.assertRaises(ValueError):extract_location(bad,c)
  with self.assertRaises(ValueError):extract_location(loc,Candidate(1,c.code+' ',''))
 def test_span_only_review_repair_recheck_and_immutable_retry(self):
  first=[]
  def handler(r,i):
   wire=json.loads(r['user'])
   if r['route']=='generation':return base.wrap(base.BAD_EXTRA)
   if r['route'].endswith('repair'):
    self.assertEqual(r['payload']['previous_candidate'],base.BAD_EXTRA);assert_integrity(r,Candidate(1,base.BAD_EXTRA,''),None)
    self.assertEqual(json.dumps(wire).count(json.dumps(base.BAD_EXTRA)[1:-1]),1)
    return base.wrap(base.GOOD)
   self.assertNotIn('source_documents',wire['context']);self.assertNotIn('original_request',wire);self.assertNotIn('static_warnings',wire);self.assertNotIn('acceptance_blockers',wire)
   self.assertEqual(json.dumps(wire).count(json.dumps(wire['full_candidate'])[1:-1]),1)
   if wire['candidate_version']==1:
    if r['route']=='review':first.append(copy.deepcopy(wire))
    else:self.assertEqual(review_base(wire),first[0]);self.assertNotIn('raw_previous_response',wire);self.assertEqual(wire['prior_issues'],[])
    obj=json.loads(base.review_response(r,'REJECT',base.issue_for(r)))
    self.assertNotIn('candidate_excerpt',obj['issues'][0]);self.assertIn('candidate_location',obj['issues'][0])
    if r['route']=='review':obj['issues'][0]['evidence_id']='UNKNOWN'
    return json.dumps(obj)
   obj=json.loads(base.review_response(r));self.assertTrue(obj['change_assessments']);self.assertNotIn('removal_assessments',obj['change_assessments'][0]);return json.dumps(obj)
  result,t,out=self.run_local(handler);self.assertEqual(result['accepted_version'],2,result);self.assertEqual(result['repair_calls'],1);self.assertEqual(result['auxiliary_format_retries'],1)
  self.assertEqual(len(result['history'][0]['findings']),2) # one nonblocking representation notice, one validated interpretation
  if os.environ.get('NLTL_TEST_OUTPUT'):
   import shutil;shutil.copytree(out,pathlib.Path(os.environ['NLTL_TEST_OUTPUT'])/'complete_review_retry_repair_recheck')
 def test_unknown_evidence_and_altered_asserted_source_do_not_authorize_repair(self):
  def handler(r,i):
   if r['route']=='generation':return base.wrap(base.BAD_EXTRA)
   obj=json.loads(base.review_response(r,'REJECT',base.issue_for(r)));obj['issues'][0]['source_excerpt']='Invented legal claim';obj['issues'][0]['evidence_id']='E999999';return json.dumps(obj)
  result,t,out=self.run_local(handler);self.assertEqual(result['status'],'REVIEWER_FORMAT_FAILURE');self.assertEqual(result['repair_calls'],0);self.assertIsNone(result['history'][0]['review'])
 def test_no_model_code_indentation_is_required(self):
  def handler(r,i):
   if r['route']=='generation':return base.wrap(base.BAD_EXTRA)
   obj=json.loads(base.review_response(r,'REJECT',base.issue_for(r)));self.assertNotIn('candidate_excerpt',obj['issues'][0]);return json.dumps(obj)
  cfg=self.p.config('configs/nltl.json');cfg['maximum_candidate_attempts']=1
  result,t,out=self.run_local(handler,cfg=cfg);self.assertEqual(result['status'],'ATTEMPT_LIMIT_EXHAUSTED');self.assertIsNotNone(result['history'][0]['review'])
 def test_meta_shacl_rejects_unreachable_malformed_shape(self):
  code=base.GOOD+'<urn:orphan> a sh:PropertyShape; sh:path n:bridgeWingsEnclosed; sh:minCount "oops".'
  findings=check(Candidate(1,code,''),self.s,'NOVEL-RULE');struct=[f for f in findings if f.category=='SHACL_STRUCTURE_ERROR'];self.assertEqual(len(struct),1);self.assertTrue(struct[0].blocking);self.assertIn('sh:minCount',struct[0].diagnostic);self.assertIn('oops',struct[0].diagnostic)
 def test_standard_property_constraint_does_not_invent_value_prebinding(self):
  q='SELECT $this WHERE { { SELECT ?this WHERE { ?this <urn:p> ?v } } }'
  code=base.GOOD+'<urn:property> a sh:PropertyShape; sh:path n:bridgeWingsEnclosed; sh:sparql [sh:select """'+q+'"""].'
  self.assertFalse(any('nested_prebound' in f.check_id for f in check(Candidate(1,code,''),self.s,'NOVEL-RULE')))
 def test_custom_validator_value_and_supplied_parameter_prebinding(self):
  q='SELECT $this WHERE { { SELECT ?this WHERE { ?this <urn:p> ?v } } }'
  code=base.GOOD+'<urn:component> a sh:ConstraintComponent; sh:parameter [ sh:path <urn:threshold> ]; sh:validator <urn:validator>. <urn:validator> a sh:SPARQLSelectValidator; sh:select """'+q+'""". <urn:shape> <urn:threshold> 1.'
  findings=check(Candidate(1,code,''),self.s,'NOVEL-RULE');nested=[f for f in findings if 'nested_prebound' in f.check_id];self.assertTrue(nested);self.assertIn('value',nested[0].message);self.assertIn('threshold',nested[0].message)
 def test_ask_has_no_outer_select_projection_requirement(self):
  self.assertFalse(any('outer_projection' in f.check_id for f in sparql_checks(Candidate(1,'',''),'ASK { $this <urn:p> ?v }',value_prebound=True)))
 def test_property_and_operand_path_roles(self):
  self.write('schema/representation_bindings.json',{'requirements':{'NOVEL-RULE':{'terms':['probeLength'],'owners':{'probeLength':'ship'},'target_owner':'ship','model_paths':[]}}});schema=Schema(self.p);prop=str(N.probeLength);operand=[prop,schema.quantity_profile['numeric_predicate']]
  def conflicts(path,role):return review_conflicts({'issues':[dict(property=prop,proposed_path=path,proposed_path_role=role)]},schema,'NOVEL-RULE')
  self.assertFalse(conflicts([prop],'PROPERTY'));self.assertFalse(conflicts(operand,'NUMERIC_OPERAND'));self.assertTrue(conflicts(operand,'PROPERTY'));self.assertTrue(conflicts(operand+['urn:wrong'],'NUMERIC_OPERAND'))
 def test_uncertain_binding_remains_warning(self):
  fs=sparql_checks(Candidate(1,'',''),'SELECT $this WHERE { $this <urn:p> ?v . FILTER(?missing>0) }');self.assertTrue(fs);self.assertTrue(all(not f.blocking and not f.confirmed for f in fs))
 def test_retry_packet_tampering_detected(self):
  def handler(r,i):
   if r['route']=='generation':return base.wrap(base.GOOD)
   wire=json.loads(r['user']);bad=copy.deepcopy(wire);bad['full_candidate']+=' '
   with self.assertRaises(ValueError):assert_review_packet(bad,Candidate(1,base.GOOD,''))
   return base.review_response(r)
  result,t,out=self.run_local(handler);self.assertEqual(result['accepted_version'],1)
 def test_dispatch_closure_is_bound_to_selection_and_candidates(self):
  file=pathlib.Path(__file__).resolve().parents[1]/'evaluation/independent.py';spec=importlib.util.spec_from_file_location('focused_evaluation',file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  selection={'workflows':{'NLTL':{'NOVEL-RULE':{'shape':'candidate.ttl'}}}};self.write('selection.json',selection);(self.root/'candidate.ttl').write_text(base.GOOD)
  with self.assertRaisesRegex(ValueError,'DISPATCH_CLOSURE_REQUIRED'):module.require_dispatch_closure(self.p,'selection.json')
  selection['dispatch_closure']='closed.json';self.write('selection.json',selection);receipt={'dispatch_closed':True,'selection_manifest_sha256':hashlib.sha256((self.root/'selection.json').read_bytes()).hexdigest(),'candidate_sha256':{'NLTL':{'NOVEL-RULE':digest(base.GOOD)}}};self.write('closed.json',receipt)
  self.assertEqual(module.require_dispatch_closure(self.p,'selection.json'),selection)
  (self.root/'candidate.ttl').write_text(base.GOOD+' ')
  with self.assertRaisesRegex(ValueError,'CANDIDATE_INTEGRITY'):module.require_dispatch_closure(self.p,'selection.json')

 def test_meta_stage_never_executes_submitted_queries(self):
  from unittest.mock import patch
  query='SELECT $this WHERE { SERVICE <https://example.invalid/data> { $this <urn:p> ?v } }'
  code=base.PREFIX+'<urn:s> a sh:NodeShape; sh:targetNode <urn:focus>; sh:sparql [sh:select """'+query+'"""].'
  with patch('rdflib.Graph.query',side_effect=AssertionError('Submitted query must not execute during Meta-SHACL')):
   findings=check(Candidate(1,code,''),self.s,'NOVEL-RULE')
  self.assertFalse(any(f.category=='SHACL_STRUCTURE_ERROR' for f in findings));self.assertTrue(any('External dataset' in f.message for f in findings))
