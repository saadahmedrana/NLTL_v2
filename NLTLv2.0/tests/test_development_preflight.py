import copy,json,os,unittest
from pathlib import Path
from rdflib import Graph,RDF
from rdflib.namespace import RDFS,XSD
from nltlv2.core import Project,load,Candidate,digest
from nltlv2.schema import Schema,N,Q,U
from nltlv2.preflight import REQUIREMENTS,structural_probe,validate_manifest,settings
from nltlv2.requests import initial_request
from nltlv2.checks import check
from nltlv2.runner import Runner
from nltlv2.transport import ScriptedTransport

class DevelopmentPreflightTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.p=Project(os.environ['NLTL_TEST_PROJECT']);cls.s=Schema(cls.p);cls.out=Path(os.environ['NLTL_TEST_OUTPUT'])
 def test_source_text_and_scope_complete(self):
  for rid in self.s.development_profiles:
   ctx=self.s.context(rid);self.assertIn(ctx['contract']['sourceEvidence']['exact_excerpt'],self.p.path(ctx['contract']['sourceEvidence']['file']).read_text());self.assertTrue(ctx['contract']['sourceBackedObligations']);self.assertTrue(ctx['contract']['verificationScope'])
  self.assertIn('welded profiles',self.s.context('I2-042')['requirement']['text'])
  self.assertIn('7°',self.s.context('I2-005')['requirement']['text'])
  self.assertIn('greatest',self.s.context('I2-004')['requirement']['text'])
 def test_i2004_path_from_explicit_owner_and_range(self):
  ctx=self.s.context('I2-004');edge=dict(fromOwner='ship',toOwner='upperIceWaterlineCase',via='hasUpperIceWaterlineCase');self.assertIn(edge,ctx['modelPaths']);self.assertEqual(self.s.allowed_paths('I2-004')[1][str(N.waterlineCaseDisplacement)],[(str(N.hasUpperIceWaterlineCase),str(N.waterlineCaseDisplacement))])
  self.assertIn((N.hasUpperIceWaterlineCase,RDFS.range,N.upperIceWaterlineCase),self.s.graph)
 def test_i2004_wrong_owner_detected(self):
  code='@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix n: <https://w3id.org/nltl/vocab#> . <urn:dev:x> a sh:NodeShape ; sh:targetClass n:ship ; sh:property [ sh:path n:waterlineCaseDisplacement ; sh:minCount 1 ] .'
  fs=check(Candidate(1,code,code),self.s,'I2-004');self.assertIn('PATH_CONTRACT_ERROR',{f.category for f in fs})
 def test_legacy_terms_not_active_or_assigned_new_owners(self):
  for rid,term in [('I2-004','upperIceWaterline'),('I2-042','thickness'),('TRF-035','classificationSociety'),('TRF-035','hullRegion')]:
   ctx=self.s.context(rid);self.assertNotIn(term,[x['localName'] for x in ctx['schema_terms']]);self.assertIn(term,ctx['contract']['inactiveLegacyTerms'])
  self.assertNotIn('upperIceWaterline',self.s.index['termOwners']['I2-004'])
  self.assertNotIn('thickness',self.s.index['termOwners']['I2-042'])
 def test_imo_category_binding_and_selector_policy(self):
  ctx=self.s.context('IMO-001');self.assertIn(str(N.polarShipCategoryA),[r['iri'] for r in ctx['schema_terms']]);self.assertTrue(any(r['localName']=='mediumFirstYearIceWithPossibleOldIceInclusions' and 'at least medium' in r['normalizedDefinition'] for r in ctx['schema_terms']))
  policy=ctx['contract']['selectorPolicies'][0];self.assertFalse(policy['absenceMeansFalse']);self.assertEqual(policy['missingEvidence'],'VIOLATION')
  corrected=next(r for r in ctx['schema_terms'] if r['localName']=='mediumFirstYearIceWithPossibleOldIceInclusions');self.assertIn('Introduction 2.1',corrected['sourceRefs']);self.assertIn('original_sourceRefs',corrected)
 def test_datatype_profile_is_locked_serialization_not_global_range(self):
  for rid in ['I2-004','I2-005','I2-042','TRF-035']:
   q=self.s.context(rid)['quantityEncoding'];self.assertEqual(q['profile']['canonical_literal_encoding'],str(XSD.decimal));self.assertFalse(q['profile']['global_RDFS_range_declared']);self.assertTrue(q['properties'])
  self.assertNotIn('quantityEncoding',self.s.context('TRF-010'))
 def test_all_supported_synthetic_mutations_detected(self):
  for rid in self.s.development_profiles:
   with self.subTest(rid=rid):self.assertTrue(structural_probe(self.s,rid)['all_supported_mutations_detected'])
 def test_missing_regulatory_logic_is_not_claimed_checked(self):
  for rid in self.s.development_profiles:
   probe=structural_probe(self.s,rid);self.assertTrue(probe['regulatory_logic_missing_from_scaffold']);self.assertFalse(probe['confirmed_logic_omission_detected'])
 def test_six_identical_initial_requests(self):
  a=self.p.config('configs/single_shot.json');b=self.p.config('configs/nltl.json')
  for rid in REQUIREMENTS:
   context=self.s.context(rid);self.assertEqual(initial_request(self.p,context,settings(a)),initial_request(self.p,context,settings(b)))
 def test_selected_fewshots_absent(self):
  for rid in REQUIREMENTS:
   ctx=self.s.context(rid);self.assertEqual([e['exampleId'] for e in ctx['examples']],['FS-BOOL-01','FS-BOOL-02']);self.assertTrue(all(rid not in json.dumps(e) for e in ctx['examples']))
 def test_trf010_context_and_prompts_comparability(self):
  self.assertEqual(self.s.context('TRF-010'),load(self.p.path('smoke_tests/compatibility/trf010_v020_initial_context.json')))
  import hashlib
  for name,expected in load(self.p.path('smoke_tests/compatibility/trf010_v020_prompt_hashes.json')).items():self.assertEqual(hashlib.sha256(self.p.path('prompts/'+name).read_bytes()).hexdigest(),expected)
 def test_manifest_prepared_but_not_dispatchable(self):
  result=validate_manifest(self.p,load(self.p.path('configs/paired_development_pilot.json')));self.assertTrue(result['structurally_valid']);self.assertFalse(result['ready_for_dispatch']);self.assertFalse(result['dispatch_performed']);self.assertEqual([b['requirement'] for b in result['blockers']],['I2-042'])
  with self.assertRaises(ValueError):validate_manifest(self.p,load(self.p.path('configs/paired_development_pilot.json')),require_ready=True)
 def test_manifest_rejects_broken_limits_and_firewall(self):
  for key in ['single','nltl','evaluation']:
   value=copy.deepcopy(load(self.p.path('configs/paired_development_pilot.json')))
   if key=='single':value['workflows']['Single-shot']['maximum_generation_calls']=2
   if key=='nltl':value['workflows']['NLTL']['maximum_candidate_attempts']=7
   if key=='evaluation':value['evaluation']['feedback_to_repair']=True
   with self.assertRaises(ValueError):validate_manifest(self.p,value)
 def test_unresolved_applicability_stops_both_before_model_call(self):
  for method,file in [('Single-shot','single_shot'),('NLTL','nltl')]:
   dest=self.out/(self._testMethodName+'_'+file);dest.mkdir();transport=ScriptedTransport([]);result=Runner(self.p,self.p.config('configs/'+file+'.json'),transport,dest).run('I2-042')
   self.assertEqual(result['status'],'BLOCKED_PREFLIGHT_CONTEXT');self.assertEqual(result['generation_calls'],0);self.assertEqual(transport.calls,[]);self.assertIsNone(result['evaluation_candidate'])
 def test_source_context_builder_never_reads_evaluation(self):
  class SourceOnly(Project):
   def path(self,relative):
    if str(relative).startswith(('evaluation/','outputs/experiments/')):raise AssertionError('Evaluation or prior outputs entered source context')
    return super().path(relative)
  repository=Schema(SourceOnly(self.p.root))
  for rid in REQUIREMENTS:repository.context(rid)
 def test_current_fixture_identity_is_not_relabelled(self):
  core=load(self.p.path('evaluation/selections/regression_core.json'));self.assertEqual(len(core['cases']),37);self.assertEqual(sum(c['expected']=='PASS' for c in core['cases']),17);self.assertEqual(sum(bool(c.get('counterfactual')) for c in core['cases']),20)
  self.assertTrue(all(c['gold_expectation_verified'] for c in core['cases']))
 def test_no_welded_selector_invented(self):
  ctx=self.s.context('I2-042');self.assertTrue(ctx['unresolvedSourceContext'][0]['blocking_before_generation']);self.assertNotIn('weldedProfile',[r['localName'] for r in ctx['schema_terms']]);self.assertNotIn('weldedProfile',ctx['termOwners'])
 def test_quantity_profile_cannot_invent_a_datatype(self):
  repository=copy.copy(self.s);repository.quantity_profile=copy.deepcopy(self.s.quantity_profile);repository.quantity_profile['canonical_literal_encoding']=str(XSD.double)
  with self.assertRaises(ValueError):repository.validate_development_profiles()
 def test_blocked_contract_does_not_claim_active_complete_status(self):
  contract=self.s.context('I2-042')['contract'];self.assertEqual(contract['status'],'BLOCKED_APPLICABILITY_BINDING');self.assertEqual(contract['lockedMetadataStatus'],'COMPLETE')
 def test_source_blocker_cannot_be_silently_removed(self):
  repository=copy.copy(self.s);repository.context_issues=copy.deepcopy(self.s.context_issues);repository.context_issues['I2-042']=[]
  with self.assertRaises(ValueError):repository.validate_development_profiles()
