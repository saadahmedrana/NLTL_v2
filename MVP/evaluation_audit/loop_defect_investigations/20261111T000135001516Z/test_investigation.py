"""Read-only evidence and synthetic checks; never replay a benchmark case."""
import ast,json,sys,hashlib,unittest,collections,io
from pathlib import Path
from rdflib import Graph,URIRef,Literal,Namespace,Variable,RDF,XSD
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.parserutils import CompValue
import pyshacl
D=Path(__file__).resolve().parent;ROOT=D.parents[2]
sys.path.insert(0,str(ROOT/'evaluation_audit'));import audit

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
class InvestigationChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.auth=read(D/'authority_snapshot.json');cls.static=read(D/'static_findings_with_diagnostic_evidence.json');cls.executions=read(D/'diagnostic_executions.json');cls.plan=read(D/'diagnostic_plan.json');cls.records=read(cls.auth['current_case_records'])
 def test_authoritative_inputs_unchanged(self):
  for p,h in read(D/'protected_inputs.json').items():self.assertEqual(sha(p),h,p)
  self.assertEqual(sum(r['state'] in ['COMPLETED','COMPLETED_PRIOR50'] for r in self.records.values()),553)
 def test_confirmed_operand_counts_are_shape_counts(self):
  core=[f for f in self.static if f['mechanism']!='RDFLIB_PLAIN_VS_XSD_STRING_COMPATIBILITY']
  self.assertEqual(len({(f['condition'],f['requirement_id']) for f in core}),29)
  self.assertEqual(len({f['requirement_id'] for f in core}),24)
  self.assertEqual(collections.Counter(w for w,q in {(f['condition'],f['requirement_id']) for f in core}),{'NO_SEMANTIC':17,'SINGLESHOT':12})
 def test_original_shapes_and_reference_code_unchanged(self):
  for s in read(D/'shape_inventory.json'):self.assertEqual(sha(s['path']),s['sha256'])
  for s in read(D/'implementation_provenance.json')['reference_files']:self.assertEqual(sha(s['path']),s['sha256'])
 def test_original_runs_not_fallback_contexts(self):
  trace=read(D/'execution_trace_audit.json');self.assertEqual(len(trace),536)
  for t in trace:
   self.assertIn('LUNA_NO_SEMANTIC_VALIDATOR' if t['condition']=='NO_SEMANTIC' else 'LUNA_CONTEXTUAL_SINGLESHOT',t['run'])
   self.assertEqual(t['roles'].get('generator'),1)
   self.assertEqual(t['roles'].get('validator',0),0);self.assertEqual(t['roles'].get('vocabulary_matcher',0),0)
  self.assertEqual(sum(t['roles'].get('syntax_repair',0) for t in trace if t['condition']=='NO_SEMANTIC'),60)
  self.assertEqual(sum(t['roles'].get('syntax_repair',0) for t in trace if t['condition']=='SINGLESHOT'),0)
 def test_operand_defects_were_actually_missed(self):
  trace={(t['condition'],t['requirement_id']):t for t in read(D/'execution_trace_audit.json')}
  for f in self.static:
   if f['mechanism']=='RDFLIB_PLAIN_VS_XSD_STRING_COMPATIBILITY':continue
   t=trace[f['condition'],f['requirement_id']]
   self.assertTrue(t['deterministic']['valid']);self.assertEqual(t['deterministic']['errors'],[])
 def test_only_changed_eligible_copies_executed(self):
  self.assertEqual(len(self.executions),130)
  rows=read(Path(self.auth['run_dir'])/'retained_rows.json');index={(r['condition'],r['case_id']):r for r in rows}
  for x in self.executions:
   arm,w,cid,mode=x['key'].split('/');self.assertTrue(index[w,cid]['original_eligible'])
   self.assertTrue(Path(x['shape']).is_relative_to(D/'shapes'));self.assertIsInstance(x['result']['conforms'],bool)
  self.assertEqual(len({x['key'] for x in self.executions}),130)
 def test_no_verdict_cannot_gain_offline_credit(self):
  rows=list(__import__('csv').DictReader(io.StringIO((D/'diagnostic_case_results.csv').read_text())))
  selected=[r for r in rows if r['arm']=='paired_boolean_branch' and r['condition']=='SINGLESHOT' and r.get('after_strict')]
  self.assertEqual(len(selected),4);self.assertEqual({r['after_strict'] for r in selected},{'NO_VERDICT'})
  self.assertFalse(any('/SINGLESHOT/IMO26-014-' in x['key'] for x in self.executions))
 def test_representation_fixes_shared_and_negative_regressions_not_hidden(self):
  rows=list(__import__('csv').DictReader(io.StringIO((D/'diagnostic_summary.csv').read_text())));s={ (r['arm'],r['workflow']):r for r in rows }
  self.assertEqual(int(s['canonical_operands','NLTL_v2']['strict_recoveries']),16)
  self.assertEqual(int(s['canonical_operands','Single-shot']['strict_recoveries']),8)
  self.assertEqual(int(s['canonical_operands','Single-shot']['ordinary_regressions']),4)
  self.assertEqual(int(s['scope_only','NLTL_v2']['positive_regressions']),2)
  for w in ['NLTL_v2','Single-shot']:self.assertEqual(int(s['scope_and_additional_power',w]['strict_recoveries']),0)
 def test_common_subset_and_deduplicated_gains(self):
  d=read(D/'deduplicated_diagnostic_gains.json');self.assertEqual(d['NLTL_v2']['reviewed_pair_cases'],d['Single-shot']['reviewed_pair_cases'])
  self.assertEqual(len(d['NLTL_v2']['reviewed_pair_cases']),28)
  self.assertEqual((d['NLTL_v2']['strict_gain_count'],d['Single-shot']['strict_gain_count']),(20,16))
  for r in d.values():self.assertEqual(len(r['strict_gain_cases']),len(set(r['strict_gain_cases'])))
 def test_rdf_string_compatibility_probe_uses_no_fixture(self):
  E=Namespace('urn:synthetic:');data=Graph();data.add((E.x,RDF.type,E.T));data.add((E.x,E.p,Literal('canonical value',datatype=XSD.string)))
  sg=Graph();sg.add((E.shape,audit.S.targetClass,E.T));sg.add((E.shape,audit.S.property,E.ps));sg.add((E.ps,audit.S.path,E.p));sg.add((E.ps,audit.S.hasValue,Literal('canonical value')))
  self.assertFalse(pyshacl.validate(data,shacl_graph=sg)[0]);sg.set((E.ps,audit.S.hasValue,Literal('canonical value',datatype=XSD.string)))
  self.assertTrue(pyshacl.validate(data,shacl_graph=sg)[0])
 def test_scope_analysis_and_minimal_repair_use_algebra_not_messages(self):
  tree=ast.parse((D/'scan_scope.py').read_text());ns={}
  declarations=[x for x in tree.body if isinstance(x,(ast.Import,ast.ImportFrom,ast.FunctionDef))]
  exec(compile(ast.Module(body=declarations,type_ignores=[]),'scope_analysis_functions','exec'),ns)
  flags=read(D/'scope_flags.json');self.assertEqual(len(flags),2);self.assertEqual({x['requirement_id'] for x in flags},{'TRF-017'})
  shape=D/'shapes/scope_only/NO_SEMANTIC/TRF-017.ttl';g=Graph().parse(shape)
  for q in g.objects(None,audit.S.select):
   for node,path in ns['walk'](prepareQuery(str(q)).algebra):
    if not isinstance(node,CompValue) or node.name!='Filter':continue
    e=node['expr']
    if not isinstance(e,CompValue) or e.name not in ['RelationalExpression','ConditionalAndExpression']:continue
    required=[e] if e.name=='RelationalExpression' else [z for z in [e['expr']]+list(e.get('other',[])) if isinstance(z,CompValue) and z.name=='RelationalExpression']
    free=set().union(*(ns['vars_expr'](z) for z in required))-ns['bound'](node['p'])-{'this'}
    self.assertFalse(free)
 def test_overturned_ownership_not_reused_as_shape_blame(self):
  fs=read(D/'manual_confirmations.json');owners=[f for f in fs if f['family']=='OWNER_PATH']
  self.assertEqual({(f['condition'],f['requirement_id']) for f in owners},{('SINGLESHOT','TRF-036')})
  self.assertFalse(any(f['requirement_id']=='TRF-050' for f in fs))
  for w in audit.WORKFLOWS:self.assertEqual(self.records['TRF-050-F05']['workflows'][w]['status'],'STRICT_INTENDED_MATCH')
 def test_all_current_mismatches_receive_a_non_guessed_disposition(self):
  rows=list(__import__('csv').DictReader(io.StringIO((D/'all_current_mismatch_dispositions.csv').read_text())))
  self.assertEqual(len(rows),355);self.assertEqual(len({(r['condition'],r['case_id']) for r in rows}),355)
  self.assertTrue(any(r['disposition']=='MECHANISM_NOT_ESTABLISHED_DO_NOT_REUSE_PROVISIONAL_CAUSE' for r in rows))

if __name__=='__main__':unittest.main(verbosity=2)
