"""Read-only ownership adjudication tests. No validator or query execution."""
import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from rdflib import Graph,URIRef,Literal,RDF,RDFS
OUT=str(Path(__file__).resolve().parent);spec=importlib.util.spec_from_file_location('owner_audit',str(Path(OUT)/'ownership_audit.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class OwnershipAuditTests(unittest.TestCase):
 def test_broad_domain_and_prompt_fallback_do_not_set_owner(self):
  schema=m.schema_info('I2-008','totalGlancingImpactForce')
  self.assertEqual(schema['domains'],[str(m.N.benchmarkEntity)]);self.assertIsNone(schema['explicit_owner_class'])
  finding=m.classify('I2-008','totalGlancingImpactForce',schema,dict(occurrences=[]),[],[],Graph())
  self.assertEqual(finding[0],'SCHEMA_UNDERSPECIFIED')
 def test_rdfs_domain_adds_type_instead_of_exclusive_owner(self):
  g=Graph();frame=URIRef('urn:frame');g.add((frame,RDF.type,m.N.frame));g.add((frame,m.N.frameShellWeldType,m.N.doubleContinuousWeld))
  types,proof=m.rdfs_types(g,frame)
  self.assertIn(m.N.frame,types);self.assertIn(m.N.frameAttachmentRecord,types)
  self.assertTrue(any(p['rule']=='RDFS_DOMAIN_TYPING_NOT_EXCLUSIVE_PLACEMENT' for p in proof))
 def test_endpoint_and_oblique_case_are_calculation_case_subclasses(self):
  for c in [m.N.interpolationPoint,m.N.obliquePlatingInterpolationCase]:self.assertIn(m.N.calculationCase,m.supertypes(c))
 def test_contract_explicit_ship_owner_is_not_replaced_by_fixture(self):
  schema=m.schema_info('TRF-130','totalRelevantEnginePower');g=Graph();owner=URIRef('urn:chest');q=URIRef('urn:q');g.add((owner,RDF.type,m.N.inletChest));g.add((owner,m.N.totalRelevantEnginePower,q))
  shape=dict(occurrences=[dict(owner_class_hints=[str(m.N.ship)])]);data=m.fixture_property(g,m.N.totalRelevantEnginePower)
  self.assertEqual(m.classify('TRF-130','totalRelevantEnginePower',schema,shape,data,[],g)[0],'FIXTURE_VIOLATES_CLEAR_SCHEMA')
 def test_missing_values_are_not_values_on_another_node(self):
  g=Graph();self.assertEqual(m.fixture_property(g,m.N.iceClass),[])
  g.add((URIRef('urn:parameters'),m.N.iceClass,m.N.iceClassIa));info=m.fixture_property(g,m.N.iceClass)
  self.assertEqual(info[0]['owner'],'urn:parameters');self.assertTrue(info[0]['values'])
 def test_shape_complete_nested_path_is_retained(self):
  g=Graph();r=URIRef('urn:shape');child=URIRef('urn:child');p=URIRef('urn:property');g.add((r,m.S.targetClass,m.N.ship));g.add((r,m.S.property,p));g.add((p,m.S.path,m.N.hasPlating));g.add((p,m.S.node,child));leaf=URIRef('urn:leaf');g.add((child,m.S.property,leaf));g.add((leaf,m.S.path,m.N.yieldStrength))
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'synthetic.ttl';g.serialize(f,format='turtle')
   info=m.shape_info(str(f),str(m.N.yieldStrength))
  self.assertEqual(info['occurrences'][0]['complete_property_path'],[str(m.N.hasPlating),str(m.N.yieldStrength)])
 def test_record_target_is_not_frame_target_despite_report_focus(self):
  row=next(v for (w,c),v in m.ROWS.items() if w=='NO_SEMANTIC' and v['requirement_id']=='TRF-050')
  with patch.object(Graph,'query',side_effect=AssertionError('No query execution')),patch.object(m.audit,'validate',side_effect=AssertionError('No validation')):
   shape=m.shape_info(row['shape_path'],str(m.N.shellPlateButtCrossing))
  self.assertTrue(shape['occurrences']);self.assertTrue(all(o['owner_class_hints']==[str(m.N.frameAttachmentRecord)] for o in shape['occurrences']))
 def test_ontology_range_does_not_identify_owner(self):
  schema=m.schema_info('I2-052','interpolatedValue')
  self.assertEqual(schema['ranges'],['http://www.w3.org/2001/XMLSchema#string']);self.assertIsNone(schema['explicit_owner_class'])
 def test_source_clause_disambiguation_includes_parent_scope(self):
  source=m.source_info('IMO-049');self.assertEqual(source['source_location_status'],'REVIEWED_FULL_CLAUSE_AND_PARENT_SCOPE')
  self.assertIn('for ships ice strengthened',source['source_excerpts'][0]['excerpt'])
  source=m.source_info('I2-052');self.assertIn('I2.13.3.1',source['source_excerpts'][0]['excerpt']);self.assertNotIn('I2.13.4.1',source['source_excerpts'][0]['excerpt'])
 def test_classification_has_no_expected_label_or_conformance_input(self):
  import inspect
  params=inspect.signature(m.classify).parameters
  self.assertFalse(any(k in params for k in ['expected','label','conforms','status','pass_graph']))

 def test_missing_original_value_is_not_called_wrong_owner(self):
  schema=m.schema_info('I2-006','aftSectionDesignBasis')
  result=m.classify('I2-006','aftSectionDesignBasis',schema,dict(occurrences=[]),[],[dict(owner='urn:ship')],Graph())
  self.assertEqual(result[0],'BOTH_CONFORM_NO_OWNERSHIP_ERROR');self.assertIn('missing, not on a wrong owner',result[3])
 def test_current_flag_inventory_is_complete(self):
  rows=json.loads((Path(OUT)/'current_provisional_cause_ledger.json').read_text())
  self.assertEqual(len(rows),115);self.assertEqual(len({r['case_id'] for r in rows}),89);self.assertEqual(len({r['requirement_id'] for r in rows}),20)

if __name__=='__main__':unittest.main()
