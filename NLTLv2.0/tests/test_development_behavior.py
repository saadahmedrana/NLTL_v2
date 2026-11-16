import unittest,os,pathlib,json,copy,tempfile,shutil
from unittest.mock import patch
from nltlv2.core import Project,GenerationProject,Candidate,load
from nltlv2.schema import Schema
from nltlv2.development_checks import assess,expected,graph_for,contracts
from nltlv2.runner import Runner
from nltlv2.transport import ScriptedTransport
from nltlv2.requests import repair_request,assert_integrity

PREFIX='@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix n: <https://w3id.org/nltl/vocab#> . @prefix q: <http://qudt.org/schema/qudt/> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n'
def iri(x):return '<'+x+'>'
def control(c):
 """Test-only generic control builder; no evaluator/reference-shape imports or IDs."""
 def quantity(field):
  return 'sh:property [ sh:path '+iri(field['path'][-1])+' ; sh:minCount 1 ; sh:node [ sh:property [ sh:path q:numericValue ; sh:minCount 1 ; sh:datatype xsd:decimal ] ; sh:property [ sh:path q:unit ; sh:hasValue '+iri(field['unit'])+' ] ] ]'
 fields=c['fields'];op=c['operation'];parts=[]
 if op=='conditional_value':
  selector=iri(fields['selector']['path'][0]);value=iri(fields['value']['path'][0]);match='sh:property [ sh:path '+selector+' ; sh:hasValue '+iri(c['applicable_value'])+' ]'
  parts=['sh:property [ sh:path '+selector+' ; sh:minCount 1 ]','sh:or ( [ '+match+' ; sh:property [ sh:path '+value+' ; sh:hasValue '+iri(c['required_value'])+' ] ] [ sh:not [ '+match+' ] ] )']
 else:
  for name,field in fields.items():
   text=quantity(field)
   if name=='items':
    if op=='constant_equal':text=text.replace('sh:datatype xsd:decimal','sh:datatype xsd:decimal ; sh:minInclusive '+c['constant']+' ; sh:maxInclusive '+c['constant'])
    text='sh:property [ sh:path '+iri(field['path'][0])+' ; sh:minCount 1 ; sh:node [ '+text+' ] ]'
   parts.append(text)
  def num(f):return '/'.join(iri(x) for x in f['path'])+'/q:numericValue'
  if op=='quantity_equal':queries=['SELECT $this WHERE { $this '+num(fields['result'])+' ?r . $this '+num(fields['operand'])+' ?v . FILTER(?r != ?v) }']
  elif op=='max_equal':queries=['SELECT $this WHERE { $this '+num(fields['result'])+' ?r . $this '+num(fields['items'])+' ?v . FILTER(?v > ?r) }','SELECT $this WHERE { $this '+num(fields['result'])+' ?r . FILTER NOT EXISTS { $this '+num(fields['items'])+' ?v . FILTER(?v = ?r) } }']
  else:queries=[]
  for query in queries:parts.append('sh:sparql [ sh:select """PREFIX q: <http://qudt.org/schema/qudt/> '+query+'""" ]')
 return PREFIX+'<urn:development:control> a sh:NodeShape ; sh:targetClass '+iri(c['target_class'])+' ; '+' ; '.join(parts)+' .\n'
def wrap(s):return '<BEGIN_SHACL>\n'+s+'<END_SHACL>\n'
ACCEPT=json.dumps(dict(decision='ACCEPT',issues=[]))

class DevelopmentBehaviorTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.p=Project(os.environ['NLTL_TEST_PROJECT']);cls.s=Schema(cls.p);cls.contracts=contracts(cls.s);cls.out=pathlib.Path(os.environ['NLTL_TEST_OUTPUT'])
 def test_correct_controls_no_false_alarm(self):
  for rid,c in self.contracts.items():
   with self.subTest(rid=rid):
    code=control(c);fs,report=assess(Candidate(1,code,code),self.s,rid);self.assertEqual(fs,[],json.dumps(report));self.assertEqual(report['status'],'FINITE_WITNESSES_PASSED');self.assertFalse(report['complete_verification']);self.assertTrue(report['unchecked'])
 def test_missing_all_logic_detected_for_every_operator(self):
  for rid,c in self.contracts.items():
   code=PREFIX+'<urn:development:empty> a sh:NodeShape ; sh:targetClass '+iri(c['target_class'])+' .'
   fs,r=assess(Candidate(1,code,code),self.s,rid);self.assertTrue(fs);self.assertTrue(all(f.confirmed for f in fs));self.assertTrue(any(row['status']=='CONFIRMED_COUNTEREXAMPLE' and not row['expected_conforms'] for row in r['witnesses']))
 def test_source_arithmetic_and_boundary_oracles(self):
  for rid,c in self.contracts.items():
   statuses={v['id']:expected(c,v['values']) for v in c['vectors']};self.assertIn(True,statuses.values());self.assertIn(False,statuses.values());self.assertTrue(all(not value for key,value in statuses.items() if key.startswith('missing_') or key=='both_missing'))
 def test_wrong_maximum_direction(self):
  c=self.contracts['I2-004'];code=control(c).replace('FILTER(?v > ?r)','FILTER(?v < ?r)');fs,r=assess(Candidate(1,code,code),self.s,'I2-004');self.assertTrue(fs);self.assertTrue(any(x['expected_conforms'] and x['status']=='CONFIRMED_COUNTEREXAMPLE' for x in r['witnesses']))
 def test_maximum_needs_result_equality(self):
  c=self.contracts['I2-004'];code=control(c);start=code.index(' ; sh:sparql',code.index('FILTER(?v > ?r)'));code=code[:start]+' .\n';fs,r=assess(Candidate(1,code,code),self.s,'I2-004');self.assertIn('above_max',[v['witness_id'] for v in r['witnesses'] if v['status']=='CONFIRMED_COUNTEREXAMPLE'])
 def test_multiple_cases_not_maxcount_one(self):
  c=self.contracts['I2-004'];code=control(c).replace('sh:path '+iri(c['fields']['items']['path'][0]),'sh:maxCount 1 ; sh:path '+iri(c['fields']['items']['path'][0]));fs,r=assess(Candidate(1,code,code),self.s,'I2-004');self.assertIn('max_last',[x['witness_id'] for x in r['witnesses'] if x['status']=='CONFIRMED_COUNTEREXAMPLE'])
 def test_constant_faults_on_either_side(self):
  c=self.contracts['I2-005']
  for marker in ['sh:minInclusive 7','sh:maxInclusive 7']:
   code=control(c).replace(marker,marker.replace('7','6' if 'min' in marker else '8'));fs,r=assess(Candidate(1,code,code),self.s,'I2-005');self.assertTrue(fs)
 def test_missing_sampled_point_detected(self):
  c=self.contracts['I2-005'];code=control(c).replace(iri(c['fields']['items']['path'][0])+' ; sh:minCount 1',iri(c['fields']['items']['path'][0]));fs,r=assess(Candidate(1,code,code),self.s,'I2-005');self.assertIn('missing_points',[x['witness_id'] for x in r['witnesses'] if x['status']=='CONFIRMED_COUNTEREXAMPLE'])
 def test_missing_numeric_operands_detected(self):
  for rid,c in self.contracts.items():
   if c['operation']=='conditional_value':continue
   code=control(c).replace('sh:path q:numericValue ; sh:minCount 1','sh:path q:numericValue');fs,r=assess(Candidate(1,code,code),self.s,rid);self.assertTrue(fs)
 def test_reversed_equality_detected(self):
  c=self.contracts['TRF-035'];code=control(c).replace('FILTER(?r != ?v)','FILTER(?r = ?v)');fs,r=assess(Candidate(1,code,code),self.s,'TRF-035');self.assertTrue(fs)
 def test_missing_selector_readiness_detected(self):
  c=self.contracts['IMO-001'];code=control(c).replace(' ; sh:minCount 1','');fs,r=assess(Candidate(1,code,code),self.s,'IMO-001');self.assertIn('missing_selector',[x['witness_id'] for x in r['witnesses'] if x['status']=='CONFIRMED_COUNTEREXAMPLE'])
 def test_unconditional_category_a_rejected(self):
  c=self.contracts['IMO-001'];code=PREFIX+'<urn:development:test> a sh:NodeShape ; sh:targetClass '+iri(c['target_class'])+' ; sh:property [ sh:path '+iri(c['fields']['selector']['path'][0])+' ; sh:minCount 1 ] ; sh:property [ sh:path '+iri(c['fields']['value']['path'][0])+' ; sh:hasValue '+iri(c['required_value'])+' ] .';fs,r=assess(Candidate(1,code,code),self.s,'IMO-001');self.assertIn('nonapplicable',[x['witness_id'] for x in r['witnesses'] if x['status']=='CONFIRMED_COUNTEREXAMPLE'])
 def test_execution_problem_is_not_conformance_failure(self):
  with patch('pyshacl.validate',side_effect=RuntimeError('synthetic local execution failure')):
   code=control(self.contracts['I2-005']);fs,r=assess(Candidate(1,code,code),self.s,'I2-005',use_cache=False);self.assertEqual(r['status'],'UNRESOLVED_EXECUTION');self.assertTrue(all(not f.confirmed for f in fs))
 def test_production_route_latest_candidate_and_complete_evidence(self):
  c=self.contracts['TRF-035'];good=control(c);bad=good.replace('FILTER(?r != ?v)','FILTER(?r = ?v)');t=ScriptedTransport([wrap(bad),wrap(good),ACCEPT]);dest=self.out/self._testMethodName;dest.mkdir();result=Runner(self.p,self.p.config('configs/nltl.json'),t,dest).run('TRF-035');self.assertEqual(result['accepted_version'],2);request=t.calls[1];self.assertEqual(request['route'],'targeted_repair');self.assertEqual(request['payload']['previous_candidate'],bad)
  for f in request['payload']['current_findings']:
   detail=json.loads(f['diagnostic']);self.assertIn('original_validation_log',detail);self.assertIn('source',detail);self.assertIn('observed_conforms',detail);self.assertIn('expected_conforms',detail);self.assertNotIn('evaluation/',f['diagnostic']);self.assertTrue(f['location']);self.assertIn(f['excerpt'],bad)
  self.assertFalse(result['complete_verification']);self.assertTrue(result['verification_coverage']['unchecked']);self.assertEqual(result['verification_coverage']['status'],'FINITE_WITNESSES_PASSED');self.assertTrue((dest/'request_002_integrity.json').exists())
 def test_firewall_denies_external_inputs(self):
  p=GenerationProject(self.p.root)
  for path in ['evaluation/fixtures/test.ttl','outputs/experiments/test.json','results/table.csv']:
   with self.assertRaisesRegex(ValueError,'EVALUATION_RESOURCE_FORBIDDEN'):p.path(path)
  s=Schema(p)
  for rid,c in self.contracts.items():self.assertFalse(assess(Candidate(1,control(c),control(c)),s,rid)[0])
 def test_witnesses_work_with_evaluation_directory_absent(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp)
   for name in ['schema','data','prompts','configs']:shutil.copytree(self.p.path(name),root/name)
   shutil.copyfile(self.p.path('pyproject.toml'),root/'pyproject.toml');p=GenerationProject(root);s=Schema(p);self.assertFalse((root/'evaluation').exists());c=self.contracts['I2-005'];code=control(c);self.assertEqual(assess(Candidate(1,code,code),s,'I2-005')[0],[])
 def test_unconfigured_obligation_stays_unchecked(self):
  fs,r=assess(Candidate(1,'',''),self.s,'I2-042');self.assertEqual(fs,[]);self.assertFalse(r['complete_verification']);self.assertEqual(r['status'],'NOT_CONFIGURED')

 def test_five_manifest_exact_subset_and_preserved_six(self):
  from nltlv2.preflight import validate_manifest
  m=load(self.p.path('configs/five_requirement_development_pilot.json'));r=validate_manifest(self.p,m,require_ready=True);self.assertTrue(r['ready_for_dispatch']);self.assertEqual(len(m['requirements']),5);self.assertEqual(m['deferred_requirements'],['I2-042']);self.assertEqual((m['evaluation']['cases'],m['evaluation']['positive'],m['evaluation']['negative'],m['evaluation']['repaired_count']),(30,14,16,16));core=load(self.p.path('evaluation/selections/regression_core.json'));five=load(self.p.path(m['evaluation']['selection']));self.assertEqual(five['cases'],[c for c in core['cases'] if c['requirement_id'] in m['requirements']]);self.assertEqual(len(core['cases']),37)
 def test_reviewer_accept_does_not_erase_limits(self):
  c=self.contracts['I2-005'];code=control(c);dest=self.out/self._testMethodName;dest.mkdir();t=ScriptedTransport([wrap(code),ACCEPT]);r=Runner(self.p,self.p.config('configs/nltl.json'),t,dest).run('I2-005');self.assertEqual(r['status'],'ACCEPTED');self.assertFalse(r['complete_verification']);self.assertFalse(r['history'][0]['development_coverage']['complete_verification']);self.assertTrue(r['history'][0]['development_coverage']['unchecked'])
