
import unittest,json,pathlib,os,copy
from rdflib import Graph,RDF,RDFS,Namespace,Literal
from rdflib.namespace import SH
import test_general_pipeline as base
from nltlv2.core import Candidate,GenerationProject,digest
from nltlv2.schema import Schema,Q,N
from nltlv2.checks import check,runtime_probe
from nltlv2.activation import checks as activation_checks,analyze
from nltlv2.requests import parse_review,repair_request,ReviewerFormatError
from nltlv2.review_protocol import normalize_response,response_format
from nltlv2.transport import provider_payload
from nltlv2.change_review import manifest
from nltlv2.source_context import select_document,retrieve
from nltlv2.prompt_accounting import measure
class NewControls(unittest.TestCase):
 setUp=base.GeneralPipelineTests.setUp
 tearDown=base.GeneralPipelineTests.tearDown
 write=base.GeneralPipelineTests.write
 run_local=base.GeneralPipelineTests.run_local
 accepting=base.GeneralPipelineTests.accepting
 def context(self):return self.s.context('NOVEL-RULE')
 def response(self):
  c=Candidate(1,base.BAD_EXTRA,'');r={'user':json.dumps(dict(context=self.context(),full_candidate=c.code,previous_candidate=None,change_manifest={'changes':[]},prior_issues=[]))}
  return c,json.loads(base.review_response(r,'REJECT',base.issue_for(r)))
 def parse(self,obj,c=None):return parse_review({'text':json.dumps(obj)},c or Candidate(1,base.BAD_EXTRA,''),self.context())
 def test_aliases_preserve_values_and_raw(self):
  c,obj=self.response();issue=obj['issues'][0];issue['exact_source_excerpt']=issue.pop('source_excerpt');issue['exact_candidate_excerpt']=issue.pop('candidate_excerpt');raw=json.dumps(obj);normalized,audit=normalize_response({'text':raw});self.assertEqual(audit['raw_text'],raw);self.assertEqual(len(audit['aliases']),2);self.assertFalse(audit['values_modified']);review,fs=parse_review({'text':raw},c,self.context());self.assertTrue(fs);self.assertFalse(fs[0].confirmed)
 def test_conflicting_alias_rejected(self):
  c,o=self.response();o['issues'][0]['exact_source_excerpt']='conflicting'
  with self.assertRaisesRegex(ReviewerFormatError,'CONFLICTING_ALIAS'):self.parse(o,c)
 def test_identical_duplicate_alias_allowed(self):
  c,o=self.response();o['issues'][0]['exact_source_excerpt']=o['issues'][0]['source_excerpt'];self.assertTrue(self.parse(o,c)[1])
 def test_conflicting_json_duplicate_rejected(self):
  with self.assertRaisesRegex(ReviewerFormatError,'CONFLICTING_DUPLICATE_FIELD'):normalize_response({'text':'{"decision":"ACCEPT","decision":"REJECT"}'})
 def test_alias_does_not_repair_invalid_quote(self):
  c,o=self.response();x=o['issues'][0];x['exact_source_excerpt']='inaccurate';x.pop('source_excerpt')
  with self.assertRaises(ReviewerFormatError) as cm:self.parse(o,c)
  self.assertEqual(cm.exception.details['category'],'INVALID_SOURCE_QUOTATION');self.assertEqual(cm.exception.details['path'],'$.issues[0].source_excerpt')
 def test_unsupported_schema_assertion_distinct(self):
  c,o=self.response();o['issues'][0]['evidence_excerpt']='Schema implies a new value'
  with self.assertRaises(ReviewerFormatError) as cm:self.parse(o,c)
  self.assertEqual(cm.exception.details['category'],'UNSUPPORTED_SCHEMA_ASSERTION')
 def test_wrong_current_quote_distinct(self):
  c,o=self.response();o['issues'][0]['candidate_excerpt']='nonexistent'
  with self.assertRaises(ReviewerFormatError) as cm:self.parse(o,c)
  self.assertEqual(cm.exception.details['category'],'INVALID_CANDIDATE_QUOTATION')
 def test_material_unchecked_blocks_acceptance(self):
  r,t,out=self.run_local(lambda req,i:base.wrap(base.GOOD) if req['route']=='generation' else json.dumps(base.bind_review_response(req,dict(decision='ACCEPT',issues=[],change_assessments=[],reconciliations=[],unchecked=[dict(scope='Target/application unresolved',material=True,reason='Cannot establish applicability')]))));self.assertEqual(r['status'],'REVIEWER_FORMAT_FAILURE');self.assertIsNone(r['accepted_version']);self.assertEqual(len(t.calls),3)
 def test_legacy_untyped_unchecked_conservatively_material(self):
  o=base.bind_review_response({'user':json.dumps(dict(context=self.context(),full_candidate=base.GOOD,previous_candidate=None,change_manifest={'changes':[]},prior_issues=[]))},dict(decision='ACCEPT',issues=[],change_assessments=[],reconciliations=[],unchecked=['Targeting unresolved']));
  with self.assertRaises(ReviewerFormatError):self.parse(o,Candidate(1,base.GOOD,''))
  o['decision']='UNRESOLVED';review,fs=self.parse(o,Candidate(1,base.GOOD,''));self.assertTrue(any(f.blocking and f.category=='UNRESOLVED_CONTEXT' for f in fs))
 def test_nonmaterial_methodology_note_allows_acceptance(self):
  r,t,_=self.run_local(self.accepting);self.assertEqual(r['accepted_version'],1)
 def test_uncertainty_not_format_retry(self):
  c,o=self.response();o['decision']='UNRESOLVED';o['issues'][0]['category']='UNRESOLVED_CONTEXT';obj,fs=self.parse(o,c);self.assertEqual(fs[0].assessment,'UNRESOLVED_CONTEXT')
 def test_retry_identifies_field_and_retains_normalized(self):
  def handler(req,i):
   if req['route']=='generation':return base.wrap(base.GOOD)
   if req['route']=='review':
    o=json.loads(base.review_response(req));o['decision']='REJECT';x=base.issue_for(req);x['source_excerpt']='not supplied';o['issues']=[x];return json.dumps(o)
   p=base.request_data(req);self.assertEqual(p['format_error']['path'],'$.issues[0].source_excerpt');self.assertIn('properties',p['expected_structure']);return base.review_response(req)
  r,t,out=self.run_local(handler);self.assertEqual(r['accepted_version'],1);self.assertTrue((out/'reviewer_normalized_002.json').is_file());self.assertTrue((out/'reviewer_normalized_003.json').is_file())
 def test_structured_output_requires_capability_evidence(self):
  with self.assertRaisesRegex(ValueError,'NOT_VERIFIED'):response_format({'review_output_mode':'json_schema'})
 def test_documented_structured_payload_offline(self):
  cfg=dict(review_output_mode='json_schema',provider_capabilities=dict(responses_text_json_schema=True,documentation_url='https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/structured-outputs'));fmt=response_format(cfg);payload=provider_payload(dict(model='OFFLINE',route='review',system='test',user='test',max_output_tokens=500,response_format=fmt));self.assertEqual(payload['text']['format']['type'],'json_schema');self.assertTrue(fmt['strict'])
 def test_no_structured_format_on_generation(self):
  with self.assertRaises(ValueError):provider_payload(dict(model='OFFLINE',route='generation',system='',user='',max_output_tokens=1,response_format={'type':'json_schema'}))
 def activation(self,code):return activation_checks(Candidate(1,code,''),Graph().parse(data=code,format='turtle'))
 def test_untargeted_root_rejected(self):self.assertTrue(any(f.category=='ACTIVATION_ERROR' for f in self.activation(base.GOOD.replace('sh:targetClass n:ship;',''))))
 def test_nested_shape_needs_no_own_target(self):
  code=base.PREFIX+'<urn:root> a sh:NodeShape; sh:targetClass n:ship; sh:node <urn:child>. <urn:child> a sh:NodeShape; sh:property [sh:path n:bridgeWingsEnclosed;sh:minCount 1].';self.assertFalse(self.activation(code))
 def test_deactivated_root_blocked(self):self.assertTrue(any(f.blocking for f in self.activation(base.GOOD.replace('a sh:NodeShape;','a sh:NodeShape; sh:deactivated true;'))))
 def test_deactivated_nested_enforcement_blocked(self):
  code=base.GOOD.replace('sh:minCount 1','sh:deactivated true;sh:minCount 1');self.assertTrue(self.activation(code))
 def test_empty_root_and_orphan_constraint_blocked(self):
  code=base.PREFIX+'<urn:root> a sh:NodeShape;sh:targetClass n:ship. <urn:child> a sh:NodeShape;sh:property [sh:path n:bridgeWingsEnclosed;sh:minCount 1].';self.assertTrue(self.activation(code))
 def test_explicit_node_target_supported(self):self.assertFalse(self.activation(base.GOOD.replace('sh:targetClass n:ship','sh:targetNode <urn:sample>')))
 def test_target_subjects_supported_and_probe_execution_only(self):
  c=Candidate(1,base.GOOD.replace('sh:targetClass n:ship','sh:targetSubjectsOf n:bridgeWingsEnclosed'),'');fs,probe=runtime_probe(c,self.s);self.assertFalse(fs);self.assertTrue(probe['ignored_conformance']);self.assertTrue(probe['activation']['supported']);self.assertNotIn('expected',probe)
 def test_implicit_class_target_supported(self):self.assertFalse(self.activation(base.GOOD.replace('a sh:NodeShape; sh:targetClass n:ship;','a sh:NodeShape, <http://www.w3.org/2000/01/rdf-schema#Class>;')))
 def test_custom_target_unresolved(self):
  code=base.GOOD.replace('sh:targetClass n:ship','sh:target [a <urn:custom>]');self.assertTrue(any(f.category=='UNRESOLVED_CONTEXT' for f in self.activation(code)))
 def test_numeric_predicate_and_unit_in_context_without_registry_rows(self):
  c=self.context();irs={x['iri'] for x in c['schema_terms']};self.assertIn(str(Q.numericValue),irs);self.assertIn(str(Q.unit),irs);self.assertEqual(c['quantityEncoding']['numeric_predicate'],str(Q.numericValue));self.assertIn('decimal',c['quantityEncoding']['canonical_literal_encoding'])
 def test_ontology_range_members_labels_without_registry(self):
  p=self.root/'schema/Schema_for_NLTL.ttl';p.write_text(p.read_text()+'\n@prefix rdfs:<http://www.w3.org/2000/01/rdf-schema#>. n:shipCategory rdfs:range n:probeClass. n:a rdfs:label "A". n:unrelated a n:otherClass. n:child rdfs:subClassOf n:probeClass. n:c a n:child.');self.write('schema/representation_bindings.json',{'requirements':{'NOVEL-RULE':{'terms':['shipCategory']}}});c=Schema(self.p).context('NOVEL-RULE');terms={x['iri']:x for x in c['schema_terms']};self.assertEqual(terms[str(N.a)]['label'],'A');self.assertIn(str(N.c),terms);self.assertNotIn(str(N.unrelated),terms)
 def test_broad_ancestor_not_reverse_expanded(self):
  p=self.root/'schema/Schema_for_NLTL.ttl';p.write_text(p.read_text()+'\n@prefix rdfs:<http://www.w3.org/2000/01/rdf-schema#>. n:probeClass rdfs:subClassOf n:broad. n:unrelatedClass rdfs:subClassOf n:broad. n:unrelated a n:unrelatedClass. n:shipCategory rdfs:range n:probeClass.');self.write('schema/representation_bindings.json',{'requirements':{'NOVEL-RULE':{'terms':['shipCategory']}}});c=Schema(self.p).context('NOVEL-RULE');self.assertNotIn(str(N.unrelated),[x['iri'] for x in c['schema_terms']])
 def test_qudt_value_feedback_exact_replacement_evidence(self):
  code=base.GOOD.replace('n:bridgeWingsEnclosed','q:value').replace('@prefix n:','@prefix q:<http://qudt.org/schema/qudt/>. @prefix n:');fs=check(Candidate(4,code,''),self.s,'NOVEL-RULE');fs=[f for f in fs if f.category=='CANONICAL_IDENTIFIER_ERROR'];self.assertEqual(len(fs),1);self.assertEqual(fs[0].expected,str(Q.numericValue));self.assertIn('do not delete',fs[0].suggestion);self.assertIn('locked_representation_context',fs[0].evidence);self.assertEqual(fs[0].version,4);self.assertIn('line',fs[0].location)
 def test_identifier_correction_does_not_change_units_values(self):
  replacement,evidence=self.s.identifier_correction(str(Q.value));self.assertEqual(replacement,str(Q.numericValue));self.assertIn('numericValue',str(evidence));self.assertEqual(self.s.identifier_correction('urn:unknown')[0],None)
 def test_removal_alerts_preserve_query_numeric_unit_evidence(self):
  code=base.GOOD+'<urn:q> sh:select "SELECT $this WHERE {$this <urn:p> ?v}".';a=Candidate(1,code,'');b=Candidate(2,base.GOOD.replace('sh:datatype xsd:boolean;',''),'');m=manifest(a,b);self.assertTrue(any(x['kind']=='QUERY' and x['removal_alerts'] for x in m['changes']));self.assertTrue(any(x['kind']=='TYPE' and x['removal_alerts'] for x in m['changes']))
 def test_removal_without_explicit_source_assessment_rejected(self):
  a=Candidate(1,base.BAD_EXTRA,'');b=Candidate(2,base.GOOD,'');m=manifest(a,b);r={'user':json.dumps(dict(context=self.context(),full_candidate=b.code,previous_candidate={'full_code':a.code},change_manifest=m,prior_issues=[]))};o=json.loads(base.review_response(r))
  for x in o['change_assessments']:x.pop('removal_assessments',None)
  with self.assertRaisesRegex(ReviewerFormatError,'UNASSESSED_OBLIGATION_LOSS'):parse_review({'text':json.dumps(o)},b,self.context(),previous=a,changes=m)
 def test_prompt_measurement_partitions_rendered_bytes(self):
  req=dict(system='system',user=json.dumps(dict(source_documents=[{'text':'source source'}],full_candidate='candidate',schema_terms=[{'iri':'urn:test'}],current_findings=[{'diagnostic':'error'}]),ensure_ascii=False));m=measure(req);self.assertEqual(sum(m['components_bytes'].values()),m['rendered_bytes']);self.assertTrue(all(m['components_bytes'][x]>0 for x in ['source','schema','code','diagnostics']));self.assertIsNone(m['token_count'])
 def test_source_selection_preserves_reference_definition_and_omission_hashes(self):
  text='1 Scope\n1.1 All vessels.\n2 Definitions\n2.1 A term is defined.\n3 Obligations\n3.1 Marker shall be recorded; see section 4.1.\n4 Support\n4.1 Required supporting provision.\n5 Unrelated\n5.1 Irrelevant item.\n';doc=dict(file='data/requirements/x.txt',sha256=digest(text),text=text);selected,m=select_document(doc,{'text':'3.1 Marker shall be recorded; see section 4.1.'});joined=''.join(x['text'] for x in selected);self.assertIn('Required supporting provision',joined);self.assertIn('A term is defined',joined);self.assertNotIn('Irrelevant item',joined);self.assertTrue(any(not s['included'] and s['sha256'] for s in m['sections']));self.assertLess(m['included_characters'],m['original_characters'])
 def test_ambiguous_source_anchor_retains_full_document(self):
  text='1.1 Same text.\n2.1 Other.\n1.1 Same text.\n';docs,m=select_document(dict(file='data/requirements/x',sha256=digest(text),text=text),{'text':'1.1 Same text.'});self.assertEqual(''.join(d['text'] for d in docs),text);self.assertTrue(m['fallback'])
 def test_source_span_retrieval_exact_hash(self):
  text=base.SOURCE;result=retrieve(GenerationProject(self.root),'data/requirements/source.txt',digest(text),0,10);self.assertEqual(result['text'],text[:10]);crlf='a\r\nb\r\n';(self.root/'data/requirements/crlf.txt').write_bytes(crlf.encode());self.assertEqual(retrieve(GenerationProject(self.root),'data/requirements/crlf.txt',digest(crlf),0,len(crlf))['text'],crlf)
  with self.assertRaises(AssertionError):retrieve(GenerationProject(self.root),'data/requirements/source.txt','stale',0,10)
 def test_external_reference_not_resolved_against_local_number(self):
  text='1.1 Duty; section 3 of the Act applies.\n3 Other\n3.1 Unrelated local section.\n';docs,m=select_document(dict(file='data/requirements/x',sha256=digest(text),text=text),{'text':'1.1 Duty; section 3 of the Act applies.'});self.assertTrue(m['unresolved_references']);self.assertNotIn('Unrelated local section',''.join(d['text'] for d in docs))

 def test_noop_closed_false_and_min_count_zero_not_enforcement(self):
  code=base.PREFIX+'<urn:root> a sh:NodeShape;sh:targetClass n:ship;sh:closed false;sh:property [sh:path n:bridgeWingsEnclosed;sh:minCount 0].';self.assertTrue(any(f.category=='ACTIVATION_ERROR' for f in self.activation(code)))
 def test_logical_not_empty_is_valid_structural_enforcement(self):
  code=base.PREFIX+'<urn:root> a sh:NodeShape;sh:targetClass n:ship;sh:not [].';self.assertFalse(self.activation(code))
 def test_empty_or_is_valid_false_constraint(self):
  code=base.PREFIX+'<urn:root> a sh:NodeShape;sh:targetClass n:ship;sh:or ().';self.assertFalse(self.activation(code))

 def test_missing_unit_declaration_not_invented(self):
  file=self.root/'schema/locked_representation_context.jsonld';obj=json.loads(file.read_text());obj['@context'].pop('unit');file.write_text(json.dumps(obj))
  with self.assertRaisesRegex(ValueError,'QUANTITY_UNIT_DECLARATION_REQUIRED'):Schema(self.p)
 def test_missing_numeric_predicate_not_invented(self):
  file=self.root/'schema/locked_representation_context.jsonld';obj=json.loads(file.read_text());obj['@context']['numericValue'].pop('@id');file.write_text(json.dumps(obj))
  with self.assertRaisesRegex(ValueError,'QUANTITY_NUMERIC_DECLARATION_REQUIRED'):Schema(self.p)
