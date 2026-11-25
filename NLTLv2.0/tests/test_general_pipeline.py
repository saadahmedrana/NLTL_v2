import unittest,tempfile,pathlib,json,os,copy,sys,socket,dataclasses,ast
from unittest.mock import patch
from nltlv2.core import Project,GenerationProject,Candidate,finding,digest,normalize,WrapperError,offline_network_guard
from nltlv2.schema import Schema,N,Q,U
from nltlv2.runner import Runner
from nltlv2.checks import check,sparql_checks,runtime_probe
from nltlv2.requests import repair_request,assert_integrity,parse_review,ReviewerFormatError
from nltlv2.tracking import Tracker
from nltlv2.change_review import manifest
from nltlv2.transport import ScriptedTransport,LiveTransport
from nltlv2.study import budget_analysis
from nltlv2.evidence import evidence_catalog,citation_error,review_binding
PREFIX='@prefix n:<https://w3id.org/nltl/vocab#>. @prefix sh:<http://www.w3.org/ns/shacl#>. @prefix xsd:<http://www.w3.org/2001/XMLSchema#>.\n'
GOOD=PREFIX+'<urn:test:shape> a sh:NodeShape; sh:targetClass n:ship; sh:property [sh:path n:bridgeWingsEnclosed; sh:datatype xsd:boolean; sh:minCount 1; sh:hasValue true].\n'
BAD_EXTRA=GOOD.replace('sh:hasValue true]','sh:hasValue true; sh:maxCount 1]')
SOURCE='Ships shall record that bridge wings are enclosed. This source imposes no maximum count for the recorded property. Length values use metres.'
def wrap(code):return '<BEGIN_SHACL>\n'+code+'<END_SHACL>\n'
def request_data(request):
 """Test-only view of the compact wire; does not add anything to model requests."""
 data=json.loads(request['user']);data=data.get('original_request',data)
 if data.get('protocol_version')!=2:return data
 data=copy.deepcopy(data);ctx=data['context'];ctx['source_documents']=[];ctx['ontology_evidence']=[];ctx['schema_terms']=[]
 for entry in data['evidence_catalog']['entries']:
  origin=entry.get('origin',{});field=origin.get('context_field')
  if entry['kind']=='SOURCE':ctx['source_documents'].append(dict(origin,text=entry['text']))
  elif entry['kind']=='RDF_FACT':ctx['ontology_evidence'].append([t.n3() for t in __import__('nltlv2.evidence',fromlist=['ground_fact']).ground_fact(entry['text'])])
  elif field=='schema_terms':ctx['schema_terms'].append(json.loads(entry['text']))
  elif field:ctx[field]=json.loads(entry['text'])
 ctx['termOwners']=ctx.get('contract',{}).get('owners',{});ctx['modelPaths']=ctx.get('contract',{}).get('modelPaths',[])
 data['admission']=ctx.get('admission');data['deterministic_findings']=data.get('findings',[]);data['acceptance_blockers']=[x for x in data.get('findings',[]) if x['blocking']]
 if data.get('format_feedback'):
  feedback=data['format_feedback'];data.update(feedback);data['format_error']=feedback['validation_errors'][0];data['expected_structure']=data['expected_response_schema']
 return data

def bind_review_response(request,obj):
 data=request_data(request);code=data['full_candidate'];change=data.get('change_manifest',{});version=data.get('candidate_version',change.get('current_version',1));c=Candidate(version,code,'');prev=data.get('previous_candidate');previous=None if prev is None else Candidate(prev.get('version',version-1),prev['full_code'],'');context=data['context'];catalog=data.get('evidence_catalog',evidence_catalog(context,data.get('execution_probe')))
 binding={k:data[k] for k in ['candidate_version','candidate_sha256','review_request_id']} if 'review_request_id' in data else review_binding(c,context,data.get('prior_issues',[]),previous,change,data.get('execution_probe'));obj.update(binding)
 def visit(x):
  if isinstance(x,dict):
   for source,key,quote in [(True,'source_evidence_id','source_excerpt'),(False,'evidence_id','evidence_excerpt')]:
    if quote in x and key not in x:
     matches=[e for e in catalog['entries'] if citation_error(catalog,e['evidence_id'],x[quote],source=source) is None]
     if matches:x[key]=matches[0]['evidence_id']
   for v in list(x.values()):visit(v)
  elif isinstance(x,list):
   for v in x:visit(v)
 visit(obj)
 if data.get('protocol_version')==2:
  from nltlv2.evidence import code_location
  def spans(x):
   if isinstance(x,dict):
    for key,target,field in [('candidate_excerpt',c,'candidate_location'),('previous_excerpt',previous,'previous_location')]:
     quote=x.get(key) or (x.get('insertion_context') if key=='candidate_excerpt' else None)
     if target is not None and isinstance(quote,str) and quote and quote in target.code:
      start=target.code.index(quote);x[field]=code_location(target,start,start+len(quote));x.pop(key,None);x.pop('insertion_context',None)
    if 'removal_assessments' in x:
     removals=x.pop('removal_assessments');x['removal_disposition']=removals[0]['disposition'] if removals else ('SUPPORTED_REMOVAL' if any(g.get('change_id')==x.get('change_id') and g.get('removal_required') for g in change.get('changes',[])) else None)
    for value in list(x.values()):spans(value)
   elif isinstance(x,list):
    for v in x:spans(v)
  spans(obj)
 return obj
