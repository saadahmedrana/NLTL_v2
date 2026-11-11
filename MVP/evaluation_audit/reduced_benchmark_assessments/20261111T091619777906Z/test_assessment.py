"""Read-only evidence gates and synthetic source-law checks; no SHACL replay."""
import ast,copy,json,sys,unittest,collections
from pathlib import Path
from unittest.mock import patch
from rdflib import Graph,URIRef,Literal,RDF,XSD
D=Path(__file__).resolve().parent;sys.path.insert(0,str(D))
import source_inventory as m
from source_review import fresh_oracle

def read(p):return json.loads(Path(p).read_text())
class AssessmentChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.cases=read(D/'reviewed_cases.json');cls.current=[c for c in cls.cases if c['scope']=='CURRENT_157'];cls.proposal=read(D/'proposed_selection.json');cls.plans=read(D/'reviewed_branch_specifications.json')
 def test_scope_correction_preserves_exact_553(self):
  self.assertEqual(len(m.REQS),157);self.assertEqual(len(m.SNAPSHOT),553)
  self.assertEqual(m.SNAPSHOT,read(D/'snapshot_553_case_ids.json'))
  self.assertEqual(set(read(m.RECON/'common_subset_case_ids.json')['after']),set(m.SNAPSHOT))
  self.assertNotIn('TRF-130',m.REQS)
 def test_inventory_contains_all_positives_and_negatives_not_just_classified(self):
  rows=[r for r in m.ROWS if r['condition']=='NO_SEMANTIC' and r['requirement_id'] in m.REQS]
  self.assertEqual({c['case_id'] for c in self.current},{r['case_id'] for r in rows})
  self.assertEqual(collections.Counter(c['expected'] for c in self.current),{'PASS':606,'FAIL':684})
  self.assertEqual(sum(c['historical_strict_snapshot_member'] for c in self.current),553)
  self.assertEqual(len({c['case_id'] for c in self.current}),1290)
 def test_workflow_case_identities_labels_and_source_text_match(self):
  index={(r['condition'],r['case_id']):r for r in m.ROWS}
  for c in self.cases:
   a=index['NO_SEMANTIC',c['case_id']];b=index['SINGLESHOT',c['case_id']]
   for key in ['case_id','requirement_id','rdf_path','expected','source_clause','frozen_requirement_text','source_oracle_rationale']:self.assertEqual(a[key],b[key])
 def test_authoring_oracle_agreement_is_not_automatic_review_credit(self):
  self.assertTrue(all(c['authoring_oracle']['expected_agreement'] for c in self.cases))
  summary=read(D/'summary.json');self.assertEqual(summary['verified_positive'],163)
  self.assertEqual(summary['verified_negative_gold'],47);self.assertEqual(summary['verified_negative_with_repair'],46)
  self.assertEqual(summary['not_certified_positive'],443)
 def test_proposal_includes_every_original_case_of_each_selected_requirement(self):
  chosen=set(self.proposal['requirements']);expected={c['case_id'] for c in self.current if c['requirement_id'] in chosen}
  self.assertEqual(set(self.proposal['case_ids']),expected)
  self.assertEqual((len(chosen),len(expected)),(6,37))
  self.assertEqual((len(self.proposal['positive_case_ids']),len(self.proposal['negative_case_ids'])),(17,20))
  self.assertTrue(all(c['freeze_verified'] for c in self.current if c['case_id'] in expected))
  for q in chosen:self.assertTrue(self.plans[q]['all_cases_source_schema_verified'])
 def test_retention_is_blind_to_workflow_performance_and_generation_eligibility(self):
  tree=ast.parse((D/'build_report.py').read_text());fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='propose');ns={};exec(compile(ast.Module(body=[fn],type_ignores=[]),'source_only_selection','exec'),ns)
  baseline=ns['propose'](self.cases,self.plans);altered=copy.deepcopy(self.cases)
  for c in altered:
   c['workflows']={'NO_SEMANTIC':{'status':'MISSED_INTENDED_DEFECT'},'SINGLESHOT':{'status':'STRICT_INTENDED_MATCH'}}
   c['original_eligible']=False;c['observed']='FAIL';c['accuracy']=0;c['historical_case_state']='BLOCKED'
  self.assertEqual(ns['propose'](altered,self.plans),baseline)
  self.assertTrue(all('workflows' not in r for r in m.RECS.values()))
 def test_same_exclusions_and_unresolved_cases_never_silently_dropped(self):
  self.assertEqual(self.proposal['workflows']['NLTL_v2'],self.proposal['workflows']['Single-shot'])
  self.assertEqual(self.proposal['excluded_case_ids'],[])
  retained=set(self.proposal['case_ids']);unresolved=set(self.proposal['unresolved_case_ids']);deferred=set(self.proposal['verified_cases_deferred_for_requirement_coverage'])
  self.assertFalse(retained&unresolved or retained&deferred or unresolved&deferred)
  self.assertEqual(retained|unresolved|deferred,{c['case_id'] for c in self.current})
  self.assertEqual((len(unresolved),len(deferred)),(1081,172))
 def test_valid_negative_without_repair_is_not_excluded_or_credited_strict(self):
  c=next(c for c in self.current if c['case_id']=='I2-048-H-F006')
  self.assertTrue(c['gold_expectation_verified']);self.assertFalse(c['freeze_verified'])
  self.assertIn(c['case_id'],self.proposal['unresolved_case_ids']);self.assertNotIn(c['case_id'],self.proposal['excluded_case_ids'])
 def test_all_branch_witness_ids_are_real_and_coverage_limits_remain_explicit(self):
  ids={c['case_id'] for c in self.current}
  for q,p in self.plans.items():
   for branch,cases in p['branches'].items():self.assertTrue(set(cases)<=ids,(q,branch))
   self.assertTrue(p['gaps'])
  self.assertEqual(self.plans['TRF-001']['branches']['missing_universal_chapter_2'],[])
  self.assertFalse(self.plans['TRF-001']['eligible_to_freeze_as_represented_core'])
  self.assertFalse(self.plans['TRF-050']['eligible_to_freeze_as_represented_core'])
 def test_source_table_cells_are_checked_against_transcription_not_shapes(self):
  r=read(D/'table8_scope_review.json');self.assertEqual(len(r['cell_checks']),126)
  self.assertTrue(all(c['contract_match'] for c in r['cell_checks']));self.assertEqual(r['positive_cells_represented'],126)
  self.assertEqual(r['positive_polar_classes'],[1,2,3,4,5,6,7])
  self.assertEqual(sum(c['freeze_verified'] for c in self.current if c['requirement_id']=='I2-048' and c['expected']=='PASS'),137)
 def test_unbound_legacy_term_is_not_assigned_an_owner_or_forced_as_input(self):
  g=Graph();s=URIRef('urn:ship');g.add((s,RDF.type,m.N.ship))
  result=m.schema_inventory(g,'I2-004')
  self.assertIn('upperIceWaterline',result['inactive_indexed_properties_with_unresolved_owner'])
  self.assertNotIn('upperIceWaterline',result['explicit_owners'])
  g.add((s,m.N.upperIceWaterline,URIRef('urn:legacy')))
  self.assertIn('upperIceWaterline',m.schema_inventory(g,'I2-004')['unresolved_binding_properties'])
 def test_no_selector_is_not_guessed_false(self):
  g=Graph();node=URIRef('urn:web');g.add((node,RDF.type,m.N.webFrame))
  result=fresh_oracle(g,'TRF-058');self.assertIsNone(result['conforms'])
  self.assertTrue(result['unresolved'])
 def test_flange_rule_is_minimum_and_does_not_require_existing_members(self):
  g=Graph();ship=URIRef('urn:ship');member=URIRef('urn:member');g.add((ship,RDF.type,m.N.ship))
  self.assertTrue(fresh_oracle(g,'I2-042')['conforms'])
  g.add((ship,m.N.hasStructuralMember,member));g.add((member,RDF.type,m.N.structuralMember))
  for name,value in [('flangeWidth','55'),('netWebThickness','10')]:
   q=URIRef('urn:'+name);g.add((member,m.N[name],q));g.add((q,m.Q.numericValue,Literal(value,datatype=XSD.decimal)));g.add((q,m.Q.unit,m.U.MilliM))
  with patch.object(m.audit,'validate',side_effect=AssertionError('No SHACL evaluation allowed')):
   self.assertTrue(fresh_oracle(g,'I2-042')['conforms'])
   g.set((URIRef('urn:flangeWidth'),m.Q.numericValue,Literal('49.9',datatype=XSD.decimal)))
   self.assertFalse(fresh_oracle(g,'I2-042')['conforms'])
 def test_trf050_intentional_mutation_and_original_classifications_are_preserved(self):
  r=read(m.A['current_case_records'])['TRF-050-F05']
  for w in m.audit.WORKFLOWS:self.assertEqual(r['workflows'][w]['status'],'STRICT_INTENDED_MATCH')
  c=next(c for c in self.current if c['case_id']=='TRF-050-F05');self.assertTrue(c['freeze_verified'])
  self.assertEqual({p for s,p in c['independent_repair_review']['semantic_roots']},{str(m.N.frameShellWeldType)})
 def test_runner_verification_is_not_syntax_only(self):
  r=read(D/'runner_route_verification.json');self.assertTrue(r['all_hashes_match'])
  self.assertEqual(r['normal_repair_routes'],{'SEMANTIC_CANDIDATE_REPAIR':8,'STATIC_REPAIR':2,'MATCHER_ASSISTED_REPAIR':3,'SYNTAX_REPAIR':2})
  self.assertEqual(len(r['canonical_requests']),4)
  for c in r['canonical_requests']:self.assertEqual(c['candidate_sha256'],c['feedback_sha256'])
  self.assertTrue(r['semantic_and_canonical_findings_reach_code_repair']);self.assertEqual(r['new_api_calls'],0)
 def test_original_snapshot_inputs_labels_and_fixtures_are_unchanged(self):
  for p,h in read(D/'protected_inputs.json').items():self.assertEqual(m.sha(p),h,p)
  for c in self.cases:self.assertEqual(m.sha(c['fixture']),c['fixture_sha256'])

if __name__=='__main__':unittest.main(verbosity=2)
