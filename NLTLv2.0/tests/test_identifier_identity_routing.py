"""Generic identity routing controls, not regulatory interpretation evidence."""
import copy,unittest
import test_general_pipeline as base
import test_reviewer_routing as existing
from nltlv2.core import Candidate
from nltlv2.schema import Schema,N
from nltlv2.requests import review_proposal_routing

class IdentifierIdentityRouting(unittest.TestCase):
 setUp=existing.ReviewerRoutingControls.setUp;tearDown=base.GeneralPipelineTests.tearDown;write=base.GeneralPipelineTests.write
 def candidate(self,ns=str(N)):return Candidate(1,base.GOOD+'\n@prefix vocab: <'+ns+'> .\n@prefix qudt: <http://qudt.org/schema/qudt/> .\n','')
 def route(self,prop,path,c=None,ctx=None,**extra):
  obj={'issues':[dict(issue_id='synthetic',category='TECHNICAL_REPRESENTATION_ERROR',operands=[dict(property=prop,proposed_path=path,proposed_path_role=extra.pop('role','PROPERTY'),**extra)])]};original=copy.deepcopy(obj);out=review_proposal_routing(obj,self.s,'NOVEL-RULE',ctx or self.s.context('NOVEL-RULE'),candidate=c or self.candidate());self.assertEqual(obj,original);return out
 def test_same_explicit_candidate_prefix_and_full_iri_identity(self):
  a=self.route('vocab:bridgeWingsEnclosed',['vocab:bridgeWingsEnclosed']);b=self.route(str(N.bridgeWingsEnclosed),[str(N.bridgeWingsEnclosed)]);self.assertEqual(a['route'],b['route']);self.assertEqual(a['route'],'VALID');self.assertEqual(a['identifier_resolutions'][0]['resolved_property'],str(N.bridgeWingsEnclosed))
 def test_unique_supplied_localname_resolves_without_guessing(self):
  self.assertEqual(self.route('bridgeWingsEnclosed',['bridgeWingsEnclosed'])['route'],'VALID')
 def test_unknown_identifiers_and_undeclared_prefix_stay_blocking(self):
  for prop,path in [('absent:bridgeWingsEnclosed',['absent:bridgeWingsEnclosed']),('vocab:unknown',['vocab:unknown']),('unknown',['unknown']),('urn:foreign:bridgeWingsEnclosed',['urn:foreign:bridgeWingsEnclosed'])]:self.assertEqual(self.route(prop,path)['route'],'CONFLICT')
 def test_same_local_spelling_in_foreign_namespace_does_not_match(self):
  self.assertEqual(self.route('vocab:bridgeWingsEnclosed',['vocab:bridgeWingsEnclosed'],c=self.candidate('urn:foreign:'))['route'],'CONFLICT')
 def test_no_candidate_namespace_does_not_assume_prefix(self):
  obj={'issues':[dict(issue_id='x',operands=[dict(property='vocab:bridgeWingsEnclosed',proposed_path=['vocab:bridgeWingsEnclosed'])])]};self.assertEqual(review_proposal_routing(obj,self.s,'NOVEL-RULE',self.s.context('NOVEL-RULE'))['route'],'CONFLICT')
 def test_property_path_mismatch_is_still_detected(self):
  result=self.route('vocab:bridgeWingsEnclosed',['vocab:hasComponent','vocab:componentValue']);self.assertEqual(result['route'],'CORRECT_RESPONSE');self.assertEqual(result['correctable'][0]['code'],'INCONSISTENT_REVIEWER_PROPERTY_PATH_PAIRING')
 def test_unsupported_path_and_datatype_remain_blocking(self):
  self.assertEqual(self.route('vocab:bridgeWingsEnclosed',['vocab:unknown'])['route'],'CONFLICT');self.assertEqual(self.route('vocab:bridgeWingsEnclosed',['vocab:bridgeWingsEnclosed'],proposed_datatype='http://www.w3.org/2001/XMLSchema#decimal')['route'],'CONFLICT')
 def test_alias_resolution_requires_supplied_mapping_identity(self):
  ctx=self.s.context('NOVEL-RULE');ctx['contract']['owners']={};self.assertEqual(self.route('vocab:bridgeWingsEnclosed',['vocab:bridgeWingsEnclosed'],ctx=ctx)['route'],'CONFLICT')