def review_response(request,decision='ACCEPT',issue=None,prior_state=None,change_state='SUPPORTED'):
 data=request_data(request);context=data['context'];code=data['full_candidate'];source=context['source_documents'][0]['text'];previous=data['previous_candidate'];changes=data['change_manifest']['changes']
 return json.dumps(bind_review_response(request,dict(decision=decision,issues=[] if issue is None else [issue],change_assessments=[dict(change_id=c['change_id'],disposition=change_state,source_excerpt=source,previous_excerpt=previous['full_code'],candidate_excerpt=code,reason='Compared actual source and candidates; removal is source-supported.',removal_assessments=[dict(alert_id=a['alert_id'],disposition='SUPPORTED_REMOVAL',source_excerpt=source,previous_excerpt=previous['full_code'],candidate_excerpt=code,reason='The synthetic source explicitly imposes no maximum count; all other constraints retained.') for a in c.get('removal_alerts',[])]) for c in changes],reconciliations=[dict(issue_id=x['issue_id'],state=prior_state or ('RESOLVED' if decision=='ACCEPT' else 'PERSISTENT'),source_excerpt=source,candidate_excerpt=code,reason='Source and current candidate compared explicitly.') for x in data['prior_issues']],unchecked=[dict(scope='Independent correctness proof',material=False,reason='Methodological limitation, not unverified implementation scope.')])))
def issue_for(request,category='SOURCE_BACKED_LOGIC_ERROR',**extra):
 data=request_data(request)
 return bind_review_response(request,{'issues':[dict(issue_id='unsupported-cardinality',category=category,source_clause='A.1',source_excerpt=SOURCE,candidate_excerpt='sh:maxCount 1' if 'sh:maxCount 1' in data['full_candidate'] else data['full_candidate'],reason='The source explicitly supplies no maximum count.',expected='No source-unsupported maximum count',suggestion='Remove only the unsupported maximum count and preserve the boolean recording obligation.',evidence_excerpt=SOURCE,**extra)]})['issues'][0]
class LocalTransport:
 def __init__(self,handler):self.handler=handler;self.calls=[]
 def dispatch(self,request,latest=None,expected_findings=None):
  if request['route'].endswith('repair'):assert_integrity(request,latest,expected_findings)
  self.calls.append(request);response=self.handler(request,len(self.calls))
  return dict(text=response,finish_reason='stop',status='completed',usage={},elapsed_seconds=0) if isinstance(response,str) else response
def software_admission(test):
 import hashlib
 source='data/requirements/source.txt';sha=hashlib.sha256((test.root/source).read_bytes()).hexdigest();catalog=json.loads((test.root/'data/requirements/source_catalog.json').read_text());title='Synthetic source document for software testing'
 catalog['sources'][title]=dict(document_id='SOFTWARE SOURCE',edition='Software edition 1',file=source,sha256=sha,authority='Software test author',provenance={'kind':'Synthetic source only'})
 test.write('data/requirements/source_catalog.json',catalog);(test.root/'data/admissions').mkdir(exist_ok=True)
 value=dict(format_version=2,admission_id='software-population',interpretation='A',population_description='Synthetic software records; no regulatory eligibility claim',focus_set=dict(mode='COMPLETE_CLASS_POPULATION_PER_INPUT',owner_class=str(N.ship)),eligibility_assertion='ASSUMED_EXTERNAL_RESEARCH_ELIGIBILITY',approval=dict(status='APPROVED',approved_by='Synthetic software test caller',reference='Synthetic approval control only'),provenance=dict(declarant='Software test caller',reference='Synthetic control',basis='Explicit test population declaration, never evaluation labels'),source_editions=[dict(document_id='SOFTWARE SOURCE',edition='Software edition 1',file=source,sha256=sha,selection_provenance='Software test caller selects synthetic source')])
 test.write('data/admissions/software.json',value);return value
class GeneralPipelineTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name).resolve();self.p=Project.__new__(Project);self.p.root=self.root
  project=pathlib.Path(os.environ.get('NLTL_TEST_PROJECT',str(pathlib.Path(__file__).resolve().parents[1])))
  self.root.joinpath('pyproject.toml').write_text('[project]\nname="offline-generic"\nversion="0.0.0"\n')
  for name in ['schema','data/requirements','prompts','configs','evaluation','tests/data','outputs']:self.root.joinpath(name).mkdir(parents=True,exist_ok=True)
  ontology="""@prefix n:<https://w3id.org/nltl/vocab#>. @prefix owl:<http://www.w3.org/2002/07/owl#>. @prefix rdfs:<http://www.w3.org/2000/01/rdf-schema#>. @prefix xsd:<http://www.w3.org/2001/XMLSchema#>. n:ship a owl:Class. n:bridgeWingsEnclosed a owl:DatatypeProperty; rdfs:domain n:ship; rdfs:range xsd:boolean. n:probeLength a owl:ObjectProperty. n:shipCategory a owl:ObjectProperty. n:probeClass a owl:Class. n:a a n:probeClass. n:b a n:probeClass. n:component a owl:Class. n:specialComponent a owl:Class; rdfs:subClassOf n:component. n:hasComponent a owl:ObjectProperty; rdfs:range n:component. n:componentValue a owl:DatatypeProperty; rdfs:range xsd:boolean. <http://qudt.org/schema/qudt/QuantityValue> a owl:Class."""
  (self.root/'schema/Schema_for_NLTL.ttl').write_text(ontology)
  terms=[dict(localName='bridgeWingsEnclosed',iri=str(N.bridgeWingsEnclosed),kind='DatatypeProperty',datatype='xsd:boolean'),dict(localName='probeLength',iri=str(N.probeLength),kind='QuantityProperty',parentOrRange=str(Q.QuantityValue),unitIri=str(U.M)),dict(localName='shipCategory',iri=str(N.shipCategory),kind='ObjectProperty')]
  self.write('schema/term_registry.json',terms);self.write('schema/representation_bindings.json',{'requirements':{}});self.write('schema/locked_representation_context.jsonld',{'@context':{'qudt':str(Q),'unit':{'@id':'qudt:unit','@type':'@id'},'xsd':str(__import__('rdflib').XSD),'numericValue':{'@id':'qudt:numericValue','@type':'xsd:decimal'}}})
  self.write('data/requirements/requirements.json',{'NOVEL-RULE':dict(id='NOVEL-RULE',source='Synthetic source document for software testing',clause='A.1',text=SOURCE,source_file='data/requirements/source.txt',normalized='MUST_NOT_LEAK_HANDWRITTEN_NORMALIZATION',solution_profile='MUST_NOT_LEAK')});self.write('data/requirements/source_catalog.json',{'sources':{}});(self.root/'data/requirements/source.txt').write_text(SOURCE)
  for name in ['generator','reviewer','repair']:(self.root/f'prompts/{name}.txt').write_text((project/f'prompts/{name}.txt').read_text())
  for method,file in [('NLTL','nltl'),('Single-shot','single_shot')]:self.write('configs/'+file+'.json',dict(review_contract_version=3,method=method,model='SCRIPTED-OFFLINE',generation_max_tokens=1000,review_max_tokens=1000,review_format_retries=1,review_max_issues=8,maximum_candidate_attempts=6 if method=='NLTL' else 1,semantic_review=method=='NLTL',fresh_regeneration=False,stagnation={'enabled':False}))
  (self.root/'evaluation/labels.json').write_text('FORBIDDEN_EVALUATION_GOLD');(self.root/'tests/data/per_regulation_witnesses.json').write_text('FORBIDDEN_WITNESS_GOLD');self.s=Schema(self.p)
 def tearDown(self):self.tmp.cleanup()
 def write(self,name,obj):self.root.joinpath(name).write_text(json.dumps(obj))
 def run_local(self,handler,method='NLTL',cfg=None):
  out=self.root/'outputs'/('run'+str(len(list((self.root/'outputs').iterdir()))));out.mkdir();t=LocalTransport(handler)
  config=cfg or self.p.config('configs/'+('nltl' if method=='NLTL' else 'single_shot')+'.json')
  if 'admission_file' not in config:software_admission(self);config=dict(config,admission_file='data/admissions/software.json')
  with offline_network_guard():result=Runner(self.p,config,t,out).run('NOVEL-RULE')
  return result,t,out
 def accepting(self,r,i):return wrap(GOOD) if r['route']=='generation' or r['route'].endswith('repair') else review_response(r)
 def test_novel_requirement_without_profile_or_witness_and_filesystem_denial(self):
  enabled=[True];denied=[self.root/'evaluation',self.root/'tests',self.root/'data/contracts']
  def audit(event,args):
   if enabled[0] and event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
    p=pathlib.Path(os.fsdecode(args[0])).resolve()
    if any(p==d or p.is_relative_to(d) for d in denied):raise RuntimeError('TEST_FORBIDDEN_INPUT_ACCESS')
  sys.addaudithook(audit)
  try:r,t,out=self.run_local(self.accepting)
  finally:enabled[0]=False
  self.assertEqual(r['status'],'ACCEPTED');self.assertEqual(r['accepted_version'],1);self.assertFalse(r['complete_verification']);self.assertFalse(r['behavioral_gold_consulted']);self.assertEqual(r['generation_calls'],1)
  joined=json.dumps(t.calls);self.assertNotIn('FORBIDDEN_',joined);self.assertNotIn('MUST_NOT_LEAK',joined);self.assertNotIn('sourceBackedObligations',joined);self.assertEqual(self.s.context('NOVEL-RULE')['termOwners'],{})
  if os.environ.get('NLTL_TEST_OUTPUT'):
   import shutil;shutil.copytree(out,pathlib.Path(os.environ['NLTL_TEST_OUTPUT'])/'novel_rule_representative',dirs_exist_ok=False)
 def test_both_methods_identical_initial_context_and_settings(self):
  a,ta,_=self.run_local(self.accepting);b,tb,_=self.run_local(self.accepting,'Single-shot');self.assertEqual(ta.calls[0],tb.calls[0]);self.assertEqual(len(tb.calls),1);self.assertEqual(b['status'],'SINGLE_SHOT_COMPLETE')
 def test_single_shot_never_checks_or_reviews(self):
  with patch('nltlv2.runner.check',side_effect=AssertionError('checker called')),patch('nltlv2.runner.runtime_probe',side_effect=AssertionError('probe called')):r,t,_=self.run_local(lambda r,i:'malformed original response','Single-shot')
  self.assertEqual(len(t.calls),1);self.assertEqual(r['evaluation_candidate'],1);self.assertEqual(r['history'][0]['status'],'FORMAT_ERROR')  # Preserve original for identical external parse/execution diagnostics.
 def test_source_grounded_removal_without_permissions(self):
  def handler(r,i):
   if r['route']=='generation':return wrap(BAD_EXTRA)
   if r['route'].endswith('repair'):
    self.assertEqual(r['payload']['previous_candidate'],BAD_EXTRA);self.assertNotIn('validated_constraint_changes',r['payload']);self.assertFalse(r['payload']['current_findings'][-1]['confirmed']);return wrap(GOOD)
   return review_response(r,'REJECT',issue_for(r)) if json.loads(r['user'])['candidate_version']==1 else review_response(r)
  result,t,out=self.run_local(handler);self.assertEqual(result['accepted_version'],2,json.dumps(result));self.assertEqual(result['repair_calls'],1);self.assertTrue(result['history'][1]['changes']['resolved']);self.assertEqual(result['history'][0]['findings'][-1]['assessment'],'MODEL_INTERPRETATION');self.assertTrue((out/'diff_01_02.patch').is_file());self.assertTrue(result['history'][1]['structural_change_manifest']['changes'])
  if os.environ.get('NLTL_TEST_OUTPUT'):
   import shutil;shutil.copytree(out,pathlib.Path(os.environ['NLTL_TEST_OUTPUT'])/'source_grounded_repair_representative')
 def test_latest_full_candidate_chained_repairs(self):
  bad=GOOD.replace('a sh:NodeShape;','a ;');middle=BAD_EXTRA
  def handler(r,i):
   if r['route']=='generation':return wrap(bad)
   if r['route'].endswith('repair'):return wrap(middle) if r['payload']['candidate_version']==1 else wrap(GOOD)
   return review_response(r,'REJECT',issue_for(r)) if json.loads(r['user'])['candidate_version']==2 else review_response(r)
  r,t,_=self.run_local(handler);self.assertEqual(r['accepted_version'],3,json.dumps(r));rep=[q for q in t.calls if q['route'].endswith('repair')];self.assertEqual([q['payload']['previous_candidate'] for q in rep],[bad,middle]);self.assertEqual([q['payload']['candidate_sha256'] for q in rep],[digest(bad),digest(middle)])
 def test_exact_parser_diagnostic(self):
  c=Candidate(1,GOOD.replace('a sh:NodeShape;','a ;'),'');fs=check(c,self.s,'NOVEL-RULE');self.assertEqual(fs[0].category,'PARSE_ERROR');self.assertTrue(fs[0].diagnostic);self.assertTrue(fs[0].location);self.assertEqual(fs[0].candidate_sha256,c.sha256)
 def test_canonical_namespace_correction(self):
  c=Candidate(1,GOOD.replace('n:bridgeWingsEnclosed','q:bridgeWingsEnclosed').replace('@prefix n:', '@prefix q:<http://qudt.org/schema/qudt/>. @prefix n:'),'');f=[f for f in check(c,self.s,'NOVEL-RULE') if f.category=='CANONICAL_IDENTIFIER_ERROR'];self.assertTrue(f);self.assertEqual(f[0].expected,str(N.bridgeWingsEnclosed))
 def test_term_kind_and_datatype(self):
  c=Candidate(1,GOOD.replace('n:bridgeWingsEnclosed','n:shipCategory'),'');self.assertIn('TERM_KIND_ERROR',[f.category for f in check(c,self.s,'NOVEL-RULE')])
 def test_unit_scale_not_renaming(self):
  code=PREFIX+'@prefix q:<http://qudt.org/schema/qudt/>. <urn:s> a sh:NodeShape; sh:targetClass n:ship; sh:property [sh:path n:probeLength; sh:node [sh:property [sh:path q:unit; sh:hasValue <http://qudt.org/vocab/unit/MilliM>]]].'
  fs=check(Candidate(1,code,''),self.s,'NOVEL-RULE');self.assertTrue(any(f.category=='UNIT_CONSISTENCY_ERROR' for f in fs))
 def test_numeric_identity_is_review_notice_not_handwritten_answer(self):
  code=PREFIX+'@prefix q:<http://qudt.org/schema/qudt/>. <urn:s> a sh:NodeShape; sh:targetClass n:ship; sh:property [sh:path q:numericValue; sh:hasValue "17.00"^^xsd:decimal].';f=[x for x in check(Candidate(1,code,''),self.s,'NOVEL-RULE') if x.category=='NUMERIC_TERM_REVIEW'];self.assertTrue(f);self.assertFalse(f[0].blocking);self.assertFalse(f[0].confirmed)
 def test_unknown_owner_is_explicit_not_ship_fallback(self):
  context=self.s.context('NOVEL-RULE');self.assertEqual(context['termOwners'],{});self.assertIsNone(self.s.allowed_paths('NOVEL-RULE')[0]);fs=check(Candidate(1,GOOD,''),self.s,'NOVEL-RULE');self.assertTrue(any(f.assessment=='UNSPECIFIED_REPRESENTATION' and not f.blocking for f in fs))
 def test_explicit_path_and_subclass_routes(self):
  self.write('schema/representation_bindings.json',{'requirements':{'NOVEL-RULE':{'terms':['componentValue'],'owners':{'hasComponent':'ship','componentValue':'specialComponent'},'target_owner':'ship','model_paths':[dict(fromOwner='ship',via='hasComponent',toOwner='component')]}}});s=Schema(self.p);root,paths=s.allowed_paths('NOVEL-RULE');self.assertEqual(root,'ship');self.assertIn((str(N.hasComponent),str(N.componentValue)),paths[str(N.componentValue)])
 def test_format_retry_separate_from_candidate_attempt(self):
  def handler(r,i):
   if r['route']=='generation':return wrap(GOOD)
   if r['route']=='review':return '{truncated'
   return review_response(r)
  r,t,_=self.run_local(handler);self.assertEqual(r['accepted_version'],1);self.assertEqual(r['auxiliary_format_retries'],1);self.assertEqual(r['generation_calls'],1);self.assertEqual(len(t.calls),3)
 def test_bounded_invalid_reviewer_failure(self):
  r,t,_=self.run_local(lambda r,i:wrap(GOOD) if r['route']=='generation' else '{bad');self.assertEqual(r['status'],'REVIEWER_FORMAT_FAILURE');self.assertEqual(len(t.calls),3);self.assertEqual(r['candidate_attempts'],1)
 def test_truncated_reviewer_keeps_raw_finish_reason(self):
  cfg=self.p.config('configs/nltl.json');cfg['review_format_retries']=0
  r,t,out=self.run_local(lambda r,i:wrap(GOOD) if r['route']=='generation' else dict(text='{}',status='incomplete',finish_reason='max_output_tokens'),cfg=cfg);self.assertEqual(r['status'],'REVIEWER_FORMAT_FAILURE');log=json.loads((out/'reviewer_format_failure_002.json').read_text());self.assertEqual(log['raw_response']['finish_reason'],'max_output_tokens')
 def test_source_quotation_must_be_exact(self):
  c=Candidate(1,BAD_EXTRA,'');ctx=self.s.context('NOVEL-RULE');r=dict(user=json.dumps(dict(context=ctx,full_candidate=BAD_EXTRA,previous_candidate=None,change_manifest={'changes':[]},prior_issues=[])));issue=issue_for(r);issue['source_excerpt']='not actually present';obj=json.loads(review_response(r,'REJECT',issue))
  with self.assertRaisesRegex(ReviewerFormatError,'SOURCE_QUOTATION'):parse_review({'text':json.dumps(obj)},c,ctx)
 def test_missing_constraint_has_real_insertion_context(self):
  c=Candidate(1,GOOD,'');ctx=self.s.context('NOVEL-RULE');r=dict(user=json.dumps(dict(context=ctx,full_candidate=GOOD,previous_candidate=None,change_manifest={'changes':[]},prior_issues=[])));issue=issue_for(r);issue['candidate_excerpt']='';issue['insertion_context']='<urn:test:shape>';obj=json.loads(review_response(r,'REJECT',issue));_,fs=parse_review({'text':json.dumps(obj)},c,ctx);self.assertEqual(fs[0].excerpt,'');self.assertIn('insertion context',fs[0].location)
 def test_accept_cannot_skip_change_review(self):
  c=Candidate(2,GOOD,'');old=Candidate(1,BAD_EXTRA,'');ctx=self.s.context('NOVEL-RULE');obj=bind_review_response({'user':json.dumps(dict(context=ctx,full_candidate=c.code,candidate_version=c.version,previous_candidate=dict(version=old.version,full_code=old.code),change_manifest=manifest(old,c),prior_issues=[]))},dict(decision='ACCEPT',issues=[],change_assessments=[],reconciliations=[],unchecked=[]))
  with self.assertRaisesRegex(ReviewerFormatError,'CHANGE_REVIEW'):parse_review({'text':json.dumps(obj)},c,ctx,previous=old,changes=manifest(old,c))
 def test_accept_cannot_hide_unresolved_change(self):
  old=Candidate(1,BAD_EXTRA,'');c=Candidate(2,GOOD,'');ctx=self.s.context('NOVEL-RULE');r={'user':json.dumps(dict(context=ctx,full_candidate=GOOD,previous_candidate={'full_code':BAD_EXTRA},change_manifest=manifest(old,c),prior_issues=[]))};raw=review_response(r,change_state='UNRESOLVED')
  with self.assertRaisesRegex(ReviewerFormatError,'UNRESOLVED'):parse_review({'text':raw},c,ctx,previous=old,changes=manifest(old,c))
 def test_conflicting_schema_advice_stops_dispatch(self):
  def handler(r,i):
   if r['route']=='generation':return wrap(GOOD)
   issue=issue_for(r,property=str(N.probeLength),proposed_unit=str(U.MilliM));return review_response(r,'REJECT',issue)
  result,t,_=self.run_local(handler);self.assertEqual(result['status'],'CONFLICT');self.assertEqual(len(t.calls),2)
 def test_uncertain_context_stops_instead_of_inventing_rule(self):
  def handler(r,i):return wrap(GOOD) if r['route']=='generation' else review_response(r,'UNRESOLVED',issue_for(r,'UNRESOLVED_CONTEXT'))
  r,t,_=self.run_local(handler);self.assertEqual(r['status'],'UNRESOLVED_CONTEXT');self.assertEqual(len(t.calls),2)
 def test_prior_model_issue_unassessable_without_new_review(self):
  tr=Tracker();a=Candidate(1,GOOD,'');f=finding(a,'SOURCE_BACKED_LOGIC_ERROR','interpretation',assessment='MODEL_INTERPRETATION',contract_id='source',obligation_id='stable',check_id='semantic');tr.observe(a,[f]);b=Candidate(2,GOOD+'\n','');states,_=tr.observe(b,[],static_complete=False);self.assertEqual(len(states['unassessable']),1);self.assertFalse(states['resolved'])
 def test_issue_resolution_and_regression_explicit(self):
  tr=Tracker();a=Candidate(1,GOOD,'');f=finding(a,'SOURCE_BACKED_LOGIC_ERROR','interpretation',assessment='MODEL_INTERPRETATION',contract_id='source',obligation_id='stable',check_id='semantic');tr.observe(a,[f]);b=Candidate(2,GOOD+'\n','');states,_=tr.observe(b,[],review={'reconciliations':[{'issue_id':'stable','state':'RESOLVED'}]});self.assertTrue(states['resolved']);c=Candidate(3,GOOD,'');states,_=tr.observe(c,[dataclasses.replace(f,version=3)]);self.assertTrue(states['regressed'])
 def test_semantic_slot_exhaustion_and_no_workflow_credit(self):
  def handler(r,i):
   if r['route']=='generation' or r['route'].endswith('repair'):return wrap(BAD_EXTRA)
   return review_response(r,'REJECT',issue_for(r))
  r,t,_=self.run_local(handler);self.assertEqual(r['status'],'REPAIR_TYPE_LIMIT_EXHAUSTED');self.assertEqual(r['candidate_attempts'],2);self.assertEqual(r['repair_calls'],1);self.assertEqual(r['repair_counts'],{'technical':0,'semantic':1});self.assertIsNone(r['evaluation_candidate']);self.assertTrue(r['history'][-1]['persistent_failure_summary']['repeat_detection']['consecutive_same_failure_set']>=2)
 def test_stagnation_is_explicit_configurable(self):
  cfg=self.p.config('configs/nltl.json');cfg['stagnation']={'enabled':True,'repeated_failure_set_limit':2}
  def handler(r,i):return wrap(BAD_EXTRA) if r['route']=='generation' or r['route'].endswith('repair') else review_response(r,'REJECT',issue_for(r))
  r,t,_=self.run_local(handler,cfg=cfg);self.assertEqual(r['status'],'STAGNATION_STOP');self.assertEqual(r['candidate_attempts'],2);self.assertEqual(cfg['maximum_candidate_attempts'],6)
 def test_runtime_error_is_not_conformance(self):
  code=GOOD.replace('sh:minCount 1','sh:minCount "bad"');fs,probe=runtime_probe(Candidate(1,code,''),self.s);self.assertTrue(fs);self.assertTrue(probe['not_conformance'])
 def test_runtime_timeout_stops_no_retry(self):
  with patch('nltlv2.runner.runtime_probe',side_effect=TimeoutError('software-test timeout')):r,t,_=self.run_local(self.accepting)
  self.assertEqual(r['status'],'RESOURCE_ATTRIBUTION_UNCERTAIN');self.assertEqual(len(t.calls),1)
 def test_source_mutation_integrity_stops_before_review(self):
  def handler(r,i):(self.root/'data/requirements/source.txt').write_text('changed');return wrap(GOOD)
  r,t,_=self.run_local(handler);self.assertEqual(r['status'],'REQUEST_INTEGRITY_FAILURE');self.assertEqual(len(t.calls),1)
 def test_wrapper_alternate_close_preserves_body(self):
  raw=wrap(GOOD).replace('<END_SHACL>','</END_SHACL>');code,m=normalize(raw);self.assertEqual(code,GOOD);self.assertTrue(m['alternate_closing_marker'])
 def test_multiple_wrappers_rejected(self):
  with self.assertRaises(WrapperError):normalize(wrap(GOOD)+wrap(GOOD))
 def test_feedback_full_code_and_same_version_enforced(self):
  c=Candidate(3,GOOD,wrap(GOOD));f=finding(c,'PARSE_ERROR','original log',suggestion='fix');q=repair_request(GenerationProject(self.root),self.s.context('NOVEL-RULE'),c,[f]);assert_integrity(q,c,[f])
  for field,value in [('previous_candidate',GOOD[:-3]),('candidate_version',2),('candidate_sha256','bad')]:
   bad=copy.deepcopy(q);bad['payload'][field]=value;bad['user']=json.dumps(bad['payload'])
   with self.assertRaises(ValueError):assert_integrity(bad,c,[f])
 def test_diagnostics_cannot_be_relabelled(self):
  c=Candidate(1,GOOD,'');f=finding(c,'PARSE_ERROR','actual',suggestion='fix');q=repair_request(GenerationProject(self.root),self.s.context('NOVEL-RULE'),c,[f]);q['payload']['current_findings'][0]['diagnostic']='different';q['user']=json.dumps(q['payload'])
  with self.assertRaisesRegex(ValueError,'FEEDBACK'):assert_integrity(q,c,[f])
 def test_legacy_permission_packet_rejected(self):
  c=Candidate(1,GOOD,'');f=finding(c,'PARSE_ERROR','actual',suggestion='fix');q=repair_request(GenerationProject(self.root),self.s.context('NOVEL-RULE'),c,[f]);q['payload']['validated_constraint_changes']=[];q['user']=json.dumps(q['payload'])
  with self.assertRaisesRegex(ValueError,'LEGACY'):assert_integrity(q,c,[f])
 def test_reviewer_cannot_silently_erase_old_issue(self):
  c=Candidate(2,GOOD,'');ctx=self.s.context('NOVEL-RULE');obj=bind_review_response({'user':json.dumps(dict(context=ctx,full_candidate=c.code,candidate_version=c.version,previous_candidate=None,change_manifest={'changes':[]},prior_issues=[{'issue_id':'old'}]))},{'decision':'ACCEPT','issues':[],'change_assessments':[],'reconciliations':[],'unchecked':[]})
  with self.assertRaisesRegex(ReviewerFormatError,'PRIOR_ISSUE'):parse_review({'text':json.dumps(obj)},c,ctx,prior_issues=[{'issue_id':'old'}])
 def test_paths_to_tests_gold_history_and_contract_answers_denied(self):
  p=GenerationProject(self.root)
  for f in ['evaluation/labels.json','tests/data/per_regulation_witnesses.json','data/contracts/development_witness_contracts.json','schema/provenance/old.json','mappings/cases.json','outputs/old.json']:
   with self.assertRaisesRegex(ValueError,'FORBIDDEN'):p.path(f)
 def test_no_legacy_seed_config_or_reviewless_nltl(self):
  c=self.p.config('configs/nltl.json');c['seed_candidate']={'path':'anything'};self.write('configs/bad.json',c)
  with self.assertRaisesRegex(ValueError,'LEGACY'):self.p.config('configs/bad.json')
  c.pop('seed_candidate');c['semantic_review']=False;self.write('configs/bad.json',c)
  with self.assertRaisesRegex(ValueError,'REQUIRES'):self.p.config('configs/bad.json')
 def test_no_source_document_no_dispatch(self):
  self.write('data/requirements/requirements.json',{'NOVEL-RULE':dict(id='NOVEL-RULE',clause='A.1',text=SOURCE)})
  software_admission(self)
  # Missing source identity is now an earlier admission blocker, with zero dispatch.
  result=Runner(self.p,self.p.config('configs/nltl.json'),LocalTransport(self.accepting),self.root/'outputs').run('NOVEL-RULE')
  self.assertEqual(result['status'],'UNRESOLVED_ADMISSION');self.assertEqual(result['generation_calls'],0)
 def test_runtime_does_not_import_solution_modules(self):
  forbidden={'nltlv2.development_checks','nltlv2.constraint_changes','nltlv2.enumerations','nltlv2.evaluation','nltlv2.preflight'};self.assertFalse(forbidden&set(sys.modules))
 def test_budget_analysis_uses_first_acceptance_and_total_attempt_time(self):
  h={'requirement_id':'generic','history':[dict(attempt=i,version=i,accepted=i==3,elapsed_seconds=2,request_metrics=[dict(elapsed_seconds=1,usage={})],external_score=100-i) for i in range(1,7)]};r=budget_analysis([h]);self.assertEqual([x['selected_version'] for x in r],[None,3,3,3,3]);self.assertEqual(r[0]['runtime_seconds'],4);self.assertEqual(r[0]['provider_seconds'],2)
 def test_stale_feedback_rejected_before_render(self):
  c=Candidate(1,GOOD,'');f=finding(c,'PARSE_ERROR','actual',suggestion='fix')
  with self.assertRaisesRegex(ValueError,'STALE'):repair_request(GenerationProject(self.root),self.s.context('NOVEL-RULE'),Candidate(2,GOOD,''),[f])
 def test_cosmetic_change_does_not_create_regulatory_permission(self):
  a=Candidate(1,GOOD,'');b=Candidate(2,GOOD.replace('sh:minCount 1','sh:message "comment"; sh:minCount 1'),'');m=manifest(a,b);self.assertEqual(m['changes'],[]);self.assertNotIn('authorizations',m)
 def test_foreign_namespace_property_typo_detected(self):
  code=GOOD.replace('n:bridgeWingsEnclosed','<https://wrong.invalid/bridgeWingsEnclosed>');fs=check(Candidate(1,code,''),self.s,'NOVEL-RULE');self.assertTrue(any(f.category=='CANONICAL_IDENTIFIER_ERROR' and f.expected==str(N.bridgeWingsEnclosed) for f in fs))
 def test_ontology_declared_property_kind_without_registry_row(self):
  code=GOOD.replace('n:bridgeWingsEnclosed','n:hasComponent');fs=check(Candidate(1,code,''),self.s,'NOVEL-RULE');self.assertTrue(any(f.category=='TERM_KIND_ERROR' for f in fs))
 def test_rule_execution_scope_not_silently_accepted(self):
  code=GOOD+'<urn:rule> sh:construct "CONSTRUCT { $this <urn:p> ?v } WHERE {$this <urn:q> ?v}" .';fs=check(Candidate(1,code,''),self.s,'NOVEL-RULE');self.assertTrue(any(f.category=='UNRESOLVED_CONTEXT' and f.blocking for f in fs))
 def test_model_finding_never_independently_verified(self):
  c=Candidate(1,BAD_EXTRA,'');ctx=self.s.context('NOVEL-RULE');r={'user':json.dumps(dict(context=ctx,full_candidate=BAD_EXTRA,previous_candidate=None,change_manifest={'changes':[]},prior_issues=[]))};obj,fs=parse_review({'text':review_response(r,'REJECT',issue_for(r))},c,ctx);self.assertFalse(fs[0].confirmed);self.assertEqual(fs[0].assessment,'MODEL_INTERPRETATION');self.assertIn('NOT_INDEPENDENT',obj['epistemic_status'])
 def test_supporting_source_documents_are_source_not_solutions(self):
  (self.root/'data/requirements/reference.txt').write_text('Referenced provision: retain the declared unit.')
  rows=json.loads((self.root/'data/requirements/requirements.json').read_text());rows['NOVEL-RULE']['supporting_sources']=[{'file':'data/requirements/reference.txt'}];self.write('data/requirements/requirements.json',rows)
  ctx=Schema(self.p).context('NOVEL-RULE');self.assertEqual(len(ctx['source_documents']),2);self.assertIn('Referenced provision',ctx['source_documents'][1]['text'])
 def test_representation_file_rejects_embedded_solution(self):
  self.write('schema/representation_bindings.json',{'requirements':{'NOVEL-RULE':{'terms':[],'expected_verdict':True}}})
  with self.assertRaisesRegex(ValueError,'NON_REPRESENTATION'):Schema(self.p)
 def test_multiple_issues_at_same_location_not_collapsed(self):
  c=Candidate(1,GOOD,'');a=finding(c,'SOURCE_BACKED_LOGIC_ERROR','first',location='same',assessment='MODEL_INTERPRETATION',contract_id='source',obligation_id='first',check_id='semantic');b=finding(c,'SOURCE_BACKED_LOGIC_ERROR','second',location='same',assessment='MODEL_INTERPRETATION',contract_id='source',obligation_id='second',check_id='semantic');t=Tracker();states,_=t.observe(c,[a,b]);self.assertEqual(len(states['new']),2);self.assertEqual(len(t.prior_semantic_issues()),2)
if __name__=='__main__':unittest.main()
