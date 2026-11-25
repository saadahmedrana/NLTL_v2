"""Generic context-question state controls; no regulatory solutions or model calls."""
import copy,json,pathlib,unittest
import test_general_pipeline as base
from test_semantic_handoff import answer
from nltlv2.core import Candidate,finding
from nltlv2.runner import Runner
from nltlv2.review_protocol import reviewer_schema
from nltlv2.review_validation import validate_review
from nltlv2.requests import parse_review,repair_request
from nltlv2.evidence import evidence_catalog,assert_review_packet
from nltlv2.context_resolution import unresolved_questions,remember_question_review,record_question_retrieval
from nltlv2.tracking import Tracker

class QuestionHistoryControls(unittest.TestCase):
 setUp=base.GeneralPipelineTests.setUp;tearDown=base.GeneralPipelineTests.tearDown;write=base.GeneralPipelineTests.write
 def capture(self,ledger=None,ctx=None,c=None):
  ctx=ctx or self.s.context('NOVEL-RULE');c=c or Candidate(1,base.GOOD,'');cfg=self.p.config('configs/nltl.json');cfg['review_contract_version']=4;dest=self.root/'outputs'/('capture'+str(len(list((self.root/'outputs').iterdir()))));dest.mkdir();r=Runner(self.p,cfg,object(),dest);r.context_questions=copy.deepcopy(ledger or {});saved={}
  class Capture(Exception):pass
  def dispatch(q,latest=None):saved.update(request=q);raise Capture()
  r.dispatch=dispatch
  try:r.review(c,ctx,None,{'status':'INITIAL','changes':[]},Tracker(),[])
  except Capture:pass
  state=json.loads((dest/'review_state_001.json').read_text());return c,ctx,state,json.loads(saved['request']['user']),saved['request']
 def first(self):
  c,ctx,state,wire,req=self.capture();e=next(e for e in wire['evidence_catalog']['entries'] if e['kind']=='SOURCE');raw=dict(assessment='HUMAN_REVIEW_REQUIRED',issues=[],questions=[dict(missing='Whether the synthetic source imposes a maximum count',why='Need to distinguish a recording duty from an extra restriction',kind='source',evidence=[e['evidence_id']])]);obj,_=parse_review({'text':json.dumps(raw)},c,ctx,request_body=state);ledger=remember_question_review({},obj,c,{'request_id':state['review_request_id'],'sequence':1},state['evidence_catalog']);return c,ctx,ledger
 def disposition(self,wire,state='RESOLVED',assessment='APPROVE'):
  e=next(e for e in wire['evidence_catalog']['entries'] if e['kind']=='SOURCE');return dict(assessment=assessment,issues=[],questions=[],question_review=[dict(id=q['id'],disposition=state,why='The supplied synthetic source explicitly imposes no maximum; this answers or withdraws the concern.',evidence=[e['evidence_id']]) for q in wire['prior_context_questions']])
 def validate(self,raw,c,ctx,state):return validate_review({'text':json.dumps(raw)},c,ctx,request_body=state)
 def test_original_text_origin_and_evidence_persist(self):
  c,ctx,ledger=self.first();q=next(iter(ledger.values()));self.assertEqual(q['id'],'Q1');self.assertEqual(q['originating_candidate'],dict(version=1,sha256=c.sha256));self.assertEqual(q['missing'],'Whether the synthetic source imposes a maximum count');self.assertTrue(q['supporting_evidence'][0]['text']);self.assertIn('file',q['supporting_evidence'][0]['origin'])
 def test_initial_contract_unchanged_followup_adds_only_one_conditional_field(self):
  self.assertEqual(reviewer_schema()['required'],['assessment','issues','questions']);s=reviewer_schema(questions=['Q1']);self.assertEqual(s['required'],['assessment','issues','questions','question_review']);self.assertNotIn('reconciliations',s['properties'])
 def test_readable_followup_and_alias_remapping_preserve_provenance(self):
  c,ctx,ledger=self.first();old=unresolved_questions(ledger,ctx)[0]['supporting_evidence'][0]['reference'];changed=None
  for i in range(256):
   candidate=copy.deepcopy(ctx);candidate['ontology_evidence'].append(['<urn:extra'+str(i)+'>','<urn:p>','<urn:o>'])
   if unresolved_questions(ledger,candidate)[0]['supporting_evidence'][0]['reference']!=old:changed=candidate;break
  self.assertIsNotNone(changed);snapshot=unresolved_questions(ledger,changed);self.assertEqual(snapshot[0]['missing'],next(iter(ledger.values()))['missing']);self.assertEqual(snapshot[0]['why'],next(iter(ledger.values()))['why']);self.assertNotEqual(snapshot[0]['supporting_evidence'][0]['reference'],old);self.assertEqual(snapshot[0]['supporting_evidence'][0]['origin'],next(iter(ledger.values()))['supporting_evidence'][0]['origin'])
  _,_,state,wire,req=self.capture(ledger,changed,c);self.assertEqual(wire['prior_context_questions'],snapshot);self.assertIn('maximum count',req['user']);assert_review_packet(wire,c)
 def test_missing_original_evidence_stays_readable_without_stale_alias(self):
  c,ctx,ledger=self.first();ctx=copy.deepcopy(ctx);ctx['source_documents']=[];s=unresolved_questions(ledger,ctx);r=s[0]['supporting_evidence'][0];self.assertIsNone(r['reference']);self.assertIn(base.SOURCE,r['original_text'])
 def test_bare_approve_cannot_clear_prior_question(self):
  c,ctx,ledger=self.first();c,ctx,state,wire,req=self.capture(ledger,ctx,c);obj,audit,errors=self.validate(dict(assessment='APPROVE',issues=[],questions=[]),c,ctx,state);self.assertTrue(errors);self.assertEqual(next(iter(ledger.values()))['status'],'STILL_UNRESOLVED')
 def test_supported_resolution_and_withdrawal_close_with_model_judgment(self):
  for disposition in ['RESOLVED','WITHDRAWN']:
   c,ctx,ledger=self.first();c,ctx,state,wire,req=self.capture(ledger,ctx,c);obj,audit,errors=self.validate(self.disposition(wire,disposition),c,ctx,state);self.assertFalse(errors,errors);new=remember_question_review(ledger,obj,c,{'sequence':2},state['evidence_catalog']);self.assertEqual(unresolved_questions(new,ctx),[]);q=next(iter(new.values()));self.assertTrue(q['dispositions'][0]['interpretation_is_model_judgment']);self.assertEqual(q['missing'],next(iter(ledger.values()))['missing'])
 def test_unknown_evidence_and_missing_explanation_cannot_close(self):
  c,ctx,ledger=self.first();c,ctx,state,wire,req=self.capture(ledger,ctx,c)
  for field,val in [('evidence',['UNKNOWN']),('evidence',[]),('why','')]:
   raw=self.disposition(wire);raw['question_review'][0][field]=val;self.assertTrue(self.validate(raw,c,ctx,state)[2])
 def test_still_unresolved_is_valid_blocking_and_approve_is_invalid(self):
  c,ctx,ledger=self.first();c,ctx,state,wire,req=self.capture(ledger,ctx,c);raw=self.disposition(wire,'STILL_UNRESOLVED','HUMAN_REVIEW_REQUIRED');raw['question_review'][0].pop('evidence');obj,audit,errors=self.validate(raw,c,ctx,state);self.assertFalse(errors,errors);self.assertTrue(obj['material_unchecked']);raw['assessment']='APPROVE';self.assertIn('UNRESOLVED_QUESTION_APPROVAL',[e['code'] for e in self.validate(raw,c,ctx,state)[2]])
 def test_stale_question_id_and_stale_snapshot_cannot_close(self):
  c,ctx,ledger=self.first();c,ctx,state,wire,req=self.capture(ledger,ctx,c);raw=self.disposition(wire);raw['question_review'][0]['id']='Q999';self.assertTrue(self.validate(raw,c,ctx,state)[2]);raw=self.disposition(wire);bad=copy.deepcopy(state);bad['prior_context_questions'][0]['why']='tampered';self.assertIn('STALE_CONTEXT_QUESTION_STATE',[e['code'] for e in self.validate(raw,c,ctx,bad)[2]])
 def test_closing_and_reasking_same_question_is_a_contradiction(self):
  c,ctx,ledger=self.first();c,ctx,state,wire,req=self.capture(ledger,ctx,c);raw=self.disposition(wire,assessment='HUMAN_REVIEW_REQUIRED');q=wire['prior_context_questions'][0];raw['questions']=[dict(missing=q['missing'],why=q['why'],kind=q['kind'])];self.assertIn('CONTRADICTORY_QUESTION_DISPOSITION',[e['code'] for e in self.validate(raw,c,ctx,state)[2]])
 def test_disposition_coverage_checks_duplicates_and_omissions(self):
  c,ctx,ledger=self.first();c,ctx,state,wire,req=self.capture(ledger,ctx,c);raw=self.disposition(wire,'STILL_UNRESOLVED','HUMAN_REVIEW_REQUIRED');raw['questions']=[dict(missing='Whether the synthetic source specifies the boolean',why='Need the source meaning',kind='source')];obj,audit,errors=self.validate(raw,c,ctx,state);self.assertFalse(errors);ledger=remember_question_review(ledger,obj,c,{'sequence':2},state['evidence_catalog']);c,ctx,state,wire,req=self.capture(ledger,ctx,c);raw=self.disposition(wire);raw['question_review'][1]=copy.deepcopy(raw['question_review'][0]);self.assertIn('INCOMPLETE_QUESTION_REVIEW',[e['code'] for e in self.validate(raw,c,ctx,state)[2]])
 def test_retrieval_attempts_and_repair_packet_carry_readable_questions(self):
  c,ctx,ledger=self.first();q=next(iter(ledger.values()));event=dict(round=1,status='EVIDENCE_ADDED',novel=True,requests=[dict(kind=q['kind'],query=q['missing'],reason=q['why'])],entries=[dict(kind='schema',term_iris=['urn:binding'])]);ledger=record_question_retrieval(ledger,event,'retrieval_01.json');snapshot=unresolved_questions(ledger,ctx);self.assertEqual(snapshot[0]['retrieval_attempts'][0]['schema_terms'],1);bad=Candidate(2,base.GOOD.replace('a sh:NodeShape;','a ;'),'');f=finding(bad,'PARSE_ERROR','Generic synthetic parse failure',diagnostic='Original parser diagnostic',suggestion='Fix only syntax');packet=repair_request(self.p,ctx,bad,[f],context_questions=snapshot);self.assertEqual(packet['payload']['prior_context_questions'][0]['missing'],q['missing']);self.assertEqual(packet['payload']['previous_candidate'],bad.code)
 def test_stale_validated_result_cannot_commit_over_new_question_state(self):
  c,ctx,ledger=self.first();c,ctx,state,wire,req=self.capture(ledger,ctx,c);obj,audit,errors=self.validate(self.disposition(wire),c,ctx,state);self.assertFalse(errors);changed=copy.deepcopy(ledger);next(iter(changed.values()))['status']='WITHDRAWN'
  with self.assertRaisesRegex(ValueError,'INTEGRITY'):remember_question_review(changed,obj,c,{},state['evidence_catalog'])
 def test_repeated_bare_approve_stops_unverified_and_keeps_ledger(self):
  import test_v080 as old
  old.ResolutionControls.document(self);self.s=base.Schema(self.p)
  def handler(q,n):
   if q['route']=='generation':return base.wrap(base.GOOD)
   if n==2:return answer(q,'HUMAN_REVIEW_REQUIRED',questions=[dict(missing='Application scope',why='Need supporting source scope',kind='source',reference='UR B2')])
   return answer(q)
  cfg=self.p.config('configs/nltl.json');cfg.update(review_contract_version=4,delivery_policy='latest_technical');r,t,out=base.GeneralPipelineTests.run_local(self,handler,cfg=cfg);self.assertEqual(r['status'],'REVIEWER_FORMAT_FAILURE');self.assertEqual(r['delivery']['status'],'UNVERIFIED');self.assertEqual(r['delivery']['final_review'],'HUMAN_REVIEW_REQUIRED');self.assertTrue(r['delivery']['context_pending']);self.assertTrue((out/'context_questions.json').exists());self.assertEqual(r['repair_calls'],0);self.assertEqual(r['auxiliary_format_retries'],1)
