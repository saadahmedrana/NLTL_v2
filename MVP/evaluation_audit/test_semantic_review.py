"""Static semantic-review checks; never run historical SHACL validations."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from rdflib import Graph,URIRef,BNode,Literal,RDF,XSD
from rdflib.collection import Collection
sys.path.insert(0,str(Path(__file__).resolve().parent))
import semantic_review as m

class StaticSemanticsTests(unittest.TestCase):
 def example(self):
  sg,bad,good=Graph(),Graph(),Graph();source=URIRef('urn:shape');owner=URIRef('urn:ship');head=BNode()
  sg.add((source,m.S['or'],head));branches=[BNode(),BNode()];Collection(sg,head,branches)
  guard=m.N.iceCapabilityMethodologyApplicable;field=m.N.certificateMethodologyReferencePresent
  def prop(branch,p,value):
   n=BNode();sg.add((branch,m.S.property,n));sg.add((n,m.S.path,p));sg.add((n,m.S.hasValue,Literal(value)))
  prop(branches[0],guard,False);prop(branches[1],guard,True);prop(branches[1],field,True)
  for g in [bad,good]:g.add((owner,guard,Literal(True)))
  bad.add((owner,field,Literal(False)));good.add((owner,field,Literal(True)))
  r=dict(requirement_id='IMO-018',selected_repair=dict(semantic_roots=[[str(owner),str(field)]]),source_evidence=dict(contract={}))
  v=dict(source_shape=str(source),component='OrConstraintComponent',focus=str(owner))
  return r,v,sg,bad,good,source,owner,branches
 def test_applicable_branch_is_selected_by_fixed_source_guard(self):
  r,v,sg,bad,good,src,owner,branches=self.example();proof=m.wrapper_proof(r,v,sg,bad,good)
  self.assertTrue(proof['resolved']);self.assertEqual(proof['branches'][0]['applicability'],'INACTIVE_BY_UNCHANGED_SOURCE_SELECTOR')
 def test_extra_failure_does_not_get_strict_credit(self):
  r,v,sg,bad,good,src,owner,branches=self.example();n=BNode();sg.add((branches[1],m.S.property,n));sg.add((n,m.S.path,m.N.otherUnrelatedField));sg.add((n,m.S.minCount,Literal(1)))
  self.assertFalse(m.wrapper_proof(r,v,sg,bad,good)['resolved'])
 def test_changed_applicability_is_not_branch_proof(self):
  r,v,sg,bad,good,src,owner,branches=self.example();r['selected_repair']['semantic_roots']=[[str(owner),str(m.N.iceCapabilityMethodologyApplicable)]];bad.set((owner,m.N.iceCapabilityMethodologyApplicable,Literal(False)))
  self.assertFalse(m.wrapper_proof(r,v,sg,bad,good)['resolved'])
 def test_unreviewed_nested_query_stays_unresolved(self):
  r,v,sg,bad,good,src,owner,branches=self.example();sg.add((branches[1],m.S.sparql,BNode()))
  self.assertFalse(m.wrapper_proof(r,v,sg,bad,good)['resolved'])
 def test_messages_are_not_a_matching_input(self):
  r,v,sg,bad,good,src,owner,branches=self.example();sg.add((src,m.S.message,Literal('entirely misleading')))
  self.assertTrue(m.wrapper_proof(r,v,sg,bad,good)['resolved'])
 def test_numeric_bound_needs_independent_source_binding(self):
  r=dict(requirement_id='I2-046',selected_repair=dict(semantic_roots=[['urn:member',str(m.N.internalStructureCorrosionAbrasionAddition)]]),source_evidence=dict(contract={}))
  leaf=dict(scope=r['selected_repair']['semantic_roots'][0],kind='minInclusive',owner='urn:q',path=str(m.Q.numericValue),expected='2')
  self.assertFalse(m.intended_leaf(r,leaf,Graph()));leaf['expected']='1.0';self.assertTrue(m.intended_leaf(r,leaf,Graph()))
 def test_unbound_query_hash_never_gets_credit(self):
  r=dict(requirement_id='I2-042',_workflow='NO_SEMANTIC',selected_repair=dict(semantic_roots=[['urn:x',str(m.N.flangeWidth)]]))
  q='SELECT ?this WHERE { ?this <https://w3id.org/nltl/vocab#flangeWidth> ?x }'
  v=dict(query=q,query_sha256=m.hashlib.sha256(q.encode()).hexdigest())
  self.assertFalse(m.query_proof(r,v)['resolved'])
 def test_inactive_nested_alternative_cannot_disable_whole_branch(self):
  r,v,sg,bad,good,src,owner,branches=self.example()
  # Move the false-guard property under a nested OR instead of direct branch.
  p=next(sg.objects(branches[0],m.S.property));sg.remove((branches[0],m.S.property,p));sub=BNode();nested=BNode();Collection(sg,nested,[sub]);sg.add((branches[0],m.S['or'],nested));sg.add((sub,m.S.property,p))
  self.assertFalse(m.wrapper_proof(r,v,sg,bad,good)['resolved'])
 def test_deactivated_constraints_are_not_failures(self):
  sg=Graph();s=BNode();sg.add((s,m.S.deactivated,Literal(True)));sg.add((s,m.S.minCount,Literal(2)))
  self.assertTrue(m.trace(sg,s,Graph(),URIRef('urn:x'))['ok'])
 def test_cached_case_review_cannot_invoke_validation_or_query_execution(self):
  for cid in ['I2-042-G-F01','IMO-018-F01','TRF-050-F05','TRF-075-F01']:
   r=m.audit.read(m.OUT/'records'/f'{cid}.json')
   # After application, use the stored original record rather than re-reviewing
   # a completed case. This test is intended to run before applying the plan.
   if r['state']!='BLOCKED':continue
   with patch.object(m.audit,'validate',side_effect=AssertionError('No validation allowed')),patch.object(Graph,'query',side_effect=AssertionError('No query execution allowed')):
    p=m.inspect_case(r)
   self.assertTrue(p['fully_resolved'],cid)
 def test_owner_mismatch_is_unrelated_even_if_repaired_passes(self):
  r=m.audit.read(m.OUT/'records/TRF-050-F05.json');bad=Graph().parse(r['negative_fixture']);good=Graph().parse(r['repaired_fixture'])
  v=dict(path=str(m.N.shellPlateButtCrossing),focus=r['selected_repair']['semantic_roots'][1][0])
  proof=m.wrong_owner_additional_failure(r,v,bad,good);self.assertTrue(proof['resolved']);self.assertEqual(proof['verdict'],'UNRELATED')

if __name__=='__main__':unittest.main()
