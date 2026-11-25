"""Offline evaluator plumbing controls, not regulatory accuracy tests."""
import unittest,pathlib,importlib.util,tempfile,json,types,copy
from rdflib import Graph,Literal,URIRef,RDF,RDFS,XSD
from nltlv2.core import GenerationProject,offline_network_guard
from nltlv2.admission import validate_declaration,validate_data_scope
import test_general_pipeline as gp
from test_general_pipeline import software_admission
ROOT=pathlib.Path(__file__).resolve().parents[1]
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
expanded=module('expanded_generic','evaluation/expanded_development.py')
independent=module('independent_generic','evaluation/independent.py')
class ExpandedEvaluationControls(unittest.TestCase):
 def test_domain_range_subproperty_and_class_closure(self):
  o=Graph().parse(data='@prefix r:<urn:software:>. @prefix s:<http://www.w3.org/2000/01/rdf-schema#>. r:p s:subPropertyOf r:parent. r:parent s:domain r:Owner; s:range r:Child. r:Child s:subClassOf r:Record.',format='turtle')
  g=Graph().parse(data='@prefix r:<urn:software:>. r:a r:p r:b.',format='turtle');original=set(g);result=expanded.representation_graph(g,o)
  self.assertIn((URIRef('urn:software:a'),RDF.type,URIRef('urn:software:Owner')),result);self.assertIn((URIRef('urn:software:b'),RDF.type,URIRef('urn:software:Record')),result);self.assertEqual(set(g),original)
 def test_inferred_equal_literals_do_not_change_original_fields(self):
  g=Graph();s=URIRef('urn:software:item');p=URIRef('urn:software:value');b=URIRef('urn:software:flag');g.add((s,p,Literal('1.00',datatype=XSD.decimal,normalize=False)));g.add((s,b,Literal(True)))
  out=expanded.representation_graph(g,Graph());self.assertEqual(list(out.objects(s,p)),list(g.objects(s,p)));self.assertEqual(list(out.objects(s,b)),list(g.objects(s,b)));self.assertEqual(len(list(out.objects(s,p))),1)
 def test_unrelated_ontology_individual_is_not_added_to_fixture(self):
  o=Graph();o.add((URIRef('urn:software:outside'),RDF.type,URIRef('urn:software:Record')));out=expanded.representation_graph(Graph(),o);self.assertNotIn((URIRef('urn:software:outside'),RDF.type,URIRef('urn:software:Record')),out)
 def test_unknown_oracle_is_unresolved_not_passed(self):
  self.assertIsNone(expanded.oracle(Graph(),'UNKNOWN-GENERIC',Graph())['conforms'])
 def test_expansion_does_not_manufacture_strict_attribution_credit(self):
  self.assertEqual(independent.strict_status(False,True,True,False,attribution_resolved=False),'UNRESOLVED_ATTRIBUTION')
 def test_generation_project_blocks_external_evaluation_inputs(self):
  p=GenerationProject(ROOT)
  for file in ['evaluation/expanded_development.py','evaluation/fixtures/twenty_20261125/any.ttl','outputs/audits/any.json']:
   with self.assertRaises(ValueError):p.path(file)
 def test_pending_scope_is_not_executable_and_cannot_admit_data(self):
  base=gp.GeneralPipelineTests();base.setUp()
  try:
   software_admission(base);decl=json.loads((base.root/'data/admissions/software.json').read_text());decl['approval']['status']='PENDING_USER_APPROVAL'
   result=validate_declaration(decl,base.schema,'NOVEL-RULE') if hasattr(base,'schema') else validate_declaration(decl,__import__('nltlv2.schema',fromlist=['Schema']).Schema(base.p),'NOVEL-RULE')
   self.assertFalse(result['valid']);self.assertTrue(any(e['path']=='$.approval' for e in result['errors']));self.assertFalse(validate_data_scope(Graph(),Graph(),dict(declaration=decl),{},'0'*64)['valid'])
  finally:base.tearDown()
class PlannedEvaluationAccounting(unittest.TestCase):
 def summary(self,rows):return module('planned_summary','evaluation/evaluate_hosted_shared_start.py').requirement_summary(rows)
 def test_not_run_is_not_a_model_error_or_no_verdict(self):
  x=self.summary([dict(ordinary_agreement=None,conforms=None,execution_status='NOT_RUN')]);self.assertEqual((x['cases'],x['not_run'],x['no_verdict'],x['wrong']),(1,1,0,0));self.assertIsNone(x['delivered_accuracy'])
 def test_delivery_accuracy_and_planned_credit_are_separate(self):
  x=self.summary([dict(ordinary_agreement=True,conforms=True,execution_status='EVALUATED_UNCHANGED'),dict(ordinary_agreement=None,conforms=None,execution_status='NO_VERDICT')]);self.assertEqual(x['delivered_accuracy'],1);self.assertEqual(x['ordinary_accuracy'],.5);self.assertEqual(x['no_verdict'],1)
 def test_wrong_verdict_counts_and_missing_verdict_does_not(self):
  x=self.summary([dict(ordinary_agreement=False,conforms=False,execution_status='EVALUATED_UNCHANGED')]);self.assertEqual(x['wrong'],1);self.assertEqual(x['delivered_accuracy'],0)
if __name__=='__main__':unittest.main()
