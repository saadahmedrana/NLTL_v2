"""Read-only regression checks: cached reports/oracles only, no SHACL execution."""
import copy,json,unittest
from collections import Counter
from unittest.mock import patch
import reconcile_ownership as r

class ReconciliationChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.before=r.read(r.DEST/'records_before.json');cls.after=r.read(r.DEST/'records_after.json')
  cls.plan=r.read(r.DEST/'plan.json');cls.executions=r.read(r.DEST/'executions.json')
 def test_population_and_common_subset(self):
  self.assertEqual(set(self.before),set(self.after));self.assertEqual(len(self.after),1205)
  ids=r.read(r.DEST/'common_subset_case_ids.json')
  self.assertEqual((len(ids['before']),len(ids['after']),len(ids['common_before_after_intersection'])),(611,553,551))
  for version,records in [('before',self.before),('after',self.after)]:
   common=set(ids[version])
   self.assertEqual(common,{c for c,x in records.items() if x['state'] in ['COMPLETED','COMPLETED_PRIOR50']})
   for w in r.audit.WORKFLOWS:
    self.assertEqual(sum(Counter(records[c]['workflows'][w]['status'] for c in common).values()),len(common))
    self.assertFalse(any(records[c]['workflows'][w]['status']=='UNRESOLVED_REASON' for c in common))
 def test_no_verdict_cannot_gain_credit_or_execution(self):
  for cid,old in self.before.items():
   for w,v in old.get('workflows',{}).items():
    if not v['original_eligible']:self.assertEqual(self.after[cid]['workflows'][w]['status'],'NO_VERDICT')
  for job in self.executions:self.assertTrue(r.ROW[job['condition'],job['case_id']]['original_eligible'])
 def test_identical_exclusions(self):
  for w in r.audit.WORKFLOWS:
   before={c for c,x in self.before.items() if x['state'].startswith('EXCLUDED')}
   after={c for c,x in self.after.items() if x['state'].startswith('EXCLUDED')}
   self.assertEqual(before,after);self.assertEqual(len(after),1)
 def test_projection_is_only_explicit_owner_and_roundtrips(self):
  for row in r.read(r.DEST/'fixture_corrections.json'):
   original=r.graph(row['before']);actual=r.graph(row['after'])
   projected,moves,errors=r.project(original,row['requirement_id'])
   self.assertFalse(errors);self.assertEqual(set(projected),set(actual))
   self.assertEqual(set(r.legacy_logic_view(actual,moves)),set(original))
   for m in moves:
    old=next(iter(r.audit.load_triples([' '.join(m['old'])+' .'])))
    new=next(iter(r.audit.load_triples([' '.join(m['new'])+' .'])))
    self.assertEqual(old[1:],new[1:]);self.assertEqual(r.INDEX['termOwners'][row['requirement_id']][r.local(old[1])],'ship')
 def test_old_invalid_repairs_withdrawn_and_source_scope_not_invented(self):
  canonical=0
  for e in self.plan['entries']:
   cid=e['case_id'];current=self.after[cid]
   if cid=='TRF-050-F05':continue
   self.assertTrue(e['old_repair_invalid']);self.assertEqual(e['old_repair_sha256'],r.sha(e['old_repair_path']))
   if e['requirement_id']=='TRF-130':
    self.assertEqual(current['state'],'BLOCKED');self.assertIsNone(current['independent_repaired_valid'])
    self.assertIsNone(e['repaired_oracle']['valid']);self.assertTrue(e['repaired_oracle']['open_declared_input_scope'])
    self.assertFalse(list(r.graph(e['repaired_fixture']).triples((None,r.N.maximumContinuousRatingPower,None))))
   else:
    canonical+=1;self.assertTrue(current['independent_repaired_valid'])
    self.assertNotEqual(current['repaired_fixture'],e['old_repair_path'])
    self.assertTrue(e['repaired_oracle']['valid']);self.assertFalse(e['negative_oracle']['valid'])
    self.assertEqual(len({p for s,p in e['semantic_roots']}),1)
  self.assertEqual(canonical,20)
  for cid in self.plan['underspecified_cases']:
   self.assertEqual(self.after[cid]['state'],'BLOCKED');self.assertIsNone(self.after[cid]['independent_repaired_valid'])
  for cid in self.plan['known_population_counterfactuals']:self.assertFalse(self.after[cid]['independent_repaired_valid'])
 def test_strict_requires_intended_report_and_complete_repair_pass(self):
  for e in self.plan['entries']:
   x=self.after[e['case_id']]
   for v in x['workflows'].values():
    if v['status']=='STRICT_INTENDED_MATCH':
     self.assertIs(v['negative']['conforms'],False);self.assertIs(v['repaired']['conforms'],True)
     meaning=v['violation_reason_review'];self.assertTrue(meaning['intended']);self.assertFalse(meaning.get('unrelated'));self.assertFalse(meaning.get('unresolved'))
    if v['status'] in ['MISSED_INTENDED_DEFECT','MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE','NO_VERDICT','UNRESOLVED_REASON']:self.assertNotEqual(v['status'],'STRICT_INTENDED_MATCH')
 def test_trf050_domain_consequence_is_scoped_and_never_rerun(self):
  with patch.object(r.audit,'validate',side_effect=AssertionError('No execution allowed')):
   proof=r.causal_trf050(self.before['TRF-050-F05'])
  self.assertEqual(set(proof),set(r.audit.WORKFLOWS))
  for w,p in proof.items():
   self.assertTrue(p['legitimate_source_constraints_only']);self.assertEqual(self.after['TRF-050-F05']['workflows'][w]['status'],'STRICT_INTENDED_MATCH')
  original=r.reason_matcher.violations
  def unrelated(*args,**kwargs):
   ds=original(*args,**kwargs)
   ds.append(dict(focus='urn:unrelated',component='MinCountConstraintComponent',path='urn:unrelated'))
   return ds
  with patch.object(r.reason_matcher,'violations',side_effect=unrelated):
   with self.assertRaises(AssertionError):r.causal_trf050(self.before['TRF-050-F05'])
 def test_only_changed_inputs_executed_and_same_pair_both_workflows(self):
  self.assertEqual(len(self.executions),108)
  jobs=self.plan['validation_jobs'];self.assertEqual(Counter(j['kind'] for j in jobs),{'ordinary':65,'repaired':43})
  self.assertFalse(any(j['case_id']=='TRF-050-F05' for j in jobs))
  self.assertEqual(len({j['key'] for j in jobs}),len(jobs))
  for j in jobs:
   self.assertEqual(r.sha(j['shape']),j['shape_sha256'])
  for e in self.plan['entries']:
   if e['case_id']=='TRF-050-F05':continue
   for w in r.audit.WORKFLOWS:
    js=[j for j in jobs if j['case_id']==e['case_id'] and j['condition']==w and j['kind']=='repaired']
    if js:self.assertEqual(js[0]['data'],e['repaired_fixture'])
 def test_ordinary_is_separate_and_preserves_no_verdict(self):
  summary=r.read(r.DEST/'summary.json')['ordinary']
  for version in ['before','after']:
   self.assertEqual([x['cases'] for x in summary[version]],[2159,2159])
  for old,new in zip(summary['before'],summary['after']):self.assertEqual(old['no_verdict'],new['no_verdict'])
 def test_original_files_and_inputs_preserved(self):
  for name,h in r.read(r.DEST/'inputs.json').items():self.assertEqual(r.sha(name),h,name)
  for name,h in r.read(r.DEST/'protected_before.json').items():self.assertEqual(r.sha(name),h,name)

if __name__=='__main__':unittest.main(verbosity=2)
