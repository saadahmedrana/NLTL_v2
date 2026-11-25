"""Generic prompt/reference controls. No regulatory answers or live calls."""
import json,copy,unittest
import test_general_pipeline as base
import test_semantic_handoff as handoff
import test_context_question_history as history
from nltlv2.review_protocol import reviewer_schema,response_correction_instruction
from nltlv2.review_validation import validate_review
from nltlv2.requests import parse_review,initial_request,repair_request,assert_integrity
from nltlv2.evidence import evidence_catalog
from nltlv2.core import Candidate,finding

class PromptClarityControls(unittest.TestCase):
 setUp=base.GeneralPipelineTests.setUp;tearDown=base.GeneralPipelineTests.tearDown;write=base.GeneralPipelineTests.write
 control=handoff.SmallHandoffControls.control;errors=handoff.SmallHandoffControls.errors
 capture=history.QuestionHistoryControls.capture;first=history.QuestionHistoryControls.first
 def test_prompt_roles_order_and_exact_generic_forms(self):
  text=self.p.path('prompts/reviewer.txt').read_text()
  for phrase in ['Regulation establishes','schema/mappings establish','Approved scope establishes','Candidate code is','Execution diagnostics establish'] :self.assertIn(phrase,text)
  positions=[text.index(str(i)+'. ') for i in range(1,7)];self.assertEqual(positions,sorted(positions))
  self.assertIn('"evidence":["E7"]',text);self.assertIn('"location":{"start":1,"end":1,"unit":"lines"}',text)
  s=reviewer_schema();ref=s['properties']['issues']['items']['properties']['evidence']['items'];self.assertNotIn('unit',ref['anyOf'][1]['properties'])
 def test_generic_evidence_forms_and_code_location_extract_exactly(self):
  for form in ['string','object']:
   c,ctx,o=self.control();eid=o['issues'][0]['evidence'][0];o['issues'][0]['evidence']=[eid if form=='string' else dict(id=eid)];o['issues'][0]['location']=dict(start=1,end=1,unit='lines');obj,fs=parse_review(dict(text=json.dumps(o)),c,ctx);self.assertEqual(obj['issues'][0]['candidate_excerpt'],c.code.splitlines(keepends=True)[0]);self.assertTrue(fs)
 def test_context_disposition_has_no_code_location(self):
  c,ctx,ledger=self.first();c,ctx,state,wire,req=self.capture(ledger,ctx,c);e=next(e for e in wire['evidence_catalog']['entries'] if e['kind']=='SOURCE');raw=dict(assessment='HUMAN_REVIEW_REQUIRED',issues=[],questions=[],question_review=[dict(id='Q1',disposition='STILL_UNRESOLVED',why='The synthetic ownership remains unspecified.',evidence=[e['evidence_id']])]);obj,audit,errors=validate_review(dict(text=json.dumps(raw)),c,ctx,request_body=state);self.assertFalse(errors,errors);self.assertTrue(obj['material_unchecked'])
 def test_all_independent_reference_errors_are_reported_without_acceptance(self):
  c,ctx,o=self.control();eid=o['issues'][0]['evidence'][0];o['issues'][0]['evidence']=[eid,dict(id=eid,start=0,end=0,quote='Fabricated synthetic quotation'),dict(id='candidate_shape',start=1,end=1,unit='lines',quote='Not exact code')];obj,audit,errors=validate_review(dict(text=json.dumps(o)),c,ctx);self.assertIsNone(obj);codes={e['code'] for e in errors};self.assertTrue({'UNKNOWN_REVIEW_FIELD','MISSING_OR_UNSUPPLIED_EVIDENCE_ID','INVALID_EVIDENCE_SPAN','INVALID_SOURCE_QUOTATION'}<=codes,codes)
  self.assertTrue(any(e['path'].endswith('evidence[2].unit') for e in errors))
 def test_correction_guidance_is_specific_and_preserves_shared_bound(self):
  errors=[dict(code='MISSING_OR_UNSUPPLIED_EVIDENCE_ID',path='$.question_review[0].evidence[0]',expected='Supplied E ID')];text=response_correction_instruction(errors);self.assertIn('Evidence fields accept only supplied E IDs',text);self.assertIn('issues[].location',text);self.assertIn('questions/dispositions need no code location',text);self.assertNotIn('Pair each comparison operand',text);self.assertNotIn('Evidence fields',response_correction_instruction([dict(code='MISSING_REVIEW_FIELD',path='$.assessment')]))
 def test_shared_initial_request_is_unchanged_between_methods(self):
  ctx=self.s.context('NOVEL-RULE');cfg=self.p.config('configs/nltl.json');settings={k:cfg[k] for k in ['model','generation_max_tokens','review_max_tokens']};one=initial_request(self.p,ctx,settings);two=initial_request(self.p,copy.deepcopy(ctx),copy.deepcopy(settings));self.assertEqual(one,two)
 def test_repair_prompt_and_packet_preserve_full_code_and_original_diagnostics(self):
  ctx=self.s.context('NOVEL-RULE');c=Candidate(1,base.GOOD,'');f=finding(c,'PARSE_ERROR','Synthetic diagnostic',diagnostic='Exact parser diagnostic: original punctuation.',suggestion='Repair only the indicated syntax.');q=repair_request(self.p,ctx,c,[f]);assert_integrity(q,c,[f]);self.assertEqual(q['payload']['previous_candidate'],c.code);self.assertEqual(q['payload']['current_findings'][0]['diagnostic'],f.diagnostic);self.assertIn('COMPLETE revised SHACL',q['system']);self.assertIn('Preserve unaffected obligations',q['system']);self.assertIn('Never delete constraints merely to pass checks',q['system'])
