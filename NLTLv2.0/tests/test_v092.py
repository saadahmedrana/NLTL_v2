"""Generic reviewer-interface controls only; no regulatory compliance witnesses."""
import copy,json,unittest,os,pathlib
from rdflib import URIRef,Literal,XSD
import test_general_pipeline as base
from nltlv2.core import Candidate,GenerationProject,digest
from nltlv2.requests import parse_review,ReviewerFormatError
from nltlv2.review_validation import validate_review
from nltlv2.evidence import evidence_catalog,citation_error,ground_fact,review_binding,assert_review_packet,probe_summary
class EvidenceControls(unittest.TestCase):
 setUp=base.GeneralPipelineTests.setUp;tearDown=base.GeneralPipelineTests.tearDown;write=base.GeneralPipelineTests.write;run_local=base.GeneralPipelineTests.run_local;accepting=base.GeneralPipelineTests.accepting
 def control(self,triple=None):
  ctx=self.s.context('NOVEL-RULE')
  if triple:ctx['ontology_evidence']=[triple]
  c=Candidate(1,base.BAD_EXTRA,'');request={'user':json.dumps(dict(context=ctx,full_candidate=c.code,candidate_version=1,previous_candidate=None,change_manifest={'changes':[]},prior_issues=[]))};obj=json.loads(base.review_response(request,'REJECT',base.issue_for(request)));return c,ctx,request,obj
 def parse(self,c,ctx,obj):return parse_review({'text':json.dumps(obj)},c,ctx)
 def test_valid_id_citations_and_stable_ids(self):
  c,ctx,request,obj=self.control();self.assertTrue(self.parse(c,ctx,obj)[1]);self.assertEqual(evidence_catalog(ctx),evidence_catalog(copy.deepcopy(ctx)));self.assertEqual(evidence_catalog(ctx)['catalog_sha256'],evidence_catalog(dict(reversed(list(ctx.items()))))['catalog_sha256'])
 def fact_control(self,text):
  c,ctx,r,obj=self.control(['<urn:s>','<urn:p>',text]);fact=next(e for e in evidence_catalog(ctx)['entries'] if e['kind']=='RDF_FACT');obj['issues'][0].update(evidence_id=fact['evidence_id'],evidence_excerpt=fact['text']);return c,ctx,obj,fact
 def test_equivalent_ground_rdf_serialization(self):
  c,ctx,obj,fact=self.fact_control('"ice"');obj['issues'][0]['evidence_excerpt']='PREFIX v: <urn:> v:s v:p "ice" .';self.assertTrue(self.parse(c,ctx,obj)[1])
 def test_altered_fact_unsupplied_fact_and_inference_rejected(self):
  c,ctx,obj,fact=self.fact_control('<urn:object>')
  for text in ['<urn:s> <urn:p> <urn:other> .','<urn:s> <urn:different> <urn:object> .','<urn:s> <urn:p> <urn:object> . <urn:s> <urn:q> <urn:o> .','[] <urn:p> <urn:object> .']:
   v=copy.deepcopy(obj);v['issues'][0]['evidence_excerpt']=text
   with self.assertRaises(ReviewerFormatError):self.parse(c,ctx,v)
  # Even a real ontology declaration is unsupplied when removed from this packet.
  v=copy.deepcopy(obj);v['issues'][0]['evidence_id']='ev:unsupplied';self.assertTrue(validate_review({'text':json.dumps(v)},c,ctx)[2])
  self.s.graph.add((URIRef('urn:hidden'),URIRef('urn:p'),URIRef('urn:object')));v=copy.deepcopy(obj);v['issues'][0]['evidence_excerpt']='<urn:hidden> <urn:p> <urn:object> .'
  with self.assertRaises(ReviewerFormatError):self.parse(c,ctx,v)
 def test_exact_numeric_lexical_datatype_and_language_identity(self):
  c,ctx,obj,fact=self.fact_control('"7.0"^^<http://www.w3.org/2001/XMLSchema#decimal>');self.assertTrue(self.parse(c,ctx,obj)[1])
  for text in ['<urn:s> <urn:p> "7"^^<http://www.w3.org/2001/XMLSchema#decimal> .','<urn:s> <urn:p> "7.0"^^<http://www.w3.org/2001/XMLSchema#double> .','<urn:s> <urn:p> "7.0"@en .']:
   v=copy.deepcopy(obj);v['issues'][0]['evidence_excerpt']=text
   with self.assertRaises(ReviewerFormatError):self.parse(c,ctx,v)
  import rdflib;self.assertTrue(rdflib.NORMALIZE_LITERALS)
 def test_source_quotation_whitespace_must_remain_exact(self):
  c,ctx,r,obj=self.control();obj['issues'][0]['source_excerpt']=base.SOURCE.replace('Ships shall','Ships  shall')
  with self.assertRaises(ReviewerFormatError) as e:self.parse(c,ctx,obj)
  self.assertEqual(e.exception.errors[0]['category'],'INVALID_SOURCE_QUOTATION')
 def test_wrong_source_kind_and_missing_references_rejected(self):
  c,ctx,obj,fact=self.fact_control('<urn:object>');obj['issues'][0]['source_evidence_id']=fact['evidence_id']
  with self.assertRaises(ReviewerFormatError):self.parse(c,ctx,obj)
  c,ctx,r,obj=self.control();obj['issues'][0].pop('source_evidence_id');obj['issues'][0].pop('evidence_id');errors=validate_review({'text':json.dumps(obj)},c,ctx)[2];self.assertEqual(sum(e['code']=='MISSING_OR_UNSUPPLIED_EVIDENCE_ID' for e in errors),2)
 def test_stale_candidate_context_and_prior_binding_rejected(self):
  c,ctx,r,obj=self.control()
  for field,val in [('candidate_version',2),('candidate_sha256','0'*64),('review_request_id','review:stale')]:
   v=copy.deepcopy(obj);v[field]=val
   with self.assertRaises(ReviewerFormatError):self.parse(c,ctx,v)
  altered=copy.deepcopy(ctx);altered['contract']={'changed':'new fact'}
  self.assertTrue(any(e['code']=='STALE_OR_ABSENT_REVIEW_BINDING' for e in validate_review({'text':json.dumps(obj)},c,altered)[2]))
 def test_all_unknown_reconciliations_collected(self):
  c,ctx,r,obj=self.control();source=obj['issues'][0];obj['reconciliations']=[dict(issue_id=x,state='PERSISTENT',source_evidence_id=source['source_evidence_id'],source_excerpt=source['source_excerpt'],candidate_excerpt=c.code,reason='Invented prior issue') for x in ['never-seen-a','never-seen-b']];errors=validate_review({'text':json.dumps(obj)},c,ctx)[2];self.assertEqual(sum(e['code']=='UNGROUNDED_ISSUE_RECONCILIATION' for e in errors),2);self.assertTrue(any(e['code']=='INCOMPLETE_PRIOR_ISSUE_RECONCILIATION' for e in errors))
 def test_retry_original_state_and_failed_issues_not_registered(self):
  observed=[]
  def handler(r,i):
   if r['route']=='generation':return base.wrap(base.GOOD)
   body=base.request_data(r)
   if r['route']=='review':
    observed.append(copy.deepcopy(json.loads(r['user'])));obj=json.loads(base.review_response(r));issue=base.issue_for(r);obj['decision']='REJECT';obj['issues']=[issue];obj['issues'][0]['evidence_excerpt']='invented unsupported fact';return json.dumps(obj)
   self.assertEqual({k:v for k,v in json.loads(r['user']).items() if k!='format_feedback'},observed[0]);self.assertEqual(body['allowed_reconciliation_ids'],[]);self.assertTrue(body['failed_review_is_not_prior_state']);self.assertTrue(body['validation_errors']);self.assertIn('source_evidence_id',body['citation_format']['source']);return base.review_response(r)
  result,t,out=self.run_local(handler);self.assertEqual(result['accepted_version'],1,result);self.assertEqual(result['auxiliary_format_retries'],1);self.assertEqual(result['repair_calls'],0);self.assertEqual(result['history'][0]['review']['reconciliations'],[])
  if os.environ.get('NLTL_TEST_OUTPUT'):
   import shutil;shutil.copytree(out,pathlib.Path(os.environ['NLTL_TEST_OUTPUT'])/'review_and_retry_complete_packets')
 def test_retry_invented_reconciliation_rejected_after_serialization_fix(self):
  def handler(r,i):
   if r['route']=='generation':return base.wrap(base.GOOD)
   obj=json.loads(base.review_response(r));data=base.request_data(r);data=data.get('original_request',data)
   if r['route']=='review':obj['decision']='UNKNOWN_DECISION';return json.dumps(obj)
   source=next(e for e in data['evidence_catalog']['entries'] if e['kind']=='SOURCE');obj['reconciliations']=[dict(issue_id='failed-review-issue',state='PERSISTENT',source_evidence_id=source['evidence_id'],source_excerpt=source['text'],candidate_excerpt=data['full_candidate'],reason='Not an actual prior issue')];return json.dumps(obj)
  result,t,out=self.run_local(handler);self.assertEqual(result['status'],'REVIEWER_FORMAT_FAILURE');self.assertIsNone(result['accepted_version']);self.assertIsNone(result['history'][0]['review']);self.assertEqual(result['history'][0]['persistent_failure_summary']['persistent_or_regressed'],[])
 def test_probe_summary_sent_and_not_regulatory_proof(self):
  def handler(r,i):
   if r['route']=='generation':return base.wrap(base.GOOD)
   body=base.request_data(r);probe=body['execution_probe'];self.assertEqual(probe['candidate_sha256'],digest(base.GOOD));self.assertEqual(probe['candidate_version'],1);self.assertEqual(probe['engine_outcome'],'COMPLETED_NO_ENGINE_ERROR');self.assertEqual(set(probe['diagnostics']),{'stdout','stderr'});self.assertEqual(probe['diagnostics']['stdout']['sha256'],digest(''));self.assertFalse(probe['regulatory_correctness_established']);self.assertNotIn('witness',probe);self.assertFalse(any(e['kind']=='EXECUTION_OBSERVATION' for e in body['evidence_catalog']['entries']));return base.review_response(r)
  result,t,out=self.run_local(handler);self.assertEqual(result['accepted_version'],1,result)
 def test_stale_or_unsupplied_execution_observation_rejected(self):
  c,ctx,r,obj=self.control()
  with self.assertRaisesRegex(ValueError,'STALE_EXECUTION'):probe_summary(c,{'candidate_sha256':'bad','candidate_version':1})
 def test_request_packet_tampering_rejected(self):
  c,ctx,r,obj=self.control();execution=probe_summary(c);body=dict(context=ctx,full_candidate=c.code,previous_candidate=None,change_manifest={'changes':[]},prior_issues=[],execution_probe=execution,evidence_catalog=evidence_catalog(ctx,execution));body.update(review_binding(c,ctx,[],None,body['change_manifest'],execution));assert_review_packet(body,c)
  bad=copy.deepcopy(body);bad['evidence_catalog']['entries'].append(dict(evidence_id='ev:invented',kind='RDF_FACT',text='<urn:x> <urn:p> <urn:y> .'))
  with self.assertRaisesRegex(ValueError,'UNSUPPLIED_REVIEW_EVIDENCE'):assert_review_packet(bad,c)
 def test_multiple_independent_field_failures_all_reported(self):
  c,ctx,r,obj=self.control();obj['candidate_sha256']='bad';obj['issues'][0]['source_excerpt']='not supplied';obj['issues'][0]['candidate_excerpt']='missing';obj['issues'][0]['evidence_excerpt']='fabricated';errors=validate_review({'text':json.dumps(obj)},c,ctx)[2];self.assertGreaterEqual(len(errors),4)

 def test_plain_and_explicit_string_rdf11_term_equivalence(self):
  c,ctx,obj,fact=self.fact_control('"ice"');obj['issues'][0]['evidence_excerpt']='<urn:s> <urn:p> "ice"^^<http://www.w3.org/2001/XMLSchema#string> .';self.assertTrue(self.parse(c,ctx,obj)[1])
 def test_boolean_candidate_version_not_accepted_as_integer_one(self):
  c,ctx,r,obj=self.control();obj['candidate_version']=True;self.assertTrue(any(e['code']=='STALE_OR_ABSENT_REVIEW_BINDING' for e in validate_review({'text':json.dumps(obj)},c,ctx)[2]))
 def test_continuation_config_cannot_run_as_fresh_generation(self):
  import sys,contextlib,io
  from unittest.mock import patch
  from nltlv2.cli import main
  config=self.p.config('configs/nltl.json');config['method']='offline';config['continuation']={'initial_generation_calls':0};self.write('configs/continuation.json',config)
  args=['nltl','--project',str(self.root),'run','--config','configs/continuation.json','--requirement','NOVEL-RULE','--experiment-id','must_not_generate','--allow-model-calls']
  with patch.object(sys,'argv',args),patch('nltlv2.transport.LiveTransport',side_effect=AssertionError('No live transport allowed')),self.assertRaisesRegex(ValueError,'generation workflow'):main()

 def test_blank_node_supplied_evidence_has_text_id_without_identity_inference(self):
  c,ctx,r,obj=self.control();ctx['ontology_evidence']=[['_:supplied','<urn:p>','<urn:o>']];catalog=evidence_catalog(ctx);entry=next(e for e in catalog['entries'] if e.get('origin',{}).get('context_field')=='ontology_evidence');self.assertEqual(entry['kind'],'SCHEMA_TEXT');self.assertIsNone(citation_error(catalog,entry['evidence_id'],entry['text']));self.assertIsNotNone(citation_error(catalog,entry['evidence_id'],'_:different <urn:p> <urn:o> .'))

 def test_bounded_schema_optional_fields_and_strict_provider_schema(self):
  from nltlv2.review_protocol import legacy_reviewer_schema as reviewer_schema
  bounded=reviewer_schema();strict=reviewer_schema(strict=True);self.assertNotIn('evidence_requests',bounded['required']);self.assertIn('review_request_id',bounded['required']);self.assertNotIn('source_evidence_id',bounded['properties']['issues']['items']['required']);self.assertIn('source_evidence_id',bounded['properties']['issues']['items']['allOf'][0]['then']['required']);self.assertNotIn('change_id',bounded['properties']['issues']['items']['required']);self.assertIn('change_id',bounded['properties']['change_assessments']['items']['required']);self.assertEqual(set(strict['required']),set(strict['properties']))
 def test_unknown_issue_fields_reported(self):
  c,ctx,r,obj=self.control();obj['issues'][0]['invented_field']='x';errors=validate_review({'text':json.dumps(obj)},c,ctx)[2];self.assertTrue(any(e['code']=='UNKNOWN_REVIEW_FIELD' for e in errors))
